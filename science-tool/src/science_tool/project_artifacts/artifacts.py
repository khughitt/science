"""High-level operations: install / check / diff (CLI-orchestration layer).

Functions here compose loader + status + install_matrix + worktree primitives
into a stable API the CLI verbs call.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.header import header_bytes, parse_header
from science_tool.project_artifacts.install_matrix import Action, decide
from science_tool.project_artifacts.paths import canonical_path
from science_tool.project_artifacts.registry_schema import Artifact, Pin
from science_tool.project_artifacts.status import classify_full


@dataclass(frozen=True)
class InstallResult:
    action: Action
    reason: str
    install_target: Path
    backup: Path | None = None  # populated for FORCE_ADOPT


class InstallError(Exception):
    """Raised when install refuses (REFUSE_*) or fails."""


def install_artifact(
    artifact: Artifact,
    project_root: Path,
    *,
    pins: list[Pin] | None = None,
    adopt: bool = False,
    force_adopt: bool = False,
) -> InstallResult:
    """Install or refuse per the install matrix; perform side effects."""
    target = project_root / artifact.install_target
    classified = classify_full(target, artifact, pins or [])

    file_bytes = target.read_bytes() if target.exists() else b""
    parsed = parse_header(file_bytes, artifact.header_protocol) if file_bytes else None
    header_present = parsed is not None
    wrong_name = parsed is not None and parsed.name != artifact.name

    # Is the body hash known?
    hash_known = False
    if file_bytes:
        bh = body_hash(file_bytes, artifact.header_protocol)
        hash_known = bh == artifact.current_hash or any(p.hash == bh for p in artifact.previous_hashes)

    decision = decide(
        status=classified.status,
        header_present=header_present,
        hash_known_to_registry=hash_known,
        wrong_name_in_header=wrong_name,
        adopt=adopt,
        force_adopt=force_adopt,
    )

    backup: Path | None = None

    if decision.action is Action.INSTALL:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(canonical_path(artifact.name), target)
        target.chmod(int(artifact.mode, 8))

    elif decision.action is Action.NO_OP:
        pass  # already current

    elif decision.action is Action.ADOPT_IN_PLACE:
        # Rewrite the header in place; body stays.
        new_header = header_bytes(artifact.name, artifact.version, artifact.current_hash, artifact.header_protocol)
        # Reconstruct: shebang line + new_header + body_bytes
        first_nl = file_bytes.find(b"\n") + 1
        shebang = file_bytes[:first_nl]
        # Skip the existing 3 header lines:
        rest = file_bytes[first_nl:]
        for _ in range(3):
            rest = rest[rest.find(b"\n") + 1 :]
        target.write_bytes(shebang + new_header + rest)
        target.chmod(int(artifact.mode, 8))

    elif decision.action is Action.FORCE_ADOPT:
        backup = target.with_suffix(target.suffix + ".pre-install.bak")
        shutil.copy(target, backup)
        shutil.copy(canonical_path(artifact.name), target)
        target.chmod(int(artifact.mode, 8))

    else:
        raise InstallError(decision.reason)

    return InstallResult(action=decision.action, reason=decision.reason, install_target=target, backup=backup)

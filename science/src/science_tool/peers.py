"""Project peers: non-fatal path resolution.

See docs/superpowers/specs/2026-05-05-project-peers-design.md.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.project_config import PeerEntry


def resolve_peer_path(project_root: Path, entry: PeerEntry) -> Path:
    """Return the canonical (or would-be canonical) Path for a peer entry.

    Non-fatal: never raises for missing files. Uses Path.resolve(strict=False),
    which follows symlinks where present and normalizes `..`.

    Path-form dispatch (Decision 3):
        - leading `~` -> expanduser(), then resolve
        - absolute    -> used as-is
        - otherwise   -> resolved against project_root
    """
    raw = entry.path
    if raw.startswith("~"):
        candidate = Path(raw).expanduser()
    else:
        raw_path = Path(raw)
        if raw_path.is_absolute():
            candidate = raw_path
        else:
            candidate = project_root / raw_path
    return candidate.resolve(strict=False)

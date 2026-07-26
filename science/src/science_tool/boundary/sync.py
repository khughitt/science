"""Install the managed block, detect drift, and verify a migration.

`verify_current_tree` is a VERIFICATION mode: it must never leave a candidate
block installed merely because it found a change. It refuses a dirty
`.gitignore`, and restores the original on every path -- success, failure, and
exception.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from science_tool.boundary.config import BoundaryConfig, BoundaryConfigError
from science_tool.boundary.generate import extract_managed_block, render_managed_block, splice_managed_block
from science_tool.boundary.gitio import BoundaryGitError, read_ignore_file, write_ignore_file
from science_tool.boundary.probes import probe_paths
from science_tool.boundary.walk import iter_repo_files
from science_tool.project_config import load_project_config

GITIGNORE = ".gitignore"


class BoundaryDirtyError(Exception):
    """Raised when `.gitignore` has uncommitted changes and must not be touched."""


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    block: str


def _assert_root_gitignore_not_symlink(project_root: Path) -> None:
    if (project_root / GITIGNORE).is_symlink():
        raise BoundaryGitError("cannot manage root .gitignore: root .gitignore is a symlink")


def _config(project_root: Path) -> BoundaryConfig:
    cfg = load_project_config(project_root).boundary
    if cfg is None or not cfg.roots:
        raise BoundaryConfigError("science.yaml declares no boundary.roots")
    return cfg


def _read(project_root: Path) -> str:
    path = project_root / GITIGNORE
    return read_ignore_file(path) if path.is_file() else ""


def sync(project_root: Path) -> SyncResult:
    _assert_root_gitignore_not_symlink(project_root)
    cfg = _config(project_root)
    block = render_managed_block(cfg)
    original = _read(project_root)
    updated = splice_managed_block(original, block)
    if updated == original:
        return SyncResult(changed=False, block=block)
    write_ignore_file(project_root / GITIGNORE, updated)
    return SyncResult(changed=True, block=block)


def has_drift(project_root: Path) -> bool:
    _assert_root_gitignore_not_symlink(project_root)
    cfg = _config(project_root)
    return extract_managed_block(_read(project_root)) != render_managed_block(cfg)


def _probe_decisions(project_root: Path, probes: list[str]) -> dict[str, bool]:
    if not probes:
        return {}
    payload = "\0".join(probes).encode("utf-8", "surrogateescape") + b"\0"
    proc = subprocess.run(
        ["git", "-C", str(project_root), "check-ignore", "--no-index", "--stdin", "-z"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        detail = proc.stderr.decode("utf-8", "replace")
        raise BoundaryGitError(f"check-ignore failed ({proc.returncode}): {detail}")
    ignored = {candidate.decode("utf-8", "surrogateescape") for candidate in proc.stdout.split(b"\0") if candidate}
    return {probe: probe in ignored for probe in probes}


def _assert_clean(project_root: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(project_root), "status", "--porcelain", "-z", "--", GITIGNORE],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git status failed ({proc.returncode}) before verification: {detail}")
    if proc.stdout.strip():
        raise BoundaryDirtyError(
            f"{GITIGNORE} has uncommitted changes; commit or stash before verifying so a "
            f"failed verification cannot discard them"
        )


def _enumerate_tree(project_root: Path) -> list[str]:
    """Every file on disk except `.git`, regardless of ignore state.

    `visible_paths` is wrong here: indexed paths stay visible as rules change,
    so it could miss a rule flip for an already tracked file.
    """
    return iter_repo_files(project_root)


def verify_current_tree(project_root: Path) -> list[tuple[str, bool, bool]]:
    """Return every path whose ignore decision changes under the managed block.

    Compares `check-ignore --no-index` decisions for the filesystem and
    synthetic probes. The original `.gitignore` is restored even on exception.
    """
    _assert_root_gitignore_not_symlink(project_root)
    _assert_clean(project_root)
    cfg = _config(project_root)
    gitignore = project_root / GITIGNORE
    existed = gitignore.is_file()
    original = _read(project_root)

    subjects = _enumerate_tree(project_root) + probe_paths(cfg)
    before = _probe_decisions(project_root, subjects)
    try:
        write_ignore_file(gitignore, splice_managed_block(original, render_managed_block(cfg)))
        after = _probe_decisions(project_root, subjects)
    finally:
        if existed:
            write_ignore_file(gitignore, original)
        else:
            gitignore.unlink(missing_ok=True)

    return [
        (path, before.get(path, False), after.get(path, False))
        for path in subjects
        if before.get(path, False) != after.get(path, False)
    ]

"""Install the managed block, detect drift, and verify a migration.

`verify_current_tree` is a VERIFICATION mode: it must never leave a candidate
block installed merely because it found a change. It refuses a dirty
`.gitignore`, and restores the original on every path -- success, failure, and
exception.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from science_tool.boundary.config import BoundaryConfig, BoundaryConfigError
from science_tool.boundary.generate import extract_managed_block, render_managed_block, splice_managed_block
from science_tool.boundary.gitio import BoundaryGitError
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


@dataclass(frozen=True)
class _IgnoreState:
    device: int
    inode: int
    change_ns: int
    content: bytes


@dataclass(frozen=True)
class _StagedFile:
    path: Path
    state: _IgnoreState


def _same_inode_and_content(left: _IgnoreState | None, right: _IgnoreState | None) -> bool:
    if left is None or right is None:
        return left is right
    return (left.device, left.inode, left.content) == (right.device, right.inode, right.content)


def _snapshot_ignore_file(project_root: Path) -> _IgnoreState | None:
    """Read the root ignore file through a no-follow descriptor.

    The lstat/open/fstat identity check catches a swap while reading.  The
    transaction below repeats that check immediately before each replacement;
    `os.replace` then replaces a symlink itself instead of opening its target.
    """
    path = project_root / GITIGNORE
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        raise BoundaryGitError("cannot manage root .gitignore: root .gitignore is a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise BoundaryGitError("cannot manage root .gitignore: root .gitignore is not a regular file")
    if not hasattr(os, "O_NOFOLLOW"):
        raise BoundaryGitError("cannot manage root .gitignore: platform lacks O_NOFOLLOW")

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise BoundaryGitError(f"cannot read root .gitignore without following symlinks: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise BoundaryGitError("root .gitignore changed during safe read")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return _IgnoreState(
                device=opened.st_dev,
                inode=opened.st_ino,
                change_ns=opened.st_ctime_ns,
                content=stream.read(),
            )
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _before_atomic_replace(_path: Path) -> None:
    """Test seam immediately before the transaction's final identity check."""


def _after_atomic_replace(_path: Path) -> None:
    """Test seam immediately after installing a verification candidate."""


def _before_staged_cleanup(_path: Path) -> None:
    """Test seam immediately before identity-guarded staging cleanup."""


def _stage_bytes(project_root: Path, content: bytes) -> _StagedFile:
    descriptor, raw_path = tempfile.mkstemp(prefix=".science-boundary-", suffix=".tmp", dir=project_root)
    path = Path(raw_path)
    metadata = os.fstat(descriptor)
    staged = _StagedFile(
        path=path,
        state=_IgnoreState(metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns, content),
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            metadata = os.fstat(stream.fileno())
            staged = _StagedFile(
                path=path,
                state=_IgnoreState(metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns, content),
            )
    except BaseException:
        if descriptor != -1:
            os.close(descriptor)
        try:
            _discard_staged(staged)
        except BaseException:
            pass
        raise
    return staged


def _discard_staged(staged: _StagedFile) -> None:
    """Remove only the temporary inode created by this transaction.

    The lstat/unlink sequence has the same unavoidable portable-CAS gap as the
    final target replacement.  It never follows a symlink, and a replacement
    observed before unlink is preserved.
    """
    _before_staged_cleanup(staged.path)
    try:
        metadata = os.lstat(staged.path)
    except FileNotFoundError:
        return
    if (metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns) != (
        staged.state.device,
        staged.state.inode,
        staged.state.change_ns,
    ):
        return
    if not hasattr(os, "O_NOFOLLOW"):
        return
    try:
        descriptor = os.open(staged.path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_ctime_ns) != (
            staged.state.device,
            staged.state.inode,
            staged.state.change_ns,
        ):
            return
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            if stream.read() != staged.state.content:
                return
    finally:
        if descriptor != -1:
            os.close(descriptor)
    staged.path.unlink()


def _replace_if_unchanged(project_root: Path, expected: _IgnoreState | None, content: bytes) -> _IgnoreState:
    """Atomically replace only the snapshot this transaction observed.

    There is no portable compare-and-swap rename.  We check immediately before
    rename and use rename's no-follow semantics, then detect every subsequent
    interference before restoration.  A hostile replacement in the tiny gap
    after this check can be atomically replaced but can never be followed or
    write outside the repository.  Absence restoration has the same final-check
    gap before its no-follow unlink.
    """
    path = project_root / GITIGNORE
    staged = _stage_bytes(project_root, content)
    try:
        _before_atomic_replace(path)
        if _snapshot_ignore_file(project_root) != expected:
            raise BoundaryGitError("root .gitignore changed before atomic replace; preserving concurrent content")
        os.replace(staged.path, path)
        return staged.state
    except BaseException:
        try:
            _discard_staged(staged)
        except BaseException:
            pass
        raise


@dataclass(frozen=True)
class _IgnoreTransaction:
    project_root: Path
    original: _IgnoreState | None
    candidate: _IgnoreState

    def restore(self) -> None:
        current = _snapshot_ignore_file(self.project_root)
        if current != self.candidate:
            raise BoundaryGitError("root .gitignore changed during verification; preserving concurrent content")
        if self.original is None:
            path = self.project_root / GITIGNORE
            _before_atomic_replace(path)
            if _snapshot_ignore_file(self.project_root) != self.candidate:
                raise BoundaryGitError("root .gitignore changed during verification; preserving concurrent content")
            path.unlink()
            return
        _replace_if_unchanged(self.project_root, self.candidate, self.original.content)


def _install_candidate(project_root: Path, original: _IgnoreState | None, content: bytes) -> _IgnoreTransaction:
    staged_candidate = _replace_if_unchanged(project_root, original, content)
    _after_atomic_replace(project_root / GITIGNORE)
    candidate = _snapshot_ignore_file(project_root)
    if not _same_inode_and_content(candidate, staged_candidate):
        raise BoundaryGitError("root .gitignore changed during candidate installation; preserving concurrent content")
    assert candidate is not None
    return _IgnoreTransaction(project_root=project_root, original=original, candidate=candidate)


def _config(project_root: Path) -> BoundaryConfig:
    cfg = load_project_config(project_root).boundary
    if cfg is None or not cfg.roots:
        raise BoundaryConfigError("science.yaml declares no boundary.roots")
    return cfg


def _text(state: _IgnoreState | None) -> str:
    return "" if state is None else state.content.decode("utf-8", "surrogateescape")


def sync(project_root: Path) -> SyncResult:
    cfg = _config(project_root)
    block = render_managed_block(cfg)
    original = _snapshot_ignore_file(project_root)
    original_text = _text(original)
    updated = splice_managed_block(original_text, block)
    if updated == original_text:
        return SyncResult(changed=False, block=block)
    _replace_if_unchanged(project_root, original, updated.encode("utf-8", "surrogateescape"))
    return SyncResult(changed=True, block=block)


def has_drift(project_root: Path) -> bool:
    cfg = _config(project_root)
    return extract_managed_block(_text(_snapshot_ignore_file(project_root))) != render_managed_block(cfg)


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
    if proc.returncode == 1 and proc.stdout:
        raise BoundaryGitError("malformed check-ignore output: return code 1 must have no records")
    if proc.returncode == 0 and not proc.stdout:
        raise BoundaryGitError("malformed check-ignore output: return code 0 must have records")
    if proc.stdout and not proc.stdout.endswith(b"\0"):
        raise BoundaryGitError("malformed check-ignore output: stream must terminate in NUL")
    submitted = set(probes)
    ignored: set[str] = set()
    for raw in proc.stdout[:-1].split(b"\0") if proc.stdout else []:
        if not raw:
            raise BoundaryGitError("malformed check-ignore output: empty path record")
        candidate = raw.decode("utf-8", "surrogateescape")
        if candidate not in submitted:
            raise BoundaryGitError(f"check-ignore returned unexpected path {candidate!r}")
        if candidate in ignored:
            raise BoundaryGitError(f"check-ignore returned duplicate path {candidate!r}")
        ignored.add(candidate)
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
    _assert_clean(project_root)
    cfg = _config(project_root)
    original = _snapshot_ignore_file(project_root)

    subjects = sorted(set(_enumerate_tree(project_root)) | set(probe_paths(cfg)))
    before = _probe_decisions(project_root, subjects)
    transaction = _install_candidate(
        project_root,
        original,
        splice_managed_block(_text(original), render_managed_block(cfg)).encode("utf-8", "surrogateescape"),
    )
    try:
        after = _probe_decisions(project_root, subjects)
    finally:
        transaction.restore()

    return [
        (path, before.get(path, False), after.get(path, False))
        for path in subjects
        if before.get(path, False) != after.get(path, False)
    ]

"""Transaction snapshots for managed-artifact mutations."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol


class Snapshot(Protocol):
    def take(self) -> None: ...
    def restore(self) -> None: ...
    def discard(self, *, commit_message: str | None = None) -> None: ...


class TempCommitSnapshot:
    """Git-only snapshot via a temp commit.

    take():    add ALL worktree changes (including untracked) and create a temp commit.
    restore(): hard-reset to HEAD~1, restoring the pre-take state.
    discard(): soft-reset HEAD~1 (keeping changes staged) and create the canonical commit.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._snapshot_sha: str | None = None
        self._original_head: str | None = None

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            check=check,
            capture_output=True,
            text=True,
        )

    def take(self) -> None:
        self._original_head = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("add", "-A")
        # --allow-empty so taking a snapshot of a clean tree still succeeds.
        self._git(
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "managed-artifacts: temp transaction snapshot",
        )
        self._snapshot_sha = self._git("rev-parse", "HEAD").stdout.strip()

    def restore(self) -> None:
        if self._snapshot_sha is None or self._original_head is None:
            raise RuntimeError("snapshot not taken; cannot restore")
        # Hard-reset to the snapshot: HEAD/index/worktree all at snap-tree,
        # which captures the exact pre-take worktree contents.
        self._git("reset", "--hard", self._snapshot_sha)
        # Remove anything created after take() that the migration left behind
        # as untracked (reset --hard does NOT remove untracked files).
        self._git("clean", "-fd")
        # Move HEAD back to the original commit so the temp snapshot commit
        # is no longer reachable; index + worktree stay at snap content.
        self._git("reset", "--soft", self._original_head)

    def discard(self, *, commit_message: str | None = None) -> None:
        if self._snapshot_sha is None or self._original_head is None:
            raise RuntimeError("snapshot not taken; cannot discard")
        # Move HEAD back to original; index stays at snap-tree, worktree
        # has the migration's mutations.
        self._git("reset", "--soft", self._original_head)
        if commit_message is not None:
            # Stage the migration's mutations on top of the pre-take index.
            self._git("add", "-A")
            self._git("commit", "-q", "-m", commit_message)


class ManifestSnapshot:
    """Snapshot a declared list of paths via copy into a tempdir.

    Used outside Git or for `transaction_kind: manifest` artifacts.
    Captures only the declared touched_paths (not arbitrary files).
    """

    def __init__(self, repo_root: Path, touched_paths: list[Path]) -> None:
        self.repo_root = repo_root
        self.touched_paths = list(touched_paths)
        self._tempdir: Path | None = None
        # For each declared path, store (rel, source_existed, copy_path|None).
        self._captured: list[tuple[Path, bool, Path | None]] = []

    def take(self) -> None:
        self._tempdir = Path(tempfile.mkdtemp(prefix="science-managed-snapshot-"))
        for rel in self.touched_paths:
            src = self.repo_root / rel
            if src.exists():
                dst = self._tempdir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                self._captured.append((rel, True, dst))
            else:
                self._captured.append((rel, False, None))

    def restore(self) -> None:
        if self._tempdir is None:
            raise RuntimeError("snapshot not taken; cannot restore")
        for rel, existed, copy in self._captured:
            target = self.repo_root / rel
            if existed:
                assert copy is not None
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copy, target)
            elif target.exists():
                target.unlink()
        self._cleanup()

    def discard(self, *, commit_message: str | None = None) -> None:
        # No-op for manifest snapshots; the canonical commit (if any) is the
        # caller's responsibility.
        self._cleanup()

    def _cleanup(self) -> None:
        if self._tempdir is not None and self._tempdir.exists():
            shutil.rmtree(self._tempdir)
        self._tempdir = None

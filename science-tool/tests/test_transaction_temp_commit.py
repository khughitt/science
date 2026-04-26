"""TempCommitSnapshot: take + restore returns to pre-state; discard finalizes."""

import subprocess
from pathlib import Path

from science_tool.project_artifacts.migrations.transaction import TempCommitSnapshot


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("orig", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def test_take_restore_round_trip(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("dirty", encoding="utf-8")
    (tmp_path / "new.txt").write_text("untracked", encoding="utf-8")

    snap = TempCommitSnapshot(tmp_path)
    snap.take()

    # Mutate further (simulate migration step).
    (tmp_path / "a.txt").write_text("further", encoding="utf-8")
    (tmp_path / "new.txt").unlink()

    snap.restore()

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "dirty"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "untracked"


def test_discard_creates_canonical_commit(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()  # snapshot the clean state

    (tmp_path / "a.txt").write_text("after-update", encoding="utf-8")
    snap.discard(commit_message="chore(artifacts): refresh validate.sh to 2026.05.10")

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "2"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert "refresh validate.sh" in log[0]
    assert "init" in log[1]


def test_restore_after_failed_apply(tmp_path: Path) -> None:
    """Failed apply mid-migration: restore returns to the pre-migration state."""
    _init_repo(tmp_path)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()
    (tmp_path / "a.txt").write_text("partial", encoding="utf-8")
    (tmp_path / "b.txt").write_text("partial2", encoding="utf-8")
    snap.restore()
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "orig"
    assert not (tmp_path / "b.txt").exists()


def test_restore_is_idempotent(tmp_path: Path) -> None:
    """Calling restore() twice is a no-op the second time.

    Covers update.update_artifact's outer-except path: run_migration already
    restored on step failure, then update's except handler restores again.
    """
    _init_repo(tmp_path)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()
    (tmp_path / "a.txt").write_text("partial", encoding="utf-8")
    snap.restore()
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "orig"
    snap.restore()
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "orig"

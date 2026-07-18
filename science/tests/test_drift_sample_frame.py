import subprocess
from pathlib import Path

import pytest

from science_tool.drift_sample.frame import (
    DirtyTreeError,
    assert_clean,
    enumerate_frame,
    pin_project,
    pinned_worktree,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "entities" / "plans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def _write_plan(root: Path, num: str, status: str) -> None:
    (root / "entities" / "plans" / f"{num}-x-plan.md").write_text(
        f"---\nkind: plan\ntitle: X\nstatus: {status}\nid: plan:{num}-x-plan\n---\n\nbody\n"
    )


def test_assert_clean_raises_on_dirty_tree(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    (root / "entities" / "plans" / "0001-x-plan.md").write_text("dirtied")
    with pytest.raises(DirtyTreeError):
        assert_clean(root)


def test_assert_clean_raises_on_untracked_file(tmp_path: Path):
    """Untracked files are dirt too -- they can change what a probe sees."""
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    (root / "stray.txt").write_text("x")
    with pytest.raises(DirtyTreeError):
        assert_clean(root)


def test_pin_project_returns_head_of_clean_tree(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    assert pin.commit == _git(root, "rev-parse", "HEAD")
    assert len(pin.commit) == 40


def test_worktree_shows_pinned_content_not_later_commits(tmp_path: Path):
    """The whole point of the pin: later commits must be invisible."""
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    _write_plan(root, "0002", "active")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "later")
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert [r.plan_id for r in rows] == ["plan:0001-x-plan"]


def test_worktree_is_removed_on_exit(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        assert wt.exists()
    assert not wt.exists()


def test_enumerate_frame_records_status_and_content_hash(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert len(rows) == 1
    assert rows[0].claimed_status == "draft"
    assert rows[0].project == "proj"
    assert rows[0].rel_path == "entities/plans/0001-x-plan.md"
    assert len(rows[0].source_sha256) == 64


def test_enumerate_frame_skips_files_without_frontmatter(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    (root / "entities" / "plans" / "README.md").write_text("# not a plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert [r.plan_id for r in rows] == ["plan:0001-x-plan"]

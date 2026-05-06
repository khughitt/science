"""Worktree state primitives: clean check, dirty paths, conflict detection."""

import subprocess
from pathlib import Path

from science_tool.project_artifacts.worktree import (
    dirty_paths,
    in_git_repo,
    is_clean,
    paths_intersect,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def test_is_clean_true_on_fresh_repo(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert is_clean(tmp_path) is True


def test_is_clean_false_with_modification(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("b", encoding="utf-8")
    assert is_clean(tmp_path) is False


def test_dirty_paths_lists_modified_and_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("b", encoding="utf-8")
    (tmp_path / "new.txt").write_text("hi", encoding="utf-8")
    paths = dirty_paths(tmp_path)
    assert {"f.txt", "new.txt"} <= {str(p) for p in paths}


def test_in_git_repo_true(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert in_git_repo(tmp_path) is True


def test_in_git_repo_false(tmp_path: Path) -> None:
    assert in_git_repo(tmp_path) is False


def test_paths_intersect_literal() -> None:
    dirty = {Path("a.txt"), Path("b.txt")}
    assert paths_intersect(["a.txt"], dirty) == {Path("a.txt")}
    assert paths_intersect(["c.txt"], dirty) == set()


def test_paths_intersect_glob() -> None:
    dirty = {Path("specs/h01.md"), Path("README.md")}
    assert paths_intersect(["specs/*.md"], dirty) == {Path("specs/h01.md")}

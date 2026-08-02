from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import (
    GitError,
    commit_tree,
    create_branch,
    current_branch,
    restore_worktree,
    stage_all,
    switch_branch,
    worktree_status,
)

SUPERVISOR = {"committer_name": "science-supervisor", "committer_email": "supervisor@science.local"}


def _plain_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _plain_git(root, "init", "-q")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _plain_git(root, "add", "-A")
    _plain_git(root, "commit", "-q", "-m", "base")
    return root


def test_current_branch_names_the_checked_out_branch(repo: Path):
    assert current_branch(repo) == _plain_git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def test_current_branch_is_none_on_a_detached_head(repo: Path):
    _plain_git(repo, "checkout", "-q", "--detach")
    assert current_branch(repo) is None


def test_create_branch_switches_to_it(repo: Path):
    create_branch(repo, "auto/x")
    assert current_branch(repo) == "auto/x"


def test_create_branch_refuses_an_existing_name(repo: Path):
    create_branch(repo, "auto/x")
    switch_branch(repo, _plain_git(repo, "rev-parse", "--abbrev-ref", "@{-1}"))
    with pytest.raises(GitError):
        create_branch(repo, "auto/x")


def test_restore_worktree_discards_modifications_and_untracked_files(repo: Path):
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    (repo / "new.txt").write_text("x\n", encoding="utf-8")
    (repo / "sub").mkdir()
    (repo / "sub" / "deep.txt").write_text("y\n", encoding="utf-8")

    restore_worktree(repo)

    assert worktree_status(repo) == ""
    assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
    assert not (repo / "new.txt").exists()
    assert not (repo / "sub").exists()


def test_commit_tree_splits_author_from_committer(repo: Path):
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    stage_all(repo)

    sha = commit_tree(
        repo,
        message="audit: report\n\nScience-Run: run:2026-08-02-health-audit-a1b2",
        author="health-audit <agent@science.local>",
        **SUPERVISOR,
    )

    assert sha == _plain_git(repo, "rev-parse", "HEAD")
    assert _plain_git(repo, "log", "-1", "--format=%an <%ae>") == "health-audit <agent@science.local>"
    assert _plain_git(repo, "log", "-1", "--format=%cn <%ce>") == "science-supervisor <supervisor@science.local>"
    trailer = _plain_git(repo, "log", "-1", "--format=%(trailers:key=Science-Run,valueonly)").strip()
    assert trailer == "run:2026-08-02-health-audit-a1b2"


def test_commit_tree_raises_when_there_is_nothing_to_commit(repo: Path):
    with pytest.raises(GitError):
        commit_tree(repo, message="empty", author="a <a@b.c>", **SUPERVISOR)


def test_no_planted_vector_executes_through_the_write_primitives(repo: Path, plant_attacks):
    sentinels = plant_attacks(repo)

    create_branch(repo, "auto/hostile")
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    stage_all(repo)
    commit_tree(repo, message="hostile", author="a <a@b.c>", **SUPERVISOR)
    worktree_status(repo)
    restore_worktree(repo)

    assert sorted(p.name for p in sentinels.iterdir()) == [], (
        "a planted git-config vector reached a program through the write primitives"
    )

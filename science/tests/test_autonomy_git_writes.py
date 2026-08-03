from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import (
    GitError,
    commit_tree,
    create_branch,
    current_branch,
    restore_path,
    restore_worktree,
    stage_all,
    stage_paths,
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


def test_restore_path_discards_a_tracked_modification_and_leaves_everything_else(repo: Path):
    """The branch `restore_worktree`'s whole-tree form cannot express.

    Both states are asserted, in two tests, because `restore_path` takes a DIFFERENT
    subcommand for each and the harness fixture only ever reaches one of them: a project that
    never materialized has an untracked `knowledge/graph.trig`, and only a project that
    committed one has a tracked modification. A single test would leave half the function
    unexecuted.
    """
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    (repo / "keep-me.txt").write_text("k\n", encoding="utf-8")

    restore_path(repo, "a.txt")

    assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
    # The whole point of being path-scoped: `restore_worktree` would have deleted this.
    assert (repo / "keep-me.txt").read_text(encoding="utf-8") == "k\n"


def test_restore_path_removes_a_path_head_does_not_have(repo: Path):
    """"Restore to HEAD's version" of a path HEAD never had means REMOVE it.

    `checkout -- <path>` refuses a pathspec the index does not know, so this state needs the
    other subcommand -- and it is the state the supervised harness actually hits, since a
    project with no committed graph gets an untracked one from the run.
    """
    (repo / "derived.txt").write_text("d\n", encoding="utf-8")
    (repo / "keep-me.txt").write_text("k\n", encoding="utf-8")

    restore_path(repo, "derived.txt")

    assert not (repo / "derived.txt").exists()
    assert (repo / "keep-me.txt").read_text(encoding="utf-8") == "k\n"


def test_restore_path_fails_closed_when_cat_file_does_not_prove_absence(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """An object-database failure is not evidence that HEAD lacks the path."""
    from science_tool.autonomy import git as git_module

    target = repo / "derived.txt"
    target.write_text("keep\n", encoding="utf-8")
    real_run_git = git_module.run_git

    def _fail_membership(root: Path, *args: str, **kwargs):
        if args[:2] == ("cat-file", "-t"):
            return subprocess.CompletedProcess(
                ["git", *args], 128, b"", b"fatal: object database unavailable\n"
            )
        return real_run_git(root, *args, **kwargs)

    monkeypatch.setattr(git_module, "run_git", _fail_membership)

    with pytest.raises(GitError, match="could not determine whether"):
        restore_path(repo, "derived.txt")

    assert target.read_text(encoding="utf-8") == "keep\n"


def test_stage_paths_stages_only_what_it_names(repo: Path):
    (repo / "named.txt").write_text("n\n", encoding="utf-8")
    (repo / "unnamed.txt").write_text("u\n", encoding="utf-8")

    stage_paths(repo, ["named.txt"])

    staged = _plain_git(repo, "diff", "--cached", "--name-only").splitlines()
    assert staged == ["named.txt"]


def test_stage_paths_refuses_a_path_that_is_not_there(repo: Path):
    """Fail early: a caller naming a path it believes it produced is wrong about the run."""
    with pytest.raises(GitError):
        stage_paths(repo, ["runs/never-written.md"])


def test_no_planted_vector_executes_through_the_path_scoped_primitives(repo: Path, plant_attacks):
    """The pathspec-limited spellings go through the same gateway as the whole-tree ones.

    A separate test from the primitives one above because `restore_path` and `stage_paths`
    are separate call sites: a hand-built argv in either would leave that test green.
    """
    sentinels = plant_attacks(repo)

    (repo / "derived.txt").write_text("d\n", encoding="utf-8")
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    stage_paths(repo, ["a.txt"])
    restore_path(repo, "derived.txt")
    restore_path(repo, "a.txt")

    assert sorted(p.name for p in sentinels.iterdir()) == [], (
        "a planted git-config vector reached a program through the path-scoped primitives"
    )


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


def test_repo_local_core_worktree_cannot_redirect_write_primitives(
    repo: Path, tmp_path: Path
):
    """Every gateway operation stays on `repo`, even when its config names another tree."""
    starting_branch = current_branch(repo)
    assert starting_branch is not None
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.txt").write_text("one\n", encoding="utf-8")
    _plain_git(repo, "config", "core.worktree", str(outside))

    create_branch(repo, "auto/pinned")
    switch_branch(repo, starting_branch)
    switch_branch(repo, "auto/pinned")

    (repo / "named.txt").write_text("inside named\n", encoding="utf-8")
    (outside / "named.txt").write_text("outside named\n", encoding="utf-8")
    stage_paths(repo, ["named.txt"])
    commit_tree(repo, message="named", author="a <a@b.c>", **SUPERVISOR)

    (repo / "named.txt").write_text("inside changed\n", encoding="utf-8")
    (outside / "named.txt").write_text("outside changed\n", encoding="utf-8")
    restore_path(repo, "named.txt")

    (repo / "all.txt").write_text("inside all\n", encoding="utf-8")
    (outside / "all.txt").write_text("outside all\n", encoding="utf-8")
    stage_all(repo)
    commit_tree(repo, message="all", author="a <a@b.c>", **SUPERVISOR)

    (repo / "all.txt").write_text("inside dirty\n", encoding="utf-8")
    (repo / "inside-untracked.txt").write_text("inside\n", encoding="utf-8")
    (outside / "all.txt").write_text("outside dirty\n", encoding="utf-8")
    (outside / "outside-untracked.txt").write_text("outside\n", encoding="utf-8")
    restore_worktree(repo)

    assert _plain_git(repo, "show", "HEAD:named.txt") == "inside named"
    assert _plain_git(repo, "show", "HEAD:all.txt") == "inside all"
    assert (repo / "named.txt").read_text(encoding="utf-8") == "inside named\n"
    assert (repo / "all.txt").read_text(encoding="utf-8") == "inside all\n"
    assert not (repo / "inside-untracked.txt").exists()
    assert (outside / "named.txt").read_text(encoding="utf-8") == "outside changed\n"
    assert (outside / "all.txt").read_text(encoding="utf-8") == "outside dirty\n"
    assert (outside / "outside-untracked.txt").read_text(encoding="utf-8") == "outside\n"

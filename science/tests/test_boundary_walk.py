from __future__ import annotations

from pathlib import Path

import pytest

import science_tool.boundary.walk as walk
from science_tool.boundary.config import BoundaryRoot
from science_tool.boundary.walk import manifest_candidates


def _root() -> BoundaryRoot:
    return BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json", "*.qa.json"]}
    )


def _mk(base: Path, rel: str, body: str = "x") -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def test_matches_at_any_depth(tmp_path: Path):
    _mk(tmp_path, "data/external/a/datapackage.json")
    _mk(tmp_path, "data/external/a/b/c/datapackage.json")
    _mk(tmp_path, "data/external/a/big.parquet")
    found = manifest_candidates(tmp_path, _root())
    assert found == ["data/external/a/b/c/datapackage.json", "data/external/a/datapackage.json"]


def test_matches_glob_pattern(tmp_path: Path):
    _mk(tmp_path, "data/external/a/run.qa.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/run.qa.json"]


def test_missing_root_is_empty(tmp_path: Path):
    assert manifest_candidates(tmp_path, _root()) == []


def test_propagates_walk_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    error = OSError("permission denied")

    def failing_walk(top: Path, *, topdown: bool = True, onerror=None, followlinks: bool = False):
        assert top == tmp_path
        assert topdown
        assert not followlinks
        if onerror is not None:
            onerror(error)
        return iter(())

    monkeypatch.setattr(walk.os, "walk", failing_walk)

    with pytest.raises(OSError) as raised:
        walk.iter_repo_files(tmp_path)

    assert raised.value is error


def test_does_not_descend_into_symlinked_directory(tmp_path: Path):
    _mk(tmp_path, "outside/datapackage.json")
    (tmp_path / "data/external").mkdir(parents=True)
    (tmp_path / "data/external/link").symlink_to(tmp_path / "outside", target_is_directory=True)
    assert manifest_candidates(tmp_path, _root()) == []


def test_symlinked_file_is_reported(tmp_path: Path):
    target = _mk(tmp_path, "outside/datapackage.json")
    (tmp_path / "data/external/a").mkdir(parents=True)
    (tmp_path / "data/external/a/datapackage.json").symlink_to(target)
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/datapackage.json"]


def test_symlink_cycle_terminates(tmp_path: Path):
    (tmp_path / "data/external/a").mkdir(parents=True)
    (tmp_path / "data/external/a/loop").symlink_to(tmp_path / "data/external", target_is_directory=True)
    _mk(tmp_path, "data/external/a/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/datapackage.json"]


def test_nested_repository_dir_form_is_pruned(tmp_path: Path):
    _mk(tmp_path, "data/external/sub/.git/HEAD", "ref: refs/heads/main\n")
    _mk(tmp_path, "data/external/sub/datapackage.json")
    _mk(tmp_path, "data/external/own/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/own/datapackage.json"]


def test_nested_repository_file_form_is_pruned(tmp_path: Path):
    """Submodules and linked worktrees carry `.git` as a FILE."""
    _mk(tmp_path, "data/external/sub/.git", "gitdir: /elsewhere/.git/modules/sub\n")
    _mk(tmp_path, "data/external/sub/datapackage.json")
    _mk(tmp_path, "data/external/own/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/own/datapackage.json"]


def test_declared_root_that_is_itself_a_nested_repo_is_pruned(tmp_path: Path):
    """The exemption from pruning belongs to the PROJECT ROOT alone. Exempting
    the supplied `base` traversed a submodule declared as a root in full."""
    _mk(tmp_path, "data/external/.git", "gitdir: /elsewhere/.git/modules/external\n")
    _mk(tmp_path, "data/external/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == []


def test_project_root_git_file_is_not_reported(tmp_path: Path):
    """A linked worktree's root `.git` is a FILE, and filtering only directory
    names returned it as a repository file."""
    from science_tool.boundary.walk import iter_repo_files

    _mk(tmp_path, ".git", "gitdir: /elsewhere/.git/worktrees/wt\n")
    _mk(tmp_path, "README.md")
    assert iter_repo_files(tmp_path) == ["README.md"]


def test_project_root_git_directory_is_not_reported(tmp_path: Path):
    from science_tool.boundary.walk import iter_repo_files

    _mk(tmp_path, ".git/HEAD", "ref: refs/heads/main\n")
    _mk(tmp_path, "README.md")
    assert iter_repo_files(tmp_path) == ["README.md"]


def test_symlinked_root_is_not_traversed(tmp_path: Path):
    _mk(tmp_path, "outside/a/datapackage.json")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/external").symlink_to(tmp_path / "outside", target_is_directory=True)
    assert manifest_candidates(tmp_path, _root()) == []


def test_multi_segment_glob_is_matched(tmp_path: Path):
    root = BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["schemas/*.json"]}
    )
    _mk(tmp_path, "data/external/ds/schemas/x.json")
    _mk(tmp_path, "data/external/ds/other.json")
    assert manifest_candidates(tmp_path, root) == ["data/external/ds/schemas/x.json"]


def test_dot_git_directory_is_skipped(tmp_path: Path):
    _mk(tmp_path, "data/external/.git/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == []

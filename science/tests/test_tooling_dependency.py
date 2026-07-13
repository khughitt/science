from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from science_tool.tooling_dependency import ScienceSourceKind, inspect_science_dependency


def _write_pyproject(project: Path, source: str, *, include_dependency: bool = True) -> None:
    project.mkdir(parents=True, exist_ok=True)
    dependency = 'dev = ["science"]' if include_dependency else "dev = []"
    project.joinpath("pyproject.toml").write_text(
        f"[project]\nname = \"fixture\"\nversion = \"0.1.0\"\n"
        f"[dependency-groups]\n{dependency}\n"
        f"[tool.uv.sources]\n{source}\n",
        encoding="utf-8",
    )


def test_git_source_is_worktree_safe(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        'science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }',
    )

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is True
    assert result.source_kind is ScienceSourceKind.GIT


def test_same_repository_path_source_is_worktree_safe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "science").mkdir()
    project = repo / "meta"
    _write_pyproject(project, 'science = { path = "../science", editable = true }')

    result = inspect_science_dependency(project)

    assert result.source_kind is ScienceSourceKind.SAME_REPO_PATH
    assert result.resolved_path == (repo / "science").resolve()


def test_external_path_source_is_worktree_unsafe(tmp_path: Path) -> None:
    consumer_repo = tmp_path / "consumer"
    (consumer_repo / ".git").mkdir(parents=True)
    toolkit_repo = tmp_path / "toolkit"
    (toolkit_repo / ".git").mkdir(parents=True)
    (toolkit_repo / "science").mkdir()
    _write_pyproject(
        consumer_repo,
        'science = { path = "../toolkit/science", editable = true }',
    )

    result = inspect_science_dependency(consumer_repo)

    assert result.source_kind is ScienceSourceKind.EXTERNAL_PATH
    assert result.resolved_path == (toolkit_repo / "science").resolve()


def test_missing_dev_dependency_is_distinct_from_missing_source(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "", include_dependency=False)

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is False
    assert result.source_kind is ScienceSourceKind.MISSING


def test_present_dependency_without_uv_source_reports_missing_source(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "")

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is True
    assert result.source_kind is ScienceSourceKind.MISSING


def test_malformed_pyproject_fails_parsing(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        inspect_science_dependency(tmp_path)

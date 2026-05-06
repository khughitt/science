from pathlib import Path

import pytest

from science_tool.project_config import (
    ChildEntry,
    ProjectRole,
    paths_equivalent,
    resolve_child_path,
    resolve_parent_path,
)


def test_resolve_child_path_expands_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "d" / "cancer" / "x"
    target.mkdir(parents=True)
    child = ChildEntry(id="x", path="~/d/cancer/x", role=ProjectRole.MECHANISM)
    assert resolve_child_path(child) == target.resolve()


def test_paths_equivalent_through_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert paths_equivalent(real, link) is True


def test_paths_equivalent_distinct(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert paths_equivalent(a, b) is False


def test_resolve_parent_path_none_returns_none() -> None:
    assert resolve_parent_path(None) is None


def test_resolve_parent_path_missing_target_returns_unresolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers decide whether a configured but missing parent is an error."""
    monkeypatch.setenv("HOME", str(tmp_path))
    parent = resolve_parent_path("~/does/not/exist")
    assert parent == (tmp_path / "does" / "not" / "exist")

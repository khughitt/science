from pathlib import Path

from science_tool.project_config import paths_equivalent


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

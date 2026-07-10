from pathlib import Path

import pytest

from science_model.frontmatter import atomic_write_text


def test_atomic_write_text_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_leaves_no_tmp_file(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    atomic_write_text(target, "content\n")
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_write_text_cleans_tmp_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "entity.md"

    def boom(_src: object, _dst: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("science_model.frontmatter.os.replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(target, "content\n")
    # temp file cleaned up; target never created
    assert list(tmp_path.iterdir()) == []

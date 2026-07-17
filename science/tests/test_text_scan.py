# science/tests/test_text_scan.py
"""The scannable-text surface: never hand a PNG to a UTF-8 read."""
from __future__ import annotations

from pathlib import Path

from science_tool.text_scan import (
    TEXT_SUFFIXES,
    iter_scannable_files,
    read_text_or_skip,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\xfd"


def test_binary_file_is_not_scannable(tmp_path: Path) -> None:
    (tmp_path / "img.png").write_bytes(PNG_MAGIC)
    (tmp_path / "a.md").write_text("# hi\n", encoding="utf-8")

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert "a.md" in names
    assert "img.png" not in names


def test_code_files_are_scannable() -> None:
    """Code carries path references; it must be SEEN even though it is never rewritten."""
    for suffix in (".py", ".ts", ".tsx", ".js"):
        assert suffix in TEXT_SUFFIXES


def test_undecodable_bytes_report_a_skip(tmp_path: Path) -> None:
    path = tmp_path / "weird.md"
    path.write_bytes(b"\xff\xfe\x00\x00not utf8")

    text, skip = read_text_or_skip(path, "weird.md")

    assert text is None
    assert skip is not None
    assert skip.rel_path == "weird.md"
    assert "utf-8" in skip.reason.lower()


def test_unreadable_file_reports_a_skip_not_a_clean_read(tmp_path: Path) -> None:
    """An OSError must never be indistinguishable from a file with no references."""
    path = tmp_path / "locked.md"
    path.write_text("see doc/plans/old.md\n", encoding="utf-8")
    path.chmod(0o000)
    try:
        text, skip = read_text_or_skip(path, "locked.md")
    finally:
        path.chmod(0o644)

    assert text is None
    assert skip is not None
    assert skip.rel_path == "locked.md"


def test_read_text_or_skip_returns_text(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("# hi\n", encoding="utf-8")

    assert read_text_or_skip(path, "a.md") == ("# hi\n", None)


def test_skip_dirs_are_honoured(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "readme.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("x\n", encoding="utf-8")

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert names == {"keep.md"}


def test_scans_the_real_repository_and_covers_its_python() -> None:
    """The regression synthetic fixtures cannot catch.

    "Does not raise" is too weak: a scan that returned [] would pass it. Assert
    positive coverage of a file class known to exist here.
    """
    repo = Path(__file__).resolve().parents[2]
    files = iter_scannable_files(repo)
    assert files, "scanned nothing"

    rels = {p.relative_to(repo).as_posix() for p in files}
    assert "science/src/science_tool/entities.py" in rels, "own source not scanned"

    skips = [skip for p in files if (skip := read_text_or_skip(p, p.name)[1]) is not None]
    assert skips == [], f"unexpected skips in a clean checkout: {skips}"

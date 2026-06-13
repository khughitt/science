from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from science_tool.book_split import BookSplitError, split_book


def _make_pdf(path: Path, n_pages: int, outline: list[tuple[str, int]]) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    for title, page in outline:
        writer.add_outline_item(title, page)
    with path.open("wb") as fh:
        writer.write(fh)


def _make_pdf_with_parts(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    p1 = writer.add_outline_item("Part I", 0)
    writer.add_outline_item("Chapter 1", 0, parent=p1)
    writer.add_outline_item("Chapter 2", 4, parent=p1)
    p2 = writer.add_outline_item("Part II", 8)
    writer.add_outline_item("Chapter 3", 8, parent=p2)
    with path.open("wb") as fh:
        writer.write(fh)


def test_split_flat_outline(tmp_path: Path) -> None:
    pdf = tmp_path / "flat.pdf"
    _make_pdf(pdf, 30, [("Introduction", 0), ("Methods", 10), ("Results", 20)])
    chapters = split_book(pdf)
    assert [c.n for c in chapters] == [1, 2, 3]
    assert chapters[0].title == "Introduction"
    assert chapters[0].start_page == 1   # 1-based
    assert chapters[0].end_page == 10    # next start (11) - 1
    assert chapters[2].end_page == 30    # last runs to final page
    assert all(c.part is None for c in chapters)


def test_split_detects_parts(tmp_path: Path) -> None:
    pdf = tmp_path / "parts.pdf"
    _make_pdf_with_parts(pdf, 12)
    chapters = split_book(pdf)
    titles = [c.title for c in chapters]
    assert titles == ["Chapter 1", "Chapter 2", "Chapter 3"]  # parts are containers, not chapters
    assert chapters[0].part == "Part I"
    assert chapters[2].part == "Part II"
    assert chapters[0].level == 1


def _make_pdf_with_sections(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    c1 = writer.add_outline_item("Chapter 1", 0)
    writer.add_outline_item("1.1 Background", 1, parent=c1)
    writer.add_outline_item("1.2 Setup", 3, parent=c1)
    c2 = writer.add_outline_item("Chapter 2", 6)
    writer.add_outline_item("2.1 Method", 7, parent=c2)
    with path.open("wb") as fh:
        writer.write(fh)


def test_split_chapter_with_section_children(tmp_path: Path) -> None:
    # Chapters with sub-section bookmarks must still be dispatched as chapters,
    # NOT replaced by their section children (the high-severity regression).
    pdf = tmp_path / "sections.pdf"
    _make_pdf_with_sections(pdf, 10)
    chapters = split_book(pdf)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].start_page == 1
    assert chapters[0].end_page == 6   # up to Chapter 2's start (7) - 1
    assert all(c.part is None for c in chapters)
    assert all(c.level == 0 for c in chapters)


def _make_pdf_with_volume(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    v1 = writer.add_outline_item("Volume 1", 0)
    writer.add_outline_item("Chapter 1", 0, parent=v1)
    writer.add_outline_item("Chapter 2", 4, parent=v1)
    with path.open("wb") as fh:
        writer.write(fh)


def test_split_detects_volume_container(tmp_path: Path) -> None:
    pdf = tmp_path / "vol.pdf"
    _make_pdf_with_volume(pdf, 8)
    chapters = split_book(pdf)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].part == "Volume 1"
    assert chapters[0].level == 1


def test_part_without_children_is_treated_as_chapter(tmp_path: Path) -> None:
    pdf = tmp_path / "emptypart.pdf"
    _make_pdf(pdf, 10, [("Part I", 0), ("Chapter 1", 2)])
    chapters = split_book(pdf)
    # "Part I" has no children, so it is emitted as a chapter, not a container.
    assert [c.title for c in chapters] == ["Part I", "Chapter 1"]
    assert all(c.part is None for c in chapters)
    assert all(c.level == 0 for c in chapters)


def test_no_outline_raises(tmp_path: Path) -> None:
    pdf = tmp_path / "bare.pdf"
    _make_pdf(pdf, 5, [])  # pages, no outline
    with pytest.raises(BookSplitError, match="no outline"):
        split_book(pdf)

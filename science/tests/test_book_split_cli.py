from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from pypdf import PdfWriter

from science_tool.cli import main


def _make_pdf(path: Path, n_pages: int, outline: list[tuple[str, int]]) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    for title, page in outline:
        writer.add_outline_item(title, page)
    with path.open("wb") as fh:
        writer.write(fh)


def test_book_split_cli_emits_json(tmp_path: Path) -> None:
    pdf = tmp_path / "b.pdf"
    _make_pdf(pdf, 20, [("Intro", 0), ("Body", 10)])
    result = CliRunner().invoke(main, ["book-split", str(pdf), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [c["title"] for c in data] == ["Intro", "Body"]
    assert data[0]["start_page"] == 1


def _make_pdf_with_parts(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    p1 = writer.add_outline_item("Part I", 0)
    writer.add_outline_item("Chapter 1", 0, parent=p1)
    writer.add_outline_item("Chapter 2", 4, parent=p1)
    with path.open("wb") as fh:
        writer.write(fh)


def test_book_split_cli_human_readable_lists_chapters_and_parts(tmp_path: Path) -> None:
    pdf = tmp_path / "parts.pdf"
    _make_pdf_with_parts(pdf, 10)
    result = CliRunner().invoke(main, ["book-split", str(pdf)])  # no --json
    assert result.exit_code == 0, result.output
    assert "Chapter 1" in result.output
    assert "pp. 1-" in result.output            # page-range rendering
    assert "[Part I]" in result.output           # part suffix rendering


def test_book_split_cli_no_outline_exits_nonzero(tmp_path: Path) -> None:
    pdf = tmp_path / "bare.pdf"
    _make_pdf(pdf, 3, [])
    result = CliRunner().invoke(main, ["book-split", str(pdf)])
    assert result.exit_code != 0
    assert "no outline" in result.output.lower()

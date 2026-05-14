"""Tests for science_tool.commons.overlay."""
from __future__ import annotations

from pathlib import Path


def test_read_markdown_body_returns_text_after_frontmatter(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "doc.md"
    md.write_text(
        "---\n"
        "id: \"paper:X\"\n"
        "---\n"
        "\n"
        "# Heading\n"
        "\n"
        "Body text.\n",
        encoding="utf-8",
    )
    body = _read_markdown_body(md)
    assert body == "\n# Heading\n\nBody text.\n"


def test_read_markdown_body_no_frontmatter_returns_whole_file(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "plain.md"
    md.write_text("# Just a heading\n\ntext\n", encoding="utf-8")
    assert _read_markdown_body(md) == "# Just a heading\n\ntext\n"

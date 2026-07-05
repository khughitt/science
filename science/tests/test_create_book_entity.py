from __future__ import annotations

from pathlib import Path

from science_tool.entities import create_entity


def test_create_book_entity_writes_template(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    result = create_entity(tmp_path, "book", "Information Rate", entity_id="book:Kelly1982")
    assert result.entity_id == "book:Kelly1982"
    assert result.warnings == []
    written = tmp_path / "entities" / "books" / "Kelly1982.md"
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    # MIGRATED_KINDS routing => the book template, not the generic Summary/Notes fallback.
    assert "## Whole-Book Synthesis" in text
    assert "kind: book" in text

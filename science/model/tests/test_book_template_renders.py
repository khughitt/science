from __future__ import annotations

from datetime import date

from science_model.templates import Renderer


def test_book_template_renders_from_packaged_copy() -> None:
    out = Renderer(today=date(2026, 6, 13)).render(
        "book",
        fields={
            "entity_id": "book:Kelly1982",
            "title": "A New Interpretation of Information Rate",
            "source_refs": ["cite:Kelly1982"],
            "related": [],
        },
    )
    assert out.startswith("---\n")
    for section in (
        "## Overview",
        "## Whole-Book Synthesis",
        "## Chapter Map",
        "## Key Themes",
        "## Relevance",
        "## Limitations",
        "## Follow-up",
    ):
        assert section in out

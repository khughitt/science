from __future__ import annotations

import re
from datetime import date

import yaml

from science_model.templates import Renderer

_RAW_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def _frontmatter(text: str) -> dict[str, object]:
    _, frontmatter_text, _ = text.split("---\n", 2)
    loaded = yaml.safe_load(frontmatter_text)
    assert isinstance(loaded, dict)
    return loaded


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
    frontmatter = _frontmatter(out)
    assert "_template" not in frontmatter
    assert not _RAW_PLACEHOLDER_RE.search(out), _RAW_PLACEHOLDER_RE.search(out).group(0)

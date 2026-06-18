from science_tool.annotation.internal_prose_adapter import (
    InternalProseAdapter,
    LocatorStatus,
    resolve_markdown_locator,
)
from science_tool.annotation.prose_decomposition import MarkdownLocator, Quote


def test_resolve_unique_heading_path_with_candidate_quote(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nIntro.\n\n## B\n\nThe claim is here.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A", "B"))
    result = resolve_markdown_locator(md, locator, Quote(exact="The claim is here."))
    assert result.status is LocatorStatus.RESOLVED
    assert result.text == "The claim is here."


def test_ambiguous_heading_path_is_reported(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\n## Repeat\n\nOne.\n\n# B\n\n## Repeat\n\nTwo.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("Repeat",))
    result = resolve_markdown_locator(md, locator, Quote(exact="One."))
    assert result.status is LocatorStatus.AMBIGUOUS
    assert "multiple sections" in result.message


def test_quote_missing_is_reported(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nDifferent text.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(md, locator, Quote(exact="The claim is here."))
    assert result.status is LocatorStatus.UNRESOLVED
    assert "quote not found" in result.message


def test_internal_prose_adapter_shape(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text("# Notes\n", encoding="utf-8")
    adapter = InternalProseAdapter()
    assert adapter.name == "internal-prose"
    assert adapter.handles(md) is True
    assert adapter.source_ref(md) == "prose-source:notes"

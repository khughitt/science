from science_tool.annotation.internal_prose_adapter import (
    InternalProseAdapter,
    LocatorStatus,
    resolve_markdown_locator,
)
from science_tool.annotation.prose_decomposition import MarkdownLocator, Quote
from science_tool.annotation.text_source_adapter import LocatorRegime, TEXT_SOURCE_ADAPTERS


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


def test_wrong_prefix_returns_context_mismatch(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nCorrect prefix claim text correct suffix.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(
        md,
        locator,
        Quote(exact="claim text", prefix="Wrong prefix ", suffix=" correct suffix."),
    )
    assert result.status is LocatorStatus.UNRESOLVED
    assert "quote context mismatch" in result.message


def test_wrong_suffix_returns_context_mismatch(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nCorrect prefix claim text correct suffix.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(
        md,
        locator,
        Quote(exact="claim text", prefix="Correct prefix ", suffix=" wrong suffix."),
    )
    assert result.status is LocatorStatus.UNRESOLVED
    assert "quote context mismatch" in result.message


def test_repeated_exact_text_without_context_is_ambiguous(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nFirst claim text.\n\nSecond claim text.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(md, locator, Quote(exact="claim text"))
    assert result.status is LocatorStatus.AMBIGUOUS


def test_repeated_exact_text_with_context_resolves(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nFirst claim text.\n\nSecond claim text.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(
        md,
        locator,
        Quote(exact="claim text", prefix="Second ", suffix="."),
    )
    assert result.status is LocatorStatus.RESOLVED
    assert result.text == "claim text"


def test_internal_prose_adapter_shape(tmp_path):
    md = tmp_path / "notes.md"
    paper_md = tmp_path / "paper.source.md"
    md.write_text("# Notes\n\nBody claim.\n", encoding="utf-8")
    paper_md.write_text("# Paper\n", encoding="utf-8")
    adapter = InternalProseAdapter()
    assert adapter.name == "internal-prose"
    assert adapter.locator_regime is LocatorRegime.REGENERABLE
    assert adapter.can_fetch is False
    assert adapter.can_seed is False
    assert adapter.handles(md) is True
    assert adapter.handles(paper_md) is False
    assert adapter.source_ref(md) == "prose-source:notes"
    assert adapter.source_ref_from_slug("notes") == "prose-source:notes"
    result = adapter.resolve_unit(
        md,
        MarkdownLocator(regime="markdown-heading-path", heading_path=("Notes",)),
        Quote(exact="Body claim."),
    )
    assert result.status is LocatorStatus.RESOLVED


def test_internal_prose_adapter_is_not_registered():
    assert all(not isinstance(adapter, InternalProseAdapter) for adapter in TEXT_SOURCE_ADAPTERS)

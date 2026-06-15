from __future__ import annotations


def test_record_types_live_in_leaf_and_reexport_from_sources() -> None:
    # Canonical home is the leaf module.
    from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument

    # Public path stays valid (aggregate_retire.py + existing tests import from here).
    from science_tool.graph.sources import (
        AggregateRowMeta as SourcesAggregateRowMeta,
        MarkdownSourceDocument as SourcesMarkdownSourceDocument,
    )

    # Re-export must be the SAME object, not a copy.
    assert SourcesAggregateRowMeta is AggregateRowMeta
    assert SourcesMarkdownSourceDocument is MarkdownSourceDocument


def test_leaf_module_does_not_import_sources_or_adapters() -> None:
    import science_tool.graph.source_records as mod

    src = mod.__file__
    assert src is not None
    text = open(src, encoding="utf-8").read()
    assert "from science_tool.graph.sources" not in text
    assert "storage_adapters" not in text

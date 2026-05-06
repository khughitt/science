"""Tests for SourceRef — first-class source-location metadata per spec §Source Location."""

from __future__ import annotations

from science_model.source_ref import SourceRef


def test_source_ref_minimal() -> None:
    ref = SourceRef(adapter_name="markdown", path="doc/hypotheses/h01.md")
    assert ref.adapter_name == "markdown"
    assert ref.path == "doc/hypotheses/h01.md"
    assert ref.line is None


def test_source_ref_with_line() -> None:
    ref = SourceRef(adapter_name="aggregate", path="knowledge/sources/local/entities.yaml", line=42)
    assert ref.line == 42


def test_source_ref_str_is_actionable_in_errors() -> None:
    ref = SourceRef(adapter_name="markdown", path="doc/hypotheses/h01.md", line=7)
    s = str(ref)
    assert "markdown" in s
    assert "doc/hypotheses/h01.md" in s
    assert "7" in s

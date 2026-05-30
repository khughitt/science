"""Regression tests for health degrading on schema-invalid entities (fb-2026-05-30-008).

A single malformed entity must not take ``science health`` fully offline: the
schema-validation failure should surface as a ``schema_invalid`` finding while the
rest of the report still renders. ``science validate`` / graph build stay strict.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.health import build_health_report
from science_tool.graph.sources import load_project_sources


def _project_with_bad_dataset(tmp_path: Path) -> Path:
    """A minimal project with one dataset that is source_class=derived but omits
    the conditionally-required derived_kind (the feedback's exact repro)."""
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    dataset = tmp_path / "doc" / "datasets" / "t007-cohort.md"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(
        "---\n"
        'id: "dataset:t007-cohort"\n'
        'type: "dataset"\n'
        'title: "t007 cohort"\n'
        'origin: "derived"\n'
        'source_class: "derived"\n'
        "---\n",
        encoding="utf-8",
    )
    return tmp_path


def test_strict_load_raises_on_invalid_core_entity(tmp_path: Path) -> None:
    root = _project_with_bad_dataset(tmp_path)
    with pytest.raises(ValueError, match="schema validation failed for registered entity kind"):
        load_project_sources(root, strict_core_schema=True)


def test_nonstrict_load_degrades_to_skipped_entity(tmp_path: Path) -> None:
    root = _project_with_bad_dataset(tmp_path)
    sources = load_project_sources(root, strict_core_schema=False)
    reasons = {s.reason for s in sources.skipped_entities}
    assert "core_schema_validation_failed" in reasons


def test_health_report_renders_with_schema_invalid_finding(tmp_path: Path) -> None:
    root = _project_with_bad_dataset(tmp_path)
    # Must NOT raise (previously aborted the whole command with empty stdout).
    report = build_health_report(root)
    assert "schema_invalid" in report
    assert any(f["code"] == "entity.schema-invalid" for f in report["schema_invalid"])
    assert report["total_issues"] >= 1

from pathlib import Path

from science_tool.findings.catalog import build_project_registry
from science_tool.graph.health import build_health_report
from science_tool.graph.health_projection import project_health_report


def _report(root: Path):
    return build_health_report(
        root,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"tooling_scaffold"},
    )


def test_projection_preserves_full_totals(tmp_path: Path) -> None:
    report = _report(tmp_path)
    projected = project_health_report(
        report,
        registry=build_project_registry(tmp_path),
        threshold="error",
    )
    assert len(projected.findings) == 1
    assert projected.totals == report.totals
    assert projected.metrics == report.metrics
    assert projected.caveats == report.caveats
    assert projected.unwired == report.unwired


def test_threshold_can_hide_rows_without_rewriting_totals(tmp_path: Path) -> None:
    report = _report(tmp_path)
    projected = project_health_report(
        report,
        registry=build_project_registry(tmp_path),
        threshold="error",
        section_row_cap=0,
    )
    assert projected.findings == ()
    assert projected.totals.findings_total == 1

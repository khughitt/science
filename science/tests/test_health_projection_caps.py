from pathlib import Path

from science_model.audit import ReportedFinding

from science_tool.findings.catalog import build_project_registry
from science_tool.graph.health import build_health_report
from science_tool.graph.health_projection import SECTION_ROW_CAP, project_health_report


def test_projection_caps_findings_but_never_actor_channels(tmp_path: Path) -> None:
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"tooling_scaffold"},
        collect_timings=True,
    )
    item = report.findings[0]
    expanded = tuple(
        ReportedFinding(producer_id=item.producer_id, finding=item.finding)
        for _ in range(SECTION_ROW_CAP + 5)
    )
    expanded_report = report.model_copy(update={"findings": expanded})
    projected = project_health_report(
        expanded_report,
        registry=build_project_registry(tmp_path),
        threshold="all",
    )
    assert len(projected.findings) == SECTION_ROW_CAP
    assert projected.totals == report.totals
    assert projected.unwired == report.unwired
    assert projected.caveats == report.caveats
    assert projected.meta.timings == report.meta.timings

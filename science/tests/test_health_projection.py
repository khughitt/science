from pathlib import Path

import pytest
from science_model.audit import AuditReport

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
    assert not isinstance(projected, AuditReport)
    assert len(projected.findings) == 1
    assert projected.report is report


def test_threshold_can_hide_rows_without_rewriting_totals(tmp_path: Path) -> None:
    report = _report(tmp_path)
    projected = project_health_report(
        report,
        registry=build_project_registry(tmp_path),
        threshold="error",
        section_row_cap=0,
    )
    assert projected.findings == ()
    assert projected.report.totals.findings_total == 1


@pytest.mark.parametrize("section_row_cap", [-1, True])
def test_projection_rejects_non_integer_or_negative_section_caps(
    tmp_path: Path,
    section_row_cap: object,
) -> None:
    report = _report(tmp_path)
    with pytest.raises((TypeError, ValueError), match="non-negative integer"):
        project_health_report(
            report,
            registry=build_project_registry(tmp_path),
            threshold="all",
            section_row_cap=section_row_cap,  # type: ignore[arg-type]
        )

"""Generic, loss-aware projection of an :class:`AuditReport` for display."""

from __future__ import annotations

from collections import defaultdict

from science_model.audit import AuditReport, ReportedFinding

from science_tool.findings.producers import FindingRegistry

SECTION_ROW_CAP = 40
_THRESHOLD_FLOOR = {"all": 0, "warn": 1, "error": 2}
_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}


def project_health_report(
    report: AuditReport,
    *,
    registry: FindingRegistry,
    threshold: str,
    section_row_cap: int = SECTION_ROW_CAP,
) -> AuditReport:
    """Cap visible rows per registry section without rewriting report totals."""
    if threshold not in _THRESHOLD_FLOOR:
        raise ValueError(f"unknown health threshold {threshold!r}")
    by_section: dict[str, list[ReportedFinding]] = defaultdict(list)
    for reported in report.findings:
        rule = registry.rule(reported.finding.rule_id)
        if rule.default_visibility != "visible":
            continue
        if _SEVERITY_RANK[reported.finding.severity] < _THRESHOLD_FLOOR[threshold]:
            continue
        by_section[rule.section].append(reported)
    projected: list[ReportedFinding] = []
    for section_id in sorted(
        by_section,
        key=lambda value: registry.section(value).section_order,
    ):
        projected.extend(by_section[section_id][:section_row_cap])
    return report.model_copy(update={"findings": tuple(projected)})

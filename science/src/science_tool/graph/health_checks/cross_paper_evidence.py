"""Cross-paper-evidence health check: derived literature evidence and scanner faults."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

from science_tool.annotation.cross_paper_evidence import (
    build_cross_paper_evidence_report,
    proposition_source_refs_map,
)
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, context_sources


class CrossPaperEvidenceFinding(TypedDict):
    code: str
    severity: str
    sidecar: str
    annotation: str
    reason: str
    detail: str


class CrossPaperEvidenceHealthReport(TypedDict):
    status: str
    empty_state: str
    summary: dict[str, object]
    findings: list[CrossPaperEvidenceFinding]
    propositions: list[dict[str, object]]


def _cross_paper_empty_state(summary: dict[str, object]) -> str:
    if summary.get("propositions") == 0:
        return "no_propositions"
    if summary.get("units") == 0:
        return "no_cross_paper_evidence"
    return "active"


def _project_relative_sidecar(project_root: Path, sidecar: str) -> str:
    path = Path(sidecar)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return sidecar


def _collect_cross_paper_evidence(context: HealthContext) -> CrossPaperEvidenceHealthReport:
    report = build_cross_paper_evidence_report(
        context.project_root,
        proposition_source_refs=proposition_source_refs_map(context_sources(context).entities),
    )
    summary = cast("dict[str, object]", report["summary"])
    findings: list[CrossPaperEvidenceFinding] = [
        {
            "code": f"cross_paper_evidence.{row['reason']}",
            "severity": "error",
            "sidecar": _project_relative_sidecar(context.project_root, row["sidecar"]),
            "annotation": row["annotation"],
            "reason": row["reason"],
            "detail": row["detail"],
        }
        for row in cast("list[dict[str, str]]", report["faults"])
    ]
    return {
        "status": "fail" if findings else "ok",
        "empty_state": _cross_paper_empty_state(summary),
        "summary": summary,
        "findings": findings,
        "propositions": cast("list[dict[str, object]]", report["propositions"]),
    }


def _empty_cross_paper_evidence_health() -> CrossPaperEvidenceHealthReport:
    return {
        "status": "ok",
        "empty_state": "no_propositions",
        "summary": {
            "propositions": 0,
            "propositions_with_units": 0,
            "units": 0,
            "faults": 0,
            "faults_by_reason": {},
            "contested": 0,
        },
        "findings": [],
        "propositions": [],
    }


CHECK = HealthCheck(
    name="cross_paper_evidence",
    description="Report derived cross-paper literature evidence and scanner faults.",
    requires_sources=True,
    run=_collect_cross_paper_evidence,
    empty=lambda _root: _empty_cross_paper_evidence_health(),
)

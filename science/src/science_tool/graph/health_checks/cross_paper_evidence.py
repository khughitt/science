"""Cross-paper-evidence health check: derived literature evidence and scanner faults."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, PathSubject, ProducerMetrics

from science_tool.annotation.cross_paper_evidence import (
    build_cross_paper_evidence_report,
    proposition_source_refs_map,
)
from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result, context_sources
from science_tool.instruments import InstrumentResult


class CrossPaperEvidenceFinding(TypedDict):
    code: str
    severity: str
    sidecar: str
    annotation: str
    reason: str
    detail: str


class CrossPaperEvidenceObservation(TypedDict):
    status: str
    empty_state: str
    summary: dict[str, object]
    findings: list[CrossPaperEvidenceFinding]
    propositions: list[dict[str, object]]


class CrossPaperQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation: str


class CrossPaperMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    empty_state: str
    summary: dict[str, object]
    propositions: list[dict[str, object]]


SECTION = FindingSection(
    id="cross-paper-evidence",
    title="Cross-paper evidence",
    section_order=203,
)
_REASONS = (
    "sidecar-parse-error",
    "non-proposition-target",
    "stale-proposition",
    "invalid-stance",
    "adapter-unresolvable",
    "ownership-mismatch",
)
RULES = {
    reason: FindingRule(
        id=f"cross-paper.{reason}",
        severities=frozenset({"error"}),
        subject_types=frozenset({"path"}),
        qualifier_schema=CrossPaperQualifiers,
        identity_qualifiers=("annotation",),
        title=f"Cross-paper {reason.replace('-', ' ')}",
        section=SECTION.id,
        display_order=index,
    )
    for index, reason in enumerate(_REASONS, start=1)
}
PRODUCER = FindingProducer(
    producer_id="cross_paper_evidence",
    namespace="health_checks",
    source_module="graph/health_checks/cross_paper_evidence.py",
    rules=tuple(RULES.values()),
    sections=(SECTION,),
    metrics_schema=CrossPaperMetrics,
)


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


def _collect_cross_paper_evidence(context: HealthContext) -> CrossPaperEvidenceObservation:
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


def run_check(context: HealthContext):
    report = _collect_cross_paper_evidence(context)
    findings = [
        RULES[row["reason"]].build(
            subject=PathSubject(path=row["sidecar"]),
            severity="error",
            qualifiers={"annotation": row["annotation"]},
            message=row["detail"],
        )
        for row in report["findings"]
    ]
    return composed_result(
        InstrumentResult.from_rows(cast("list[object]", report["findings"])),
        findings,
        metrics=ProducerMetrics.model_validate(
            {
                "status": report["status"],
                "empty_state": report["empty_state"],
                "summary": report["summary"],
                "propositions": report["propositions"],
            }
        ),
    )


CHECK = HealthCheck(
    name="cross_paper_evidence",
    description="Report derived cross-paper literature evidence and scanner faults.",
    requires_sources=True,
    run=run_check,
    producer=PRODUCER,
)

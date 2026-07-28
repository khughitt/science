"""Prose-epistemics health check: reads the project-level prose epistemics artifact."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, PathSubject, ProducerMetrics

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult


class ProseEpistemicsQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str | None


class ProseEpistemicsMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applicable: bool
    summary: "ProseSummaryMetrics | EmptyProseMetrics"
    coverage: "ProseCoverageMetrics | EmptyProseMetrics"
    sources: list["ProseSourceMetrics"]


class EmptyProseMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProseSourceSummaryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_candidate_units: int
    promoted_units: int
    grounded_units: int
    below_floor_units: int
    unbacked_units: int
    unpromoted_units: int
    skipped_units: int
    stale_units: int
    contested_units: int


class ProseSummaryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declared_sources: int
    sources_with_decomposition: int
    sources_with_grounding: int
    current_candidate_units: int
    promoted_units: int
    grounded_units: int
    below_floor_units: int
    unbacked_units: int
    unpromoted_units: int
    skipped_units: int
    stale_units: int
    contested_units: int


class ProseCoverageMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int
    denominator: int
    ratio: float | None


class ProseCoverageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promotion: ProseCoverageMetric
    grounding: ProseCoverageMetric
    strict_grounding: ProseCoverageMetric


class ProseSourceMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str
    title: str
    path: str
    decomposition_artifact_id: str | None
    grounding_report_path: str
    summary: ProseSourceSummaryMetrics
    state: Literal[
        "missing_decomposition",
        "invalid_decomposition",
        "missing_grounding",
        "invalid_grounding",
        "stale_grounding",
        "complete",
    ]


SECTION = FindingSection(
    id="prose-epistemics",
    title="Prose epistemics",
    section_order=207,
)
_CODES = (
    "manifest_invalid",
    "prose_health_artifact_missing",
    "prose_health_artifact_invalid",
    "missing_decomposition",
    "invalid_decomposition",
    "missing_grounding",
    "invalid_grounding",
    "stale_grounding",
    "undeclared_grounding_report",
)
RULES = {
    code: FindingRule(
        id=f"prose-epistemics.{code.replace('_', '-')}",
        severities=frozenset({"error", "warn"}),
        subject_types=frozenset({"path"}),
        qualifier_schema=ProseEpistemicsQualifiers,
        title=code.replace("_", " ").title(),
        section=SECTION.id,
        display_order=index,
    )
    for index, code in enumerate(_CODES, start=1)
}
PRODUCER = FindingProducer(
    producer_id="prose_epistemics",
    namespace="health_checks",
    source_module="graph/health_checks/prose_epistemics.py",
    rules=tuple(RULES.values()),
    sections=(SECTION,),
    metrics_schema=ProseEpistemicsMetrics,
)


def _empty_prose_epistemics() -> dict[str, object]:
    return {
        "applicable": False,
        "summary": {},
        "coverage": {},
        "sources": [],
        "findings": [],
    }


def _collect_prose_epistemics(context: HealthContext) -> dict[str, object]:
    from science_tool.annotation.prose_health import (
        ProseHealthError,
        load_prose_health_artifact,
        load_prose_health_manifest,
        prose_health_manifest_path,
        prose_health_path,
    )

    manifest_path = prose_health_manifest_path(context.project_root)
    artifact_path = prose_health_path(context.project_root)
    if not manifest_path.exists() and not artifact_path.exists():
        return _empty_prose_epistemics()
    if manifest_path.exists():
        try:
            load_prose_health_manifest(context.project_root)
        except ProseHealthError as exc:
            return {
                "applicable": True,
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [
                    {
                        "code": "manifest_invalid",
                        "severity": "error",
                        "counts_as_issue": True,
                        "source_ref": None,
                        "path": manifest_path.relative_to(context.project_root).as_posix(),
                        "message": str(exc),
                    }
                ],
            }
    if not artifact_path.exists():
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_missing",
                    "severity": "warning",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": (
                        "Prose health manifest exists but prose-health.json is missing; "
                        "run science annotate build-prose-health --write."
                    ),
                }
            ],
        }
    try:
        artifact = load_prose_health_artifact(context.project_root)
    except ProseHealthError as exc:
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_invalid",
                    "severity": "error",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": str(exc),
                }
            ],
        }
    return {
        "applicable": True,
        "summary": artifact.get("summary", {}),
        "coverage": artifact.get("coverage", {}),
        "sources": artifact.get("sources", []),
        "findings": artifact.get("findings", []),
    }


def run_check(context: HealthContext):
    report = _collect_prose_epistemics(context)
    rows = cast("list[dict[str, object]]", report["findings"])
    findings = [
        RULES[str(row["code"])].build(
            subject=PathSubject(path=str(row["path"])),
            severity="warn" if row["severity"] == "warning" else "error",
            qualifiers={"source_ref": row.get("source_ref")},
            message=str(row["message"]),
        )
        for row in rows
        if row.get("counts_as_issue") is True
    ]
    return composed_result(
        InstrumentResult.from_rows(cast("list[object]", rows)),
        findings,
        metrics=ProducerMetrics.model_validate(
            {
                "applicable": report["applicable"],
                "summary": report["summary"],
                "coverage": report["coverage"],
                "sources": report["sources"],
            }
        ),
    )


CHECK = HealthCheck(
    name="prose_epistemics",
    description="Read the project-level prose epistemics health artifact.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)

"""Entity-identity health check: canonical entity identifiers, baseline status, and prose references."""

from __future__ import annotations

from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    EntitySubject,
    FindingRule,
    FindingSection,
    LocationEvidence,
    PathSubject,
    Severity,
)
from science_model.audit.subjects import SubjectError
from science_model.contracts.inventory_common import InventoryWarning

from science_tool.data_root import PROJECT_CONFIG_FILENAME
from science_tool.entity_identity import collect_identity_warnings
from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result, context_sources
from science_tool.instruments import InstrumentResult


class EntityIdentityFinding(TypedDict):
    code: str
    severity: str
    message: str
    path: str | None
    canonical_id: str | None


class EntityIdentityQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


SECTION = FindingSection(id="entity-identity", title="Entity identity", section_order=201)
RULE = FindingRule(
    id="identity.entity",
    severities=frozenset({"error", "warn"}),
    subject_types=frozenset({"entity", "path"}),
    qualifier_schema=EntityIdentityQualifiers,
    identity_qualifiers=("code",),
    title="Entity identity",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="entity_identity",
    namespace="health_checks",
    source_module="graph/health_checks/entity_identity.py",
    rules=(RULE,),
    sections=(SECTION,),
)


def _entity_identity_finding(warning: InventoryWarning) -> EntityIdentityFinding:
    return {
        "code": warning.code,
        "severity": warning.severity,
        "message": warning.message,
        "path": warning.path,
        "canonical_id": warning.canonical_id,
    }


def _collect_entity_identity(context: HealthContext) -> list[EntityIdentityFinding]:
    sources = context_sources(context)
    return [
        _entity_identity_finding(warning)
        for warning in collect_identity_warnings(context.project_root, sources=sources)
    ]


def _subject(row: EntityIdentityFinding):
    if row["canonical_id"]:
        try:
            return EntitySubject(ref=row["canonical_id"])
        except (SubjectError, ValueError):
            pass
    return PathSubject(path=row["path"] or PROJECT_CONFIG_FILENAME)


def _severity(value: str) -> Severity:
    normalized = "warn" if value == "warning" else value
    if normalized not in {"error", "warn", "info"}:
        raise ValueError(f"unknown entity identity severity {value!r}")
    return cast(Severity, normalized)


def run_check(context: HealthContext):
    rows = _collect_entity_identity(context)
    observed = InstrumentResult.from_rows(rows)
    findings = [
        RULE.build(
            subject=_subject(row),
            severity=_severity(row["severity"]),
            qualifiers={"code": row["code"]},
            message=row["message"],
            evidence=[LocationEvidence(path=row["path"])] if row["path"] else [],
        )
        for row in rows
    ]
    return composed_result(observed, findings)


CHECK = HealthCheck(
    name="entity_identity",
    description="Validate canonical entity identifiers, baseline status, and prose references.",
    requires_sources=True,
    run=run_check,
    producer=PRODUCER,
)

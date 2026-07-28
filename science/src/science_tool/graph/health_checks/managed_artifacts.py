"""Managed-artifacts health check: installed managed artifacts vs. canonical versions."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    FindingRule,
    FindingSection,
    IdentifierSubject,
    ProducerMetrics,
)

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult


class ManagedArtifactQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_target: str
    version: str
    status: str


class ManagedArtifactMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory: list[dict[str, object]]


SECTION = FindingSection(
    id="managed-artifacts",
    title="Managed artifacts",
    section_order=204,
)
_ISSUE_STATUSES = ("stale", "locally_modified", "missing", "pinned_but_locally_modified")
RULES = {
    status: FindingRule(
        id=f"managed-artifact.{status.replace('_', '-')}",
        severities=frozenset({"warn"}),
        subject_types=frozenset({"identifier"}),
        identifier_namespaces=frozenset({"managed-artifact"}),
        qualifier_schema=ManagedArtifactQualifiers,
        title=f"Managed artifact {status.replace('_', ' ')}",
        section=SECTION.id,
        display_order=index,
    )
    for index, status in enumerate(_ISSUE_STATUSES, start=1)
}
PRODUCER = FindingProducer(
    producer_id="managed_artifacts",
    namespace="health_checks",
    source_module="graph/health_checks/managed_artifacts.py",
    rules=tuple(RULES.values()),
    sections=(SECTION,),
    metrics_schema=ManagedArtifactMetrics,
)


def _collect_managed_artifacts(context: HealthContext) -> list[dict]:
    from science_tool.project_artifacts.health_integration import health_findings

    return cast("list[dict]", health_findings(context.project_root))


def run_check(context: HealthContext):
    rows = _collect_managed_artifacts(context)
    findings = [
        RULES[row["status"]].build(
            subject=IdentifierSubject(namespace="managed-artifact", value=str(row["name"])),
            severity="warn",
            qualifiers={
                "install_target": str(row["install_target"]),
                "version": str(row["version"]),
                "status": str(row["status"]),
            },
            message=str(row["detail"]),
        )
        for row in rows
        if row["counts_as_issue"]
    ]
    return composed_result(
        InstrumentResult.from_rows(cast("list[object]", rows)),
        findings,
        metrics=ProducerMetrics.model_validate({"inventory": rows}),
    )


CHECK = HealthCheck(
    name="managed_artifacts",
    description="Check installed managed artifacts against canonical versions.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)

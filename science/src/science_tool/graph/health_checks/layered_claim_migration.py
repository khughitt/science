"""Layered-claim-migration health check: layered-claim adoption gaps and migration issues."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    EntitySubject,
    FindingRule,
    FindingSection,
    LocationEvidence,
    ProducerMetrics,
    ProjectSubject,
)

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result, context_sources
from science_tool.graph.migrate import (
    LayeredClaimMigrationReport,
    build_layered_claim_migration_report,
)
from science_tool.instruments import InstrumentResult


class LayeredClaimMigrationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warnings: list[str]
    todos: list[str]


class RivalModelQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: str


class CoverageIncompleteQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axis: str


class CoverageMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int
    denominator: int
    fraction: float


class LayeredClaimMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposition_claim_layer_coverage: CoverageMetric
    causal_leaning_identification_coverage: CoverageMetric


SECTION = FindingSection(
    id="layered-claim-migration",
    title="Layered claim migration",
    section_order=202,
)
RULE_MIGRATION = FindingRule(
    id="layered-claim.migration",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"entity"}),
    qualifier_schema=LayeredClaimMigrationQualifiers,
    title="Layered claim migration",
    section=SECTION.id,
    display_order=1,
)
RULE_RIVAL_MODEL = FindingRule(
    id="layered-claim.rival-model-gap",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"entity"}),
    qualifier_schema=RivalModelQualifiers,
    identity_qualifiers=("packet_id",),
    title="Rival model gap",
    section=SECTION.id,
    display_order=2,
)
RULE_COVERAGE = FindingRule(
    id="layered-claim.coverage-incomplete",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=CoverageIncompleteQualifiers,
    identity_qualifiers=("axis",),
    title="Layered claim coverage incomplete",
    section=SECTION.id,
    display_order=3,
)
PRODUCER = FindingProducer(
    producer_id="layered_claim_migration",
    namespace="health_checks",
    source_module="graph/health_checks/layered_claim_migration.py",
    rules=(RULE_MIGRATION, RULE_RIVAL_MODEL, RULE_COVERAGE),
    sections=(SECTION,),
    metrics_schema=LayeredClaimMetrics,
)


def _metric(numerator: int, denominator: int) -> dict[str, int | float]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": 1.0 if denominator == 0 else numerator / denominator,
    }


def run_check(context: HealthContext):
    report: LayeredClaimMigrationReport = build_layered_claim_migration_report(
        context.project_root,
        sources=context_sources(context),
    )
    rows = report["rows"]
    propositions = [
        entity for entity in context_sources(context).entities if entity.kind == "proposition"
    ]
    causal = [
        row
        for row in rows
        if row["authored_claim_layer"] in {"causal_effect", "mechanistic_narrative"}
        or row["authored_identification_strength"] is not None
        or row["inferred_identification_strength"] is not None
        or any("mechanistic" in warning.lower() for warning in row["warnings"])
    ]
    claim_metric = _metric(
        report["summary"]["authored_claim_layer_count"],
        report["summary"]["proposition_count"],
    )
    identification_metric = _metric(
        sum(bool(row["authored_identification_strength"]) for row in causal),
        len(causal),
    )
    findings = [
        RULE_MIGRATION.build(
            subject=EntitySubject(ref=row["proposition"]),
            severity="warn",
            qualifiers={"warnings": row["warnings"], "todos": row["todos"]},
            message="; ".join((*row["warnings"], *row["todos"])),
            evidence=[LocationEvidence(path=row["source_path"])],
        )
        for row in rows
        if row["warnings"] or row["todos"]
    ]
    for entity in propositions:
        packet = getattr(entity, "rival_model_packet", None)
        if packet is None or packet.discriminating_predictions:
            continue
        findings.append(
            RULE_RIVAL_MODEL.build(
                subject=EntitySubject(ref=entity.canonical_id),
                severity="warn",
                qualifiers={"packet_id": packet.packet_id},
                message="Rival-model packet lacks discriminating predictions.",
                evidence=[LocationEvidence(path=entity.file_path)],
            )
        )
    for axis, metric in (
        ("claim-layer", claim_metric),
        ("identification-strength", identification_metric),
    ):
        if metric["numerator"] < metric["denominator"]:
            findings.append(
                RULE_COVERAGE.build(
                    subject=ProjectSubject(),
                    severity="warn",
                    qualifiers={"axis": axis},
                    message=(
                        f"{axis} coverage is {metric['numerator']}/{metric['denominator']}."
                    ),
                )
            )
    return composed_result(
        InstrumentResult.from_rows(list(rows)),
        findings,
        metrics=ProducerMetrics.model_validate(
            {
                "proposition_claim_layer_coverage": claim_metric,
                "causal_leaning_identification_coverage": identification_metric,
            }
        ),
    )


CHECK = HealthCheck(
    name="layered_claim_migration",
    description="Report layered-claim adoption gaps and migration issues.",
    requires_sources=True,
    run=run_check,
    producer=PRODUCER,
)

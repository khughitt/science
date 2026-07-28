"""Source-load producer for core entities skipped after schema validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, PathSubject, TextEvidence

from science_tool.findings.producers import FindingProducer, FindingProducerResult
from science_tool.graph.sources import SkippedEntity
from science_tool.instruments import InstrumentResult


class SchemaInvalidQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    reason: str


SECTION = FindingSection(
    id="schema-invalid",
    title="Schema-invalid entities",
    section_order=215,
)
RULE = FindingRule(
    id="entity.schema-invalid",
    severities=frozenset({"error"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=SchemaInvalidQualifiers,
    title="Schema-invalid entity",
    section=SECTION.id,
    display_order=1,
)
SCHEMA_INVALID_PRODUCER = FindingProducer(
    producer_id="schema_invalid",
    namespace="health_checks",
    source_module="graph/health_checks/schema_invalid.py",
    rules=(RULE,),
    sections=(SECTION,),
)


def produce_schema_invalid(
    skipped_entities: list[SkippedEntity],
) -> FindingProducerResult:
    findings = [
        RULE.build(
            subject=PathSubject(path=row.path),
            severity="error",
            qualifiers={"kind": row.kind, "reason": row.reason},
            message=f"{row.kind} entity failed schema validation: {row.details}",
            evidence=[TextEvidence(label="validation details", text=row.details)],
        )
        for row in skipped_entities
        if row.reason
        in {"entity_schema_validation_failed", "core_schema_validation_failed"}
    ]
    return FindingProducerResult(instrument=InstrumentResult.from_rows(findings))

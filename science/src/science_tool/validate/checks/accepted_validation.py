"""Positive classification for configured validation acceptances."""

from __future__ import annotations

from collections.abc import Iterator

from science_model.audit import FindingRule, FindingSection, IdentifierSubject

from science_tool.validate.acceptance import (
    CurrentAcceptance,
    InvalidAcceptance,
    LegacyAcceptance,
    accepted_validation_entries,
    classify_acceptance_entry,
)
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import (
    EmptyQualifiers,
    validation_observation,
)
from science_tool.validate.result import Severity

SECTION = FindingSection(
    id="accepted-validation",
    title="accepted validation",
    section_order=160,
)
RULE_LEGACY_SHAPE = FindingRule(
    id="accepted-validation.legacy-shape",
    severities=frozenset({"error"}),
    subject_types=frozenset({"identifier"}),
    identifier_namespaces=frozenset({"accepted-validation"}),
    qualifier_schema=EmptyQualifiers,
    identity_qualifiers=(),
    title="Legacy validation acceptance",
    section=SECTION.id,
    display_order=16001,
    default_visibility="visible",
)
RULE_INVALID_ENTRY = FindingRule(
    id="accepted-validation.invalid-entry",
    severities=frozenset({"error"}),
    subject_types=frozenset({"identifier"}),
    identifier_namespaces=frozenset({"accepted-validation"}),
    qualifier_schema=EmptyQualifiers,
    identity_qualifiers=(),
    title="Invalid validation acceptance",
    section=SECTION.id,
    display_order=16002,
    default_visibility="visible",
)
RULES = {rule.id: rule for rule in (RULE_LEGACY_SHAPE, RULE_INVALID_ENTRY)}


@Check(
    section=SECTION,
    order=206,
    producer_id="validate.accepted-validation",
    rules=tuple(RULES.values()),
)
def check_accepted_validation(
    ctx: ValidateContext,
) -> Iterator[CheckObservation]:
    emitted: set[str] = set()
    for raw in accepted_validation_entries(ctx.project_root):
        classified = classify_acceptance_entry(raw)
        if isinstance(classified, CurrentAcceptance):
            continue
        if classified.raw_digest in emitted:
            continue
        emitted.add(classified.raw_digest)
        subject = IdentifierSubject(
            namespace="accepted-validation",
            value=classified.raw_digest,
        )
        if isinstance(classified, LegacyAcceptance):
            yield validation_observation(
                severity=Severity.ERROR,
                path=None,
                line=None,
                message=(
                    "legacy accepted_validation entry cannot suppress findings; "
                    "run `science findings migrate-acceptances`"
                ),
                rule=RULE_LEGACY_SHAPE,
                task=None,
                qualifiers={},
                subject=subject,
            )
        elif isinstance(classified, InvalidAcceptance):
            yield validation_observation(
                severity=Severity.ERROR,
                path=None,
                line=None,
                message=(f"invalid accepted_validation entry cannot suppress findings: {classified.error}"),
                rule=RULE_INVALID_ENTRY,
                task=None,
                qualifiers={},
                subject=subject,
            )

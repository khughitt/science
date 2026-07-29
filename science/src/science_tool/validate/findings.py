from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field
from science_model.audit import (
    AuditFinding,
    Evidence,
    FindingRule,
    FindingSection,
    FindingSubject,
    LocationEvidence,
    PathSubject,
    ProjectSubject,
    Severity as AuditSeverity,
)
from science_model.audit.rules import SubjectType, Visibility

from science_tool.findings.paths import project_relative
from science_tool.validate.observations import ValidationNotice

if TYPE_CHECKING:
    from science_tool.validate.checks import CheckObservation
    from science_tool.validate.result import Severity


class EmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: list[str]
    task: str | None = None


class ProseHitQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check: str
    match: str


class ProseAdvisoryQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check: str
    count: int = Field(ge=1)


class CorrespondenceQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str | None = None
    evidence_signature: str


class NumericVerificationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: int = Field(ge=0)
    unverifiable: int = Field(ge=0)
    mismatch: int = Field(ge=0)
    error: int = Field(ge=0)


def declare_validation_rules(
    *,
    section_id: str,
    section_title: str,
    section_order: int,
    rule_ids: Sequence[str],
    severities: frozenset[AuditSeverity] = frozenset({"error", "warn"}),
    subject_types: frozenset[SubjectType] = frozenset({"path", "project"}),
    qualifier_schema: type[BaseModel] = ValidationQualifiers,
    identity_qualifiers: tuple[str, ...] = ("key",),
    default_visibility: Visibility = "visible",
) -> tuple[FindingSection, dict[str, FindingRule]]:
    """Declare one validation module's finite ordinary-rule table."""
    section = FindingSection(
        id=section_id,
        title=section_title,
        section_order=section_order,
    )
    rules = {
        rule_id: FindingRule(
            id=rule_id,
            severities=severities,
            subject_types=subject_types,
            qualifier_schema=qualifier_schema,
            identity_qualifiers=identity_qualifiers,
            title=rule_id,
            section=section.id,
            display_order=section_order * 100 + index,
            default_visibility=default_visibility,
        )
        for index, rule_id in enumerate(rule_ids, start=1)
    }
    return section, rules


_POLICY_INFO_RULE_IDS = frozenset(
    {
        "prose-lints.config",
        "prose-lints.advisory",
    }
)


def is_policy_info_rule(rule: FindingRule) -> bool:
    """Return whether an INFO result is an intentional policy finding."""
    return rule.id in _POLICY_INFO_RULE_IDS


def validation_observation(
    *,
    severity: Severity,
    path: Path | None,
    line: int | None,
    message: str,
    rule: FindingRule,
    task: str | None,
    qualifiers: Mapping[str, object],
    evidence: Sequence[Evidence] = (),
) -> CheckObservation:
    """Build the internal issue/notice split before the producer boundary."""
    if severity.value == "info" and not is_policy_info_rule(rule):
        return ValidationNotice(path=path, line=line, message=message)
    from science_tool.validate.result import Result

    return Result(
        severity=severity,
        path=path,
        line=line,
        message=message,
        rule=rule,
        task=task,
        qualifiers=qualifiers,
        evidence=tuple(evidence),
    )


def rule_kind_segment(kind: str) -> str:
    return kind.lower().replace("_", "-")


def validation_subject(project_root: Path, path: Path | None) -> FindingSubject:
    if path is None:
        return ProjectSubject()
    return PathSubject(path=project_relative(project_root, path))


def validation_evidence(
    project_root: Path,
    path: Path | None,
    line: int | None,
) -> tuple[LocationEvidence, ...]:
    if path is None or line is None:
        return ()
    return (
        LocationEvidence(
            path=project_relative(project_root, path),
            line=line,
        ),
    )


def build_validation_finding(
    *,
    project_root: Path,
    rule: FindingRule,
    severity: str,
    path: Path | None,
    line: int | None,
    message: str,
    qualifiers: dict[str, object],
    evidence: Sequence[Evidence] = (),
) -> AuditFinding:
    return rule.build(
        subject=validation_subject(project_root, path),
        severity=cast(AuditSeverity, severity),
        qualifiers=qualifiers,
        message=message,
        evidence=[
            *validation_evidence(project_root, path, line),
            *evidence,
        ],
    )

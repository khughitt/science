from __future__ import annotations

from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field
from science_model.audit import (
    AuditFinding,
    FindingRule,
    FindingSubject,
    LocationEvidence,
    PathSubject,
    ProjectSubject,
    Severity,
)

from science_tool.findings.paths import project_relative


class EmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: list[str]
    task: str | None = None


class ProseHitQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check: str


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


def rule_kind_segment(kind: str) -> str:
    return kind.replace("_", "-")


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
) -> AuditFinding:
    return rule.build(
        subject=validation_subject(project_root, path),
        severity=cast(Severity, severity),
        qualifiers=qualifiers,
        message=message,
        evidence=list(validation_evidence(project_root, path, line)),
    )

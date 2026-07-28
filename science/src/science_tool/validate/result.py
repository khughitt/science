from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from science_model.audit import AuditFinding, Evidence, FindingRule

from science_tool.validate.findings import build_validation_finding


class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    @classmethod
    def from_str(cls, name: str) -> "Severity":
        normalized = name.lower()
        for severity in cls:
            if normalized in {severity.name.lower(), severity.value}:
                return severity
        raise ValueError(f"unknown severity: {name}")


@dataclass(frozen=True)
class Result:
    severity: Severity
    path: Path | None
    line: int | None
    message: str
    rule: FindingRule
    task: str | None
    qualifiers: Mapping[str, object]
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rule, FindingRule):
            raise TypeError(f"Result.rule must be FindingRule, got {type(self.rule).__name__}")

    @property
    def rule_id(self) -> str:
        return self.rule.id

    def to_finding(self, project_root: Path) -> AuditFinding:
        observed = dict(self.qualifiers)
        if self.task is not None and "task" not in observed:
            observed["task"] = self.task
        return build_validation_finding(
            project_root=project_root,
            rule=self.rule,
            severity=self.severity.value,
            path=self.path,
            line=self.line,
            message=self.message,
            qualifiers=observed,
            evidence=self.evidence,
        )

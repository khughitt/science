from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


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
    rule: str | None
    task: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "path": str(self.path) if self.path is not None else None,
            "line": self.line,
            "message": self.message,
            "rule": self.rule,
            "task": self.task,
        }

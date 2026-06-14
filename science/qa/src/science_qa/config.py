from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class QAConfigError(Exception):
    """Raised when the QA config is missing or malformed (fail early, explicit)."""


@dataclass
class QAConfig:
    program: str = ""
    unique_key: str | None = None
    required_complete: list[str] = field(default_factory=list)
    categoricals: dict[str, dict] = field(default_factory=dict)
    exclusive_flags: list[list[str]] = field(default_factory=list)
    expected_types: dict[str, str] = field(default_factory=dict)
    polarity: list[str] = field(default_factory=list)
    ranges: dict[str, dict] = field(default_factory=dict)
    bounds: dict[str, dict] = field(default_factory=dict)
    unique_keys: list[list[str]] = field(default_factory=list)
    missing_sentinels: list = field(default_factory=list)
    column_sets: dict[str, object] = field(default_factory=dict)
    aspect_params: dict[str, dict] = field(default_factory=dict)
    project_local: list[str] = field(default_factory=list)
    base_dir: Path = field(default_factory=lambda: Path("."))

    @classmethod
    def from_file(cls, path: Path, require_program: bool = True) -> "QAConfig":
        if not path.exists():
            raise QAConfigError(f"QA config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "qa" not in data:
            raise QAConfigError(f"config {path} has no 'qa:' block")
        qa = data["qa"] or {}
        program = qa.get("program")
        if require_program and not program:
            raise QAConfigError(f"config {path} has no 'program:' key (required)")
        return cls(
            program=str(program) if program else "",
            unique_key=qa.get("unique_key"),
            required_complete=list(qa.get("required_complete", []) or []),
            categoricals=dict(qa.get("categoricals", {}) or {}),
            exclusive_flags=[list(pair) for pair in (qa.get("exclusive_flags", []) or [])],
            expected_types=dict(qa.get("expected_types", {}) or {}),
            polarity=list(qa.get("polarity", []) or []),
            ranges=dict(qa.get("ranges", {}) or {}),
            bounds=dict(qa.get("bounds", {}) or {}),
            unique_keys=[list(g) for g in (qa.get("unique_keys", []) or [])],
            missing_sentinels=list(qa.get("missing_sentinels", []) or []),
            column_sets=dict(qa.get("column_sets", {}) or {}),
            aspect_params=dict(qa.get("aspect_params", {}) or {}),
            project_local=list(qa.get("project_local", []) or []),
            base_dir=path.parent,
        )

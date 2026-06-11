from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class QAConfigError(Exception):
    """Raised when the QA config is missing or malformed (fail early, explicit)."""


@dataclass
class QAConfig:
    unique_key: str | None = None
    required_complete: list[str] = field(default_factory=list)
    categoricals: dict[str, dict] = field(default_factory=dict)
    exclusive_flags: list[list[str]] = field(default_factory=list)
    ranges: dict[str, dict] = field(default_factory=dict)
    missing_sentinels: list = field(default_factory=list)
    packs: list[str] = field(default_factory=list)
    pack_params: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "QAConfig":
        if not path.exists():
            raise QAConfigError(f"QA config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "qa" not in data:
            raise QAConfigError(f"config {path} has no 'qa:' block")
        qa = data["qa"] or {}
        return cls(
            unique_key=qa.get("unique_key"),
            required_complete=list(qa.get("required_complete", []) or []),
            categoricals=dict(qa.get("categoricals", {}) or {}),
            exclusive_flags=[list(pair) for pair in (qa.get("exclusive_flags", []) or [])],
            ranges=dict(qa.get("ranges", {}) or {}),
            missing_sentinels=list(qa.get("missing_sentinels", []) or []),
            packs=list(qa.get("packs", []) or []),
            pack_params=dict(qa.get("pack_params", {}) or {}),
        )

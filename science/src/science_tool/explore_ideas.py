from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)
_VALID_DECISIONS = {"keep", "drop", "defer", "applied"}
_ROUTABLE_KINDS = {"question", "hypothesis"}
_MANUAL_KINDS = {"topic", "theme"}
_VALID_KINDS = _ROUTABLE_KINDS | _MANUAL_KINDS


class ApplyValidationError(Exception):
    """Bad or ambiguous report input; raised before any entity is written."""


class ApplyWriteBackError(Exception):
    """A report write-back failed AFTER an entity was created (fatal, non-resumable)."""


@dataclass(frozen=True)
class CandidateBlock:
    candidate_id: str
    data: dict


def resolve_report_path(project_root: Path, from_value: str) -> Path:
    direct = Path(from_value)
    if direct.is_file():
        return direct

    candidate = project_root / "entities" / "meta" / "explorations" / f"{from_value}.md"
    if candidate.is_file():
        return candidate

    raise ApplyValidationError(
        f"report not found: {from_value!r} (looked for a file path and for "
        f"entities/meta/explorations/{from_value}.md)"
    )


def parse_report(text: str) -> list[CandidateBlock]:
    blocks: list[CandidateBlock] = []
    for raw in _YAML_BLOCK_RE.findall(text):
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ApplyValidationError(f"invalid yaml candidate block: {exc}") from exc

        if isinstance(data, dict) and "candidate_id" in data:
            blocks.append(CandidateBlock(candidate_id=str(data["candidate_id"]), data=data))
    return blocks

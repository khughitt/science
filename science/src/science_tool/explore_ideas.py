from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from science_model.entities import OriginRecord

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


@dataclass(frozen=True)
class CreatePlan:
    candidate_id: str
    kind: str
    title: str
    origins: list[dict]
    source_refs: list[str]
    added_by: str


@dataclass(frozen=True)
class ReportPlan:
    to_create: list[CreatePlan]
    skipped_applied: list[str]
    skipped_other: list[str]
    manual: list[tuple[str, str]]


def resolve_report_path(project_root: Path, from_value: str) -> Path:
    direct = Path(from_value)
    if direct.is_absolute():
        if direct.is_file():
            return direct
    else:
        anchored_direct = project_root / direct
        if anchored_direct.is_file():
            return anchored_direct

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


def _normalize_origin(origin: object, candidate_id: str) -> dict:
    if not isinstance(origin, dict):
        raise ApplyValidationError(f"{candidate_id}: origin entry must be a mapping")
    normalized = dict(origin)
    value = normalized.get("date")
    if isinstance(value, date):
        normalized["date"] = value.isoformat()
    try:
        return OriginRecord.model_validate(normalized).model_dump(
            mode="json", exclude_none=True, exclude_defaults=True
        )
    except ValidationError as exc:
        raise ApplyValidationError(f"{candidate_id}: invalid origin {normalized!r}: {exc}") from exc


def build_create_plan(candidate_id: str, data: dict, model_id: str) -> CreatePlan:
    kind = data.get("proposed_kind")
    if not isinstance(kind, str) or kind not in _ROUTABLE_KINDS:
        raise ApplyValidationError(f"{candidate_id}: keep block has invalid 'proposed_kind'")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ApplyValidationError(f"{candidate_id}: keep block missing a non-empty 'title'")

    origin_plan = data.get("origin_plan")
    origins_raw = origin_plan.get("origins") if isinstance(origin_plan, dict) else None
    if not origins_raw:
        raise ApplyValidationError(f"{candidate_id}: keep block missing 'origin_plan.origins'")

    origins: list[dict] = []
    for origin in origins_raw:
        origins.append(_normalize_origin(origin, candidate_id))

    anchors = data.get("literature_anchors") or []
    source_refs: list[str] = []
    seen: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ApplyValidationError(
                f"{candidate_id}: literature_anchors entry must be a mapping"
            )
        ref = anchor.get("ref")
        note = anchor.get("note")
        if note is not None and not isinstance(note, str):
            raise ApplyValidationError(f"{candidate_id}: anchor 'note' must be a string")
        if ref is None:
            continue
        if not isinstance(ref, str):
            raise ApplyValidationError(f"{candidate_id}: anchor 'ref' must be a string")
        if (note or "").startswith("predates:"):
            continue
        if ref not in seen:
            seen.add(ref)
            source_refs.append(ref)

    return CreatePlan(
        candidate_id=candidate_id,
        kind=kind,
        title=title,
        origins=origins,
        source_refs=source_refs,
        added_by=f"explore-ideas:{model_id}:{candidate_id}",
    )


def plan_report(blocks: list[CandidateBlock], model_id: str) -> ReportPlan:
    seen_ids: set[str] = set()
    duplicates: set[str] = set()
    for block in blocks:
        if block.candidate_id in seen_ids:
            duplicates.add(block.candidate_id)
        else:
            seen_ids.add(block.candidate_id)
    if duplicates:
        raise ApplyValidationError(f"duplicate candidate_id(s): {', '.join(sorted(duplicates))}")

    to_create: list[CreatePlan] = []
    skipped_applied: list[str] = []
    skipped_other: list[str] = []
    manual: list[tuple[str, str]] = []
    errors: list[str] = []

    for block in blocks:
        decision = block.data.get("decision")
        if decision not in _VALID_DECISIONS:
            errors.append(f"{block.candidate_id}: unknown decision {decision!r}")
            continue
        if decision == "applied":
            skipped_applied.append(block.candidate_id)
            continue
        if decision in {"drop", "defer"}:
            skipped_other.append(block.candidate_id)
            continue

        kind = block.data.get("proposed_kind")
        if kind not in _VALID_KINDS:
            errors.append(f"{block.candidate_id}: unknown proposed_kind {kind!r}")
            continue
        if kind in _MANUAL_KINDS:
            manual.append((block.candidate_id, kind))
            continue

        try:
            to_create.append(build_create_plan(block.candidate_id, block.data, model_id))
        except ApplyValidationError as exc:
            errors.append(str(exc))

    if errors:
        raise ApplyValidationError("invalid keep block(s): " + "; ".join(errors))

    return ReportPlan(
        to_create=to_create,
        skipped_applied=skipped_applied,
        skipped_other=skipped_other,
        manual=manual,
    )

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from science_model.entities import LensView, OriginRecord
from science_tool.entities import EntityCommandError, create_entity

_YAML_BLOCK_RE = re.compile(r"```yaml\r?\n(.*?)```", re.DOTALL)
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
    lens_views: list[dict]
    added_by: str


@dataclass(frozen=True)
class ReportPlan:
    to_create: list[CreatePlan]
    skipped_applied: list[str]
    skipped_other: list[str]
    manual: list[tuple[str, str]]


@dataclass(frozen=True)
class CreatedEntity:
    candidate_id: str
    entity_id: str
    kind: str
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class ApplyResult:
    report: Path
    created: list[CreatedEntity]
    skipped_applied: list[str]
    skipped_other: list[str]
    manual: list[tuple[str, str]]
    failures: list[tuple[str, str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "report": str(self.report),
            "created": [
                {
                    "candidate_id": created.candidate_id,
                    "entity_id": created.entity_id,
                    "kind": created.kind,
                    "path": str(created.path),
                    "warnings": list(created.warnings),
                }
                for created in self.created
            ],
            "skipped_applied": list(self.skipped_applied),
            "skipped_other": list(self.skipped_other),
            "manual": [
                {"candidate_id": candidate_id, "proposed_kind": kind}
                for candidate_id, kind in self.manual
            ],
            "failures": [
                {"candidate_id": candidate_id, "error": error}
                for candidate_id, error in self.failures
            ],
        }


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


def _normalize_lens_view(view: object, candidate_id: str, planned_refs: set[str]) -> dict:
    if not isinstance(view, dict):
        raise ApplyValidationError(f"{candidate_id}: lens_views entry must be a mapping")
    try:
        record = LensView.model_validate(dict(view))
    except ValidationError as exc:
        raise ApplyValidationError(f"{candidate_id}: invalid lens_view {view!r}: {exc}") from exc
    if record.origin_ref is not None and record.origin_ref not in planned_refs:
        raise ApplyValidationError(
            f"{candidate_id}: lens_view origin_ref {record.origin_ref!r} is not one of the "
            "block's planned origin refs"
        )
    return record.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def derive_lens_views(data: dict, origins: list[dict], candidate_id: str = "?") -> list[dict]:
    """Return the lens_views for a candidate block.

    Explicit ``lens_views`` are validated against the planned origin refs. A
    legacy block (no ``lens_views``) with a top-level ``lens``+``rationale``
    synthesizes one view, linked to the ``explore-ideas-<lens>`` origin when the
    block planned it. Returns ``[]`` when neither is present.
    """
    planned_refs = {o["ref"] for o in origins if o.get("ref")}
    raw = data.get("lens_views")
    if raw is not None:
        if not isinstance(raw, list):
            raise ApplyValidationError(f"{candidate_id}: 'lens_views' must be a list")
        return [_normalize_lens_view(v, candidate_id, planned_refs) for v in raw]

    lens = data.get("lens")
    rationale = data.get("rationale")
    if isinstance(lens, str) and isinstance(rationale, str) and rationale.strip():
        view: dict = {"lens": lens, "rationale": rationale}
        origin_ref = f"explore-ideas-{lens}"
        if origin_ref in planned_refs:
            view["origin_ref"] = origin_ref
        return [_normalize_lens_view(view, candidate_id, planned_refs)]
    return []


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

    planned_refs = [o["ref"] for o in origins if o.get("ref")]
    if len(planned_refs) != len(set(planned_refs)):
        raise ApplyValidationError(
            f"{candidate_id}: duplicate non-null origin_plan.origins[].ref"
        )

    lens_views = derive_lens_views(data, origins, candidate_id)

    seen_lenses: set[str] = set()
    for view in lens_views:
        if view["lens"] in seen_lenses:
            raise ApplyValidationError(
                f"{candidate_id}: duplicate lens_views[].lens {view['lens']!r} "
                "(at most one view per lens)"
            )
        seen_lenses.add(view["lens"])

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
        lens_views=lens_views,
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


def write_back(text: str, candidate_id: str, entity_id: str, applied_at: str) -> str:
    lines = text.splitlines(keepends=True)
    fence_line = re.compile(r"^(?P<indent>\s*)```yaml$")
    candidate_line = re.compile(rf"^(?P<indent>\s*)candidate_id:\s*{re.escape(candidate_id)}\s*$")

    def _newline(line: str) -> str:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
        return ""

    i = 0
    n = len(lines)
    while i < n:
        fence_match = fence_line.match(lines[i].rstrip("\r\n"))
        if fence_match:
            fence_indent = fence_match.group("indent")
            start = i + 1
            j = start
            closing_fence = re.compile(rf"^{re.escape(fence_indent)}```$")
            while j < n and not closing_fence.match(lines[j].rstrip("\r\n")):
                j += 1

            for k in range(start, j):
                candidate_match = candidate_line.match(lines[k].rstrip("\r\n"))
                if candidate_match:
                    indent = candidate_match.group("indent")
                    decision_line = re.compile(
                        rf"^{re.escape(indent)}decision:(?P<separator>\s*)(?P<value>keep|drop|defer|applied)(?P<trailing>.*)$"
                    )
                    applied_as_line = re.compile(rf"^{re.escape(indent)}applied_as:(?P<separator>\s*).*")
                    applied_at_line = re.compile(rf"^{re.escape(indent)}applied_at:(?P<separator>\s*).*")

                    for m in range(start, j):
                        decision_match = decision_line.match(lines[m].rstrip("\r\n"))
                        if decision_match:
                            separator = decision_match.group("separator")
                            trailing = decision_match.group("trailing")
                            newline = _newline(lines[m])
                            lines[m] = f"{indent}decision:{separator}applied{trailing}{newline}"

                            applied_as_index = m + 1
                            applied_at_index = m + 2
                            if (
                                applied_at_index < j
                                and applied_as_line.match(lines[applied_as_index].rstrip("\r\n"))
                                and applied_at_line.match(lines[applied_at_index].rstrip("\r\n"))
                            ):
                                lines[applied_as_index] = f"{indent}applied_as: {entity_id}{newline}"
                                lines[applied_at_index] = f"{indent}applied_at: {applied_at}{newline}"
                            else:
                                lines[m + 1 : m + 1] = [
                                    f"{indent}applied_as: {entity_id}{newline}",
                                    f"{indent}applied_at: {applied_at}{newline}",
                                ]
                            return "".join(lines)
                    raise ApplyWriteBackError(
                        f"{candidate_id}: block has no 'decision:' line to mark applied"
                    )
            i = j + 1
            continue
        i += 1

    raise ApplyWriteBackError(f"{candidate_id}: block not found in report for write-back")


def apply_report(project_root: Path, from_value: str, model_id: str, today: date) -> ApplyResult:
    report_path = resolve_report_path(project_root, from_value)
    text = report_path.read_text(encoding="utf-8")
    blocks = parse_report(text)
    plan = plan_report(blocks, model_id)

    created: list[CreatedEntity] = []
    failures: list[tuple[str, str]] = []

    for create_plan in plan.to_create:
        try:
            result = create_entity(
                project_root,
                kind=create_plan.kind,
                title=create_plan.title,
                source_refs=create_plan.source_refs,
                today=today,
                extra_frontmatter={
                    "origins": create_plan.origins,
                    "added_by": create_plan.added_by,
                    **({"lens_views": create_plan.lens_views} if create_plan.lens_views else {}),
                },
            )
        except EntityCommandError as exc:
            failures.append((create_plan.candidate_id, str(exc)))
            continue

        try:
            text = write_back(text, create_plan.candidate_id, result.entity_id, today.isoformat())
            report_path.write_text(text, encoding="utf-8")
        except (ApplyWriteBackError, OSError) as exc:
            raise ApplyWriteBackError(
                f"created entity {result.entity_id} at {result.path}, but failed to record it in "
                f"{report_path}: {exc}. Mark that candidate's block 'decision: applied' with "
                f"'applied_as: {result.entity_id}' before retrying, or a retry may create a duplicate."
            ) from exc

        created.append(
            CreatedEntity(
                candidate_id=create_plan.candidate_id,
                entity_id=result.entity_id,
                kind=create_plan.kind,
                path=result.path,
                warnings=list(result.warnings),
            )
        )

    return ApplyResult(
        report=report_path,
        created=created,
        skipped_applied=plan.skipped_applied,
        skipped_other=plan.skipped_other,
        manual=plan.manual,
        failures=failures,
    )

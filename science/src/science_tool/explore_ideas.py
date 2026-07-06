from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from science_model.entities import LensView, OriginRecord
from science_model.frontmatter import parse_frontmatter
from science_model.lenses import LENS_BY_SLUG
from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _parse_markdown_file_preserving_body,
    _render_markdown,
    create_entity,
)
from science_tool.entity_scan import iter_entity_markdown
from science_tool.resolve_refs import RefIndex, build_ref_index, load_index_rows

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
    related: list[str] = field(default_factory=list)


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
            "manual": [{"candidate_id": candidate_id, "proposed_kind": kind} for candidate_id, kind in self.manual],
            "failures": [{"candidate_id": candidate_id, "error": error} for candidate_id, error in self.failures],
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

    candidate = project_root / "doc" / "explorations" / f"{from_value}.md"
    if candidate.is_file():
        return candidate

    raise ApplyValidationError(
        f"report not found: {from_value!r} (looked for a file path and for doc/explorations/{from_value}.md)"
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
        return OriginRecord.model_validate(normalized).model_dump(mode="json", exclude_none=True, exclude_defaults=True)
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
            f"{candidate_id}: lens_view origin_ref {record.origin_ref!r} is not one of the block's planned origin refs"
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


def _resolve_related(raw: object, candidate_id: str, ref_index: RefIndex | None) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApplyValidationError(f"{candidate_id}: related_existing must be a list")
    if raw and ref_index is None:
        raise ApplyValidationError(f"{candidate_id}: cannot resolve related_existing without a project index")
    if ref_index is None:
        return []
    resolver = ref_index
    resolved: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            raise ApplyValidationError(
                f"{candidate_id}: related_existing entries must be non-empty strings (got {entry!r})"
            )
        res = resolver.resolve(entry)
        if res.resolved is None:
            if res.candidates:
                raise ApplyValidationError(
                    f"{candidate_id}: ambiguous related_existing {entry!r} (candidates: {', '.join(res.candidates)})"
                )
            raise ApplyValidationError(f"{candidate_id}: unresolved related_existing {entry!r} (no matching entity)")
        if res.resolved not in seen:
            seen.add(res.resolved)
            resolved.append(res.resolved)
    return resolved


def build_create_plan(candidate_id: str, data: dict, model_id: str, *, ref_index: RefIndex | None = None) -> CreatePlan:
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

    # Harden unconditionally: apply rejects duplicate non-null origin refs even absent lens_views (stricter than the model, which only checks this when lens_views are present) so a later lens_views addition can never collide.
    planned_refs = [o["ref"] for o in origins if o.get("ref")]
    if len(planned_refs) != len(set(planned_refs)):
        raise ApplyValidationError(f"{candidate_id}: duplicate non-null origin_plan.origins[].ref")

    related = _resolve_related(data.get("related_existing"), candidate_id, ref_index)

    lens_views = derive_lens_views(data, origins, candidate_id)

    seen_lenses: set[str] = set()
    for view in lens_views:
        if view["lens"] in seen_lenses:
            raise ApplyValidationError(
                f"{candidate_id}: duplicate lens_views[].lens {view['lens']!r} (at most one view per lens)"
            )
        seen_lenses.add(view["lens"])

    anchors = data.get("literature_anchors") or []
    source_refs: list[str] = []
    seen: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ApplyValidationError(f"{candidate_id}: literature_anchors entry must be a mapping")
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
        related=related,
    )


def plan_report(blocks: list[CandidateBlock], model_id: str, *, ref_index: RefIndex | None = None) -> ReportPlan:
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
            to_create.append(build_create_plan(block.candidate_id, block.data, model_id, ref_index=ref_index))
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
                    raise ApplyWriteBackError(f"{candidate_id}: block has no 'decision:' line to mark applied")
            i = j + 1
            continue
        i += 1

    raise ApplyWriteBackError(f"{candidate_id}: block not found in report for write-back")


def apply_report(project_root: Path, from_value: str, model_id: str, today: date) -> ApplyResult:
    report_path = resolve_report_path(project_root, from_value)
    text = report_path.read_text(encoding="utf-8")
    blocks = parse_report(text)
    ref_index = build_ref_index(load_index_rows(project_root))
    plan = plan_report(blocks, model_id, ref_index=ref_index)

    created: list[CreatedEntity] = []
    failures: list[tuple[str, str]] = []

    for create_plan in plan.to_create:
        try:
            result = create_entity(
                project_root,
                kind=create_plan.kind,
                title=create_plan.title,
                source_refs=create_plan.source_refs,
                related=create_plan.related,
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


def _file_id(path: Path) -> str | None:
    parsed = parse_frontmatter(path)
    if not parsed:
        return None
    fm, _ = parsed
    value = fm.get("id")
    return value if isinstance(value, str) else None


def backfill_lens_views(project_root: Path, from_value: str, today: date) -> list[tuple[str, int]]:
    """Backfill lens_views onto entities created by a prior applied report.

    For each applied block, add one lens_view per lens-encoding assistant origin
    on the created entity that has no matching view yet. Per-lens rationales are
    recovered via ``derive_lens_views`` (so explicit per-lens rationales from
    newer reports survive); any lens-origin the block didn't cover falls back to
    the canonical lens-frame description as an honest interim rationale. When an
    entity gains new views, its ``updated`` frontmatter advances to ``today``,
    matching the sibling in-place mutators in ``entities.py``. Returns
    ``(entity_id, views_added)`` for each touched entity.
    """
    report_path = resolve_report_path(project_root, from_value)
    blocks = parse_report(report_path.read_text(encoding="utf-8"))
    by_applied_as = {
        str(b.data.get("applied_as")): b.data
        for b in blocks
        if b.data.get("decision") == "applied" and b.data.get("applied_as")
    }

    entities_root = project_root / "entities"
    touched: list[tuple[str, int]] = []
    for entity_id, block in by_applied_as.items():
        target = next((p for p in iter_entity_markdown(entities_root) if _file_id(p) == entity_id), None)
        if target is None:
            continue
        # Body-preserving parse (not science_model's parse_frontmatter, which
        # strips the body) so the write-back below only touches lens_views —
        # no incidental whitespace churn to a hand-authored entity's prose.
        fm, body = _parse_markdown_file_preserving_body(target)

        # Recover per-lens rationales the report already carried (explicit
        # lens_views, or a synthesized single-lens view) via the same helper
        # apply uses; fall back to the canonical lens-frame description
        # otherwise.
        block_origins = (block.get("origin_plan") or {}).get("origins") or []
        try:
            block_views = derive_lens_views(block, list(block_origins), entity_id)
        except ApplyValidationError:
            block_views = []
        rationale_by_lens = {v["lens"]: v["rationale"] for v in block_views}

        existing = {v.get("lens") for v in (fm.get("lens_views") or []) if isinstance(v, dict)}
        added: list[dict] = []
        for origin in fm.get("origins") or []:
            ref = origin.get("ref") if isinstance(origin, dict) else None
            if not (isinstance(ref, str) and ref.startswith("explore-ideas-")):
                continue
            lens = ref.removeprefix("explore-ideas-")
            if lens not in LENS_BY_SLUG or lens in existing:
                continue
            rationale = rationale_by_lens.get(lens) or LENS_BY_SLUG[lens].description
            added.append({"lens": lens, "rationale": rationale, "origin_ref": ref})
            existing.add(lens)
        if not added:
            continue
        fm["lens_views"] = list(fm.get("lens_views") or [])
        fm["lens_views"].extend(added)
        fm["updated"] = today.isoformat()
        _atomic_replace_text(target, _render_markdown(fm, body))
        touched.append((entity_id, len(added)))
    return touched

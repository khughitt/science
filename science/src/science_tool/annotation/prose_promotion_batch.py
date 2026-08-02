from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from science_tool.annotation.promote import (
    ApplyReport,
    PromotionApplyError,
    PromotionCandidate,
    PromotionTarget,
    build_targets,
    entity_dest,
    load_corpora,
)
from science_tool.annotation.planned_edits import (
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update_from_text,
    publish_edit,
    publish_order,
)
from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    ProseDecompositionStore,
    artifact_unit_ref,
    canonical_json_text,
)
from science_tool.annotation.prose_promote import (
    ProsePromotionError,
    ProsePromotionPlanRow,
    plan_prose_unit_promotion,
)
from science_tool.dag.entity_frontmatter import EntityWriteError
from science_tool.entities import (
    EntityCommandError,
    find_entity,
    render_entity_source_refs,
    slug_for_claim_text,
)
from science_tool.entity_reservation import propose_number

_SCHEMA_VERSION = 1
_PLAN_KEYS = frozenset({"schema_version", "source_slug", "rows"})
_ROW_KEYS = frozenset(
    {
        "source_slug",
        "source_ref",
        "artifact_id",
        "unit_id",
        "fingerprint",
        "artifact_unit_ref",
        "decision",
        "target_ref",
    }
)


@dataclass(frozen=True)
class ProsePromotionPlan:
    source_slug: str
    rows: tuple[ProsePromotionPlanRow, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "source_slug": self.source_slug,
            "rows": [row.to_json() for row in self.rows],
        }


@dataclass(frozen=True)
class _ValidatedPromotionRow:
    row: ProsePromotionPlanRow
    candidate: PromotionCandidate
    recovered_link: bool = False


def plan_prose_promotions(project_root: Path, source_slug: str, unit_ids: Sequence[str]) -> ProsePromotionPlan:
    if not unit_ids:
        raise ProsePromotionError("promotion plan requires at least one unit")
    _reject_duplicate_unit_ids(unit_ids)
    rows: list[ProsePromotionPlanRow] = []
    for unit_id in unit_ids:
        row = plan_prose_unit_promotion(project_root, source_slug, unit_id)
        if row is None:
            raise ProsePromotionError(f"unit {unit_id!r} does not have a mint/link promotion decision")
        rows.append(row)
    targets = build_targets()
    _reject_duplicate_mint_targets([_validate_current_row(project_root.resolve(), row) for row in rows], targets)
    return ProsePromotionPlan(source_slug=source_slug, rows=tuple(rows))


def apply_prose_promotion_plan(project_root: Path, plan: ProsePromotionPlan) -> ApplyReport:
    """Plan every row, aggregate refusals, then publish.

    Recovered units can inherit promote_prose_unit's empty ApplyReport because the
    entity already has the artifact unit ref and apply only records index recovery.
    """
    project_root = project_root.resolve()
    targets = build_targets()
    store = ProseDecompositionStore(project_root)
    rows = _plan_rows(plan)
    for source_slug in {row.source_slug for row in rows}:
        store.load_latest(source_slug)

    report = ApplyReport()
    refusals: list[str] = []
    current_rows: list[_ValidatedPromotionRow] = []
    for row in rows:
        try:
            current_rows.append(_validate_current_row(project_root, row))
        except ProsePromotionError as exc:
            refusals.append(f"{row.unit_id}: {exc}")
    try:
        _reject_duplicate_mint_targets(current_rows, targets)
    except ProsePromotionError as exc:
        refusals.append(f"promotion plan: {exc}")

    planned_text_by_path: dict[Path, str] = {}
    original_text_by_path: dict[Path, str] = {}
    creates: dict[Path, tuple[str, str, int] | None] = {}
    index_state_by_slug: dict[str, dict] = {}
    index_text_by_slug: dict[str, str] = {}
    next_number: dict[str, int] = {}

    for source_slug in {current.row.source_slug for current in current_rows}:
        index_path = store.index_path(source_slug)
        index_text_by_slug[source_slug] = current_text(index_path)
        index_state_by_slug[source_slug] = store.parse_index(
            source_slug, index_text_by_slug[source_slug]
        )

    def composed(path: Path) -> str | None:
        if path in planned_text_by_path:
            return planned_text_by_path[path]
        if not path.exists():
            return None
        original_text_by_path[path] = current_text(path)
        planned_text_by_path[path] = original_text_by_path[path]
        return planned_text_by_path[path]

    for current in current_rows:
        try:
            promoted_to = _plan_row_edit(
                project_root,
                current,
                targets,
                composed,
                planned_text_by_path,
                creates,
                next_number,
                report,
            )
            row = current.row
            if promoted_to is not None:
                index_state_by_slug[row.source_slug] = store.plan_promotion(
                    row.source_slug,
                    row.fingerprint,
                    promoted_to,
                    state=index_state_by_slug[row.source_slug],
                )
        except (
            DecompositionError,
            EntityCommandError,
            PromotionApplyError,
            ProsePromotionError,
        ) as exc:
            refusals.append(f"{current.row.unit_id}: {exc}")

    if refusals:
        joined = "\n  ".join(refusals)
        raise ProsePromotionError(
            f"{len(refusals)} row(s) were refused and nothing was written:\n  {joined}"
        )

    edits = edits_for_planned_texts(
        planned_text_by_path,
        original_text_by_path,
        creates,
        reason_create="prose_promotion_mint",
        reason_update="prose_promotion_accrual",
    )
    for slug, state in index_state_by_slug.items():
        index_path = store.index_path(slug)
        edits[index_path] = plan_update_from_text(
            index_path,
            index_text_by_slug[slug],
            canonical_json_text(state),
            "prose_decomposition_index",
        )

    written: list[str] = []
    for edit in publish_order(edits.values()):
        if not edit.changed:
            continue
        try:
            publish_edit(edit, project_root=project_root)
        except (OSError, EntityCommandError, EntityWriteError) as exc:
            raise ProsePromotionError(
                f"[stage=write, files_written={len(written)}, written_paths={tuple(written)}] "
                f"failed to write {path_string(edit.path)}: {exc}"
            ) from exc
        written.append(path_string(edit.path))
        if edit.operation == "create":
            report.written_paths.append(str(edit.path))

    return report


def _plan_row_edit(
    project_root: Path,
    current: _ValidatedPromotionRow,
    targets: dict[str, PromotionTarget],
    composed: Callable[[Path], str | None],
    planned_text_by_path: dict[Path, str],
    creates: dict[Path, tuple[str, str, int] | None],
    next_number: dict[str, int],
    report: ApplyReport,
) -> str | None:
    """Plan one row's entity edit and return its promoted target ref."""
    row = current.row
    candidate = current.candidate
    if current.recovered_link:
        if candidate.slug is None:
            raise ProsePromotionError(
                f"recovered link for unit {row.unit_id!r} is missing target ref"
            )
        return candidate.slug

    if candidate.decision == "MINT":
        target = targets[candidate.kind]
        assigned: int | None = None
        dest: Path | None = None
        if target.slug_addressed:
            dest = entity_dest(f"{candidate.kind}:{candidate.slug}", project_root)
        else:
            if candidate.kind not in next_number:
                next_number[candidate.kind] = propose_number(project_root, candidate.kind)
            assigned = next_number[candidate.kind]
            next_number[candidate.kind] += 1
        planned = target.plan_mint(
            candidate,
            [row.source_ref, row.artifact_unit_ref],
            project_root,
            None,
            assigned,
            composed(dest) if dest is not None else None,
        )
        planned_text_by_path[planned.path] = planned.post_image
        if planned.operation == "create":
            kind, local_part = planned.entity_id.split(":", 1)
            creates[planned.path] = (
                (kind, local_part, planned.claim_number)
                if planned.claim_number is not None
                else None
            )
            report.minted += 1
        else:
            report.linked += 1
        return planned.entity_id

    if candidate.decision == "LINK":
        if candidate.slug is None:
            raise ProsePromotionError(
                f"LINK decision for unit {row.unit_id!r} is missing target ref"
            )
        dest = find_entity(project_root, candidate.slug).path
        before = composed(dest)
        if before is None:
            raise ProsePromotionError(f"LINK target {candidate.slug} does not exist at {dest}")
        post_image, _changed = render_entity_source_refs(
            before, [row.source_ref, row.artifact_unit_ref], entity_path=dest
        )
        planned_text_by_path[dest] = post_image
        report.linked += 1
        return candidate.slug

    report.skipped[candidate.reason] += 1
    return None


def plan_to_json_text(plan: ProsePromotionPlan) -> str:
    return json.dumps(plan.to_json(), indent=2) + "\n"


def plan_from_json_text(raw: str) -> ProsePromotionPlan:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProsePromotionError(f"promotion plan is not valid JSON: {exc}") from exc
    return plan_from_json(payload)


def plan_from_json(payload: object) -> ProsePromotionPlan:
    if not isinstance(payload, dict):
        raise ProsePromotionError("promotion plan must be a JSON object")
    _reject_unknown_keys(payload, _PLAN_KEYS, "promotion plan")
    if payload.get("schema_version") != _SCHEMA_VERSION:
        raise ProsePromotionError(f"promotion plan schema_version must be {_SCHEMA_VERSION}")
    source_slug = _required_string(payload, "source_slug")
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise ProsePromotionError("promotion plan rows must be an array")
    rows = tuple(_row_from_json(item, source_slug=source_slug, index=index) for index, item in enumerate(raw_rows))
    _plan_rows(ProsePromotionPlan(source_slug=source_slug, rows=rows))
    return ProsePromotionPlan(source_slug=source_slug, rows=rows)


def _validate_current_row(project_root: Path, row: ProsePromotionPlanRow) -> _ValidatedPromotionRow:
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(row.source_slug)
    except DecompositionError as exc:
        raise ProsePromotionError(str(exc)) from exc
    if row.source_ref != artifact.source_ref:
        raise ProsePromotionError(
            f"source_ref mismatch for unit {row.unit_id!r}: "
            f"planned {row.source_ref!r}, latest {artifact.source_ref!r}"
        )
    if artifact.artifact.artifact_id != row.artifact_id:
        raise ProsePromotionError(
            f"stale artifact for unit {row.unit_id!r}: "
            f"planned {row.artifact_id!r}, latest {artifact.artifact.artifact_id!r}"
        )
    unit = next((candidate_unit for candidate_unit in artifact.units if candidate_unit.unit_id == row.unit_id), None)
    if unit is None:
        raise ProsePromotionError(f"unit {row.unit_id!r} is not in latest artifact for {row.source_ref}; stale or missing")
    expected_ref = artifact_unit_ref(artifact, unit)
    if row.artifact_unit_ref != expected_ref:
        raise ProsePromotionError(
            f"artifact_unit_ref mismatch for unit {row.unit_id!r}: "
            f"planned {row.artifact_unit_ref!r}, latest {expected_ref!r}"
        )
    if unit.disposition != "candidate":
        raise ProsePromotionError(f"unit {row.unit_id!r} is non-candidate: {unit.disposition}")
    if unit.candidate is None:
        raise ProsePromotionError(f"candidate unit {row.unit_id!r} is missing candidate payload")
    if unit.fingerprint != row.fingerprint:
        raise ProsePromotionError(
            f"fingerprint mismatch for unit {row.unit_id!r}: "
            f"planned {row.fingerprint!r}, latest {unit.fingerprint!r}"
        )
    current = plan_prose_unit_promotion(project_root, row.source_slug, row.unit_id)
    if current is None:
        raise ProsePromotionError(f"unit {row.unit_id!r} no longer has a mint/link promotion decision")
    if (current.decision, current.target_ref) != (row.decision, row.target_ref):
        raise ProsePromotionError(
            f"decision drift for unit {row.unit_id!r}: "
            f"planned {(row.decision, row.target_ref)!r}, current {(current.decision, current.target_ref)!r}"
        )
    _, derived_refs = load_corpora(project_root)
    recovered_link = current.decision == "link" and current.artifact_unit_ref in derived_refs
    return _ValidatedPromotionRow(
        row=current,
        candidate=_promotion_candidate(current, unit.candidate),
        recovered_link=recovered_link,
    )


def _promotion_candidate(row: ProsePromotionPlanRow, candidate) -> PromotionCandidate:
    if row.decision == "mint":
        try:
            slug = slug_for_claim_text(candidate.exact)
        except EntityCommandError as exc:
            raise ProsePromotionError(str(exc)) from exc
        return PromotionCandidate(
            ref=row.artifact_unit_ref,
            frag=row.unit_id,
            claim=candidate.exact,
            subject=candidate.subject,
            object=candidate.object,
            decision="MINT",
            slug=slug,
            reason="planned prose promotion",
            kind=candidate.type,
        )
    if row.target_ref is None:
        raise ProsePromotionError(f"link decision for unit {row.unit_id!r} is missing target_ref")
    return PromotionCandidate(
        ref=row.artifact_unit_ref,
        frag=row.unit_id,
        claim=candidate.exact,
        subject=candidate.subject,
        object=candidate.object,
        decision="LINK",
        slug=row.target_ref,
        reason="planned prose promotion",
        kind=candidate.type,
    )


def _row_from_json(payload: object, *, source_slug: str, index: int) -> ProsePromotionPlanRow:
    if not isinstance(payload, dict):
        raise ProsePromotionError(f"promotion plan row[{index}] must be an object")
    _reject_unknown_keys(payload, _ROW_KEYS, f"promotion plan row[{index}]")
    row_source_slug = _required_string(payload, "source_slug")
    if row_source_slug != source_slug:
        raise ProsePromotionError(
            f"promotion plan row[{index}] source_slug {row_source_slug!r} does not match plan {source_slug!r}"
        )
    source_ref = _required_string(payload, "source_ref")
    expected_source_ref = f"prose-source:{source_slug}"
    if source_ref != expected_source_ref:
        raise ProsePromotionError(
            f"promotion plan row[{index}] source_ref {source_ref!r} does not match {expected_source_ref!r}"
        )
    decision = _required_decision(payload, "decision")
    target_ref = payload.get("target_ref")
    if target_ref is not None and not isinstance(target_ref, str):
        raise ProsePromotionError(f"promotion plan row[{index}] target_ref must be a string or null")
    if decision == "link" and not target_ref:
        raise ProsePromotionError(f"promotion plan row[{index}] link decision requires target_ref")
    if decision == "mint" and target_ref is not None:
        raise ProsePromotionError(f"promotion plan row[{index}] mint decision must not carry target_ref")
    return ProsePromotionPlanRow(
        source_slug=row_source_slug,
        source_ref=source_ref,
        artifact_id=_required_string(payload, "artifact_id"),
        unit_id=_required_string(payload, "unit_id"),
        fingerprint=_required_string(payload, "fingerprint"),
        artifact_unit_ref=_required_string(payload, "artifact_unit_ref"),
        decision=decision,
        target_ref=target_ref,
    )


def _required_decision(payload: dict[str, object], key: str) -> Literal["mint", "link"]:
    value = _required_string(payload, key)
    if value not in {"mint", "link"}:
        raise ProsePromotionError(f"{key} must be mint or link")
    return cast(Literal["mint", "link"], value)


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProsePromotionError(f"{key} must be a non-empty string")
    return value


def _reject_unknown_keys(payload: dict[str, object], allowed: frozenset[str], label: str) -> None:
    extra = set(payload) - allowed
    if extra:
        raise ProsePromotionError(f"unknown {label} keys: {sorted(extra)}")


def _plan_rows(plan: ProsePromotionPlan) -> tuple[ProsePromotionPlanRow, ...]:
    if not plan.rows:
        raise ProsePromotionError("promotion plan requires at least one row")
    _reject_duplicate_unit_ids([row.unit_id for row in plan.rows])
    _reject_duplicate_fingerprints([row.fingerprint for row in plan.rows])
    return plan.rows


def _reject_duplicate_unit_ids(unit_ids: Sequence[str]) -> None:
    seen: set[str] = set()
    for unit_id in unit_ids:
        if unit_id in seen:
            raise ProsePromotionError(f"duplicate promotion plan unit_id: {unit_id}")
        seen.add(unit_id)


def _reject_duplicate_fingerprints(fingerprints: Sequence[str]) -> None:
    seen: set[str] = set()
    for fingerprint in fingerprints:
        if fingerprint in seen:
            raise ProsePromotionError(f"duplicate promotion plan fingerprint: {fingerprint}")
        seen.add(fingerprint)


def _reject_duplicate_mint_targets(
    rows: Sequence[_ValidatedPromotionRow],
    targets: dict[str, PromotionTarget],
) -> None:
    seen: set[tuple[str, str]] = set()
    for validated in rows:
        candidate = validated.candidate
        if candidate.decision != "MINT" or candidate.slug is None:
            continue
        target = targets.get(candidate.kind)
        if target is None or not target.slug_addressed:
            continue
        key = (candidate.kind, candidate.slug)
        if key in seen:
            raise ProsePromotionError(f"duplicate mint target in promotion plan: {candidate.kind}:{candidate.slug}")
        seen.add(key)

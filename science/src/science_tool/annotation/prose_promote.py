from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.internal_prose_adapter import InternalProseAdapter, LocatorStatus
from science_tool.annotation.promote import (
    ApplyReport,
    Promotable,
    PromotionApplyError,
    PromotionCandidate,
    build_targets,
    decide_all,
    entity_dest,
    load_corpora,
)
from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update_from_text,
    publish_edit,
    publish_order,
)
from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    DecompositionArtifact,
    ProseDecompositionStore,
    Quote,
    artifact_unit_ref,
    canonical_json_text,
)
from science_tool.dag.entity_frontmatter import EntityWriteError
from science_tool.entities import EntityCommandError, find_entity, render_entity_source_refs
from science_tool.entity_reservation import propose_number


class ProsePromotionError(ValueError):
    """Raised when a prose unit cannot be promoted."""


@dataclass(frozen=True)
class ProsePromotionPlanRow:
    source_slug: str
    source_ref: str
    artifact_id: str
    unit_id: str
    fingerprint: str
    artifact_unit_ref: str
    decision: Literal["mint", "link"]
    target_ref: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "source_slug": self.source_slug,
            "source_ref": self.source_ref,
            "artifact_id": self.artifact_id,
            "unit_id": self.unit_id,
            "fingerprint": self.fingerprint,
            "artifact_unit_ref": self.artifact_unit_ref,
            "decision": self.decision,
            "target_ref": self.target_ref,
        }


def plan_prose_unit_promotion(project_root: Path, source_slug: str, unit_id: str) -> ProsePromotionPlanRow | None:
    project_root = project_root.resolve()
    store = ProseDecompositionStore(project_root)

    try:
        artifact = store.load_latest(source_slug)
        index = store.load_index(source_slug)
    except DecompositionError as exc:
        raise ProsePromotionError(str(exc)) from exc

    return _plan_prose_unit_promotion_from_snapshot(
        project_root,
        source_slug,
        unit_id,
        artifact,
        index,
    )


def _plan_prose_unit_promotion_from_snapshot(
    project_root: Path,
    source_slug: str,
    unit_id: str,
    artifact: DecompositionArtifact,
    index: dict[str, Any],
) -> ProsePromotionPlanRow | None:

    source_ref = artifact.source_ref
    if artifact.source.slug != source_slug:
        raise ProsePromotionError(
            f"latest artifact source slug {artifact.source.slug!r} does not match requested {source_slug!r}"
        )

    unit = next((candidate_unit for candidate_unit in artifact.units if candidate_unit.unit_id == unit_id), None)
    if unit is None:
        raise ProsePromotionError(f"unit {unit_id!r} is not in latest artifact for {source_ref}; stale or missing")
    if unit.disposition != "candidate":
        raise ProsePromotionError(f"unit {unit_id!r} is non-candidate: {unit.disposition}")
    if unit.candidate is None:
        raise ProsePromotionError(f"candidate unit {unit_id!r} is missing candidate payload")

    ref = artifact_unit_ref(artifact, unit)
    row = _index_row(index, unit.fingerprint)
    if row.get("stale") is True:
        raise ProsePromotionError(f"unit {unit_id!r} is stale in the decomposition index")
    existing_promotion = row.get("promoted_to")
    if existing_promotion:
        raise ProsePromotionError(
            f"unit {unit_id!r} is already promoted to {existing_promotion}"
        )

    corpora, derived_refs = load_corpora(project_root)
    if ref in derived_refs:
        recovered_to = _entity_ref_with_source_ref(project_root, ref, kind=unit.candidate.type)
        if recovered_to is None:
            raise ProsePromotionError(f"artifact unit ref {ref!r} is present in derived refs but no entity was found")
        return _plan_row(
            artifact=artifact,
            unit_id=unit.unit_id,
            fingerprint=unit.fingerprint,
            artifact_unit_ref=ref,
            decision="link",
            target_ref=recovered_to,
        )

    # Intentionally mirrors promote_prose_unit's read/decision path so read-only
    # planning and apply stay behaviorally aligned.
    quote = Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    try:
        resolution = InternalProseAdapter().resolve_unit(artifact.source.path, unit.locator, quote)
    except OSError as exc:
        raise ProsePromotionError(f"source/locator resolution failed for unit {unit_id!r}: {exc}") from exc
    if resolution.status is not LocatorStatus.RESOLVED:
        detail = f": {resolution.message}" if resolution.message else ""
        raise ProsePromotionError(f"locator for unit {unit_id!r} is {resolution.status.value}{detail}")

    targets = build_targets()
    if unit.candidate.type not in targets:
        raise ProsePromotionError(f"unit {unit_id!r} type {unit.candidate.type!r} is not a promotable target")

    promotable = Promotable(
        ref=ref,
        frag=unit.unit_id,
        claim=unit.candidate.exact,
        subject=unit.candidate.subject,
        object=unit.candidate.object,
        kind=unit.candidate.type,
    )
    decision = decide_all([promotable], corpora, targets)[0]
    if decision.decision == "MINT":
        return _plan_row(
            artifact=artifact,
            unit_id=unit.unit_id,
            fingerprint=unit.fingerprint,
            artifact_unit_ref=ref,
            decision="mint",
            target_ref=None,
        )
    if decision.decision == "LINK":
        if decision.slug is None:
            raise ProsePromotionError(f"LINK decision for unit {unit_id!r} is missing target ref")
        return _plan_row(
            artifact=artifact,
            unit_id=unit.unit_id,
            fingerprint=unit.fingerprint,
            artifact_unit_ref=ref,
            decision="link",
            target_ref=decision.slug,
        )
    return None


def promote_prose_unit(project_root: Path, source_ref: str, unit_id: str, apply: bool) -> ApplyReport:
    project_root = project_root.resolve()
    source_slug = _source_slug(source_ref)
    store = ProseDecompositionStore(project_root)

    try:
        artifact = store.load_latest(source_slug)
        index_path = store.index_path(source_slug)
        index_before = current_text(index_path)
        index = store.parse_index(source_slug, index_before)
    except DecompositionError as exc:
        raise ProsePromotionError(str(exc)) from exc

    if artifact.source_ref != source_ref:
        raise ProsePromotionError(
            f"latest artifact source_ref {artifact.source_ref!r} does not match requested {source_ref!r}"
        )

    unit = next((candidate_unit for candidate_unit in artifact.units if candidate_unit.unit_id == unit_id), None)
    if unit is None:
        raise ProsePromotionError(f"unit {unit_id!r} is not in latest artifact for {source_ref}; stale or missing")
    if unit.disposition != "candidate":
        raise ProsePromotionError(f"unit {unit_id!r} is non-candidate: {unit.disposition}")
    if unit.candidate is None:
        raise ProsePromotionError(f"candidate unit {unit_id!r} is missing candidate payload")

    ref = artifact_unit_ref(artifact, unit)
    row = _index_row(index, unit.fingerprint)
    if row.get("stale") is True:
        raise ProsePromotionError(f"unit {unit_id!r} is stale in the decomposition index")
    existing_promotion = row.get("promoted_to")
    if existing_promotion:
        raise ProsePromotionError(
            f"unit {unit_id!r} is already promoted to {existing_promotion}"
        )

    corpora, derived_refs = load_corpora(project_root)
    if apply and ref in derived_refs:
        recovered_to = _entity_ref_with_source_ref(project_root, ref, kind=unit.candidate.type)
        if recovered_to is None:
            raise ProsePromotionError(f"artifact unit ref {ref!r} is present in derived refs but no entity was found")
        try:
            state = store.plan_promotion(
                source_slug=source_slug,
                fingerprint=unit.fingerprint,
                promoted_to=recovered_to,
                state=index,
            )
            recovery_report = ApplyReport()
            _publish(
                project_root,
                [
                    plan_update_from_text(
                        index_path,
                        index_before,
                        canonical_json_text(state),
                        "prose_decomposition_index",
                    )
                ],
                recovery_report,
            )
        except DecompositionError as exc:
            raise ProsePromotionError(str(exc)) from exc
        return recovery_report

    quote = Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    try:
        resolution = InternalProseAdapter().resolve_unit(artifact.source.path, unit.locator, quote)
    except OSError as exc:
        raise ProsePromotionError(f"source/locator resolution failed for unit {unit_id!r}: {exc}") from exc
    if resolution.status is not LocatorStatus.RESOLVED:
        detail = f": {resolution.message}" if resolution.message else ""
        raise ProsePromotionError(f"locator for unit {unit_id!r} is {resolution.status.value}{detail}")

    targets = build_targets()
    if unit.candidate.type not in targets:
        raise ProsePromotionError(f"unit {unit_id!r} type {unit.candidate.type!r} is not a promotable target")

    promotable = Promotable(
        ref=ref,
        frag=unit.unit_id,
        claim=unit.candidate.exact,
        subject=unit.candidate.subject,
        object=unit.candidate.object,
        kind=unit.candidate.type,
    )
    decision = decide_all([promotable], corpora, targets)[0]

    if not apply:
        return _read_only_report(decision)

    report = ApplyReport()
    planned_text_by_path: dict[Path, str] = {}
    original_text_by_path: dict[Path, str] = {}
    creates: dict[Path, tuple[str, str, int] | None] = {}
    promoted_to: str | None = None
    try:
        if decision.decision == "MINT":
            target = targets[decision.kind]
            assigned = None if target.slug_addressed else propose_number(project_root, decision.kind)
            dest = (
                entity_dest(f"{decision.kind}:{decision.slug}", project_root)
                if target.slug_addressed
                else None
            )
            existing = current_text(dest) if dest is not None and dest.exists() else None
            if dest is not None and existing is not None:
                original_text_by_path[dest] = existing
            planned = target.plan_mint(
                decision,
                [source_ref, decision.ref],
                project_root,
                None,
                assigned,
                existing,
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
            promoted_to = planned.entity_id
        elif decision.decision == "LINK":
            if decision.slug is None:
                raise ProsePromotionError(f"LINK decision for unit {unit_id!r} is missing target ref")
            dest = find_entity(project_root, decision.slug).path
            before = current_text(dest)
            original_text_by_path[dest] = before
            post_image, _changed = render_entity_source_refs(
                before, [source_ref, decision.ref], entity_path=dest
            )
            planned_text_by_path[dest] = post_image
            report.linked += 1
            promoted_to = decision.slug
        else:
            report.skipped[decision.reason] += 1

        edits = edits_for_planned_texts(
            planned_text_by_path,
            original_text_by_path,
            creates,
            reason_create="prose_promotion_mint",
            reason_update="prose_promotion_accrual",
        )
        if promoted_to is not None:
            state = store.plan_promotion(
                source_slug=source_slug,
                fingerprint=unit.fingerprint,
                promoted_to=promoted_to,
                state=index,
            )
            edits[index_path] = plan_update_from_text(
                index_path,
                index_before,
                canonical_json_text(state),
                "prose_decomposition_index",
            )
    except (DecompositionError, EntityCommandError, PromotionApplyError) as exc:
        raise ProsePromotionError(str(exc)) from exc

    _publish(project_root, publish_order(edits.values()), report)
    return report


def _publish(
    project_root: Path, edits: Sequence[PlannedFileEdit], report: ApplyReport
) -> None:
    written: list[str] = []
    for edit in edits:
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


def _source_slug(source_ref: str) -> str:
    prefix = "prose-source:"
    if not source_ref.startswith(prefix):
        raise ProsePromotionError("source_ref must use prose-source:<slug>")
    slug = source_ref.removeprefix(prefix)
    if not slug:
        raise ProsePromotionError("source slug must not be empty")
    return slug


def _index_row(index: dict[str, object], fingerprint: str) -> dict[str, object]:
    units = index.get("units")
    if not isinstance(units, dict):
        raise ProsePromotionError("prose decomposition index units must be an object")
    row = units.get(fingerprint)
    if row is None:
        raise ProsePromotionError("decomposition unit fingerprint is stale or missing from the index")
    if not isinstance(row, dict):
        raise ProsePromotionError(f"prose decomposition index row must be an object: {fingerprint}")
    return row


def _entity_ref_with_source_ref(project_root: Path, ref: str, *, kind: str) -> str | None:
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root)
    for entity in sources.entities:
        if entity.kind == kind and ref in entity.source_refs:
            return entity.canonical_id
    return None


def _plan_row(
    *,
    artifact,
    unit_id: str,
    fingerprint: str,
    artifact_unit_ref: str,
    decision: Literal["mint", "link"],
    target_ref: str | None,
) -> ProsePromotionPlanRow:
    return ProsePromotionPlanRow(
        source_slug=artifact.source.slug,
        source_ref=artifact.source_ref,
        artifact_id=artifact.artifact.artifact_id,
        unit_id=unit_id,
        fingerprint=fingerprint,
        artifact_unit_ref=artifact_unit_ref,
        decision=decision,
        target_ref=target_ref,
    )


def _read_only_report(decision: PromotionCandidate) -> ApplyReport:
    report = ApplyReport()
    if decision.decision == "MINT":
        report.minted = 1
    elif decision.decision == "LINK":
        report.linked = 1
    else:
        report.skipped[decision.reason] += 1
    return report

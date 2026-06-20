from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.annotation.internal_prose_adapter import InternalProseAdapter, LocatorStatus
from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    ProseDecompositionStore,
    Quote,
    artifact_unit_ref,
)
from science_tool.annotation.promote import (
    ApplyReport,
    PromotionApplyError,
    PromotionCandidate,
    Promotable,
    build_targets,
    decide_all,
    entity_dest,
    load_corpora,
)
from science_tool.entities import EntityCommandError, append_entity_source_ref, find_entity


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
    promoted_to = row.get("promoted_to")
    if promoted_to:
        raise ProsePromotionError(f"unit {unit_id!r} is already promoted to {promoted_to}")

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
        index = store.load_index(source_slug)
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
    promoted_to = row.get("promoted_to")
    if promoted_to:
        raise ProsePromotionError(f"unit {unit_id!r} is already promoted to {promoted_to}")

    corpora, derived_refs = load_corpora(project_root)
    if apply and ref in derived_refs:
        recovered_to = _entity_ref_with_source_ref(project_root, ref, kind=unit.candidate.type)
        if recovered_to is None:
            raise ProsePromotionError(f"artifact unit ref {ref!r} is present in derived refs but no entity was found")
        try:
            store.record_promotion(
                source_slug=source_slug,
                fingerprint=unit.fingerprint,
                promoted_to=recovered_to,
            )
        except DecompositionError as exc:
            raise ProsePromotionError(str(exc)) from exc
        return ApplyReport()

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
    promoted_to = None
    try:
        if decision.decision == "MINT":
            promoted_to = targets[decision.kind].mint(decision, [source_ref, decision.ref], project_root, None)
            report.written_paths.append(str(entity_dest(promoted_to, project_root)))
            report.minted += 1
        elif decision.decision == "LINK":
            if decision.slug is None:
                raise ProsePromotionError(f"LINK decision for unit {unit_id!r} is missing target ref")
            dest = find_entity(project_root, decision.slug).path
            append_entity_source_ref(dest, source_ref)
            append_entity_source_ref(dest, decision.ref)
            report.linked += 1
            promoted_to = decision.slug
        else:
            report.skipped[decision.reason] += 1
    except (DecompositionError, EntityCommandError, PromotionApplyError) as exc:
        raise ProsePromotionError(str(exc)) from exc

    if promoted_to is not None:
        try:
            store.record_promotion(
                source_slug=source_slug,
                fingerprint=unit.fingerprint,
                promoted_to=promoted_to,
            )
        except DecompositionError as exc:
            raise ProsePromotionError(str(exc)) from exc
    return report


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

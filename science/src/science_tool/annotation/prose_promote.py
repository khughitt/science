from __future__ import annotations

from pathlib import Path

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

    row = _index_row(index, unit.fingerprint)
    if row.get("stale") is True:
        raise ProsePromotionError(f"unit {unit_id!r} is stale in the decomposition index")
    promoted_to = row.get("promoted_to")
    if promoted_to:
        raise ProsePromotionError(f"unit {unit_id!r} is already promoted to {promoted_to}")

    quote = Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    resolution = InternalProseAdapter().resolve_unit(artifact.source.path, unit.locator, quote)
    if resolution.status is not LocatorStatus.RESOLVED:
        detail = f": {resolution.message}" if resolution.message else ""
        raise ProsePromotionError(f"locator for unit {unit_id!r} is {resolution.status.value}{detail}")

    targets = build_targets()
    if unit.candidate.type not in targets:
        raise ProsePromotionError(f"unit {unit_id!r} type {unit.candidate.type!r} is not a promotable target")

    ref = artifact_unit_ref(artifact, unit)
    promotable = Promotable(
        ref=ref,
        frag=unit.unit_id,
        claim=unit.candidate.exact,
        subject=unit.candidate.subject,
        object=unit.candidate.object,
        kind=unit.candidate.type,
    )
    corpora, _derived = load_corpora(project_root)
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


def _read_only_report(decision: PromotionCandidate) -> ApplyReport:
    report = ApplyReport()
    if decision.decision == "MINT":
        report.minted = 1
    elif decision.decision == "LINK":
        report.linked = 1
    else:
        report.skipped[decision.reason] += 1
    return report

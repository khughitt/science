from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from science_tool.annotation.io import serialize_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.proposition_reconciliation_apply import (
    PlannedFileEdit,
    ReconciliationApplyError,
    _edit,
    _live_annotation_index,
    _sha256_text,
)
from science_tool.annotation.proposition_resynthesis import (
    AnnotationAssignment,
    ResynthesisDraft,
    ResynthesisDraftError,
    ResynthesisValidationReport,
    render_replacement_proposition,
    validate_resynthesis_draft,
)
from science_tool.annotation.query import SidecarParseError, read_sidecar_strict
from science_tool.entities import EntityCommandError, find_entity, render_entity_frontmatter_updates


class ResynthesisApplyError(ReconciliationApplyError):
    """Raised when proposition resynthesis apply cannot proceed safely."""


@dataclass(frozen=True)
class ResynthesisPreflight:
    draft: ResynthesisDraft
    validation: ResynthesisValidationReport
    file_edits: tuple[PlannedFileEdit, ...]
    expected_annotation_targets: Mapping[str, str]
    expected_source_refs_by_replacement: Mapping[str, tuple[str, ...]]
    expected_original_state: Mapping[str, object]


def _validate(
    project_root: Path,
    draft: ResynthesisDraft,
    as_of: date | None,
) -> ResynthesisValidationReport:
    try:
        return validate_resynthesis_draft(project_root, draft, as_of=as_of)
    except ResynthesisDraftError as exc:
        raise ResynthesisApplyError(str(exc)) from exc


def _sidecar_final_texts_for_assignments(
    project_root: Path,
    assignments: Sequence[AnnotationAssignment],
) -> dict[Path, str]:
    try:
        live_index = _live_annotation_index(project_root)
    except ReconciliationApplyError as exc:
        raise ResynthesisApplyError(str(exc)) from exc

    targets: dict[Path, dict[str, tuple[str, str, str]]] = {}
    for assignment in assignments:
        indexed = live_index.get(assignment.annotation)
        if indexed is None:
            raise ResynthesisApplyError(f"{assignment.annotation} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to not in {assignment.from_proposition, assignment.to_proposition}:
            raise ResynthesisApplyError(
                f"{assignment.annotation} promoted_to {promoted_to!r} is not from or to proposition"
            )

        sidecar_targets = targets.setdefault(sidecar_path, {})
        other = sidecar_targets.get(assignment.annotation)
        if other is not None and other[2] != assignment.to_proposition:
            raise ResynthesisApplyError(
                f"{assignment.annotation} has incompatible resynthesis targets: "
                f"{other[2]}, {assignment.to_proposition}"
            )
        sidecar_targets[assignment.annotation] = (
            assignment.from_proposition,
            assignment.annotation.rsplit("#", 1)[-1],
            assignment.to_proposition,
        )

    final_texts: dict[Path, str] = {}
    for sidecar_path, sidecar_targets in targets.items():
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ResynthesisApplyError(str(exc)) from exc

        seen: set[str] = set()
        annotations = []
        targets_by_id = {
            annotation_id: (annotation_ref, to_proposition)
            for annotation_ref, (_from_proposition, annotation_id, to_proposition) in sidecar_targets.items()
        }
        for annotation in sidecar.annotations:
            target = targets_by_id.get(annotation.id)
            if target is None:
                annotations.append(annotation)
                continue
            annotation_ref, to_proposition = target
            seen.add(annotation.id)
            current = annotation.promoted_to
            from_proposition = sidecar_targets[annotation_ref][0]
            if current not in {from_proposition, to_proposition}:
                raise ResynthesisApplyError(
                    f"{annotation_ref} promoted_to {current!r} is not from or to proposition"
                )
            annotations.append(replace(annotation, promoted_to=to_proposition))

        missing = sorted(set(targets_by_id) - seen)
        if missing:
            rel = sidecar_path.relative_to(project_root).as_posix()
            raise ResynthesisApplyError(f"{rel} missing targeted annotation(s): {', '.join(missing)}")

        final_texts[sidecar_path] = serialize_sidecar(
            Sidecar(
                annotations=tuple(annotations),
                ledgers=sidecar.ledgers,
                shared_targets=sidecar.shared_targets,
            )
        )
    return final_texts


def _original_updates(draft: ResynthesisDraft) -> dict[str, object]:
    if draft.disposition == "split_partial":
        return {}
    replacements = sorted(replacement.id for replacement in draft.new_propositions)
    if len(replacements) == 1:
        return {"status": "superseded", "superseded_by": replacements[0]}
    return {"status": "superseded", "resynthesized_into": replacements}


def _original_edit(
    project_root: Path,
    draft: ResynthesisDraft,
    as_of: date | None,
) -> PlannedFileEdit | None:
    updates = _original_updates(draft)
    if not updates:
        return None
    try:
        location = find_entity(project_root, draft.original_proposition)
        final_text, _changed = render_entity_frontmatter_updates(location.path, updates, as_of=as_of)
    except EntityCommandError as exc:
        raise ResynthesisApplyError(str(exc)) from exc
    return _edit(location.path, final_text, "original_resynthesis_lineage")


def _new_or_existing_edit(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=_sha256_text(before),
        after_sha256=_sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )


def plan_resynthesis_apply(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    as_of: date | None = None,
) -> ResynthesisPreflight:
    root = project_root.resolve()
    validation = _validate(root, draft, as_of)

    edits: dict[Path, PlannedFileEdit] = {}
    for replacement in draft.new_propositions:
        expected_refs = validation.expected_source_refs_by_replacement[replacement.id]
        rendered = render_replacement_proposition(root, replacement, expected_refs, as_of=as_of)
        edits[rendered.path] = _new_or_existing_edit(
            rendered.path,
            rendered.text,
            "replacement_proposition",
        )

    original_edit = _original_edit(root, draft, as_of)
    if original_edit is not None:
        edits[original_edit.path] = original_edit

    for sidecar_path, final_text in _sidecar_final_texts_for_assignments(
        root,
        draft.annotation_assignments,
    ).items():
        edits[sidecar_path] = _edit(sidecar_path, final_text, "annotation_promoted_to_rewrite")

    return ResynthesisPreflight(
        draft=draft,
        validation=validation,
        file_edits=tuple(edits[path] for path in sorted(edits)),
        expected_annotation_targets=validation.expected_annotation_targets,
        expected_source_refs_by_replacement=validation.expected_source_refs_by_replacement,
        expected_original_state=_original_updates(draft),
    )

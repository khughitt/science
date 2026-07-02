from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from science_tool.annotation.io import atomic_write_text, serialize_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.cross_paper_evidence import _resolve_paper_ref
from science_tool.annotation.proposition_reconciliation_apply import (
    PlannedFileEdit,
    ReconciliationApplyError,
    _changed_and_noop_paths,
    _edit,
    _live_annotation_index,
    _path_string,
    _sha256_text,
)
from science_tool.annotation.proposition_reconciliation_plan import reconciliation_action_id
from science_tool.annotation.proposition_resynthesis import (
    AnnotationAssignment,
    ResynthesisDraft,
    ResynthesisDraftError,
    ResynthesisValidationReport,
    _read_review,
    _replacement_frontmatter_source_refs,
    _replacement_local_part,
    _validate_replacement_frontmatter,
    render_replacement_proposition,
    validate_resynthesis_draft,
)
from science_tool.annotation.query import SidecarParseError, read_sidecar_strict
from science_tool.entities import (
    EntityCommandError,
    find_entity,
    parse_markdown_entity_file,
    render_entity_frontmatter_updates,
)


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


@dataclass(frozen=True)
class ResynthesisApplyReport:
    status: str
    original_proposition: str
    replacement_propositions: tuple[str, ...]
    rewritten_annotations: tuple[str, ...]
    changed_paths: tuple[str, ...]
    noop_paths: tuple[str, ...]
    written_paths: tuple[str, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    original_state: Mapping[str, object] = field(default_factory=dict)


def _report_path(path: str, *, project_root: Path | None) -> str:
    parsed = Path(path)
    if project_root is None or not parsed.is_absolute():
        return parsed.as_posix()
    try:
        return parsed.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return parsed.as_posix()


def _report_paths(paths: tuple[str, ...], *, project_root: Path | None) -> list[str]:
    return [_report_path(path, project_root=project_root) for path in paths]


def apply_resynthesis_report_to_json(
    report: ResynthesisApplyReport,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if project_root is not None:
        project_root = project_root.resolve()
    return {
        "schema_version": 1,
        "status": report.status,
        "original_proposition": report.original_proposition,
        "replacement_propositions": list(report.replacement_propositions),
        "rewritten_annotations": list(report.rewritten_annotations),
        "changed_paths": _report_paths(report.changed_paths, project_root=project_root),
        "noop_paths": _report_paths(report.noop_paths, project_root=project_root),
        "written_paths": _report_paths(report.written_paths, project_root=project_root),
        "original_state": dict(report.original_state),
        "diagnostics": [dict(diagnostic) for diagnostic in report.diagnostics],
        "summary": {
            "replacement_propositions": len(report.replacement_propositions),
            "rewritten_annotations": len(report.rewritten_annotations),
            "changed_paths": len(report.changed_paths),
            "noop_paths": len(report.noop_paths),
            "written_paths": len(report.written_paths),
            "diagnostics": len(report.diagnostics),
        },
    }


def _validate(
    project_root: Path,
    draft: ResynthesisDraft,
    as_of: date | None,
) -> ResynthesisValidationReport:
    try:
        return validate_resynthesis_draft(project_root, draft, as_of=as_of)
    except ResynthesisDraftError as exc:
        resume_report = _resume_validation_report(project_root, draft, as_of=as_of)
        if resume_report is not None:
            return resume_report
        raise ResynthesisApplyError(str(exc)) from exc


def _validate_resume_identity(project_root: Path, draft: ResynthesisDraft) -> set[str]:
    expected_action_id = reconciliation_action_id(
        "resynthesize_proposition",
        draft.judgment_id,
        draft.original_proposition,
    )
    if draft.action_id != expected_action_id:
        raise ResynthesisApplyError("draft action_id is stale")

    review_path = Path(draft.source_review)
    if not review_path.is_absolute():
        review_path = project_root / review_path
    try:
        review_doc = _read_review(review_path)
    except ResynthesisDraftError as exc:
        raise ResynthesisApplyError(str(exc)) from exc
    judgments = review_doc.get("judgments")
    if isinstance(judgments, str) or not isinstance(judgments, Sequence):
        raise ResynthesisApplyError("source review judgments must be a list")

    found_candidate = False
    found_judgment = False
    for judgment in judgments:
        if not isinstance(judgment, Mapping):
            continue
        if judgment.get("candidate_id") == draft.candidate_id:
            found_candidate = True
        if judgment.get("judgment_id") == draft.judgment_id:
            found_judgment = True
        if judgment.get("candidate_id") != draft.candidate_id:
            continue
        if judgment.get("judgment_id") != draft.judgment_id:
            continue
        if judgment.get("proposition") != draft.original_proposition:
            raise ResynthesisApplyError("source review judgment proposition is stale")
        return _draft_context_input_annotations(draft)

    if found_judgment:
        raise ResynthesisApplyError("draft candidate_id is stale")
    if found_candidate:
        raise ResynthesisApplyError("draft judgment_id is stale")
    raise ResynthesisApplyError("source review judgment for draft was not found")


def _draft_context_input_annotations(draft: ResynthesisDraft) -> set[str]:
    annotations = draft.context.get("input_annotations")
    if isinstance(annotations, str) or not isinstance(annotations, Sequence):
        raise ResynthesisApplyError("context.input_annotations must be a list of annotation refs")

    current_annotations: set[str] = set()
    for annotation in annotations:
        if not isinstance(annotation, str) or not annotation:
            raise ResynthesisApplyError("context.input_annotations must contain non-empty strings")
        current_annotations.add(annotation)
    return current_annotations


def _resume_validation_report(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    as_of: date | None,
) -> ResynthesisValidationReport | None:
    expected_action_annotations = _validate_resume_identity(project_root, draft)

    replacements = {replacement.id: replacement for replacement in draft.new_propositions}
    if len(replacements) != len(draft.new_propositions):
        return None
    for replacement in draft.new_propositions:
        _replacement_local_part(project_root, replacement.id)
        _validate_replacement_frontmatter(replacement)

    try:
        live_index = _live_annotation_index(project_root)
    except ReconciliationApplyError as exc:
        raise ResynthesisApplyError(str(exc)) from exc

    seen_annotations: set[str] = set()
    expected_targets: dict[str, str] = {}
    expected_refs: dict[str, set[str]] = {
        replacement.id: set(_replacement_frontmatter_source_refs(replacement.frontmatter))
        for replacement in draft.new_propositions
    }
    moved = 0
    retained = 0
    for assignment in draft.annotation_assignments:
        if assignment.annotation in seen_annotations:
            raise ResynthesisApplyError(f"{assignment.annotation} assigned more than once")
        seen_annotations.add(assignment.annotation)

        if assignment.annotation not in expected_action_annotations:
            raise ResynthesisApplyError(f"{assignment.annotation} is not a current input annotation")
        if assignment.from_proposition != draft.original_proposition:
            raise ResynthesisApplyError(
                f"{assignment.annotation} from_proposition must be {draft.original_proposition}"
            )

        if assignment.to_proposition == draft.original_proposition:
            if draft.disposition != "split_partial":
                raise ResynthesisApplyError(f"{assignment.annotation} must target a draft proposition")
            retained += 1
        elif assignment.to_proposition in replacements:
            moved += 1
        else:
            raise ResynthesisApplyError(f"{assignment.to_proposition} is not a draft proposition")

        indexed = live_index.get(assignment.annotation)
        if indexed is None:
            raise ResynthesisApplyError(f"{assignment.annotation} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        allowed_promoted = {assignment.from_proposition, assignment.to_proposition}
        if promoted_to not in allowed_promoted:
            return None

        expected_targets[assignment.annotation] = assignment.to_proposition
        if assignment.to_proposition in replacements:
            expected_refs[assignment.to_proposition].add(assignment.annotation)
            paper_ref = _resolve_paper_ref(sidecar_path)
            if paper_ref is None:
                raise ResynthesisApplyError(f"{assignment.annotation} resolves to no paper ref")
            expected_refs[assignment.to_proposition].add(paper_ref)

    if draft.disposition == "replace":
        if seen_annotations != expected_action_annotations:
            raise ResynthesisApplyError("replace must assign every input annotation")
        if retained:
            raise ResynthesisApplyError("replace assignments must target draft propositions")
    elif draft.disposition == "split_partial":
        if seen_annotations != expected_action_annotations:
            raise ResynthesisApplyError("split_partial must assign every input annotation")
        if moved == 0:
            raise ResynthesisApplyError("split_partial must move at least one annotation to a new proposition")
        if retained == 0:
            raise ResynthesisApplyError(
                "split_partial must retain at least one annotation on original proposition; use replace if all move"
            )

    for proposition, refs in expected_refs.items():
        if not refs:
            raise ResynthesisApplyError(f"{proposition} replacement proposition has no source refs")

    planned_changed_paths = 0
    planned_noop_paths = 0
    for replacement in draft.new_propositions:
        rendered = render_replacement_proposition(
            project_root,
            replacement,
            sorted(expected_refs[replacement.id]),
            as_of=as_of,
        )
        if rendered.changed:
            planned_changed_paths += 1
        else:
            planned_noop_paths += 1

    return ResynthesisValidationReport(
        status="ok",
        original_proposition=draft.original_proposition,
        replacement_propositions=len(draft.new_propositions),
        moved_annotations=moved,
        retained_annotations=retained,
        planned_changed_paths=planned_changed_paths,
        planned_noop_paths=planned_noop_paths,
        expected_annotation_targets=expected_targets,
        expected_source_refs_by_replacement={
            proposition: tuple(sorted(refs)) for proposition, refs in sorted(expected_refs.items())
        },
        action=None,
    )


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


def _frontmatter_for_ref(project_root: Path, ref: str) -> Mapping[str, Any]:
    try:
        location = find_entity(project_root, ref)
        frontmatter, _body = parse_markdown_entity_file(location.path)
    except (EntityCommandError, OSError, ValueError) as exc:
        raise ResynthesisApplyError(f"{ref} failed postflight parse: {exc}") from exc
    return frontmatter


def _postflight(project_root: Path, preflight: ResynthesisPreflight) -> None:
    draft = preflight.draft
    for replacement in draft.new_propositions:
        _frontmatter_for_ref(project_root, replacement.id)

    try:
        live_index = _live_annotation_index(project_root)
    except ReconciliationApplyError as exc:
        raise ResynthesisApplyError(str(exc)) from exc

    for annotation_ref, expected_target in sorted(preflight.expected_annotation_targets.items()):
        indexed = live_index.get(annotation_ref)
        if indexed is None:
            raise ResynthesisApplyError(
                f"{annotation_ref} missing after write; expected promoted_to {expected_target!r}"
            )
        _sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to != expected_target:
            raise ResynthesisApplyError(
                f"{annotation_ref} postflight promoted_to mismatch: "
                f"promoted_to={promoted_to!r}, expected {expected_target!r}"
            )

    original = draft.original_proposition
    if draft.disposition == "replace":
        for assignment in draft.annotation_assignments:
            indexed = live_index.get(assignment.annotation)
            if indexed is None:
                continue
            _sidecar_path, _sidecar, promoted_to = indexed
            if promoted_to == original:
                raise ResynthesisApplyError(
                    f"{assignment.annotation} remains promoted_to original after replace"
                )
    elif draft.disposition == "split_partial":
        for assignment in draft.annotation_assignments:
            if assignment.to_proposition != original:
                continue
            indexed = live_index.get(assignment.annotation)
            if indexed is None:
                raise ResynthesisApplyError(
                    f"{assignment.annotation} missing after write; expected retained original"
                )
            _sidecar_path, _sidecar, promoted_to = indexed
            if promoted_to != original:
                raise ResynthesisApplyError(
                    f"{assignment.annotation} retained assignment mismatch: "
                    f"promoted_to={promoted_to!r}, expected {original!r}"
                )

    for replacement, expected_refs in sorted(preflight.expected_source_refs_by_replacement.items()):
        frontmatter = _frontmatter_for_ref(project_root, replacement)
        source_refs = {str(ref) for ref in frontmatter.get("source_refs") or ()}
        missing = tuple(ref for ref in expected_refs if ref not in source_refs)
        if missing:
            raise ResynthesisApplyError(
                f"{replacement} missing expected source_refs after write: {', '.join(missing)}"
            )

    original_frontmatter = _frontmatter_for_ref(project_root, original)
    for key, expected_value in sorted(preflight.expected_original_state.items()):
        actual_value = original_frontmatter.get(key)
        if actual_value != expected_value:
            raise ResynthesisApplyError(
                f"{original} postflight frontmatter mismatch: "
                f"{key}={actual_value!r}, expected {expected_value!r}"
            )


def apply_resynthesis_draft(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    as_of: date | None = None,
) -> ResynthesisApplyReport:
    root = project_root.resolve()
    preflight = plan_resynthesis_apply(root, draft, as_of=as_of)
    changed_paths, noop_paths = _changed_and_noop_paths(preflight.file_edits)
    written: list[str] = []
    for edit in preflight.file_edits:
        if not edit.changed:
            continue
        try:
            edit.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(edit.path, edit.final_text)
        except OSError as exc:
            written_paths = tuple(written)
            raise ResynthesisApplyError(
                "[stage=write, "
                f"files_written={len(written_paths)}, "
                f"written_paths={written_paths}] "
                f"failed to write {_path_string(edit.path)}: {exc}"
            ) from exc
        written.append(_path_string(edit.path))

    try:
        _postflight(root, preflight)
    except ResynthesisApplyError as exc:
        raise ResynthesisApplyError(f"[stage=postflight, written_paths={tuple(written)}] {exc}") from exc

    rewritten_annotations = tuple(
        sorted(
            assignment.annotation
            for assignment in draft.annotation_assignments
            if assignment.to_proposition != draft.original_proposition
        )
    )
    replacement_propositions = tuple(sorted(replacement.id for replacement in draft.new_propositions))
    return ResynthesisApplyReport(
        status="ok",
        original_proposition=draft.original_proposition,
        replacement_propositions=replacement_propositions,
        rewritten_annotations=rewritten_annotations,
        changed_paths=changed_paths,
        noop_paths=noop_paths,
        written_paths=tuple(written),
        diagnostics=(),
        original_state=preflight.expected_original_state,
    )

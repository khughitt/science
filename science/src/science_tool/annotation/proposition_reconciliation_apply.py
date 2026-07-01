from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from science_tool.annotation.cross_paper_evidence import (
    _iter_project_annotation_sidecar_paths,
    _resolve_paper_ref,
)
from science_tool.annotation.io import atomic_write_text, serialize_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
)
from science_tool.annotation.query import (
    SidecarParseError,
    entity_relpath_for_sidecar,
    read_sidecar_strict,
)
from science_tool.entities import (
    EntityCommandError,
    find_entity,
    parse_markdown_entity_file,
    render_entity_frontmatter_updates,
    render_entity_source_refs,
)


class ReconciliationApplyError(RuntimeError):
    """Raised when proposition reconciliation apply cannot proceed safely."""


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str
    after_sha256: str
    final_text: str
    changed: bool


@dataclass(frozen=True)
class InboundBacklink:
    duplicate: str
    canonical: str
    annotation_ref: str
    paper_ref: str
    sidecar_path: Path
    annotation_id: str
    current_promoted_to: str


@dataclass(frozen=True)
class CanonicalizationPreflight:
    actions: tuple[ReconciliationAction, ...]
    file_edits: tuple[PlannedFileEdit, ...]
    expected_source_refs_by_canonical: Mapping[str, tuple[str, ...]] = field(
        default_factory=dict
    )
    expected_annotation_targets: Mapping[str, str] = field(default_factory=dict)
    action_edit_paths_by_id: Mapping[str, tuple[Path, ...]] = field(default_factory=dict)
    action_path_changed_by_id: Mapping[str, Mapping[Path, bool]] = field(
        default_factory=dict
    )
    action_diagnostics_by_id: Mapping[str, tuple[Mapping[str, Any], ...]] = field(
        default_factory=dict
    )
    diagnostics: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ApplyActionResult:
    action_id: str
    kind: str
    canonical_proposition: str
    members: tuple[str, ...]
    duplicate_propositions: tuple[str, ...]
    status: str
    changed_paths: tuple[str, ...] = ()
    noop_paths: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ReconciliationApplyReport:
    status: str
    selected_actions: int
    changed_paths: tuple[str, ...]
    noop_paths: tuple[str, ...]
    actions: tuple[ApplyActionResult, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    written_paths: tuple[str, ...] = ()


def _path_string(path: Path) -> str:
    return path.as_posix()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _current_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _changed_and_noop_paths(
    edits: Sequence[PlannedFileEdit],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(_path_string(edit.path) for edit in edits if edit.changed)
    noop = tuple(_path_string(edit.path) for edit in edits if not edit.changed)
    return changed, noop


def _changed_and_noop_paths_from_path_changes(
    path_changes: Mapping[Path, bool],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(
        _path_string(path)
        for path, path_changed in sorted(path_changes.items())
        if path_changed
    )
    noop = tuple(
        _path_string(path)
        for path, path_changed in sorted(path_changes.items())
        if not path_changed
    )
    return changed, noop


def _edit(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = _current_text(path)
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=_sha256_text(before),
        after_sha256=_sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )


def _annotation_ref(sidecar_path: Path, project_root: Path, annotation_id: str) -> str:
    entity_relpath = entity_relpath_for_sidecar(sidecar_path, project_root)
    return f"annotation:{entity_relpath}#{annotation_id}"


def _live_annotation_index(
    project_root: Path,
) -> dict[str, tuple[Path, Sidecar, str | None]]:
    index: dict[str, tuple[Path, Sidecar, str | None]] = {}
    for sidecar_path in _iter_project_annotation_sidecar_paths(project_root):
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc
        for annotation in sidecar.annotations:
            ref = _annotation_ref(sidecar_path, project_root, annotation.id)
            index[ref] = (sidecar_path, sidecar, annotation.promoted_to)
    return index


def _duplicate_to_canonical(actions: Sequence[ReconciliationAction]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for action in actions:
        canonical = action.canonical_proposition
        if canonical is None:
            raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
        for member in action.members:
            if member == canonical:
                continue
            other = mapping.get(member)
            if other is not None and other != canonical:
                raise ReconciliationApplyError(
                    f"{member} maps to multiple canonicals: {other}, {canonical}"
                )
            mapping[member] = canonical
    return mapping


def _action_duplicate_propositions(action: ReconciliationAction) -> set[str]:
    canonical = action.canonical_proposition
    if canonical is None:
        raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
    return {member for member in action.members if member != canonical}


def scan_inbound_backlinks(
    project_root: Path,
    duplicate_to_canonical: Mapping[str, str],
) -> tuple[InboundBacklink, ...]:
    rows: list[InboundBacklink] = []
    for sidecar_path in _iter_project_annotation_sidecar_paths(project_root):
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc

        sidecar_rows: list[InboundBacklink] = []
        for annotation in sidecar.annotations:
            promoted_to = annotation.promoted_to
            if promoted_to not in duplicate_to_canonical:
                continue
            annotation_ref = _annotation_ref(sidecar_path, project_root, annotation.id)
            sidecar_rows.append(
                InboundBacklink(
                    duplicate=promoted_to,
                    canonical=duplicate_to_canonical[promoted_to],
                    annotation_ref=annotation_ref,
                    paper_ref="",
                    sidecar_path=sidecar_path,
                    annotation_id=annotation.id,
                    current_promoted_to=promoted_to,
                )
            )

        if not sidecar_rows:
            continue
        paper_ref = _resolve_paper_ref(sidecar_path)
        if paper_ref is None:
            raise ReconciliationApplyError(
                f"{sidecar_path} has duplicate promoted_to backlinks but no resolvable paper ref"
            )
        rows.extend(replace(row, paper_ref=paper_ref) for row in sidecar_rows)

    return tuple(sorted(rows, key=lambda row: (str(row.sidecar_path), row.annotation_id)))


def _listed_sidecar_refs(
    actions: Sequence[ReconciliationAction],
) -> dict[str, str]:
    listed: dict[str, str] = {}
    for action in actions:
        for row in action.inputs.get("sidecar_backlink_rewrites", ()):
            if not isinstance(row, Mapping):
                raise ReconciliationApplyError(
                    f"{action.action_id} has malformed sidecar_backlink_rewrites row"
                )
            duplicate = row.get("from")
            if not isinstance(duplicate, str) or not duplicate:
                raise ReconciliationApplyError(
                    f"{action.action_id} has sidecar_backlink_rewrites row without from"
                )
            annotation_refs = row.get("annotation_refs", ())
            if not isinstance(annotation_refs, Sequence) or isinstance(
                annotation_refs, str
            ):
                raise ReconciliationApplyError(
                    f"{action.action_id} has malformed annotation_refs"
                )
            for annotation_ref in annotation_refs:
                if not isinstance(annotation_ref, str) or not annotation_ref:
                    raise ReconciliationApplyError(
                        f"{action.action_id} has malformed annotation_ref"
                    )
                other = listed.get(annotation_ref)
                if other is not None and other != duplicate:
                    raise ReconciliationApplyError(
                        f"{annotation_ref} listed for multiple duplicates: {other}, {duplicate}"
                    )
                listed[annotation_ref] = duplicate
    return listed


def _listed_sidecar_refs_by_action(
    actions: Sequence[ReconciliationAction],
) -> dict[str, set[str]]:
    refs_by_action: dict[str, set[str]] = {}
    for action in actions:
        action_refs = refs_by_action.setdefault(action.action_id, set())
        for row in action.inputs.get("sidecar_backlink_rewrites", ()):
            if not isinstance(row, Mapping):
                raise ReconciliationApplyError(
                    f"{action.action_id} has malformed sidecar_backlink_rewrites row"
                )
            annotation_refs = row.get("annotation_refs", ())
            if not isinstance(annotation_refs, Sequence) or isinstance(
                annotation_refs, str
            ):
                raise ReconciliationApplyError(
                    f"{action.action_id} has malformed annotation_refs"
                )
            for annotation_ref in annotation_refs:
                if not isinstance(annotation_ref, str) or not annotation_ref:
                    raise ReconciliationApplyError(
                        f"{action.action_id} has malformed annotation_ref"
                    )
                action_refs.add(annotation_ref)
    return refs_by_action


def _diagnostics_by_action(
    actions: Sequence[ReconciliationAction],
    diagnostics: Sequence[Mapping[str, Any]],
    listed_refs_by_action: Mapping[str, set[str]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    by_action: dict[str, list[Mapping[str, Any]]] = {
        action.action_id: [] for action in actions
    }
    for diagnostic in diagnostics:
        diagnostic_duplicate = diagnostic.get("duplicate")
        diagnostic_canonical = diagnostic.get("canonical")
        diagnostic_annotation_ref = diagnostic.get("annotation_ref")
        for action in actions:
            canonical = action.canonical_proposition
            duplicates = _action_duplicate_propositions(action)
            if (
                diagnostic_duplicate in duplicates
                or diagnostic_canonical == canonical
                or diagnostic_annotation_ref
                in listed_refs_by_action.get(action.action_id, set())
            ):
                by_action[action.action_id].append(diagnostic)
    return {
        action_id: tuple(action_diagnostics)
        for action_id, action_diagnostics in by_action.items()
    }


def _validate_listed_refs(
    *,
    duplicate_to_canonical: Mapping[str, str],
    live_backlinks: Sequence[InboundBacklink],
    live_annotation_index: Mapping[str, tuple[Path, Sidecar, str | None]],
    listed_refs: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    diagnostics: list[Mapping[str, Any]] = []
    listed = set(listed_refs)
    for backlink in live_backlinks:
        if backlink.annotation_ref in listed:
            continue
        diagnostics.append(
            {
                "reason": "half_b_missing_live_backlink",
                "annotation_ref": backlink.annotation_ref,
                "duplicate": backlink.duplicate,
                "canonical": backlink.canonical,
            }
        )

    for annotation_ref, duplicate in sorted(listed_refs.items()):
        canonical = duplicate_to_canonical.get(duplicate)
        if canonical is None:
            raise ReconciliationApplyError(
                f"{annotation_ref} lists unselected duplicate {duplicate}"
            )
        indexed = live_annotation_index.get(annotation_ref)
        if indexed is None:
            raise ReconciliationApplyError(
                f"{annotation_ref} resolves to no live sidecar annotation"
            )
        _sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to == duplicate:
            continue
        if promoted_to == canonical:
            diagnostics.append(
                {
                    "reason": "listed_backlink_already_canonical",
                    "annotation_ref": annotation_ref,
                    "duplicate": duplicate,
                    "canonical": canonical,
                }
            )
            continue
        raise ReconciliationApplyError(
            f"{annotation_ref} promoted_to {promoted_to!r} is not {duplicate} or {canonical}"
        )

    return tuple(diagnostics)


def _listed_already_canonical_targets(
    *,
    duplicate_to_canonical: Mapping[str, str],
    live_annotation_index: Mapping[str, tuple[Path, Sidecar, str | None]],
    listed_refs: Mapping[str, str],
) -> dict[str, str]:
    targets: dict[str, str] = {}
    for annotation_ref, duplicate in sorted(listed_refs.items()):
        canonical = duplicate_to_canonical.get(duplicate)
        indexed = live_annotation_index.get(annotation_ref)
        if canonical is None or indexed is None:
            continue
        _sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to == canonical:
            targets[annotation_ref] = canonical
    return targets


def _entity_location(project_root: Path, ref: str):
    try:
        return find_entity(project_root, ref)
    except EntityCommandError as exc:
        raise ReconciliationApplyError(str(exc)) from exc


def _canonical_source_refs(
    action: ReconciliationAction,
    live_backlinks: Sequence[InboundBacklink],
) -> tuple[str, ...]:
    canonical = action.canonical_proposition
    duplicates = {member for member in action.members if member != canonical}
    refs: set[str] = set()
    for row in action.inputs.get("source_ref_moves", ()):
        if not isinstance(row, Mapping):
            raise ReconciliationApplyError(
                f"{action.action_id} has malformed source_ref_moves row"
            )
        if row.get("from") not in duplicates:
            continue
        source_refs = row.get("source_refs", ())
        if not isinstance(source_refs, Sequence) or isinstance(source_refs, str):
            raise ReconciliationApplyError(
                f"{action.action_id} has malformed source_refs"
            )
        refs.update(str(ref) for ref in source_refs)
    for backlink in live_backlinks:
        if backlink.duplicate not in duplicates:
            continue
        refs.add(backlink.paper_ref)
        refs.add(backlink.annotation_ref)
    return tuple(sorted(refs))


def _sidecar_final_texts(
    project_root: Path,
    live_backlinks: Sequence[InboundBacklink],
) -> dict[Path, str]:
    targets: dict[Path, dict[str, str]] = {}
    for backlink in live_backlinks:
        sidecar_targets = targets.setdefault(backlink.sidecar_path, {})
        other = sidecar_targets.get(backlink.annotation_id)
        if other is not None and other != backlink.canonical:
            raise ReconciliationApplyError(
                f"{backlink.annotation_ref} has incompatible canonical targets: "
                f"{other}, {backlink.canonical}"
            )
        sidecar_targets[backlink.annotation_id] = backlink.canonical

    final_texts: dict[Path, str] = {}
    for sidecar_path, sidecar_targets in targets.items():
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc
        seen: set[str] = set()
        annotations = []
        for annotation in sidecar.annotations:
            canonical = sidecar_targets.get(annotation.id)
            if canonical is None:
                annotations.append(annotation)
                continue
            seen.add(annotation.id)
            annotations.append(replace(annotation, promoted_to=canonical))
        missing = sorted(set(sidecar_targets) - seen)
        if missing:
            rel = sidecar_path.relative_to(project_root).as_posix()
            raise ReconciliationApplyError(
                f"{rel} missing targeted annotation(s): {', '.join(missing)}"
            )
        final_texts[sidecar_path] = serialize_sidecar(
            Sidecar(
                annotations=tuple(annotations),
                ledgers=sidecar.ledgers,
                shared_targets=sidecar.shared_targets,
            )
        )
    return final_texts


def _format_issue(issue: object, index: int) -> str:
    if not isinstance(issue, Mapping):
        raise ReconciliationApplyError(
            f"action plan has malformed top-level error at index {index}"
        )
    reason = issue.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ReconciliationApplyError("action plan has malformed error entry: missing reason")
    detail = issue.get("detail")
    if detail is None or detail == "":
        return reason
    return f"{reason}: {detail}"


def _format_blocker(action_id: str, blocker: object, index: int) -> str:
    if not isinstance(blocker, Mapping):
        raise ReconciliationApplyError(f"{action_id} has malformed blocker at index {index}")
    reason = blocker.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ReconciliationApplyError(f"{action_id} has malformed blocker at index {index}")
    detail = blocker.get("detail")
    if detail is None or detail == "":
        return reason
    return f"{reason}: {detail}"


def _duplicate_action_ids(actions: Sequence[ReconciliationAction]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for action in actions:
        if action.action_id in seen:
            duplicates.add(action.action_id)
        seen.add(action.action_id)
    return tuple(sorted(duplicates))


def select_canonicalization_actions(
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
) -> tuple[ReconciliationAction, ...]:
    if plan.errors:
        error_messages = "; ".join(
            _format_issue(error, index) for index, error in enumerate(plan.errors)
        )
        raise ReconciliationApplyError(
            "action plan has top-level errors; "
            f"{error_messages}; run plan-proposition-reconciliation first"
        )

    duplicate_action_ids = _duplicate_action_ids(plan.actions)
    if duplicate_action_ids:
        raise ReconciliationApplyError(
            "duplicate reconciliation action id(s) in plan: "
            f"{', '.join(duplicate_action_ids)}"
        )

    by_id = {action.action_id: action for action in plan.actions}
    if requested_action_ids:
        seen_requested_ids: set[str] = set()
        duplicate_requested_ids: set[str] = set()
        for action_id in requested_action_ids:
            if action_id in seen_requested_ids:
                duplicate_requested_ids.add(action_id)
            seen_requested_ids.add(action_id)
        if duplicate_requested_ids:
            raise ReconciliationApplyError(
                "duplicate reconciliation action request(s): "
                f"{', '.join(sorted(duplicate_requested_ids))}"
            )
        unknown = sorted(set(requested_action_ids) - set(by_id))
        if unknown:
            raise ReconciliationApplyError(
                f"unknown reconciliation action(s): {', '.join(unknown)}"
            )
        candidates = tuple(by_id[action_id] for action_id in requested_action_ids)
    else:
        candidates = tuple(
            action
            for action in plan.actions
            if action.kind == "canonicalize_propositions"
            and action.status == "ready"
            and not action.blockers
        )

    selected: list[ReconciliationAction] = []
    for action in candidates:
        if action.kind == "resynthesize_proposition":
            raise ReconciliationApplyError(
                f"{action.action_id} is resynthesize_proposition; "
                "factorization resynthesis is not executable by Half C"
            )
        if action.blockers:
            blocker_messages = [
                _format_blocker(action.action_id, blocker, index)
                for index, blocker in enumerate(action.blockers)
            ]
            raise ReconciliationApplyError(
                f"{action.action_id} has blocker(s): {'; '.join(blocker_messages)}"
            )
        if action.kind != "canonicalize_propositions" or action.status != "ready":
            raise ReconciliationApplyError(
                f"{action.action_id} is {action.status} {action.kind}, "
                "not executable by Half C"
            )
        if not action.canonical_proposition:
            raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
        if len(action.members) < 2:
            raise ReconciliationApplyError(f"{action.action_id} has fewer than two members")
        selected.append(action)

    if not selected:
        raise ReconciliationApplyError("no ready canonicalize_propositions actions to apply")

    seen_members: dict[str, str] = {}
    for action in selected:
        for member in action.members:
            other = seen_members.get(member)
            if other is not None and other != action.action_id:
                raise ReconciliationApplyError(
                    f"{member} is targeted by multiple selected actions: "
                    f"{other}, {action.action_id}"
                )
            seen_members[member] = action.action_id

    return tuple(sorted(selected, key=lambda action: action.action_id))


def plan_canonicalization_apply(
    project_root: Path,
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
    as_of: date | None = None,
) -> CanonicalizationPreflight:
    project_root = project_root.resolve()
    actions = select_canonicalization_actions(
        plan,
        requested_action_ids=requested_action_ids,
    )
    duplicate_to_canonical = _duplicate_to_canonical(actions)
    live_backlinks = scan_inbound_backlinks(project_root, duplicate_to_canonical)
    live_annotation_index = _live_annotation_index(project_root)
    listed_refs = _listed_sidecar_refs(actions)
    diagnostics = list(
        _validate_listed_refs(
            duplicate_to_canonical=duplicate_to_canonical,
            live_backlinks=live_backlinks,
            live_annotation_index=live_annotation_index,
            listed_refs=listed_refs,
        )
    )

    edits: dict[Path, PlannedFileEdit] = {}
    expected_refs_by_canonical: dict[str, tuple[str, ...]] = {}
    expected_annotation_targets = {
        backlink.annotation_ref: backlink.canonical for backlink in live_backlinks
    }
    expected_annotation_targets.update(
        _listed_already_canonical_targets(
            duplicate_to_canonical=duplicate_to_canonical,
            live_annotation_index=live_annotation_index,
            listed_refs=listed_refs,
        )
    )
    listed_refs_by_action = _listed_sidecar_refs_by_action(actions)
    action_edit_paths_by_id: dict[str, tuple[Path, ...]] = {}
    action_path_changed_by_id: dict[str, Mapping[Path, bool]] = {}

    for action in actions:
        canonical = action.canonical_proposition
        if canonical is None:
            raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")

        action_path_changed: dict[Path, bool] = {}
        canonical_location = _entity_location(project_root, canonical)
        canonical_refs = _canonical_source_refs(action, live_backlinks)
        expected_refs_by_canonical[canonical] = canonical_refs
        final_text, _changed = render_entity_source_refs(
            canonical_location.path,
            canonical_refs,
            as_of=as_of,
        )
        canonical_edit = _edit(
            canonical_location.path,
            final_text,
            "canonical_source_refs",
        )
        edits[canonical_location.path] = canonical_edit
        action_path_changed[canonical_location.path] = canonical_edit.changed

        for duplicate in action.members:
            if duplicate == canonical:
                continue
            duplicate_location = _entity_location(project_root, duplicate)
            frontmatter, _body = parse_markdown_entity_file(duplicate_location.path)
            existing_superseded_by = frontmatter.get("superseded_by")
            if (
                existing_superseded_by is not None
                and str(existing_superseded_by) != canonical
            ):
                raise ReconciliationApplyError(
                    f"{duplicate} already has superseded_by {existing_superseded_by}"
                )
            final_text, _changed = render_entity_frontmatter_updates(
                duplicate_location.path,
                {"status": "superseded", "superseded_by": canonical},
                as_of=as_of,
            )
            duplicate_edit = _edit(
                duplicate_location.path,
                final_text,
                "duplicate_supersession",
            )
            edits[duplicate_location.path] = duplicate_edit
            action_path_changed[duplicate_location.path] = duplicate_edit.changed

        action_duplicates = _action_duplicate_propositions(action)
        for backlink in live_backlinks:
            if backlink.duplicate in action_duplicates:
                action_path_changed[backlink.sidecar_path] = True
        for annotation_ref in listed_refs_by_action.get(action.action_id, set()):
            indexed = live_annotation_index.get(annotation_ref)
            if indexed is not None:
                sidecar_path, _sidecar, promoted_to = indexed
                target_changed = promoted_to != canonical
                action_path_changed[sidecar_path] = (
                    action_path_changed.get(sidecar_path, False) or target_changed
                )
        action_edit_paths_by_id[action.action_id] = tuple(sorted(action_path_changed))
        action_path_changed_by_id[action.action_id] = dict(action_path_changed)

    for sidecar_path, final_text in _sidecar_final_texts(
        project_root,
        live_backlinks,
    ).items():
        edits[sidecar_path] = _edit(sidecar_path, final_text, "sidecar_promoted_to")

    return CanonicalizationPreflight(
        actions=actions,
        file_edits=tuple(edits[path] for path in sorted(edits)),
        expected_source_refs_by_canonical=expected_refs_by_canonical,
        expected_annotation_targets=expected_annotation_targets,
        action_edit_paths_by_id=action_edit_paths_by_id,
        action_path_changed_by_id=action_path_changed_by_id,
        action_diagnostics_by_id=_diagnostics_by_action(
            actions,
            diagnostics,
            listed_refs_by_action,
        ),
        diagnostics=tuple(diagnostics),
    )


def _postflight(
    project_root: Path,
    actions: Sequence[ReconciliationAction],
    expected_source_refs_by_canonical: Mapping[str, tuple[str, ...]],
    expected_annotation_targets: Mapping[str, str],
) -> None:
    duplicate_to_canonical = _duplicate_to_canonical(actions)
    for duplicate, canonical in sorted(duplicate_to_canonical.items()):
        duplicate_location = _entity_location(project_root, duplicate)
        frontmatter, _body = parse_markdown_entity_file(duplicate_location.path)
        status = frontmatter.get("status")
        superseded_by = frontmatter.get("superseded_by")
        if status != "superseded" or superseded_by != canonical:
            raise ReconciliationApplyError(
                f"{duplicate} postflight supersession mismatch: "
                f"status={status!r}, superseded_by={superseded_by!r}, "
                f"expected status='superseded', superseded_by={canonical!r}"
            )

    remaining_backlinks = scan_inbound_backlinks(project_root, duplicate_to_canonical)
    if remaining_backlinks:
        refs = ", ".join(backlink.annotation_ref for backlink in remaining_backlinks)
        raise ReconciliationApplyError(
            "duplicate promoted_to backlinks remain after write: " f"{refs}"
        )

    live_annotation_index = _live_annotation_index(project_root)
    for annotation_ref, expected_canonical in sorted(expected_annotation_targets.items()):
        indexed = live_annotation_index.get(annotation_ref)
        if indexed is None:
            raise ReconciliationApplyError(
                f"{annotation_ref} missing after write; expected promoted_to "
                f"{expected_canonical!r}"
            )
        _sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to != expected_canonical:
            raise ReconciliationApplyError(
                f"{annotation_ref} postflight promoted_to mismatch: "
                f"promoted_to={promoted_to!r}, expected {expected_canonical!r}"
            )

    for canonical, expected_refs in sorted(expected_source_refs_by_canonical.items()):
        canonical_location = _entity_location(project_root, canonical)
        frontmatter, _body = parse_markdown_entity_file(canonical_location.path)
        source_refs = {str(ref) for ref in frontmatter.get("source_refs") or ()}
        missing = tuple(ref for ref in expected_refs if ref not in source_refs)
        if missing:
            raise ReconciliationApplyError(
                f"{canonical} missing expected source_refs after write: "
                f"{', '.join(missing)}"
            )


def _action_result(
    action: ReconciliationAction,
    changed_paths: tuple[str, ...],
    noop_paths: tuple[str, ...],
    diagnostics: tuple[Mapping[str, Any], ...],
) -> ApplyActionResult:
    canonical = action.canonical_proposition
    if canonical is None:
        raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
    duplicate_propositions = tuple(member for member in action.members if member != canonical)
    return ApplyActionResult(
        action_id=action.action_id,
        kind=action.kind,
        canonical_proposition=canonical,
        members=action.members,
        duplicate_propositions=duplicate_propositions,
        status="applied" if changed_paths else "noop",
        changed_paths=changed_paths,
        noop_paths=noop_paths,
        diagnostics=diagnostics,
    )


def apply_canonicalization_plan(
    project_root: Path,
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
    as_of: date | None = None,
) -> ReconciliationApplyReport:
    project_root = project_root.resolve()
    preflight = plan_canonicalization_apply(
        project_root,
        plan,
        requested_action_ids=requested_action_ids,
        as_of=as_of,
    )
    changed_paths, noop_paths = _changed_and_noop_paths(preflight.file_edits)
    written: list[str] = []
    for edit in preflight.file_edits:
        if not edit.changed:
            continue
        try:
            atomic_write_text(edit.path, edit.final_text)
        except OSError as exc:
            written_paths = tuple(written)
            raise ReconciliationApplyError(
                "[stage=write, "
                f"files_written={len(written_paths)}, "
                f"written_paths={written_paths}] "
                f"failed to write {_path_string(edit.path)}: {exc}"
            ) from exc
        written.append(_path_string(edit.path))

    try:
        _postflight(
            project_root,
            preflight.actions,
            preflight.expected_source_refs_by_canonical,
            preflight.expected_annotation_targets,
        )
    except ReconciliationApplyError as exc:
        raise ReconciliationApplyError(
            f"[stage=postflight, written_paths={tuple(written)}] {exc}"
        ) from exc

    return ReconciliationApplyReport(
        status="ok",
        selected_actions=len(preflight.actions),
        changed_paths=changed_paths,
        noop_paths=noop_paths,
        actions=tuple(
            _action_result(
                action,
                *_changed_and_noop_paths_from_path_changes(
                    preflight.action_path_changed_by_id.get(action.action_id, {})
                ),
                preflight.action_diagnostics_by_id.get(action.action_id, ()),
            )
            for action in preflight.actions
        ),
        diagnostics=preflight.diagnostics,
        written_paths=tuple(written),
    )

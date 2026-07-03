from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from science_model.propositions import PropositionEntity
from science_tool.annotation.cross_paper_evidence import _resolve_paper_ref
from science_tool.annotation.proposition_reconciliation import (
    ReconciliationValidationError,
    build_reconciliation_report,
)
from science_tool.annotation.proposition_reconciliation_apply import _live_annotation_index
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
)
from science_tool.entities import (
    EntityCommandError,
    _render_markdown,
    find_entity,
    local_part_conforms,
    parse_markdown_entity_file,
    resolve_path_policy,
)

RESYNTHESIS_SCHEMA_VERSION = 1
RESYNTHESIS_CONTEXT_SCHEMA_VERSION = 1
RESYNTHESIS_CONTEXT_SOURCE = "derived:proposition-resynthesis-context-v1"
RESYNTHESIS_CONTEXT_FRONTMATTER_KEYS = (
    "subject",
    "predicate",
    "object",
    "polarity",
    "claim_layer",
    "identification_strength",
    "source_refs",
)
RESYNTHESIS_SOURCE_RE = re.compile(r"^llm-review:[A-Za-z0-9._-]+:proposition-resynthesis-v1$")
DEFAULT_RESYNTHESIS_SOURCE_MODEL = "codex-gpt-5"
RESYNTHESIS_DISPOSITIONS = frozenset({"replace", "split_partial"})
ALLOWED_REPLACEMENT_FRONTMATTER_KEYS = frozenset(
    {
        "type",
        "kind",
        "status",
        "related",
        "source_refs",
        "subject",
        "predicate",
        "object",
        "polarity",
        "claim_layer",
        "identification_strength",
        "ontology_terms",
        "discusses",
    }
)
ALLOWED_DRAFT_KEYS = frozenset(
    {
        "schema_version",
        "source",
        "action_id",
        "candidate_id",
        "judgment_id",
        "source_review",
        "original_proposition",
        "disposition",
        "input_annotations",
        "new_propositions",
        "annotation_assignments",
        "context",
        "notes",
    }
)
ALLOWED_NEW_PROPOSITION_KEYS = frozenset({"id", "title", "body", "frontmatter"})
ALLOWED_ASSIGNMENT_KEYS = frozenset({"annotation", "from", "to"})


class ResynthesisDraftError(ValueError):
    """Raised when a proposition resynthesis draft cannot be used safely."""


@dataclass(frozen=True)
class NewPropositionDraft:
    id: str
    title: str
    body: str
    frontmatter: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnnotationAssignment:
    annotation: str
    from_proposition: str
    to_proposition: str


@dataclass(frozen=True)
class ResynthesisDraft:
    schema_version: int
    source: str
    action_id: str
    candidate_id: str
    judgment_id: str
    source_review: str
    original_proposition: str
    disposition: Literal["replace", "split_partial"]
    input_annotations: tuple[str, ...]
    new_propositions: tuple[NewPropositionDraft, ...] = ()
    annotation_assignments: tuple[AnnotationAssignment, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class RenderedReplacement:
    proposition: str
    path: Path
    text: str
    changed: bool


@dataclass(frozen=True)
class ResynthesisValidationReport:
    status: str
    original_proposition: str
    replacement_propositions: int
    moved_annotations: int
    retained_annotations: int
    planned_changed_paths: int = 0
    planned_noop_paths: int = 0
    expected_annotation_targets: Mapping[str, str] = field(default_factory=dict)
    expected_source_refs_by_replacement: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    action: ReconciliationAction | None = None
    errors: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[Mapping[str, Any], ...] = ()


def _read_review(path: Path) -> Mapping[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResynthesisDraftError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ResynthesisDraftError(f"{path} must contain a JSON object")
    return loaded


def build_live_action_plan(project_root: Path, source_review: str) -> ReconciliationActionPlan:
    review_path = Path(source_review)
    if not review_path.is_absolute():
        review_path = project_root / review_path

    try:
        doc = _read_review(review_path)
        report = build_reconciliation_report(project_root)
        return build_reconciliation_action_plan(
            report,
            [ReviewedReconciliationInput(path=str(review_path), doc=doc)],
        )
    except (ReconciliationValidationError, ValueError) as exc:
        raise ResynthesisDraftError(str(exc)) from exc


def resolve_resynthesis_action(
    plan: ReconciliationActionPlan,
    *,
    requested_action_id: str | None,
) -> ReconciliationAction:
    if plan.errors:
        details = "; ".join(str(error.get("reason", error)) for error in plan.errors)
        raise ResynthesisDraftError(f"action plan has top-level errors: {details}")

    ready = tuple(
        action
        for action in plan.actions
        if action.kind == "resynthesize_proposition" and action.status == "ready" and not action.blockers
    )
    if requested_action_id is None:
        if len(ready) == 1:
            return ready[0]
        if not ready:
            raise ResynthesisDraftError("no ready resynthesize_proposition actions")
        raise ResynthesisDraftError("multiple ready resynthesize_proposition actions; pass --action")

    by_id = {action.action_id: action for action in plan.actions}
    action = by_id.get(requested_action_id)
    if action is None:
        raise ResynthesisDraftError(f"unknown reconciliation action: {requested_action_id}")
    if action.kind != "resynthesize_proposition" or action.status != "ready" or action.blockers:
        raise ResynthesisDraftError(f"{requested_action_id} is not ready resynthesize_proposition")
    return action


def build_resynthesis_scaffold(
    plan: ReconciliationActionPlan,
    *,
    requested_action_id: str | None,
    source_review: str,
    model: str = DEFAULT_RESYNTHESIS_SOURCE_MODEL,
) -> ResynthesisDraft:
    action = resolve_resynthesis_action(plan, requested_action_id=requested_action_id)
    if action.proposition is None:
        raise ResynthesisDraftError(f"{action.action_id} has no proposition")

    return ResynthesisDraft(
        schema_version=RESYNTHESIS_SCHEMA_VERSION,
        source=f"llm-review:{model}:proposition-resynthesis-v1",
        action_id=action.action_id,
        candidate_id=action.candidate_id,
        judgment_id=action.judgment_id,
        source_review=source_review,
        original_proposition=action.proposition,
        disposition="replace",
        input_annotations=tuple(action.inputs.get("annotations", ())),
        new_propositions=(),
        annotation_assignments=(),
        context={
            "rationale": action.rationale,
            "observed_statement_hints": tuple(action.inputs.get("observed_statement_hints", ())),
            "papers": tuple(action.inputs.get("papers", ())),
        },
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _selected_original_frontmatter(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(frontmatter.get(key)) for key in RESYNTHESIS_CONTEXT_FRONTMATTER_KEYS}


def draft_to_json(draft: ResynthesisDraft) -> dict[str, Any]:
    return {
        "schema_version": draft.schema_version,
        "source": draft.source,
        "action_id": draft.action_id,
        "candidate_id": draft.candidate_id,
        "judgment_id": draft.judgment_id,
        "source_review": draft.source_review,
        "original_proposition": draft.original_proposition,
        "disposition": draft.disposition,
        "input_annotations": list(draft.input_annotations),
        "new_propositions": [
            {
                "id": row.id,
                "title": row.title,
                "body": row.body,
                "frontmatter": _jsonable(row.frontmatter),
            }
            for row in draft.new_propositions
        ],
        "annotation_assignments": [
            {
                "annotation": row.annotation,
                "from": row.from_proposition,
                "to": row.to_proposition,
            }
            for row in draft.annotation_assignments
        ],
        "context": _jsonable(draft.context),
        "notes": draft.notes,
    }


def validation_report_to_json(report: ResynthesisValidationReport) -> dict[str, Any]:
    return {
        "schema_version": RESYNTHESIS_SCHEMA_VERSION,
        "status": report.status,
        "original_proposition": report.original_proposition,
        "replacement_propositions": report.replacement_propositions,
        "moved_annotations": report.moved_annotations,
        "retained_annotations": report.retained_annotations,
        "planned_changed_paths": report.planned_changed_paths,
        "planned_noop_paths": report.planned_noop_paths,
        "expected_annotation_targets": dict(report.expected_annotation_targets),
        "expected_source_refs_by_replacement": {
            proposition: list(refs)
            for proposition, refs in report.expected_source_refs_by_replacement.items()
        },
        "errors": [dict(error) for error in report.errors],
        "warnings": [dict(warning) for warning in report.warnings],
        "summary": {
            "replacement_propositions": report.replacement_propositions,
            "moved_annotations": report.moved_annotations,
            "retained_annotations": report.retained_annotations,
            "planned_changed_paths": report.planned_changed_paths,
            "planned_noop_paths": report.planned_noop_paths,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
        },
    }


def _required_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ResynthesisDraftError(f"missing or invalid {key}")
    return value


def _required_mapping(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key)
    if not isinstance(value, Mapping):
        raise ResynthesisDraftError(f"missing or invalid {key}")
    return value


def _optional_mapping(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key, {})
    if not isinstance(value, Mapping):
        raise ResynthesisDraftError(f"invalid {key}")
    return value


def _required_string_sequence(row: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = row.get(key)
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ResynthesisDraftError(f"{key} must be a list of annotation refs")

    seen: set[str] = set()
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item != item.strip():
            raise ResynthesisDraftError(f"{key} must contain non-empty strings")
        if item in seen:
            raise ResynthesisDraftError(f"{key} contains duplicate annotation refs")
        seen.add(item)
        refs.append(item)
    return tuple(refs)


def _reject_unknown_keys(row: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(row) - allowed)
    if unknown:
        raise ResynthesisDraftError(f"unknown {label} key: {unknown[0]}")


def _ensure_keys(row: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    missing = sorted(allowed - set(row))
    if missing:
        raise ResynthesisDraftError(f"missing {label} key: {missing[0]}")
    _reject_unknown_keys(row, allowed, label)


def parse_resynthesis_draft(payload: Any) -> ResynthesisDraft:
    if not isinstance(payload, Mapping):
        raise ResynthesisDraftError("resynthesis draft must be an object")
    _ensure_keys(payload, ALLOWED_DRAFT_KEYS, "resynthesis draft")

    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != RESYNTHESIS_SCHEMA_VERSION:
        raise ResynthesisDraftError(f"schema_version must be {RESYNTHESIS_SCHEMA_VERSION}")

    source = _required_str(payload, "source")
    if RESYNTHESIS_SOURCE_RE.fullmatch(source) is None:
        raise ResynthesisDraftError("source must match proposition resynthesis source format")

    disposition = _required_str(payload, "disposition")
    if disposition not in RESYNTHESIS_DISPOSITIONS:
        raise ResynthesisDraftError(f"disposition must be one of {sorted(RESYNTHESIS_DISPOSITIONS)}")

    raw_new = payload.get("new_propositions")
    if not isinstance(raw_new, list):
        raise ResynthesisDraftError("new_propositions must be a list")
    new_propositions: list[NewPropositionDraft] = []
    for index, row in enumerate(raw_new):
        if not isinstance(row, Mapping):
            raise ResynthesisDraftError(f"new_propositions[{index}] must be an object")
        _reject_unknown_keys(row, ALLOWED_NEW_PROPOSITION_KEYS, f"new_propositions[{index}]")
        new_propositions.append(
            NewPropositionDraft(
                id=_required_str(row, "id"),
                title=_required_str(row, "title"),
                body=_required_str(row, "body"),
                frontmatter=dict(_required_mapping(row, "frontmatter")),
            )
        )

    raw_assignments = payload.get("annotation_assignments")
    if not isinstance(raw_assignments, list):
        raise ResynthesisDraftError("annotation_assignments must be a list")
    assignments: list[AnnotationAssignment] = []
    for index, row in enumerate(raw_assignments):
        if not isinstance(row, Mapping):
            raise ResynthesisDraftError(f"annotation_assignments[{index}] must be an object")
        _reject_unknown_keys(row, ALLOWED_ASSIGNMENT_KEYS, f"annotation_assignments[{index}]")
        assignments.append(
            AnnotationAssignment(
                annotation=_required_str(row, "annotation"),
                from_proposition=_required_str(row, "from"),
                to_proposition=_required_str(row, "to"),
            )
        )

    notes = payload["notes"]
    if not isinstance(notes, str):
        raise ResynthesisDraftError("invalid notes")

    return ResynthesisDraft(
        schema_version=schema_version,
        source=source,
        action_id=_required_str(payload, "action_id"),
        candidate_id=_required_str(payload, "candidate_id"),
        judgment_id=_required_str(payload, "judgment_id"),
        source_review=_required_str(payload, "source_review"),
        original_proposition=_required_str(payload, "original_proposition"),
        disposition=disposition,  # type: ignore[arg-type]
        input_annotations=_required_string_sequence(payload, "input_annotations"),
        new_propositions=tuple(new_propositions),
        annotation_assignments=tuple(assignments),
        context=_required_mapping(payload, "context"),
        notes=notes,
    )


def _live_action_for_draft(project_root: Path, draft: ResynthesisDraft) -> ReconciliationAction:
    plan = build_live_action_plan(project_root, draft.source_review)
    action = resolve_resynthesis_action(plan, requested_action_id=draft.action_id)
    if action.proposition != draft.original_proposition:
        raise ResynthesisDraftError("draft original_proposition is stale")
    if action.candidate_id != draft.candidate_id:
        raise ResynthesisDraftError("draft candidate_id is stale")
    if action.judgment_id != draft.judgment_id:
        raise ResynthesisDraftError("draft judgment_id is stale")
    return action


def _replacement_frontmatter_source_refs(frontmatter: Mapping[str, Any]) -> tuple[str, ...]:
    if "source_refs" not in frontmatter:
        return ()
    source_refs = frontmatter["source_refs"]
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, str):
        raise ResynthesisDraftError("proposition frontmatter source_refs must be a list")
    refs: list[str] = []
    for ref in source_refs:
        if not isinstance(ref, str) or not ref or ref != ref.strip():
            raise ResynthesisDraftError("proposition frontmatter source_refs must contain non-empty strings")
        refs.append(ref)
    return tuple(refs)


def _validate_replacement_frontmatter(replacement: NewPropositionDraft) -> None:
    unknown = sorted(set(replacement.frontmatter) - ALLOWED_REPLACEMENT_FRONTMATTER_KEYS)
    if unknown:
        raise ResynthesisDraftError(f"unknown proposition frontmatter key: {unknown[0]}")
    _replacement_frontmatter_source_refs(replacement.frontmatter)


def _replacement_local_part(project_root: Path, proposition_id: str) -> str:
    prefix, separator, local_part = proposition_id.partition(":")
    if (
        prefix != "proposition"
        or separator != ":"
        or not local_part
        or not local_part_conforms("proposition", local_part, project_root=project_root)
    ):
        raise ResynthesisDraftError(f"invalid replacement proposition id: {proposition_id}")
    return local_part


def _current_action_annotations(action: ReconciliationAction) -> tuple[str, ...]:
    if "annotations" not in action.inputs:
        raise ResynthesisDraftError(f"{action.action_id} has malformed input annotations")
    annotations = action.inputs["annotations"]
    if isinstance(annotations, str) or not isinstance(annotations, Sequence):
        raise ResynthesisDraftError(f"{action.action_id} has malformed input annotations")

    current_annotations: list[str] = []
    seen_annotations: set[str] = set()
    for annotation in annotations:
        if (
            not isinstance(annotation, str)
            or not annotation
            or annotation != annotation.strip()
            or any(char.isspace() for char in annotation)
        ):
            raise ResynthesisDraftError(f"{action.action_id} has malformed input annotations")
        if annotation in seen_annotations:
            raise ResynthesisDraftError(f"{action.action_id} has duplicate input annotations")
        current_annotations.append(annotation)
        seen_annotations.add(annotation)
    return tuple(current_annotations)


def _observed_hint_index(action: ReconciliationAction) -> dict[str, Mapping[str, Any]]:
    raw_hints = action.inputs.get("observed_statement_hints", ())
    if isinstance(raw_hints, str) or not isinstance(raw_hints, Sequence):
        raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")

    by_annotation: dict[str, Mapping[str, Any]] = {}
    for hint in raw_hints:
        if not isinstance(hint, Mapping):
            raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")
        annotation = hint.get("annotation")
        if annotation is None:
            continue
        if not isinstance(annotation, str) or not annotation or annotation != annotation.strip():
            raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")
        if annotation in by_annotation:
            raise ResynthesisDraftError(f"{action.action_id} has duplicate observed hint for {annotation}")
        by_annotation[annotation] = hint
    return by_annotation


def _context_annotation_row(
    annotation_ref: str,
    hint: Mapping[str, Any],
    *,
    paper_ref: str,
    promoted_to: str | None,
) -> dict[str, Any]:
    return {
        "annotation": annotation_ref,
        "paper": paper_ref,
        "stance": hint.get("stance"),
        "section": hint.get("section"),
        "exact": hint.get("exact"),
        "subject": hint.get("subject"),
        "object": hint.get("object"),
        "subject_concept": hint.get("subject_concept"),
        "object_concept": hint.get("object_concept"),
        "current_promoted_to": promoted_to,
    }


def build_resynthesis_context_packet(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    draft_path: str | None = None,
) -> dict[str, Any]:
    action = _live_action_for_draft(project_root, draft)
    current_annotations = _current_action_annotations(action)
    if draft.input_annotations != current_annotations:
        raise ResynthesisDraftError("input_annotations are stale")

    try:
        original_location = find_entity(project_root, draft.original_proposition)
    except (EntityCommandError, OSError) as exc:
        raise ResynthesisDraftError(str(exc)) from exc

    hints_by_annotation = _observed_hint_index(action)
    live_index = _live_annotation_index(project_root)
    input_rows: list[dict[str, Any]] = []
    for annotation_ref in current_annotations:
        hint = hints_by_annotation.get(annotation_ref)
        if hint is None:
            raise ResynthesisDraftError(f"{annotation_ref} has no observed statement hint")
        indexed = live_index.get(annotation_ref)
        if indexed is None:
            raise ResynthesisDraftError(f"{annotation_ref} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        paper_ref = _resolve_paper_ref(sidecar_path)
        if paper_ref is None:
            raise ResynthesisDraftError(f"{annotation_ref} resolves to no paper ref")
        input_rows.append(
            _context_annotation_row(
                annotation_ref,
                hint,
                paper_ref=paper_ref,
                promoted_to=promoted_to,
            )
        )

    draft_payload = draft_to_json(draft)
    validate_input = draft_path or "<draft>"
    return {
        "schema_version": RESYNTHESIS_CONTEXT_SCHEMA_VERSION,
        "source": RESYNTHESIS_CONTEXT_SOURCE,
        "draft_path": draft_path,
        "action_id": draft.action_id,
        "candidate_id": draft.candidate_id,
        "judgment_id": draft.judgment_id,
        "original_proposition": {
            "id": draft.original_proposition,
            "title": original_location.title,
            "body": original_location.body,
            "frontmatter": _selected_original_frontmatter(original_location.frontmatter),
        },
        "review": {
            "decision": action.decision,
            "confidence": action.confidence,
            "rationale": action.rationale,
        },
        "input_annotations": input_rows,
        "draft_progress": {
            "disposition": draft.disposition,
            "new_propositions": draft_payload["new_propositions"],
            "annotation_assignments": draft_payload["annotation_assignments"],
            "notes": draft.notes,
        },
        "constraints": {
            "allowed_dispositions": sorted(RESYNTHESIS_DISPOSITIONS),
            "required_assignment_annotations": list(current_annotations),
            "replacement_id_prefix": "proposition:",
            "replacement_id_policy": "canonical proposition local part; lowercase words joined by hyphens",
            "allowed_replacement_frontmatter_keys": sorted(ALLOWED_REPLACEMENT_FRONTMATTER_KEYS),
        },
        "output_contract": {
            "write": "a Half D proposition resynthesis draft JSON",
            "validate_with": f"science annotate validate-proposition-resynthesis --input {validate_input}",
            "do_not_write": ["proposition files", "annotation sidecars", "archive rows"],
        },
    }


def validate_resynthesis_draft(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    as_of: date | None = None,
) -> ResynthesisValidationReport:
    action = _live_action_for_draft(project_root, draft)
    current_annotations = _current_action_annotations(action)
    if draft.input_annotations != current_annotations:
        raise ResynthesisDraftError("input_annotations are stale")
    current_annotation_set = set(current_annotations)
    live_index = _live_annotation_index(project_root)

    replacements = {replacement.id: replacement for replacement in draft.new_propositions}
    if len(replacements) != len(draft.new_propositions):
        raise ResynthesisDraftError("replacement proposition assigned more than once")
    if draft.original_proposition in replacements:
        raise ResynthesisDraftError("original proposition cannot be a replacement")
    for replacement in draft.new_propositions:
        _replacement_local_part(project_root, replacement.id)
        _validate_replacement_frontmatter(replacement)

    seen_annotations: set[str] = set()
    expected_targets: dict[str, str] = {}
    expected_refs: dict[str, set[str]] = {
        replacement.id: set(_replacement_frontmatter_source_refs(replacement.frontmatter))
        for replacement in draft.new_propositions
    }

    moved = 0
    retained = 0
    assigned_replacement_ids: set[str] = set()
    for assignment in draft.annotation_assignments:
        if assignment.annotation in seen_annotations:
            raise ResynthesisDraftError(f"{assignment.annotation} assigned more than once")
        seen_annotations.add(assignment.annotation)

        if assignment.annotation not in current_annotation_set:
            raise ResynthesisDraftError(f"{assignment.annotation} is not a current input annotation")
        if assignment.from_proposition != draft.original_proposition:
            raise ResynthesisDraftError(f"{assignment.annotation} from_proposition must be {draft.original_proposition}")

        if assignment.to_proposition == draft.original_proposition:
            if draft.disposition != "split_partial":
                raise ResynthesisDraftError(f"{assignment.annotation} must target a draft proposition")
            retained += 1
        elif assignment.to_proposition in replacements:
            moved += 1
            assigned_replacement_ids.add(assignment.to_proposition)
        else:
            raise ResynthesisDraftError(f"{assignment.to_proposition} is not a draft proposition")

        indexed = live_index.get(assignment.annotation)
        if indexed is None:
            raise ResynthesisDraftError(f"{assignment.annotation} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        allowed_promoted = {assignment.from_proposition, assignment.to_proposition}
        if promoted_to not in allowed_promoted:
            raise ResynthesisDraftError(
                f"{assignment.annotation} promoted_to {promoted_to!r} is not from or to proposition"
            )

        expected_targets[assignment.annotation] = assignment.to_proposition
        if assignment.to_proposition in replacements:
            expected_refs[assignment.to_proposition].add(assignment.annotation)
            paper_ref = _resolve_paper_ref(sidecar_path)
            if paper_ref is None:
                raise ResynthesisDraftError(f"{assignment.annotation} resolves to no paper ref")
            expected_refs[assignment.to_proposition].add(paper_ref)

    if draft.disposition == "replace":
        if seen_annotations != current_annotation_set:
            raise ResynthesisDraftError("replace must assign every input annotation")
        if retained:
            raise ResynthesisDraftError("replace assignments must target draft propositions")
    elif draft.disposition == "split_partial":
        if seen_annotations != current_annotation_set:
            raise ResynthesisDraftError("split_partial must assign every input annotation")
        if moved == 0:
            raise ResynthesisDraftError("split_partial must move at least one annotation to a new proposition")
        if retained == 0:
            raise ResynthesisDraftError(
                "split_partial must retain at least one annotation on original proposition; use replace if all move"
            )

    if set(replacements) != assigned_replacement_ids:
        raise ResynthesisDraftError("replacement propositions must match assigned annotation targets")

    for proposition, refs in expected_refs.items():
        if not refs:
            raise ResynthesisDraftError(f"{proposition} replacement proposition has no source refs")

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
        action=action,
    )


def _replacement_path(project_root: Path, proposition_id: str) -> Path:
    local_part = _replacement_local_part(project_root, proposition_id)
    policy = resolve_path_policy("proposition", project_root=project_root)
    return project_root / policy.root / f"{local_part}.md"


def _merged_source_refs(draft_refs: Sequence[str], expected_refs: Sequence[str]) -> list[str]:
    merged: list[str] = []
    for ref in (*draft_refs, *expected_refs):
        if ref not in merged:
            merged.append(ref)
    return merged


def render_replacement_proposition(
    project_root: Path,
    replacement: NewPropositionDraft,
    expected_source_refs: Sequence[str],
    *,
    as_of: date | None = None,
) -> RenderedReplacement:
    if isinstance(expected_source_refs, str):
        raise ResynthesisDraftError("expected_source_refs must be a list")
    _validate_replacement_frontmatter(replacement)
    today = as_of or date.today()
    path = _replacement_path(project_root, replacement.id)
    draft_source_refs = _replacement_frontmatter_source_refs(replacement.frontmatter)

    frontmatter: dict[str, Any] = dict(replacement.frontmatter)
    frontmatter.update(
        {
            "id": replacement.id,
            "type": "proposition",
            "title": replacement.title,
            "status": "active",
            "created": today,
            "updated": today,
            "source_refs": _merged_source_refs(draft_source_refs, expected_source_refs),
        }
    )

    body = f"\n# {replacement.title}\n\n{replacement.body.rstrip()}\n"
    if path.exists():
        existing_frontmatter, _existing_body = parse_markdown_entity_file(path)
        if "created" in existing_frontmatter:
            frontmatter["created"] = existing_frontmatter["created"]
        if "updated" in existing_frontmatter:
            frontmatter["updated"] = existing_frontmatter["updated"]

    try:
        PropositionEntity.model_validate(frontmatter)
    except ValueError as exc:
        raise ResynthesisDraftError(str(exc)) from exc

    text = _render_markdown(frontmatter, body)
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        if existing_text == text:
            return RenderedReplacement(proposition=replacement.id, path=path, text=text, changed=False)
        raise ResynthesisDraftError("existing replacement proposition differs from draft")

    return RenderedReplacement(proposition=replacement.id, path=path, text=text, changed=True)

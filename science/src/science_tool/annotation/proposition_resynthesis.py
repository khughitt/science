from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    ReconciliationValidationError,
    build_reconciliation_report,
)
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
)

RESYNTHESIS_SCHEMA_VERSION = 1
RESYNTHESIS_SOURCE_RE = re.compile(r"^llm-review:[A-Za-z0-9._-]+:proposition-resynthesis-v1$")
DEFAULT_RESYNTHESIS_SOURCE_MODEL = "codex-gpt-5"
RESYNTHESIS_DISPOSITIONS = frozenset({"replace", "split_partial"})


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
    new_propositions: tuple[NewPropositionDraft, ...] = ()
    annotation_assignments: tuple[AnnotationAssignment, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""


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
        new_propositions=(),
        annotation_assignments=(),
        context={
            "rationale": action.rationale,
            "observed_statement_hints": tuple(action.inputs.get("observed_statement_hints", ())),
            "input_annotations": tuple(action.inputs.get("annotations", ())),
            "papers": tuple(action.inputs.get("papers", ())),
        },
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


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

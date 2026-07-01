from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    FactorizationCandidate,
    ReconciliationFault,
    ReconciliationReport,
    ResolvedReviewJudgment,
    resolve_review_doc,
)


ActionStatus = Literal["ready", "blocked", "advisory"]
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReviewedReconciliationInput:
    path: str
    doc: Mapping[str, Any]


@dataclass(frozen=True)
class ReconciliationAction:
    action_id: str
    kind: str
    status: ActionStatus
    decision: str
    candidate_id: str
    judgment_id: str
    confidence: str
    rationale: str
    source_review: str
    review_source: str
    proposition: str | None = None
    canonical_proposition: str | None = None
    members: tuple[str, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    suggested_operations: tuple[Mapping[str, Any], ...] = ()
    preconditions: tuple[Mapping[str, Any], ...] = ()
    blockers: tuple[Mapping[str, Any], ...] = ()
    writes: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ReconciliationActionPlan:
    schema_version: int
    source_reviews: tuple[str, ...]
    actions: tuple[ReconciliationAction, ...]
    errors: tuple[Mapping[str, Any], ...] = ()


def reconciliation_action_id(
    action_kind: str,
    judgment_ref: str,
    primary_ref: str,
    secondary_refs: Sequence[str] = (),
) -> str:
    parts = [action_kind, judgment_ref, primary_ref, *sorted(secondary_refs)]
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()
    return f"reconcile-action:{digest}"


def _fault_to_error(fault: ReconciliationFault) -> dict[str, Any]:
    return {
        "reason": fault.reason,
        "detail": fault.detail,
        "members": list(fault.members),
    }


def _factorization_inputs(candidate: FactorizationCandidate) -> dict[str, Any]:
    hints = tuple(dict(hint) for hint in candidate.observed_statement_hints)
    annotations = tuple(
        sorted(
            str(hint["annotation"])
            for hint in candidate.observed_statement_hints
            if hint.get("annotation")
        )
    )
    return {
        "annotations": annotations,
        "papers": tuple(candidate.papers),
        "disagreement": tuple(candidate.disagreement),
        "observed_statement_hints": hints,
    }


def _factorization_suggestions(decision: str) -> tuple[Mapping[str, Any], ...]:
    if decision == "factorization_needs_resynthesis":
        return (
            {
                "kind": "draft_proposition",
                "detail": "Draft one or more narrower proposition records from the observed hints.",
            },
            {
                "kind": "review_factorization",
                "detail": "Confirm source annotations align to the revised proposition scope.",
            },
        )
    if decision == "stance_review_needed":
        return (
            {
                "kind": "review_annotation_stance",
                "detail": "Inspect assertion stances before changing proposition factorization.",
            },
        )
    if decision == "insufficient_hints":
        return (
            {
                "kind": "cleanup_factorization_hints",
                "detail": "Add missing statement hints before planning proposition changes.",
            },
        )
    if decision == "needs_human":
        return (
            {
                "kind": "request_human_review",
                "detail": "Route this reconciliation judgment to a human reviewer.",
            },
        )
    return (
        {
            "kind": "record_decision",
            "detail": "Record the reconciliation decision without automated writes.",
        },
    )


def _action_from_factorization(
    source_path: str,
    resolved: ResolvedReviewJudgment,
) -> ReconciliationAction:
    candidate = resolved.candidate
    if not isinstance(candidate, FactorizationCandidate):
        raise TypeError("factorization action requires FactorizationCandidate")

    judgment = resolved.judgment
    decision = str(judgment["decision"])
    rationale = str(judgment["rationale"])
    action_kind: str
    status: ActionStatus
    if decision == "factorization_needs_resynthesis":
        action_kind = "resynthesize_proposition"
        status = "ready"
    elif decision == "stance_review_needed":
        action_kind = "review_annotation_stance"
        status = "blocked"
    elif decision == "insufficient_hints":
        action_kind = "cleanup_factorization_hints"
        status = "advisory"
    elif decision == "needs_human":
        action_kind = "needs_human_review"
        status = "blocked"
    else:
        action_kind = "record_reconciliation_decision"
        status = "advisory"

    blockers: tuple[Mapping[str, Any], ...] = ()
    if status == "blocked":
        blockers = ({"reason": decision, "detail": rationale},)

    proposition = candidate.proposition
    judgment_id = str(judgment["judgment_id"])
    return ReconciliationAction(
        action_id=reconciliation_action_id(action_kind, judgment_id, proposition),
        kind=action_kind,
        status=status,
        decision=decision,
        candidate_id=str(judgment["candidate_id"]),
        judgment_id=judgment_id,
        confidence=str(judgment["confidence"]),
        rationale=rationale,
        source_review=source_path,
        review_source=resolved.review_source,
        proposition=proposition,
        inputs=_factorization_inputs(candidate),
        suggested_operations=_factorization_suggestions(decision),
        blockers=blockers,
        writes=(),
    )


def _action_from_resolved(
    source_path: str,
    resolved: ResolvedReviewJudgment,
) -> ReconciliationAction:
    lane = resolved.judgment["lane"]
    if lane == LANE_FACTORIZATION:
        return _action_from_factorization(source_path, resolved)
    if lane == LANE_SAME_CLAIM:
        raise NotImplementedError("same-claim action planning is added in Task 3")
    raise ValueError(f"unsupported reconciliation lane: {lane!r}")


def build_reconciliation_action_plan(
    report: ReconciliationReport,
    reviews: Sequence[ReviewedReconciliationInput],
) -> ReconciliationActionPlan:
    actions: list[ReconciliationAction] = []
    for review in reviews:
        resolved_doc = resolve_review_doc(review.doc, report)
        for resolved in resolved_doc.judgments:
            actions.append(_action_from_resolved(review.path, resolved))

    return ReconciliationActionPlan(
        schema_version=SCHEMA_VERSION,
        source_reviews=tuple(review.path for review in reviews),
        actions=tuple(sorted(actions, key=lambda action: action.action_id)),
        errors=tuple(_fault_to_error(fault) for fault in report.faults),
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _action_to_json(action: ReconciliationAction) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action_id": action.action_id,
        "kind": action.kind,
        "status": action.status,
        "decision": action.decision,
        "candidate_id": action.candidate_id,
        "judgment_id": action.judgment_id,
        "confidence": action.confidence,
        "rationale": action.rationale,
        "source_review": action.source_review,
        "review_source": action.review_source,
        "inputs": _jsonable(action.inputs),
        "suggested_operations": _jsonable(action.suggested_operations),
        "preconditions": _jsonable(action.preconditions),
        "blockers": _jsonable(action.blockers),
        "writes": _jsonable(action.writes),
    }
    if action.proposition is not None:
        payload["proposition"] = action.proposition
    if action.canonical_proposition is not None:
        payload["canonical_proposition"] = action.canonical_proposition
    if action.members:
        payload["members"] = list(action.members)
    return payload


def action_plan_to_json(plan: ReconciliationActionPlan) -> dict[str, Any]:
    ready_actions = sum(1 for action in plan.actions if action.status == "ready")
    blocked_actions = sum(1 for action in plan.actions if action.status == "blocked")
    advisory_actions = sum(1 for action in plan.actions if action.status == "advisory")
    return {
        "schema_version": plan.schema_version,
        "source_reviews": list(plan.source_reviews),
        "summary": {
            "ready_actions": ready_actions,
            "blocked_actions": blocked_actions,
            "advisory_actions": advisory_actions,
            "errors": len(plan.errors),
        },
        "actions": [_action_to_json(action) for action in plan.actions],
        "errors": [_jsonable(error) for error in plan.errors],
    }

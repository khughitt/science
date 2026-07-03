from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    DECISION_ACCEPTED_SPARSE_HINTS,
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    FactorizationCandidate,
    ReconciliationFault,
    ReconciliationReport,
    ReconciliationValidationError,
    ResolvedReviewJudgment,
    SameClaimCandidate,
    factorization_assertion_fingerprint,
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
    if decision == DECISION_ACCEPTED_SPARSE_HINTS:
        return (
            {
                "kind": "record_sparse_hint_closure",
                "detail": "Record reviewed closure for the current sparse-hint candidate.",
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


def _snapshot(report: ReconciliationReport, ref: str):
    try:
        return report.proposition_snapshots[ref]
    except KeyError as exc:
        raise ValueError(f"missing proposition snapshot for {ref}") from exc


def _review_text(judgment: Mapping[str, Any], field: str) -> str:
    return str(judgment[field]).strip()


def _canonicalization_inputs(
    canonical: str,
    members: Sequence[str],
    report: ReconciliationReport,
) -> Mapping[str, Any]:
    duplicates = tuple(ref for ref in members if ref != canonical)
    source_ref_moves: list[Mapping[str, Any]] = []
    sidecar_backlink_rewrites: list[Mapping[str, Any]] = []
    for duplicate in duplicates:
        duplicate_snapshot = _snapshot(report, duplicate)
        source_ref_moves.append(
            {
                "from": duplicate,
                "to": canonical,
                "source_refs": tuple(sorted(duplicate_snapshot.source_refs)),
            }
        )
        sidecar_backlink_rewrites.append(
            {
                "from": duplicate,
                "to": canonical,
                "annotation_refs": tuple(sorted(duplicate_snapshot.annotation_refs)),
            }
        )
    return {
        "source_ref_moves": tuple(source_ref_moves),
        "sidecar_backlink_rewrites": tuple(sidecar_backlink_rewrites),
        "archive_candidates": duplicates,
    }


def _same_claim_suggestions() -> tuple[Mapping[str, Any], ...]:
    return (
        {
            "kind": "move_source_refs_to_canonical",
            "detail": "Move duplicate proposition source references onto the canonical proposition.",
        },
        {
            "kind": "rewrite_sidecar_promoted_to_backlinks",
            "detail": "Rewrite sidecar promoted_to backlinks from duplicates to the canonical proposition.",
        },
        {
            "kind": "archive_duplicate_propositions",
            "detail": "Archive duplicate proposition records after backlinks are rewritten.",
        },
    )


def _action_from_same_claim(
    source_path: str,
    resolved: ResolvedReviewJudgment,
    report: ReconciliationReport,
) -> ReconciliationAction:
    candidate = resolved.candidate
    if not isinstance(candidate, SameClaimCandidate):
        raise TypeError("same-claim action requires SameClaimCandidate")

    judgment = resolved.judgment
    decision = _review_text(judgment, "decision")
    rationale = _review_text(judgment, "rationale")
    judgment_id = _review_text(judgment, "judgment_id")
    candidate_id = str(candidate.candidate_id).strip()
    confidence = _review_text(judgment, "confidence")
    members = tuple(sorted(str(member) for member in judgment["members"]))

    if decision == "same_claim":
        canonical = _review_text(judgment, "canonical_proposition")
        secondary_refs = tuple(ref for ref in members if ref != canonical)
        action_kind = "canonicalize_propositions"
        return ReconciliationAction(
            action_id=reconciliation_action_id(
                action_kind,
                judgment_id,
                canonical,
                secondary_refs,
            ),
            kind=action_kind,
            status="ready",
            decision=decision,
            candidate_id=candidate_id,
            judgment_id=judgment_id,
            confidence=confidence,
            rationale=rationale,
            source_review=source_path,
            review_source=resolved.review_source,
            canonical_proposition=canonical,
            members=members,
            inputs=_canonicalization_inputs(canonical, members, report),
            suggested_operations=_same_claim_suggestions(),
            preconditions=(
                {
                    "kind": "review_validation",
                    "detail": "Review document validates against the current reconciliation report.",
                },
                {
                    "kind": "current_snapshots",
                    "detail": "Current proposition snapshots exist for reviewed same-claim members.",
                },
            ),
            blockers=(),
            writes=(),
        )

    if decision == "needs_human":
        action_kind = "needs_human_review"
        return ReconciliationAction(
            action_id=reconciliation_action_id(
                action_kind,
                judgment_id,
                candidate.candidate_id,
                members,
            ),
            kind=action_kind,
            status="blocked",
            decision=decision,
            candidate_id=candidate_id,
            judgment_id=judgment_id,
            confidence=confidence,
            rationale=rationale,
            source_review=source_path,
            review_source=resolved.review_source,
            members=members,
            inputs={"members": members, "flags": tuple(candidate.flags)},
            suggested_operations=(
                {
                    "kind": "request_human_review",
                    "detail": "Route this same-claim judgment to a human reviewer.",
                },
            ),
            blockers=({"reason": decision, "detail": rationale},),
            writes=(),
        )

    action_kind = "record_reconciliation_decision"
    return ReconciliationAction(
        action_id=reconciliation_action_id(
            action_kind,
            judgment_id,
            candidate.candidate_id,
            members,
        ),
        kind=action_kind,
        status="advisory",
        decision=decision,
        candidate_id=candidate_id,
        judgment_id=judgment_id,
        confidence=confidence,
        rationale=rationale,
        source_review=source_path,
        review_source=resolved.review_source,
        members=members,
        inputs={"members": members, "flags": tuple(candidate.flags)},
        suggested_operations=(
            {
                "kind": "record_non_merge_decision",
                "detail": "Record the reviewed same-claim decision without canonicalization writes.",
            },
        ),
        blockers=(),
        writes=(),
    )


def _action_from_factorization(
    source_path: str,
    resolved: ResolvedReviewJudgment,
) -> ReconciliationAction:
    candidate = resolved.candidate
    if not isinstance(candidate, FactorizationCandidate):
        raise TypeError("factorization action requires FactorizationCandidate")

    judgment = resolved.judgment
    decision = _review_text(judgment, "decision")
    rationale = _review_text(judgment, "rationale")
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
    elif decision == DECISION_ACCEPTED_SPARSE_HINTS:
        action_kind = "record_reconciliation_decision"
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
    judgment_id = _review_text(judgment, "judgment_id")
    inputs = _factorization_inputs(candidate)
    if decision == DECISION_ACCEPTED_SPARSE_HINTS:
        inputs = {
            **inputs,
            "assertion_fingerprint": factorization_assertion_fingerprint(candidate),
        }
    return ReconciliationAction(
        action_id=reconciliation_action_id(action_kind, judgment_id, proposition),
        kind=action_kind,
        status=status,
        decision=decision,
        candidate_id=_review_text(judgment, "candidate_id"),
        judgment_id=judgment_id,
        confidence=_review_text(judgment, "confidence"),
        rationale=rationale,
        source_review=source_path,
        review_source=resolved.review_source,
        proposition=proposition,
        inputs=inputs,
        suggested_operations=_factorization_suggestions(decision),
        blockers=blockers,
        writes=(),
    )


def _action_from_resolved(
    source_path: str,
    resolved: ResolvedReviewJudgment,
    report: ReconciliationReport,
) -> ReconciliationAction:
    lane = _review_text(resolved.judgment, "lane")
    if lane == LANE_FACTORIZATION:
        return _action_from_factorization(source_path, resolved)
    if lane == LANE_SAME_CLAIM:
        return _action_from_same_claim(source_path, resolved, report)
    raise ValueError(f"unsupported reconciliation lane: {lane!r}")


def _with_blocker(
    action: ReconciliationAction,
    reason: str,
    detail: str,
) -> ReconciliationAction:
    return replace(
        action,
        status="blocked",
        blockers=(*action.blockers, {"reason": reason, "detail": detail}),
    )


def _apply_incomplete_review_blockers(
    actions: Sequence[ReconciliationAction],
    incomplete: Sequence[Mapping[str, Any]],
) -> tuple[ReconciliationAction, ...]:
    missing_by_candidate = {
        str(item["candidate_id"]).strip(): tuple(str(ref) for ref in item["missing"])
        for item in incomplete
    }
    blocked: list[ReconciliationAction] = []
    for action in actions:
        missing = missing_by_candidate.get(action.candidate_id)
        if missing and action.kind == "canonicalize_propositions":
            blocked.append(
                _with_blocker(
                    action,
                    "review_incomplete",
                    f"candidate has unreviewed members: {', '.join(missing)}",
                )
            )
        else:
            blocked.append(action)
    return tuple(blocked)


def _action_target_refs(action: ReconciliationAction) -> tuple[str, ...]:
    if action.members:
        return action.members
    if action.proposition is not None:
        return (action.proposition,)
    if action.canonical_proposition is not None:
        return (action.canonical_proposition,)
    return ()


def _apply_cross_action_conflicts(
    actions: Sequence[ReconciliationAction],
) -> tuple[ReconciliationAction, ...]:
    action_id_counts: dict[str, int] = {}
    for action in actions:
        action_id_counts[action.action_id] = action_id_counts.get(action.action_id, 0) + 1
    duplicate_action_ids = {
        action_id for action_id, count in action_id_counts.items() if count > 1
    }

    by_ref: dict[str, list[ReconciliationAction]] = {}
    for action in actions:
        for ref in _action_target_refs(action):
            by_ref.setdefault(ref, []).append(action)

    conflicted: dict[str, set[str]] = {}
    for ref_actions in by_ref.values():
        action_ids = sorted({action.action_id for action in ref_actions})
        if len(action_ids) < 2:
            continue
        for action_id in action_ids:
            conflicted.setdefault(action_id, set()).update(
                other for other in action_ids if other != action_id
            )

    out: list[ReconciliationAction] = []
    for action in actions:
        if action.action_id in duplicate_action_ids:
            out.append(
                _with_blocker(
                    action,
                    reason="action_conflict",
                    detail="duplicate action produced by multiple reviewed inputs",
                )
            )
            continue
        other_ids = sorted(conflicted.get(action.action_id, set()))
        if not other_ids:
            out.append(action)
            continue
        out.append(
            _with_blocker(
                action,
                reason="action_conflict",
                detail=f"conflicts with actions: {', '.join(other_ids)}",
            )
        )
    return tuple(out)


def build_reconciliation_action_plan(
    report: ReconciliationReport,
    reviews: Sequence[ReviewedReconciliationInput],
) -> ReconciliationActionPlan:
    actions: list[ReconciliationAction] = []
    incomplete: list[Mapping[str, Any]] = []
    for review in reviews:
        try:
            resolved_doc = resolve_review_doc(review.doc, report)
        except ReconciliationValidationError as exc:
            raise ReconciliationValidationError(f"{review.path}: {exc}") from exc
        if not resolved_doc.judgments:
            raise ValueError(f"{review.path} produced no judgments")
        incomplete.extend(resolved_doc.validation["review_incomplete"])
        for resolved in resolved_doc.judgments:
            actions.append(_action_from_resolved(review.path, resolved, report))

    blocked_for_incomplete = _apply_incomplete_review_blockers(actions, incomplete)
    blocked_for_conflicts = _apply_cross_action_conflicts(blocked_for_incomplete)
    return ReconciliationActionPlan(
        schema_version=SCHEMA_VERSION,
        source_reviews=tuple(review.path for review in reviews),
        actions=tuple(
            sorted(
                blocked_for_conflicts,
                key=lambda action: action.action_id,
            )
        ),
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

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    judgment_id,
)


SCHEMA_VERSION = 1
DEFAULT_DECISION_LOG = "results/proposition-reconciliation/decisions.jsonl"

DecisionLane = Literal["same_claim", "factorization_disagreement"]

_ACTION_KIND = "record_reconciliation_decision"
_LANE_A_DECISIONS = frozenset({"related_but_distinct", "conflict_or_negation"})
_LANE_B_DECISIONS = frozenset({"split_possible"})


class DecisionRecordError(ValueError):
    pass


@dataclass(frozen=True)
class DecisionRecord:
    schema_version: int
    decision_id: str
    judgment_id: str
    candidate_id: str
    lane: DecisionLane
    decision: str
    members: tuple[str, ...]
    proposition: str | None
    confidence: str
    rationale: str
    source_review: str
    review_source: str
    recorded_at: str


def decision_record_id(
    lane: str,
    decision: str,
    judgment_ref: str,
    primary_ref: str,
    refs: Sequence[str] = (),
) -> str:
    digest = hashlib.sha256(
        "\0".join([lane, decision, judgment_ref, primary_ref, *sorted(refs)]).encode()
    ).hexdigest()
    return f"reconcile-decision:{digest}"


def record_from_action_payload(
    action: Mapping[str, Any],
    *,
    recorded_at: str,
) -> DecisionRecord:
    if action.get("kind") != _ACTION_KIND:
        raise DecisionRecordError(f"action kind must be {_ACTION_KIND!r}")
    if action.get("status") != "advisory":
        raise DecisionRecordError("action status must be 'advisory'")
    if action.get("blockers"):
        raise DecisionRecordError("advisory action must not have blockers")

    recorded = _required_str(recorded_at, "recorded_at")
    decision = _required_text(action, "decision")
    candidate_id = _required_text(action, "candidate_id")
    judgment_ref = _required_text(action, "judgment_id")

    if decision in _LANE_A_DECISIONS:
        lane: DecisionLane = LANE_SAME_CLAIM
        members = _members(action)
        proposition = None
        expected_judgment = judgment_id(lane, decision, members)
        record_refs = members
    elif decision in _LANE_B_DECISIONS:
        lane = LANE_FACTORIZATION
        members = ()
        proposition = _required_text(action, "proposition")
        expected_judgment = judgment_id(lane, decision, [proposition])
        record_refs = (proposition,)
    else:
        raise DecisionRecordError(f"unsupported reconciliation decision: {decision!r}")

    if judgment_ref != expected_judgment:
        raise DecisionRecordError("action judgment_id does not match decision inputs")

    return DecisionRecord(
        schema_version=SCHEMA_VERSION,
        decision_id=decision_record_id(
            lane,
            decision,
            judgment_ref,
            candidate_id,
            record_refs,
        ),
        judgment_id=judgment_ref,
        candidate_id=candidate_id,
        lane=lane,
        decision=decision,
        members=members,
        proposition=proposition,
        confidence=_required_text(action, "confidence"),
        rationale=_required_text(action, "rationale"),
        source_review=_required_text(action, "source_review"),
        review_source=_required_text(action, "review_source"),
        recorded_at=recorded,
    )


def _required_text(action: Mapping[str, Any], field_name: str) -> str:
    return _required_str(action.get(field_name), field_name)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionRecordError(f"{field_name} must be a non-empty string")
    return value.strip()


def _members(action: Mapping[str, Any]) -> tuple[str, ...]:
    members = action.get("members")
    if not isinstance(members, Sequence) or isinstance(members, str):
        raise DecisionRecordError("members must be a sequence of strings")
    if not all(isinstance(member, str) and member.strip() for member in members):
        raise DecisionRecordError("members must be non-empty strings")
    refs = tuple(sorted({member.strip() for member in members}))
    if not refs:
        raise DecisionRecordError("members must not be empty")
    return refs

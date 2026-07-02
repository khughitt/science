from __future__ import annotations

import pytest

from science_tool.annotation.proposition_reconciliation import judgment_id
from science_tool.annotation.proposition_reconciliation_decisions import (
    DecisionRecordError,
    decision_record_id,
    record_from_action_payload,
)


def _same_claim_advisory_action() -> dict:
    members = ["proposition:b", "proposition:a"]
    return {
        "action_id": "reconcile-action:abc",
        "kind": "record_reconciliation_decision",
        "status": "advisory",
        "decision": "related_but_distinct",
        "candidate_id": "reconcile:same-claim/candidate",
        "judgment_id": judgment_id("same_claim", "related_but_distinct", members),
        "confidence": "high",
        "rationale": "Same paper context, distinct claim scope.",
        "source_review": "results/proposition-reconciliation/review.json",
        "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "members": members,
        "inputs": {"members": tuple(members), "flags": ()},
        "suggested_operations": [],
        "preconditions": [],
        "blockers": [],
        "writes": [],
    }


def test_decision_record_id_is_stable_for_sorted_refs():
    left = decision_record_id(
        "same_claim",
        "related_but_distinct",
        "reconcile:judgment/j",
        "reconcile:same-claim/candidate",
        ["proposition:b", "proposition:a"],
    )
    right = decision_record_id(
        "same_claim",
        "related_but_distinct",
        "reconcile:judgment/j",
        "reconcile:same-claim/candidate",
        ["proposition:a", "proposition:b"],
    )
    assert left == right
    assert left.startswith("reconcile-decision:")
    assert len(left.removeprefix("reconcile-decision:")) == 64


def test_record_from_same_claim_advisory_action_payload():
    action = _same_claim_advisory_action()
    record = record_from_action_payload(action, recorded_at="2026-07-02")

    assert record.schema_version == 1
    assert record.lane == "same_claim"
    assert record.decision == "related_but_distinct"
    assert record.members == ("proposition:a", "proposition:b")
    assert record.proposition is None
    assert record.candidate_id == action["candidate_id"]
    assert record.judgment_id == action["judgment_id"]
    assert record.confidence == action["confidence"]
    assert record.rationale == action["rationale"]
    assert record.source_review == action["source_review"]
    assert record.review_source == action["review_source"]
    assert record.recorded_at == "2026-07-02"
    assert record.decision_id == decision_record_id(
        "same_claim",
        "related_but_distinct",
        record.judgment_id,
        record.candidate_id,
        record.members,
    )


def test_record_from_same_claim_conflict_or_negation_action_payload():
    action = _same_claim_advisory_action()
    action["decision"] = "conflict_or_negation"
    action["judgment_id"] = judgment_id(
        "same_claim",
        "conflict_or_negation",
        action["members"],
    )

    record = record_from_action_payload(action, recorded_at="2026-07-02")

    assert record.lane == "same_claim"
    assert record.decision == "conflict_or_negation"
    assert record.members == ("proposition:a", "proposition:b")


def test_record_from_factorization_split_possible_action_payload():
    action = {
        "action_id": "reconcile-action:def",
        "kind": "record_reconciliation_decision",
        "status": "advisory",
        "decision": "split_possible",
        "candidate_id": "reconcile:factorization/candidate",
        "judgment_id": judgment_id(
            "factorization_disagreement",
            "split_possible",
            ["proposition:broad"],
        ),
        "confidence": "medium",
        "rationale": "The proposition may split, but not enough for resynthesis.",
        "source_review": "results/proposition-reconciliation/review.json",
        "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "proposition": "proposition:broad",
        "inputs": {},
        "suggested_operations": [],
        "preconditions": [],
        "blockers": [],
        "writes": [],
    }

    record = record_from_action_payload(action, recorded_at="2026-07-02")

    assert record.schema_version == 1
    assert record.lane == "factorization_disagreement"
    assert record.decision == "split_possible"
    assert record.proposition == "proposition:broad"
    assert record.members == ()
    assert record.recorded_at == "2026-07-02"
    assert record.candidate_id == action["candidate_id"]
    assert record.judgment_id == action["judgment_id"]
    assert record.confidence == action["confidence"]
    assert record.rationale == action["rationale"]
    assert record.source_review == action["source_review"]
    assert record.review_source == action["review_source"]
    assert record.decision_id == decision_record_id(
        "factorization_disagreement",
        "split_possible",
        record.judgment_id,
        record.candidate_id,
        ["proposition:broad"],
    )


def test_record_from_action_rejects_non_decision_action():
    action = _same_claim_advisory_action()
    action["kind"] = "cleanup_factorization_hints"

    try:
        record_from_action_payload(action, recorded_at="2026-07-02")
    except DecisionRecordError as exc:
        assert "record_reconciliation_decision" in str(exc)
    else:
        raise AssertionError("expected DecisionRecordError")


def test_record_from_action_rejects_non_advisory_status():
    action = _same_claim_advisory_action()
    action["status"] = "accepted"

    with pytest.raises(DecisionRecordError, match="advisory"):
        record_from_action_payload(action, recorded_at="2026-07-02")


def test_record_from_action_rejects_advisory_action_with_blockers():
    action = _same_claim_advisory_action()
    action["blockers"] = ["human review required"]

    with pytest.raises(DecisionRecordError, match="advisory action.*blockers"):
        record_from_action_payload(action, recorded_at="2026-07-02")


def test_record_from_action_rejects_mismatched_judgment_id():
    action = _same_claim_advisory_action()
    action["judgment_id"] = judgment_id(
        "same_claim",
        "conflict_or_negation",
        action["members"],
    )

    with pytest.raises(DecisionRecordError, match="judgment_id"):
        record_from_action_payload(action, recorded_at="2026-07-02")


def test_record_from_action_rejects_empty_recorded_at():
    action = _same_claim_advisory_action()

    with pytest.raises(DecisionRecordError, match="recorded_at"):
        record_from_action_payload(action, recorded_at=" ")

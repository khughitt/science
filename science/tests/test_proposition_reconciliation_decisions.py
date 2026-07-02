from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    ReconciliationReport,
    SameClaimCandidate,
    candidate_id,
    judgment_id,
)
from science_tool.annotation.proposition_reconciliation_decisions import (
    DecisionRecord,
    DecisionRecordError,
    append_decision_records,
    decision_record_from_json,
    decision_record_id,
    decision_record_to_json,
    evaluate_decision_records,
    load_decision_records,
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


def _same_candidate(refs=("proposition:a", "proposition:b")) -> SameClaimCandidate:
    refs = tuple(sorted(refs))
    return SameClaimCandidate(
        candidate_id=candidate_id("same_claim", refs),
        propositions=refs,
        priority="high",
        splittable=len(refs) > 2,
        flags=(),
        signals={},
        explanation=(),
        pair_edges=frozenset({(refs[0], refs[1])}),
    )


def _report_with_same_candidate(candidate: SameClaimCandidate) -> ReconciliationReport:
    return ReconciliationReport(same_claim_candidates=(candidate,))


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


def test_jsonl_load_reports_line_number_for_invalid_json(tmp_path: Path):
    path = tmp_path / "decisions.jsonl"
    path.write_text('{"schema_version": 1}\nnot-json\n', encoding="utf-8")

    with pytest.raises(DecisionRecordError, match="line 2"):
        load_decision_records(path)


def test_jsonl_load_reports_line_number_for_invalid_record(tmp_path: Path):
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")
    payload = decision_record_to_json(record)
    payload["decision_id"] = "reconcile-decision:wrong"
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(DecisionRecordError, match="line 1"):
        load_decision_records(path)


def test_jsonl_load_rejects_bool_schema_version(tmp_path: Path):
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")
    payload = decision_record_to_json(record)
    payload["schema_version"] = True
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(DecisionRecordError, match=r"line 1: schema_version"):
        load_decision_records(path)


def test_load_decision_records_returns_empty_tuple_for_missing_log(tmp_path: Path):
    assert load_decision_records(tmp_path / "missing" / "decisions.jsonl") == ()


def test_decision_record_from_json_accepts_supported_lane():
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")

    parsed = decision_record_from_json(decision_record_to_json(record))

    assert parsed == record
    assert parsed.lane == "same_claim"


def test_append_decision_records_is_idempotent(tmp_path: Path):
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")
    path = tmp_path / "results" / "proposition-reconciliation" / "decisions.jsonl"

    assert decision_record_to_json(record)["decision_id"] == record.decision_id

    first = append_decision_records(path, [record])
    second = append_decision_records(path, [record])

    assert first.appended == (record.decision_id,)
    assert second.already_recorded == (record.decision_id,)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_append_decision_records_writes_sorted_records_with_sorted_json_keys(tmp_path: Path):
    related_action = _same_claim_advisory_action()
    conflict_action = _same_claim_advisory_action()
    conflict_action["decision"] = "conflict_or_negation"
    conflict_action["judgment_id"] = judgment_id(
        "same_claim",
        "conflict_or_negation",
        conflict_action["members"],
    )
    related = record_from_action_payload(related_action, recorded_at="2026-07-02")
    conflict = record_from_action_payload(conflict_action, recorded_at="2026-07-02")
    path = tmp_path / "decisions.jsonl"

    result = append_decision_records(path, [related, conflict])

    expected_order = tuple(sorted([related.decision_id, conflict.decision_id]))
    assert result.appended == expected_order
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line.split('"decision_id": "', maxsplit=1)[1].split('"', maxsplit=1)[0] for line in lines] == list(
        expected_order
    )
    assert all(line.startswith('{"candidate_id":') for line in lines)


def test_decision_record_to_json_rejects_malformed_primitive_field_with_record_error():
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")
    malformed = DecisionRecord(
        schema_version=record.schema_version,
        decision_id=record.decision_id,
        judgment_id=record.judgment_id,
        candidate_id=123,  # type: ignore[arg-type]
        lane=record.lane,
        decision=record.decision,
        members=record.members,
        proposition=record.proposition,
        confidence=record.confidence,
        rationale=record.rationale,
        source_review=record.source_review,
        review_source=record.review_source,
        recorded_at=record.recorded_at,
    )

    with pytest.raises(DecisionRecordError, match="candidate_id"):
        decision_record_to_json(malformed)


def test_evaluate_current_same_claim_record_suppresses_full_candidate():
    candidate = _same_candidate()
    action = _same_claim_advisory_action()
    action["candidate_id"] = candidate.candidate_id
    action["judgment_id"] = judgment_id("same_claim", "related_but_distinct", list(candidate.propositions))
    action["members"] = list(candidate.propositions)
    record = record_from_action_payload(action, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records([record], _report_with_same_candidate(candidate))

    assert [item.record.decision_id for item in evaluation.active] == [record.decision_id]
    assert evaluation.suppressed_same_claim_candidate_ids == frozenset({candidate.candidate_id})
    assert not evaluation.stale


def test_evaluate_conflicting_current_same_claim_decisions_have_no_active_or_suppression():
    candidate = _same_candidate()
    related_action = _same_claim_advisory_action()
    related_action["candidate_id"] = candidate.candidate_id
    related_action["judgment_id"] = judgment_id(
        "same_claim",
        "related_but_distinct",
        list(candidate.propositions),
    )
    related_action["members"] = list(candidate.propositions)
    conflict_action = _same_claim_advisory_action()
    conflict_action["decision"] = "conflict_or_negation"
    conflict_action["candidate_id"] = candidate.candidate_id
    conflict_action["judgment_id"] = judgment_id(
        "same_claim",
        "conflict_or_negation",
        list(candidate.propositions),
    )
    conflict_action["members"] = list(candidate.propositions)
    related = record_from_action_payload(related_action, recorded_at="2026-07-02")
    conflict = record_from_action_payload(conflict_action, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records(
        [related, conflict],
        _report_with_same_candidate(candidate),
    )

    assert len(evaluation.conflicts) == 1
    assert evaluation.conflicts[0].scope == ("same_claim", candidate.propositions)
    assert evaluation.conflicts[0].decision_ids == tuple(sorted([related.decision_id, conflict.decision_id]))
    assert evaluation.conflicts[0].decisions == ("conflict_or_negation", "related_but_distinct")
    assert evaluation.active == ()
    assert evaluation.suppressed_same_claim_candidate_ids == frozenset()


def test_evaluate_duplicate_records_reports_decision_id_once():
    candidate = _same_candidate()
    action = _same_claim_advisory_action()
    action["candidate_id"] = candidate.candidate_id
    action["judgment_id"] = judgment_id("same_claim", "related_but_distinct", list(candidate.propositions))
    action["members"] = list(candidate.propositions)
    record = record_from_action_payload(action, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records([record, record], _report_with_same_candidate(candidate))

    assert evaluation.duplicates == (record.decision_id,)
    assert [item.record.decision_id for item in evaluation.active] == [record.decision_id]


def test_evaluate_splittable_subset_does_not_suppress_whole_component():
    candidate = _same_candidate(("proposition:a", "proposition:b", "proposition:c"))
    action = _same_claim_advisory_action()
    action["candidate_id"] = candidate_id("same_claim", ["proposition:a", "proposition:b"])
    action["members"] = ["proposition:a", "proposition:b"]
    action["judgment_id"] = judgment_id("same_claim", "related_but_distinct", ["proposition:a", "proposition:b"])
    record = record_from_action_payload(action, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records([record], _report_with_same_candidate(candidate))

    assert [item.record.decision_id for item in evaluation.active] == [record.decision_id]
    assert evaluation.suppressed_same_claim_candidate_ids == frozenset()
    assert not evaluation.stale


def test_evaluate_stale_record_does_not_suppress_candidate():
    candidate = _same_candidate()
    action = _same_claim_advisory_action()
    action["candidate_id"] = "reconcile:same-claim/stale"
    record = record_from_action_payload(action, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records([record], _report_with_same_candidate(candidate))

    assert evaluation.suppressed_same_claim_candidate_ids == frozenset()
    assert evaluation.stale[0].reason == "candidate-missing"


def test_evaluate_current_factorization_split_suppresses_candidate():
    factor = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:broad"]),
        proposition="proposition:broad",
        priority="medium",
        papers=(),
        current={},
        observed_statement_hints=(),
        disagreement=("subject differs",),
        recommended_action="split_possible",
    )
    action = {
        "kind": "record_reconciliation_decision",
        "status": "advisory",
        "decision": "split_possible",
        "candidate_id": factor.candidate_id,
        "judgment_id": judgment_id("factorization_disagreement", "split_possible", ["proposition:broad"]),
        "confidence": "medium",
        "rationale": "Could split, but leave active for now.",
        "source_review": "review.json",
        "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "proposition": "proposition:broad",
    }
    record = record_from_action_payload(action, recorded_at="2026-07-02")
    report = ReconciliationReport(factorization_disagreements=(factor,))

    evaluation = evaluate_decision_records([record], report)

    assert evaluation.suppressed_factorization_candidate_ids == frozenset({factor.candidate_id})
    assert not evaluation.stale

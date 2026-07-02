# Phase 4e Reviewed Decision Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist reviewed advisory proposition-reconciliation decisions and use current saved decisions to keep `reconcile-propositions` focused on unresolved candidates.

**Architecture:** Add a focused `proposition_reconciliation_decisions.py` module that owns decision-record IDs, JSONL parsing, current-corpus validation, and dry-run/apply planning. Integrate it into the existing flat `science annotate` CLI with one record command and a small report-time filtering hook for `reconcile-propositions`. Keep mutation decisions out of the log; canonicalization and resynthesis remain owned by their existing apply surfaces.

**Tech Stack:** Python 3.13, dataclasses, Click, JSON/JSONL, existing Phase 4e reconciliation dataclasses, pytest, ruff, pyright.

---

## Files

- Create: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
  - Decision-record dataclasses.
  - Deterministic `decision_id`.
  - Action-plan advisory record extraction.
  - JSONL load/append.
  - Current-corpus validation and report filtering.
- Modify: `science/src/science_tool/annotation/cli.py`
  - Add `record-proposition-reconciliation-decisions`.
  - Add `--decisions` and `--show-reviewed` to `reconcile-propositions`.
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
  - Keep existing report model; no candidate heuristic changes.
  - Promote current private candidate-resolution helpers to public module helpers so the decisions module does not import `_`-prefixed internals.
- Create: `science/tests/test_proposition_reconciliation_decisions.py`
  - Unit tests for IDs, record parsing, validation, filtering, and append idempotency.
- Modify: `science/tests/test_proposition_reconciliation_cli.py`
  - CLI tests for record command and `reconcile-propositions` diagnostics.

## Design Notes For Implementers

- Persist only Half B actions with `kind == "record_reconciliation_decision"` and `status == "advisory"`.
- In current code this covers:
  - Lane A `related_but_distinct`;
  - Lane A `conflict_or_negation`;
  - Lane B `split_possible`.
- Do not persist:
  - `same_claim` ready canonicalization;
  - `factorization_needs_resynthesis` ready resynthesis;
  - blocked `stance_review_needed` / `needs_human`;
  - advisory `cleanup_factorization_hints` for `insufficient_hints`.
- A saved same-claim subset decision may reanchor through a larger splittable candidate, but it must not hide the whole larger candidate unless the saved `members` equal the current candidate's full proposition set.
- The record command applies blockers with targeted exclusion, not all-or-nothing: a stale, malformed, or conflicting action withholds only its own decision (and, for a conflict, the specific new decisions in that scope). Every other valid decision in the same plan still appears in `would_append` and is appended under `--apply`. Blockers are reported per action so a partial apply is never silent.

---

## Task 1: Decision Record Model And Action Extraction

**Files:**
- Create: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Create: `science/tests/test_proposition_reconciliation_decisions.py`

- [ ] **Step 1: Write failing tests for deterministic IDs and record extraction**

Add `science/tests/test_proposition_reconciliation_decisions.py`:

```python
from __future__ import annotations

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
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")

    assert record.schema_version == 1
    assert record.lane == "same_claim"
    assert record.decision == "related_but_distinct"
    assert record.members == ("proposition:a", "proposition:b")
    assert record.proposition is None
    assert record.recorded_at == "2026-07-02"
    assert record.decision_id == decision_record_id(
        "same_claim",
        "related_but_distinct",
        record.judgment_id,
        record.candidate_id,
        record.members,
    )


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

    assert record.lane == "factorization_disagreement"
    assert record.decision == "split_possible"
    assert record.proposition == "proposition:broad"
    assert record.members == ()


def test_record_from_action_rejects_non_decision_action():
    action = _same_claim_advisory_action()
    action["kind"] = "cleanup_factorization_hints"

    try:
        record_from_action_payload(action, recorded_at="2026-07-02")
    except DecisionRecordError as exc:
        assert "record_reconciliation_decision" in str(exc)
    else:
        raise AssertionError("expected DecisionRecordError")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.proposition_reconciliation_decisions'`.

- [ ] **Step 3: Implement the record model and extraction**

Create `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`:

```python
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


def _digest(parts: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def decision_record_id(
    lane: str,
    decision: str,
    judgment_ref: str,
    primary_ref: str,
    refs: Sequence[str] = (),
) -> str:
    return f"reconcile-decision:{_digest([lane, decision, judgment_ref, primary_ref, *sorted(refs)])}"


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionRecordError(f"{field_name} must be a non-empty string")
    return value.strip()


def _members_from_action(action: Mapping[str, Any]) -> tuple[str, ...]:
    members = action.get("members")
    if not isinstance(members, list) or not all(isinstance(item, str) for item in members):
        raise DecisionRecordError("members must be a list of strings")
    if not members:
        raise DecisionRecordError("members must not be empty")
    return tuple(sorted(set(member.strip() for member in members if member.strip())))


def _lane_for_action(action: Mapping[str, Any]) -> DecisionLane:
    if action.get("members"):
        return LANE_SAME_CLAIM
    if action.get("proposition"):
        return LANE_FACTORIZATION
    raise DecisionRecordError("action must have members or proposition")


def _validate_decision_for_lane(lane: str, decision: str) -> None:
    if lane == LANE_SAME_CLAIM and decision in {"related_but_distinct", "conflict_or_negation"}:
        return
    if lane == LANE_FACTORIZATION and decision == "split_possible":
        return
    raise DecisionRecordError(f"decision {decision!r} is not persistable for lane {lane!r}")


def record_from_action_payload(action: Mapping[str, Any], *, recorded_at: str) -> DecisionRecord:
    if action.get("kind") != "record_reconciliation_decision":
        raise DecisionRecordError("action kind must be record_reconciliation_decision")
    if action.get("status") != "advisory":
        raise DecisionRecordError("action status must be advisory")
    if action.get("blockers"):
        raise DecisionRecordError("advisory action must not have blockers")

    lane = _lane_for_action(action)
    decision = _require_str(action.get("decision"), "decision")
    _validate_decision_for_lane(lane, decision)
    candidate_id = _require_str(action.get("candidate_id"), "candidate_id")
    judgment_ref = _require_str(action.get("judgment_id"), "judgment_id")
    confidence = _require_str(action.get("confidence"), "confidence")
    rationale = _require_str(action.get("rationale"), "rationale")
    source_review = _require_str(action.get("source_review"), "source_review")
    review_source = _require_str(action.get("review_source"), "review_source")

    if lane == LANE_SAME_CLAIM:
        members = _members_from_action(action)
        expected = judgment_id(LANE_SAME_CLAIM, decision, members)
        proposition = None
        primary_ref = candidate_id
        refs = members
    else:
        members = ()
        proposition = _require_str(action.get("proposition"), "proposition")
        expected = judgment_id(LANE_FACTORIZATION, decision, [proposition])
        primary_ref = proposition
        refs = ()
    if judgment_ref != expected:
        raise DecisionRecordError("judgment_id mismatch")

    decision_ref = decision_record_id(lane, decision, judgment_ref, primary_ref, refs)
    return DecisionRecord(
        schema_version=SCHEMA_VERSION,
        decision_id=decision_ref,
        judgment_id=judgment_ref,
        candidate_id=candidate_id,
        lane=lane,
        decision=decision,
        members=members,
        proposition=proposition,
        confidence=confidence,
        rationale=rationale,
        source_review=source_review,
        review_source=review_source,
        recorded_at=_require_str(recorded_at, "recorded_at"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_decisions.py
rtk git commit -m "feat(4e): model reviewed reconciliation decisions"
```

---

## Task 2: JSONL Loading, Appending, And Current-Corpus Validation

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Modify: `science/tests/test_proposition_reconciliation_decisions.py`

- [ ] **Step 1: Add failing tests for JSONL parsing and validation**

Append to `science/tests/test_proposition_reconciliation_decisions.py`:

```python
from pathlib import Path

import pytest

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    ReconciliationReport,
    SameClaimCandidate,
    candidate_id,
)
from science_tool.annotation.proposition_reconciliation_decisions import (
    append_decision_records,
    decision_record_to_json,
    evaluate_decision_records,
    load_decision_records,
)


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


def test_jsonl_load_reports_line_number_for_malformed_record(tmp_path: Path):
    path = tmp_path / "decisions.jsonl"
    path.write_text('{"schema_version": 1}\nnot-json\n', encoding="utf-8")

    with pytest.raises(DecisionRecordError, match="line 2"):
        load_decision_records(path)


def test_append_decision_records_is_idempotent(tmp_path: Path):
    record = record_from_action_payload(_same_claim_advisory_action(), recorded_at="2026-07-02")
    path = tmp_path / "results" / "proposition-reconciliation" / "decisions.jsonl"

    first = append_decision_records(path, [record])
    second = append_decision_records(path, [record])

    assert first.appended == (record.decision_id,)
    assert second.already_recorded == (record.decision_id,)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: FAIL on missing JSONL/evaluation functions.

- [ ] **Step 3: Promote candidate-resolution helpers to public API**

In `science/src/science_tool/annotation/proposition_reconciliation.py`, add public
aliases immediately after the existing private helpers:

```python
def candidate_indexes(
    report: ReconciliationReport,
) -> tuple[dict[str, SameClaimCandidate], dict[str, FactorizationCandidate]]:
    return _candidate_indexes(report)


def members_have_current_edge(candidate: SameClaimCandidate, members: set[str]) -> bool:
    return _members_have_current_edge(candidate, members)


def resolve_same_claim_candidate(
    candidate_ref: str,
    members: set[str],
    same_by_id: Mapping[str, SameClaimCandidate],
    all_same: tuple[SameClaimCandidate, ...],
) -> SameClaimCandidate | None:
    return _resolve_same_claim_candidate(candidate_ref, members, same_by_id, all_same)
```

Do not delete the private helpers in this task; `validate_review_doc` and
`resolve_review_doc` already use them internally. The public wrappers make the
cross-module dependency explicit.

- [ ] **Step 4: Implement JSON conversion, load, append, and evaluation**

Extend `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`:

```python
import json
from pathlib import Path

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    ReconciliationReport,
    SameClaimCandidate,
    candidate_indexes,
    members_have_current_edge,
    resolve_same_claim_candidate,
)


@dataclass(frozen=True)
class EvaluatedDecision:
    record: DecisionRecord
    current_candidate_id: str
    suppresses_candidate: bool


@dataclass(frozen=True)
class StaleDecision:
    record: DecisionRecord
    reason: str


@dataclass(frozen=True)
class ConflictingDecision:
    scope: tuple[str, tuple[str, ...]]
    decision_ids: tuple[str, ...]
    decisions: tuple[str, ...]


@dataclass(frozen=True)
class DecisionEvaluation:
    active: tuple[EvaluatedDecision, ...]
    stale: tuple[StaleDecision, ...]
    duplicates: tuple[str, ...]
    conflicts: tuple[ConflictingDecision, ...]
    suppressed_same_claim_candidate_ids: frozenset[str]
    suppressed_factorization_candidate_ids: frozenset[str]


@dataclass(frozen=True)
class AppendDecisionResult:
    appended: tuple[str, ...]
    already_recorded: tuple[str, ...]


def decision_record_to_json(record: DecisionRecord) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "decision_id": record.decision_id,
        "judgment_id": record.judgment_id,
        "candidate_id": record.candidate_id,
        "lane": record.lane,
        "decision": record.decision,
        "members": list(record.members),
        "proposition": record.proposition,
        "confidence": record.confidence,
        "rationale": record.rationale,
        "source_review": record.source_review,
        "review_source": record.review_source,
        "recorded_at": record.recorded_at,
    }


def decision_record_from_json(payload: Mapping[str, Any], *, line_no: int | None = None) -> DecisionRecord:
    prefix = f"line {line_no}: " if line_no is not None else ""
    try:
        schema_version = payload["schema_version"]
        decision_ref = _require_str(payload.get("decision_id"), "decision_id")
        judgment_ref = _require_str(payload.get("judgment_id"), "judgment_id")
        candidate_ref = _require_str(payload.get("candidate_id"), "candidate_id")
        lane = _require_str(payload.get("lane"), "lane")
        decision = _require_str(payload.get("decision"), "decision")
        members_raw = payload.get("members")
        if not isinstance(members_raw, list) or not all(isinstance(item, str) for item in members_raw):
            raise DecisionRecordError("members must be a list of strings")
        proposition_raw = payload.get("proposition")
        proposition = None if proposition_raw is None else _require_str(proposition_raw, "proposition")
        record = DecisionRecord(
            schema_version=schema_version,
            decision_id=decision_ref,
            judgment_id=judgment_ref,
            candidate_id=candidate_ref,
            lane=lane,  # type: ignore[arg-type]
            decision=decision,
            members=tuple(sorted(members_raw)),
            proposition=proposition,
            confidence=_require_str(payload.get("confidence"), "confidence"),
            rationale=_require_str(payload.get("rationale"), "rationale"),
            source_review=_require_str(payload.get("source_review"), "source_review"),
            review_source=_require_str(payload.get("review_source"), "review_source"),
            recorded_at=_require_str(payload.get("recorded_at"), "recorded_at"),
        )
        _validate_record_shape(record)
        return record
    except (KeyError, DecisionRecordError) as exc:
        raise DecisionRecordError(f"{prefix}{exc}") from exc


def _validate_record_shape(record: DecisionRecord) -> None:
    if record.schema_version != SCHEMA_VERSION:
        raise DecisionRecordError(f"unsupported schema_version: {record.schema_version!r}")
    _validate_decision_for_lane(record.lane, record.decision)
    if record.lane == LANE_SAME_CLAIM:
        if not record.members:
            raise DecisionRecordError("same_claim record must have members")
        if record.proposition is not None:
            raise DecisionRecordError("same_claim record must not have proposition")
        expected = judgment_id(LANE_SAME_CLAIM, record.decision, record.members)
        primary = record.candidate_id
        refs = record.members
    elif record.lane == LANE_FACTORIZATION:
        if record.members:
            raise DecisionRecordError("factorization record must not have members")
        if record.proposition is None:
            raise DecisionRecordError("factorization record must have proposition")
        expected = judgment_id(LANE_FACTORIZATION, record.decision, [record.proposition])
        primary = record.proposition
        refs = ()
    else:
        raise DecisionRecordError(f"unknown lane: {record.lane!r}")
    if record.judgment_id != expected:
        raise DecisionRecordError("judgment_id mismatch")
    expected_decision = decision_record_id(record.lane, record.decision, record.judgment_id, primary, refs)
    if record.decision_id != expected_decision:
        raise DecisionRecordError("decision_id mismatch")


def load_decision_records(path: Path) -> tuple[DecisionRecord, ...]:
    if not path.exists():
        return ()
    records: list[DecisionRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DecisionRecordError(f"line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise DecisionRecordError(f"line {line_no}: record must be an object")
        records.append(decision_record_from_json(payload, line_no=line_no))
    return tuple(records)


def append_decision_records(path: Path, records: Sequence[DecisionRecord]) -> AppendDecisionResult:
    existing = load_decision_records(path)
    existing_ids = {record.decision_id for record in existing}
    to_append = [record for record in sorted(records, key=lambda item: item.decision_id) if record.decision_id not in existing_ids]
    if not to_append:
        return AppendDecisionResult((), tuple(sorted(record.decision_id for record in records)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in to_append:
            handle.write(json.dumps(decision_record_to_json(record), sort_keys=True) + "\n")
    return AppendDecisionResult(
        appended=tuple(record.decision_id for record in to_append),
        already_recorded=tuple(sorted(record.decision_id for record in records if record.decision_id in existing_ids)),
    )


def evaluate_decision_records(records: Sequence[DecisionRecord], report: ReconciliationReport) -> DecisionEvaluation:
    same_by_id, factor_by_id = candidate_indexes(report)
    seen: set[str] = set()
    duplicates: list[str] = []
    active: list[EvaluatedDecision] = []
    stale: list[StaleDecision] = []

    for record in records:
        if record.decision_id in seen:
            duplicates.append(record.decision_id)
            continue
        seen.add(record.decision_id)
        if record.lane == LANE_SAME_CLAIM:
            members = set(record.members)
            candidate = resolve_same_claim_candidate(
                record.candidate_id,
                members,
                same_by_id,
                report.same_claim_candidates,
            )
            if candidate is None:
                stale.append(StaleDecision(record, "candidate-missing"))
                continue
            if not members_have_current_edge(candidate, members):
                stale.append(StaleDecision(record, "members-no-longer-edge-connected"))
                continue
            suppresses = set(candidate.propositions) == members
            active.append(EvaluatedDecision(record, candidate.candidate_id, suppresses))
        else:
            candidate = factor_by_id.get(record.candidate_id)
            if candidate is None or candidate.proposition != record.proposition:
                stale.append(StaleDecision(record, "candidate-missing"))
                continue
            active.append(EvaluatedDecision(record, candidate.candidate_id, True))

    conflicts = _decision_conflicts(active)
    conflict_scopes = {conflict.scope for conflict in conflicts}
    effective_active = tuple(
        item for item in active if _decision_scope(item.record) not in conflict_scopes
    )
    suppress_same = {
        item.current_candidate_id
        for item in effective_active
        if item.record.lane == LANE_SAME_CLAIM and item.suppresses_candidate
    }
    suppress_factor = {
        item.current_candidate_id
        for item in effective_active
        if item.record.lane == LANE_FACTORIZATION and item.suppresses_candidate
    }
    return DecisionEvaluation(
        active=effective_active,
        stale=tuple(stale),
        duplicates=tuple(sorted(duplicates)),
        conflicts=conflicts,
        suppressed_same_claim_candidate_ids=frozenset(suppress_same),
        suppressed_factorization_candidate_ids=frozenset(suppress_factor),
    )


def _decision_scope(record: DecisionRecord) -> tuple[str, tuple[str, ...]]:
    if record.lane == LANE_SAME_CLAIM:
        return (record.lane, record.members)
    return (record.lane, (record.proposition or "",))


def _decision_conflicts(active: Sequence[EvaluatedDecision]) -> tuple[ConflictingDecision, ...]:
    by_scope: dict[tuple[str, tuple[str, ...]], list[DecisionRecord]] = {}
    for item in active:
        by_scope.setdefault(_decision_scope(item.record), []).append(item.record)
    conflicts: list[ConflictingDecision] = []
    for scope, records in sorted(by_scope.items()):
        decisions = sorted({record.decision for record in records})
        if len(decisions) < 2:
            continue
        conflicts.append(
            ConflictingDecision(
                scope=scope,
                decision_ids=tuple(sorted(record.decision_id for record in records)),
                decisions=tuple(decisions),
            )
        )
    return tuple(conflicts)
```

- [ ] **Step 5: Run focused tests and fix type/lint issues**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
rtk uv run --frozen --project science ruff check science/src/science_tool/annotation/proposition_reconciliation.py science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_decisions.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_decisions.py
rtk git commit -m "feat(4e): validate reviewed decision records"
```

---

## Task 3: Record Command Dry Run And Apply

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_record_reconciliation_decisions_dry_run_reports_would_append(tmp_path: Path):
    runner = CliRunner()
    root = _reconciliation_project(tmp_path)
    candidate = _first_same_claim_candidate(root)
    review = _related_but_distinct_review_for_candidate(candidate)
    review_path = root / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan_path = root / "plan.json"
    plan_result = runner.invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(root),
            "--input",
            str(review_path),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output

    result = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(root),
            "--input",
            str(plan_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["would_append"] == 1
    assert payload["summary"]["appended"] == 0
    assert not (root / "results/proposition-reconciliation/decisions.jsonl").exists()


def test_record_reconciliation_decisions_apply_is_idempotent(tmp_path: Path):
    runner = CliRunner()
    root = _reconciliation_project(tmp_path)
    candidate = _first_same_claim_candidate(root)
    review = _related_but_distinct_review_for_candidate(candidate)
    review_path = root / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan_path = root / "plan.json"
    runner.invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(root),
            "--input",
            str(review_path),
            "--output",
            str(plan_path),
        ],
    )

    first = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(root),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )
    second = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(root),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_payload = json.loads(first.output)
    second_payload = json.loads(second.output)
    assert first_payload["summary"]["appended"] == 1
    assert second_payload["summary"]["already_recorded"] == 1
    log_path = root / "results/proposition-reconciliation/decisions.jsonl"
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1
```

If `_reconciliation_project` or `_first_same_claim_candidate` are not existing helpers,
add minimal helpers near the existing reconciliation CLI fixtures rather than copying a
large project setup.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_cli.py -k "record_reconciliation_decisions" -q
```

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Add plan loading and record planning helpers**

First append this regression test to `science/tests/test_proposition_reconciliation_decisions.py`.
It pins the targeted-exclusion contract: a stale (or conflicting) sibling action must
not withhold the unrelated valid decisions in the same plan.

```python
from science_tool.annotation.proposition_reconciliation_decisions import (
    build_record_decision_plan,
)


def test_build_record_decision_plan_appends_valid_despite_stale_sibling():
    candidate = _same_candidate()
    valid = _same_claim_advisory_action()
    valid["candidate_id"] = candidate.candidate_id
    valid["members"] = list(candidate.propositions)
    valid["judgment_id"] = judgment_id(
        "same_claim", "related_but_distinct", list(candidate.propositions)
    )

    stale = _same_claim_advisory_action()
    stale["action_id"] = "reconcile-action:stale"
    stale["candidate_id"] = "reconcile:same-claim/missing"
    stale["members"] = ["proposition:x", "proposition:y"]
    stale["judgment_id"] = judgment_id(
        "same_claim", "related_but_distinct", ["proposition:x", "proposition:y"]
    )

    plan = build_record_decision_plan(
        action_plan={"schema_version": 1, "actions": [valid, stale], "errors": []},
        existing_records=(),
        report=_report_with_same_candidate(candidate),
        recorded_at="2026-07-02",
    )

    valid_record = record_from_action_payload(valid, recorded_at="2026-07-02")
    assert [record.decision_id for record in plan.would_append] == [valid_record.decision_id]
    assert [blocker["reason"] for blocker in plan.blockers] == ["candidate-missing"]
```

Then extend `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`:

```python
@dataclass(frozen=True)
class RecordDecisionPlan:
    would_append: tuple[DecisionRecord, ...]
    already_recorded: tuple[str, ...]
    stale_existing: tuple[StaleDecision, ...]
    blockers: tuple[Mapping[str, Any], ...]


def build_record_decision_plan(
    *,
    action_plan: Mapping[str, Any],
    existing_records: Sequence[DecisionRecord],
    report: ReconciliationReport,
    recorded_at: str,
) -> RecordDecisionPlan:
    if action_plan.get("schema_version") != 1:
        raise DecisionRecordError("unsupported action plan schema_version")
    if action_plan.get("errors"):
        raise DecisionRecordError("action plan has top-level errors")
    actions = action_plan.get("actions")
    if not isinstance(actions, list):
        raise DecisionRecordError("action plan actions must be a list")

    records: list[DecisionRecord] = []
    blockers: list[Mapping[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise DecisionRecordError(f"actions[{index}] must be an object")
        if action.get("kind") != "record_reconciliation_decision":
            continue
        try:
            record = record_from_action_payload(action, recorded_at=recorded_at)
        except DecisionRecordError as exc:
            blockers.append({"action": action.get("action_id"), "reason": str(exc)})
            continue
        current_eval = evaluate_decision_records([record], report)
        if current_eval.stale:
            blockers.append(
                {
                    "action": action.get("action_id"),
                    "decision_id": record.decision_id,
                    "reason": current_eval.stale[0].reason,
                }
            )
            continue
        records.append(record)

    existing_ids = {record.decision_id for record in existing_records}
    existing_eval = evaluate_decision_records(existing_records, report)
    new_ids = {record.decision_id for record in records}
    combined_eval = evaluate_decision_records([*existing_records, *records], report)

    # Targeted exclusion: a conflict withholds ONLY the conflicting new decisions,
    # never the unrelated valid ones. Stale/malformed actions are already excluded
    # from `records` above and reported as per-action blockers; they must not
    # suppress sibling appends.
    conflicted_new_ids: set[str] = set()
    for conflict in combined_eval.conflicts:
        conflict_new_ids = {
            decision_id for decision_id in conflict.decision_ids if decision_id in new_ids
        }
        if not conflict_new_ids:
            continue
        conflicted_new_ids.update(conflict_new_ids)
        blockers.append(
            {
                "reason": "conflicting-reviewed-decisions",
                "decision_ids": list(conflict.decision_ids),
                "decisions": list(conflict.decisions),
            }
        )

    would_append = tuple(
        sorted(
            (
                record
                for record in records
                if record.decision_id not in existing_ids
                and record.decision_id not in conflicted_new_ids
            ),
            key=lambda item: item.decision_id,
        )
    )
    already = tuple(sorted(record.decision_id for record in records if record.decision_id in existing_ids))
    return RecordDecisionPlan(
        would_append=would_append,
        already_recorded=already,
        stale_existing=existing_eval.stale,
        blockers=tuple(blockers),
    )


def record_decision_plan_to_json(plan: RecordDecisionPlan, *, appended: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "summary": {
            "would_append": len(plan.would_append),
            "already_recorded": len(plan.already_recorded),
            "stale_existing": len(plan.stale_existing),
            "blockers": len(plan.blockers),
            "appended": len(appended),
        },
        "would_append": [decision_record_to_json(record) for record in plan.would_append],
        "already_recorded": list(plan.already_recorded),
        "stale_existing": [
            {"decision_id": item.record.decision_id, "reason": item.reason}
            for item in plan.stale_existing
        ],
        "blockers": [dict(item) for item in plan.blockers],
        "appended": list(appended),
    }
```

- [ ] **Step 4: Add the CLI command**

In `science/src/science_tool/annotation/cli.py`, add a flat command near the other
proposition reconciliation commands:

```python
@annotate_group.command("record-proposition-reconciliation-decisions")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--decisions",
    "decisions_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
@click.option("--apply", "apply", is_flag=True, default=False)
def record_proposition_reconciliation_decisions_cmd(
    input_path: Path,
    root: Path | None,
    decisions_path: Path | None,
    fmt: str,
    apply: bool,
) -> None:
    """Persist reviewed advisory proposition reconciliation decisions."""
    from datetime import date

    from science_tool.annotation.proposition_reconciliation import build_reconciliation_report
    from science_tool.annotation.proposition_reconciliation_decisions import (
        DEFAULT_DECISION_LOG,
        DecisionRecordError,
        append_decision_records,
        build_record_decision_plan,
        load_decision_records,
        record_decision_plan_to_json,
    )

    project_root = (root or Path.cwd()).resolve()
    decision_log = decisions_path or project_root / DEFAULT_DECISION_LOG
    if not decision_log.is_absolute():
        decision_log = project_root / decision_log
    try:
        action_plan = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
    if not isinstance(action_plan, dict):
        raise click.ClickException("--input must be a JSON object")

    try:
        existing = load_decision_records(decision_log)
        report = build_reconciliation_report(project_root)
        plan = build_record_decision_plan(
            action_plan=action_plan,
            existing_records=existing,
            report=report,
            recorded_at=date.today().isoformat(),
        )
    except DecisionRecordError as exc:
        raise click.ClickException(str(exc)) from exc

    appended: tuple[str, ...] = ()
    if apply and plan.would_append:
        result = append_decision_records(decision_log, plan.would_append)
        appended = result.appended

    payload = record_decision_plan_to_json(plan, appended=appended)
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "proposition reconciliation decisions: "
        f"would_append={summary['would_append']} "
        f"already_recorded={summary['already_recorded']} "
        f"stale_existing={summary['stale_existing']} "
        f"blockers={summary['blockers']} "
        f"appended={summary['appended']}"
    )
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_cli.py -k "record_reconciliation_decisions" -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): record reviewed reconciliation decisions"
```

---

## Task 4: Reconciliation Report Suppression And Diagnostics

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing report integration tests**

Append to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_reconcile_propositions_suppresses_reviewed_decision_by_default(tmp_path: Path):
    runner = CliRunner()
    root = _reconciliation_project(tmp_path)
    candidate = _first_same_claim_candidate(root)
    review = _related_but_distinct_review_for_candidate(candidate)
    review_path = root / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan_path = root / "plan.json"
    runner.invoke(
        annotate_group,
        ["plan-proposition-reconciliation", "--root", str(root), "--input", str(review_path), "--output", str(plan_path)],
    )
    result = runner.invoke(
        annotate_group,
        ["record-proposition-reconciliation-decisions", "--root", str(root), "--input", str(plan_path), "--apply"],
    )
    assert result.exit_code == 0, result.output

    report_result = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--root", str(root), "--all", "--format", "json"],
    )

    assert report_result.exit_code == 0, report_result.output
    payload = json.loads(report_result.output)
    assert payload["summary"]["reviewed_decisions"] == 1
    assert payload["summary"]["same_claim_candidates"] == 0
    assert payload["summary"]["generated_same_claim_candidates"] == 1
    assert payload["same_claim_candidates"] == []
    assert payload["reviewed_decisions"]["active"][0]["candidate_id"] == candidate["candidate_id"]


def test_reconcile_propositions_show_reviewed_keeps_annotated_candidate(tmp_path: Path):
    runner = CliRunner()
    root = _reconciliation_project(tmp_path)
    candidate = _first_same_claim_candidate(root)
    review = _related_but_distinct_review_for_candidate(candidate)
    review_path = root / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan_path = root / "plan.json"
    runner.invoke(
        annotate_group,
        ["plan-proposition-reconciliation", "--root", str(root), "--input", str(review_path), "--output", str(plan_path)],
    )
    runner.invoke(
        annotate_group,
        ["record-proposition-reconciliation-decisions", "--root", str(root), "--input", str(plan_path), "--apply"],
    )

    report_result = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--root", str(root), "--all", "--show-reviewed", "--format", "json"],
    )

    assert report_result.exit_code == 0, report_result.output
    payload = json.loads(report_result.output)
    assert payload["summary"]["same_claim_candidates"] == 1
    assert len(payload["same_claim_candidates"]) == 1
    assert payload["same_claim_candidates"][0]["reviewed_decision_id"].startswith("reconcile-decision:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_cli.py -k "reconcile_propositions_suppresses_reviewed or show_reviewed" -q
```

Expected: FAIL because `--show-reviewed` and report filtering do not exist.

- [ ] **Step 3: Implement payload filtering helper**

Extend `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`:

```python
def reviewed_decisions_to_json(evaluation: DecisionEvaluation) -> dict[str, Any]:
    return {
        "active": [
            {
                "decision_id": item.record.decision_id,
                "candidate_id": item.current_candidate_id,
                "lane": item.record.lane,
                "decision": item.record.decision,
                "members": list(item.record.members),
                "proposition": item.record.proposition,
                "suppresses_candidate": item.suppresses_candidate,
            }
            for item in evaluation.active
        ],
        "stale": [
            {"decision_id": item.record.decision_id, "reason": item.reason}
            for item in evaluation.stale
        ],
        "duplicates": list(evaluation.duplicates),
        "conflicts": [
            {
                "scope": {"lane": item.scope[0], "refs": list(item.scope[1])},
                "decision_ids": list(item.decision_ids),
                "decisions": list(item.decisions),
            }
            for item in evaluation.conflicts
        ],
    }


def apply_reviewed_decisions_to_report_payload(
    payload: Mapping[str, Any],
    evaluation: DecisionEvaluation,
    *,
    show_reviewed: bool,
) -> dict[str, Any]:
    out = dict(payload)
    summary = dict(out.get("summary", {}))
    generated_same = int(summary.get("same_claim_candidates", 0))
    generated_factor = int(summary.get("factorization_disagreements", 0))
    active_by_candidate = {item.current_candidate_id: item for item in evaluation.active}
    summary["generated_same_claim_candidates"] = generated_same
    summary["generated_factorization_disagreements"] = generated_factor
    summary["reviewed_decisions"] = len(evaluation.active)
    summary["stale_reviewed_decisions"] = len(evaluation.stale)
    summary["duplicate_reviewed_decisions"] = len(evaluation.duplicates)
    summary["conflicting_reviewed_decisions"] = len(evaluation.conflicts)
    out["reviewed_decisions"] = reviewed_decisions_to_json(evaluation)

    same_candidates = []
    for item in out.get("same_claim_candidates", []):
        candidate_ref = item.get("candidate_id")
        active = active_by_candidate.get(candidate_ref)
        if active is not None and active.suppresses_candidate and not show_reviewed:
            continue
        if active is not None:
            annotated = dict(item)
            annotated["reviewed_decision_id"] = active.record.decision_id
            same_candidates.append(annotated)
        else:
            same_candidates.append(item)
    out["same_claim_candidates"] = same_candidates

    factor_candidates = []
    for item in out.get("factorization_disagreements", []):
        candidate_ref = item.get("candidate_id")
        active = active_by_candidate.get(candidate_ref)
        if active is not None and active.suppresses_candidate and not show_reviewed:
            continue
        if active is not None:
            annotated = dict(item)
            annotated["reviewed_decision_id"] = active.record.decision_id
            factor_candidates.append(annotated)
        else:
            factor_candidates.append(item)
    out["factorization_disagreements"] = factor_candidates
    summary["same_claim_candidates"] = len(same_candidates)
    summary["factorization_disagreements"] = len(factor_candidates)
    out["summary"] = summary
    return out
```

- [ ] **Step 4: Integrate decision log into `reconcile-propositions`**

Modify the `reconcile-propositions` command in `science/src/science_tool/annotation/cli.py`:

```python
@click.option(
    "--decisions",
    "decisions_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--show-reviewed", "show_reviewed", is_flag=True, default=False)
def reconcile_propositions_cmd(
    all_scope: bool,
    proposition_ref: str | None,
    source_md: Path | None,
    root: Path | None,
    fmt: str,
    decisions_path: Path | None,
    show_reviewed: bool,
) -> None:
```

After `payload = report_to_json(report)`, add:

```python
    from science_tool.annotation.proposition_reconciliation_decisions import (
        DEFAULT_DECISION_LOG,
        DecisionRecordError,
        apply_reviewed_decisions_to_report_payload,
        evaluate_decision_records,
        load_decision_records,
    )

    decision_log = decisions_path or project_root / DEFAULT_DECISION_LOG
    if not decision_log.is_absolute():
        decision_log = project_root / decision_log
    try:
        records = load_decision_records(decision_log)
        evaluation = evaluate_decision_records(records, report)
    except DecisionRecordError as exc:
        raise click.ClickException(str(exc)) from exc
    payload = apply_reviewed_decisions_to_report_payload(
        payload,
        evaluation,
        show_reviewed=show_reviewed,
    )
```

This hook intentionally runs before the `fmt in {"json", "scaffold"}` branch. Both
JSON and scaffold output should suppress already-recorded advisory decisions by
default, and both should honor `--show-reviewed`.

Update table output summary to include reviewed counts:

```python
    click.echo(
        "proposition reconciliation: "
        f"same_claim={summary['same_claim_candidates']} "
        f"factorization={summary['factorization_disagreements']} "
        f"faults={summary['faults']} "
        f"reviewed={summary.get('reviewed_decisions', 0)} "
        f"stale_reviewed={summary.get('stale_reviewed_decisions', 0)}"
    )
```

- [ ] **Step 5: Run focused CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_cli.py -k "record_reconciliation_decisions or reconcile_propositions_suppresses_reviewed or show_reviewed" -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): apply reviewed decisions to reconciliation reports"
```

---

## Task 5: Hardening And Validation Edge Cases

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Modify: `science/tests/test_proposition_reconciliation_decisions.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing edge-case tests**

Append to `science/tests/test_proposition_reconciliation_decisions.py`:

```python
def test_conflicting_current_same_claim_decisions_are_diagnostics_not_suppression():
    candidate = _same_candidate()
    base = _same_claim_advisory_action()
    base["candidate_id"] = candidate.candidate_id
    base["members"] = list(candidate.propositions)
    base["judgment_id"] = judgment_id("same_claim", "related_but_distinct", list(candidate.propositions))
    related = record_from_action_payload(base, recorded_at="2026-07-02")
    conflict_payload = dict(base)
    conflict_payload["decision"] = "conflict_or_negation"
    conflict_payload["judgment_id"] = judgment_id("same_claim", "conflict_or_negation", list(candidate.propositions))
    conflict = record_from_action_payload(conflict_payload, recorded_at="2026-07-02")

    evaluation = evaluate_decision_records([related, conflict], _report_with_same_candidate(candidate))

    assert evaluation.conflicts[0].decisions == ("conflict_or_negation", "related_but_distinct")
    assert evaluation.suppressed_same_claim_candidate_ids == frozenset()
    assert evaluation.active == ()


def test_malformed_decision_record_reports_line_number(tmp_path: Path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decision_id": "wrong",
                "judgment_id": "reconcile:judgment/wrong",
                "candidate_id": "reconcile:same-claim/c",
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": ["proposition:a", "proposition:b"],
                "proposition": None,
                "confidence": "high",
                "rationale": "Reviewed.",
                "source_review": "review.json",
                "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
                "recorded_at": "2026-07-02",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DecisionRecordError, match="line 1"):
        load_decision_records(path)
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: FAIL for conflict detection if not implemented yet.

- [ ] **Step 3: Verify conflict detection suppresses nothing**

Confirm `evaluate_decision_records` has the Task 2 conflict behavior:

```python
    conflicts = _decision_conflicts(active)
    conflict_scopes = {conflict.scope for conflict in conflicts}
    effective_active = tuple(
        item for item in active if _decision_scope(item.record) not in conflict_scopes
    )
```

and returns:

```python
        active=effective_active,
        conflicts=conflicts,
```

If the test from Step 1 fails, make the implementation match those snippets and
recompute suppression sets only from `effective_active`.

Do not raise from `evaluate_decision_records` for current same-scope conflicts. The
read path must keep `reconcile-propositions` usable and surface the conflict as data.

- [ ] **Step 4: Run focused tests and static checks**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_cli.py -k "decision or reviewed" -q
rtk uv run --frozen --project science ruff check science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_cli.py
rtk uv run --frozen --project science pyright science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/src/science_tool/annotation/cli.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "fix(4e): harden reviewed decision validation"
```

---

## Task 6: Verification And Smoke

**Files:**
- Modify only if verification reveals a defect.

- [ ] **Step 1: Run full relevant test suite**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_apply.py \
  science/tests/test_proposition_reconciliation_cli.py \
  science/tests/test_proposition_reconciliation_decisions.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting/lint/type checks on touched files**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/annotation/proposition_reconciliation_decisions.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_proposition_reconciliation_decisions.py \
  science/tests/test_proposition_reconciliation_cli.py
rtk uv run --frozen --project science pyright \
  science/src/science_tool/annotation/proposition_reconciliation_decisions.py \
  science/src/science_tool/annotation/cli.py
```

Expected: PASS.

- [ ] **Step 3: Real-corpus dry smoke if an advisory review exists**

Search for a committed advisory review:

```bash
rtk rg -n '"decision": "(related_but_distinct|conflict_or_negation|split_possible)"' meta/results/proposition-reconciliation
```

If a matching review exists, run:

```bash
cd meta
PYTHONPATH=../science/src:../science/model/src rtk uv run --frozen --project ../science \
  science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/<review-file>.json \
  --output /tmp/phase4e-reviewed-decision-plan.json
PYTHONPATH=../science/src:../science/model/src rtk uv run --frozen --project ../science \
  science annotate record-proposition-reconciliation-decisions \
  --input /tmp/phase4e-reviewed-decision-plan.json \
  --format json
```

Expected: command exits 0 and reports either `would_append > 0` or
`already_recorded > 0`. Treat stale review failures as corpus facts to inspect, not
as automatic implementation bugs.

- [ ] **Step 4: Run full science test suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests -q
```

Expected: PASS.

- [ ] **Step 5: Final commit if verification fixes were needed**

If Step 1-4 required fixes:

```bash
rtk git add <changed-files>
rtk git commit -m "test(4e): verify reviewed decision persistence"
```

If no fixes were needed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - Append-only decision log: Tasks 1-3.
  - Deterministic IDs: Task 1.
  - Current-corpus validation: Tasks 2 and 5.
  - Dry-run/apply command: Task 3.
  - Report-time suppression/annotation: Task 4.
  - Stale diagnostics and duplicate handling: Tasks 2, 4, and 5.
  - No mutation decision persistence: Task 1 extraction rules and Task 3 filtering.
- Placeholder scan:
  - No `TBD` / `TODO`.
  - No broad "add tests" steps without concrete test code.
- Type consistency:
  - Uses existing `ReconciliationAction` JSON fields from `action_plan_to_json`.
  - Uses existing `candidate_id`, `judgment_id`, `SameClaimCandidate`, `FactorizationCandidate`, and `ReconciliationReport`.
  - Uses `--root`, `--format`, and flat `annotate` command conventions already present in `annotation/cli.py`.

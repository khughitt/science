# Phase 4f Reviewed Reconciliation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewed, stale-aware closure path for current low-priority `insufficient_hints` factorization candidates so reviewed sparse-hint candidates stop resurfacing unless their live assertion shape changes.

**Architecture:** Extend the existing Phase 4e reviewed-decision pipeline rather than adding a new waiver system. The review validator accepts one new Lane B decision, Half B emits a persistable advisory action carrying a deterministic assertion fingerprint, and the decision-log evaluator suppresses only current `accepted_sparse_hints` records whose candidate still recommends `insufficient_hints` and whose fingerprint still matches.

**Tech Stack:** Python 3.13, dataclasses, Click, JSON/JSONL, pytest, ruff, pyright, existing `science_tool.annotation` reconciliation modules.

---

## File Structure

- Modify `science/src/science_tool/annotation/proposition_reconciliation.py`
  - Add `accepted_sparse_hints` to reviewed decision vocabulary.
  - Add an exported `factorization_assertion_fingerprint(candidate)` helper.
  - Tighten Lane B review validation so `accepted_sparse_hints` is valid only for current `insufficient_hints` candidates.

- Modify `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
  - Map reviewed `accepted_sparse_hints` judgments to persistable `record_reconciliation_decision` actions.
  - Carry `assertion_fingerprint` on the action payload.

- Modify `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
  - Extend `DecisionRecord` with optional `assertion_fingerprint`.
  - Serialize, parse, and validate the conditional field.
  - Include the fingerprint in `accepted_sparse_hints` decision ids.
  - Evaluate stale closure states for changed fingerprints and no-longer-sparse-hint candidates.

- Modify `science/src/science_tool/annotation/cli.py`
  - No new command is expected. Existing `reconcile-propositions`, `plan-proposition-reconciliation`, and `record-proposition-reconciliation-decisions` should work through the module changes.
  - Only adjust CLI table text if tests reveal an output assumption that needs a clearer label.

- Modify tests:
  - `science/tests/test_proposition_reconciliation.py`
  - `science/tests/test_proposition_reconciliation_plan.py`
  - `science/tests/test_proposition_reconciliation_decisions.py`
  - `science/tests/test_proposition_reconciliation_cli.py`

- Add corpus review artifacts only after the feature is green:
  - `meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json`
  - `meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json`
  - `meta/results/proposition-reconciliation/decisions.jsonl`

---

## Task 1: Review Vocabulary And Assertion Fingerprint

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Test: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add failing tests for the new Lane B decision and fingerprint**

Append tests to `science/tests/test_proposition_reconciliation.py`. If the file already has nearby review-validation tests, place these beside them; otherwise append near the bottom.

```python
def test_validate_review_doc_accepts_sparse_hint_closure_for_insufficient_hints():
    candidate = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="low",
        papers=("paper:A2020", "paper:B2021"),
        current={},
        observed_statement_hints=(
            {
                "paper": "paper:A2020",
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "stance": "asserted",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "First sparse assertion.",
            },
            {
                "paper": "paper:B2021",
                "annotation": "annotation:entities/papers/B2021.source#b1",
                "stance": "asserted",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "Second sparse assertion.",
            },
        ),
        disagreement=("multiple assertions have insufficient factorization hints",),
        recommended_action="insufficient_hints",
    )
    report = ReconciliationReport(factorization_disagreements=(candidate,))
    doc = {
        "source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement",
                    "accepted_sparse_hints",
                    [candidate.proposition],
                ),
                "lane": "factorization_disagreement",
                "decision": "accepted_sparse_hints",
                "proposition": candidate.proposition,
                "rationale": "Reviewed sparse hints and accepted the current proposition scope.",
                "confidence": "high",
            }
        ],
    }

    result = validate_review_doc(doc, report)

    assert result["status"] == "ok"
    assert result["judgments"] == 1


def test_validate_review_doc_rejects_sparse_hint_closure_for_non_sparse_candidate():
    candidate = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="high",
        papers=("paper:A2020", "paper:B2021"),
        current={},
        observed_statement_hints=(),
        disagreement=("stance mix requires review",),
        recommended_action="stance_review_needed",
    )
    report = ReconciliationReport(factorization_disagreements=(candidate,))
    doc = {
        "source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement",
                    "accepted_sparse_hints",
                    [candidate.proposition],
                ),
                "lane": "factorization_disagreement",
                "decision": "accepted_sparse_hints",
                "proposition": candidate.proposition,
                "rationale": "This should not close a stance-review candidate.",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="accepted_sparse_hints"):
        validate_review_doc(doc, report)


def test_factorization_assertion_fingerprint_changes_when_subject_hint_changes():
    base = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="low",
        papers=("paper:A2020",),
        current={},
        observed_statement_hints=(
            {
                "paper": "paper:A2020",
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "stance": "asserted",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "Sparse assertion.",
            },
        ),
        disagreement=("multiple assertions have insufficient factorization hints",),
        recommended_action="insufficient_hints",
    )
    changed = FactorizationCandidate(
        candidate_id=base.candidate_id,
        proposition=base.proposition,
        priority=base.priority,
        papers=base.papers,
        current=base.current,
        observed_statement_hints=(
            {
                "paper": "paper:A2020",
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "stance": "asserted",
                "section": "results",
                "subject": "Bayesian Evidence Synthesis",
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "Sparse assertion.",
            },
        ),
        disagreement=base.disagreement,
        recommended_action=base.recommended_action,
    )

    left = factorization_assertion_fingerprint(base)
    right = factorization_assertion_fingerprint(changed)

    assert left.startswith("sha256:")
    assert len(left.removeprefix("sha256:")) == 64
    assert left != right
```

Also update imports in that test file:

```python
from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    ReconciliationReport,
    ReconciliationValidationError,
    candidate_id,
    factorization_assertion_fingerprint,
    judgment_id,
    validate_review_doc,
)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation.py -q
```

Expected: FAIL because `accepted_sparse_hints` is not in `DECISIONS` / `LANE_B_DECISIONS`, `factorization_assertion_fingerprint` does not exist, or both.

- [ ] **Step 3: Implement the vocabulary and fingerprint helper**

In `science/src/science_tool/annotation/proposition_reconciliation.py`, add a constant near the lane constants:

```python
DECISION_ACCEPTED_SPARSE_HINTS = "accepted_sparse_hints"
SPARSE_HINT_DISAGREEMENT = "multiple assertions have insufficient factorization hints"
```

Add `DECISION_ACCEPTED_SPARSE_HINTS` to both `DECISIONS` and `LANE_B_DECISIONS`.

Add this helper near `_digest` / id helpers:

```python
def _fingerprint_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def factorization_assertion_fingerprint(candidate: FactorizationCandidate) -> str:
    rows: list[str] = []
    for hint in candidate.observed_statement_hints:
        rows.append(
            "\0".join(
                [
                    _fingerprint_text(hint.get("annotation")),
                    _fingerprint_text(hint.get("paper")),
                    _fingerprint_text(hint.get("stance")),
                    _fingerprint_text(hint.get("subject")),
                    _fingerprint_text(hint.get("object")),
                    _fingerprint_text(hint.get("subject_concept")),
                    _fingerprint_text(hint.get("object_concept")),
                    _fingerprint_text(hint.get("exact")),
                ]
            )
        )
    digest = _digest(
        [
            "factorization-assertions-v1",
            candidate.proposition,
            *sorted(rows),
        ]
    )
    return f"sha256:{digest}"
```

In the Lane B branch of `validate_review_doc`, after the proposition match and before `expected_judgment`, add:

```python
            if decision == DECISION_ACCEPTED_SPARSE_HINTS:
                _require(
                    candidate.recommended_action == "insufficient_hints"
                    and tuple(candidate.disagreement) == (SPARSE_HINT_DISAGREEMENT,),
                    f"judgments[{idx}].accepted_sparse_hints requires a current insufficient_hints candidate",
                )
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat: add sparse hint closure vocabulary"
```

---

## Task 2: Half B Action Planning For Closure

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
- Test: `science/tests/test_proposition_reconciliation_plan.py`

- [ ] **Step 1: Add failing action-plan tests**

In `science/tests/test_proposition_reconciliation_plan.py`, add imports:

```python
from science_tool.annotation.proposition_reconciliation import (
    factorization_assertion_fingerprint,
)
```

Add tests near `test_insufficient_hints_maps_to_advisory_cleanup_action`:

```python
def test_accepted_sparse_hints_maps_to_record_decision_action_with_fingerprint():
    candidate = _factor_candidate(recommended_action="insufficient_hints")
    candidate = FactorizationCandidate(
        candidate_id=candidate.candidate_id,
        proposition=candidate.proposition,
        priority="low",
        papers=candidate.papers,
        current=candidate.current,
        observed_statement_hints=candidate.observed_statement_hints,
        disagreement=("multiple assertions have insufficient factorization hints",),
        recommended_action="insufficient_hints",
    )
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(candidate, decision="accepted_sparse_hints"),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "record_reconciliation_decision"
    assert action.status == "advisory"
    assert action.decision == "accepted_sparse_hints"
    assert action.proposition == candidate.proposition
    assert action.inputs["assertion_fingerprint"] == factorization_assertion_fingerprint(candidate)
    assert action.blockers == ()
```

- [ ] **Step 2: Run the focused plan test and verify it fails**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_plan.py::test_accepted_sparse_hints_maps_to_record_decision_action_with_fingerprint -q
```

Expected: FAIL because the action kind is not `record_reconciliation_decision`, or because the fingerprint is absent from `inputs`.

- [ ] **Step 3: Implement action planning**

In `science/src/science_tool/annotation/proposition_reconciliation_plan.py`, import:

```python
from science_tool.annotation.proposition_reconciliation import (
    DECISION_ACCEPTED_SPARSE_HINTS,
    factorization_assertion_fingerprint,
)
```

Keep the existing imported names intact.

Update `_factorization_suggestions`:

```python
    if decision == DECISION_ACCEPTED_SPARSE_HINTS:
        return (
            {
                "kind": "record_sparse_hint_closure",
                "detail": "Record reviewed closure for the current sparse-hint candidate.",
            },
        )
```

Update `_action_from_factorization` decision mapping:

```python
    elif decision == DECISION_ACCEPTED_SPARSE_HINTS:
        action_kind = "record_reconciliation_decision"
        status = "advisory"
```

Before returning `ReconciliationAction`, compute:

```python
    inputs = _factorization_inputs(candidate)
    if decision == DECISION_ACCEPTED_SPARSE_HINTS:
        inputs = {
            **inputs,
            "assertion_fingerprint": factorization_assertion_fingerprint(candidate),
        }
```

Then pass `inputs=inputs` instead of `inputs=_factorization_inputs(candidate)`.

- [ ] **Step 4: Run focused plan tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_plan.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_plan.py
rtk git commit -m "feat: plan sparse hint closure records"
```

---

## Task 3: Decision Record Shape, IDs, And Freshness

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`
- Test: `science/tests/test_proposition_reconciliation_decisions.py`

- [ ] **Step 1: Add failing decision-record tests**

In `science/tests/test_proposition_reconciliation_decisions.py`, update imports:

```python
from science_tool.annotation.proposition_reconciliation import (
    DECISION_ACCEPTED_SPARSE_HINTS,
    SPARSE_HINT_DISAGREEMENT,
    factorization_assertion_fingerprint,
)
```

Keep existing imported names.

Add helper functions near `_same_candidate`:

```python
def _sparse_factor_candidate(
    *,
    proposition: str = "proposition:broad",
    subject: str | None = None,
    recommended_action: str = "insufficient_hints",
) -> FactorizationCandidate:
    return FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", [proposition]),
        proposition=proposition,
        priority="low",
        papers=("paper:A2020", "paper:B2021"),
        current={},
        observed_statement_hints=(
            {
                "paper": "paper:A2020",
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "stance": "asserted",
                "section": "results",
                "subject": subject,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "First assertion.",
            },
            {
                "paper": "paper:B2021",
                "annotation": "annotation:entities/papers/B2021.source#b1",
                "stance": "asserted",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "Second assertion.",
            },
        ),
        disagreement=(SPARSE_HINT_DISAGREEMENT,),
        recommended_action=recommended_action,
    )


def _accepted_sparse_hints_action(candidate: FactorizationCandidate) -> dict:
    return {
        "action_id": "reconcile-action:sparse",
        "kind": "record_reconciliation_decision",
        "status": "advisory",
        "decision": DECISION_ACCEPTED_SPARSE_HINTS,
        "candidate_id": candidate.candidate_id,
        "judgment_id": judgment_id(
            "factorization_disagreement",
            DECISION_ACCEPTED_SPARSE_HINTS,
            [candidate.proposition],
        ),
        "confidence": "high",
        "rationale": "Reviewed sparse hints and accepted the current proposition scope.",
        "source_review": "review.json",
        "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "proposition": candidate.proposition,
        "inputs": {
            "assertion_fingerprint": factorization_assertion_fingerprint(candidate),
            "observed_statement_hints": candidate.observed_statement_hints,
        },
        "suggested_operations": [],
        "preconditions": [],
        "blockers": [],
        "writes": [],
    }
```

Add tests:

```python
def test_record_from_accepted_sparse_hints_action_payload_round_trips_fingerprint():
    candidate = _sparse_factor_candidate()
    action = _accepted_sparse_hints_action(candidate)

    record = record_from_action_payload(action, recorded_at="2026-07-03")
    payload = decision_record_to_json(record)
    parsed = decision_record_from_json(payload)

    assert record.decision == DECISION_ACCEPTED_SPARSE_HINTS
    assert record.assertion_fingerprint == factorization_assertion_fingerprint(candidate)
    assert payload["assertion_fingerprint"] == record.assertion_fingerprint
    assert parsed == record
    assert record.decision_id == decision_record_id(
        "factorization_disagreement",
        DECISION_ACCEPTED_SPARSE_HINTS,
        record.judgment_id,
        record.candidate_id,
        [record.proposition, record.assertion_fingerprint],
    )


def test_record_from_sparse_hints_action_requires_fingerprint():
    candidate = _sparse_factor_candidate()
    action = _accepted_sparse_hints_action(candidate)
    del action["inputs"]["assertion_fingerprint"]

    with pytest.raises(DecisionRecordError, match="assertion_fingerprint"):
        record_from_action_payload(action, recorded_at="2026-07-03")


def test_evaluate_sparse_hint_closure_suppresses_matching_candidate():
    candidate = _sparse_factor_candidate()
    record = record_from_action_payload(
        _accepted_sparse_hints_action(candidate),
        recorded_at="2026-07-03",
    )
    report = ReconciliationReport(factorization_disagreements=(candidate,))

    evaluation = evaluate_decision_records([record], report)

    assert evaluation.stale == ()
    assert evaluation.suppressed_factorization_candidate_ids == frozenset({candidate.candidate_id})
    assert evaluation.active[0].record.decision == DECISION_ACCEPTED_SPARSE_HINTS


def test_evaluate_sparse_hint_closure_stale_when_fingerprint_changes():
    original = _sparse_factor_candidate()
    changed = _sparse_factor_candidate(subject="Bayesian Evidence Synthesis")
    record = record_from_action_payload(
        _accepted_sparse_hints_action(original),
        recorded_at="2026-07-03",
    )
    report = ReconciliationReport(factorization_disagreements=(changed,))

    evaluation = evaluate_decision_records([record], report)

    assert evaluation.suppressed_factorization_candidate_ids == frozenset()
    assert evaluation.stale[0].reason == "assertion-fingerprint-changed"


def test_evaluate_sparse_hint_closure_stale_when_candidate_no_longer_sparse():
    original = _sparse_factor_candidate()
    changed = _sparse_factor_candidate(recommended_action="factorization_needs_resynthesis")
    record = record_from_action_payload(
        _accepted_sparse_hints_action(original),
        recorded_at="2026-07-03",
    )
    report = ReconciliationReport(factorization_disagreements=(changed,))

    evaluation = evaluate_decision_records([record], report)

    assert evaluation.suppressed_factorization_candidate_ids == frozenset()
    assert evaluation.stale[0].reason == "candidate-no-longer-sparse-hints"


def test_reclosing_sparse_hints_after_fingerprint_drift_appends_new_record():
    original = _sparse_factor_candidate()
    changed = _sparse_factor_candidate(subject="Bayesian Evidence Synthesis")
    existing = record_from_action_payload(
        _accepted_sparse_hints_action(original),
        recorded_at="2026-07-03",
    )
    action = _accepted_sparse_hints_action(changed)

    plan = build_record_decision_plan(
        action_plan={"schema_version": 1, "actions": [action], "errors": []},
        existing_records=(existing,),
        report=ReconciliationReport(factorization_disagreements=(changed,)),
        recorded_at="2026-07-04",
    )

    assert plan.already_recorded == ()
    assert len(plan.would_append) == 1
    assert plan.would_append[0].decision_id != existing.decision_id
    assert plan.stale_existing[0].reason == "assertion-fingerprint-changed"
```

- [ ] **Step 2: Run the focused decision tests and verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: FAIL because `DecisionRecord.assertion_fingerprint` and `accepted_sparse_hints` persistence are not implemented.

- [ ] **Step 3: Implement decision-record shape and ID logic**

In `science/src/science_tool/annotation/proposition_reconciliation_decisions.py`, import:

```python
from science_tool.annotation.proposition_reconciliation import (
    DECISION_ACCEPTED_SPARSE_HINTS,
    factorization_assertion_fingerprint,
)
```

Keep existing imports.

Change `_LANE_B_DECISIONS`:

```python
_LANE_B_DECISIONS = frozenset({"split_possible", DECISION_ACCEPTED_SPARSE_HINTS})
```

Add a field to `DecisionRecord` after `proposition`:

```python
    assertion_fingerprint: str | None
```

In `decision_record_to_json`, build the payload as a local dict and include the field only when present:

```python
    payload = {
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
    if record.assertion_fingerprint is not None:
        payload["assertion_fingerprint"] = record.assertion_fingerprint
    return payload
```

In `decision_record_from_json`, parse:

```python
    fingerprint_value = payload.get("assertion_fingerprint")
    if fingerprint_value is not None and not isinstance(fingerprint_value, str):
        raise DecisionRecordError(f"{prefix}assertion_fingerprint must be a string")
```

Pass:

```python
        assertion_fingerprint=(
            fingerprint_value.strip() if isinstance(fingerprint_value, str) else None
        ),
```

In `record_from_action_payload`, initialize `assertion_fingerprint` **before** the
`if decision in _LANE_A_DECISIONS: ... elif decision in _LANE_B_DECISIONS: ...`
branch so it is in scope on every path (Lane A and the `DecisionRecord(...)`
construction), then populate it only in the Lane B sparse-hint case:

```python
    # before the Lane A / Lane B branch:
    assertion_fingerprint: str | None = None
```

```python
    # inside the `elif decision in _LANE_B_DECISIONS:` branch, replacing
    # `record_refs = (proposition,)`:
        if decision == DECISION_ACCEPTED_SPARSE_HINTS:
            inputs = action.get("inputs")
            if not isinstance(inputs, Mapping):
                raise DecisionRecordError("inputs must contain assertion_fingerprint")
            assertion_fingerprint = _required_str(
                inputs.get("assertion_fingerprint"),
                "assertion_fingerprint",
            )
            record_refs = (proposition, assertion_fingerprint)
        else:
            record_refs = (proposition,)
```

Leave the Lane A branch alone; `assertion_fingerprint` stays `None` there.

Note that `expected_judgment = judgment_id(lane, decision, [proposition])` is
**unchanged** — the fingerprint is part of `record_refs` (which feeds
`decision_id`) but never part of `judgment_id`.

Pass `assertion_fingerprint=assertion_fingerprint` into `DecisionRecord`.

In `_validate_record_shape`, add:

```python
    if record.assertion_fingerprint is not None:
        _required_str(record.assertion_fingerprint, "assertion_fingerprint")
        suffix = record.assertion_fingerprint.removeprefix("sha256:")
        if (
            not record.assertion_fingerprint.startswith("sha256:")
            or len(suffix) != 64
            or any(ch not in "0123456789abcdef" for ch in suffix)
        ):
            raise DecisionRecordError("assertion_fingerprint must be sha256: followed by 64 hex chars")
```

**Split the reconstruction refs.** The existing `_validate_record_shape` uses a
single `refs` variable to rebuild **both** `judgment_id` and `decision_id`:

```python
    expected_judgment = judgment_id(record.lane, record.decision, refs)
    ...
    expected_decision = decision_record_id(
        record.lane, record.decision, record.judgment_id, record.candidate_id, refs,
    )
```

For `accepted_sparse_hints` these two diverge: `judgment_id` is authored from
`[proposition]` only (the reviewer never sees the fingerprint, and
`validate_review_doc` / `record_from_action_payload` both compute it that way),
while `decision_id` must include the fingerprint. Reusing one `refs` for both
would make `expected_judgment` mismatch the stored `judgment_id` and raise
`"judgment_id does not match decision inputs"` for every closure record — and
because `_validate_record_shape` runs inside `decision_record_to_json`,
`evaluate_decision_records`, and `append_decision_records`, this breaks the
Task 3 round-trip, evaluate, and suppress tests despite their "Expected: PASS".

So replace the single `refs` with `judgment_refs` (never includes the
fingerprint) and `decision_refs` (includes it for closure records).

Lane A branch — require the fingerprint absent, and set both refs to members:

```python
        if record.assertion_fingerprint is not None:
            raise DecisionRecordError("same_claim record must not have assertion_fingerprint")
        judgment_refs: Sequence[str] = record.members
        decision_refs: Sequence[str] = record.members
```

Lane B branch:

```python
        if record.decision == DECISION_ACCEPTED_SPARSE_HINTS:
            if record.assertion_fingerprint is None:
                raise DecisionRecordError("accepted_sparse_hints record must have assertion_fingerprint")
            judgment_refs = (record.proposition,)
            decision_refs = (record.proposition, record.assertion_fingerprint)
        else:
            if record.assertion_fingerprint is not None:
                raise DecisionRecordError("factorization record must not have assertion_fingerprint")
            judgment_refs = (record.proposition,)
            decision_refs = (record.proposition,)
```

Then use each ref set with the matching id:

```python
    expected_judgment = judgment_id(record.lane, record.decision, judgment_refs)
    if record.judgment_id != expected_judgment:
        raise DecisionRecordError("judgment_id does not match decision inputs")
    expected_decision = decision_record_id(
        record.lane, record.decision, record.judgment_id, record.candidate_id, decision_refs,
    )
    if record.decision_id != expected_decision:
        raise DecisionRecordError("decision_id does not match decision inputs")
```

This ensures `decision_id` includes the fingerprint for closure records while
`judgment_id` stays fingerprint-free, so re-review after fingerprint drift mints a
distinct `decision_id` and the record still shape-validates.

- [ ] **Step 4: Implement sparse-hint evaluation freshness**

In `evaluate_decision_records`, after resolving `factor`, before appending current:

```python
        if record.decision == DECISION_ACCEPTED_SPARSE_HINTS:
            if factor.recommended_action != "insufficient_hints":
                stale.append(StaleDecision(record, "candidate-no-longer-sparse-hints"))
                continue
            current_fingerprint = factorization_assertion_fingerprint(factor)
            if record.assertion_fingerprint != current_fingerprint:
                stale.append(StaleDecision(record, "assertion-fingerprint-changed"))
                continue
```

Leave `split_possible` behavior unchanged.

- [ ] **Step 5: Run focused decision tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_decisions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_decisions.py science/tests/test_proposition_reconciliation_decisions.py
rtk git commit -m "feat: persist sparse hint closure decisions"
```

---

## Task 4: CLI Flow And Report Suppression

**Files:**
- Modify: `science/tests/test_proposition_reconciliation_cli.py`
- Modify: `science/src/science_tool/annotation/cli.py` only if needed for output text.

- [ ] **Step 1: Add a CLI end-to-end test**

Append this test near the existing reviewed-decision CLI tests in `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_sparse_hint_closure_review_records_and_suppresses_candidate(tmp_path: Path):
    runner = CliRunner()
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "broad",
        "BES does not rescue underpowered studies by pooling data",
        subject="Bayesian Evidence Synthesis",
        predicate="associates_with",
        object="data-pooling rescue of underpowered studies",
        polarity="negative",
        source_refs=(
            "paper:A2020",
            "annotation:entities/papers/A2020.source#a1",
            "paper:B2021",
            "annotation:entities/papers/B2021.source#b1",
        ),
    )
    _paper_sidecar(
        tmp_path,
        "A2020",
        (_ann("a1", "proposition:broad"),),
    )
    _paper_sidecar(
        tmp_path,
        "B2021",
        (_ann("b1", "proposition:broad"),),
    )
    generated = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    assert generated.exit_code == 0, generated.output
    candidate = json.loads(generated.output)["factorization_disagreements"][0]
    assert candidate["recommended_action"] == "insufficient_hints"

    review = {
        "source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id(
                    "factorization_disagreement",
                    "accepted_sparse_hints",
                    [candidate["proposition"]],
                ),
                "lane": "factorization_disagreement",
                "decision": "accepted_sparse_hints",
                "proposition": candidate["proposition"],
                "rationale": "The proposition is already factored; sparse statement hints do not require mutation.",
                "confidence": "high",
            }
        ],
    }
    review_path = tmp_path / "sparse-review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan_path = tmp_path / "sparse-plan.json"

    validate_result = runner.invoke(
        annotate_group,
        [
            "validate-proposition-reconciliation",
            "--root",
            str(tmp_path),
            str(review_path),
            "--format",
            "json",
        ],
    )
    assert validate_result.exit_code == 0, validate_result.output

    plan_result = runner.invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output
    action_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert action_plan["actions"][0]["kind"] == "record_reconciliation_decision"
    assert action_plan["actions"][0]["inputs"]["assertion_fingerprint"].startswith("sha256:")

    record_result = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )
    assert record_result.exit_code == 0, record_result.output
    record_payload = json.loads(record_result.output)
    assert record_payload["summary"]["appended"] == 1

    suppressed = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    assert suppressed.exit_code == 0, suppressed.output
    suppressed_payload = json.loads(suppressed.output)
    assert suppressed_payload["summary"]["generated_factorization_disagreements"] == 1
    assert suppressed_payload["summary"]["factorization_disagreements"] == 0
    assert suppressed_payload["summary"]["reviewed_decisions"] == 1
    assert suppressed_payload["factorization_disagreements"] == []

    shown = runner.invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--all",
            "--show-reviewed",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert shown.exit_code == 0, shown.output
    shown_payload = json.loads(shown.output)
    assert shown_payload["summary"]["factorization_disagreements"] == 1
    assert shown_payload["factorization_disagreements"][0]["reviewed_decision_id"].startswith(
        "reconcile-decision:"
    )
```

- [ ] **Step 2: Run the CLI test and verify it fails before implementation or passes after Tasks 1-3**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_proposition_reconciliation_cli.py::test_sparse_hint_closure_review_records_and_suppresses_candidate -q
```

Expected after Tasks 1-3: PASS. If it fails, fix the module responsible for the failure rather than changing the test expectation.

- [ ] **Step 3: Run all reconciliation tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_decisions.py \
  science/tests/test_proposition_reconciliation_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
rtk git add science/tests/test_proposition_reconciliation_cli.py science/src/science_tool/annotation/cli.py
rtk git commit -m "test: cover sparse hint closure CLI flow"
```

If `science/src/science_tool/annotation/cli.py` was not modified, omit it from `git add`.

---

## Task 5: Real-Corpus Dogfood Closure

**Files:**
- Create: `meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json`
- Create: `meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json`
- Create or modify: `meta/results/proposition-reconciliation/decisions.jsonl`

- [ ] **Step 1: Confirm the two current candidates**

Run:

```bash
rtk uv run --frozen --project science science annotate reconcile-propositions --root meta --all --format json > /tmp/phase4f-reconcile-before.json
```

Expected: JSON summary has `factorization_disagreements: 2`, `faults: 0`, and both candidates have `recommended_action: "insufficient_hints"`.

Inspect:

```bash
rtk rg -n '"proposition"|"recommended_action"|"candidate_id"|"exact"' /tmp/phase4f-reconcile-before.json
```

- [ ] **Step 2: Write reviewed closure files**

Create `meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json`:

```json
{
  "source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
  "judgments": [
    {
      "candidate_id": "reconcile:factorization/3d258aa71a79219a27a4c1258106b072cd1f0f94b077e77adc18c4f3eec0dc46",
      "judgment_id": "reconcile:judgment/1a5941bea0e77cc87ae1deede1305c4950ca1003a9e5935515c937fa4f0a17d6",
      "lane": "factorization_disagreement",
      "decision": "accepted_sparse_hints",
      "proposition": "proposition:bes-does-not-rescue-underpowered-studies-by-pooling-data",
      "rationale": "The proposition is already factored in frontmatter; the remaining candidate reflects sparse statement-hint metadata on two concordant asserted annotations, not a reconciliation need.",
      "confidence": "high"
    }
  ]
}
```

Create `meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json`:

```json
{
  "source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
  "judgments": [
    {
      "candidate_id": "reconcile:factorization/121d907c080a2c073dc7e12d7bb4acf4c4d3e45381809c172a2c190d8ec02117",
      "judgment_id": "reconcile:judgment/ac806937c0f3b8c1ae054b44cccab34d438d71ccdf9bebd1beb5261dc0486579",
      "lane": "factorization_disagreement",
      "decision": "accepted_sparse_hints",
      "proposition": "proposition:conceptual-replication-evidence-can-be-aggregated-over-informative-hypotheses",
      "rationale": "The proposition intentionally makes a broad cross-method claim over BES and product Bayes factor examples; the current sparse-hint candidate reflects missing statement-hint metadata, not a current need to split or resynthesize the proposition.",
      "confidence": "medium"
    }
  ]
}
```

- [ ] **Step 3: Validate both review files**

Run:

```bash
rtk uv run --frozen --project science science annotate validate-proposition-reconciliation \
  --root meta \
  meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json \
  --format json
```

Run:

```bash
rtk uv run --frozen --project science science annotate validate-proposition-reconciliation \
  --root meta \
  meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json \
  --format json
```

Expected: both exit 0 with `"status": "ok"`.

- [ ] **Step 4: Plan and record both decisions**

Run:

```bash
rtk uv run --frozen --project science science annotate plan-proposition-reconciliation \
  --root meta \
  --input meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json \
  --input meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json \
  --output meta/results/proposition-reconciliation/2026-07-03-phase4f-sparse-hints-action-plan.json \
  --format json
```

Expected: action plan has two advisory `record_reconciliation_decision` actions and no top-level errors.

Dry-run:

```bash
rtk uv run --frozen --project science science annotate record-proposition-reconciliation-decisions \
  --root meta \
  --input meta/results/proposition-reconciliation/2026-07-03-phase4f-sparse-hints-action-plan.json \
  --format json
```

Expected: `would_append: 2`, `blockers: 0`.

Apply:

```bash
rtk uv run --frozen --project science science annotate record-proposition-reconciliation-decisions \
  --root meta \
  --input meta/results/proposition-reconciliation/2026-07-03-phase4f-sparse-hints-action-plan.json \
  --apply \
  --format json
```

Expected: `appended: 2`, `blockers: 0`.

- [ ] **Step 5: Verify corpus queue is quiet**

Run:

```bash
rtk uv run --frozen --project science science annotate reconcile-propositions --root meta --all --format json > /tmp/phase4f-reconcile-after.json
```

Expected:

- `summary.generated_factorization_disagreements == 2`
- `summary.factorization_disagreements == 0`
- `summary.reviewed_decisions == 2`
- `summary.faults == 0`

Run validation:

```bash
rtk env PYTHONPATH=meta/src uv run --frozen --project science science validate --project-root meta --profile commit --format json > /tmp/phase4f-meta-validate.json
```

Expected: command exits 0. Existing warnings are acceptable; errors must be 0.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
rtk git add meta/results/proposition-reconciliation/2026-07-03-bes-negative-sparse-hints-review.json \
  meta/results/proposition-reconciliation/2026-07-03-conceptual-replication-sparse-hints-review.json \
  meta/results/proposition-reconciliation/2026-07-03-phase4f-sparse-hints-action-plan.json \
  meta/results/proposition-reconciliation/decisions.jsonl
rtk git commit -m "data: record phase4f sparse hint closures"
```

---

## Task 6: Final Verification

**Files:**
- No new source files unless prior tasks reveal required CLI text changes.

- [ ] **Step 1: Run ruff on modified source and tests**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/annotation/proposition_reconciliation.py \
  science/src/science_tool/annotation/proposition_reconciliation_plan.py \
  science/src/science_tool/annotation/proposition_reconciliation_decisions.py \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_decisions.py \
  science/tests/test_proposition_reconciliation_cli.py
```

Expected: PASS.

- [ ] **Step 2: Run pyright on modified modules**

Run:

```bash
rtk uv run --frozen --project science pyright \
  science/src/science_tool/annotation/proposition_reconciliation.py \
  science/src/science_tool/annotation/proposition_reconciliation_plan.py \
  science/src/science_tool/annotation/proposition_reconciliation_decisions.py
```

Expected: PASS.

- [ ] **Step 3: Run focused test suite**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_decisions.py \
  science/tests/test_proposition_reconciliation_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run full tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests -q
```

Expected: PASS.

- [ ] **Step 5: Inspect final diff and status**

Run:

```bash
rtk git status --short
rtk git log --oneline -6
```

Expected: status is clean after commits. Recent commits include the Phase 4f implementation and dogfood closure records.

---

## Implementation Notes

- Do not add a separate closure log or waiver file. The existing `results/proposition-reconciliation/decisions.jsonl` remains the durable reviewed-decision store.
- Do not make `candidate-no-longer-sparse-hints` a load-time error. It is an evaluation-time stale reason because aged records must not break `load_decision_records`.
- Do not include `assertion_fingerprint` on existing `split_possible`, Lane A `related_but_distinct`, or Lane A `conflict_or_negation` records.
- Do not change belief aggregation, graph materialization, or sidecar/proposition mutation behavior.
- The intentionally stable factorization `candidate_id` is not enough freshness for sparse-hint closure. The closure `decision_id` must include the fingerprint so re-review after drift can append a new record.

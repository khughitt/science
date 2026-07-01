# Proposition Reconciliation Phase 4e Half B Action Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only `plan-proposition-reconciliation` surface that turns validated Phase 4e review judgments into deterministic, inspectable action plans.

**Architecture:** Keep Half A candidate generation and validation in `proposition_reconciliation.py`, extending it only with the current proposition snapshot map and a public review-resolution helper. Put Half B action-plan construction in a new focused module, `proposition_reconciliation_plan.py`, and wire it into a flat `annotate` CLI command. The planner writes no proposition, sidecar, or graph state; `--output` writes only the JSON plan artifact.

**Tech Stack:** Python 3.13, dataclasses, Click, existing `science_tool.annotation` CLI, existing `load_project_sources` / 4d scanner path, pytest, pyright, ruff.

---

## File Structure

- Modify `science/src/science_tool/annotation/proposition_reconciliation.py`
  - Add `ReconciliationReport.proposition_snapshots`.
  - Add resolved-review dataclasses.
  - Add `resolve_review_doc(doc, report)` so the planner does not duplicate private validation resolution.

- Create `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
  - Define action-plan dataclasses.
  - Define deterministic action IDs.
  - Map resolved review judgments to action rows.
  - Add report-fault errors, incomplete-review blockers, and cross-action conflict blockers.
  - Serialize the plan to stable JSON.

- Modify `science/src/science_tool/annotation/cli.py`
  - Add `annotate plan-proposition-reconciliation`.
  - Read one or more review JSON files.
  - Build the current reconciliation report once.
  - Print table or JSON output.
  - Optionally write the JSON action plan to `--output`.

- Create `science/tests/test_proposition_reconciliation_plan.py`
  - Unit coverage for the new planner and resolver contract.

- Modify `science/tests/test_proposition_reconciliation.py`
  - Focused tests for `proposition_snapshots` and `resolve_review_doc`.

- Modify `science/tests/test_proposition_reconciliation_cli.py`
  - CLI coverage for JSON, table, repeatable `--input`, `--output`, and invalid review rejection.

## Task 1: Extend Half A Report Snapshots And Review Resolution

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add failing tests for snapshot retention and review resolution**

Append these tests to `science/tests/test_proposition_reconciliation.py`:

```python
def test_reconciliation_report_can_carry_proposition_snapshots():
    snapshot = _prop(
        "proposition:a",
        "BRCA1 loss increases genomic instability",
        papers=frozenset({"paper:A2020"}),
    )
    report = ReconciliationReport(proposition_snapshots={snapshot.ref: snapshot})

    assert report.proposition_snapshots == {"proposition:a": snapshot}


def test_resolve_review_doc_returns_candidate_and_validation_payload():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }

    resolved = resolve_review_doc(doc, report)

    assert resolved.validation["status"] == "ok"
    assert resolved.validation["review_incomplete"] == []
    assert len(resolved.judgments) == 1
    assert resolved.judgments[0].candidate == candidate
    assert resolved.judgments[0].judgment["decision"] == "same_claim"


def test_resolve_review_doc_preserves_review_incomplete_payload():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate_id(
                    "same_claim", ["proposition:a", "proposition:b"]
                ),
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "The pair is a same-claim subset of the current component.",
                "confidence": "high",
            }
        ],
    }

    resolved = resolve_review_doc(doc, report)

    assert resolved.validation["review_incomplete"] == [
        {
            "candidate_id": report.same_claim_candidates[0].candidate_id,
            "missing": ["proposition:c"],
        }
    ]
    assert resolved.judgments[0].candidate == report.same_claim_candidates[0]
```

Add `resolve_review_doc` to the import list at the top of the same test file:

```python
from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    MAX_RECONCILIATION_COMPONENT_SIZE,
    PropositionSnapshot,
    ReconciliationReport,
    ReconciliationValidationError,
    build_factorization_disagreements,
    build_same_claim_candidates,
    candidate_id,
    candidate_to_json,
    judgment_id,
    normalize_phrase,
    polarity_compatible,
    predicate_compatible,
    report_to_json,
    resolve_review_doc,
    title_tokens,
    validate_review_doc,
)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL with `ImportError: cannot import name 'resolve_review_doc'` or `TypeError: ReconciliationReport.__init__() got an unexpected keyword argument 'proposition_snapshots'`.

- [ ] **Step 3: Add report snapshots and resolved review dataclasses**

In `science/src/science_tool/annotation/proposition_reconciliation.py`, update the import and dataclasses near the existing `ReconciliationReport`:

```python
from typing import Any, Literal
```

Keep the existing `typing` import if it already matches this line.

Replace the existing `ReconciliationReport` block with:

```python
@dataclass(frozen=True)
class ReconciliationReport:
    same_claim_candidates: tuple[SameClaimCandidate, ...] = ()
    factorization_disagreements: tuple[FactorizationCandidate, ...] = ()
    faults: tuple[ReconciliationFault, ...] = ()
    summary: Mapping[str, Any] = field(default_factory=dict)
    proposition_snapshots: Mapping[str, PropositionSnapshot] = field(default_factory=dict)
```

Add these dataclasses after `ReconciliationReport`:

```python
@dataclass(frozen=True)
class ResolvedReviewJudgment:
    review_source: str
    judgment: Mapping[str, Any]
    candidate: SameClaimCandidate | FactorizationCandidate


@dataclass(frozen=True)
class ResolvedReviewDoc:
    validation: Mapping[str, Any]
    judgments: tuple[ResolvedReviewJudgment, ...]
```

- [ ] **Step 4: Preserve snapshots in build_reconciliation_report**

In `build_reconciliation_report`, replace the return block with:

```python
    return ReconciliationReport(
        same_claim_candidates=same.candidates,
        factorization_disagreements=factors,
        faults=tuple(faults),
        proposition_snapshots=scoped_snapshots,
    )
```

This keeps scoped command behavior intact: `--all` stores all proposition snapshots, `--proposition` stores one, and `--source` stores propositions reachable from that source.

- [ ] **Step 5: Add resolve_review_doc**

Add this function after `validate_review_doc` in `science/src/science_tool/annotation/proposition_reconciliation.py`:

```python
def resolve_review_doc(doc: Any, report: ReconciliationReport) -> ResolvedReviewDoc:
    validation = validate_review_doc(doc, report)
    source = str(validation["source"])
    same_by_id, factor_by_id = _candidate_indexes(report)
    resolved: list[ResolvedReviewJudgment] = []

    for idx, judgment in enumerate(doc["judgments"]):
        lane = judgment["lane"]
        candidate_ref = judgment["candidate_id"]
        if lane == LANE_SAME_CLAIM:
            members = set(judgment["members"])
            candidate = _resolve_same_claim_candidate(
                candidate_ref,
                members,
                same_by_id,
                report.same_claim_candidates,
            )
            if candidate is None:
                raise ReconciliationValidationError(
                    f"judgments[{idx}].candidate_id is stale or unknown"
                )
            resolved.append(
                ResolvedReviewJudgment(
                    review_source=source,
                    judgment=judgment,
                    candidate=candidate,
                )
            )
        elif lane == LANE_FACTORIZATION:
            candidate = factor_by_id.get(candidate_ref)
            if candidate is None:
                raise ReconciliationValidationError(
                    f"judgments[{idx}].candidate_id is stale or unknown"
                )
            resolved.append(
                ResolvedReviewJudgment(
                    review_source=source,
                    judgment=judgment,
                    candidate=candidate,
                )
            )
        else:
            raise ReconciliationValidationError(f"judgments[{idx}].lane is not allowed")

    return ResolvedReviewDoc(validation=validation, judgments=tuple(resolved))
```

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): resolve reviewed reconciliation judgments"
```

Expected: commit succeeds with no `Co-Authored-By` trailer.

## Task 2: Core Action Plan Types And Factorization Mapping

**Files:**
- Create: `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
- Create: `science/tests/test_proposition_reconciliation_plan.py`

- [ ] **Step 1: Write failing tests for action IDs, report faults, and factorization actions**

Create `science/tests/test_proposition_reconciliation_plan.py` with this content:

```python
import hashlib
from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    PropositionSnapshot,
    ReconciliationFault,
    ReconciliationReport,
    candidate_id,
    judgment_id,
)
from science_tool.annotation.proposition_reconciliation_plan import (
    ReviewedReconciliationInput,
    action_plan_to_json,
    build_reconciliation_action_plan,
    reconciliation_action_id,
)


def _snapshot(ref: str) -> PropositionSnapshot:
    return PropositionSnapshot(
        ref=ref,
        title=ref,
        source_refs=frozenset({"paper:A2020", "annotation:entities/papers/A2020.source#a1"}),
        paper_refs=frozenset({"paper:A2020"}),
        annotation_refs=frozenset({"annotation:entities/papers/A2020.source#a1"}),
    )


def _factor_candidate(
    *,
    proposition: str = "proposition:p",
    candidate_ref: str | None = None,
    recommended_action: str = "factorization_needs_resynthesis",
) -> FactorizationCandidate:
    return FactorizationCandidate(
        candidate_id=candidate_ref
        or candidate_id("factorization_disagreement", [proposition]),
        proposition=proposition,
        priority="high",
        papers=("paper:A2020", "paper:B2021"),
        current={
            "subject": None,
            "predicate": None,
            "object": None,
            "polarity": None,
            "claim_layer": None,
        },
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
                "exact": "BES behaves similarly to meta-analysis in many settings.",
            },
            {
                "paper": "paper:B2021",
                "annotation": "annotation:entities/papers/B2021.source#b1",
                "stance": "negated",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "BES does not behave like data pooling.",
            },
        ),
        disagreement=("stance mix requires review",),
        recommended_action=recommended_action,
    )


def _factor_review(
    candidate: FactorizationCandidate,
    *,
    decision: str = "factorization_needs_resynthesis",
) -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement", decision, [candidate.proposition]
                ),
                "lane": "factorization_disagreement",
                "decision": decision,
                "proposition": candidate.proposition,
                "rationale": "This broad proposition bundles distinct claim families.",
                "confidence": "high",
            }
        ],
    }


def test_reconciliation_action_id_uses_full_sha256():
    expected = hashlib.sha256(
        b"resynthesize_proposition\x00reconcile:judgment:j1\x00proposition:p"
    ).hexdigest()

    assert reconciliation_action_id(
        "resynthesize_proposition",
        "reconcile:judgment:j1",
        "proposition:p",
    ) == f"reconcile-action:{expected}"


def test_factorization_review_maps_to_ready_resynthesis_action():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="results/proposition-reconciliation/review.json",
                doc=_factor_review(candidate),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "resynthesize_proposition"
    assert action.status == "ready"
    assert action.proposition == "proposition:p"
    assert action.decision == "factorization_needs_resynthesis"
    assert action.blockers == ()
    assert action.writes == ()
    assert action.inputs["annotations"] == (
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    )
    assert action.inputs["papers"] == ("paper:A2020", "paper:B2021")
    assert action.suggested_operations[0]["kind"] == "draft_proposition"


def test_report_faults_become_top_level_errors():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        faults=(ReconciliationFault("component-too-large", "26 propositions"),),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="review.json",
                doc=_factor_review(candidate),
            )
        ],
    )
    payload = action_plan_to_json(plan)

    assert payload["summary"]["ready_actions"] == 1
    assert payload["summary"]["errors"] == 1
    assert payload["errors"] == [
        {"reason": "component-too-large", "detail": "26 propositions", "members": []}
    ]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.proposition_reconciliation_plan'`.

- [ ] **Step 3: Create the action-plan module with dataclasses and serialization**

Create `science/src/science_tool/annotation/proposition_reconciliation_plan.py`:

```python
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    ReconciliationFault,
    ReconciliationReport,
    ResolvedReviewJudgment,
    SameClaimCandidate,
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
    suggested_operations: tuple[Mapping[str, str], ...] = ()
    preconditions: tuple[str, ...] = ()
    blockers: tuple[Mapping[str, str], ...] = ()
    writes: tuple[Any, ...] = ()


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


def _fault_to_error(fault: ReconciliationFault) -> Mapping[str, Any]:
    return {
        "reason": fault.reason,
        "detail": fault.detail,
        "members": list(fault.members),
    }


def _factorization_inputs(candidate: FactorizationCandidate) -> Mapping[str, Any]:
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
        "observed_statement_hints": tuple(
            dict(hint) for hint in candidate.observed_statement_hints
        ),
    }


def _factorization_suggestions(decision: str) -> tuple[Mapping[str, str], ...]:
    if decision == "factorization_needs_resynthesis":
        return (
            {
                "kind": "draft_proposition",
                "description": (
                    "Draft one or more narrower propositions from the reviewed "
                    "factorization disagreement and the observed statement hints."
                ),
            },
            {
                "kind": "draft_proposition",
                "description": (
                    "Use the reviewer rationale as context, but do not synthesize "
                    "new claim-family prose in the planner."
                ),
            },
            {
                "kind": "reassign_annotations",
                "description": (
                    "After new propositions are reviewed, move each annotation "
                    "backlink to the proposition it actually supports or disputes."
                ),
            },
        )
    if decision == "stance_review_needed":
        return (
            {
                "kind": "review_annotation_stance",
                "description": (
                    "Review the conflicting annotation stances before deciding "
                    "whether to split, resynthesize, or keep the proposition."
                ),
            },
        )
    if decision == "insufficient_hints":
        return (
            {
                "kind": "add_statement_factorization_hints",
                "description": (
                    "Add subject/object statement hints to the source annotations "
                    "before attempting semantic reconciliation."
                ),
            },
        )
    return (
        {
            "kind": "review_reconciliation_candidate",
            "description": "Review this reconciliation candidate manually before mutation.",
        },
    )


def _action_from_factorization(
    source_path: str,
    resolved: ResolvedReviewJudgment,
) -> ReconciliationAction:
    candidate = resolved.candidate
    if not isinstance(candidate, FactorizationCandidate):
        raise TypeError("resolved factorization judgment carried the wrong candidate type")
    judgment = resolved.judgment
    decision = str(judgment["decision"])
    judgment_ref = str(judgment["judgment_id"])
    proposition = candidate.proposition

    if decision == "factorization_needs_resynthesis":
        kind = "resynthesize_proposition"
        status: ActionStatus = "ready"
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
            "target proposition exists in the current reconciliation report",
        )
    elif decision == "stance_review_needed":
        kind = "review_annotation_stance"
        status = "blocked"
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
        )
    elif decision == "insufficient_hints":
        kind = "cleanup_factorization_hints"
        status = "advisory"
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
        )
    elif decision == "needs_human":
        kind = "needs_human_review"
        status = "blocked"
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
        )
    else:
        kind = "record_reconciliation_decision"
        status = "advisory"
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
        )

    return ReconciliationAction(
        action_id=reconciliation_action_id(kind, judgment_ref, proposition),
        kind=kind,
        status=status,
        decision=decision,
        candidate_id=candidate.candidate_id,
        judgment_id=judgment_ref,
        confidence=str(judgment["confidence"]),
        rationale=str(judgment["rationale"]),
        source_review=source_path,
        review_source=resolved.review_source,
        proposition=proposition,
        inputs=_factorization_inputs(candidate),
        suggested_operations=_factorization_suggestions(decision),
        preconditions=preconditions,
        blockers=()
        if status != "blocked"
        else (
            {
                "reason": decision,
                "detail": str(judgment["rationale"]),
            },
        ),
        writes=(),
    )


def _action_from_resolved(
    source_path: str,
    resolved: ResolvedReviewJudgment,
    report: ReconciliationReport,
) -> ReconciliationAction:
    lane = str(resolved.judgment["lane"])
    if lane == LANE_FACTORIZATION:
        return _action_from_factorization(source_path, resolved)
    raise NotImplementedError("same-claim action planning is added in Task 3")


def _sort_actions(actions: Sequence[ReconciliationAction]) -> tuple[ReconciliationAction, ...]:
    return tuple(sorted(actions, key=lambda action: action.action_id))


def build_reconciliation_action_plan(
    report: ReconciliationReport,
    reviews: Sequence[ReviewedReconciliationInput],
) -> ReconciliationActionPlan:
    source_reviews: list[str] = []
    actions: list[ReconciliationAction] = []

    for review in reviews:
        source_reviews.append(review.path)
        resolved = resolve_review_doc(review.doc, report)
        for item in resolved.judgments:
            actions.append(_action_from_resolved(review.path, item, report))

    return ReconciliationActionPlan(
        schema_version=SCHEMA_VERSION,
        source_reviews=tuple(source_reviews),
        actions=_sort_actions(actions),
        errors=tuple(_fault_to_error(fault) for fault in report.faults),
    )


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
        "inputs": dict(action.inputs),
        "suggested_operations": [dict(item) for item in action.suggested_operations],
        "preconditions": list(action.preconditions),
        "blockers": [dict(item) for item in action.blockers],
        "writes": list(action.writes),
    }
    if action.proposition is not None:
        payload["proposition"] = action.proposition
    if action.canonical_proposition is not None:
        payload["canonical_proposition"] = action.canonical_proposition
    if action.members:
        payload["members"] = list(action.members)
    return payload


def action_plan_to_json(plan: ReconciliationActionPlan) -> dict[str, Any]:
    ready = sum(1 for action in plan.actions if action.status == "ready")
    blocked = sum(1 for action in plan.actions if action.status == "blocked")
    advisory = sum(1 for action in plan.actions if action.status == "advisory")
    return {
        "schema_version": plan.schema_version,
        "source_reviews": list(plan.source_reviews),
        "summary": {
            "ready_actions": ready,
            "blocked_actions": blocked,
            "advisory_actions": advisory,
            "errors": len(plan.errors),
        },
        "actions": [_action_to_json(action) for action in plan.actions],
        "errors": [dict(error) for error in plan.errors],
    }
```

- [ ] **Step 4: Run the new tests and verify they pass**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_plan.py
rtk git commit -m "feat(4e): map reconciliation reviews to action plans"
```

Expected: commit succeeds.

## Task 3: Same-Claim Canonicalization Actions And Incomplete Review Blockers

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
- Modify: `science/tests/test_proposition_reconciliation_plan.py`

- [ ] **Step 1: Add failing tests for same-claim planning and incomplete-review blockers**

Append these helpers and tests to `science/tests/test_proposition_reconciliation_plan.py`:

```python
from science_tool.annotation.proposition_reconciliation import (
    build_same_claim_candidates,
)


def _same_claim_report() -> ReconciliationReport:
    left = PropositionSnapshot(
        ref="proposition:a",
        title="BRCA1 loss increases genomic instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset(
            {
                "paper:A2020",
                "annotation:entities/papers/A2020.source#a1",
            }
        ),
        paper_refs=frozenset({"paper:A2020"}),
        annotation_refs=frozenset({"annotation:entities/papers/A2020.source#a1"}),
    )
    right = PropositionSnapshot(
        ref="proposition:b",
        title="Loss of BRCA1 raises genome instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset(
            {
                "paper:B2021",
                "annotation:entities/papers/B2021.source#b1",
            }
        ),
        paper_refs=frozenset({"paper:B2021"}),
        annotation_refs=frozenset({"annotation:entities/papers/B2021.source#b1"}),
    )
    same = build_same_claim_candidates([left, right])
    return ReconciliationReport(
        same_claim_candidates=same.candidates,
        proposition_snapshots={left.ref: left, right.ref: right},
    )


def _same_claim_review(report: ReconciliationReport) -> dict:
    candidate = report.same_claim_candidates[0]
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "The propositions are the same signed claim.",
                "confidence": "high",
            }
        ],
    }


def test_same_claim_review_maps_to_canonicalization_action():
    report = _same_claim_report()

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="same-review.json", doc=_same_claim_review(report))],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "canonicalize_propositions"
    assert action.status == "ready"
    assert action.canonical_proposition == "proposition:a"
    assert action.members == ("proposition:a", "proposition:b")
    assert action.inputs["source_ref_moves"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "source_refs": (
                "annotation:entities/papers/B2021.source#b1",
                "paper:B2021",
            ),
        },
    )
    assert action.inputs["sidecar_backlink_rewrites"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "annotation_refs": ("annotation:entities/papers/B2021.source#b1",),
        },
    )
    assert action.writes == ()


def test_review_incomplete_blocks_same_claim_canonicalization():
    left = PropositionSnapshot(
        ref="proposition:a",
        title="BRCA1 loss increases genomic instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
    )
    middle = PropositionSnapshot(
        ref="proposition:b",
        title="Loss of BRCA1 raises genome instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
    )
    right = PropositionSnapshot(
        ref="proposition:c",
        title="BRCA1 loss promotes genomic instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset(
            {
                "paper:C2022",
                "annotation:entities/papers/C2022.source#c1",
            }
        ),
        paper_refs=frozenset({"paper:C2022"}),
        annotation_refs=frozenset({"annotation:entities/papers/C2022.source#c1"}),
    )
    same = build_same_claim_candidates([left, middle, right])
    report = ReconciliationReport(
        same_claim_candidates=same.candidates,
        proposition_snapshots={
            left.ref: left,
            middle.ref: middle,
            right.ref: right,
        },
    )
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate_id("same_claim", ["proposition:a", "proposition:b"]),
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "This subset is the same claim.",
                "confidence": "high",
            }
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="subset-review.json", doc=review)],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "canonicalize_propositions"
    assert action.status == "blocked"
    assert action.blockers == (
        {
            "reason": "review_incomplete",
            "detail": "candidate has unreviewed members: proposition:c",
        },
    )
    assert action.inputs["archive_candidates"] == ("proposition:b",)


def test_splittable_subset_canonicalization_inputs_exclude_non_members():
    left = PropositionSnapshot(
        ref="proposition:a",
        title="BRCA1 loss increases genomic instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset({"paper:A2020"}),
        paper_refs=frozenset({"paper:A2020"}),
    )
    middle = PropositionSnapshot(
        ref="proposition:b",
        title="Loss of BRCA1 raises genome instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset(
            {
                "paper:B2021",
                "annotation:entities/papers/B2021.source#b1",
            }
        ),
        paper_refs=frozenset({"paper:B2021"}),
        annotation_refs=frozenset({"annotation:entities/papers/B2021.source#b1"}),
    )
    right = PropositionSnapshot(
        ref="proposition:c",
        title="BRCA1 loss promotes genomic instability",
        subject="BRCA1 loss",
        predicate="affects",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset(
            {
                "paper:C2022",
                "annotation:entities/papers/C2022.source#c1",
            }
        ),
        paper_refs=frozenset({"paper:C2022"}),
        annotation_refs=frozenset({"annotation:entities/papers/C2022.source#c1"}),
    )
    same = build_same_claim_candidates([left, middle, right])
    report = ReconciliationReport(
        same_claim_candidates=same.candidates,
        proposition_snapshots={
            left.ref: left,
            middle.ref: middle,
            right.ref: right,
        },
    )
    candidate = report.same_claim_candidates[0]
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate_id("same_claim", ["proposition:a", "proposition:b"]),
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "This subset is the same claim.",
                "confidence": "high",
            },
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "related_but_distinct", ["proposition:c"]
                ),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": ["proposition:c"],
                "rationale": "The third proposition should remain separate.",
                "confidence": "medium",
            },
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="subset-review.json", doc=review)],
    )

    canonical = [
        action for action in plan.actions if action.kind == "canonicalize_propositions"
    ][0]
    assert canonical.status == "ready"
    assert canonical.inputs["source_ref_moves"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "source_refs": (
                "annotation:entities/papers/B2021.source#b1",
                "paper:B2021",
            ),
        },
    )
    assert canonical.inputs["archive_candidates"] == ("proposition:b",)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: FAIL with `NotImplementedError: same-claim action planning is added in Task 3`.

- [ ] **Step 3: Add same-claim action construction**

In `science/src/science_tool/annotation/proposition_reconciliation_plan.py`, add these helpers before `_action_from_resolved`:

```python
def _snapshot(report: ReconciliationReport, ref: str) -> Any:
    try:
        return report.proposition_snapshots[ref]
    except KeyError as exc:
        raise ValueError(f"missing proposition snapshot for {ref}") from exc


def _canonicalization_inputs(
    canonical: str,
    members: Sequence[str],
    report: ReconciliationReport,
) -> Mapping[str, Any]:
    duplicates = tuple(ref for ref in members if ref != canonical)
    source_ref_moves = []
    sidecar_backlink_rewrites = []
    archive_candidates = []

    for duplicate in duplicates:
        snapshot = _snapshot(report, duplicate)
        source_ref_moves.append(
            {
                "from": duplicate,
                "to": canonical,
                "source_refs": tuple(sorted(snapshot.source_refs)),
            }
        )
        sidecar_backlink_rewrites.append(
            {
                "from": duplicate,
                "to": canonical,
                "annotation_refs": tuple(sorted(snapshot.annotation_refs)),
            }
        )
        archive_candidates.append(duplicate)

    return {
        "source_ref_moves": tuple(source_ref_moves),
        "sidecar_backlink_rewrites": tuple(sidecar_backlink_rewrites),
        "archive_candidates": tuple(archive_candidates),
    }


def _same_claim_suggestions() -> tuple[Mapping[str, str], ...]:
    return (
        {
            "kind": "move_source_refs",
            "description": (
                "Move duplicate proposition source refs onto the reviewed canonical "
                "proposition in a future apply phase."
            ),
        },
        {
            "kind": "rewrite_promoted_to",
            "description": (
                "Rewrite duplicate annotation backlinks to the reviewed canonical "
                "proposition in a future apply phase."
            ),
        },
        {
            "kind": "archive_duplicate_propositions",
            "description": (
                "Archive or redirect duplicate propositions only after source refs "
                "and backlinks have been moved."
            ),
        },
    )


def _action_from_same_claim(
    source_path: str,
    resolved: ResolvedReviewJudgment,
    report: ReconciliationReport,
) -> ReconciliationAction:
    candidate = resolved.candidate
    if not isinstance(candidate, SameClaimCandidate):
        raise TypeError("resolved same-claim judgment carried the wrong candidate type")
    judgment = resolved.judgment
    decision = str(judgment["decision"])
    judgment_ref = str(judgment["judgment_id"])
    members = tuple(sorted(str(member) for member in judgment["members"]))

    if decision == "same_claim":
        canonical = str(judgment["canonical_proposition"])
        kind = "canonicalize_propositions"
        status: ActionStatus = "ready"
        primary_ref = canonical
        secondary_refs = tuple(member for member in members if member != canonical)
        inputs = _canonicalization_inputs(canonical, members, report)
        suggestions = _same_claim_suggestions()
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
            "all member propositions exist in the current reconciliation snapshot",
        )
        blockers: tuple[Mapping[str, str], ...] = ()
    else:
        canonical = None
        kind = "record_reconciliation_decision"
        status = "advisory"
        primary_ref = candidate.candidate_id
        secondary_refs = members
        inputs = {"members": members, "flags": tuple(candidate.flags)}
        suggestions = (
            {
                "kind": "record_non_merge_decision",
                "description": "Record the reviewed non-merge decision for future candidate suppression.",
            },
        )
        preconditions = (
            "review judgment validates against the current reconciliation candidate",
        )
        blockers = ()

    return ReconciliationAction(
        action_id=reconciliation_action_id(kind, judgment_ref, primary_ref, secondary_refs),
        kind=kind,
        status=status,
        decision=decision,
        candidate_id=candidate.candidate_id,
        judgment_id=judgment_ref,
        confidence=str(judgment["confidence"]),
        rationale=str(judgment["rationale"]),
        source_review=source_path,
        review_source=resolved.review_source,
        proposition=None,
        canonical_proposition=canonical,
        members=members,
        inputs=inputs,
        suggested_operations=suggestions,
        preconditions=preconditions,
        blockers=blockers,
        writes=(),
    )
```

Replace `_action_from_resolved` with:

```python
def _action_from_resolved(
    source_path: str,
    resolved: ResolvedReviewJudgment,
    report: ReconciliationReport,
) -> ReconciliationAction:
    lane = str(resolved.judgment["lane"])
    if lane == LANE_FACTORIZATION:
        return _action_from_factorization(source_path, resolved)
    if lane == LANE_SAME_CLAIM:
        return _action_from_same_claim(source_path, resolved, report)
    raise ValueError(f"unsupported reconciliation lane: {lane}")
```

- [ ] **Step 4: Add incomplete-review blockers**

In `science/src/science_tool/annotation/proposition_reconciliation_plan.py`, update the dataclass import:

```python
from dataclasses import dataclass, field, replace
```

Then add this helper before `build_reconciliation_action_plan`:

```python
def _with_blocker(
    action: ReconciliationAction,
    *,
    reason: str,
    detail: str,
) -> ReconciliationAction:
    blockers = (*action.blockers, {"reason": reason, "detail": detail})
    return replace(action, status="blocked", blockers=blockers)


def _apply_incomplete_review_blockers(
    actions: Sequence[ReconciliationAction],
    incomplete: Sequence[Mapping[str, Any]],
) -> tuple[ReconciliationAction, ...]:
    missing_by_candidate = {
        str(item["candidate_id"]): tuple(str(ref) for ref in item["missing"])
        for item in incomplete
    }
    out: list[ReconciliationAction] = []
    for action in actions:
        missing = missing_by_candidate.get(action.candidate_id)
        if missing and action.kind == "canonicalize_propositions":
            out.append(
                _with_blocker(
                    action,
                    reason="review_incomplete",
                    detail=f"candidate has unreviewed members: {', '.join(missing)}",
                )
            )
        else:
            out.append(action)
    return tuple(out)
```

Then update `build_reconciliation_action_plan` to collect validation incompletes:

```python
def build_reconciliation_action_plan(
    report: ReconciliationReport,
    reviews: Sequence[ReviewedReconciliationInput],
) -> ReconciliationActionPlan:
    source_reviews: list[str] = []
    actions: list[ReconciliationAction] = []
    incomplete: list[Mapping[str, Any]] = []

    for review in reviews:
        source_reviews.append(review.path)
        resolved = resolve_review_doc(review.doc, report)
        incomplete.extend(resolved.validation["review_incomplete"])
        for item in resolved.judgments:
            actions.append(_action_from_resolved(review.path, item, report))

    blocked_for_incomplete = _apply_incomplete_review_blockers(actions, incomplete)
    return ReconciliationActionPlan(
        schema_version=SCHEMA_VERSION,
        source_reviews=tuple(source_reviews),
        actions=_sort_actions(blocked_for_incomplete),
        errors=tuple(_fault_to_error(fault) for fault in report.faults),
    )
```

- [ ] **Step 5: Run the tests and verify they pass**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_plan.py
rtk git commit -m "feat(4e): plan same-claim reconciliation actions"
```

Expected: commit succeeds.

## Task 4: Advisory Decisions And Cross-Action Conflict Blockers

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
- Modify: `science/tests/test_proposition_reconciliation_plan.py`

- [ ] **Step 1: Add failing tests for advisory decisions and action conflicts**

Append these tests to `science/tests/test_proposition_reconciliation_plan.py`:

```python
def test_stance_review_needed_maps_to_blocked_action():
    candidate = _factor_candidate(recommended_action="stance_review_needed")
    review = _factor_review(candidate, decision="stance_review_needed")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="stance-review.json", doc=review)],
    )

    assert plan.actions[0].kind == "review_annotation_stance"
    assert plan.actions[0].status == "blocked"
    assert plan.actions[0].blockers == (
        {
            "reason": "stance_review_needed",
            "detail": "This broad proposition bundles distinct claim families.",
        },
    )


def test_insufficient_hints_maps_to_advisory_action():
    candidate = _factor_candidate(recommended_action="insufficient_hints")
    review = _factor_review(candidate, decision="insufficient_hints")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="hint-review.json", doc=review)],
    )

    assert plan.actions[0].kind == "cleanup_factorization_hints"
    assert plan.actions[0].status == "advisory"


def test_conflicting_actions_for_same_proposition_are_both_blocked():
    candidate = _factor_candidate()
    resynthesis_review = _factor_review(candidate)
    needs_human_review = _factor_review(candidate, decision="needs_human")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(path="resynthesis.json", doc=resynthesis_review),
            ReviewedReconciliationInput(path="human.json", doc=needs_human_review),
        ],
    )

    assert len(plan.actions) == 2
    assert {action.status for action in plan.actions} == {"blocked"}
    for action in plan.actions:
        assert any(blocker["reason"] == "action_conflict" for blocker in action.blockers)


def test_actions_are_sorted_by_action_id():
    candidate_a = _factor_candidate(proposition="proposition:a")
    candidate_b = _factor_candidate(proposition="proposition:b")
    report = ReconciliationReport(
        factorization_disagreements=(candidate_b, candidate_a),
        proposition_snapshots={
            "proposition:a": _snapshot("proposition:a"),
            "proposition:b": _snapshot("proposition:b"),
        },
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(path="b.json", doc=_factor_review(candidate_b)),
            ReviewedReconciliationInput(path="a.json", doc=_factor_review(candidate_a)),
        ],
    )

    assert [action.action_id for action in plan.actions] == sorted(
        action.action_id for action in plan.actions
    )


def test_duplicate_reviewed_actions_are_blocked():
    candidate = _factor_candidate()
    review = _factor_review(candidate)
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={"proposition:p": _snapshot("proposition:p")},
    )

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(path="one.json", doc=review),
            ReviewedReconciliationInput(path="two.json", doc=review),
        ],
    )

    assert len(plan.actions) == 2
    assert {action.status for action in plan.actions} == {"blocked"}
    for action in plan.actions:
        assert action.blockers == (
            {
                "reason": "action_conflict",
                "detail": "duplicate action produced by multiple reviewed inputs",
            },
        )


def test_same_claim_advisory_conflicts_with_ready_canonicalization():
    report = _same_claim_report()
    candidate = report.same_claim_candidates[0]
    same_claim_review = _same_claim_review(report)
    advisory_review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "related_but_distinct", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": list(candidate.propositions),
                "rationale": "These should not be merged despite lexical similarity.",
                "confidence": "medium",
            }
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(path="merge.json", doc=same_claim_review),
            ReviewedReconciliationInput(path="no-merge.json", doc=advisory_review),
        ],
    )

    assert len(plan.actions) == 2
    assert {action.status for action in plan.actions} == {"blocked"}
    for action in plan.actions:
        assert any(blocker["reason"] == "action_conflict" for blocker in action.blockers)
```

- [ ] **Step 2: Run the tests and verify the conflict test fails**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: FAIL in `test_conflicting_actions_for_same_proposition_are_both_blocked` because conflicts are not applied yet.

- [ ] **Step 3: Add action-target and conflict helpers**

In `science/src/science_tool/annotation/proposition_reconciliation_plan.py`, add these helpers before `build_reconciliation_action_plan`:

```python
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
    for ref, ref_actions in by_ref.items():
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
```

Update `build_reconciliation_action_plan` so it applies conflict blockers after incomplete blockers:

```python
    blocked_for_incomplete = _apply_incomplete_review_blockers(actions, incomplete)
    blocked_for_conflicts = _apply_cross_action_conflicts(blocked_for_incomplete)
    return ReconciliationActionPlan(
        schema_version=SCHEMA_VERSION,
        source_reviews=tuple(source_reviews),
        actions=_sort_actions(blocked_for_conflicts),
        errors=tuple(_fault_to_error(fault) for fault in report.faults),
    )
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_plan.py
rtk git commit -m "feat(4e): block conflicting reconciliation actions"
```

Expected: commit succeeds.

## Task 5: CLI Command For Planning Proposition Reconciliation

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append these tests to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def _review_for_candidate(candidate: dict, *, canonical: str = "proposition:a") -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "same_claim", candidate["propositions"]),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": canonical,
                "members": candidate["propositions"],
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }


def test_plan_proposition_reconciliation_cli_json(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["summary"]["ready_actions"] == 1
    assert payload["actions"][0]["kind"] == "canonicalize_propositions"
    assert payload["actions"][0]["writes"] == []


def test_plan_proposition_reconciliation_cli_table_and_output(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")
    output_path = tmp_path / "plan.json"

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "proposition reconciliation action plan:" in result.output
    assert "canonicalize_propositions" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["ready_actions"] == 1


def test_plan_proposition_reconciliation_cli_accepts_repeated_input(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_a = tmp_path / "review-a.json"
    review_b = tmp_path / "review-b.json"
    review_a.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")
    review_b.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_a),
            "--input",
            str(review_b),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_reviews"] == [str(review_a), str(review_b)]
    assert payload["summary"]["blocked_actions"] == 2


def test_plan_proposition_reconciliation_cli_rejects_empty_review_even_with_valid_input(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    valid_review = tmp_path / "valid-review.json"
    empty_review = tmp_path / "empty-review.json"
    valid_review.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")
    empty_review.write_text(
        json.dumps({"source": "llm-review:claude:proposition-reconcile-v1", "judgments": []}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(valid_review),
            "--input",
            str(empty_review),
        ],
    )

    assert result.exit_code != 0
    assert f"{empty_review} produced no judgments" in result.output


def test_plan_proposition_reconciliation_cli_rejects_invalid_review(tmp_path: Path):
    _manifest(tmp_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps({"source": "llm-review:claude:proposition-reconcile-v1", "judgments": []}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
        ],
    )

    assert result.exit_code != 0
    assert f"{review_path} produced no judgments" in result.output
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_cli.py -q
```

Expected: FAIL with `No such command 'plan-proposition-reconciliation'`.

- [ ] **Step 3: Reject empty review inputs in the core planner**

In `science/src/science_tool/annotation/proposition_reconciliation_plan.py`, add this validation inside the review loop in `build_reconciliation_action_plan`, immediately after `resolved = resolve_review_doc(review.doc, report)`:

```python
        if not resolved.judgments:
            raise ValueError(f"{review.path} produced no judgments")
```

The CLI will convert this `ValueError` to a Click error.

- [ ] **Step 4: Add the CLI command**

In `science/src/science_tool/annotation/cli.py`, add this command after `validate_proposition_reconciliation_cmd`:

```python
@annotate_group.command("plan-proposition-reconciliation")
@click.option(
    "--input",
    "input_paths",
    required=True,
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
)
def plan_proposition_reconciliation_cmd(
    input_paths: tuple[Path, ...],
    root: Path | None,
    fmt: str,
    output_path: Path | None,
) -> None:
    """Build a read-only action plan from reviewed proposition reconciliation artifacts."""
    from science_tool.annotation.proposition_reconciliation import (
        ReconciliationValidationError,
        build_reconciliation_report,
    )
    from science_tool.annotation.proposition_reconciliation_plan import (
        ReviewedReconciliationInput,
        action_plan_to_json,
        build_reconciliation_action_plan,
    )

    project_root = (root or Path.cwd()).resolve()
    reviews: list[ReviewedReconciliationInput] = []
    for input_path in input_paths:
        try:
            doc = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"{input_path} is not valid JSON: {exc}") from exc
        reviews.append(ReviewedReconciliationInput(path=str(input_path), doc=doc))

    report = build_reconciliation_report(project_root)
    try:
        plan = build_reconciliation_action_plan(report, reviews)
    except (ReconciliationValidationError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = action_plan_to_json(plan)
    json_text = json.dumps(payload, indent=2, sort_keys=True)
    if output_path is not None:
        output_path.write_text(json_text + "\n", encoding="utf-8")

    if fmt == "json":
        click.echo(json_text)
        return

    summary = payload["summary"]
    click.echo(
        "proposition reconciliation action plan: "
        f"ready={summary['ready_actions']} "
        f"blocked={summary['blocked_actions']} "
        f"advisory={summary['advisory_actions']} "
        f"errors={summary['errors']}"
    )
    for action in payload["actions"]:
        target = (
            action.get("proposition")
            or action.get("canonical_proposition")
            or ",".join(action.get("members", []))
            or action["candidate_id"]
        )
        click.echo(f"{action['status']:8s} {action['kind']} {target}")
    if output_path is not None:
        click.echo(f"wrote JSON action plan to {output_path}")
```

- [ ] **Step 5: Run CLI tests and verify they pass**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Run core planner tests and verify the empty-review guard did not regress**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_plan.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
rtk git add science/src/science_tool/annotation/cli.py science/src/science_tool/annotation/proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): add reconciliation action plan CLI"
```

Expected: commit succeeds.

## Task 6: Regression Net, Static Checks, And Real-Corpus Smoke

**Files:**
- Modify if needed: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify if needed: `science/src/science_tool/annotation/proposition_reconciliation_plan.py`
- Modify if needed: `science/src/science_tool/annotation/cli.py`
- Modify if needed: `science/tests/test_proposition_reconciliation.py`
- Modify if needed: `science/tests/test_proposition_reconciliation_plan.py`
- Modify if needed: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Run the combined reconciliation test suite**

Run:

```bash
cd science && rtk uv run --frozen pytest \
  tests/test_proposition_reconciliation.py \
  tests/test_proposition_reconciliation_plan.py \
  tests/test_proposition_reconciliation_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run pyright on touched Python modules**

Run:

```bash
cd science && rtk uv run --frozen pyright \
  src/science_tool/annotation/proposition_reconciliation.py \
  src/science_tool/annotation/proposition_reconciliation_plan.py \
  src/science_tool/annotation/cli.py
```

Expected: `0 errors, 0 warnings, 0 informations`.

- [ ] **Step 3: Run ruff on touched Python files**

Run:

```bash
cd science && rtk uv run --frozen ruff check \
  src/science_tool/annotation/proposition_reconciliation.py \
  src/science_tool/annotation/proposition_reconciliation_plan.py \
  src/science_tool/annotation/cli.py \
  tests/test_proposition_reconciliation.py \
  tests/test_proposition_reconciliation_plan.py \
  tests/test_proposition_reconciliation_cli.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run the real-corpus Half B smoke**

Run:

```bash
cd meta && PYTHONPATH=../science/src:../science/model/src rtk uv run --frozen --project ../science \
  science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json \
  --format json
```

Expected: command exits 0 if the committed review still matches the current generated
BES factorization candidate. If it exits non-zero with a stale-candidate validation
message, stop and inspect the current `reconcile-propositions --proposition
proposition:bes-behaves-like-pooled-meta-analysis --format json` output before changing
Half B code.

When the command exits 0, inspect these JSON properties:

```json
{
  "schema_version": 1
}
```

There should be at least one action for the reviewed BES proposition, and that action
should have:

```json
{
  "kind": "resynthesize_proposition",
  "status": "ready",
  "decision": "factorization_needs_resynthesis",
  "proposition": "proposition:bes-behaves-like-pooled-meta-analysis",
  "writes": []
}
```

Do not treat a non-zero top-level `summary.errors` as a Half B failure by itself:
`errors` reflects current project-wide reconciliation faults such as scanner faults or
oversized components.

- [ ] **Step 5: Run the real-corpus output-file smoke**

Run:

```bash
cd meta && PYTHONPATH=../science/src:../science/model/src rtk uv run --frozen --project ../science \
  science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json \
  --output /tmp/phase4e-half-b-action-plan.json
python -m json.tool /tmp/phase4e-half-b-action-plan.json >/tmp/phase4e-half-b-action-plan.pretty.json
```

Expected: both commands exit 0 if the committed review still matches the current
candidate graph. The table output should include `proposition reconciliation action
plan:`, and `/tmp/phase4e-half-b-action-plan.pretty.json` should exist. Inspect the
summary counts instead of pinning them to exact corpus-wide values.

- [ ] **Step 6: Inspect git diff for accidental writes**

Run:

```bash
rtk git status --short --branch
rtk git diff --stat
```

Expected: only intended source and test files are modified. No proposition files, sidecars, graph files, or meta result files should be changed by the new command.

- [ ] **Step 7: Commit final regressions if fixes were needed**

If Steps 1-6 required code or test changes after Task 5, run:

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py \
  science/src/science_tool/annotation/proposition_reconciliation_plan.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "fix(4e): stabilize reconciliation action planner"
```

Expected: commit succeeds. If no files changed after Task 5, skip this step.

## Acceptance Checklist

- `science annotate plan-proposition-reconciliation --input review.json --format json` emits a versioned plan with `summary`, `actions`, and `errors`.
- `--input` is repeatable.
- `--output` writes only a JSON plan artifact.
- The planner uses `resolve_review_doc`; it does not duplicate private candidate-resolution logic.
- `ReconciliationReport.proposition_snapshots` is populated by `build_reconciliation_report`.
- `review_incomplete` blocks same-claim canonicalization actions.
- `ReconciliationReport.faults` populate top-level `errors`.
- Cross-action conflicts block every involved action.
- All action IDs are full SHA-256 refs and action ordering is deterministic by `action_id`.
- Every action has `writes: []`.
- The BES review in `meta/results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json` produces one ready `resynthesize_proposition` action.

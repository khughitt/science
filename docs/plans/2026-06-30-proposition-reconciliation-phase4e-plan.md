# Proposition Reconciliation Phase 4e Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 4e Half A: deterministic proposition reconciliation candidates, agent-facing review scaffold, and strict reviewed-file validation, without rewriting propositions or changing belief aggregation.

**Architecture:** Extend the existing 4d scanner with statement context so all reconciliation lanes share one sidecar parser. Add a focused `annotation/proposition_reconciliation.py` module that loads proposition snapshots, builds Lane A same-claim groups and Lane B factorization diagnostics, validates reviewed judgments, and exposes JSON/table/scaffold payloads. Add two flat `science annotate` commands: `reconcile-propositions` for generation and `validate-proposition-reconciliation` for reviewed-file validation.

**Tech Stack:** Python 3.13, dataclasses, Click, `rdflib`-backed existing graph utilities, `science_model.reasoning` enums, pytest, pyright. Design spec: `docs/plans/2026-06-30-proposition-reconciliation-phase4e-design.md`.

---

## File Structure

Create:

- `science/src/science_tool/annotation/proposition_reconciliation.py` - all Phase 4e candidate generation, deterministic IDs, review validation, and report serialization.
- `science/tests/test_proposition_reconciliation.py` - core unit tests for IDs, predicate/polarity compatibility, Lane A grouping, Lane B diagnostics, and review validation.
- `science/tests/test_proposition_reconciliation_cli.py` - CLI shape tests for generation and reviewed-file validation.

Modify:

- `science/src/science_tool/annotation/cross_paper_evidence.py` - append statement context fields to `LiteratureAssertion`; parse the statement JSON once in the shared scanner.
- `science/src/science_tool/annotation/cli.py` - add flat `reconcile-propositions` and `validate-proposition-reconciliation` commands to `annotate_group`.
- `science/tests/test_cross_paper_evidence.py` - update constructor helpers and add scanner coverage for the new statement context fields.
- `science/tests/test_cross_paper_evidence_materialize.py` - update positional `LiteratureAssertion` fixture calls if any remain.

Do not modify:

- Belief aggregation modules.
- Proposition entity model fields.
- Sidecar `promoted_to` values.
- Entity archive/alias machinery.

---

## Task 1: Extend 4d Literature Assertions With Statement Context

**Files:**
- Modify: `science/src/science_tool/annotation/cross_paper_evidence.py`
- Modify: `science/tests/test_cross_paper_evidence.py`
- Modify: `science/tests/test_cross_paper_evidence_materialize.py`

- [ ] **Step 1: Add failing scanner test for statement context**

Append this test to `science/tests/test_cross_paper_evidence.py`:

```python
def test_scan_literature_assertions_carries_statement_context(tmp_path: Path):
    body = _json.dumps(
        {
            "section": "results",
            "stance": "asserted",
            "subject": "BRCA1 loss",
            "object": "genomic instability",
            "subject_concept": "https://identifiers.org/ncbigene:672",
            "object_concept": "concept:genomic-instability",
        }
    )
    ann = _ann("a-1", stance="asserted")
    rich_ann = Annotation(
        id=ann.id,
        target=SpecificResource(
            source=ann.target.source,
            selector=TextQuoteSelector(
                exact="BRCA1 loss increases genomic instability",
                prefix="",
                suffix="",
            ),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=ann.motivation,
        annotation_type=ann.annotation_type,
        source=ann.source,
        status=ann.status,
        creator=ann.creator,
        created=ann.created,
        content_hash=ann.content_hash,
        promoted_to=ann.promoted_to,
    )
    _write_paper_sidecar(tmp_path, "Smith2020", [rich_ann])
    refs = {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert faults == []
    assert len(assertions) == 1
    assertion = assertions[0]
    assert assertion.statement_exact == "BRCA1 loss increases genomic instability"
    assert assertion.section == "results"
    assert assertion.subject == "BRCA1 loss"
    assert assertion.object == "genomic instability"
    assert assertion.subject_concept == "https://identifiers.org/ncbigene:672"
    assert assertion.object_concept == "concept:genomic-instability"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_cross_paper_evidence.py::test_scan_literature_assertions_carries_statement_context -q
```

Expected: FAIL with `AttributeError: 'LiteratureAssertion' object has no attribute 'statement_exact'`.

- [ ] **Step 3: Extend `LiteratureAssertion` with appended fields**

In `science/src/science_tool/annotation/cross_paper_evidence.py`, append fields after `annotation_ref` so existing positional constructor churn is minimized:

```python
@dataclass(frozen=True)
class LiteratureAssertion:
    proposition_ref: str
    paper_ref: str
    stance: str
    annotation_id: str
    sidecar: str
    annotation_ref: str
    statement_exact: str = ""
    section: str = ""
    subject: str | None = None
    object: str | None = None
    subject_concept: str | None = None
    object_concept: str | None = None
```

Add this helper near `_statement_stance`:

```python
def _statement_context(ann) -> dict[str, str | None]:
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            try:
                data = json.loads(body.value)
            except json.JSONDecodeError:
                return {}
            if not isinstance(data, dict):
                return {}
            return {
                "section": str(data.get("section", "")),
                "subject": data.get("subject") if isinstance(data.get("subject"), str) else None,
                "object": data.get("object") if isinstance(data.get("object"), str) else None,
                "subject_concept": (
                    data.get("subject_concept") if isinstance(data.get("subject_concept"), str) else None
                ),
                "object_concept": (
                    data.get("object_concept") if isinstance(data.get("object_concept"), str) else None
                ),
            }
    return {}
```

In `scan_literature_assertions`, immediately before appending `LiteratureAssertion`, compute:

```python
            context = _statement_context(ann)
```

Then pass the new fields:

```python
            assertions.append(
                LiteratureAssertion(
                    proposition_ref=ann.promoted_to,
                    paper_ref=paper_ref,
                    stance=stance,
                    annotation_id=ann.id,
                    sidecar=sidecar_ref,
                    annotation_ref=ann_ref,
                    statement_exact=ann.target.selector.exact,
                    section=str(context.get("section") or ""),
                    subject=context.get("subject"),
                    object=context.get("object"),
                    subject_concept=context.get("subject_concept"),
                    object_concept=context.get("object_concept"),
                )
            )
```

- [ ] **Step 4: Run the cross-paper evidence tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_materialize.py -q
```

Expected: PASS. During this step, update every `LiteratureAssertion(...)` fixture in `test_cross_paper_evidence_materialize.py` to use keyword arguments. Keep the new context fields omitted there so the defaults prove old materialization behavior is unchanged.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence.py science/tests/test_cross_paper_evidence_materialize.py
rtk git commit -m "feat(4e): carry statement context on literature assertions"
```

---

## Task 2: Core Reconciliation Types, IDs, and Compatibility

**Files:**
- Create: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Create: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Write failing tests for deterministic IDs and compatibility**

Create `science/tests/test_proposition_reconciliation.py` with:

```python
import hashlib

from science_tool.annotation.proposition_reconciliation import (
    candidate_id,
    judgment_id,
    normalize_phrase,
    polarity_compatible,
    predicate_compatible,
    title_tokens,
)


def test_candidate_id_uses_full_sha256_of_lane_and_sorted_refs():
    expected = hashlib.sha256(b"same_claim\x00proposition:a\x00proposition:b").hexdigest()
    assert candidate_id("same_claim", ["proposition:b", "proposition:a"]) == (
        f"reconcile:same-claim/{expected}"
    )


def test_judgment_id_uses_lane_decision_and_sorted_member_set():
    expected = hashlib.sha256(
        b"same_claim\x00same_claim\x00proposition:a\x00proposition:b"
    ).hexdigest()
    assert judgment_id("same_claim", "same_claim", ["proposition:b", "proposition:a"]) == (
        f"reconcile:judgment/{expected}"
    )


def test_normalize_phrase_casefolds_and_collapses_whitespace():
    assert normalize_phrase("  BRCA1   Loss ") == "brca1 loss"


def test_predicate_compatibility_is_small_and_enum_tied():
    assert predicate_compatible("affects", "affects") is True
    assert predicate_compatible("affects", "regulates") is True
    assert predicate_compatible("associates_with", "regulates") is True
    assert predicate_compatible("subtype_of", "part_of") is False
    assert predicate_compatible("induces_state", "transitions_to") is False
    assert predicate_compatible(None, "affects") is False


def test_polarity_compatibility_allows_unsigned_but_not_opposite_signs():
    assert polarity_compatible("positive", "positive") is True
    assert polarity_compatible("positive", "unsigned") is True
    assert polarity_compatible("negative", "unsigned") is True
    assert polarity_compatible("positive", "negative") is False
    assert polarity_compatible("not_applicable", "not_applicable") is True


def test_title_tokens_remove_stopwords_and_short_tokens():
    assert title_tokens("The BRCA1 loss affects genomic instability in cells") == {
        "brca1",
        "loss",
        "affects",
        "genomic",
        "instability",
        "cells",
    }
```

- [ ] **Step 2: Run tests to verify module is missing**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.proposition_reconciliation'`.

- [ ] **Step 3: Create the module skeleton**

Create `science/src/science_tool/annotation/proposition_reconciliation.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from science_model.reasoning import SIGN_MEANINGFUL_PREDICATES


LANE_SAME_CLAIM = "same_claim"
LANE_FACTORIZATION = "factorization_disagreement"
MAX_RECONCILIATION_COMPONENT_SIZE = 25

DECISIONS = frozenset(
    {
        "same_claim",
        "related_but_distinct",
        "conflict_or_negation",
        "factorization_needs_resynthesis",
        "stance_review_needed",
        "split_possible",
        "insufficient_hints",
        "needs_human",
    }
)
LANE_B_DECISIONS = frozenset(
    {
        "factorization_needs_resynthesis",
        "stance_review_needed",
        "split_possible",
        "insufficient_hints",
        "needs_human",
    }
)
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "onto",
        "than",
        "then",
        "when",
        "where",
        "which",
        "while",
    }
)


@dataclass(frozen=True)
class PropositionSnapshot:
    ref: str
    title: str
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    polarity: str | None = None
    claim_layer: str | None = None
    identification_strength: str | None = None
    source_refs: frozenset[str] = frozenset()
    paper_refs: frozenset[str] = frozenset()
    annotation_refs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SameClaimCandidate:
    candidate_id: str
    propositions: tuple[str, ...]
    priority: Literal["high", "medium", "low"]
    splittable: bool
    flags: tuple[str, ...]
    signals: dict[str, Any]
    explanation: tuple[str, ...]
    pair_edges: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class FactorizationCandidate:
    candidate_id: str
    proposition: str
    priority: Literal["high", "medium", "low"]
    papers: tuple[str, ...]
    current: dict[str, Any]
    observed_statement_hints: tuple[dict[str, Any], ...]
    disagreement: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class ReconciliationFault:
    reason: str
    detail: str
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconciliationReport:
    same_claim_candidates: tuple[SameClaimCandidate, ...] = ()
    factorization_disagreements: tuple[FactorizationCandidate, ...] = ()
    faults: tuple[ReconciliationFault, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
    proposition_snapshots: dict[str, PropositionSnapshot] = field(default_factory=dict)


def _digest(parts: list[str]) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def candidate_id(lane: str, refs: list[str] | tuple[str, ...]) -> str:
    sorted_refs = sorted(refs)
    digest = _digest([lane, *sorted_refs])
    token = "same-claim" if lane == LANE_SAME_CLAIM else "factorization"
    return f"reconcile:{token}/{digest}"


def judgment_id(lane: str, decision: str, refs: list[str] | tuple[str, ...]) -> str:
    return f"reconcile:judgment/{_digest([lane, decision, *sorted(refs)])}"


def normalize_phrase(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def predicate_compatible(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return left in SIGN_MEANINGFUL_VALUES and right in SIGN_MEANINGFUL_VALUES


def polarity_compatible(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return "unsigned" in {left, right} and {left, right} <= {"positive", "negative", "unsigned"}


def title_tokens(title: str) -> set[str]:
    tokens = set(_TOKEN_RE.findall(title.casefold()))
    return {token for token in tokens if len(token) >= 4 and token not in _STOPWORDS}
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): proposition reconciliation core ids and compatibility"
```

---

## Task 3: Lane A Same-Claim Candidate Generation

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add failing tests for Lane A generation**

Append to `science/tests/test_proposition_reconciliation.py`:

```python
from science_tool.annotation.proposition_reconciliation import (
    MAX_RECONCILIATION_COMPONENT_SIZE,
    build_same_claim_candidates,
)


def _prop(
    ref: str,
    title: str,
    *,
    subject: str | None = "BRCA1 loss",
    predicate: str | None = "affects",
    object: str | None = "genomic instability",
    polarity: str | None = "positive",
    papers: frozenset[str] = frozenset(),
) -> PropositionSnapshot:
    return PropositionSnapshot(
        ref=ref,
        title=title,
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        source_refs=frozenset(papers),
        paper_refs=frozenset(papers),
    )


def test_same_claim_structured_match_high_priority():
    report = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )

    assert report.faults == ()
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.propositions == ("proposition:a", "proposition:b")
    assert candidate.priority == "high"
    assert candidate.splittable is False
    assert candidate.signals["same_subject"] is True
    assert candidate.signals["predicate_compatible"] is True


def test_same_claim_opposite_polarity_is_conflict_flag_not_same_claim_merge():
    report = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability", polarity="positive"),
            _prop("proposition:b", "BRCA1 loss decreases genomic instability", polarity="negative"),
        ]
    )

    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert "conflict_or_negation" in candidate.flags
    assert candidate.priority == "medium"


def test_missing_factorization_with_shared_paper_and_high_title_overlap_is_low_priority():
    report = build_same_claim_candidates(
        [
            _prop(
                "proposition:a",
                "BRCA1 loss increases genomic instability",
                subject=None,
                predicate=None,
                object=None,
                polarity=None,
                papers=frozenset({"paper:A2020"}),
            ),
            _prop(
                "proposition:b",
                "BRCA1 loss raises genomic instability",
                subject=None,
                predicate=None,
                object=None,
                polarity=None,
                papers=frozenset({"paper:A2020"}),
            ),
        ]
    )

    assert len(report.candidates) == 1
    assert report.candidates[0].priority == "low"
    assert "needs_factorization_context" in report.candidates[0].flags


def test_connected_component_groups_pairs_deterministically():
    report = build_same_claim_candidates(
        [
            _prop("proposition:c", "claim c"),
            _prop("proposition:a", "claim a"),
            _prop("proposition:b", "claim b"),
        ]
    )

    assert len(report.candidates) == 1
    assert report.candidates[0].propositions == ("proposition:a", "proposition:b", "proposition:c")
    assert report.candidates[0].splittable is True


def test_large_component_faults_instead_of_scaffolding():
    props = [
        _prop(f"proposition:p{i:02d}", f"claim {i}", papers=frozenset({"paper:A2020"}))
        for i in range(MAX_RECONCILIATION_COMPONENT_SIZE + 1)
    ]
    report = build_same_claim_candidates(props)

    assert report.candidates == ()
    assert len(report.faults) == 1
    assert report.faults[0].reason == "component-too-large"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL because `build_same_claim_candidates` is not defined.

- [ ] **Step 3: Implement Lane A generation**

In `proposition_reconciliation.py`, add:

```python
@dataclass(frozen=True)
class SameClaimBuildResult:
    candidates: tuple[SameClaimCandidate, ...]
    faults: tuple[ReconciliationFault, ...]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def _blocking_pairs(propositions: list[PropositionSnapshot]) -> set[tuple[str, str]]:
    # Bucketed blocking keeps the common case sub-quadratic. A single hot title token shared
    # by many propositions can still produce a quadratic bucket, but `_pair_signals` requires a
    # strong structural signal (endpoint match or shared paper) for inclusion and
    # MAX_RECONCILIATION_COMPONENT_SIZE caps emitted groups; both bound real output at meta scale.
    buckets: dict[tuple[str, str], list[str]] = {}
    for prop in propositions:
        subject = normalize_phrase(prop.subject)
        object_ = normalize_phrase(prop.object)
        predicate = prop.predicate or ""
        if subject and predicate and object_:
            buckets.setdefault(("spo", f"{subject}\0{predicate}\0{object_}"), []).append(prop.ref)
        if subject and object_:
            buckets.setdefault(("so", f"{subject}\0{object_}"), []).append(prop.ref)
        for paper in prop.paper_refs:
            buckets.setdefault(("paper", paper), []).append(prop.ref)
        for token in title_tokens(prop.title):
            buckets.setdefault(("title-token", token), []).append(prop.ref)

    pairs: set[tuple[str, str]] = set()
    for refs in buckets.values():
        if len(refs) < 2:
            continue
        ordered = sorted(set(refs))
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                pairs.add((left, right))
    return pairs


def _pair_signals(left: PropositionSnapshot, right: PropositionSnapshot) -> tuple[bool, dict[str, Any], tuple[str, ...], tuple[str, ...], str]:
    same_subject = bool(normalize_phrase(left.subject)) and normalize_phrase(left.subject) == normalize_phrase(right.subject)
    same_object = bool(normalize_phrase(left.object)) and normalize_phrase(left.object) == normalize_phrase(right.object)
    pred_ok = predicate_compatible(left.predicate, right.predicate)
    pol_ok = polarity_compatible(left.polarity, right.polarity)
    tokens_left = title_tokens(left.title)
    tokens_right = title_tokens(right.title)
    title_jaccard = _jaccard(tokens_left, tokens_right)
    shared_papers = sorted(left.paper_refs & right.paper_refs)
    full_structured = same_subject and same_object and left.predicate == right.predicate and pol_ok
    endpoint_compatible = same_subject and same_object and pred_ok
    strong = full_structured or endpoint_compatible or bool(shared_papers)
    lexical = title_jaccard >= 0.55 or bool(tokens_left and tokens_left <= tokens_right) or bool(tokens_right and tokens_right <= tokens_left)
    include = strong and (endpoint_compatible or lexical or bool(shared_papers))
    flags: list[str] = []
    explanation: list[str] = []
    if same_subject and same_object:
        explanation.append("same subject/object")
    if pred_ok:
        explanation.append("compatible predicate")
    if not pol_ok and same_subject and same_object and pred_ok:
        flags.append("conflict_or_negation")
        include = True
    if title_jaccard >= 0.55:
        explanation.append("high title token overlap")
    if not (left.subject and left.object and left.predicate and right.subject and right.object and right.predicate):
        flags.append("needs_factorization_context")
    signals = {
        "title_token_jaccard": round(title_jaccard, 3),
        "same_subject": same_subject,
        "same_object": same_object,
        "predicate_compatible": pred_ok,
        "polarity_compatible": pol_ok,
        "shared_source_papers": shared_papers,
    }
    if full_structured:
        priority = "high"
    elif endpoint_compatible and lexical:
        priority = "medium"
    elif include:
        priority = "low"
    else:
        priority = "low"
    return include, signals, tuple(sorted(set(flags))), tuple(explanation), priority


def build_same_claim_candidates(propositions: list[PropositionSnapshot]) -> SameClaimBuildResult:
    by_ref = {p.ref: p for p in propositions}
    edges: dict[tuple[str, str], tuple[dict[str, Any], tuple[str, ...], tuple[str, ...], str]] = {}
    for left_ref, right_ref in sorted(_blocking_pairs(propositions)):
        include, signals, flags, explanation, priority = _pair_signals(by_ref[left_ref], by_ref[right_ref])
        if include:
            edges[(left_ref, right_ref)] = (signals, flags, explanation, priority)

    parent = {ref: ref for ref in by_ref}

    def find(ref: str) -> str:
        while parent[ref] != ref:
            parent[ref] = parent[parent[ref]]
            ref = parent[ref]
        return ref

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for left, right in edges:
        union(left, right)

    groups: dict[str, list[str]] = {}
    for ref in by_ref:
        groups.setdefault(find(ref), []).append(ref)

    candidates: list[SameClaimCandidate] = []
    faults: list[ReconciliationFault] = []
    for refs in sorted((tuple(sorted(v)) for v in groups.values() if len(v) > 1)):
        group_edges = {edge for edge in edges if edge[0] in refs and edge[1] in refs}
        if len(refs) > MAX_RECONCILIATION_COMPONENT_SIZE:
            faults.append(ReconciliationFault("component-too-large", f"{len(refs)} propositions", refs))
            continue
        priorities = [edges[edge][3] for edge in group_edges]
        priority = "high" if "high" in priorities else "medium" if "medium" in priorities else "low"
        flags = tuple(sorted({flag for edge in group_edges for flag in edges[edge][1]}))
        explanation = tuple(sorted({item for edge in group_edges for item in edges[edge][2]}))
        # Carry the design §2 signal shape (same_subject / same_object / predicate_compatible /
        # polarity_compatible / title_token_jaccard / shared_source_papers). A pair has exactly
        # one edge; a larger component surfaces its strongest edge (max title overlap, with a
        # deterministic tie-break on the sorted edge tuple) as the representative, plus aggregate
        # counts. Without this the agent scaffold and JSON consumers lose every structural signal.
        representative = max(
            sorted(group_edges),
            key=lambda edge: edges[edge][0]["title_token_jaccard"],
        )
        signals = dict(edges[representative][0])
        signals["pair_count"] = len(group_edges)
        signals["max_title_token_jaccard"] = max(
            edges[edge][0]["title_token_jaccard"] for edge in group_edges
        )
        candidates.append(
            SameClaimCandidate(
                candidate_id=candidate_id(LANE_SAME_CLAIM, list(refs)),
                propositions=refs,
                priority=priority,  # type: ignore[arg-type]
                splittable=len(refs) > 2,
                flags=flags,
                signals=signals,
                explanation=explanation,
                pair_edges=frozenset(group_edges),
            )
        )
    return SameClaimBuildResult(tuple(candidates), tuple(faults))
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): generate deterministic same-claim candidates"
```

---

## Task 4: Lane B Factorization Diagnostics

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add failing Lane B tests**

Append to `science/tests/test_proposition_reconciliation.py`:

```python
from science_tool.annotation.cross_paper_evidence import LiteratureAssertion
from science_tool.annotation.proposition_reconciliation import build_factorization_disagreements


def _assertion(
    frag: str,
    *,
    proposition_ref: str = "proposition:p",
    paper_ref: str = "paper:A2020",
    stance: str = "asserted",
    subject: str | None = "BRCA1 loss",
    object: str | None = "genomic instability",
) -> LiteratureAssertion:
    return LiteratureAssertion(
        proposition_ref=proposition_ref,
        paper_ref=paper_ref,
        stance=stance,
        annotation_id=frag,
        sidecar=f"{paper_ref}.anno.trig",
        annotation_ref=f"annotation:entities/papers/{paper_ref.split(':', 1)[1]}.source#{frag}",
        statement_exact=f"{subject or 'claim'} -> {object or 'target'}",
        section="results",
        subject=subject,
        object=object,
    )


def test_factorization_disagreement_detects_incompatible_objects():
    prop = _prop("proposition:p", "BRCA1 loss affects genome stability")
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [
            _assertion("a1", object="genomic instability"),
            _assertion("a2", paper_ref="paper:B2021", object="replication stress"),
        ],
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.proposition == "proposition:p"
    assert candidate.recommended_action == "factorization_needs_resynthesis"
    assert "object differs" in candidate.disagreement
    assert len(candidate.observed_statement_hints) == 2


def test_factorization_disagreement_detects_mixed_stances():
    prop = _prop("proposition:p", "BRCA1 loss affects genome stability")
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [
            _assertion("a1", stance="asserted"),
            _assertion("a2", paper_ref="paper:B2021", stance="negated"),
        ],
    )

    assert len(candidates) == 1
    assert candidates[0].recommended_action == "stance_review_needed"
    assert "stance mix requires review" in candidates[0].disagreement


def test_factorization_disagreement_detects_unfactored_multiple_useful_hints():
    prop = _prop(
        "proposition:p",
        "BRCA1 loss affects genome stability",
        subject=None,
        predicate=None,
        object=None,
        polarity=None,
    )
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [_assertion("a1"), _assertion("a2", paper_ref="paper:B2021")],
    )

    assert len(candidates) == 1
    assert candidates[0].recommended_action == "factorization_needs_resynthesis"
    assert "current proposition is unfactored despite useful statement hints" in candidates[0].disagreement
```

- [ ] **Step 2: Run failing Lane B tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL because `build_factorization_disagreements` is not defined.

- [ ] **Step 3: Implement Lane B diagnostics**

In `proposition_reconciliation.py`, add:

```python
def _hint(assertion) -> dict[str, Any]:
    return {
        "paper": assertion.paper_ref,
        "annotation": assertion.annotation_ref,
        "stance": assertion.stance,
        "section": assertion.section,
        "subject": assertion.subject,
        "object": assertion.object,
        "subject_concept": assertion.subject_concept,
        "object_concept": assertion.object_concept,
        "exact": assertion.statement_exact,
    }


def _distinct_normalized(values: list[str | None]) -> set[str]:
    return {normalize_phrase(value) for value in values if normalize_phrase(value)}


def build_factorization_disagreements(
    propositions: dict[str, PropositionSnapshot],
    assertions: list[Any],
) -> tuple[FactorizationCandidate, ...]:
    by_prop: dict[str, list[Any]] = {}
    for assertion in assertions:
        if assertion.proposition_ref in propositions:
            by_prop.setdefault(assertion.proposition_ref, []).append(assertion)

    out: list[FactorizationCandidate] = []
    for prop_ref, prop_assertions in sorted(by_prop.items()):
        if len(prop_assertions) < 2:
            continue
        prop = propositions[prop_ref]
        stances = {a.stance for a in prop_assertions}
        subjects = _distinct_normalized([a.subject for a in prop_assertions])
        objects = _distinct_normalized([a.object for a in prop_assertions])
        useful_hints = [a for a in prop_assertions if a.subject or a.object]
        disagreement: list[str] = []
        recommended = ""
        priority: Literal["high", "medium", "low"] = "medium"
        if "asserted" in stances and "negated" in stances:
            disagreement.append("stance mix requires review")
            recommended = "stance_review_needed"
            priority = "high"
        if len(subjects) > 1:
            disagreement.append("subject differs")
            recommended = recommended or "factorization_needs_resynthesis"
        if len(objects) > 1:
            disagreement.append("object differs")
            recommended = recommended or "factorization_needs_resynthesis"
        if useful_hints and not (prop.subject and prop.predicate and prop.object):
            disagreement.append("current proposition is unfactored despite useful statement hints")
            recommended = recommended or "factorization_needs_resynthesis"
        if not disagreement and len(prop_assertions) > 1 and not useful_hints:
            disagreement.append("multiple assertions have insufficient factorization hints")
            recommended = "insufficient_hints"
            priority = "low"
        if not disagreement:
            continue
        out.append(
            FactorizationCandidate(
                candidate_id=candidate_id(LANE_FACTORIZATION, [prop_ref]),
                proposition=prop_ref,
                priority=priority,
                papers=tuple(sorted({a.paper_ref for a in prop_assertions})),
                current={
                    "subject": prop.subject,
                    "predicate": prop.predicate,
                    "object": prop.object,
                    "polarity": prop.polarity,
                    "claim_layer": prop.claim_layer,
                },
                observed_statement_hints=tuple(_hint(a) for a in prop_assertions),
                disagreement=tuple(disagreement),
                recommended_action=recommended,
            )
        )
    return tuple(out)
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): detect proposition factorization disagreements"
```

---

## Task 5: Project Report Builder and Serialization

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add report-builder tests**

Append to `science/tests/test_proposition_reconciliation.py`:

```python
from science_tool.annotation.proposition_reconciliation import candidate_to_json, report_to_json


def test_candidate_to_json_keeps_stable_public_shape():
    candidate = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    ).candidates[0]

    payload = candidate_to_json(candidate)

    assert payload["candidate_id"].startswith("reconcile:same-claim/")
    assert payload["propositions"] == ["proposition:a", "proposition:b"]
    assert payload["priority"] == "high"
    assert payload["splittable"] is False
    assert payload["flags"] == []
    assert "pair_edges" not in payload


def test_report_to_json_includes_summary_counts():
    same = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=same.candidates, faults=same.faults)

    payload = report_to_json(report)

    assert payload["summary"]["same_claim_candidates"] == 1
    assert payload["summary"]["factorization_disagreements"] == 0
    assert payload["summary"]["faults"] == 0
```

- [ ] **Step 2: Run failing report tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL because `candidate_to_json` and `report_to_json` are not implemented. At the top of the test file, add `ReconciliationReport` to the existing `from science_tool.annotation.proposition_reconciliation import (...)` block.

- [ ] **Step 3: Implement serialization helpers**

Add to `proposition_reconciliation.py`:

```python
def candidate_to_json(candidate: SameClaimCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "propositions": list(candidate.propositions),
        "priority": candidate.priority,
        "splittable": candidate.splittable,
        "flags": list(candidate.flags),
        "signals": candidate.signals,
        "explanation": list(candidate.explanation),
    }


def factorization_to_json(candidate: FactorizationCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "proposition": candidate.proposition,
        "priority": candidate.priority,
        "papers": list(candidate.papers),
        "current": candidate.current,
        "observed_statement_hints": [dict(item) for item in candidate.observed_statement_hints],
        "disagreement": list(candidate.disagreement),
        "recommended_action": candidate.recommended_action,
    }


def fault_to_json(fault: ReconciliationFault) -> dict[str, Any]:
    return {
        "reason": fault.reason,
        "detail": fault.detail,
        "members": list(fault.members),
    }


def report_to_json(report: ReconciliationReport) -> dict[str, Any]:
    summary = {
        "same_claim_candidates": len(report.same_claim_candidates),
        "factorization_disagreements": len(report.factorization_disagreements),
        "faults": len(report.faults),
    }
    summary.update(report.summary)
    return {
        "summary": summary,
        "same_claim_candidates": [candidate_to_json(item) for item in report.same_claim_candidates],
        "factorization_disagreements": [
            factorization_to_json(item) for item in report.factorization_disagreements
        ],
        "faults": [fault_to_json(item) for item in report.faults],
    }


SCAFFOLD_INSTRUCTION = (
    "Review each candidate using ONLY the propositions, refs, and statement hints listed "
    "here. Never invent proposition or annotation refs. For a same_claim group, choose a "
    "decision from the closed vocabulary and, when the decision is same_claim, a "
    "canonical_proposition drawn from the listed members. For a factorization candidate, "
    "choose exactly one Lane B decision."
)


def _snapshot_public(snapshot: PropositionSnapshot) -> dict[str, Any]:
    return {
        "ref": snapshot.ref,
        "title": snapshot.title,
        "subject": snapshot.subject,
        "predicate": snapshot.predicate,
        "object": snapshot.object,
        "polarity": snapshot.polarity,
        "claim_layer": snapshot.claim_layer,
        "identification_strength": snapshot.identification_strength,
        "paper_refs": sorted(snapshot.paper_refs),
        "annotation_refs": sorted(snapshot.annotation_refs),
    }


def same_claim_scaffold(
    candidate: SameClaimCandidate, snapshots: dict[str, PropositionSnapshot]
) -> dict[str, Any]:
    payload = candidate_to_json(candidate)
    payload["lane"] = LANE_SAME_CLAIM
    # Replace the bare ref list with full per-member snapshots so the reviewing agent has
    # the frontmatter / factorization context the design §4 scaffold requires, instead of
    # being handed opaque proposition refs it would have to re-load itself.
    payload["propositions"] = [
        _snapshot_public(snapshots[ref]) if ref in snapshots else {"ref": ref}
        for ref in candidate.propositions
    ]
    return payload


def report_to_scaffold(report: ReconciliationReport) -> dict[str, Any]:
    base = report_to_json(report)
    return {
        "instruction": SCAFFOLD_INSTRUCTION,
        "decision_vocabulary": sorted(DECISIONS),
        "confidence_vocabulary": sorted(CONFIDENCE_VALUES),
        "summary": base["summary"],
        "same_claim_candidates": [
            same_claim_scaffold(candidate, report.proposition_snapshots)
            for candidate in report.same_claim_candidates
        ],
        "factorization_disagreements": [
            {**item, "lane": LANE_FACTORIZATION} for item in base["factorization_disagreements"]
        ],
        "faults": base["faults"],
    }
```

- [ ] **Step 4: Add project loading helpers**

Add this implementation. It is intentionally thin and uses `getattr` so it works with the actual entities returned by `load_project_sources`:

```python
def snapshot_from_entity(entity: Any) -> PropositionSnapshot:
    source_refs = frozenset(str(ref) for ref in (getattr(entity, "source_refs", None) or []))
    return PropositionSnapshot(
        ref=str(entity.canonical_id),
        title=str(getattr(entity, "title", "") or ""),
        subject=getattr(entity, "subject", None),
        predicate=str(getattr(entity, "predicate")) if getattr(entity, "predicate", None) is not None else None,
        object=getattr(entity, "object", None),
        polarity=str(getattr(entity, "polarity")) if getattr(entity, "polarity", None) is not None else None,
        claim_layer=str(getattr(entity, "claim_layer")) if getattr(entity, "claim_layer", None) is not None else None,
        identification_strength=(
            str(getattr(entity, "identification_strength"))
            if getattr(entity, "identification_strength", None) is not None
            else None
        ),
        source_refs=source_refs,
        paper_refs=frozenset(ref for ref in source_refs if ref.startswith("paper:")),
        annotation_refs=frozenset(ref for ref in source_refs if ref.startswith("annotation:")),
    )


def build_reconciliation_report(
    project_root,
    *,
    proposition_ref: str | None = None,
    source_sidecar: str | None = None,
) -> ReconciliationReport:
    from pathlib import Path

    from science_tool.annotation.cross_paper_evidence import (
        proposition_source_refs_map,
        scan_literature_assertions,
    )
    from science_tool.graph.sources import load_project_sources

    root = Path(project_root).resolve()
    sources = load_project_sources(root)  # load once; reuse entities for refs + snapshots
    proposition_entities = [
        entity for entity in sources.entities if getattr(entity, "kind", None) == "proposition"
    ]
    snapshots = {entity.canonical_id: snapshot_from_entity(entity) for entity in proposition_entities}
    assertions, scan_faults = scan_literature_assertions(
        root, proposition_source_refs_map(sources.entities)
    )

    # Lane A blocking must see the whole corpus, so candidates are always generated over the
    # full snapshot set; scope is then applied as a post-filter on candidates. Pre-filtering
    # the universe (the earlier approach) would hide a scoped proposition's blocking partners
    # and make `--proposition` produce zero same-claim candidates.
    same = build_same_claim_candidates(list(snapshots.values()))
    factors = build_factorization_disagreements(snapshots, assertions)

    scope_refs: set[str] | None = None
    if proposition_ref is not None:
        scope_refs = {proposition_ref}
    if source_sidecar is not None:
        sidecar_props = {a.proposition_ref for a in assertions if a.sidecar == source_sidecar}
        scope_refs = sidecar_props if scope_refs is None else scope_refs & sidecar_props

    same_candidates = same.candidates
    factor_candidates = factors
    scoped_snapshots = snapshots
    if scope_refs is not None:
        same_candidates = tuple(c for c in same.candidates if scope_refs & set(c.propositions))
        factor_candidates = tuple(c for c in factors if c.proposition in scope_refs)
        keep: set[str] = set(scope_refs)
        for candidate in same_candidates:
            keep.update(candidate.propositions)
        scoped_snapshots = {ref: snapshots[ref] for ref in sorted(keep) if ref in snapshots}

    faults = [
        ReconciliationFault(fault.reason, f"{fault.sidecar}:{fault.annotation_id} {fault.detail}")
        for fault in scan_faults
    ]
    faults.extend(same.faults)
    return ReconciliationReport(
        same_claim_candidates=same_candidates,
        factorization_disagreements=factor_candidates,
        faults=tuple(faults),
        proposition_snapshots=scoped_snapshots,
    )
```

- [ ] **Step 5: Run core tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): build proposition reconciliation reports"
```

---

## Task 6: Reviewed Judgment Validation

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation.py`
- Modify: `science/tests/test_proposition_reconciliation.py`

- [ ] **Step 1: Add reviewed-file validation tests**

Append to `science/tests/test_proposition_reconciliation.py`:

```python
import pytest

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    ReconciliationReport,
    ReconciliationValidationError,
    validate_review_doc,
)


def _candidate_report() -> ReconciliationReport:
    same = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )
    return ReconciliationReport(same_claim_candidates=same.candidates)


def test_validate_review_doc_accepts_same_claim_judgment():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude-opus-4-8:proposition-reconcile-v1",
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
                "rationale": "The claims share endpoints, predicate, polarity, and assertion meaning.",
                "confidence": "high",
            }
        ],
    }

    result = validate_review_doc(doc, report)

    assert result["status"] == "ok"
    assert result["judgments"] == 1
    assert result["errors"] == []


def test_validate_review_doc_reanchors_splittable_subset_after_component_growth():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    old_pair_candidate_id = candidate_id("same_claim", ["proposition:a", "proposition:b"])
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": old_pair_candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "The pair remains the same claim even though the current component grew.",
                "confidence": "high",
            }
        ],
    }

    result = validate_review_doc(doc, report)

    assert result["status"] == "ok"
    assert result["review_incomplete"] == [
        {"candidate_id": report.same_claim_candidates[0].candidate_id, "missing": ["proposition:c"]}
    ]


@pytest.mark.parametrize(
    "bad_source",
    [
        "llm-review:<MODEL>:proposition-reconcile-v1",
        "llm-synth:claude:proposition-reconcile-v1",
        "llm-review:claude opus:proposition-reconcile-v1",
    ],
)
def test_validate_review_doc_rejects_bad_source(bad_source):
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": bad_source,
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "same_claim", list(candidate.propositions)),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "valid rationale",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="source"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_wrong_judgment_id():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": "reconcile:judgment/not-the-right-hash",
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "valid rationale",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="judgment_id"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_lane_b_same_claim_decision():
    factor = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="medium",
        papers=("paper:A2020",),
        current={},
        observed_statement_hints=(),
        disagreement=("object differs",),
        recommended_action="factorization_needs_resynthesis",
    )
    report = ReconciliationReport(factorization_disagreements=(factor,))
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": factor.candidate_id,
                "judgment_id": judgment_id("factorization_disagreement", "same_claim", ["proposition:p"]),
                "lane": "factorization_disagreement",
                "decision": "same_claim",
                "proposition": "proposition:p",
                "rationale": "valid rationale",
                "confidence": "medium",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="Lane B"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_incomplete_direct_splittable_review():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "a and b are the same claim; c was left unjudged.",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="incomplete"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_second_factorization_judgment():
    factor = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="medium",
        papers=("paper:A2020",),
        current={},
        observed_statement_hints=(),
        disagreement=("object differs",),
        recommended_action="factorization_needs_resynthesis",
    )
    report = ReconciliationReport(factorization_disagreements=(factor,))
    judgment = {
        "candidate_id": factor.candidate_id,
        "judgment_id": judgment_id(
            "factorization_disagreement", "stance_review_needed", ["proposition:p"]
        ),
        "lane": "factorization_disagreement",
        "decision": "stance_review_needed",
        "proposition": "proposition:p",
        "rationale": "valid rationale",
        "confidence": "medium",
    }
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [dict(judgment), dict(judgment)],
    }

    with pytest.raises(ReconciliationValidationError, match="more than one"):
        validate_review_doc(doc, report)
```

- [ ] **Step 2: Run failing validation tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: FAIL because validation functions are not defined.

- [ ] **Step 3: Implement validation**

Add to `proposition_reconciliation.py`. The module already imports `re` from Task 2; do not add a duplicate `import re` line:

```python
REVIEW_SOURCE_RE = re.compile(r"^llm-review:[A-Za-z0-9._-]+:proposition-reconcile-v1$")


class ReconciliationValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReconciliationValidationError(message)


def _candidate_indexes(report: ReconciliationReport) -> tuple[dict[str, SameClaimCandidate], dict[str, FactorizationCandidate]]:
    same = {candidate.candidate_id: candidate for candidate in report.same_claim_candidates}
    factors = {candidate.candidate_id: candidate for candidate in report.factorization_disagreements}
    return same, factors


def _members_have_current_edge(candidate: SameClaimCandidate, members: set[str]) -> bool:
    if len(members) < 2:
        return False
    for left, right in candidate.pair_edges:
        if left in members and right in members:
            return True
    return False


def _resolve_same_claim_candidate(
    candidate_ref: str,
    members: set[str],
    same_by_id: dict[str, SameClaimCandidate],
    all_same: tuple[SameClaimCandidate, ...],
) -> SameClaimCandidate | None:
    direct = same_by_id.get(candidate_ref)
    if direct is not None:
        return direct
    matches = [
        candidate
        for candidate in all_same
        if candidate.splittable
        and members <= set(candidate.propositions)
        and _members_have_current_edge(candidate, members)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _require_non_empty_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def validate_review_doc(doc: Any, report: ReconciliationReport) -> dict[str, Any]:
    _require(isinstance(doc, dict), "review document must be an object")
    source = _require_non_empty_string(doc.get("source"), "source")
    _require(REVIEW_SOURCE_RE.match(source) is not None, "source must match llm-review:<model>:proposition-reconcile-v1")
    judgments = doc.get("judgments")
    _require(isinstance(judgments, list), "judgments must be a list")
    same_by_id, factor_by_id = _candidate_indexes(report)
    covered_by_candidate: dict[str, set[str]] = {}
    directly_targeted: set[str] = set()
    factor_seen: set[str] = set()
    errors: list[str] = []

    for idx, judgment in enumerate(judgments):
        _require(isinstance(judgment, dict), f"judgments[{idx}] must be an object")
        candidate_ref = _require_non_empty_string(judgment.get("candidate_id"), f"judgments[{idx}].candidate_id")
        lane = _require_non_empty_string(judgment.get("lane"), f"judgments[{idx}].lane")
        decision = _require_non_empty_string(judgment.get("decision"), f"judgments[{idx}].decision")
        _require(decision in DECISIONS, f"judgments[{idx}].decision is not allowed")
        _require(judgment.get("confidence") in CONFIDENCE_VALUES, f"judgments[{idx}].confidence is not allowed")
        _require_non_empty_string(judgment.get("rationale"), f"judgments[{idx}].rationale")

        if lane == LANE_SAME_CLAIM:
            members = judgment.get("members")
            _require(isinstance(members, list) and all(isinstance(m, str) for m in members), f"judgments[{idx}].members must be strings")
            member_set = set(members)
            _require(bool(member_set), f"judgments[{idx}].members must not be empty")
            candidate = _resolve_same_claim_candidate(
                candidate_ref,
                member_set,
                same_by_id,
                report.same_claim_candidates,
            )
            _require(candidate is not None, f"judgments[{idx}].candidate_id is stale or unknown")
            if candidate_ref == candidate.candidate_id:
                directly_targeted.add(candidate.candidate_id)
            candidate_members = set(candidate.propositions)
            if candidate.splittable:
                _require(member_set <= candidate_members, f"judgments[{idx}].members must be a subset of the candidate")
            else:
                _require(member_set == candidate_members, f"judgments[{idx}].members must equal the candidate")
            expected_judgment = judgment_id(lane, decision, list(member_set))
            _require(judgment.get("judgment_id") == expected_judgment, f"judgments[{idx}].judgment_id mismatch")
            if decision == "same_claim":
                canonical = _require_non_empty_string(judgment.get("canonical_proposition"), f"judgments[{idx}].canonical_proposition")
                _require(canonical in member_set, f"judgments[{idx}].canonical_proposition must be one of members")
            else:
                _require("canonical_proposition" not in judgment, f"judgments[{idx}].canonical_proposition is forbidden")
            covered_by_candidate.setdefault(candidate.candidate_id, set()).update(member_set)
        elif lane == LANE_FACTORIZATION:
            candidate = factor_by_id.get(candidate_ref)
            _require(candidate is not None, f"judgments[{idx}].candidate_id is stale or unknown")
            _require(
                candidate_ref not in factor_seen,
                f"judgments[{idx}].candidate_id has more than one factorization judgment",
            )
            factor_seen.add(candidate_ref)
            _require(decision in LANE_B_DECISIONS, f"judgments[{idx}] Lane B decision is not allowed")
            proposition = _require_non_empty_string(judgment.get("proposition"), f"judgments[{idx}].proposition")
            _require(proposition == candidate.proposition, f"judgments[{idx}].proposition does not match candidate")
            expected_judgment = judgment_id(lane, decision, [proposition])
            _require(judgment.get("judgment_id") == expected_judgment, f"judgments[{idx}].judgment_id mismatch")
            _require("canonical_proposition" not in judgment, f"judgments[{idx}].canonical_proposition is forbidden")
        else:
            raise ReconciliationValidationError(f"judgments[{idx}].lane is not allowed")

    incomplete: list[dict[str, Any]] = []
    for candidate in report.same_claim_candidates:
        if not candidate.splittable:
            continue
        covered = covered_by_candidate.get(candidate.candidate_id, set())
        missing = sorted(set(candidate.propositions) - covered)
        if not missing:
            continue
        # Two regimes (design §3/§4). A review authored *against the current candidate* (a
        # direct candidate_id hit) must cover every member — leaving one unjudged is a silent
        # fall-through and fails the authoring gate. A subset judgment that only re-anchored
        # to this component after membership churn (stale candidate_id) leaves the newly added
        # members as advisory "not-yet-reviewed", never a hard failure.
        if candidate.candidate_id in directly_targeted:
            raise ReconciliationValidationError(
                f"review of {candidate.candidate_id} is incomplete: unjudged members {missing}"
            )
        incomplete.append({"candidate_id": candidate.candidate_id, "missing": missing})

    return {
        "status": "ok" if not errors else "error",
        "source": source,
        "judgments": len(judgments),
        "errors": errors,
        "review_incomplete": incomplete,
    }
```

- [ ] **Step 4: Run validation tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation.py science/tests/test_proposition_reconciliation.py
rtk git commit -m "feat(4e): validate proposition reconciliation reviews"
```

---

## Task 7: CLI Commands

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Create: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add CLI tests**

Create `science/tests/test_proposition_reconciliation_cli.py`:

```python
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.proposition_reconciliation import judgment_id


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(root: Path, slug: str, title: str) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {title}\n"
        "status: active\nsubject: BRCA1 loss\npredicate: affects\n"
        "object: genomic instability\npolarity: positive\n---\n\nClaim.\n",
        encoding="utf-8",
    )


def test_reconcile_propositions_json(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["same_claim_candidates"] == 1
    assert payload["same_claim_candidates"][0]["propositions"] == ["proposition:a", "proposition:b"]


def test_reconcile_propositions_table(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "same_claim" in result.output
    assert "proposition:a" in result.output


def test_validate_proposition_reconciliation_cli(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    payload = json.loads(generated.output)
    candidate = payload["same_claim_candidates"][0]
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "same_claim", candidate["propositions"]),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": candidate["propositions"],
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "ok"


def test_reconcile_propositions_rejects_multiple_scopes(tmp_path: Path):
    _manifest(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--all",
            "--proposition",
            "proposition:a",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "choose exactly one scope" in result.output


def test_reconcile_propositions_scaffold_embeds_member_snapshots(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "scaffold"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "instruction" in payload
    members = payload["same_claim_candidates"][0]["propositions"]
    assert {m["ref"] for m in members} == {"proposition:a", "proposition:b"}
    assert all("title" in m and "subject" in m for m in members)


def test_reconcile_propositions_proposition_scope_keeps_involving_candidates(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--proposition",
            "proposition:a",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["same_claim_candidates"] == 1
    assert "proposition:a" in payload["same_claim_candidates"][0]["propositions"]
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_cli.py -q
```

Expected: FAIL because the commands do not exist.

- [ ] **Step 3: Add flat `annotate` commands**

In `science/src/science_tool/annotation/cli.py`, add imports only inside commands. Place these near `cross-paper-evidence`:

```python
@annotate_group.command("reconcile-propositions")
@click.option("--all", "all_scope", is_flag=True, default=False)
@click.option("--proposition", "proposition_ref", default=None)
@click.option("--source", "source_md", default=None, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json", "scaffold")), default="table")
def reconcile_propositions_cmd(
    all_scope: bool,
    proposition_ref: str | None,
    source_md: Path | None,
    root: Path | None,
    fmt: str,
) -> None:
    """Generate deterministic proposition reconciliation candidates."""
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.proposition_reconciliation import (
        build_reconciliation_report,
        report_to_json,
        report_to_scaffold,
    )

    selected = sum(1 for item in (all_scope, proposition_ref is not None, source_md is not None) if item)
    if selected != 1:
        raise click.ClickException("choose exactly one scope: --all, --proposition, or --source")
    if proposition_ref is not None and not proposition_ref.startswith("proposition:"):
        raise click.ClickException("--proposition must use proposition:<slug>")

    project_root = (root or Path.cwd()).resolve()
    source_sidecar = None
    if source_md is not None:
        source_path = source_md if source_md.is_absolute() else project_root / source_md
        source_sidecar = str(anno_io.sidecar_for_markdown(source_path))

    report = build_reconciliation_report(
        project_root,
        proposition_ref=proposition_ref,
        source_sidecar=source_sidecar,
    )
    payload = report_to_json(report)

    if fmt == "scaffold":
        click.echo(json.dumps(report_to_scaffold(report), indent=2, sort_keys=True))
        return
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "proposition reconciliation: "
        f"same_claim={summary['same_claim_candidates']} "
        f"factorization={summary['factorization_disagreements']} "
        f"faults={summary['faults']}"
    )
    for item in payload["same_claim_candidates"]:
        click.echo(
            f"same_claim {item['priority']:6s} {','.join(item['propositions'])} "
            f"flags={','.join(item['flags']) or '-'}"
        )
    for item in payload["factorization_disagreements"]:
        click.echo(
            f"factorization {item['priority']:6s} {item['proposition']} "
            f"action={item['recommended_action']}"
        )
    if payload["faults"]:
        click.echo(f"FAULTS ({len(payload['faults'])}):")
        for fault in payload["faults"]:
            click.echo(f"  {fault['reason']}: {fault['detail']}")


@annotate_group.command("validate-proposition-reconciliation")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def validate_proposition_reconciliation_cmd(input_path: Path, root: Path | None, fmt: str) -> None:
    """Validate an agent-reviewed proposition reconciliation artifact."""
    from science_tool.annotation.proposition_reconciliation import (
        ReconciliationValidationError,
        build_reconciliation_report,
        validate_review_doc,
    )

    project_root = (root or Path.cwd()).resolve()
    try:
        doc = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
    report = build_reconciliation_report(project_root)
    try:
        payload = validate_review_doc(doc, report)
    except ReconciliationValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(
        f"proposition reconciliation review: {payload['status']} "
        f"judgments={payload['judgments']} incomplete={len(payload['review_incomplete'])}"
    )
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run combined reconciliation tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/test_proposition_reconciliation.py tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): add proposition reconciliation CLI"
```

---

## Task 8: Regression, Type Check, and Real-Corpus Smoke

**Files:**
- No new files expected.

- [ ] **Step 1: Run targeted regression tests**

Run:

```bash
cd science && rtk uv run --frozen pytest \
  tests/test_cross_paper_evidence.py \
  tests/test_cross_paper_evidence_materialize.py \
  tests/test_cross_paper_evidence_cli.py \
  tests/test_proposition_reconciliation.py \
  tests/test_proposition_reconciliation_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run pyright on touched modules**

Run:

```bash
cd science && rtk uv run --frozen pyright \
  src/science_tool/annotation/cross_paper_evidence.py \
  src/science_tool/annotation/proposition_reconciliation.py \
  src/science_tool/annotation/cli.py
```

Expected: `0 errors`.

- [ ] **Step 3: Run real-corpus JSON smoke**

Run from repo root:

```bash
cd meta && PYTHONPATH=../science/src rtk uv run --frozen --project ../science science annotate reconcile-propositions --all --format json > /tmp/phase4e-reconcile.json
```

Expected: exit 0. The JSON should parse and include top-level `summary`, `same_claim_candidates`, `factorization_disagreements`, and `faults`.

- [ ] **Step 4: Validate the smoke JSON shape**

Run:

```bash
cd science && rtk uv run --frozen python -m json.tool /tmp/phase4e-reconcile.json >/tmp/phase4e-reconcile.pretty.json
```

Expected: exit 0.

- [ ] **Step 5: Run help text smoke**

Run:

```bash
cd science && rtk uv run --frozen python -c "from science_tool.cli import main; main(['annotate', 'reconcile-propositions', '--help'], standalone_mode=False)"
```

Expected: help text includes `--all`, `--proposition`, `--source`, and `--format`.

- [ ] **Step 6: Commit any verification-only fixes**

If Steps 1-5 required code changes, commit them:

```bash
rtk git add science/src/science_tool/annotation/cross_paper_evidence.py science/src/science_tool/annotation/proposition_reconciliation.py science/src/science_tool/annotation/cli.py science/tests/test_cross_paper_evidence.py science/tests/test_cross_paper_evidence_materialize.py science/tests/test_proposition_reconciliation.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "fix(4e): stabilize proposition reconciliation regressions"
```

If no code changed, do not create an empty commit.

---

## Acceptance Criteria

- 4d cross-paper evidence behavior remains unchanged except that `LiteratureAssertion` exposes additional context fields.
- `science annotate reconcile-propositions --all --format json` emits stable `summary`, `same_claim_candidates`, `factorization_disagreements`, and `faults`.
- Same-claim candidate `signals` carry the design §2 shape (`same_subject`, `same_object`, `predicate_compatible`, `polarity_compatible`, `title_token_jaccard`, `shared_source_papers`) plus aggregate `pair_count` / `max_title_token_jaccard`.
- `--format scaffold` emits an agent-facing payload: a review instruction, the decision/confidence vocabularies, and per-member proposition snapshots (title + factorization fields) embedded in each same-claim candidate — not a bare alias of `json`.
- `--proposition` / `--source` filters output to candidates involving the scoped proposition(s), while Lane A blocking still runs over the full corpus so blocking partners are not hidden.
- Lane A candidates use deterministic full-SHA-256 candidate ids over `same_claim\0<sorted refs>`.
- Lane B diagnostics consume uncollapsed per-annotation assertions and can see subject/object/exact context.
- `science annotate validate-proposition-reconciliation --input review.json` validates reviewed files without writing proposition files; it enforces splittable coverage as an authoring gate on a directly-targeted candidate, treats re-anchored subsets' missing members as advisory `review_incomplete`, and rejects a second factorization judgment for one candidate.
- No proposition entities, sidecars, aliases, archives, or belief aggregation code are mutated by 4e Half A.
- Targeted pytest, pyright, and real-corpus smoke pass.

---
id: "plan:2026-05-13-reason-coded-attention-implementation"
type: "plan"
title: "Reason-coded attention implementation plan"
status: "draft"
created: "2026-05-13"
related:
  - "plan:2026-05-13-reason-coded-attention-design"
  - "hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting"
---

# Reason-Coded Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 1 reason payloads and a non-default Phase 1.5 reason-aware review-routing toggle to upstream graph attention sampling.

**Architecture:** Keep the current attention-weight formula unchanged by default.
Extend `AttentionCandidate` with derived reason metadata, format those reasons in JSON output, and add an opt-in CLI mode that routes a bounded reason-coded review slice before filling the rest from weighted sampling.
All Phase 1 reasons are proposition-only and derived from observable graph state.

**Tech Stack:** Python 3.12, rdflib, Click, pytest, existing `science_tool.graph.attention` and `science_tool.cli` modules.

---

## File Structure

- Modify: `science/src/science_tool/graph/attention.py`
  - Owns `AttentionReason`, reason derivation, default attention candidate formatting, and opt-in reason-aware review routing.
- Modify: `science/src/science_tool/cli.py`
  - Adds a non-default `--reason-aware` flag to `graph attention-sample` and includes reason columns in table output.
- Modify: `science/tests/test_attention_sampling.py`
  - Adds proposition fixtures and regression tests for Phase 1 reason derivation, JSON output, default behavior, and Phase 1.5 routing.
- No new compatibility layer.
  Existing callers of `query_attention_sample()` should keep working because the default sampler and formatted row keys are preserved.

## Task 1: Add Reason Data Structures And Derivation Tests

**Files:**
- Modify: `science/tests/test_attention_sampling.py`
- Modify: `science/src/science_tool/graph/attention.py`

- [ ] **Step 1: Add the failing proposition reason fixture and unit test**

Append this fixture and test to `science/tests/test_attention_sampling.py` after `_attention_fixture()`:

```python
def _reason_fixture() -> Dataset:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    p0 = _u("proposition/unscaffolded")
    p1 = _u("proposition/fragile")
    p2 = _u("proposition/contested")
    p3 = _u("proposition/counterevidence")
    h1 = _u("hypothesis/not_reason_scoped")

    support_a = _u("observation/support_a")
    support_b = _u("observation/support_b")
    dispute_a = _u("observation/dispute_a")
    dispute_b = _u("observation/dispute_b")
    dispute_c = _u("observation/dispute_c")

    for uri, label in (
        (p0, "Unscaffolded proposition"),
        (p1, "Fragile proposition"),
        (p2, "Contested proposition"),
        (p3, "Counterevidence proposition"),
    ):
        knowledge.add((uri, RDF.type, SCI_NS.Proposition))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        knowledge.add((uri, SCI_NS.lastReviewed, Literal("2026-04-30", datatype=XSD.date)))

    knowledge.add((h1, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((h1, SKOS.prefLabel, Literal("Hypothesis outside Phase 1 reason scope")))
    knowledge.add((h1, SCI_NS.freshnessState, Literal("fresh")))
    knowledge.add((h1, SCI_NS.lastReviewed, Literal("2026-04-30", datatype=XSD.date)))
    knowledge.add((support_a, CITO_NS.supports, h1))
    knowledge.add((dispute_a, CITO_NS.disputes, h1))

    knowledge.add((support_a, CITO_NS.supports, p1))

    knowledge.add((support_a, CITO_NS.supports, p2))
    knowledge.add((support_b, CITO_NS.supports, p2))
    knowledge.add((dispute_a, CITO_NS.disputes, p2))
    knowledge.add((dispute_b, CITO_NS.disputes, p2))

    knowledge.add((support_a, CITO_NS.supports, p3))
    knowledge.add((dispute_a, CITO_NS.disputes, p3))
    knowledge.add((dispute_b, CITO_NS.disputes, p3))
    knowledge.add((dispute_c, CITO_NS.disputes, p3))

    return dataset


def test_phase1_reason_derivation_is_proposition_scoped() -> None:
    candidates = compute_attention_candidates(_reason_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}

    assert by_id["proposition:unscaffolded"].reasons == [
        {
            "code": "unscaffolded",
            "direction": "route_attention",
            "strength": "high",
            "provenance": "derived:unscaffolded_source_count(evidence_source_count)",
            "next_action": "scaffold_evidence_base",
        }
    ]
    assert by_id["proposition:fragile"].reasons == [
        {
            "code": "fragility",
            "direction": "increase_attention",
            "strength": "high",
            "provenance": "derived:fragility_source_count(evidence_source_count)",
            "next_action": "seek_independent_evidence",
        }
    ]
    assert by_id["proposition:contested"].reasons == [
        {
            "code": "contestation",
            "direction": "increase_attention",
            "strength": "high",
            "provenance": "derived:contestation_counts(support_count,dispute_count)",
            "next_action": "compare_contexts",
        }
    ]
    assert by_id["proposition:counterevidence"].reasons == [
        {
            "code": "contestation",
            "direction": "increase_attention",
            "strength": "low",
            "provenance": "derived:contestation_counts(support_count,dispute_count)",
            "next_action": "compare_contexts",
        },
        {
            "code": "strong_counterevidence",
            "direction": "decrease_attention",
            "strength": "high",
            "provenance": "derived:counterevidence_counts(support_count,dispute_count)",
            "next_action": "preserve_floor",
        },
    ]
    assert by_id["hypothesis:not_reason_scoped"].reasons == []
```

In the existing `test_attention_weight_uses_observable_graph_features()` exact `contested.components` assertion, add the new component so the existing regression test remains exact:

```python
        "evidence_source_count": 2.0,
```

Place it next to the existing `support_count` and `dispute_count` component assertions.

- [ ] **Step 2: Run the failing reason-derivation test**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_phase1_reason_derivation_is_proposition_scoped -q
```

Expected: FAIL because `AttentionCandidate` has no `reasons` attribute.

- [ ] **Step 3: Add `AttentionReason` and extend `AttentionCandidate`**

In `science/src/science_tool/graph/attention.py`, add `Any` to the typing import:

```python
from typing import Any, Iterable, Mapping, Sequence
```

Add this dataclass before `AttentionCandidate`:

```python
@dataclass(frozen=True)
class AttentionReason:
    """Machine-visible reason metadata for why an entity deserves attention."""

    code: str
    direction: str
    strength: str
    provenance: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "direction": self.direction,
            "strength": self.strength,
            "provenance": self.provenance,
            "next_action": self.next_action,
        }
```

Update `AttentionCandidate`:

```python
@dataclass(frozen=True)
class AttentionCandidate:
    """One graph entity with an observable attention weight."""

    entity_id: str
    uri: str
    kind: str
    label: str
    freshness_state: str
    weight: float
    components: Mapping[str, float]
    reasons: Sequence[AttentionReason]
```

- [ ] **Step 4: Derive Phase 1 reasons in `compute_attention_candidates()`**

Inside `compute_attention_candidates()`, after `dispute_count` is computed, add:

```python
        evidence_source_count = support_count + dispute_count
```

In the `components` mapping, add:

```python
                    "evidence_source_count": float(evidence_source_count),
```

In the `AttentionCandidate(...)` call, add:

```python
                reasons=_derive_phase1_reasons(kind, support_count, dispute_count),
```

Add these helper functions above `_count_uri_objects()`:

```python
def _derive_phase1_reasons(kind: str, support_count: int, dispute_count: int) -> list[AttentionReason]:
    if kind != "proposition":
        return []

    evidence_source_count = support_count + dispute_count
    reasons: list[AttentionReason] = []

    if evidence_source_count == 0:
        reasons.append(
            AttentionReason(
                code="unscaffolded",
                direction="route_attention",
                strength="high",
                provenance="derived:unscaffolded_source_count(evidence_source_count)",
                next_action="scaffold_evidence_base",
            )
        )
        return reasons

    if evidence_source_count <= 2:
        reasons.append(
            AttentionReason(
                code="fragility",
                direction="increase_attention",
                strength="high" if evidence_source_count == 1 else "moderate",
                provenance="derived:fragility_source_count(evidence_source_count)",
                next_action="seek_independent_evidence",
            )
        )

    if support_count >= 1 and dispute_count >= 1:
        reasons.append(
            AttentionReason(
                code="contestation",
                direction="increase_attention",
                strength=_contestation_strength(support_count, dispute_count),
                provenance="derived:contestation_counts(support_count,dispute_count)",
                next_action="compare_contexts",
            )
        )

    if _has_strong_counterevidence(support_count, dispute_count):
        reasons.append(
            AttentionReason(
                code="strong_counterevidence",
                direction="decrease_attention",
                strength=_counterevidence_strength(support_count, dispute_count),
                provenance="derived:counterevidence_counts(support_count,dispute_count)",
                next_action="preserve_floor",
            )
        )

    return reasons


def _contestation_strength(support_count: int, dispute_count: int) -> str:
    weaker_count = min(support_count, dispute_count)
    stronger_count = max(support_count, dispute_count)
    if weaker_count >= 2:
        return "high"
    if stronger_count < weaker_count * 3:
        return "moderate"
    return "low"


def _has_strong_counterevidence(support_count: int, dispute_count: int) -> bool:
    if dispute_count >= 1 and support_count == 0:
        return True
    return dispute_count >= 2 * max(support_count, 1) and dispute_count >= 2


def _counterevidence_strength(support_count: int, dispute_count: int) -> str:
    if support_count == 0 and dispute_count >= 3:
        return "high"
    if support_count > 0 and dispute_count / support_count >= 3:
        return "high"
    return "moderate"
```

- [ ] **Step 5: Run the reason-derivation test**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_phase1_reason_derivation_is_proposition_scoped -q
```

Expected: PASS.

- [ ] **Step 6: Run the existing attention unit tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat: derive reason-coded attention payloads"
```

## Task 2: Emit Reasons In JSON Without Breaking Table Output

**Files:**
- Modify: `science/tests/test_attention_sampling.py`
- Modify: `science/src/science_tool/graph/attention.py`

- [ ] **Step 1: Add failing formatting tests**

Append these tests to `science/tests/test_attention_sampling.py`:

```python
def test_format_attention_candidate_includes_reasons_for_json_ready_rows() -> None:
    candidates = compute_attention_candidates(_reason_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}

    row = format_attention_candidate(by_id["proposition:unscaffolded"])

    assert row["belief_weight"] is None
    assert row["influence_weight"] is None
    assert row["evidence_source_count"] == "0"
    assert row["reasons"] == [
        {
            "code": "unscaffolded",
            "direction": "route_attention",
            "strength": "high",
            "provenance": "derived:unscaffolded_source_count(evidence_source_count)",
            "next_action": "scaffold_evidence_base",
        }
    ]


def test_format_attention_candidate_uses_empty_reasons_list_when_no_reason_qualifies() -> None:
    candidates = compute_attention_candidates(_reason_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}

    row = format_attention_candidate(by_id["hypothesis:not_reason_scoped"])

    assert row["reasons"] == []
```

Update the import in that test file to include `format_attention_candidate`:

```python
from science_tool.graph.attention import (
    compute_attention_candidates,
    format_attention_candidate,
    weighted_sample_without_replacement,
)
```

- [ ] **Step 2: Run the failing formatting tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_format_attention_candidate_includes_reasons_for_json_ready_rows science/tests/test_attention_sampling.py::test_format_attention_candidate_uses_empty_reasons_list_when_no_reason_qualifies -q
```

Expected: FAIL because formatted rows do not include `belief_weight`, `influence_weight`, `evidence_source_count`, or `reasons`.

- [ ] **Step 3: Update `format_attention_candidate()` return type and body**

In `attention.py`, change the signature:

```python
def format_attention_candidate(candidate: AttentionCandidate) -> dict[str, Any]:
```

Update the returned mapping to include the new fields:

```python
    return {
        "id": candidate.entity_id,
        "kind": candidate.kind,
        "label": candidate.label,
        "freshness_state": candidate.freshness_state,
        "attention_weight": f"{candidate.weight:.4f}",
        "belief_weight": None,
        "influence_weight": None,
        "incoming_bears_on": str(int(components["incoming_bears_on"])),
        "days_since_last_review": f"{components['days_since_last_review']:.0f}",
        "support_count": str(int(components["support_count"])),
        "dispute_count": str(int(components["dispute_count"])),
        "evidence_source_count": str(int(components["evidence_source_count"])),
        "evidence_balance_factor": f"{components['evidence_balance_factor']:.2f}",
        "reasons": [reason.as_dict() for reason in candidate.reasons],
    }
```

Change `query_attention_sample()` return type:

```python
) -> list[dict[str, Any]]:
```

- [ ] **Step 4: Run formatting tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_format_attention_candidate_includes_reasons_for_json_ready_rows science/tests/test_attention_sampling.py::test_format_attention_candidate_uses_empty_reasons_list_when_no_reason_qualifies -q
```

Expected: PASS.

- [ ] **Step 5: Run all attention tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat: emit attention reasons in formatted rows"
```

## Task 3: Preserve CLI Default Behavior And JSON Reason Payload

**Files:**
- Modify: `science/tests/test_attention_sampling.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Add a failing CLI JSON assertion**

In `test_graph_attention_sample_cli_outputs_seeded_json()`, after `assert rows[0]["freshness_state"]`, add:

```python
    assert "belief_weight" in rows[0]
    assert "influence_weight" in rows[0]
    assert "reasons" in rows[0]
```

Append this test:

```python
def test_graph_attention_sample_cli_table_does_not_print_raw_reason_dicts(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    save_canonical_graph_dataset(
        _reason_fixture(),
        graph_path,
        preferred_graph_order=[PROJECT_NS["graph/knowledge"]],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "graph",
            "attention-sample",
            "--path",
            str(graph_path),
            "--limit",
            "1",
            "--seed",
            "1",
            "--today",
            "2026-05-01",
        ],
    )

    assert result.exit_code == 0
    assert '"code":' not in result.output
    assert "'code':" not in result.output
    assert "Reasons" in result.output
```

- [ ] **Step 2: Run the failing CLI table test**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_graph_attention_sample_cli_table_does_not_print_raw_reason_dicts -q
```

Expected: FAIL because the table does not include a `Reasons` column yet.

- [ ] **Step 3: Add a table-friendly reason summary**

In `science/src/science_tool/cli.py`, before `emit_query_rows(...)` inside `graph_attention_sample()`, add:

```python
    table_rows = rows
    if output_format == "table":
        table_rows = [
            {
                **row,
                "reasons": ", ".join(reason["code"] for reason in row.get("reasons", [])),
            }
            for row in rows
        ]
```

In the `emit_query_rows(...)` call, change `rows=rows` to:

```python
        rows=table_rows,
```

Add reason and evidence-source columns to the columns list immediately after `("dispute_count", "Disputes")` and before `("label", "Label")`, so `Label` remains the final table column:

```python
            ("evidence_source_count", "Evidence Sources"),
            ("reasons", "Reasons"),
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_graph_attention_sample_cli_outputs_seeded_json science/tests/test_attention_sampling.py::test_graph_attention_sample_cli_table_does_not_print_raw_reason_dicts -q
```

Expected: PASS.

- [ ] **Step 5: Run all attention tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add science/src/science_tool/cli.py science/tests/test_attention_sampling.py
git commit -m "feat: expose attention reasons in graph CLI"
```

## Task 4: Add Phase 1.5 Reason-Aware Review Routing Toggle

**Files:**
- Modify: `science/tests/test_attention_sampling.py`
- Modify: `science/src/science_tool/graph/attention.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Add failing unit tests for bounded reason-aware routing**

Append these tests to `science/tests/test_attention_sampling.py`:

```python
def test_reason_aware_sample_promotes_uncertainty_but_caps_review_routing() -> None:
    candidates = compute_attention_candidates(_reason_fixture(), today=date(2026, 5, 1))

    sampled = reason_aware_sample_candidates(candidates, limit=5, seed=17)

    assert [candidate.entity_id for candidate in sampled[:2]] == [
        "proposition:contested",
        "proposition:fragile",
    ]
    assert "hypothesis:not_reason_scoped" in {candidate.entity_id for candidate in sampled}
    assert len(sampled) == 5


def test_reason_aware_sample_does_not_promote_counterevidence_or_unscaffolded_first() -> None:
    candidates = compute_attention_candidates(_reason_fixture(), today=date(2026, 5, 1))

    sampled = reason_aware_sample_candidates(candidates, limit=2, seed=17)

    assert [candidate.entity_id for candidate in sampled] == [
        "proposition:contested",
        "proposition:fragile",
    ]
```

Update the test import to include `reason_aware_sample_candidates`.

- [ ] **Step 2: Run the failing reason-aware routing tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_reason_aware_sample_promotes_uncertainty_but_caps_review_routing science/tests/test_attention_sampling.py::test_reason_aware_sample_does_not_promote_counterevidence_or_unscaffolded_first -q
```

Expected: FAIL because `reason_aware_sample_candidates` does not exist.

- [ ] **Step 3: Implement bounded reason-aware review routing**

In `attention.py`, add this function above `weighted_sample_without_replacement()`:

```python
def reason_aware_sample_candidates(
    candidates: Sequence[AttentionCandidate],
    *,
    limit: int,
    seed: int | None = None,
) -> list[AttentionCandidate]:
    """Sample candidates with a bounded reason-coded review slice.

    This is a review-routing toggle, not a replacement belief model. It promotes
    ordinary uncertainty reasons first, then fills the rest using the existing
    weighted sampler so the epsilon floor remains meaningful.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if limit == 0 or not candidates:
        return []

    promoted = [candidate for candidate in candidates if _is_uncertainty_review_candidate(candidate)]
    promoted = sorted(promoted, key=_reason_route_sort_key)
    promoted_limit = min(len(promoted), max(1, limit // 2))
    review_slice = promoted[:promoted_limit]

    remaining_limit = limit - len(review_slice)
    if remaining_limit == 0:
        return review_slice

    selected_ids = {candidate.entity_id for candidate in review_slice}
    tail_pool = [candidate for candidate in candidates if candidate.entity_id not in selected_ids]
    return review_slice + weighted_sample_without_replacement(tail_pool, limit=remaining_limit, seed=seed)


def _is_uncertainty_review_candidate(candidate: AttentionCandidate) -> bool:
    codes = {reason.code for reason in candidate.reasons}
    if "strong_counterevidence" in codes or "unscaffolded" in codes:
        return False
    return bool(codes & {"contestation", "fragility"})


def _reason_route_sort_key(candidate: AttentionCandidate) -> tuple[int, float, str]:
    codes = {reason.code for reason in candidate.reasons}
    if "contestation" in codes:
        bucket = 0
    elif "fragility" in codes:
        bucket = 1
    else:
        bucket = 2
    return (bucket, -candidate.weight, candidate.entity_id)
```

- [ ] **Step 4: Add query option for reason-aware mode**

Change `query_attention_sample()` signature in `attention.py`:

```python
    reason_aware: bool = False,
) -> list[dict[str, Any]]:
```

Replace:

```python
    sample = weighted_sample_without_replacement(candidates, limit=limit, seed=seed)
```

with:

```python
    if reason_aware:
        sample = reason_aware_sample_candidates(candidates, limit=limit, seed=seed)
    else:
        sample = weighted_sample_without_replacement(candidates, limit=limit, seed=seed)
```

- [ ] **Step 5: Run routing tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_reason_aware_sample_promotes_uncertainty_but_caps_review_routing science/tests/test_attention_sampling.py::test_reason_aware_sample_does_not_promote_counterevidence_or_unscaffolded_first -q
```

Expected: PASS.

- [ ] **Step 6: Add failing CLI test for `--reason-aware`**

Append this test:

```python
def test_graph_attention_sample_cli_reason_aware_json_uses_bounded_review_route(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    save_canonical_graph_dataset(
        _reason_fixture(),
        graph_path,
        preferred_graph_order=[PROJECT_NS["graph/knowledge"]],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "graph",
            "attention-sample",
            "--path",
            str(graph_path),
            "--limit",
            "2",
            "--today",
            "2026-05-01",
            "--reason-aware",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    rows = json.loads(result.output)["rows"]
    assert [row["id"] for row in rows] == [
        "proposition:contested",
        "proposition:fragile",
    ]
```

- [ ] **Step 7: Run the failing CLI reason-aware test**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_graph_attention_sample_cli_reason_aware_json_uses_bounded_review_route -q
```

Expected: FAIL because the CLI does not accept `--reason-aware`.

- [ ] **Step 8: Wire `--reason-aware` through the CLI**

In `science/src/science_tool/cli.py`, add this option above `def graph_attention_sample(...)`:

```python
@click.option(
    "--reason-aware",
    is_flag=True,
    help="Use opt-in reason-coded review routing before weighted random sampling.",
)
```

Add `reason_aware: bool,` to the command function parameters.

In the `query_attention_sample(...)` call, pass:

```python
            reason_aware=reason_aware,
```

- [ ] **Step 9: Run Phase 1.5 CLI test**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py::test_graph_attention_sample_cli_reason_aware_json_uses_bounded_review_route -q
```

Expected: PASS.

- [ ] **Step 10: Run all attention tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit Task 4**

Run:

```bash
git add science/src/science_tool/graph/attention.py science/src/science_tool/cli.py science/tests/test_attention_sampling.py
git commit -m "feat: add reason-aware attention routing"
```

## Task 5: Verify Full Upstream Checks

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --frozen pytest science/tests/test_attention_sampling.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting and lint checks**

Run:

```bash
uv run --frozen ruff format --check science/src/science_tool/graph/attention.py science/src/science_tool/cli.py science/tests/test_attention_sampling.py
uv run --frozen ruff check science/src/science_tool/graph/attention.py science/src/science_tool/cli.py science/tests/test_attention_sampling.py
```

Expected: both commands PASS.

- [ ] **Step 3: Run graph CLI smoke test on the meta graph if present**

Run:

```bash
uv run --frozen science graph attention-sample --limit 5 --seed 17 --format json
uv run --frozen science graph attention-sample --limit 5 --reason-aware --format json
```

Expected: both commands exit 0 and JSON rows include `reasons`.
If the default graph path is absent, run the same commands with a known local `--path` fixture or skip this smoke test with the absence recorded in the final implementation note.

- [ ] **Step 4: Commit any final formatting-only changes**

If Step 2 reformatted files, run:

```bash
git add science/src/science_tool/graph/attention.py science/src/science_tool/cli.py science/tests/test_attention_sampling.py
git commit -m "style: format reason-coded attention changes"
```

If Step 2 made no changes, do not create an empty commit.

## Self-Review Checklist

- Phase 1 default sampling formula is unchanged.
- Phase 1 reason derivation is proposition-only.
- `reasons: []` is emitted when the reason pass runs and no reason qualifies.
- `belief_weight` and `influence_weight` are present as reserved `null` fields in JSON rows.
- `query_attention_sample()` and `format_attention_candidate()` return types are widened to `dict[str, Any]` because formatted rows now contain strings, nulls, and nested reason lists.
- `unscaffolded` handles `evidence_source_count == 0`.
- `fragility` handles only non-zero low evidence-source counts.
- `contestation` and `strong_counterevidence` can co-exist and are not silently averaged.
- Phase 1.5 does not promote `unscaffolded` stubs or `strong_counterevidence` candidates ahead of ordinary uncertainty-review candidates.
- Phase 1.5 fills the non-promoted tail with `weighted_sample_without_replacement()` so the epsilon floor still matters.
- `--reason-aware` is opt-in review routing for pilot comparison, not a replacement belief model.
- Table output does not dump raw Python/JSON reason dictionaries.

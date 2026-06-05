# M1 Epistemic Drift Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship M1 of the epistemic-drift detection design — an open-question-debt attention term that raises the attention weight of epistemic entities carrying unincorporated questions, plus an artifact-guard on the `entity review` command so a review can no longer be a bare timestamp bump, plus the agentic review skill that performs the actual scrutiny.

**Architecture:** Three independently-shippable parts against `~/d/science/science` (the Python tool) and `~/d/science` (the skill source under `commands/`). **Part A** adds a graph-computed debt signal to `compute_attention_candidates` over `skos:related` edges + theme co-membership (deliberately *not* `bears_on`, per the design's load-bearing constraint), and a deterministic `graph attention-rank` command to surface it as a review queue. **Part B** adds a `require_artifact` guard inside `review_entity` (after entity resolution + the epistemic-kind gate) so `entity review` refuses an empty artifact without masking lookup/kind errors. **Part C** authors the durable `commands/review.md` source and regenerates the `science-review` skill (per-kind rubrics + artifact-required checklist). Parts A and B are pure-code TDD; Part C is skill authoring via the generator.

**Tech Stack:** Python 3.13, `rdflib` (TriG knowledge graph), `click` CLI, `pytest`, `uv` for env management. Skills are Markdown under `codex-skills/`.

**Design source:** `docs/plans/2026-06-04-epistemic-drift-detection-design.md` (mechanisms 2 + 3, staged rollout M1; revised 2026-06-05 for entity-layout and dataset-kind drift).
**Anchor question:** `science-meta:question:15-claim-operationalization-drift`.
**Regression fixture (real data):** in `multiple-myeloma`, `question:01-double-hit-expression-validation` and `question:38-mafb-paradox-transcriptomic-profile-mm30` already carry `skos:related → hypothesis:h2-...` with `projectStatus "active"`; so the Part A term surfaces H2 against live data today.

---

## Grounding facts (verified against current code on 2026-06-05)

These were confirmed by reading the code; the implementer can trust them without re-deriving.

- `compute_attention_candidates` (`science/src/science_tool/graph/attention.py:66`) iterates entities carrying `sci:freshnessState`, computes a multiplicative `weight` from `incoming_bears_on`, `days_since_last_review`, `freshness_multiplier`, `evidence_balance_factor`, then `+ epsilon`. It already imports `SKOS` (`rdflib.namespace`) and `canonical_id_from_entity_uri` (`graph.store`).
- `related:` frontmatter is materialized as `skos:related` triples, **subject = authoring entity** (`materialize.py:353`). To find questions related to an entity you must check **both** directions.
- A question node carries `sci:projectStatus "<status>"` (`materialize.py:247`) but **no** `created`/`updated`/`lastReviewed` triples in the knowledge graph — so question-age weighting is **not** computable from the graph alone and is explicitly deferred out of M1 (documented, not silently dropped).
- Theme entities exist (`a sci:Theme`, kind prefix `theme`); an entity and a question are "theme co-members" when both `skos:related` the same theme node.
- `canonical_id_from_entity_uri(str(uri))` returns e.g. `"question:06-..."`; the kind is the substring before the first `:`.
- Question debt statuses are the canonical vocabulary `active` / `partially-answered` / `deferred` (`science/model/src/science_model/entities.py:97`); `answered` / `retired` are resolved, not debt.
- `review_entity` (`entity_review.py:39`) is called from exactly one production site — the CLI `entity_review` command (`cli.py:486`). No programmatic freshness caller does a bare bump. The artifact guard goes **inside `review_entity`** behind `require_artifact` (default `False`), placed after `find_entity` and the epistemic-kind gate so lookup/kind errors fire first; the CLI passes `require_artifact=True`. `review_entity`'s note semantics (`None`=keep, `""`=clear, str=replace) stay intact for direct/unit callers (default path).
- The only existing attention CLI is `graph attention-sample` (`cli.py:1655`) → `query_attention_sample` (`attention.py:222`), which returns a **weighted random sample**, not a stable ranking. M1 adds a deterministic `graph attention-rank` for review targeting.
- `codex-skills/` is **generated** by `generate_codex_skills` (`codex_skills.py:33`) from `commands/*.md` + `COMPANION_SKILLS`, writing each `SKILL.md` and `INDEX.md` and injecting `references/command-preamble.md`. The durable source for a new skill is a `commands/*.md` file; run `scripts/generate_codex_skills.py` to build the outputs.
- Source-authored entities now default to `entities/` after the Plan 3 hard cutover. `load_project_sources` still explicitly scans `research/packages`, `doc/datasets`, `doc/workflows`, and `doc/workflow-runs` as transitional operational roots; do not assume a root-level `entities/` directory exists in this repository checkout itself.
- `dataset`, `paper`, `workflow`, `workflow-run`, `research-package`, `task`, `plan`, `pre-registration`, and similar kinds are operational in `EntityRegistry.with_core_types()`, and the model rejects `review_state` on known non-epistemic kinds. The Part B guard stays epistemic-only; the review skill may inspect operational entities as evidence/manifests but must stamp the reviewed epistemic claim, not the operational source.
- Tests run from the Python project dir: `cd ~/d/science/science && uv run pytest <path>`. The generator runs from the repo root: `cd ~/d/science && uv run --project science python scripts/generate_codex_skills.py`.

---

## File structure

| File | Part | Responsibility | Change |
|------|------|----------------|--------|
| `science/src/science_tool/graph/attention.py` | A | attention scoring | add debt helpers, fold debt into weight + components + a reason; add `query_attention_ranked` |
| `science/src/science_tool/cli.py` | A, B | CLI | add `graph attention-rank`; pass `require_artifact=True` to `entity review` |
| `science/tests/test_attention_sampling.py` | A | attention tests | update exact-components assertion; add debt-term + ranked-query tests |
| `science/src/science_tool/entity_review.py` | B | review mutation | add `require_artifact` guard after resolution + kind gate |
| `science/tests/test_entity_review_cli.py` | B | CLI tests | add guard + ordering tests; supply `--note` to bare-bump setups |
| `commands/review.md` | C | skill source (durable) | new command source for the review skill |
| `codex-skills/` (generated) | C | skill registry | regenerated by `generate_codex_skills.py` |

---

# Part A — Open-question-debt attention term

**Files:**
- Modify: `science/src/science_tool/graph/attention.py`
- Test: `science/tests/test_attention_sampling.py`

### Task A1: Debt-counting helpers (related + theme co-membership)

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` (add module constants near line 22; add helpers near the other `_*` helpers, e.g. after `_count_uri_objects` at line 364)
- Test: `science/tests/test_attention_sampling.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_attention_sampling.py` (after the imports, extend the `from science_tool.graph.attention import (...)` block to also import `_open_question_debt`):

```python
def _debt_fixture() -> Dataset:
    """An entity with: 1 directly-related active question, 1 related-but-answered
    question (not debt), 1 question reachable only via a shared theme, and 1
    deferred question related to a *different* entity (must not count)."""
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    h = _u("hypothesis/h_scope")
    other = _u("hypothesis/h_other")
    theme = _u("theme/cyto_scope")
    q_direct = _u("question/q_direct")        # active, related -> h  (debt)
    q_answered = _u("question/q_answered")    # answered, related -> h (NOT debt)
    q_theme = _u("question/q_theme")          # partially-answered, theme co-member (debt)
    q_elsewhere = _u("question/q_elsewhere")  # deferred, related -> other only (NOT debt for h)

    for uri, label in (
        (h, "Scoped hypothesis"),
        (other, "Unrelated hypothesis"),
    ):
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        knowledge.add((uri, SCI_NS.lastReviewed, Literal("2026-04-30", datatype=XSD.date)))

    knowledge.add((theme, RDF.type, SCI_NS.Theme))
    knowledge.add((h, SKOS.related, theme))

    # direction matters: questions author the related: edge -> question is subject
    knowledge.add((q_direct, SKOS.related, h))
    knowledge.add((q_direct, SCI_NS.projectStatus, Literal("active")))

    knowledge.add((q_answered, SKOS.related, h))
    knowledge.add((q_answered, SCI_NS.projectStatus, Literal("answered")))

    knowledge.add((q_theme, SKOS.related, theme))
    knowledge.add((q_theme, SCI_NS.projectStatus, Literal("partially-answered")))

    knowledge.add((q_elsewhere, SKOS.related, other))
    knowledge.add((q_elsewhere, SCI_NS.projectStatus, Literal("deferred")))

    return dataset


def test_open_question_debt_counts_related_and_theme_comembers() -> None:
    dataset = _debt_fixture()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef(PROJECT_NS["hypothesis/h_scope"])
    other = URIRef(PROJECT_NS["hypothesis/h_other"])

    # h: q_direct (active, direct) + q_theme (partially-answered, via theme) = 2
    #    q_answered excluded (resolved); q_elsewhere excluded (not connected to h)
    assert _open_question_debt(knowledge, h) == 2
    # other: only q_elsewhere (deferred, direct) = 1
    assert _open_question_debt(knowledge, other) == 1
    # q_theme is a theme co-member of itself; it must not count itself as debt.
    q_theme = URIRef(PROJECT_NS["question/q_theme"])
    assert _open_question_debt(knowledge, q_theme) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py::test_open_question_debt_counts_related_and_theme_comembers -v`
Expected: FAIL with `ImportError: cannot import name '_open_question_debt'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/graph/attention.py`, add the constants just below the existing weight constants (after line 22, `NEVER_REVIEWED_DAYS = 365.0`):

```python
OPEN_QUESTION_DEBT_WEIGHT = 0.5
# Canonical question debt statuses (science_model entities.py); resolved
# states (answered/retired) are deliberately excluded — they are not debt.
DEBT_QUESTION_STATUSES = frozenset({"active", "partially-answered", "deferred"})
```

Then add these helpers near the other private helpers (e.g. after `_count_uri_objects`, line ~364):

```python
def _entity_kind_of(uri: URIRef) -> str | None:
    canonical_id = canonical_id_from_entity_uri(str(uri))
    if canonical_id is None:
        return None
    return canonical_id.partition(":")[0]


def _related_neighbors(knowledge, uri: URIRef) -> set[URIRef]:
    """All entities joined to ``uri`` by a skos:related edge, either direction.

    `related:` is materialized subject=authoring-entity (materialize.py:353), so a
    question that lists an entity in its `related:` shows up as an *incoming* edge.
    """
    neighbors: set[URIRef] = set()
    for obj in knowledge.objects(uri, SKOS.related):
        if isinstance(obj, URIRef):
            neighbors.add(obj)
    for subj in knowledge.subjects(SKOS.related, uri):
        if isinstance(subj, URIRef):
            neighbors.add(subj)
    return neighbors


def _open_question_debt(knowledge, entity_uri: URIRef) -> int:
    """Count debt-status questions bearing on ``entity_uri`` via the connectivity
    layer freshness ignores: direct skos:related (either direction) plus theme
    co-membership (entity and question both related to the same theme node).

    Intentionally does NOT use bears_on: scoping questions sit on related: edges
    or weaker, which never become bears_on (freshness.py:70), so a bears_on-based
    metric would inherit the exact blind spot this term exists to cover. Question
    age is not weighted here because created/updated are not emitted as graph
    triples (see plan grounding facts); age weighting is deferred past M1.
    """
    neighbors = _related_neighbors(knowledge, entity_uri)
    question_uris: set[URIRef] = set()
    for neighbor in neighbors:
        kind = _entity_kind_of(neighbor)
        if kind == "question":
            question_uris.add(neighbor)
        elif kind == "theme":
            for theme_neighbor in _related_neighbors(knowledge, neighbor):
                if _entity_kind_of(theme_neighbor) == "question":
                    question_uris.add(theme_neighbor)

    # A question is itself an attention candidate (it carries freshnessState) and a
    # question→theme edge makes the question a theme co-member of itself. Never let
    # an entity count itself as its own debt.
    question_uris.discard(entity_uri)

    debt = 0
    for question_uri in question_uris:
        status_literal = next(knowledge.objects(question_uri, SCI_NS.projectStatus), None)
        if status_literal is not None and str(status_literal) in DEBT_QUESTION_STATUSES:
            debt += 1
    return debt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py::test_open_question_debt_counts_related_and_theme_comembers -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat(attention): add open-question-debt helpers over related + theme"
```

### Task A2: Fold debt into the attention weight, components, and a reason

**Files:**
- Modify: `science/src/science_tool/graph/attention.py:66` (`compute_attention_candidates`), add a reason helper
- Test: `science/tests/test_attention_sampling.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_attention_sampling.py`:

```python
def test_open_question_debt_raises_weight_and_emits_reason() -> None:
    candidates = compute_attention_candidates(_debt_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}

    indebted = by_id["hypothesis:h_scope"]   # debt 2
    light = by_id["hypothesis:h_other"]       # debt 1

    assert indebted.components["open_question_debt"] == 2.0
    assert light.components["open_question_debt"] == 1.0
    # both fresh, same review date, no evidence/bears_on -> debt is the only
    # differentiator, so more debt must mean strictly more weight.
    assert indebted.weight > light.weight

    debt_reasons = [r for r in indebted.reasons if r.code == "open_question_debt"]
    assert debt_reasons == [
        AttentionReason(
            code="open_question_debt",
            direction="increase_attention",
            strength="moderate",
            provenance="derived:open_question_debt(related+theme,2)",
            next_action="incorporate_or_answer_open_questions",
        )
    ]


def test_zero_debt_emits_no_debt_reason() -> None:
    candidates = compute_attention_candidates(_attention_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}
    for candidate in by_id.values():
        assert all(r.code != "open_question_debt" for r in candidate.reasons)
        assert candidate.components["open_question_debt"] == 0.0
```

Extend the existing import block to also import `AttentionReason`:

```python
from science_tool.graph.attention import (
    AttentionReason,
    compute_attention_candidates,
    format_attention_candidate,
    reason_aware_sample_candidates,
    weighted_sample_without_replacement,
    _open_question_debt,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py::test_open_question_debt_raises_weight_and_emits_reason -v`
Expected: FAIL with `KeyError: 'open_question_debt'`.

- [ ] **Step 3: Update the existing exact-components assertion (it will otherwise break)**

In `science/tests/test_attention_sampling.py`, the `test_attention_weight_uses_observable_graph_features` assertion (lines 118–127) pins the components dict exactly. Add the new key:

```python
    assert contested.components == {
        "incoming_bears_on": 2.0,
        "days_since_last_review": 30.0,
        "freshness_multiplier": 3.0,
        "support_count": 1.0,
        "dispute_count": 1.0,
        "evidence_source_count": 2.0,
        "evidence_balance_factor": 2.0,
        "open_question_debt": 0.0,
        "epsilon": 0.05,
    }
```

- [ ] **Step 4: Write minimal implementation**

In `science/src/science_tool/graph/attention.py`, add a reason helper (near `_derive_phase1_reasons`):

```python
def _open_question_debt_reason(debt: int) -> AttentionReason:
    if debt >= 3:
        strength = "high"
    elif debt == 2:
        strength = "moderate"
    else:
        strength = "low"
    return AttentionReason(
        code="open_question_debt",
        direction="increase_attention",
        strength=strength,
        provenance=f"derived:open_question_debt(related+theme,{debt})",
        next_action="incorporate_or_answer_open_questions",
    )
```

In `compute_attention_candidates`, inside the loop, compute the debt after `freshness_multiplier` is set (around line 103) and fold it into the weight and components. Replace the existing `weight = (...) + epsilon` block and the `AttentionCandidate(...)` construction so the debt participates:

```python
        freshness_multiplier = _freshness_multiplier(freshness_state)
        open_question_debt = _open_question_debt(knowledge, entity_uri)

        weight = (
            (1.0 + incoming_bears_on)
            * (1.0 + (days_since_last_review / 30.0))
            * freshness_multiplier
            * evidence_balance_factor
            * (1.0 + OPEN_QUESTION_DEBT_WEIGHT * open_question_debt)
        ) + epsilon

        reasons = list(_derive_phase1_reasons(kind, support_count, dispute_count))
        if open_question_debt > 0:
            reasons.append(_open_question_debt_reason(open_question_debt))

        candidates.append(
            AttentionCandidate(
                entity_id=entity_id,
                uri=str(entity_uri),
                kind=kind,
                label=_label_for(knowledge, entity_uri, entity_id),
                freshness_state=freshness_state,
                weight=weight,
                components={
                    "incoming_bears_on": float(incoming_bears_on),
                    "days_since_last_review": float(days_since_last_review),
                    "freshness_multiplier": float(freshness_multiplier),
                    "support_count": float(support_count),
                    "dispute_count": float(dispute_count),
                    "evidence_source_count": float(evidence_source_count),
                    "evidence_balance_factor": float(evidence_balance_factor),
                    "open_question_debt": float(open_question_debt),
                    "epsilon": float(epsilon),
                },
                reasons=reasons,
            )
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py -v`
Expected: PASS — the two new tests, the updated exact-components test, and all pre-existing tests (the reason-derivation tests use a fixture with no questions, so debt is 0 and their reason lists are unchanged).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat(attention): weight entities by open-question debt + emit reason"
```

### Task A3: Surface debt in the formatted attention row

**Files:**
- Modify: `science/src/science_tool/graph/attention.py:257` (`format_attention_candidate`)
- Test: `science/tests/test_attention_sampling.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_attention_sampling.py`:

```python
def test_format_attention_candidate_exposes_open_question_debt() -> None:
    candidates = compute_attention_candidates(_debt_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}
    row = format_attention_candidate(by_id["hypothesis:h_scope"])
    assert row["open_question_debt"] == "2"
    assert any(r["code"] == "open_question_debt" for r in row["reasons"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py::test_format_attention_candidate_exposes_open_question_debt -v`
Expected: FAIL with `KeyError: 'open_question_debt'`.

- [ ] **Step 3: Write minimal implementation**

In `format_attention_candidate` (`attention.py:257`), add the field to the returned dict, right after the `"evidence_balance_factor"` line (line 275):

```python
        "evidence_balance_factor": f"{components['evidence_balance_factor']:.2f}",
        "open_question_debt": str(int(components["open_question_debt"])),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py -v`
Expected: PASS (all attention tests).

- [ ] **Step 5: Guard the downstream consumers (wander/curate/next-steps/status)**

The `open_question_debt` key now flows through every consumer of `format_attention_candidate` / `query_attention_sample`. Run the consuming suites to confirm none pins the row shape in a way the new key breaks:

Run: `cd ~/d/science/science && uv run pytest tests/test_wander_sampling.py tests/test_wander_context.py tests/test_curate_cli.py tests/test_status.py -v`
Expected: PASS. If a test fails on an exact-key assertion, add `open_question_debt` to its expected shape (do not remove the key). If a consumer formats a fixed table, decide whether the debt column is useful there; JSON rows should retain the key either way.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat(attention): surface open_question_debt in formatted rows"
```

### Task A4: Deterministic `graph attention-rank` command (review-queue surface)

The only existing attention CLI is `graph attention-sample` (`cli.py:1655`), which returns a **weighted random sample** — not a stable ranking. A review skill targeting "the most indebted/overdue entities" needs a deterministic ordered list. Add a sibling `graph attention-rank` command that returns all candidates sorted by attention weight (descending, ties broken by id), reusing the same candidate computation and belief-weight formatting.

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` (extract a shared row-builder; add `query_attention_ranked`)
- Modify: `science/src/science_tool/cli.py` (add the `attention-rank` command near `attention-sample`, line ~1655)
- Test: `science/tests/test_attention_sampling.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_attention_sampling.py` (the import block already pulls in `save_canonical_graph_dataset` via `from science_tool.graph.io import ...`; if not, add it):

```python
def test_query_attention_ranked_is_deterministic_by_weight(tmp_path: Path) -> None:
    from science_tool.graph.attention import query_attention_ranked
    from science_tool.graph.io import save_canonical_graph_dataset

    graph_path = tmp_path / "graph.trig"
    save_canonical_graph_dataset(_debt_fixture(), graph_path)

    rows = query_attention_ranked(graph_path, today=date(2026, 5, 1))
    ids = [row["id"] for row in rows]
    # h_scope (debt 2) outranks h_other (debt 1); both carry the debt field.
    assert ids.index("hypothesis:h_scope") < ids.index("hypothesis:h_other")
    assert rows[0]["open_question_debt"] == "2"

    top1 = query_attention_ranked(graph_path, today=date(2026, 5, 1), limit=1)
    assert [row["id"] for row in top1] == ["hypothesis:h_scope"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py::test_query_attention_ranked_is_deterministic_by_weight -v`
Expected: FAIL with `ImportError: cannot import name 'query_attention_ranked'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/graph/attention.py`, extract the belief-formatting tail of `query_attention_sample` into a shared helper, then add the ranked query. Replace the body of `query_attention_sample` (lines 232–254) so it delegates to the helper, and add the two new functions after it:

```python
def query_attention_sample(
    graph_path: Path,
    *,
    limit: int,
    seed: int | None = None,
    today: date | None = None,
    kinds: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
    reason_aware: bool = False,
) -> list[dict[str, Any]]:
    """Load a materialized graph and return sampled attention rows."""
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    if reason_aware:
        sample = reason_aware_sample_candidates(candidates, limit=limit, seed=seed)
    else:
        sample = weighted_sample_without_replacement(candidates, limit=limit, seed=seed)
    return _rows_with_belief(graph_path, dataset, sample)


def query_attention_ranked(
    graph_path: Path,
    *,
    limit: int | None = None,
    today: date | None = None,
    kinds: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
) -> list[dict[str, Any]]:
    """Load a materialized graph and return all candidates ranked by weight desc.

    Deterministic (no sampling): ties break by entity_id. This is the review-queue
    surface — `graph attention-rank` — distinct from the weighted-random
    `attention-sample`.
    """
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    ranked = sorted(candidates, key=lambda candidate: (-candidate.weight, candidate.entity_id))
    if limit is not None:
        ranked = ranked[:limit]
    return _rows_with_belief(graph_path, dataset, ranked)


def _rows_with_belief(
    graph_path: Path, dataset: Dataset, candidates: Sequence[AttentionCandidate]
) -> list[dict[str, Any]]:
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))

    def _belief_weight(candidate: AttentionCandidate) -> dict[str, Any] | None:
        if not enabled:
            return None
        units = collect_evidence_units(
            knowledge, provenance, _evidence_targets_for_uri(knowledge, URIRef(candidate.uri))
        )
        result = aggregate_belief(units)
        return format_belief_weight(result, belief_scalar(result))

    return [format_attention_candidate(c, belief_weight=_belief_weight(c)) for c in candidates]
```

In `science/src/science_tool/cli.py`, add a command immediately after `graph_attention_sample` (after line ~1700, the end of that function). Mirror its options minus `--seed`/`--reason-aware`:

```python
@graph.command("attention-rank")
@click.option("--limit", type=int, default=None, help="Cap the number of ranked rows (default: all).")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option("--today", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="Date for age weighting.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_attention_rank(
    limit: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    today: datetime | None,
    output_format: str,
    graph_path: Path,
) -> None:
    """Rank epistemic entities by graph-derived attention weight (deterministic)."""
    from science_tool.graph.attention import query_attention_ranked

    if limit is not None and limit < 0:
        raise click.ClickException("--limit must be >= 0")
    rank_date: date | None = today.date() if today is not None else None
    rows = query_attention_ranked(
        graph_path=graph_path,
        limit=limit,
        today=rank_date,
        kinds=set(kinds) if kinds else None,
        epsilon=epsilon,
    )
    emit_query_rows(
        output_format=output_format,
        title="Attention ranking",
        columns=[
            ("id", "ID"),
            ("kind", "Kind"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("open_question_debt", "Q-Debt"),
        ],
        rows=rows,
    )
```

> Confirm `emit_query_rows` is already imported in `cli.py` (it is used by `entity_needs_review`); if the import is local to that function, add `from science_tool.output import emit_query_rows` at the top of `graph_attention_rank` to match the surrounding style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py -v`
Expected: PASS (new ranked test + all prior attention tests; `query_attention_sample` behavior is unchanged because the extracted helper is byte-for-byte its old tail).

- [ ] **Step 5: Smoke-test the CLI wiring**

Run: `cd ~/d/science/science && uv run python -c "from science_tool.cli import main; from click.testing import CliRunner; r=CliRunner().invoke(main, ['graph','attention-rank','--help']); print(r.exit_code); print('attention-rank' in r.output or r.output)"`
Expected: prints `0` and help text mentioning ranking.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/attention.py science/src/science_tool/cli.py science/tests/test_attention_sampling.py
git commit -m "feat(cli): add deterministic graph attention-rank review queue"
```

---

# Part B — Artifact guard on `entity review`

**Rationale:** The design's M1 calls for the review command to "refuse a bare timestamp bump without a recorded artifact." The guard must fire **only after** the entity resolves and passes the epistemic-kind gate — otherwise an unknown id or a non-epistemic target with no `--note` would wrongly report "needs artifact" instead of "not found" / "non-epistemic" (the existing `test_entity_review_unknown_id_errors` and `test_entity_review_rejects_non_epistemic_target` depend on those errors firing first). So the check goes **inside `review_entity`**, behind a new `require_artifact` parameter, placed after `find_entity` and the kind gate. The CLI passes `require_artifact=True`; direct/unit callers default to `False`, preserving `review_entity`'s `note=None`/`""`/str semantics.

**Files:**
- Modify: `science/src/science_tool/entity_review.py:39` (`review_entity` signature + guard)
- Modify: `science/src/science_tool/cli.py:483-498` (`entity_review` passes `require_artifact=True`, help text)
- Test: `science/tests/test_entity_review_cli.py`

### Task B1: Reject empty artifact after resolution + kind gate

**Files:**
- Modify: `science/src/science_tool/entity_review.py`
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_entity_review_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_entity_review_cli.py`:

```python
def test_entity_review_requires_artifact(tmp_path: Path, monkeypatch):
    """A bare `entity review` (no --note) is review-theater and must be refused."""
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code != 0
    assert "artifact" in result.output.lower() or "note" in result.output.lower()
    # frontmatter must be untouched
    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert "review_state:" not in text


def test_entity_review_rejects_blank_note(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "   "])
    assert result.exit_code != 0
    assert "artifact" in result.output.lower() or "note" in result.output.lower()


def test_entity_review_succeeds_with_artifact(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["entity", "review", "hypothesis:h1", "--note", "scope re-checked vs constants.py::EVENTS; no change"],
    )
    assert result.exit_code == 0, result.output
    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert "scope re-checked" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_review_cli.py::test_entity_review_requires_artifact tests/test_entity_review_cli.py::test_entity_review_rejects_blank_note -v`
Expected: FAIL — currently a bare review exits 0 and writes `review_state:`.

- [ ] **Step 3a: Add a regression test pinning the resolution-before-guard order**

Add to `science/tests/test_entity_review_cli.py`:

```python
def test_entity_review_unknown_id_errors_even_without_note(tmp_path: Path, monkeypatch):
    """Unknown id with no --note must still report 'not found', not 'needs artifact'."""
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "unknown" in result.output.lower()
    assert "artifact" not in result.output.lower()
```

- [ ] **Step 3b: Write minimal implementation**

In `science/src/science_tool/entity_review.py`, add the `require_artifact` parameter to `review_entity` (line 39) and place the guard **after** the kind gate (after line 70), before any frontmatter mutation:

```python
def review_entity(
    project_root: Path,
    entity_ref: str,
    *,
    note: str | None = None,
    today: date | None = None,
    require_artifact: bool = False,
) -> tuple[Path, bool]:
    """Set review_state.last_reviewed = today on the entity's frontmatter.

    Preserves any existing review_state fields. Note semantics: `note=None`
    keeps any existing `last_review_note`; `note=""` clears it; a non-empty
    string replaces it.

    When `require_artifact` is True, a missing/blank `note` is rejected (the
    review-theater guard): the review must record a concrete artifact. The check
    runs only after the entity resolves and passes the epistemic-kind gate, so
    lookup and kind errors still take precedence.

    Returns (path, changed) — `changed` is True iff the file was rewritten.
    Raises ReviewError on lookup failure, non-epistemic target, or (when
    require_artifact) a missing artifact.
    """
    today = today or date.today()
    try:
        location = find_entity(project_root, entity_ref)
    except EntityCommandError as exc:
        raise ReviewError(str(exc)) from exc

    registry = EntityRegistry.with_core_types()
    try:
        kind_class = registry.kind_class(location.kind)
    except EntityKindNotRegisteredError:
        kind_class = None  # extension kinds default to allowed
    if kind_class is not None and kind_class != EntityClass.EPISTEMIC:
        raise ReviewError(
            f"entity {entity_ref!r} has kind {location.kind!r} "
            f"({kind_class.value}); review_state is only meaningful on epistemic entities"
        )

    if require_artifact and (note is None or not note.strip()):
        raise ReviewError(
            "review requires a recorded artifact: pass a note with the finding, "
            "prose diff, created task, or a reasoned 'no change'. "
            "A bare timestamp bump is not a review."
        )

    path = project_root / location.rel_path
    frontmatter = dict(location.frontmatter)
    # ... (rest of the function is unchanged)
```

(Leave everything from `rs_raw = frontmatter.get("review_state")` onward exactly as-is.)

In `science/src/science_tool/cli.py`, update the command (lines 483–498) to request the guard and refresh the help text:

```python
@entity_group.command("review")
@click.argument("ref")
@click.option(
    "--note",
    default=None,
    help="Required review artifact: the finding, prose diff, created task, or a "
    "reasoned 'no change'. A review without a recorded artifact is rejected.",
)
def entity_review(ref: str, note: str | None) -> None:
    """Mark an epistemic entity as reviewed-as-of today.

    A review must record an artifact via --note; a bare timestamp bump is
    rejected to prevent review-theater (see epistemic-drift-detection design M1).
    """
    from science_tool.entity_review import ReviewError, review_entity

    try:
        path, changed = review_entity(Path.cwd(), ref, note=note, require_artifact=True)
    except ReviewError as exc:
        raise click.ClickException(str(exc)) from exc
    rel = path.relative_to(Path.cwd())
    if changed:
        click.echo(f"Reviewed {ref} -> {rel}")
    else:
        click.echo(f"Reviewed {ref} -> {rel} (no changes)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_review_cli.py::test_entity_review_requires_artifact tests/test_entity_review_cli.py::test_entity_review_rejects_blank_note tests/test_entity_review_cli.py::test_entity_review_succeeds_with_artifact tests/test_entity_review_cli.py::test_entity_review_unknown_id_errors_even_without_note tests/test_entity_review_cli.py::test_entity_review_rejects_non_epistemic_target -v`
Expected: PASS — including the unknown-id and non-epistemic tests, which prove resolution/kind errors fire before the artifact guard.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_review.py science/src/science_tool/cli.py science/tests/test_entity_review_cli.py
git commit -m "feat(review): require a review artifact (guard after resolution + kind gate)"
```

### Task B2: Reconcile the existing CLI tests with the guard

The guard makes several existing tests fail because they invoke `entity review` with no `--note`. Two of them assert *note semantics* that are only reachable via the unchanged `review_entity` function, so they move down to the function level.

**Files:**
- Modify: `science/tests/test_entity_review_cli.py`

- [ ] **Step 1: Run the full file to see exactly what the guard broke**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_review_cli.py -v`
Expected: FAIL in `test_entity_review_sets_last_reviewed`, `test_entity_review_idempotent`, `test_entity_review_preserves_existing_review_horizon_days`, `test_entity_review_preserves_existing_note_when_no_note_passed`, `test_entity_review_clears_existing_note_when_empty_string_passed`, `test_entity_needs_review_empty_when_all_fresh` (each calls `review` without a note).

- [ ] **Step 2: Add `--note` to the bare-bump setups**

Edit these four tests so each `runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", ...])` carries a note:

`test_entity_review_sets_last_reviewed` — change the invoke to:
```python
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
```

`test_entity_review_idempotent` — change both invokes to:
```python
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
    text_first = (root / "entities" / "hypotheses" / "h1.md").read_text()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
    text_second = (root / "entities" / "hypotheses" / "h1.md").read_text()
```

`test_entity_review_preserves_existing_review_horizon_days` — change the invoke to:
```python
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "horizon check"])
```

`test_entity_needs_review_empty_when_all_fresh` — change the invoke to:
```python
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "reviewed for freshness"])
```

- [ ] **Step 3: Move the two note-semantics tests to the function level**

The "preserve existing note when no note passed" and "clear note on empty string" behaviors are properties of `review_entity` (`note=None` keeps, `note=""` clears) that the CLI guard now makes unreachable from the command. Replace both CLI tests with direct `review_entity` unit tests. First add the import near the top of the file:

```python
from science_tool.entity_review import review_entity
```

Then replace the body of `test_entity_review_preserves_existing_note_when_no_note_passed` with:

```python
def test_review_entity_preserves_existing_note_when_note_is_none(tmp_path: Path):
    """review_entity(note=None) keeps any pre-existing last_review_note."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "entities" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    review_entity(root, "hypothesis:h1", note=None)
    assert "Original note" in h_path.read_text()
```

And replace `test_entity_review_clears_existing_note_when_empty_string_passed` with:

```python
def test_review_entity_clears_note_on_empty_string(tmp_path: Path):
    """review_entity(note="") clears any pre-existing last_review_note."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "entities" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    review_entity(root, "hypothesis:h1", note="")
    text = h_path.read_text()
    assert "last_review_note" not in text
    assert "Original note" not in text
```

(`test_entity_review_records_note` and `test_entity_review_replaces_existing_note_when_new_note_passed` already pass `--note` and need no change.)

- [ ] **Step 4: Run the full file to verify green**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_review_cli.py -v`
Expected: PASS (all tests, including the new guard tests from B1).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/tests/test_entity_review_cli.py
git commit -m "test(cli): reconcile entity-review tests with the artifact guard"
```

---

# Part C — `science-review` skill (per-kind rubric + artifact-required checklist)

This is the agentic layer that performs the scrutiny a review records. It consumes the attention ranking (now including `open_question_debt` and the deterministic `graph attention-rank` command from A4) and, per target, applies a type-specific rubric, then records the outcome through the guarded `entity review` command.

**Durability constraint (finding 3):** `codex-skills/` is **generated**. `generate_codex_skills` (`science/src/science_tool/codex_skills.py:33`) builds each `<skill>/SKILL.md` and `INDEX.md` from `commands/*.md` (plus the hard-coded `COMPANION_SKILLS`) and injects the command preamble from `references/command-preamble.md`. Hand-editing the generated files is non-durable — a later regeneration drops them. So the source of truth is a new `commands/review.md`; the skill and INDEX row are produced by running the generator.

**Files:**
- Create: `commands/review.md` (the durable source)
- Regenerate (do not hand-edit): `codex-skills/science-review/SKILL.md`, `codex-skills/INDEX.md`

### Task C1: Author the command source and regenerate

**Files:**
- Create: `commands/review.md`
- Run: `scripts/generate_codex_skills.py`

- [ ] **Step 1: Create the command source file**

Create `commands/review.md` with exactly this content. Do **not** embed the preamble — the generator injects `## Science Codex Command Preamble` from `references/command-preamble.md`, and rewrites companion-skill references:

```markdown
---
description: Scrutinize one or more epistemic entities (hypothesis, proposition, interpretation, report) for claim-vs-operationalization drift, leaky or overstated language, eroded falsifiability, and unincorporated open questions, then record an artifact-guarded review. Use when an entity looks settled but is heavily caveated or carries open-question debt, or on a periodic sweep of the attention ranking.
---

# Entity Review

Review load-bearing (epistemic) entities for drift between what they claim and what their
evidence and operationalization actually support. Targets failure mode A
(scope/operationalization drift) and the residue of B/C that static checks cannot
adjudicate. See `docs/plans/2026-06-04-epistemic-drift-detection-design.md` and
`science-meta:question:15-claim-operationalization-drift`.

Use `$ARGUMENTS` to scope the review to specific epistemic entities. If no scope is given,
pull the top of the attention ranking. If `$ARGUMENTS` names an operational entity such as
`dataset:*`, `paper:*`, `workflow:*`, `workflow-run:*`, `task:*`, `plan:*`, or
`pre-registration:*`, do not stamp it with `entity review`; follow it only as evidence or
manifest context for the epistemic claim under review.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
Load the `research-methodology` and `scientific-writing` skills.

## Selecting targets

If `$ARGUMENTS` names epistemic entities, review exactly those. Otherwise pull the
deterministic attention ranking (rows carry `open_question_debt` and reason codes):

```
science graph attention-rank --limit 15 --format json
```

Prefer the conjunction that names the blind spot — settled-looking but overdue and
indebted. Rank by, in order: `open_question_debt` desc, then `needs-review`/`stale`
freshness, then `status: supported` / high-confidence with an old `last_reviewed`.
Independent entities may be reviewed in parallel (one sub-agent per entity, mirroring
`big-picture`'s per-hypothesis fan-out). Do not parallelize entities that cite each other.

## Per-kind rubric

For every epistemic kind, check: does the stated scope exceed what is actually
operationalized/measured? Is the language leaky or overstated relative to the evidence?
Are there open questions (debt statuses: `active` / `partially-answered` / `deferred`)
related to this entity, or sharing a theme, that have never been folded into its claims?

- **hypothesis:** scope vs operationalization (enumerate what the pipeline/code actually
  measures and compare to the prose claim); falsifiability still crisp and testable;
  confidence rating justified by *current* evidence, not legacy; high-risk or edge cases
  the framing silently excludes.
- **proposition:** claim layer and identification strategy still accurate; evidence stance
  (supports/disputes balance) current; not over-generalized beyond its tested contexts.
- **interpretation:** conclusions still match the cited evidence and effect sizes; no
  drift between the headline reading and the underlying numbers.
- **report:** headline claims still match the entities they summarize; no inherited
  overstatement from a since-narrowed source entity.

**Decisions are out of scope for now.** `decision` is not a registered entity kind;
decisions live as `##` sections in `core/decisions.md` without their own `review_state`.
Do not run `entity review` on a decision. If a review surfaces a stale or code-contradicted
decision, record it as a finding/task and flag it for the future decision-review path.

**Operational entities are context, not review targets.** `dataset`, `paper`, `workflow`,
`workflow-run`, `research-package`, `task`, `plan`, and `pre-registration` are operational
in the core registry. Inspect them for manifests, evidence, provenance, and contradiction
checks, but record the review on the epistemic entity whose claim depends on them.

## Recording the review (artifact-required)

A review MUST emit a concrete artifact before the timestamp is set — never a bare bump:

1. **Finding / overstatement:** edit the entity to qualify or narrow the claim, or open a
   task (`science tasks add ...`) capturing the data-dependent follow-up.
2. **Prose-vs-code contradiction (mode B):** correct the prose and cite the authoritative
   manifest (e.g. a code constant such as `constants.py::EVENTS`).
3. **Unincorporated question (mode C):** fold it into the claim, or explicitly link/defer
   it with a reason.
4. **No change warranted:** record the *reasoning* for why no change is needed.

Then stamp the review with the artifact as the note:

```
science entity review <kind>:<id> --note "<finding | diff summary | task id | reasoned no-change>"
```

The command refuses an empty `--note` — that guard is what keeps this review honest.
```

- [ ] **Step 2: Regenerate the Codex skills**

Run: `cd ~/d/science && uv run --project science python scripts/generate_codex_skills.py`
Expected: prints `Generated Codex skills in <repo>/codex-skills`.

- [ ] **Step 3: Verify the generated skill and index row exist**

Run: `cd ~/d/science && test -f codex-skills/science-review/SKILL.md && grep -q "science-review/SKILL.md" codex-skills/INDEX.md && grep -q "Science Codex Command Preamble" codex-skills/science-review/SKILL.md && echo "OK: science-review generated, indexed, preamble injected"`
Expected: prints `OK: science-review generated, indexed, preamble injected`.

- [ ] **Step 4: Review the regeneration diff before committing**

Run: `cd ~/d/science && git status --short codex-skills/`
Expected: a new `codex-skills/science-review/` directory and a modified `codex-skills/INDEX.md`. If the generator also rewrote *unrelated* skills (because the checked-in tree was stale), inspect with `git diff codex-skills/` and confirm those changes are benign regeneration noise before staging — do not hand-revert generated files.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add commands/review.md codex-skills/
git commit -m "feat(skills): add review command + regenerate science-review skill"
```

---

## Final verification

- [ ] **Run the full affected test surface**

Run: `cd ~/d/science/science && uv run pytest tests/test_attention_sampling.py tests/test_entity_review_cli.py tests/test_wander_sampling.py tests/test_wander_context.py tests/test_curate_cli.py tests/test_status.py tests/test_codex_skills.py -v`
Expected: PASS.

- [ ] **Confirm the regression fixture would surface H2 (manual, when the multiple-myeloma graph is available)**

From the `multiple-myeloma` project root (with a materialized `knowledge/graph.trig`):

Run: `science graph attention-rank --kind hypothesis --format json` and confirm `hypothesis:h2-cytogenetic-distinct-entities` carries `open_question_debt >= 1` (it has `question:01` and `question:38` related with `projectStatus active`) and an `open_question_debt` reason.

Note: `question:06-1q-gain-vs-amplification-tier` is fully unlinked (no `skos:related`, no theme), so it remains invisible to the term **by design** — that is the residual case the design's "complementary authoring fix" (type/relate scoping questions) and a future age-weighting milestone address. Surface this explicitly when reporting M1 coverage; do not present the term as catching every scoping question.

---

## Out of scope for M1 (tracked, not silently dropped)

- **Question-age / "unincorporated" weighting** — needs `created`/`updated` emitted as graph triples for question nodes; not currently present. Deferred.
- **Operationalization-coverage check** (`operationalized_by:` / `claims_scope:`, mechanism 1) — that is M2.
- **Decision review** — `decision` is not a registered entity kind; needs either a `decision` kind + `core/decisions.md` migration or a section-level ledger. M3 / open question in the design doc.
- **Operational entity review-state** — `dataset`, `paper`, workflow/run, task, plan, and pre-registration entities are operational context, not M1 `entity review` targets. Use dataset/pipeline health checks for their own recency/quality state.
- **Typed scoping predicate into the `bears_on` deriver** — open design question (propagation side effects); not M1.
- **Fully-unlinked scoping questions** — uncatchable without minimal authoring; the debt term raises the payoff of even a weak `related:` link but cannot manufacture connectivity.

## Self-review checklist (completed by plan author)

- **Spec coverage:** mechanism 2 (debt term, related+theme, not bears_on) → Part A1–A3; deterministic review-queue surface → Part A4; mechanism 3 review-state hardening → Part B; mechanism 3 agentic skill + per-kind rubric → Part C. Age-weighting, decision-review, and operational-entity review-state are explicitly deferred with rationale.
- **Review findings reconciled:** (1) no `query attention` command → A4 adds deterministic `graph attention-rank`, skill points at it; (2) guard ordering → moved into `review_entity` behind `require_artifact`, after resolution + kind gate, with a regression test (`test_entity_review_unknown_id_errors_even_without_note`); (3) non-durable INDEX edit → Part C authors `commands/review.md` and regenerates; (4) self-counting via theme → `question_uris.discard(entity_uri)` + a self-exclusion assertion.
- **Placeholder scan:** every code/test step contains complete code; no placeholder or vague edge-case instructions remain.
- **Type consistency:** `_open_question_debt`, `_related_neighbors`, `_entity_kind_of`, `_open_question_debt_reason`, `_rows_with_belief`, `query_attention_ranked`, `OPEN_QUESTION_DEBT_WEIGHT`, `DEBT_QUESTION_STATUSES`, `require_artifact`, and the `open_question_debt` component/row key are named identically across Parts A1–A4, B, and the tests.
```

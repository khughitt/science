# Dataset Sub-Cohort Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design:** `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md` (read first; decisions are locked there).

**Goal:** Make the existing `parent_dataset` field a first-class **sub-cohort-of** lineage relation and teach B2 dataset-independence to honor it, so a child-on-parent evidence-line pair (e.g. UKB-PPP ⊂ UK Biobank) stops double-counting in belief — without inferring biological overlap (lineage is *declared*, not computed).

**Architecture:** Three thin additions to existing layers, no new field:
1. a validate check enforcing `parent_dataset` referential integrity + acyclicity;
2. a materialization step emitting a `sci:subCohortOf` edge into the knowledge graph from `parent_dataset`;
3. lineage-aware grouping in `graph/dataset_independence.py` (group by lineage root; ancestor⊂descendant pair ⇒ commitment, co-descendant/sibling pair ⇒ candidate `lineage-sibling`, unrelated ⇒ unchanged).

Belief/aggregation is **not** touched: lineage commitments reuse the existing `DatasetIndependenceCommitment` record type and flow through the current collection/aggregation path unchanged.

**Tech Stack:** rdflib `Graph`/`Dataset`, dataclasses, pytest; existing `science_tool.graph.dataset_independence`, `science_tool.graph.materialize`, `science_tool.graph.sources`, `science_tool.validate` check framework.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/validate/checks/dataset_lineage.py` | **New.** Pure `evaluate_dataset_lineage(datasets)` over raw frontmatter + `@Check` wrapper: `parent_dataset` resolves, acyclic, parent-not-a-`member_of`-member; optional `parent_dataset ↔ siblings` symmetry promotion. |
| `science/src/science_tool/validate/checks/__init__.py` | Register `"dataset_lineage"` in `CANONICAL_CHECK_MODULES`. |
| `science/src/science_tool/graph/sources.py` | Surface each dataset entity's `parent_dataset` to the materializer (collect into a `dataset_parents` map alongside `dataset_datapackages`). |
| `science/src/science_tool/graph/materialize.py` | Emit `<child> sci:subCohortOf <parent>` into the knowledge graph from the `dataset_parents` map, before B2 derivation runs (line ~130, near `_add_dataset_usage_edges`). |
| `science/src/science_tool/graph/dataset_independence.py` | Read `sci:subCohortOf` into a lineage map; group by lineage root; extend `_is_committable_pair` (ancestor/descendant) and `_candidate_reason` (`lineage-sibling`). |
| `science/src/science_tool/graph/io.py` | (No change — `sci:` predicates are accessed dynamically via `SCI_NS.subCohortOf`; the prefix is already registered.) |
| `science/model/src/science_model/tests/test_dataset_models.py` | Regression: `origin: external` + `access` + `parent_dataset` validates (no invariant #7/#8 regression). |
| `science/tests/validate/test_checks_dataset_lineage.py` | **New.** Lineage validation tests. |
| `science/tests/test_dataset_independence.py` | Lineage-aware commitment/candidate derivation tests + identical-dataset regression. |
| `science/tests/test_dataset_usage_materialize.py` | Materialization integration test: `parent_dataset` → `sci:subCohortOf` triple; UKB end-to-end. |
| `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md` | Flip Status after code lands. |

## Current-Code Alignment Notes

- Run from repo root (`~/d/science`) with the AGENTS/RTK convention: `rtk uv run --frozen --project science <cmd>`. Test paths keep the `science/tests/...` prefix.
- B2 usage facts live in the **provenance** graph (`SCI_NS.hasDatasetUsage`/`DatasetUsage`/`dataset`/`usageRole`/`usageOverlap`); structural entity edges live in the **knowledge** graph. Put `sci:subCohortOf` in **knowledge** — `derive_dataset_independence_records(knowledge, provenance)` already receives both.
- B2 record emission must stay **blank-node-free** (canonical serialization rejects blank nodes). The lineage edge is `dataset→dataset` (two named URIs) so this is automatic.
- `_line_graph()` and `_add_usage(provenance, consumer, dataset, role, overlap, suffix)` already exist in `test_dataset_independence.py`; reuse them and add a small `_add_sub_cohort(knowledge, child, parent)` helper.
- `dataset_frontmatters(ctx)` (`validate/_helpers.py`) returns raw frontmatter dicts each carrying `_path`; model the new check on `validate/checks/dataset_taxonomy.py`.
- The collapse decision (design §5.2) in one line: **commitment ⇔ both lines direct + dependence + overlap==full AND datasets are identical-or-ancestor/descendant**; **co-descendant (sibling) pair ⇒ candidate `lineage-sibling`**; **different lineage root ⇒ no pair (independent)**.

---

## Task 1: Lineage Validation Check

**Files:**
- Create: `science/src/science_tool/validate/checks/dataset_lineage.py`
- Create: `science/tests/validate/test_checks_dataset_lineage.py`
- Edit: `science/src/science_tool/validate/checks/__init__.py`

- [ ] **Step 1: Write failing validation tests**

Create `science/tests/validate/test_checks_dataset_lineage.py` with pure-core cases over raw frontmatter dicts (each dict carries `_path`, `id`, optional `parent_dataset`, `siblings`, `derivation`):

```python
from science_tool.validate.checks.dataset_lineage import evaluate_dataset_lineage

def _ds(id_, **kw):
    return {"_path": f"doc/datasets/{id_.split(':')[1]}.md", "type": "dataset", "id": id_, **kw}

def test_parent_dataset_must_resolve():
    results = list(evaluate_dataset_lineage([_ds("dataset:ukb-ppp", parent_dataset="dataset:nope")]))
    assert any(r.severity.name == "ERROR" and "parent_dataset" in r.message for r in results)

def test_cycle_is_error():
    dss = [_ds("dataset:a", parent_dataset="dataset:b"), _ds("dataset:b", parent_dataset="dataset:a")]
    results = list(evaluate_dataset_lineage(dss))
    assert any(r.severity.name == "ERROR" and "cycle" in r.message.lower() for r in results)

def test_parent_may_not_be_member_of_collection_member():
    member = _ds("dataset:row", derivation={"kind": "member_of", "parent_dataset": "dataset:coll", "member_key": "k"})
    child = _ds("dataset:c", parent_dataset="dataset:row")
    results = list(evaluate_dataset_lineage([member, child]))
    assert any(r.severity.name == "ERROR" and "member_of" in r.message for r in results)

def test_well_formed_chain_is_clean():
    dss = [_ds("dataset:uk-biobank", siblings=["dataset:ukb-ppp"]),
           _ds("dataset:ukb-ppp", parent_dataset="dataset:uk-biobank")]
    assert list(evaluate_dataset_lineage(dss)) == []
```

- [ ] **Step 2: Run tests to verify they fail** — `rtk uv run --frozen --project science pytest science/tests/validate/test_checks_dataset_lineage.py` (import error / no module).

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/dataset_lineage.py` modeled on `dataset_taxonomy.py`:

```python
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

def evaluate_dataset_lineage(datasets):  # -> Iterator[Result]
    by_id = {d.get("id"): d for d in datasets if isinstance(d.get("id"), str)}
    member_of_ids = {
        d["id"] for d in datasets
        if isinstance(d.get("derivation"), dict) and d["derivation"].get("kind") == "member_of"
    }
    for d in datasets:
        parent = d.get("parent_dataset")
        if not parent:
            continue
        path = d.get("_path")
        if not isinstance(parent, str) or not parent.startswith("dataset:"):
            yield _err(path, f"{d['id']}: parent_dataset must be a 'dataset:' reference", "dataset.lineage.ref")
            continue
        if parent not in by_id:
            yield _err(path, f"{d['id']}: parent_dataset {parent!r} does not resolve to a dataset entity", "dataset.lineage.unresolved")
            continue
        if parent in member_of_ids:
            yield _err(path, f"{d['id']}: parent_dataset {parent!r} is a member_of collection member, not a sub-cohort parent", "dataset.lineage.member-parent")
    # cycle detection over the parent_dataset chain
    for start in by_id:
        seen, cur = set(), start
        while cur in by_id and by_id[cur].get("parent_dataset"):
            cur = by_id[cur]["parent_dataset"]
            if cur in seen or cur == start:
                yield _err(by_id[start].get("_path"), f"{start}: parent_dataset chain forms a cycle", "dataset.lineage.cycle")
                break
            seen.add(cur)
    # (optional, recommended) symmetry: parent.siblings must list child when present
    # — promote the health.py:1540 WARN here if desired; keep as WARN.

def _err(path, message, rule):
    from pathlib import Path
    return Result(Severity.ERROR, Path(path) if path else None, None, message, rule, None)

@Check(section="dataset_lineage", order=0)
def check(ctx: ValidateContext):
    yield from evaluate_dataset_lineage(dataset_frontmatters(ctx))
```

Register in `science/src/science_tool/validate/checks/__init__.py` by adding `"dataset_lineage",` to `CANONICAL_CHECK_MODULES` (after `"dataset_metadata"`).

- [ ] **Step 4: Run tests to verify they pass** — same pytest path, plus `rtk uv run --frozen --project science science validate` on a scratch project to confirm registration.

- [ ] **Step 5: Commit** — `feat(validate): dataset_lineage check — parent_dataset integrity + acyclicity`.

---

## Task 2: Model Regression Guard (origin-orthogonality)

**Files:**
- Edit: `science/model/src/science_model/tests/test_dataset_models.py`

- [ ] **Step 1: Add a passing-guard test** proving the design's origin-orthogonality claim holds (and will keep holding):

```python
def test_external_dataset_may_carry_parent_dataset():
    ds = DatasetEntity(
        id="dataset:ukb-ppp", type="dataset", kind="dataset",
        origin="external",
        access=AccessBlock(level="controlled", verified=True),
        parent_dataset="dataset:uk-biobank",
        datapackage="x", tier="use-now",
    )
    assert ds.parent_dataset == "dataset:uk-biobank"
    assert ds.derivation is None  # parent_dataset is NOT a derivation block
```

(Adjust constructor kwargs to the test module's existing factory/helpers.)

- [ ] **Step 2: Run** — `rtk uv run --frozen --project science pytest science/model/src/science_model/tests/test_dataset_models.py`. This should **pass immediately** (origin-orthogonality already holds); it is a guard against future regression, not a red test. If it fails, the schema drifted — stop and reconcile with the design before continuing.

- [ ] **Step 3: Commit** — `test(model): guard external dataset may carry parent_dataset`.

---

## Task 3: Materialize `sci:subCohortOf`

**Files:**
- Edit: `science/src/science_tool/graph/sources.py` (collect `dataset_parents`)
- Edit: `science/src/science_tool/graph/materialize.py` (emit the edge)
- Test: `science/tests/test_dataset_usage_materialize.py`

- [ ] **Step 1: Write a failing materialization test** using the existing `_write_project` / `_write_dataset` / `_load_trig` helpers: write `dataset:uk-biobank` and `dataset:ukb-ppp` (with `parent_dataset: dataset:uk-biobank`), build the graph, and assert the knowledge graph contains `(ukb-ppp_uri, SCI_NS.subCohortOf, uk-biobank_uri)`.

- [ ] **Step 2: Run to verify it fails** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_usage_materialize.py -k sub_cohort`.

- [ ] **Step 3: Collect `parent_dataset` in `sources.py`.** Where dataset entities are scanned and `dataset_datapackages[entity.canonical_id] = ref.path` is set (~line 481), also populate `dataset_parents[entity.canonical_id] = entity.parent_dataset` when non-empty. Thread `dataset_parents` through `ProjectSources` alongside `dataset_datapackages` (~line 682).

- [ ] **Step 4: Emit the edge in `materialize.py`.** Near line 130 (just before B2 derivation at ~169, after `_add_dataset_usage_edges`), add:

```python
def _add_sub_cohort_edges(sources, *, resolver, knowledge):
    for child_id, parent_ref in sources.dataset_parents.items():
        if not parent_ref:
            continue
        child = PROJECT_NS[_dataset_local(child_id)]
        parent = PROJECT_NS[_dataset_local(_resolve_dataset_usage_ref(parent_ref, resolver))]
        knowledge.add((child, SCI_NS.subCohortOf, parent))
```

Use the same dataset-URI minting helper that `_add_dataset_usage_edges` / `dataset_usage.py` uses for `SCI_NS.dataset` objects, so child/parent URIs match the URIs B2 sees on usage facts (critical — they must be identical for grouping to line up). Reuse `_resolve_dataset_usage_ref` for alias resolution. Integrity (resolvability/acyclicity) is Task 1's job; materialization emits the edge as-authored and stays blank-node-free.

- [ ] **Step 5: Run to verify it passes**, then run the full materialize suite for regressions: `rtk uv run --frozen --project science pytest science/tests/test_dataset_usage_materialize.py`.

- [ ] **Step 6: Commit** — `feat(graph): materialize sci:subCohortOf from dataset.parent_dataset`.

---

## Task 4: Lineage-Aware Collapse in B2

**Files:**
- Edit: `science/src/science_tool/graph/dataset_independence.py`
- Test: `science/tests/test_dataset_independence.py`

- [ ] **Step 1: Write failing derivation tests.** Add a helper and cases (reusing `_line_graph` / `_add_usage`):

```python
def _add_sub_cohort(knowledge, child, parent):
    knowledge.add((child, SCI_NS.subCohortOf, parent))

def test_child_parent_full_overlap_pair_is_commitment():
    knowledge, provenance, target, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]
    _add_sub_cohort(knowledge, ppp, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [r.kind for r in records] == ["commitment"]
    assert records[0].members == frozenset({line_a, line_b})
    assert records[0].datasets == frozenset({ppp, ukb})

def test_sibling_full_overlap_pair_is_candidate_lineage_sibling():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]; nmr = PROJECT_NS["dataset/ukb-nmr"]
    _add_sub_cohort(knowledge, ppp, ukb); _add_sub_cohort(knowledge, nmr, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, nmr, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [(r.kind, r.reason) for r in records] == [("candidate", "lineage-sibling")]

def test_child_parent_partial_is_candidate_partial_overlap():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]
    _add_sub_cohort(knowledge, ppp, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "partial", "a")
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [(r.kind, r.reason) for r in records] == [("candidate", "partial-overlap")]

def test_unrelated_datasets_stay_independent():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ppp = PROJECT_NS["dataset/ukb-ppp"]; fin = PROJECT_NS["dataset/finngen"]
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, fin, "analyzed", "full", "b")
    assert derive_dataset_independence_records(knowledge, provenance) == []

def test_grandparent_chain_full_overlap_is_commitment():
    knowledge, provenance, target, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]; sub = PROJECT_NS["dataset/ppp-sub"]
    _add_sub_cohort(knowledge, ppp, ukb); _add_sub_cohort(knowledge, sub, ppp)
    _add_usage(provenance, line_a, sub, "analyzed", "full", "a")   # grandchild
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")   # grandparent
    assert [r.kind for r in derive_dataset_independence_records(knowledge, provenance)] == ["commitment"]
```

Plus a **regression** assertion that the existing identical-dataset case (`test_full_overlap_direct_shared_dataset_derives_one_commitment_component`) still yields exactly one commitment with `independence_group == f"{DERIVED_GROUP_PREFIX}gtex-v8"`.

- [ ] **Step 2: Run to verify the new tests fail** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_independence.py`.

- [ ] **Step 3: Implement lineage awareness.**

  a. **Read the lineage map** (near the other graph readers, ~line 188): from `knowledge`, build `parent_of: dict[URIRef, URIRef]` from all `(c, SCI_NS.subCohortOf, p)` triples. Derive helpers:
     - `_lineage_root(d)` — walk `parent_of` to the top (the materializer/validate guarantee acyclicity; guard with a visited-set anyway);
     - `_relation(x, y)` → `"same" | "ancestor" | "descendant" | "codescendant" | "unrelated"` (ancestor/descendant by walking `parent_of`; co-descendant = same root but neither is an ancestor of the other; unrelated = different root).
     Thread this lineage object into `_commitment_components` / `_candidate_components` (or compute once in `derive_dataset_independence_records` and pass down).

  b. **Group by lineage root, not raw dataset.** In `_candidate_edges` (line ~263) and `_components_from_ancestors` (line ~315), replace the grouping key `ancestor.dataset` with `_lineage_root(ancestor.dataset)`. Identical-dataset lines still co-group (their root is themselves or a shared ancestor); cross-family lines never co-group (distinct roots) → preserves the unrelated-stays-independent behavior with no extra code.

  c. **Gate commitment on relation.** Extend `_is_committable_pair(left, right, lineage)` (line ~283):
     ```python
     return (
         left.path == right.path == "direct"
         and left.usage.interpretation == right.usage.interpretation == "dependence"
         and left.usage.overlap == right.usage.overlap == "full"
         and lineage.relation(left.dataset, right.dataset) in {"same", "ancestor", "descendant"}
     )
     ```
     Co-descendant (sibling) full/full pairs now fall through to candidate.

  d. **Add the sibling reason.** In `_candidate_reason(left, right, lineage)` (line ~291), after the existing `citation` / `validation` branches and before the overlap branches, add:
     ```python
     if lineage.relation(left.dataset, right.dataset) == "codescendant":
         return "lineage-sibling"
     ```
     Ancestor/descendant pairs that are not committable (e.g. one is `partial`) keep falling through to the existing `partial-overlap` / `unknown-overlap` reasons — correct, since a non-full subset usage is a genuine partial overlap.

  e. **Justification / group key.** `_components_from_ancestors` already records `member_datasets` (now spanning child+parent) and `_group_key(member_datasets)`. Confirm `_group_key` (line ~405) is stable for a multi-dataset family set; if its single-dataset shortcut picks an arbitrary member, prefer keying on the lineage root for determinism. Add/extend a test asserting the committed record's `datasets` includes both child and parent.

- [ ] **Step 4: Run to verify all pass**, including the unchanged-regression assertions — `rtk uv run --frozen --project science pytest science/tests/test_dataset_independence.py`.

- [ ] **Step 5: Commit** — `feat(graph): lineage-aware B2 collapse (sub-cohort commitment + sibling candidate)`.

---

## Task 5: Belief Flow-Through (verification, no formula change)

**Files:**
- Test: `science/tests/test_belief_collect.py` (and `test_belief_aggregate.py` if a numeric assertion is added)

- [ ] **Step 1: Add a collection test** proving a lineage **commitment** record is merged into the same `EvidenceUnit` collapse path as an identical-dataset commitment (i.e. two lines on child+parent collapse to one independence group in belief), and that a lineage **candidate** does **not** collapse. Reuse existing belief-collect fixtures; assert the committed group membership, not a hand-computed score.

- [ ] **Step 2: Run** — `rtk uv run --frozen --project science pytest science/tests/test_belief_collect.py science/tests/test_belief_aggregate.py`.

- [ ] **Step 3: Confirm `CONFIG_VERSION` is unchanged.** Lineage changes *which inputs exist*, not the aggregation config/formula, so `belief_weights.CONFIG_VERSION` must **not** be bumped. If `test_belief_weights.py` fails, you changed the formula by accident — revert that part. Document this explicitly in the commit body.

- [ ] **Step 4: Commit** — `test(belief): lineage commitments collapse via existing path; no config bump`.

---

## Task 6: End-to-End UKB Example

**Files:**
- Test: `science/tests/test_dataset_usage_materialize.py` (or `test_dataset_evidence_flow_e2e.py`)

- [ ] **Step 1: Write an end-to-end test** reproducing design §6: a project with `dataset:uk-biobank`, `dataset:ukb-ppp` (`parent_dataset: dataset:uk-biobank`), two papers each `analyzed`/`full` on one of the two datasets, a target proposition, and two evidence lines (`cito:supports`) — one per paper. Build the graph end-to-end and assert exactly one `sci:DatasetIndependenceCommitment` over the two lines with `sci:sharedDataset` covering the family. (Use the materialize helpers; remember to create the proposition entity, else the `cito:supports` edges are not materialized — see alignment notes.)

- [ ] **Step 2: Run** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_usage_materialize.py -k ukb`.

- [ ] **Step 3: Commit** — `test(graph): end-to-end UKB/UKB-PPP sub-cohort commitment`.

---

## Task 7: Documentation Status And Full Verification

- [ ] **Step 1: Flip design status.** In `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md`, change Status to "implemented; see `…-plan.md`". Resolve the two design open-calls in the doc with what was actually done (symmetry-promotion: yes/no; predicate `sci:subCohortOf`: confirmed).

- [ ] **Step 2: Run the full affected suite** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_independence.py science/tests/test_dataset_usage_materialize.py science/tests/validate/test_checks_dataset_lineage.py science/tests/test_belief_collect.py science/model/src/science_model/tests/test_dataset_models.py`.

- [ ] **Step 3: Run lint + whitespace + full validate** per repo convention (ruff / whitespace check / `science validate` on a fixture project).

- [ ] **Step 4: Commit** — `docs(datasets): mark sub-cohort lineage implemented`.

---

## Acceptance Criteria (recap from design §8)

- `parent_dataset` referential-integrity ERROR; cycle ERROR; `member_of`-member-as-parent ERROR.
- `origin: external` + `access` + `parent_dataset` validates (no invariant #7/#8 regression).
- `parent_dataset` materializes to `sci:subCohortOf`; URIs match usage-fact dataset URIs.
- Ancestor–descendant full/full pair ⇒ **commitment**; co-descendant pair ⇒ **candidate `lineage-sibling`**; non-full subset pair ⇒ existing partial/unknown candidate; unrelated ⇒ independent.
- Chain (sub-cohort of a sub-cohort) commitment is transitive.
- Identical-dataset collapse unchanged (regression green); `CONFIG_VERSION` unchanged.
- End-to-end UKB/UKB-PPP example yields one commitment.

## Downstream Note (health-meta)

Once this ships, the manual UKB/UKB-PPP reconciliation in `~/d/health/meta` (commit on `main`, 2026-06-13) becomes mechanically enforced: re-pointing the Olink papers to `dataset:ukb-ppp` plus a single `parent_dataset: dataset:uk-biobank` on the ukb-ppp entity will let B2 derive the non-independence automatically. No data migration is required there beyond adding that one `parent_dataset` line.

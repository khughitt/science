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
| `science/src/science_tool/graph/sources.py` | Surface each dataset entity's `parent_dataset` to the materializer (collect into a `dataset_parents` map from the **finalized `entities` list**, not the datapackage-defer branch — see Task 3). |
| `science/src/science_tool/graph/materialize.py` | Emit `<child> sci:subCohortOf <parent>` into the knowledge graph from the `dataset_parents` map, before B2 derivation runs (line ~130, near `_add_dataset_usage_edges`). |
| `science/src/science_tool/graph/dataset_independence.py` | Read `sci:subCohortOf` into a lineage map; group by lineage root; gate the **commitment edge builder** and `_is_committable_pair` with one shared lineage-committable predicate; add `lineage-sibling` to `_candidate_reason`. |
| `science/src/science_tool/graph/io.py` | (No change — `sci:` predicates are accessed dynamically via `SCI_NS.subCohortOf`; the prefix is already registered.) |
| `science/model/tests/test_dataset_models.py` | Regression: `origin: external` + `access` + `parent_dataset` validates (no invariant #7/#8 regression). |
| `science/tests/validate/test_checks_dataset_lineage.py` | **New.** Lineage validation tests. |
| `science/tests/test_dataset_independence.py` | Lineage-aware commitment/candidate derivation tests + identical-dataset regression. |
| `science/tests/test_dataset_usage_materialize.py` | Materialization integration test: `parent_dataset` → `sci:subCohortOf` triple; UKB end-to-end. |
| `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md` | Flip Status after code lands. |

## Current-Code Alignment Notes

- Run from repo root (`~/d/science`) with the AGENTS/RTK convention: `rtk uv run --frozen --project science <cmd>`. Test paths keep the `science/tests/...` prefix.
- B2 usage facts live in the **provenance** graph (`SCI_NS.hasDatasetUsage`/`DatasetUsage`/`dataset`/`usageRole`/`usageOverlap`); structural entity edges live in the **knowledge** graph. Put `sci:subCohortOf` in **knowledge** — `derive_dataset_independence_records(knowledge, provenance)` already receives both.
- B2 record emission must stay **blank-node-free** (canonical serialization rejects blank nodes). The lineage edge is `dataset→dataset` (two named URIs) so this is automatic.
- `_line_graph()` and `_add_usage(provenance, consumer, dataset, role, overlap, suffix)` already exist in `test_dataset_independence.py`; reuse them and add a small `_add_sub_cohort(knowledge, child, parent)` helper.
- `dataset_frontmatters(ctx)` (`validate/_helpers.py`) returns raw frontmatter dicts each carrying `_path`; model the new check on `validate/checks/dataset_taxonomy.py`. **Caveat:** that helper scans only local datapackages + `doc/datasets/` — it does **not** see commons-hosted datasets. A valid `parent_dataset` may live in the commons, so resolution must be commons-aware (Task 1 Step 3) using the established pattern in `validate/checks/reference_collections.py` (`resolve_commons_root` / `CommonsEntityAdapter`).
- **The commitment path does NOT call `_is_committable_pair`.** `_commitment_components` pre-filters `direct_full` (direct + dependence + overlap==full) and hands them to `_components_from_ancestors`, which builds edges by *consecutive-pair chaining within a dataset group* (`dataset_independence.py:309-325`). The candidate path (`_candidate_edges`) is the only caller of `_is_committable_pair`. So lineage-gating must be applied at **both** sites via one shared predicate (Task 4) — gating only `_is_committable_pair` would let full/full sibling lines chain into a false commitment.
- Dataset URIs are minted by `project_entity_uri(canonical_id)` in `dataset_usage.py` (`dataset:ukb-ppp` → `PROJECT_NS["dataset/ukb-ppp"]`); reuse it for the lineage edge so URIs match the usage-fact `SCI_NS.dataset` objects exactly.
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

def test_parent_dataset_unresolved_in_project_and_commons_is_error():
    # commons_cache pins the resolver: False == commons is available but lacks the id.
    results = list(evaluate_dataset_lineage(
        [_ds("dataset:ukb-ppp", parent_dataset="dataset:nope")],
        commons_cache={"dataset:nope": False}))
    assert any(r.severity.name == "ERROR" and "does not resolve" in r.message for r in results)

def test_parent_dataset_nonlocal_with_unavailable_commons_is_info_not_error():
    # None == commons root not configured/available -> INFO, never a false ERROR.
    results = list(evaluate_dataset_lineage(
        [_ds("dataset:ukb-ppp", parent_dataset="dataset:commons-parent")],
        commons_cache={"dataset:commons-parent": None}))
    assert [r.severity.name for r in results] == ["INFO"]

def test_parent_dataset_resolved_in_commons_is_clean():
    results = list(evaluate_dataset_lineage(
        [_ds("dataset:ukb-ppp", parent_dataset="dataset:commons-parent")],
        commons_cache={"dataset:commons-parent": True}))
    assert results == []

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
from pathlib import Path

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

def evaluate_dataset_lineage(datasets, *, commons_cache=None):  # -> Iterator[Result]
    if commons_cache is None:
        commons_cache = {}
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
        if parent in member_of_ids:
            yield _err(path, f"{d['id']}: parent_dataset {parent!r} is a member_of collection member, not a sub-cohort parent", "dataset.lineage.member-parent")
        if parent in by_id:
            continue  # resolved locally
        # Not local — resolve against the commons, mirroring reference_collections._commons_has_dataset.
        present = _commons_has_dataset(parent, commons_cache)  # True | False | None
        if present is False:
            yield _err(path, f"{d['id']}: parent_dataset {parent!r} does not resolve to a dataset entity (not in project or commons)", "dataset.lineage.unresolved")
        elif present is None:
            yield _result(Severity.INFO, path,
                          f"{d['id']}: parent_dataset {parent!r} is non-local and the commons is unavailable; cannot verify",
                          "dataset.lineage.commons-unavailable")
        # present is True -> resolved in commons, no defect
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

def _result(severity, path, message, rule):
    return Result(severity, Path(path) if path else None, None, message, rule, None)

def _err(path, message, rule):
    return _result(Severity.ERROR, path, message, rule)

@Check(section="dataset_lineage", order=0)
def check(ctx: ValidateContext):
    yield from evaluate_dataset_lineage(dataset_frontmatters(ctx))
```

Reuse the commons resolver from `reference_collections.py` rather than re-implementing it: import (or lift to a shared `_helpers`) the `_commons_has_dataset(parent_id, cache)` pattern — `resolve_commons_root()` → `CommonsEntityAdapter(root).load(parent_id)` → `True` if present, `False` if the commons is configured but lacks the id, `None` (caught `CommonsError`/no root) when it cannot be verified. The `None` → INFO `commons-unavailable` rule (never a false ERROR) matches how `reference-collection.commons-unavailable` already behaves, so lineage and reference-collection checks stay consistent.

Register in `science/src/science_tool/validate/checks/__init__.py` by adding `"dataset_lineage",` to `CANONICAL_CHECK_MODULES` (after `"dataset_metadata"`).

- [ ] **Step 4: Run tests to verify they pass** — same pytest path, plus `rtk uv run --frozen --project science science validate` on a scratch project to confirm registration.

- [ ] **Step 5: Commit** — `feat(validate): dataset_lineage check — parent_dataset integrity + acyclicity`.

---

## Task 2: Model Regression Guard (origin-orthogonality)

**Files:**
- Edit: `science/model/tests/test_dataset_models.py`

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

- [ ] **Step 2: Run** — `rtk uv run --frozen --project science pytest science/model/tests/test_dataset_models.py`. This should **pass immediately** (origin-orthogonality already holds); it is a guard against future regression, not a red test. If it fails, the schema drifted — stop and reconcile with the design before continuing.

- [ ] **Step 3: Commit** — `test(model): guard external dataset may carry parent_dataset`.

---

## Task 3: Materialize `sci:subCohortOf`

**Files:**
- Edit: `science/src/science_tool/graph/sources.py` (collect `dataset_parents`)
- Edit: `science/src/science_tool/graph/materialize.py` (emit the edge)
- Test: `science/tests/test_dataset_usage_materialize.py`

- [ ] **Step 1: Write a failing materialization test** using the existing `_write_project` / `_write_dataset` / `_load_trig` helpers: write `dataset:uk-biobank` and `dataset:ukb-ppp` (with `parent_dataset: dataset:uk-biobank`), build the graph, and assert the knowledge graph contains `(ukb-ppp_uri, SCI_NS.subCohortOf, uk-biobank_uri)`.

- [ ] **Step 2: Run to verify it fails** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_usage_materialize.py -k sub_cohort`.

- [ ] **Step 3: Collect `parent_dataset` in `sources.py`.** Do **not** collect in the `dataset_datapackages[...] = ref.path` defer branch (~line 481) — that branch only runs for deferred `DatapackageAdapter` entities that `continue` without becoming owners; normal markdown/structured dataset entities win and are appended elsewhere (~lines 532 and 578). Do **not** collect after the line-581 `entities.sort(...)` either — when `include_commons` is set, the commons block (~lines 611-674) appends more entities and **re-sorts** before the function returns, so commons-hosted datasets would be missed. Build the map **immediately before `return ProjectSources(...)`** (~line 676), after the commons block, from the now-final `entities` list:

  ```python
  dataset_parents = {
      e.canonical_id: e.parent_dataset
      for e in entities
      if e.kind == "dataset" and getattr(e, "parent_dataset", "")
  }
  ```

  Thread `dataset_parents` through `ProjectSources` alongside `dataset_datapackages`. This single pass over the finalized list covers every dataset entity — local *and* commons — regardless of adapter.

- [ ] **Step 4: Emit the edge in `materialize.py`.** Near line 130 (just before B2 derivation at ~169, after `_add_dataset_usage_edges`), add:

```python
from science_tool.graph.dataset_usage import project_entity_uri

def _add_sub_cohort_edges(sources, *, resolver, knowledge):
    for child_id, parent_ref in sources.dataset_parents.items():
        if not parent_ref:
            continue
        child = project_entity_uri(child_id)
        parent = project_entity_uri(_resolve_dataset_usage_ref(parent_ref, resolver))
        knowledge.add((child, SCI_NS.subCohortOf, parent))
```

`project_entity_uri` (`dataset_usage.py:161`) is the exact helper that mints the `SCI_NS.dataset` objects on usage facts (`add_usage_record_to_graph`, `dataset_usage.py:200`), so child/parent URIs match the URIs B2 sees on usage facts — critical, since grouping joins on URI identity. (There is no `_dataset_local` helper; do not invent one.) Reuse `_resolve_dataset_usage_ref` for alias resolution. Integrity (resolvability/acyclicity) is Task 1's job; materialization emits the edge as-authored and stays blank-node-free.

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

  a. **Read the lineage map** (near the other graph readers, ~line 188): from `knowledge`, build `parent_of: dict[URIRef, URIRef]` from all `(c, SCI_NS.subCohortOf, p)` triples. Wrap it in a small `lineage` object with:
     - `root(d)` — walk `parent_of` to the top (validate/materialize guarantee acyclicity; guard with a visited-set anyway);
     - `relation(x, y)` → `"same" | "ancestor" | "descendant" | "codescendant" | "unrelated"` (ancestor/descendant by walking `parent_of`; co-descendant = same root but neither is an ancestor of the other; unrelated = different root);
     - `committable(x, y)` → `relation(x, y) in {"same", "ancestor", "descendant"}` — the **one shared predicate** both paths must use.
     Compute once in `derive_dataset_independence_records` and pass `lineage` down into `_commitment_components`/`_components_from_ancestors` **and** `_candidate_components`/`_candidate_edges`.

  b. **Group by lineage root, not raw dataset (a bucket only).** In `_candidate_edges` (line ~263) and `_components_from_ancestors` (line ~315), group ancestors by `lineage.root(ancestor.dataset)` instead of `ancestor.dataset`, so cross-dataset pairs within one family are enumerated and cross-family pairs (distinct roots) never are. **The root key is only a bucket — never derive a record's `datasets` from it** (see step f); doing so is the trap that would mislabel a committed record's `datasets` as the root.

  c. **Commitment edge builder — iterate ancestor PAIRS, gate by `committable`, carry both real datasets (the High fix).** `_components_from_ancestors` does **not** call `_is_committable_pair`; it chains consecutive *lines* within a `by_dataset` group (`zip(lines, lines[1:])`, ~line 324) and then derives `member_datasets` from each edge's third element (~line 331). Both assumptions break under root grouping. Rewrite the edge build to iterate **ancestor pairs** within each root bucket and carry the actual pair datasets in the edge:
     ```python
     edges: list[tuple[URIRef, URIRef, frozenset[URIRef]]] = []
     for _root, group in by_root.items():            # group: list[LineAncestor]
         for a, b in itertools.combinations(group, 2):
             if a.line != b.line and lineage.committable(a.dataset, b.dataset):
                 edges.append((a.line, b.line, frozenset({a.dataset, b.dataset})))
     ```
     `direct_full` already pre-filtered to direct + dependence + overlap==full, so only the relation gate is new. Iterating raw ancestors (not the deduped line set) is deliberate: a single line carrying several datasets in the family contributes one ancestor per dataset, so every committable cross-dataset pairing is seen. Effects: a **sibling-only** pair (ppp, nmr) with no parent line → no committable edge → no commitment (it surfaces as a candidate, step e). The **transitive-hub** case (lines on ppp, ukb, nmr) keeps its conservative single component: edges ppp–ukb and nmr–ukb are committable and `_connected_components` merges {ppp, ukb, nmr} through the ukb hub, while the un-committable ppp–nmr pair contributes no edge.

  d. **Gate `_is_committable_pair` with the SAME predicate (candidate path).** Extend `_is_committable_pair(left, right, lineage)` (line ~283) so the candidate path's "skip true commitments" exclusion stays consistent with step c:
     ```python
     return (
         left.path == right.path == "direct"
         and left.usage.interpretation == right.usage.interpretation == "dependence"
         and left.usage.overlap == right.usage.overlap == "full"
         and lineage.committable(left.dataset, right.dataset)
     )
     ```
     Co-descendant full/full pairs are now *not* committable, so they are no longer skipped from candidates and reach `_candidate_reason`.

  e. **Add the sibling reason.** In `_candidate_reason(left, right, lineage)` (line ~291), after the existing `citation` / `validation` branches and before the overlap branches, add:
     ```python
     if lineage.relation(left.dataset, right.dataset) == "codescendant":
         return "lineage-sibling"
     ```
     Ancestor/descendant pairs that are not committable (e.g. one is `partial`) keep falling through to the existing `partial-overlap` / `unknown-overlap` reasons — correct, since a non-full subset usage is a genuine partial overlap.

  f. **Record `datasets` from actual ancestor datasets, not the bucket key (BOTH paths).** This is the other half of the High fix — the grouping change (step b) makes the existing `datasets` derivations read the root instead of the real datasets.
     - **Commitment** (`_components_from_ancestors`, ~line 331): currently `member_datasets = frozenset(dataset for left, right, dataset in edges if ...)` reads each edge's third element. With the new edge shape it becomes a union of the per-pair frozensets:
       ```python
       member_datasets = frozenset(
           d for left, right, datasets in edges
           if left in members and right in members
           for d in datasets
       )
       ```
       `_connected_components` ignores the third element, so widening it `URIRef → frozenset[URIRef]` is safe — update that function's parameter type hint to `tuple[URIRef, URIRef, frozenset[URIRef]]` (or relax to `object`). The `usage_nodes` filter (`ancestor.dataset in member_datasets`, ~line 335) keeps working since `member_datasets` now holds the actual child+parent datasets.
     - **Candidate** (`_records_from_candidate_edges`, ~line 361): currently `datasets = frozenset(edge.dataset for edge in component_edges)`; under root grouping `edge.dataset` is the root, so read the actual endpoints instead:
       ```python
       datasets = frozenset(d for edge in component_edges for d in (edge.left.dataset, edge.right.dataset))
       ```
       (`CandidateEdge.left/.right` are `LineAncestor`s carrying `.dataset`; the `CandidateEdge.dataset` field is now vestigial for the record's `datasets` — leave it or drop it.)
     - `_group_key` (line ~405) then hashes the sorted multi-dataset set, so a family group is deterministic; the single-dataset shortcut still applies to the unchanged identical-dataset case.
     - **Tests:** assert a committed lineage record's `datasets == frozenset({child, parent})` and a `lineage-sibling` candidate's `datasets == frozenset({sibling_a, sibling_b})` — these directly catch the root-mislabeling regression.

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

- [ ] **Step 2: Run the full affected suite** — `rtk uv run --frozen --project science pytest science/tests/test_dataset_independence.py science/tests/test_dataset_usage_materialize.py science/tests/validate/test_checks_dataset_lineage.py science/tests/test_belief_collect.py science/model/tests/test_dataset_models.py`.

- [ ] **Step 3: Run lint + whitespace + full validate** per repo convention (ruff / whitespace check / `science validate` on a fixture project).

- [ ] **Step 4: Commit** — `docs(datasets): mark sub-cohort lineage implemented`.

---

## Acceptance Criteria (recap from design §8)

- `parent_dataset` referential-integrity ERROR; cycle ERROR; `member_of`-member-as-parent ERROR.
- `origin: external` + `access` + `parent_dataset` validates (no invariant #7/#8 regression).
- `parent_dataset` materializes to `sci:subCohortOf`; URIs match usage-fact dataset URIs.
- Ancestor–descendant full/full pair ⇒ **commitment**; co-descendant pair ⇒ **candidate `lineage-sibling`**; non-full subset pair ⇒ existing partial/unknown candidate; unrelated ⇒ independent.
- Committed/candidate records carry the **actual** member datasets (`{child, parent}` / `{sibling_a, sibling_b}`), never the lineage-root bucket key.
- Chain (sub-cohort of a sub-cohort) commitment is transitive.
- Identical-dataset collapse unchanged (regression green); `CONFIG_VERSION` unchanged.
- End-to-end UKB/UKB-PPP example yields one commitment.

## Downstream Note (health-meta)

Once this ships, the manual UKB/UKB-PPP reconciliation in `~/d/health/meta` (commit on `main`, 2026-06-13) becomes mechanically enforced: re-pointing the Olink papers to `dataset:ukb-ppp` plus a single `parent_dataset: dataset:uk-biobank` on the ukb-ppp entity will let B2 derive the non-independence automatically. No data migration is required there beyond adding that one `parent_dataset` line.

# Dataset Evidence Flow (Framework) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

> **⛔ HELD until `layout_version: 3` is confirmed in place.** Per the umbrella
> ([`2026-06-08-epistemic-data-model-design.md`](./2026-06-08-epistemic-data-model-design.md) §7) and
> the design ([`2026-06-08-dataset-evidence-flow-design.md`](./2026-06-08-dataset-evidence-flow-design.md)).
> Phase 0 is the gate. Tasks tagged **[v3-API]** must be *finalized against the confirmed v3 substrate
> API* (entity layout under `entities/<kind>/`, materialization/belief-eligibility contract).

> **Non-duplication.** The `belief_eligible` field on `EvidenceLineEntity`, its staging exclusion from
> belief materialization, and the *presence* rule "empirical line must have `dataset_usage` to be
> belief-eligible" are owned by the **`epistemic-edges` framework plan** (its Tasks 1c / 2c / 3b). This
> plan must **not** re-implement them; it consumes them and adds only the dataset-specific pieces.

**Goal:** Add the framework machinery that lets evidence-lines be grounded in datasets — `dataset`
entity layout, `dataset_usage` reference + dataset-entity integrity validation, task-key provenance
wiring, and a generated-projection drift gate — **without** building any new independence engine (A1/
A2/B1/B2 already exist) and **without** the MM30 resolution-table data or dataset generation (deferred).

**Architecture:** Thin wiring over already-merged machinery. (1) **Layout** — register the
`entities/datasets/` path policy so `DatasetEntity` files are first-class. (2) **Validation** — every
`DatasetUsage.ref` resolves to a registered dataset entity; `DatasetEntity` carries a well-formed
`origin` + origin-specific provenance; `overlap=unknown` on an `analyzed` role WARNs (it silently
no-ops B2 collapse). (3) **Provenance** — an evidence-line's originating task key materializes as
`prov:wasDerivedFrom` in the PROV-O graph, never as a `cito:` belief edge. (4) **Generation** — a
generic regeneration drift-check primitive (the dataset analog of the workbench fixpoint gate) the MM30
plan will drive.

**Tech Stack:** Python; `science_model` (pydantic) + `science_tool` (Click CLI, `@Check` validators,
RDF/TriG materialization via `rdflib`); `uv run pytest`; `ruff`.

**Repos:** All tasks in **`~/d/science`** (`science/` package). The MM30 `task → dataset` resolution
table, `mm30.v8.yml` `source_class` extension, dataset-entity generation, and filling the staged
evidence-lines are **out of scope** (separate `~/d/r/mm30` migration plan, gated on this + the
`epistemic-edges` framework plan + v3).

---

## File structure

| File | Responsibility | Phase |
|---|---|---|
| `science/src/science_tool/entities.py` | add `dataset` to `_BUILTIN_MARKDOWN_POLICIES` + status set | 1 |
| `science/model/src/science_model/entities.py` | confirm/extend `DatasetEntity` `origin` + provenance shape; surface `dataset_usage` on `EvidenceLineEntity` if not inherited | 0, 2b |
| `science/src/science_tool/validate/checks/datasets.py` *(new)* | `dataset_usage` ref integrity; `origin`-provenance well-formedness; `overlap` candidate WARN | 2 |
| `science/src/science_tool/graph/materialize.py` | evidence-line task key → `prov:wasDerivedFrom` (PROV-O), not belief | 3 |
| `science/src/science_tool/graph/entity_projection.py` *(new)* | generic regeneration drift-check primitive | 4 |
| `science/tests/...` | per-task tests | all |

---

## Phase 0 — v3 gate + confirm inherited surfaces (no/low code)

### Task 0: Confirm v3 + dataset surfaces

**Files:** none (investigation; record findings in this checklist).

- [ ] **Step 1: Confirm `layout_version: 3`** (as in the edges plan Task 0): `science validate` passes
  manifest + directory-structure; `entities/<kind>/` is the live layout.
- [ ] **Step 2: Confirm `dataset_usage` reaches the evidence-line.** Verify `Entity.dataset_usage`
  (`science_model/entities.py:333`) is inherited by `EvidenceLineEntity` and that authoring it on a
  line round-trips through load/serialize. If it is NOT surfaced on the line (template/schema hides
  it), note that Task 2b must surface it; if inherited cleanly, Task 2b is a no-op confirmation.
- [ ] **Step 3: Confirm `DatasetEntity` `origin` + provenance fields.** The recon noted `DatasetEntity`
  enforces `origin ∈ {external, derived}` (Invariants #7/#8, `science_model/entities.py:594`). Record
  what provenance fields already exist (accessions/access for external; derivation/`produced_by` for
  derived) so Task 2a only *adds* what's missing.
- [ ] **Step 4: Confirm B1/B2 read line-authored `dataset_usage`.** Verify `dataset_usage.py`
  (`usage_records_for_entity`) and `dataset_independence.py` operate over *any* entity's `dataset_usage`
  (so a line that carries it is materialized + grouped). Record the consumer URI semantics.

**Acceptance:** v3 confirmed; the three "is it already there?" questions (line `dataset_usage`,
`DatasetEntity` provenance fields, B1/B2 line consumption) are answered, so Tasks 2a/2b are scoped to
*only the genuine gap*.

---

## Phase 1 — Dataset entity layout

### Task 1: Register the `entities/datasets/` path policy **[v3-API]**

**Files:**
- Modify: `science/src/science_tool/entities.py` (`_BUILTIN_MARKDOWN_POLICIES` ~25–65; `_DEFAULT_STATUS`/`_STATUS_VALUES` ~200–262)
- Test: `science/tests/test_dataset_path_policy.py` *(new)*

- [ ] **Step 1: Write the failing test:**
```python
# tests/test_dataset_path_policy.py
from science_tool.entities import path_policy_for   # match the actual accessor in entities.py
def test_dataset_has_markdown_path_policy():
    policy = path_policy_for("dataset")
    assert policy is not None
    assert policy.directory.as_posix().endswith("entities/datasets")
    assert policy.naming == "slug"
```
- [ ] **Step 2: Run it; expect FAIL** (`dataset` not in policies). `cd ~/d/science/science && uv run pytest tests/test_dataset_path_policy.py -q`
- [ ] **Step 3: Add** `"dataset": EntityPathPolicy(Path("entities/datasets"), "slug")` to
  `_BUILTIN_MARKDOWN_POLICIES`; add a `_DEFAULT_STATUS["dataset"]`/`_STATUS_VALUES["dataset"]` of
  `{"active", "retired"}` (operational kind — no belief status).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit** `feat(entities): entities/datasets path policy`.

**Acceptance:** `dataset:<slug>` entities are first-class markdown entities under `entities/datasets/`
(design §4), so `dataset_usage` refs and gate 2 have real targets.

---

## Phase 2 — Validation

### Task 2a: `DatasetEntity` `origin` + origin-specific provenance

**Files:**
- Modify: `science/model/src/science_model/entities.py` (`DatasetEntity` ~594; only if Task 0 found gaps)
- Test: `science/tests/test_dataset_origin_provenance.py` *(new)*

- [ ] **Step 1: Write the failing tests** (design §4 / review L1):
```python
from pydantic import ValidationError
import pytest
from science_model.entities import DatasetEntity

def test_external_requires_accessions():
    DatasetEntity(id="dataset:gse19784", origin="external", source_class="observational",
                  accessions=["GSE19784"])                      # ok
    with pytest.raises(ValidationError):
        DatasetEntity(id="dataset:gse19784", origin="external", source_class="observational")  # missing accessions

def test_derived_requires_produced_by():
    DatasetEntity(id="dataset:meta_sumz", origin="derived", source_class="derived",
                  derived_kind="model_output", produced_by="stage:meta")   # ok
    with pytest.raises(ValidationError):
        DatasetEntity(id="dataset:meta_sumz", origin="derived", source_class="derived",
                      derived_kind="model_output")             # missing produced_by
```
- [ ] **Step 2: Run it; expect FAIL** (whichever invariant is missing per Task 0).
- [ ] **Step 3: Implement** the missing `model_validator` clauses on `DatasetEntity`: `origin ==
  "external"` requires non-empty `accessions` (add the field if absent); `origin == "derived"` requires
  `produced_by` (add if absent). Do **not** re-add invariants Task 0 found already present.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** a generated/registered dataset entity is operationally specified, not just
taxonomy-tagged (design §4, review L1).

### Task 2b: surface `dataset_usage` on the evidence-line (conditional)

**Files:** `science/model/src/science_model/entities.py` (`EvidenceLineEntity` ~725); test `science/tests/test_evidence_line_dataset_usage.py` *(new)*

- [ ] **Step 1: Write the test** that an `EvidenceLineEntity` accepts and round-trips a
  `dataset_usage=[DatasetUsage(ref="dataset:mmrf", role="analyzed", overlap="full")]`.
- [ ] **Step 2: Run it.** If Task 0 found `dataset_usage` already inherited, this **PASSES immediately**
  → this task is a confirmation, commit the test and move on. If it FAILS, proceed.
- [ ] **Step 3 (only if failing): surface** `dataset_usage` on `EvidenceLineEntity` (it is on base
  `Entity:333`; if a template/schema omits it for lines, explicitly include it).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** evidence-lines carry structured `dataset_usage` (design §2, review L2 — narrow gap).

### Task 2c: `dataset_usage` reference integrity (generic gate 2)

**Files:** `science/src/science_tool/validate/checks/datasets.py` *(new)*; test `science/tests/validate/test_check_dataset_usage_refs.py` *(new)*

- [ ] **Step 1: Write the failing test:** an entity carrying `dataset_usage` with `ref:
  dataset:nonexistent` yields `Result(severity=ERROR, rule="dataset.usage.ref_unresolved")`; a `ref`
  pointing at a registered dataset entity yields none. Follow `validate/checks/evidence_lines.py` style.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `@Check(section="datasets", order=10) def check_dataset_usage_refs(ctx)`:
  for every entity's `dataset_usage`, assert each `ref` resolves to a known `dataset:` entity in the
  index; ERROR otherwise. This is the **generic form of the design §3 gate 2** (migration's
  resolved-dataset-has-entity gate); MM30's migration relies on it.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** no `dataset_usage` can reference a non-existent dataset entity (design §3 gate 2).

### Task 2d: `overlap` candidate WARN (protects the B2 payoff)

**Files:** `science/src/science_tool/validate/checks/datasets.py` (extend); same test module.

- [ ] **Step 1: Write the failing test:** a `dataset_usage` with `role: analyzed` and `overlap:
  unknown` yields `Result(severity=WARN, rule="dataset.usage.overlap_unknown")`; `overlap: full` yields
  none.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `@Check(section="datasets", order=20) def check_overlap_unknown_candidates(ctx)`:
  WARN on `role == "analyzed"` + `overlap == "unknown"`, with a message noting that B2 will treat it as
  a *candidate* (no shared-source collapse) until `overlap` is curated to `full` (design §2 / review
  M2). WARN, not ERROR — `unknown` is legal but flags an un-collapsed group for review.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the silent-no-op failure mode (unknown overlap → no B2 collapse) is surfaced at validate
time (design §5, review M2).

---

## Phase 3 — Provenance wiring

### Task 3: evidence-line task key → `prov:wasDerivedFrom` (not belief) **[v3-API]**

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_evidence_line_relations` ~536; `_add_evidence_line_metadata` ~570)
- Test: `science/tests/test_evidence_line_task_provenance.py` *(new)*

- [ ] **Step 1: Write the failing test:** an evidence-line whose `source`/`derived_from` is a task ref
  (`task:t082`) emits `evidence-line prov:wasDerivedFrom task:t082` into the **provenance** graph and
  emits **no** `cito:` edge to the task (assert the knowledge graph has no triple linking the task to
  belief). The `cito:supports/disputes` edge still points only at the proposition target.
- [ ] **Step 2: Run it; expect FAIL** (if task-as-source isn't materialized to PROV-O today).
- [ ] **Step 3: Implement / confirm.** The recon shows `_add_evidence_line_relations:554–567` already
  emits `prov:wasDerivedFrom` for the line's `source`. Ensure a **task** source is accepted and routed
  to PROV-O (provenance graph), never the knowledge/belief graph. If `source` already does this for
  task refs, the change is just a regression test; otherwise route task refs to the provenance emission.
  *(v3-API: confirm the provenance-graph emission path under the v3 materialization contract.)*
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the migration's task key is auditable provenance, structurally incapable of entering
belief (design §3).

---

## Phase 4 — Generation drift gate

### Task 4: generic regeneration drift-check primitive

**Files:**
- Create: `science/src/science_tool/graph/entity_projection.py`
- Test: `science/tests/test_entity_projection_driftcheck.py` *(new)*

- [ ] **Step 1: Write the failing test:** given a list of "expected" entity records (the projection of
  some registry) and the committed on-disk entities, `check_projection_drift(expected, committed)`
  returns no diff when they match and a non-empty diff (naming the drifted ids) when they don't —
  performing **no writes**.
```python
from science_tool.graph.entity_projection import check_projection_drift
def test_driftcheck_detects_divergence():
    expected = {"dataset:mmrf": {"origin": "external", "source_class": "observational"}}
    committed = {"dataset:mmrf": {"origin": "external", "source_class": "derived"}}  # drifted
    diff = check_projection_drift(expected, committed)
    assert "dataset:mmrf" in diff and diff   # non-empty
```
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** a pure, side-effect-free `check_projection_drift(expected, committed) ->
  dict` (the dataset analog of the workbench fixpoint gate, edges plan Task 5d): deterministic compare,
  returns the per-id field diffs. The **actual `mm30.v8.yml → DatasetEntity` projection** is MM30-side
  (migration plan); this is the reusable engine + the CI hook a project wires.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the generated-projection invariant (committed `entities/datasets/` == registry
projection, design §4) has a reusable, side-effect-free drift primitive; MM30 supplies the projection.

---

## Phase 5 — Integration

### Task 5: end-to-end dataset grounding + B2 payoff on a fixture **[v3-API]**

**Files:** `science/tests/test_dataset_evidence_flow_e2e.py` *(new)*; small fixtures under `tests/fixtures/`.

- [ ] **Step 1: Write the failing test** exercising the whole loop on a fixture:
  - two empirical evidence-lines that both `dataset_usage` the *same* dataset (`dataset:mmrf`, role
    `analyzed`, overlap `full`) targeting one proposition → after materialize+B2, `reduce_units`
    **collapses** them to one winner (shared-source `independence_group`);
  - two empirical evidence-lines on *distinct* datasets (`dataset:mmrf`, `dataset:gse19784`) → stay
    **independent** (both contribute);
  - an empirical line with empty `dataset_usage` is `belief_eligible=False` (edges-plan rule) and
    excluded; adding `dataset_usage` flips it eligible;
  - a `dataset_usage.ref` to an unregistered dataset fails Task 2c;
  - the line's task source appears as `prov:wasDerivedFrom`, not in belief.
- [ ] **Step 2: Run it; expect FAIL → wire any glue → PASS.**
- [ ] **Step 3: Run full suite** `cd ~/d/science/science && uv run pytest tests/ -m "not snapshot and not real_projects" -q` + `uv run ruff check .`; expect green.
- [ ] **Step 4: Commit.**

**Acceptance:** the Issue-1 payoff (N-independent-datasets vs N-analyses-of-one) works end-to-end on a
fixture, with no MM30 data; this is the seam the deferred MM30 migration plugs into.

---

## Out of scope (separate `~/d/r/mm30` migration plan)

- The curated `task → dataset` **resolution table** (auto-seed + curate + the two loud-fail gates as a
  *migration* step), and recording `prov:wasDerivedFrom task:<id>` for real MM30 lines.
- `mm30.v8.yml` `source_class`/`origin` **extension** + the concrete `mm30.v8.yml → entities/datasets/`
  **projection** (wired to Task 4's drift primitive) + external-dataset registration.
- **Filling** the staged (`belief_eligible=False`) evidence-lines the `epistemic-edges` migration
  created with resolved `dataset_usage`.
- Gated on: this plan + the `epistemic-edges` framework plan + confirmed v3.

---

## Self-review notes (coverage vs design)

- §1.1 reuse (A1/A2/B1/B2) → no tasks (already merged); Task 0 confirms B1/B2 read line `dataset_usage`. ✓
- §1.2 seam (`belief_eligible`) → owned by edges plan; Task 5 exercises it; not duplicated. ✓
- §2 line carrier + required → edges plan owns the presence rule; Task 2b surfaces the field; Task 5
  exercises eligibility flip. ✓
- §2 `overlap=full` curation → Task 2d WARN (validate-time protection of the B2 payoff). ✓
- §3 resolution table → **MM30 plan** (out of scope); generic gate 2 → Task 2c; task-trace → Task 3. ✓
- §4 dataset entities → Task 1 (path policy), Task 2a (origin/provenance), Task 4 (drift primitive);
  the MM30 projection itself is deferred. ✓
- §5 independence payoff → Task 5 e2e. ✓
- §9 risks: M2 overlap (Task 2d), origin under-specification (Task 2a), `source_class` registry
  extension (MM30 plan), intra-line breadth→strength (out of scope, belief-engine owners). ✓
- [v3-API] tasks: 1, 3, 5 — carry the finalize-against-v3 note.

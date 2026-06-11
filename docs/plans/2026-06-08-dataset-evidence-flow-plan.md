# Dataset Evidence Flow (Framework) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

> **v3 status (2026-06-10 reconciliation).** The v2→v3 layout migration **landed** (applied 2026-06-09;
> v3 conformance gate `2ffb182f`), and `docs/epistemic-data-model` was merged to `main`. The
> *dataset-specific* framework (Tasks 1–4) is therefore **v3-unblocked**. Phase 0 now *confirms* v3 in
> the target project rather than gating on it. Tasks tagged **[v3-API]** still finalize against the
> confirmed v3 substrate API (entity layout, materialization contract).
>
> **⛔ Task 5 is still gated on the `epistemic-edges` framework plan.** Its belief-eligibility assertions
> require the `belief_eligible` field + staging-exclusion machinery, which that plan owns and which is
> **not yet in this repo** (confirmed 2026-06-10: zero `belief_eligible` occurrences in `science/model`,
> `science/src`, `science/tests`; `EvidenceLineEntity` has no such field). The *dataset-independence*
> half of Task 5 (B2 same-vs-distinct collapse) does **not** depend on it and can run now; the
> `belief_eligible` assertions must wait. See Task 5's gating note.

> **Reconciled against merged `~/d/science` `main` (2026-06-10).** Substantial drift from the original
> draft was found and corrected here — most of what this plan first proposed to *build* has since been
> built (differently) by the dataset-taxonomy / register-run / `dataset_influence` work:
> - **Datasets are already first-class** as markdown descriptors under **`doc/datasets/*.md`** (plus
>   datapackages), discovered by `dataset_frontmatters` (scan roots in `graph/sources.py:297`), and
>   written idempotently by `datasets_register.py::write_derived_dataset_entities`. There is **no
>   `entities/datasets/` path policy** and none is needed. (Design doc §4 now points at
>   `doc/datasets/<slug>.md`, the real home.)
> - **`dataset_usage` reference integrity already ships** in `validate/checks/dataset_influence.py`
>   (registered in `CANONICAL_CHECK_MODULES`), so the originally-planned new `dataset_usage.py` module +
>   registration is dropped.
> The single genuine validation gap that remains is the **`overlap=unknown` (or omitted) on any
> dependence role** WARN (Task 2d). Everything else in this plan is now *confirm / characterize /
> regression-test*.

> **Non-duplication.** The `belief_eligible` field on `EvidenceLineEntity`, its staging exclusion from
> belief materialization, and the *presence* rule "empirical line must have `dataset_usage` to be
> belief-eligible" are owned by the **`epistemic-edges` framework plan** (its Tasks 1c / 2c / 3b). This
> plan must **not** re-implement them; it consumes them and adds only the dataset-specific pieces.

**Goal:** Close the remaining framework gaps so evidence-lines grounded in datasets behave correctly —
add the `overlap=unknown` B2-protection WARN, and pin the already-built surfaces (`doc/datasets/`
dataset entities, `DatasetUsage` ref integrity, `DatasetEntity` origin invariants, task→`prov:`
provenance, A1/A2/B1/B2 independence) with characterization + regression + an end-to-end payoff test —
**without** rebuilding any of them and **without** the MM30 resolution-table data or dataset generation
(deferred).

**Architecture:** Thin verification + one small extension over already-merged machinery. (1) **Layout**
— datasets are *already* first-class under `doc/datasets/`; confirm, don't add. (2) **Validation** —
`DatasetUsage.ref` integrity *already* ships in `dataset_influence.py`; the only new check is
`overlap=unknown` (or omitted) on any **dependence role** WARNing (it silently no-ops the B2 collapse).
(3) **Provenance**
— the evidence-line `source → prov:wasDerivedFrom` split into the provenance graph (never belief)
*already* exists; confirm a task-ref source routes there. (4) **Generation** — a generic,
side-effect-free regeneration drift-check primitive (the read-only CI analog of `datasets_register.py`'s
idempotent write) the MM30 plan will drive.

**Tech Stack:** Python; `science_model` (pydantic) + `science_tool` (Click CLI, `@Check` validators,
RDF/TriG materialization via `rdflib`); `uv run pytest`; `ruff`.

**Repos:** All tasks in **`~/d/science`** (`science/` package). The MM30 `task → dataset` resolution
table, `mm30.v8.yml` `source_class` extension, dataset-entity generation, and filling the staged
evidence-lines are **out of scope** (separate `~/d/r/mm30` migration plan, gated on this + the
`epistemic-edges` framework plan).

---

## File structure

| File | Responsibility | Phase |
|---|---|---|
| *(none — layout)* | datasets are already first-class under `doc/datasets/`; Task 1 only confirms | 1 |
| `science/src/science_tool/validate/checks/dataset_influence.py` | **extend** (already registered) with the `overlap=unknown` + dependence-role candidate WARN | 2d |
| `science/src/science_tool/graph/materialize.py` | confirm evidence-line task-ref `source` → `prov:wasDerivedFrom` (provenance graph), not belief | 3 |
| `science/src/science_tool/graph/entity_projection.py` *(new)* | generic regeneration drift-check primitive | 4 |
| `science/model/tests/test_dataset_models.py` *(extend)* | pin `DatasetEntity` origin invariants (#7/#8) | 2a |
| `science/tests/validate/test_checks_dataset_influence.py` *(extend)* | `doc/datasets/` resolution (exists), ref-integrity severity contract, new `overlap=unknown` WARN | 1, 2c, 2d |
| `science/tests/...` | remaining per-task tests (2b, 3, 4, 5) | as noted |

> **No new check module, no `CANONICAL_CHECK_MODULES` edit.** `dataset_influence.py` already exists and
> is registered; Task 2d extends it in place.
>
> **Extend existing tests, don't fork.** `test_dataset_models.py` already covers origin invariants and
> `test_checks_dataset_influence.py` already has a `doc/datasets/` markdown-resolution test
> (`test_check_dataset_influence_resolves_local_markdown_dataset_ref`, ~:312) and the `ref-unresolved`
> WARN cases. The confirm/characterize tasks add cases to those files rather than creating parallel ones.

---

## Phase 0 — Confirm v3 + the already-built dataset surfaces

### Task 0: Confirm v3 + record what already exists

**Files:** none (investigation; record findings in this checklist).

- [ ] **Step 1: Confirm `layout_version: 3`** in the target project: `science validate` passes manifest +
  directory-structure; `entities/<kind>/` is the live layout. (Migration landed 2026-06-09; this is a
  re-confirmation, not a gate.)
- [ ] **Step 2: Confirm the dataset home is `doc/datasets/`.** Verify `dataset_frontmatters`
  (`validate/_helpers.py`) discovers datasets from both backends, and that `graph/sources.py:297`
  scan roots include `doc/datasets`. Confirm `datasets_register.py::write_derived_dataset_entities`
  writes `doc/datasets/<slug>.md`. Record that **no `entities/datasets/` policy exists or is needed**
  (Task 1 is a confirmation).
- [ ] **Step 3: Confirm `dataset_usage` reaches the evidence-line.** Verify `Entity.dataset_usage`
  (`science_model/entities.py:333`, `list[DatasetUsage]`) is inherited by `EvidenceLineEntity`
  (`entities.py:725`) and round-trips through load/serialize. If surfaced cleanly, Task 2b is a no-op
  confirmation.
- [ ] **Step 4: Confirm `DatasetEntity` `origin` invariants.** `DatasetEntity` (`entities.py:594-644`)
  enforces #7 (`origin=external` → `access` block; no `derivation`/`produced_by`) and #8
  (`origin=derived` → `derivation` and/or non-empty `produced_by`; no `access`/`accessions`/`local_path`).
  Read the real `access` / `derivation` block constructors so Task 2a's tests use correct shapes.
- [ ] **Step 5: Confirm `dataset_influence.py` ref integrity + registration.** Verify it is in
  `CANONICAL_CHECK_MODULES` (`validate/checks/__init__.py`, ~line 61) and that it already emits:
  `dataset-influence.dataset-usage-malformed` (ERROR), `dataset-influence.self-reference` (ERROR),
  `dataset-influence.ref-not-dataset` (ERROR), `dataset-influence.ref-unresolved` (WARN, local/commons
  miss), `dataset-influence.ref-unresolved-unavailable` (INFO), `dataset-influence.paper-datasets-*`.
  Record that `_OVERLAPS = ("full","partial","unknown")` is validated for membership but **not** for the
  dependence-role + `unknown`/omitted-overlap candidate case (that is Task 2d, the genuine gap).
- [ ] **Step 6: Confirm B1/B2 read line-authored `dataset_usage`.** Verify `graph/dataset_usage.py` and
  `graph/dataset_independence.py` operate over *any* entity's `dataset_usage` (so a line that carries it
  is materialized + grouped), and confirm the `source → prov:wasDerivedFrom` provenance split in
  `materialize.py` (~:286, comment ~:570).

**Acceptance:** v3 confirmed; the "is it already there?" questions (dataset home, line `dataset_usage`,
`DatasetEntity` invariants, `dataset_influence` ref integrity + registration, B1/B2 line consumption,
prov split) are answered, so the remaining tasks are scoped to *only the genuine gap* plus pinning.

---

## Phase 1 — Dataset entity layout (confirmation)

### Task 1: Confirm datasets are first-class under `doc/datasets/` **[v3-API]**

> **Reconciled:** the original "register an `entities/datasets/` path policy" task is **obsolete**.
> Datasets are markdown descriptors under `doc/datasets/*.md` (+ datapackages), discovered via
> `dataset_frontmatters`, written by `datasets_register.py`, and already populated in MM30. There is
> nothing to register; this task pins the real model so `dataset_usage` refs and the influence check
> have real targets.

**Files:**
- Modify: `science/tests/validate/test_checks_dataset_influence.py` *(extend)* — characterization only

> **Largely already covered.** `test_check_dataset_influence_resolves_local_markdown_dataset_ref` (~:312)
> already asserts a `doc/datasets/` markdown descriptor resolves a `dataset:` ref. This task confirms
> that coverage exists and adds only a gap case if one is missing — it does **not** create a new file.

- [ ] **Step 1: Confirm the existing test** asserts a `dataset:<slug>` descriptor under `doc/datasets/`
  is discovered by `dataset_frontmatters` and resolves (no `dataset-influence.ref-unresolved`). If a
  case is missing (e.g. an `evidence-line`/non-paper consumer referencing a `doc/datasets/` dataset),
  add it to the existing module, following its fixtures.
- [ ] **Step 2: Run it; expect PASS** (the layout already works). `cd ~/d/science/science && uv run pytest tests/validate/test_checks_dataset_influence.py -q`
- [ ] **Step 3: Commit** *(only if a case was added)* `test(datasets): characterize doc/datasets dataset discovery`.

**Acceptance:** `dataset:<slug>` descriptors under `doc/datasets/` are confirmed first-class discovery
targets (design §4 — *with the corrected location*), so `dataset_usage` refs and the influence check
resolve against real entities. **No path policy is added.**

---

## Phase 2 — Validation

### Task 2a: Confirm `DatasetEntity` origin invariants (#7/#8) — characterization tests

> **Note:** `DatasetEntity` **already enforces** invariants #7/#8 (`science_model/entities.py:594-644`,
> `model_validator`): `origin == "external"` requires an **`access` block** (and must *not* carry
> `derivation`/`produced_by`); `origin == "derived"` requires a **`derivation` block and/or a non-empty
> `produced_by`** (a **list** of code-file refs) and must *not* carry `access`/`accessions`/`local_path`.
> This task **characterizes** the existing contract — it does **not** change the model. The *generator*
> (MM30 plan) is what must emit a conformant `access`/`derivation` block per dataset.

**Files:**
- Modify: `science/model/tests/test_dataset_models.py` *(extend)* — characterization only

> **Largely already covered.** `test_dataset_models.py` already exercises #7/#8 (external⟹access required,
> external⟹no derivation, derived⟹no access, derived-without-derivation/produced_by, `produced_by=[]`).
> Add only genuinely-missing cases. Two pitfalls the snippets below avoid:
> - **Use the module's `_entity_kwargs()` helper** (and `_ext_access()` / `_der_block()`) — a bare
>   `DatasetEntity(id=..., origin=...)` is missing required entity fields (`kind`, `type`, `title`,
>   `project`, `file_path`, …), so `match=` would fire on a *missing-field* error, not the origin invariant.
> - **`produced_by` entries must be `code-file:` refs** (enforced at `science_model/entities.py:359`) — a
>   `code:` prefix raises for the *wrong reason*. Use `pytest.raises(..., match=<invariant text>)` so the
>   test characterizes the origin invariant specifically.

- [ ] **Step 1: Add any missing characterization cases** in `test_dataset_models.py`, reusing its
  existing `_entity_kwargs()` / `_ext_access()` / `_der_block()` helpers (read them first):
```python
def test_external_must_not_carry_produced_by():
    with pytest.raises(ValidationError, match="origin=external must not carry produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="external", access=_ext_access(),
                      produced_by=["code-file:stages/meta.smk"])   # invariant #7 violation
```
  (External-requires-access is at ~:211, derived-requires-derivation-or-produced_by at ~:238/:249 — confirm
  they assert with `match=` on the invariant text; add the `match=` if missing. Only *add* the
  produced-by-on-external case if it is not already covered.)
- [ ] **Step 2: Run them; expect PASS** (the invariants already exist). If a `match=` fails because a
  different error fires first (e.g. a malformed `produced_by` ref or a missing entity field), fix the
  test input so it isolates the origin invariant. If an invariant is genuinely absent, only then add the
  `model_validator` clause.
- [ ] **Step 3: Commit** *(only if cases were added)* (`test(model): characterize DatasetEntity origin invariants`).

**Acceptance:** the existing #7/#8 invariants are pinned by tests with correct `access`/`derivation`/
`produced_by`-list shapes; no model change (design §4, review L1).

### Task 2b: Confirm `dataset_usage` on the evidence-line

**Files:** test `science/tests/test_evidence_line_dataset_usage.py` *(new)*; `science/model/src/science_model/entities.py` *(only if a genuine gap)*

- [ ] **Step 1: Write the test** that an `EvidenceLineEntity` accepts and round-trips a
  `dataset_usage=[DatasetUsage(ref="dataset:mmrf", role="analyzed", overlap="full")]`.
- [ ] **Step 2: Run it.** Per Task 0, `dataset_usage` is inherited from base `Entity:333`, so this
  should **PASS immediately** → commit the test as a confirmation and move on. If it FAILS, surface
  `dataset_usage` on `EvidenceLineEntity` explicitly, then re-run to PASS.
- [ ] **Step 3: Commit.**

**Acceptance:** evidence-lines carry structured `dataset_usage` (design §2, review L2 — narrow gap).

### Task 2c: Characterize the existing `dataset_usage` ref-integrity **warning contract** (already shipped)

> **Reconciled:** the original "build a new `dataset_usage.py` check + register it" task is **dropped**.
> `dataset_influence.py` already implements ref resolution and is registered in `CANONICAL_CHECK_MODULES`.
> This task pins its **warning contract** — and is explicit that it is **not a hard gate**: a
> `dataset_usage.ref` that fails to resolve locally is *surfaced* (`WARN`), **not prevented**. Only a
> ref that resolves to a *non-dataset* entity is a hard `ERROR`. The design's "gate 2" framing
> (resolved-dataset-must-have-an-entity, *loud-fail*) is therefore **not** met by this check alone; the
> loud-fail behavior is a **migration/CI concern owned by the MM30 plan** (see Out of scope).

**Files:**
- Modify: `science/tests/validate/test_checks_dataset_influence.py` *(extend)* — characterization only

- [ ] **Step 1: Add any missing characterization cases** over the validate runner (not a direct call),
  following the module's existing style, pinning the **severity contract**:
  - `dataset_usage` with `ref: dataset:nonexistent` (no local/commons descriptor) →
    `Result(severity=WARN, rule="dataset-influence.ref-unresolved")` — *surfaced, not blocked*;
  - registry resources unavailable → `Result(severity=INFO, rule="dataset-influence.ref-unresolved-unavailable")`;
  - a `ref` resolving to a **non-dataset** entity → `Result(severity=ERROR, rule="dataset-influence.ref-not-dataset")` — the only hard failure;
  - a `ref` resolving to a `doc/datasets/` descriptor → **no** result (already covered, ~:312);
  - malformed `dataset_usage` (not a list / bad `role` / `overlap` ∉ `_OVERLAPS`) →
    `dataset-influence.dataset-usage-malformed` (ERROR).
- [ ] **Step 2: Run them; expect PASS** (behavior already exists).
- [ ] **Step 3: Commit** *(only if cases were added)* (`test(validate): pin dataset_usage ref-integrity warning contract`).

> **Decision to raise with the user (do not silently change):** the MM30 migration's gate ("every
> *resolved* dataset must have a `doc/datasets/` entity, else fail the migration") wants a **hard error**,
> but the live check warns on local misses (deliberately — cross-project/commons refs are unverifiable
> in a single project). That hard gate belongs to the **MM30 migration step** (a migration-time
> assertion over its own resolution table), not to this project-agnostic validate check.

**Acceptance:** the `dataset_influence` ref-resolution **warning contract** is pinned by tests
(WARN local-miss / INFO unavailable / ERROR non-dataset / ERROR malformed); the design's *loud-fail*
gate 2 is explicitly delegated to the MM30 migration plan, not claimed here (design §3).

### Task 2d: `overlap=unknown` on any **dependence role** candidate WARN (the genuine gap, extends `dataset_influence.py`)

> **Scope corrected (review F3):** B2 collapse fires only on `overlap == "full"`
> (`dataset_independence.py:235`, `direct_full`) and the dependence interpretation covers **all four**
> `DEPENDENCE_ROLES = {analyzed, set_definition_source, training, upstream}` (`dataset_independence.py:16`).
> So `overlap=unknown` silently prevents collapse for **every** dependence role, not just `analyzed`.
> The WARN must cover the whole set. (`validation_source`/`cited` are *not* dependence roles — no WARN.)
>
> **Omitted overlap == unknown (review F2):** `DatasetUsage.overlap` **defaults to `"unknown"`**
> (`packages/schema.py:215`) and materialization coerces a missing value the same way
> (`graph/dataset_usage.py:67`, `str(usage.overlap or "unknown")`). So an entry with **no `overlap` key**
> has identical B2 no-collapse behavior and must WARN too. Normalize with `(entry.get("overlap") or
> "unknown") == "unknown"` — **not** `entry.get("overlap") == "unknown"` (which would miss the omitted case).

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_influence.py` (the existing, already-registered module)
- Test: `science/tests/validate/test_checks_dataset_influence.py` (extend)

- [ ] **Step 1: Write the failing test:** a `dataset_usage` entry with `overlap: unknown` and a
  **dependence** role yields `Result(severity=WARN, rule="dataset-influence.overlap-unknown-candidate")`
  — parametrize over all of `{analyzed, set_definition_source, training, upstream}`. **Add an
  omitted-`overlap` case** (entry has a dependence role and *no* `overlap` key) → same WARN. Assert
  `overlap: full` yields none, and that `overlap: unknown` (and omitted) with a **non-dependence** role
  (`validation_source`, `cited`) yields **no** such WARN. Run it through the validate runner.
- [ ] **Step 2: Run it; expect FAIL** (no such rule today).
- [ ] **Step 3: Implement** the WARN inside `evaluate_dataset_influence` (or a sibling helper) in
  `dataset_influence.py`. **Import the dependence-role set from the single source of truth** —
  `from science_tool.graph.dataset_independence import DEPENDENCE_ROLES` — do **not** re-hardcode the
  list (keeps it in lock-step with B2). While iterating `usage_entries`, when
  `entry["role"] in DEPENDENCE_ROLES` and `(entry.get("overlap") or "unknown") == "unknown"` (the
  `or "unknown"` catches the **omitted** case, matching `DatasetUsage`'s default and the materialization
  coercion), emit `_result(Severity.WARN, path, f"{ident}: dataset_usage {ref!r} has a dependence role
  ({role}) with overlap=unknown — B2 treats it as a candidate (no shared-source collapse) until overlap
  is curated to full", "dataset-influence.overlap-unknown-candidate")`. WARN, not ERROR — `unknown` is
  legal but flags an un-collapsed independence group for review (design §2 / review M2). No new module,
  no `CANONICAL_CHECK_MODULES` edit (the module is already registered).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit** (`feat(validate): warn dependence-role + overlap=unknown candidate`).

**Acceptance:** the silent-no-op failure mode (unknown overlap → no B2 collapse) is surfaced at validate
time for **all dependence roles** (sourced from `DEPENDENCE_ROLES`), by the existing influence check
(design §5, review M2; scope per review F3).

---

## Phase 3 — Provenance wiring (confirmation + regression)

### Task 3: Confirm evidence-line task-ref `source` → `prov:wasDerivedFrom` (not belief) **[v3-API]**

> **Reconciled:** the `source → prov:wasDerivedFrom` split into the provenance graph already exists
> (`materialize.py:286`; knowledge/provenance comment ~:570; overlay source at :298; entity-target
> derivation at :449). This task adds a **regression test** that a *task-ref* source lands in provenance,
> never belief.

**Files:**
- Modify *(only if a gap)*: `science/src/science_tool/graph/materialize.py` (`_add_evidence_line_relations` ~:554; `_add_evidence_line_metadata` ~:570)
- Test: `science/tests/test_evidence_line_task_provenance.py` *(new)*

- [ ] **Step 1: Write the test:** an evidence-line whose `source`/`derived_from` is a task ref
  (`task:t082`) emits `<line> prov:wasDerivedFrom task:t082` into the **provenance** graph and emits
  **no** `cito:` edge linking the task to belief. The `cito:supports/disputes` edge still points only at
  the proposition target.
- [ ] **Step 2: Run it.** If the task-ref source already routes to PROV-O, this PASSES → keep it as a
  regression guard. If it FAILS (task refs not routed), proceed.
- [ ] **Step 3 (only if failing): route** task-ref sources to the provenance emission path (alongside the
  existing `_source_uri`/`PROV.wasDerivedFrom` logic), never the knowledge/belief graph. *(v3-API:
  confirm the provenance-graph emission path under the v3 materialization contract.)*
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the migration's task key is auditable provenance, structurally incapable of entering
belief (design §3).

---

## Phase 4 — Generation drift gate

### Task 4: generic regeneration drift-check primitive

> **Reconciled:** `datasets_register.py::write_derived_dataset_entities` already writes `doc/datasets/`
> descriptors **idempotently** (skip-if-identical). This task adds the *read-only* CI analog — a pure
> drift check the MM30 projection can run without writing — so a project can assert "committed
> `doc/datasets/` == registry projection" in CI.

**Files:**
- Create: `science/src/science_tool/graph/entity_projection.py`
- Test: `science/tests/test_entity_projection_driftcheck.py` *(new)*

- [ ] **Step 1: Write the failing test:** given a dict of "expected" dataset records (the projection of
  some registry) and the committed on-disk records, `check_projection_drift(expected, committed)`
  returns an empty diff when they match and a non-empty diff (naming the drifted ids) when they don't —
  performing **no writes**.
```python
from science_tool.graph.entity_projection import check_projection_drift
def test_driftcheck_detects_divergence():
    expected = {"dataset:mmrf": {"origin": "external", "source_class": "observational"}}
    committed = {"dataset:mmrf": {"origin": "external", "source_class": "derived"}}  # drifted
    diff = check_projection_drift(expected, committed)
    assert "dataset:mmrf" in diff and diff   # non-empty

def test_driftcheck_clean_when_matching():
    rec = {"dataset:mmrf": {"origin": "external", "source_class": "observational"}}
    assert check_projection_drift(rec, dict(rec)) == {}
```
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** a pure, side-effect-free `check_projection_drift(expected, committed) ->
  dict` (deterministic compare; returns per-id field diffs incl. ids present on only one side). The
  **actual `mm30.v8.yml → doc/datasets/` projection** is MM30-side (migration plan); this is the
  reusable engine + the CI hook a project wires. Mirror the idempotency contract `datasets_register.py`
  already uses for writes.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the generated-projection invariant (committed `doc/datasets/` == registry projection,
design §4 *with corrected location*) has a reusable, side-effect-free drift primitive; MM30 supplies the
projection.

---

## Phase 5 — Integration

### Task 5: end-to-end dataset grounding + B2 payoff on a fixture **[v3-API]**

> **Split by dependency (review F1).** Task 5a (B2 independence payoff) is runnable **now** — it does not
> touch `belief_eligible`. Task 5b (belief-eligibility) is **gated on the `epistemic-edges` framework
> plan**, which introduces `belief_eligible` (confirmed absent from this repo on 2026-06-10). Do **not**
> write the 5b assertions until that field exists; attempting them now will not even import.

**Files:** `science/tests/test_dataset_evidence_flow_e2e.py` *(new)*; small fixtures under `tests/fixtures/` (datasets as `doc/datasets/*.md` descriptors).

#### Task 5a — independence payoff + validation + provenance (runnable now)

- [ ] **Step 1: Write the failing test** exercising the loop on a fixture:
  - two empirical evidence-lines that both `dataset_usage` the *same* dataset (`dataset:mmrf`, role
    `analyzed`, overlap `full`) targeting one proposition → after materialize+B2, `reduce_units`
    **collapses** them to one winner (shared-source `independence_group`);
  - two empirical evidence-lines on *distinct* datasets (`dataset:mmrf`, `dataset:gse19784`) → stay
    **independent** (both contribute);
  - a `dataset_usage.ref` to an unregistered dataset WARNs via Task 2c's characterized check;
  - a dependence-role entry with `overlap=unknown` WARNs via Task 2d;
  - the line's task-ref source appears as `prov:wasDerivedFrom`, not in belief.
- [ ] **Step 2: Run it; expect FAIL → wire any glue → PASS.**
- [ ] **Step 3: Run full suite** `cd ~/d/science/science && uv run pytest tests/ -m "not snapshot and not real_projects" -q` + `uv run ruff check .`; expect green.
- [ ] **Step 4: Commit.**

#### Task 5b — belief-eligibility exclusion ⛔ **GATED on the `epistemic-edges` framework plan**

- [ ] **Precondition:** `belief_eligible` exists on `EvidenceLineEntity` and the staging-exclusion path
  is merged (owned by the edges plan). If `grep -rn belief_eligible science/` is empty, **skip this
  task** and leave it unchecked.
- [ ] **Step 1: Extend the e2e fixture** so that an empirical line with `belief_eligible=False` (empty
  `dataset_usage`) is **excluded** from belief; a line explicitly written **with** `dataset_usage` **and**
  `belief_eligible=True` (as the resolver/migration would write it — that flip is the MM30 plan's job,
  *not* this framework plan) **enters** belief. Do **not** assert an automatic framework flip — no task
  here performs one.
- [ ] **Step 2: Run → PASS. Step 3: Commit.**

**Acceptance:** the Issue-1 payoff (N-independent-datasets vs N-analyses-of-one) works end-to-end on a
fixture with no MM30 data (5a, now); belief-eligibility exclusion is verified once the edges plan lands
(5b). This is the seam the deferred MM30 migration plugs into.

---

## Out of scope (separate `~/d/r/mm30` migration plan)

- The curated `task → dataset` **resolution table** (auto-seed + curate + the two loud-fail gates as a
  *migration* step), and recording `prov:wasDerivedFrom task:<id>` for real MM30 lines.
- `mm30.v8.yml` `source_class`/`origin` **extension** + the concrete `mm30.v8.yml → doc/datasets/`
  **projection** (wired to Task 4's drift primitive) + external-dataset registration.
- **Filling** the staged (`belief_eligible=False`) evidence-lines the `epistemic-edges` migration
  created with resolved `dataset_usage`.
- Gated on: this plan + the `epistemic-edges` framework plan + confirmed v3.

---

## Self-review notes (coverage vs design, reconciled 2026-06-10)

- §1.1 reuse (A1/A2/B1/B2) → no tasks (already merged); Task 0 confirms B1/B2 read line `dataset_usage`. ✓
- §1.2 seam (`belief_eligible`) → owned by edges plan; Task 5 exercises it; not duplicated. ✓
- §2 line carrier + required → edges plan owns the presence rule; Task 2b confirms the field; Task **5b
  (gated on edges plan)** exercises eligibility — `belief_eligible` is **not in this repo yet** (F1). ✓
- §2 `overlap=full` curation → **Task 2d WARN — the one genuine build** (validate-time protection of the
  B2 payoff), extending `dataset_influence.py`, covering **all `DEPENDENCE_ROLES`** not just `analyzed`
  (F3), and treating **omitted overlap as `unknown`** via `(entry.get("overlap") or "unknown")` (F2). ✓
- §3 resolution table → **MM30 plan** (out of scope); ref integrity → **already shipped in
  `dataset_influence.py`** as a **WARN contract, not a hard gate** (F2) — characterized by Task 2c; the
  loud-fail "gate 2" is delegated to the MM30 migration step; task-trace → Task 3 (confirm + regression). ✓
- §4 dataset entities → **corrected to `doc/datasets/`** (not `entities/datasets/`): Task 1 confirms the
  layout, Task 2a pins origin/provenance, Task 4 the drift primitive; the MM30 projection is deferred.
  Design doc §4 corrected to `doc/datasets/<slug>.md` (2026-06-10). ✓
- §5 independence payoff → Task 5a e2e (runnable now); Task 5b (eligibility) gated on edges plan. ✓
- §9 risks: M2 overlap (Task 2d), origin under-specification (Task 2a), `source_class` registry
  extension (MM30 plan), intra-line breadth→strength (out of scope, belief-engine owners). ✓
- [v3-API] tasks: 1, 3, 5 — carry the finalize-against-v3 note. v3 itself landed 2026-06-09. ✓
- **Dropped from original draft:** new `entities/datasets/` path policy (Task 1) and new
  `validate/checks/dataset_usage.py` module + `CANONICAL_CHECK_MODULES` registration (Tasks 2c/2d) —
  both superseded by merged work (`doc/datasets/` layout; registered `dataset_influence.py`). ✓
- **Extend, don't fork (review Note):** Tasks 1/2a/2c/2d add cases to `test_dataset_models.py` and
  `test_checks_dataset_influence.py` (which already cover origin invariants and `doc/datasets/`
  resolution) rather than creating parallel test files. ✓
- **`produced_by` refs are `code-file:` (review F4):** Task 2a uses `code-file:` (per
  `entities.py:359`) and `pytest.raises(match=...)` so the test characterizes the *origin* invariant,
  not an incidental bad-ref error. ✓

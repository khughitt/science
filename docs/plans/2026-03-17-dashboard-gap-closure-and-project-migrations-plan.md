# Dashboard Gap Closure And Project Migrations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining dashboard gaps in the claim-centric uncertainty rollout and migrate existing projects onto the new claim/evidence workflow without losing their current research state.

**Architecture:** Move the dashboard away from raw triple heuristics and toward reusable store-level uncertainty summaries that understand claim support, dispute, evidence composition, and neighborhood fragility. Treat project migration as a documentation-first rollout: define the canonical dashboard outputs, add the missing graph/query machinery, then migrate projects by decomposing high-level hypotheses into relation claims plus typed evidence records.

**Tech Stack:** Click CLI, rdflib dataset queries, marimo/Polars visualization, Markdown docs, pytest, Ruff, Pyright.

## Status Snapshot (2026-03-18)

This plan is now partially implemented on `main`.

Completed:
- Task 1 landed: `docs/claim-centric-dashboard-contract.md` now defines the canonical claim and neighborhood summary contract, and the claim-centric uncertainty design links to it.
- Task 2 landed in a minimal but usable form: `graph add claim` and `graph add relation-claim` accept `--evidence-type`, and the graph store aggregates typed evidence signals for dashboarding.
- Task 3 landed on `main` via `d4acff2`: `query_dashboard_summary(...)` and `science-tool graph dashboard-summary` now exist and expose claim summaries in `table` and `json` formats.
- Task 4 now has a first implementation: `query_neighborhood_summary(...)` and `science-tool graph neighborhood-summary` provide claim-centered neighborhood risk summaries with separate structural fragility reporting.
- Task 6 is complete: the shared migration guide and project-specific migration guides were written.
- Task 7 has been piloted in `3d-attention-bias`: the project was migrated to claim-backed support/dispute records and typed evidence.

Still pending:
- Task 5: the marimo notebook/dashboard still needs to be rebuilt around the store-level summary surfaces.
- Task 8: shared user guidance still needs a final pass to teach the dashboard-guided migration workflow.

Refinement note:
- The shipped `dashboard-summary` command already covers the core claim-level summary fields, so the next implementation phase should treat claim summaries as an existing dependency and focus on neighborhood summaries plus notebook integration rather than rebuilding Task 3 from scratch.

---

### Task 1: Define A Reusable Dashboard Summary Contract

**Status:** Completed.

**Files:**
- Create: `docs/claim-centric-dashboard-contract.md`
- Modify: `docs/plans/2026-03-16-claim-centric-uncertainty-design.md`
- Test: none

**Step 1: Write the contract document**

Create `docs/claim-centric-dashboard-contract.md` defining:

- the dashboard summary units (`claim_summary`, `neighborhood_summary`, `evidence_mix_summary`)
- required panels:
  - weakly supported claims
  - contested claims
  - single-source claims
  - claims lacking empirical data evidence
  - high-uncertainty neighborhoods
- required fields per claim summary:
  - `claim`
  - `label`
  - `support_count`
  - `dispute_count`
  - `source_count`
  - `evidence_types`
  - `has_empirical_data`
  - `belief_state`
  - `risk_score`

**Step 2: Define what the dashboard must not do**

Document that the dashboard must not:

- treat raw `sci:confidence` as the primary signal
- infer claim state from arbitrary notebook-local string scanning
- collapse empirical, simulation, and literature support into one undifferentiated bucket

**Step 3: Link the uncertainty design doc**

Add a short note in `docs/plans/2026-03-16-claim-centric-uncertainty-design.md` pointing to `docs/claim-centric-dashboard-contract.md` as the canonical dashboard data contract.

**Step 4: Commit**

```bash
git add docs/claim-centric-dashboard-contract.md docs/plans/2026-03-16-claim-centric-uncertainty-design.md
git commit -m "docs: define claim-centric dashboard contract"
```

### Task 2: Add Evidence-Type Metadata Needed For Dashboard Differentiation

**Status:** Partially completed on `main`.

What landed:
- `graph add claim` and `graph add relation-claim` now accept `--evidence-type`.
- `science-tool` persists that metadata in provenance and aggregates it in dashboard summaries.

Remaining gap:
- We still need to decide whether richer evidence-item-first authoring should supersede or complement claim-level evidence-type metadata for future dashboard and migration work.

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py`
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add tests covering:

- authoring an evidence item or claim-supporting assertion with an explicit evidence type
- querying evidence summaries that distinguish:
  - `literature_evidence`
  - `empirical_data_evidence`
  - `simulation_evidence`
  - `benchmark_evidence`
  - `expert_judgment`
  - `negative_result`

Example:

```python
def test_graph_evidence_summary_distinguishes_empirical_and_simulation_support() -> None:
    ...
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "evidence_summary or evidence_type"
```

Expected: FAIL because the graph model does not yet expose typed evidence summaries.

**Step 3: Implement the minimal schema support**

Update the model and CLI so evidence-bearing entities can carry an explicit evidence type in graph/provenance or claim metadata, and make sure the store can aggregate those types per claim.

**Step 4: Run the targeted tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "evidence_summary or evidence_type"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-model/src/science_model/profiles/core.py science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add typed evidence summaries for dashboarding"
```

### Task 3: Add Store-Level Dashboard Summary Queries

**Status:** Completed on `main` in `d4acff2`.

What landed:
- `query_dashboard_summary(...)` in `science-tool/src/science_tool/graph/store.py`
- `science-tool graph dashboard-summary` in `science-tool/src/science_tool/cli.py`
- JSON and table output for claim summaries
- belief states, typed evidence composition, empirical-presence detection, and stable prioritization ordering

Follow-up focus:
- Keep this task closed unless the output contract itself changes.
- Put new implementation effort into neighborhood summaries and notebook consumption instead.

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add tests for a reusable summary query that returns:

- weakly supported claims
- contested claims
- single-source claims
- claims lacking empirical data evidence

Example:

```python
def test_graph_dashboard_summary_prioritizes_claims_without_empirical_support() -> None:
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "dashboard_summary or uncertainty"
```

Expected: FAIL because the CLI/store currently expose only partial uncertainty summaries.

**Step 3: Implement the reusable query path**

Add a store-level query, for example `query_dashboard_summary(...)`, and a CLI surface, for example `science-tool graph dashboard-summary`, that emits JSON/table data for the notebook and other tooling.

The query must compute:

- claim-level risk and evidence composition
- whether empirical data evidence is present
- whether support is single-source or contested
- a stable sort order for prioritization

**Step 4: Run the targeted tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k "dashboard_summary or uncertainty"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add reusable claim-centric dashboard summaries"
```

### Task 4: Add Neighborhood Uncertainty Prioritization

**Status:** Completed for the first claim-centered pass.

What landed:
- `query_neighborhood_summary(...)` in `science-tool/src/science_tool/graph/store.py`
- `science-tool graph neighborhood-summary` in `science-tool/src/science_tool/cli.py`
- neighborhood-level risk aggregation over local claim clusters
- separate structural fragility reporting via `structural_fragility`

Remaining refinement space:
- richer neighborhood diffusion
- stronger locality definitions beyond shared hypotheses and explicit claim links
- tighter integration with notebook/dashboard panels in Task 5

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add tests requiring:

- neighborhood risk to increase when nearby claims are weak, contested, or single-source
- structurally sparse but well-supported regions not to outrank highly contested regions automatically

Example:

```python
def test_graph_neighborhood_uncertainty_prioritizes_contested_local_clusters() -> None:
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k neighborhood
```

Expected: FAIL because neighborhood uncertainty is not yet an explicit dashboard output.

**Step 3: Implement the minimal diffusion pass**

Add a neighborhood summary query that:

- starts from claim-level risk
- diffuses risk over local graph neighborhoods
- preserves a distinction between structural fragility and evidential fragility
- emits a compact ranked list usable for dashboard prioritization

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k neighborhood
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add neighborhood uncertainty prioritization"
```

### Task 5: Rebuild The Marimo Dashboard Around Store Summaries

**Files:**
- Modify: `science-tool/src/science_tool/graph/viz_template.py`
- Modify: `knowledge/viz.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing notebook-content tests**

Add assertions that the generated notebook contains panels and helper text for:

- claims lacking empirical data evidence
- high-uncertainty neighborhoods
- evidence-type composition

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k viz_notebook
```

Expected: FAIL because the notebook does not yet expose those panels.

**Step 3: Rework the notebook**

Update the marimo template so it uses the store-level dashboard summary output instead of ad hoc raw triple parsing wherever practical.

At minimum, add panels for:

- weakly supported claims
- contested claims
- single-source claims
- claims lacking empirical data evidence
- high-uncertainty neighborhoods

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_graph_cli.py -q -k viz_notebook
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/viz_template.py knowledge/viz.py science-tool/tests/test_graph_cli.py
git commit -m "feat: rebuild dashboard around claim-centric summaries"
```

### Task 6: Add Canonical Migration Guides And A Shared Migration Checklist

**Status:** Completed.

**Files:**
- Create: `docs/migrations/seq-feats-claim-centric-uncertainty.md`
- Create: `docs/migrations/3d-attention-bias-claim-centric-uncertainty.md`
- Create: `docs/migrations/natural-systems-guide-claim-centric-uncertainty.md`
- Modify: `docs/kg-project-migration-guide.md`
- Test: none

**Step 1: Expand the shared migration guide**

Update `docs/kg-project-migration-guide.md` with a new section explaining:

- claim decomposition
- typed evidence migration
- authored-confidence demotion
- dashboard expectations after migration

**Step 2: Write the three project guides**

Each guide must include:

- current project shape
- why migration is needed
- which hypotheses/questions should be decomposed first
- where evidence should come from in that project
- a recommended migration order
- success checks and graph commands to run

**Step 3: Cross-check against actual project state**

Verify each guide references real files and structures in:

- `/home/keith/d/seq-feats`
- `/home/keith/d/3d-attention-bias`
- `/home/keith/d/mindful/natural-systems-guide`

**Step 4: Commit**

```bash
git add docs/migrations/seq-feats-claim-centric-uncertainty.md docs/migrations/3d-attention-bias-claim-centric-uncertainty.md docs/migrations/natural-systems-guide-claim-centric-uncertainty.md docs/kg-project-migration-guide.md
git commit -m "docs: add claim-centric migration guides"
```

### Task 7: Pilot One Project Migration End-To-End

**Status:** Completed for the first pilot project.

Pilot completed:
- `3d-attention-bias`

Outcome:
- high-value hypotheses were decomposed into claims
- typed evidence records now distinguish literature-only from empirically supported claims
- project-local graph validation passed after migration

**Files:**
- Modify: project files in exactly one pilot project
- Create: one migration report in that project
- Test: project-local graph audit/build/validate outputs

**Step 1: Choose the pilot**

Use `3d-attention-bias` first.

Reason:

- smaller hypothesis surface than `seq-feats`
- clearer experiment/result boundaries
- easier to classify literature vs empirical benchmark evidence

**Step 2: Write the failing migration checks**

In the pilot project, define expected checks such as:

- claim-backed support/dispute records exist for H01/H02
- benchmark results are represented as empirical data evidence rather than only prose
- dashboard summary shows which claims lack empirical support

**Step 3: Migrate the pilot project minimally**

Convert only the highest-value claims and evidence first. Do not try to migrate every note and interpretation in one pass.

**Step 4: Run the project-local verification**

Run the project’s standard graph audit/build/validate commands and capture the outputs in a migration report.

**Step 5: Commit**

Commit in the pilot project repo, not in `science`.

### Task 8: Fold The Migration Lessons Back Into Shared Guidance

**Files:**
- Modify: `README.md`
- Modify: `skills/research/SKILL.md`
- Modify: `commands/status.md`
- Modify: `commands/interpret-results.md`
- Test: none

**Step 1: Update user guidance**

Teach users:

- how to recognize unmigrated projects
- when to create relation claims instead of just updating hypothesis prose
- how to classify evidence as literature, empirical, simulation, benchmark, or expert judgment

**Step 2: Add the new dashboard expectations**

Make sure shared guidance tells users to look for:

- no empirical support
- contested claims
- fragile single-source claims
- uncertain neighborhoods worth investigating next

**Step 3: Commit**

```bash
git add README.md skills/research/SKILL.md commands/status.md commands/interpret-results.md
git commit -m "docs: teach dashboard-guided claim migration workflow"
```

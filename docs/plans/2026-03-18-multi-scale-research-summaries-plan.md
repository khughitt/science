# Multi-Scale Research Summaries Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add higher-level question, inquiry, and research-project reasoning summaries on top of the existing claim and neighborhood summary layer.

**Architecture:** Extend the claim-centric dashboard contract with three new summary units: `question_summary`, `inquiry_summary`, and a `research`-profile `project_summary`. Implement the semantics in `science_tool.graph.store`, expose them through new `graph` CLI commands, and update notebook and guidance surfaces to consume those store-owned summaries rather than reconstructing them ad hoc.

**Tech Stack:** Markdown docs, Python `science-tool`, `click`, `rdflib`, existing graph summary helpers, `pytest`, `ruff`.

---

## Scope And Constraints

- Treat `research` projects as the primary target for this phase.
- Keep `software`-profile support explicit but minimal.
- Reuse the existing `claim_summary` and `neighborhood_summary` semantics.
- Keep summary logic in the store, not in CLI formatting or notebook code.
- Do not introduce compatibility shims for older dashboard-local logic.

## Task 1: Lock The Higher-Level Summary Contract

**Files:**
- Modify: `docs/claim-centric-dashboard-contract.md`
- Modify: `docs/plans/2026-03-18-claim-centric-reasoning-roadmap.md`
- Modify: `docs/plans/2026-03-18-multi-scale-research-summaries-plan.md`

**Step 1: Extend the contract document with the new summary units**

Add sections for:

- `question_summary`
- `inquiry_summary`
- `project_summary`

Include:

- required fields
- interpretation rules
- first-pass profile constraints
- explicit distinction between rollup prioritization and claim-local belief state

**Step 2: Update the roadmap to point at this implementation plan**

Add a `See also` link to:

- `2026-03-18-multi-scale-research-summaries-plan.md`

Also make sure the roadmap’s near-term priorities and open questions remain consistent with the new plan.

**Step 3: Verify the contract language is internally consistent**

Run:

```bash
rg -n "question_summary|inquiry_summary|project_summary|profile-aware|research profile|software profile" docs/claim-centric-dashboard-contract.md docs/plans/2026-03-18-claim-centric-reasoning-roadmap.md
```

Expected:

- the new summary units are documented exactly once each as first-class contract sections
- the profile-aware constraints are explicit

**Step 4: Commit**

```bash
git add docs/claim-centric-dashboard-contract.md docs/plans/2026-03-18-claim-centric-reasoning-roadmap.md docs/plans/2026-03-18-multi-scale-research-summaries-plan.md
git commit -m "docs: define higher-level reasoning summary contract"
```

## Task 2: Add Shared Rollup Helpers In The Store

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_inquiry_cli.py`

**Step 1: Write the failing question-summary regression**

Add a focused CLI regression to `science-tool/tests/test_graph_cli.py` for a graph containing:

- one question
- two claims addressing that question
- one contested claim
- one claim lacking empirical support

**Step 2: Run the targeted test to verify it fails**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k question_summary_reports_rollup_metrics
```

Expected:

- FAIL because `graph question-summary` and its rollup logic do not exist yet

**Step 3: Write the failing inquiry-summary regression**

Add a regression to `science-tool/tests/test_inquiry_cli.py` for an inquiry with:

- explicit `sci:backedByClaim` references on inquiry edges
- one backed claim with empirical support
- one backed claim that is contested or single-source

**Step 4: Run the targeted inquiry test to verify it fails**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_inquiry_cli.py -q -k inquiry_summary_reports_claim_backing_and_priority
```

Expected:

- FAIL because `graph inquiry-summary` and its rollup logic do not exist yet

**Step 5: Implement reusable rollup helpers in `store.py`**

Add small, explicit helpers in `science-tool/src/science_tool/graph/store.py` such as:

- `_question_claims(...)`
- `_inquiry_claims(...)`
- `_question_summary_data(...)`
- `_inquiry_summary_data(...)`
- `_format_question_summary_row(...)`
- `_format_inquiry_summary_row(...)`

Implementation rules:

- derive higher-level rollups from existing claim/neighborhood summaries
- avoid a second, divergent evidence-scoring path
- use explicit graph predicates such as `sci:addresses`, `sci:target`, and `sci:backedByClaim`
- keep inquiry claim collection explicit; do not infer claim membership from loose proximity

**Step 6: Run the targeted tests to make them pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k question_summary_reports_rollup_metrics
uv run --frozen pytest science-tool/tests/test_inquiry_cli.py -q -k inquiry_summary_reports_claim_backing_and_priority
```

Expected:

- PASS

**Step 7: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_cli.py science-tool/tests/test_inquiry_cli.py
git commit -m "feat: add question and inquiry summary rollups"
```

## Task 3: Expose `graph question-summary` And `graph inquiry-summary`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/src/science_tool/output.py`
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_inquiry_cli.py`

**Step 1: Write CLI-format regressions**

Extend the Task 2 tests so they also verify:

- `--format table` includes the right columns
- `--top` limits output
- JSON output preserves the documented field names

**Step 2: Run the CLI-format regressions to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k "question_summary and table_headers"
uv run --frozen pytest science-tool/tests/test_inquiry_cli.py -q -k "inquiry_summary and table_headers"
```

Expected:

- FAIL because the commands are not wired into the CLI yet

**Step 3: Add the new CLI commands**

In `science-tool/src/science_tool/cli.py`:

- import the new store query functions
- add `graph question-summary`
- add `graph inquiry-summary`
- mirror the existing `dashboard-summary` / `neighborhood-summary` command style
- support `--format json|table` and `--top`

Use `emit_query_rows(...)` rather than hand-formatting tables.

**Step 4: Run the targeted CLI tests to make them pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k question_summary
uv run --frozen pytest science-tool/tests/test_inquiry_cli.py -q -k inquiry_summary
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/src/science_tool/output.py science-tool/tests/test_graph_cli.py science-tool/tests/test_inquiry_cli.py
git commit -m "feat: add question and inquiry summary commands"
```

## Task 4: Add A `research`-Profile `graph project-summary`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/src/science_tool/paths.py`
- Test: `science-tool/tests/test_graph_cli.py`
- Test: `science-tool/tests/test_paths.py`

**Step 1: Write the failing research-profile project-summary regression**

Add a regression in `science-tool/tests/test_graph_cli.py` that writes `science.yaml` with `profile: research`, creates a graph with questions, inquiries, and claims, and asserts that `graph project-summary --format json` returns the documented rollup fields.

**Step 2: Write the failing unsupported-profile regression**

Add a regression in `science-tool/tests/test_paths.py` or `science-tool/tests/test_graph_cli.py` that sets `profile: software` and asserts `graph project-summary` exits non-zero with a clear message.

**Step 3: Run the targeted regressions to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k project_summary
uv run --frozen pytest science-tool/tests/test_paths.py -q -k project_summary
```

Expected:

- FAIL because the rollup and profile gate do not exist yet

**Step 4: Implement `query_project_summary(...)`**

In `science-tool/src/science_tool/graph/store.py`:

- resolve project profile from `science.yaml` using `resolve_paths(...)`
- for `research` projects, roll up question summaries, inquiry summaries, claim summaries, and neighborhood summaries
- compute counts, average risk, high-risk neighborhood count, and aggregate priority score

**Step 5: Add `graph project-summary`**

In `science-tool/src/science_tool/cli.py`:

- add `graph project-summary`
- support `--format json|table`
- use the same output conventions as other summary commands

**Step 6: Run the targeted tests to make them pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k project_summary
uv run --frozen pytest science-tool/tests/test_paths.py -q -k project_summary
```

Expected:

- PASS

**Step 7: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/src/science_tool/paths.py science-tool/tests/test_graph_cli.py science-tool/tests/test_paths.py
git commit -m "feat: add research project summary"
```

## Task 5: Rebuild Knowledge And Guidance Surfaces Around Higher-Level Summaries

**Files:**
- Modify: `science-tool/src/science_tool/graph/viz_template.py`
- Modify: `knowledge/viz.py`
- Modify: `commands/status.md`
- Modify: `commands/interpret-results.md`
- Modify: `README.md`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing notebook/guidance regressions**

Add regressions that verify the generated notebook imports and calls the new summary queries and that `graph init` still copies a notebook that references store-owned summary functions rather than local triple scans.

**Step 2: Run the targeted regressions to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k "viz_notebook and summary"
```

Expected:

- FAIL because the notebook does not yet import or render the higher-level summaries

**Step 3: Update the notebook template and tracked notebook**

In `science-tool/src/science_tool/graph/viz_template.py` and `knowledge/viz.py`:

- add question/inquiry/project summary queries
- add panels or sections for high-priority questions, high-priority inquiries, and research project summary
- keep the notebook a thin rendering layer over store summaries

**Step 4: Update shared guidance**

In `commands/status.md`, `commands/interpret-results.md`, and `README.md`, teach the higher-level workflow.

**Step 5: Run the targeted notebook/guidance tests to make them pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py -q -k "viz_notebook or graph_init_copies_viz_notebook"
```

Expected:

- PASS

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/viz_template.py knowledge/viz.py commands/status.md commands/interpret-results.md README.md science-tool/tests/test_graph_cli.py
git commit -m "docs: teach higher-level reasoning summaries"
```

## Task 6: Full Verification And Follow-On Decisions

**Files:**
- Modify: `docs/plans/2026-03-18-claim-centric-reasoning-roadmap.md`
- Modify: `docs/claim-centric-dashboard-contract.md`

**Step 1: Run the focused regression suite**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py science-tool/tests/test_inquiry_cli.py science-tool/tests/test_paths.py -q
```

**Step 2: Run the broader graph/inquiry regression suite**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_materialize.py science-tool/tests/test_inquiry.py science-tool/tests/test_causal_cli.py science-tool/tests/test_causal.py -q
```

**Step 3: Run formatting and lint checks**

Run:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

**Step 4: Refresh roadmap and contract status**

Update the roadmap and contract to record which Phase 5 deliverables are now implemented.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-18-claim-centric-reasoning-roadmap.md docs/claim-centric-dashboard-contract.md
git commit -m "docs: refresh roadmap after multi-scale summaries"
```

## Out Of Scope For This Plan

- full `software`-profile reasoning overlays
- automatic task creation from summaries
- fully structured study/result authoring
- decision-theoretic next-step or expected-information-gain outputs
- probabilistic graph updates beyond the current skeptical summary layer

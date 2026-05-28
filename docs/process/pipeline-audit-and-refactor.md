# Pipeline Audit & Refactor — a three-axis playbook

This playbook gives science projects a repeatable method to **audit and refactor their data
pipelines along three axes**, in a single pass per data source:

1. **Data QA** — every table analysis consumes has a wired-in QA/sanity step (per
   [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md)).
2. **Consistency, organization, code quality / reuse.**
3. **Data portability** — reusable "base" ingestion+cleaning is disentangled from project-specific
   processing, and clean base datasets are promoted to the shared commons.

## The organizing insight — the "clean base table" boundary

Do not treat the three axes as three independent checklists. They **converge on one boundary in
every pipeline: the clean base table** — the dataset after ingestion and source-level cleaning,
carrying good metadata, but *before* any project-specific processing.

That single boundary is at once three things:

- the **substrate axis 1 must validate** — a QA step reads the clean base table;
- the **seam axis 2 wants factored** out of project-specific code — a reusable ingestion module;
- the **unit axis 3 promotes** to the commons — a clean dataset plus its `datapackage.json`.

So the core move for every data source is **isolate → QA → promote the clean base table**. Force
that boundary into the open for each source, and one structural refactor — making the boundary
explicit — pays off on all three axes at once.

**Scope caveat for axis 1 — load-bearing.** The clean base table is *one* QA substrate, not the
only one. The data-QA convention validates **every table analysis actually consumes**, and the
clean base table sits *before* project-specific processing — so QA at that boundary cannot see
defects introduced by downstream project-specific transformations. Clean-base QA therefore **does
not satisfy** final-analysis-table QA. Require a QA step on the clean base table **and** on each
project-specific analysis table produced after it that feeds models or statistics (one QA step per
substrate, per the convention). The "one boundary" framing above is about the *refactor move* that
serves all three axes; it is not a claim that one QA step covers the whole pipeline.

## Artifact placement — upstream vs downstream

Split the artifacts deliberately so project-specific audit reports never leak into the shared
`science` codebase.

- **Upstream (this `science` repo, reusable and project-agnostic):** this playbook itself and its
  embedded report skeletons (fenced copy-paste blocks, not separate template files — keep the
  methodology in one self-contained doc).
- **Downstream (the target project, per-project instances):** the filled-in **inventory**, per-chain
  **findings**, **synthesis/backlog**, and the resulting **refactor tasks** live in the project's
  existing audits area, under a `pipeline-refactor/` subdir (e.g. mm30 uses `doc/audits/` →
  `doc/audits/pipeline-refactor/`). Follow the project's own `doc/` vs `docs/` convention; do not
  introduce a new top-level dir.

Because these instances live *inside* a single project repo, the central framework's
per-project naming qualifier is unneeded: filenames collapse to `inventory.{md,json}`, `findings.md`,
and `synthesis.md`. Preserve the three-part shape; drop the per-project qualifier.

Two things still flow upstream from an audit run — and neither is an audit *report*:

- **Convention nominations:** a project-grown QA check judged broadly useful becomes a normal doc PR
  to `science/docs/conventions/`.
- **Commons promotions:** promotion writes the clean dataset into the shared store, and cross-project
  reuse is realized through the **commons registry itself** (see the axis-3 procedure), so no central
  cross-project synthesis document is needed.

## Method

The unit of work is the **data-source chain**:
`external source → ingest → clean/normalize → clean base table → project-specific downstream`.
Each chain is swept on all three axes in one pass.

**Phase 0 — Inventory.** Enumerate the project's data-source chains. For each, capture the source,
the ingest/clean rules, the clean base table output, its config, and the project-specific downstream
that consumes it. Produce `pipeline-refactor/inventory.{md,json}`.

**Phase 1 — Per-chain sweep (all three axes together).** Walk each chain once and score the three
axis rubrics. Record findings in `pipeline-refactor/findings.md`, one section per chain, and attach a
disposition to every finding — fix-now / backlog / promote / flagged-optional / leave.

**Phase 2 — Synthesis & backlog.** Roll the findings into `pipeline-refactor/synthesis.md`: a
prioritized refactor backlog, recurring code anti-patterns, and a dedicated **"convention
nominations"** subsection listing project-grown QA checks worth promoting upstream. Triage the
backlog into tasks in the project's task system.

**Phase 3 — Execute & guard.** Run refactors through the normal task lifecycle with TDD. Land axis-1
fixes as **structural** QA checks that regression-guard the defect (per the convention). Run axis-3
promotions through the multi-step procedure in the axis-3 rubric (create/verify the dataset entity →
dry-run → `--apply`), not a single command.

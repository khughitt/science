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

## The three axis rubrics

Each axis scores PASS / WARN / FAIL per sub-dimension; attach a disposition to every finding.

### Axis 1 — Data QA

- A **wired-in** data-QA step (own pipeline rule on the default target) for **every table analysis
  consumes**: the clean base table **and** each project-specific analysis table produced downstream.
  Clean-base QA does **not** satisfy final-analysis-table QA (see the scope caveat above). One QA step per
  substrate, per [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md).
- Each QA step splits **structural** (build-fatal) vs **distribution** (surfaced-not-fatal) flags.
- Bounds / allowed-codes / sentinels are **config-driven** and shared with the cleaning step.
- **Existing post-hoc checks:** which manual / pytest-only QA scripts should become wired-in
  structural checks on a built table?
- **Companion DAG-validation check (NOT table-QA):** is each pipeline output produced by exactly one
  rule, with no orphaned/duplicately-owned outputs? This is a **workflow/DAG-level** structural
  checkpoint scored alongside data-QA but explicitly *outside* the table-QA convention (it inspects
  the rule graph, not a table). See "Deferred disciplines" below.

Rubric reuses the `review-pipeline` → **QA Coverage** dimension (incl. its severity-split row), plus
the DAG-validation check as its own line. Disposition: a missing structural check on an
already-fixed bug → **fix-now** (regression-guard); missing distribution checks → **backlog**.

### Axis 2 — Consistency, organization, code quality / reuse

- **Naming & layout** consistency across chains (e.g. `workflows/` vs `scripts/` vs an unused
  `code/`; config sprawl; versioned-config drift like `v8` / `v8.1`).
- **Config-driven over hardcoded:** flag scripts bypassing config with hardcoded data paths.
- **Duplication → shared helpers:** repeated datapackage boilerplate, effect-size/association logic,
  decode logic wanting a shared module.
- **Code → task back-links** per [`../conventions/code-task-backlinks.md`](../conventions/code-task-backlinks.md).

Disposition: extract helper / consolidate config / add back-links → **backlog** (mechanical,
TDD-guarded). **Package consolidation** (flat `scripts/` + `sys.path` hacks → an installable
package) is an **optional flagged finding**, never a default recommendation.

### Axis 3 — Data portability / commons

Per source: is the **base ingestion + cleaning** (clean state + good metadata, no project-specific
processing) **disentangled** from downstream?

- Entangled → refactor task to **split the chain at the clean-base-table boundary** (the same
  boundary axis 1 QAs — do them together).
- Cleanly factored → is the clean base dataset (with `datapackage.json`) **promoted to the commons**?

Rubric: **PASS** (base separated *and* promoted) / **WARN** (separated, not promoted — includes "no
dataset entity yet") / **FAIL** (entangled).

**Promotion procedure (not a one-liner).** `science commons promote dataset` sources from the
project's dataset entity descriptors (`doc/datasets/data-<slug>.md`), requires `--slug`, and selects
the source project with `--from <project-id>`. So promotion has prerequisites that are themselves
refactor tasks:

1. **Create / verify the dataset entity** at `doc/datasets/data-<slug>.md` with the required
   `mixin-dataset-1.0` fields and a `datapackage:` pointer to the clean base table's `datapackage.json`.
2. **Dry-run** `science commons promote dataset --from <project-id> --slug <slug>` and inspect the plan.
3. **Apply** with `--apply` (add `--mixin <bio.*>` where a bio extension matches the dataset modality).

## Deferred disciplines (named, not specified here)

This playbook **names** two related disciplines and **nominates** each as a future convention, but
does not specify them:

- **Analysis / result-QA** — validates *results*, not the input table: leave-one-out /
  dataset-dropout stability; permutation / empirical-null calibration and assumption sweeps.
- **Workflow / DAG-validation** — validates the *rule graph*, not a table: output-ownership / dedup
  (each output produced by exactly one rule). Deliberately kept out of the table-QA convention,
  whose contract is "one script + one rule reads the built table" and which cannot see DAG structure.

Surface both during the sweep so they are not forgotten; writing either convention is a separate
decision recorded in the synthesis "convention nominations".

## Report skeletons (copy into the target project)

Copy these into the project's audits area (`<doc-or-docs>/audits/pipeline-refactor/`).

### `inventory.md` — one row per data-source chain

````markdown
# Pipeline inventory — <project>

| Chain | Source | Ingest rule(s) | Clean base table | Base config | Project-specific downstream |
| --- | --- | --- | --- | --- | --- |
| <name> | <external source> | <rule(s)> | <path to clean table> | <config key/file> | <consumers> |
````

A machine-readable `inventory.json` mirrors the table: a list of objects with keys
`chain, source, ingest_rules[], clean_base_table, base_config, downstream[]`.

### `findings.md` — one section per chain

````markdown
# Pipeline audit findings — <project>

## Chain: <name>

- **Axis 1 — Data QA:** PASS / WARN / FAIL — <notes>
  - substrates with a wired-in QA step: clean base [y/n]; <downstream tables…> [y/n]
  - companion DAG-validation (output-ownership): PASS / WARN / FAIL
- **Axis 2 — Consistency/quality:** PASS / WARN / FAIL — <notes>
- **Axis 3 — Portability/commons:** PASS / WARN / FAIL — base separated [y/n]; promoted [y/n]

### Findings
| # | Axis | Finding | Severity | Disposition | Task |
| --- | --- | --- | --- | --- | --- |
| 1 | 1/2/3 | <what> | structural / distribution / quality | fix-now / backlog / promote / flagged-optional / leave | <task-id> |
````

### `synthesis.md` — roll-up across chains

````markdown
# Pipeline audit synthesis — <project>

## Prioritized refactor backlog
| Rank | Axis | Item | Chains affected | Effort | Task |
| --- | --- | --- | --- | --- | --- |

## Recurring anti-patterns
- <pattern> — <chains where it recurs>

## Convention nominations (upstream candidates)
| Candidate check | Kind (data-QA / analysis-result-QA / workflow-DAG) | Evidence (chains / bugs caught) | Proposed home |
| --- | --- | --- | --- |

## Commons promotion candidates
| Dataset | Entity exists? | Promoted? | Blocking prerequisites |
| --- | --- | --- | --- |
````

## See also

- [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md) — the
  axis-1 (data-QA) convention this playbook audits against.
- [`../conventions/code-task-backlinks.md`](../conventions/code-task-backlinks.md) — axis-2 code→task
  back-link patterns.
- [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
  — `plan-pipeline` / `review-pipeline` QA sections.
- `science commons promote dataset` (`science/src/science_tool/commons/promote.py`) — the axis-3 endpoint.
- [`../plans/2026-05-28-pipeline-audit-and-refactor-design.md`](../plans/2026-05-28-pipeline-audit-and-refactor-design.md)
  — the design this playbook implements.

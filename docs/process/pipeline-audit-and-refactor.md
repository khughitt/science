# Pipeline Audit & Refactor — a three-axis playbook

This playbook gives science projects a repeatable method to **audit and refactor their
computational data workflows along three axes**, in a single pass per source chain:

1. **Data QA** — every substrate analysis consumes has a wired-in QA/sanity step (per
   [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md)).
2. **Consistency, organization, code quality / reuse.**
3. **Data portability** — reusable "base" ingestion+cleaning is disentangled from project-specific
   processing, and clean base substrates are promoted to the shared commons when appropriate.

## The organizing insight — the "clean base substrate" boundary

Do not treat the three axes as three independent checklists. They **converge on one boundary in
every pipeline: the clean base substrate** — the reusable artifact after ingestion and source-level
cleaning, carrying good metadata, but *before* any project-specific processing.

The substrate may be a table, but it may also be a record stream, graph, corpus, model-result bundle,
manifest, or package:

| Substrate kind | Examples | Typical clean-base QA |
| --- | --- | --- |
| Table | CSV, TSV, Feather, Parquet | schema, required columns, bounds, sentinels, duplicate keys |
| Record stream | JSONL, NDJSON | parseability, required fields, duplicate record IDs, enum coverage |
| Graph | RDF/TriG, graph JSON, edge list | parseability, dangling refs, edge-shape checks, reachability/orphan checks |
| Corpus | PDFs, TeX source trees, markdown source docs | source-yield, file integrity, extraction coverage, inaccessible-source accounting |
| Result bundle | fit estimates, predictions, score artifacts | schema, numeric-domain checks, split/leakage checks, status consistency |
| Manifest/package | datapackage, research package, KG source bundle | resource existence, hashes, provenance, entity cross-references |

That single boundary is at once three things:

- the **substrate axis 1 must validate** — a QA step reads the clean base substrate;
- the **seam axis 2 wants factored** out of project-specific code — a reusable ingestion module;
- the **unit axis 3 promotes** to the commons — a clean dataset/substrate plus its manifest.

So the core move for every data source is **isolate → QA → promote the clean base substrate**. Force
that boundary into the open for each source, and one structural refactor — making the substrate
explicit — pays off on all three axes at once.

**Scope caveat for axis 1 — load-bearing.** The clean base substrate is *one* QA substrate, not the
only one. The existing data-QA convention is table-centered, but this playbook generalizes the same
principle to every consumed substrate. The clean base substrate sits *before* project-specific
processing, so QA at that boundary cannot see defects introduced by downstream project-specific
transformations. Clean-base QA therefore **does not satisfy** final-analysis-substrate or final-result
QA. Require a QA step on the clean base substrate **and** on each project-specific analysis substrate
produced after it that feeds models, statistics, or interpretation (one QA step per substrate, per
the convention's intent). The "one boundary" framing above is about the *refactor move* that serves
all three axes; it is not a claim that one QA step covers the whole pipeline.

**Consumer-contract caveat — also load-bearing.** A substrate can pass its own QA and still break the
next stage. During the sweep, also check the **consumer contract** at every important handoff:
does the producer's output schema, dimensions, key space, status vocabulary, and freshness match what
the consuming script, model, report, or UI actually reads?
This is the pipeline-audit version of the `review-pipeline` integration-boundary dimension.

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

The unit of work is the **source-substrate chain**:
`external/internal source → ingest → clean/normalize → clean base substrate → project-specific downstream`.
Each chain is swept on all three axes in one pass.

**Phase 0 — Inventory.** Enumerate the project's source-substrate chains. For each, capture the source,
the substrate kind, the ingest/clean rules, the clean base substrate output, its config, and the
project-specific downstream that consumes it. Produce `pipeline-refactor/inventory.{md,json}`.

Use an explicit discovery pass before hand-curating the inventory:

- workflow definitions: `Snakefile`, `*.smk`, CI workflows, notebooks, task runners;
- command surfaces: `package.json`, `pyproject.toml`, `Makefile`, `justfile`, project CLIs;
- generated substrates: `data/processed/`, `pipeline/`, `results/`, `reports/`, `knowledge/sources/`;
- manifests and packages: `datapackage.json`, research packages, lockfiles, provenance manifests;
- QA and validation: test files, audit scripts, health checks, schema validators;
- dataset entities: `doc/datasets/data-*.md`, KG dataset records, commons registrations.

**Phase 1 — Per-chain sweep (all three axes together).** Walk each chain once and score the three
axis rubrics. Record findings in `pipeline-refactor/findings.md`, one section per chain, and attach a
disposition to every finding — fix-now / backlog / promote / flagged-optional / leave.
For each chain, explicitly record both substrate QA and consumer-contract QA.

**Phase 2 — Synthesis & backlog.** Roll the findings into `pipeline-refactor/synthesis.md`: a
prioritized refactor backlog, recurring code anti-patterns, and a dedicated **"convention
nominations"** subsection listing project-grown QA checks worth promoting upstream. Triage the
backlog into tasks in the project's task system. The audit is not finished until each non-`leave`
finding has either a task ID or an explicit `defer-no-task` rationale.

**Phase 3 — Execute & guard.** Run refactors through the normal task lifecycle with TDD. Land axis-1
fixes as **structural** QA checks that regression-guard the defect (per the convention). Run axis-3
promotions through the multi-step procedure in the axis-3 rubric (create/verify the dataset entity →
dry-run → `--apply`), not a single command.

**Risk ordering.** Start execution where the clean-base substrate is already explicit, the downstream
blast radius is small, and the QA can be made structural quickly. Defer large entangled chains until a
smaller slice has established the local QA and manifest pattern.

## The three axis rubrics

Each axis scores PASS / WARN / FAIL per sub-dimension; attach a disposition to every finding.

### Axis 1 — Data QA

- A **wired-in** data-QA step (own pipeline rule on the default target) for **every substrate analysis
  consumes**: the clean base substrate **and** each project-specific analysis substrate produced downstream.
  Clean-base QA does **not** satisfy final-analysis-substrate QA (see the scope caveat above). One QA step
  per substrate, per [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md).
- Each QA step splits **structural** (build-fatal) vs **distribution** (surfaced-not-fatal) flags.
- Bounds / allowed-codes / sentinels are **config-driven** and shared with the cleaning step.
- **Existing post-hoc checks:** which manual / pytest-only QA scripts should become wired-in
  structural checks on a built substrate?
- **Consumer-contract QA:** does each consumed output match the next stage's expected schema, dimensions,
  key namespace, status values, and freshness assumptions?
- **Companion DAG-validation check (NOT substrate-QA):** is each pipeline output produced by exactly one
  rule, included in a default target when appropriate, and free of orphaned/duplicately-owned outputs?
  This is a **workflow/DAG-level** structural checkpoint scored alongside data-QA but explicitly *outside*
  the table-QA convention (it inspects the rule graph, not a table).

Use modality-specific checks when the substrate is not a table:

- **JSON/JSONL:** parseability, required fields, duplicate record IDs, enum coverage, null policy.
- **Graphs:** parser validity, unresolved refs, orphan nodes, edge-shape constraints, reachability.
- **Corpora:** source-yield, extraction-yield, checksums, inaccessible-source accounting.
- **Fit/prediction/score bundles:** numeric domains, split disjointness, leakage checks, prediction
  coverage, status/readiness consistency.
- **Manifests/packages:** resource existence, hashes, provenance, declared entity links.

Rubric reuses the `review-pipeline` → **QA Coverage** dimension (incl. its severity-split row), plus
the DAG-validation check as its own line. Disposition: a missing structural check on an
already-fixed bug → **fix-now** (regression-guard); missing distribution checks → **backlog**.
Result-QA findings are recorded here as **analysis-result-QA**, but they do not substitute for data-QA.

### Axis 2 — Consistency, organization, code quality / reuse

- **Minimum workflow contract:** each active workflow should have a root-runnable command, declared
  config, explicit default target, QA target, manifest/datapackage when outputs feed later analyses,
  and task/code back-links.
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

- Entangled → refactor task to **split the chain at the clean-base-substrate boundary** (the same
  boundary axis 1 QAs — do them together).
- Cleanly factored → is the clean base dataset (with `datapackage.json`) **promoted to the commons**?

Rubric: **PASS** (base separated *and* promoted) / **WARN** (separated, not promoted — includes "no
dataset entity yet") / **FAIL** (entangled).

**Commons-readiness gate.** Do not jump from "datapackage exists" to "promote".
A clean base substrate is commons-ready only when:

- the local runtime file stages and passes structural QA;
- a dataset entity exists with access verification or an explicit exception;
- the manifest lists all resources with hashes/provenance;
- downstream project-specific outputs are excluded from the base dataset;
- license/access restrictions are recorded.

**Promotion procedure (not a one-liner).** `science commons promote dataset` sources from the
project's dataset entity descriptors (`doc/datasets/data-<slug>.md`), requires `--slug`, and selects
the source project with `--from <project-id>`. So promotion has prerequisites that are themselves
refactor tasks:

1. **Create / verify the dataset entity** at `doc/datasets/data-<slug>.md` with the required
   `mixin-dataset-1.0` fields and a `datapackage:` pointer to the clean base substrate's
   `datapackage.json`.
2. **Dry-run** `science commons promote dataset --from <project-id> --slug <slug>` and inspect the plan.
3. **Apply** with `--apply` (add `--mixin <bio.*>` where a bio extension matches the dataset modality).

## Related QA disciplines

This playbook scores two related disciplines during the sweep, but keeps them distinct from data-QA:

- **Analysis / result-QA** — validates *results*, not the input table: leave-one-out /
  dataset-dropout stability; permutation / empirical-null calibration and assumption sweeps.
- **Workflow / DAG-validation** — validates the *rule graph*, not a table: output-ownership / dedup
  (each output produced by exactly one rule). Deliberately kept out of the table-QA convention,
  whose contract is "one script + one rule reads the built table" and which cannot see DAG structure.

Surface both during the sweep so they are not forgotten.
If a project-grown check becomes broadly reusable, record it in the synthesis "convention nominations".

## Report skeletons (copy into the target project)

Copy these into the project's audits area (`<doc-or-docs>/audits/pipeline-refactor/`).

### `inventory.md` — one row per source-substrate chain

````markdown
# Pipeline inventory — <project>

| Chain | Source | Substrate kind | Ingest rule(s) | Clean base substrate | Base config | Project-specific downstream |
| --- | --- | --- | --- | --- | --- | --- |
| <name> | <external source> | <table/jsonl/graph/corpus/result/manifest> | <rule(s)> | <path to clean substrate> | <config key/file> | <consumers> |
````

A machine-readable `inventory.json` mirrors the table: a list of objects with keys
`chain, source, substrate_kind, ingest_rules[], clean_base_substrate, base_config, downstream[]`.

### `findings.md` — one section per chain

````markdown
# Pipeline audit findings — <project>

## Chain: <name>

- **Axis 1 — Data QA:** PASS / WARN / FAIL — <notes>
  - substrates with a wired-in QA step: clean base [y/n]; <downstream substrates…> [y/n]
  - consumer-contract QA: PASS / WARN / FAIL
  - companion DAG-validation (output-ownership): PASS / WARN / FAIL
- **Axis 2 — Consistency/quality:** PASS / WARN / FAIL — <notes>
- **Axis 3 — Portability/commons:** PASS / WARN / FAIL — base separated [y/n]; promoted [y/n]

### Findings
| # | Axis | Finding | Severity | Disposition | Task |
| --- | --- | --- | --- | --- | --- |
| 1 | 1/2/3 | <what> | structural / distribution / consumer-contract / result-QA / quality | fix-now / backlog / promote / flagged-optional / leave | <task-id or defer-no-task:rationale> |
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

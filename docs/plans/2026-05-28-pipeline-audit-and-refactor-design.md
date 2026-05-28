# Pipeline Audit & Refactor — three-axis playbook (design)

Date: 2026-05-28

Status: design for review

Related (builds on / connects to):
- `docs/conventions/pipeline-qa-checkpoints.md` — the data-QA convention axis 1 audits against (this design also expands it; see §7)
- `aspects/computational-analysis/computational-analysis.md` — `plan-pipeline` (QA Checkpoints) and `review-pipeline` (QA Coverage) sections; axis 1 reuses the QA Coverage rubric
- `docs/conventions/code-task-backlinks.md` — axis 2 checks code→task back-links against this
- `docs/audits/downstream-project-conventions/_report-template.md` — the proven `inventory → projects → synthesis` audit shape this playbook mirrors
- `science/src/science_tool/commons/promote.py` — `science commons promote dataset`, the axis-3 endpoint
- `docs/process/adding-a-domain.md` — sibling process doc; the playbook lives alongside it

---

## 1. Purpose

Give science projects a repeatable method to **audit and refactor their data pipelines along
three axes**, in a single pass per data source:

1. **Data QA** — every processed analysis table has a wired-in QA/sanity step that catches data
   and metadata defects early (per `pipeline-qa-checkpoints.md`).
2. **Consistency, organization, code quality / reuse** — naming/layout consistency, config-driven
   over hardcoded, duplicated logic extracted to shared helpers.
3. **Data portability** — the reusable "base" ingestion+cleaning for each external source is
   disentangled from project-specific processing, and clean base datasets are promoted to the
   shared commons so other projects need not reprocess them.

The deliverable of the work this design specifies is a **project-agnostic playbook** plus a small
expansion of the data-QA convention. Applying the playbook to a first project (multiple-myeloma /
mm30) is a separate, later effort.

## 2. The organizing insight — the "clean base table" boundary

The three axes are not independent checklists; they **converge on one boundary in every pipeline:
the clean base table** — the dataset after ingestion and source-level cleaning, carrying good
metadata, but *before* any project-specific processing.

That single boundary is simultaneously:

- a **substrate axis 1** must validate (a QA step reads the clean base table);
- the **seam axis 2** wants factored out of project-specific code (a reusable ingestion module);
- the **unit axis 3** promotes to the commons (a clean dataset + `datapackage.json`).

**Important scope caveat for axis 1.** The clean base table is *one* QA substrate, not the only
one. The data-QA convention validates **every table analysis actually consumes**, and a clean base
table sits *before* project-specific processing — so QA at that boundary cannot see defects
introduced by downstream project-specific transformations. Clean-base QA therefore **does not
satisfy** final-analysis-table QA. Axis 1 requires a QA step on the clean base table **and** on each
project-specific analysis table produced after it that feeds models or statistics (one QA step per
substrate, per the convention). The "one boundary" framing below is about the *refactor move* that
serves all three axes; it is not a claim that one QA step covers the whole pipeline.

So the playbook's core move per source is **isolate → QA → promote the clean base table**, and one
structural refactor — making that boundary explicit — pays off on all three axes at once. The
playbook is built around forcing that boundary into the open for every data source.

## 3. Artifact placement — upstream vs downstream

The split is deliberate and removes any risk of project-specific audit reports leaking into the
shared `science` codebase.

**Upstream (this `science` repo) — reusable, project-agnostic:**
- `docs/process/pipeline-audit-and-refactor.md` — the playbook (the "how").
- The **report skeletons are embedded inside the playbook** as fenced copy-paste blocks (same
  house style as `pipeline-qa-checkpoints.md`), not shipped as separate template files — keeps the
  methodology one self-contained doc.
- The expansion of `docs/conventions/pipeline-qa-checkpoints.md` (§7).

**Downstream (the target project) — per-project instances:**
- The filled-in **inventory**, per-chain **findings**, **synthesis/backlog**, and the resulting
  **refactor tasks** live in the project's existing audits area, under a `pipeline-refactor/`
  subdir (e.g. mm30 uses `doc/audits/` → `doc/audits/pipeline-refactor/`). Follow the project's own
  `doc/` vs `docs/` convention; do not introduce a new top-level dir.
- Because these instances live *inside* the project repo, the central framework's
  `inventory/<proj>.md` + `projects/<proj>.md` naming (which exists to hold many projects in one
  place) collapses to project-local filenames: `inventory.{md,json}`, `findings.md`,
  `synthesis.md`. The three-part **shape** is preserved; the per-project filename qualifier is not
  needed.

**The two things that still flow upstream from an audit run** (neither is an audit *report*):
- **Convention nominations** (Phase 2): a project-grown QA check judged broadly useful becomes a
  normal doc PR to `science/docs/conventions/`.
- **Commons promotions** (axis 3): promotion writes the clean dataset into the shared store;
  cross-project reuse is realized through the **commons registry itself**, so no central
  cross-project synthesis document is needed. Promotion is **not a one-liner** — it has real
  prerequisites; see the axis-3 procedure in §5.

## 4. Unit of work and method

The unit is the **data-source chain**: `external source → ingest → clean/normalize → clean base
table → project-specific downstream`. Each chain is swept on all three axes in one pass.

**Phase 0 — Inventory.** Enumerate the project's data-source chains: for each, the source, the
ingest/clean rules, the clean base table output, its config, and the project-specific downstream
that consumes it. Produces `pipeline-refactor/inventory.{md,json}`.

**Phase 1 — Per-chain sweep (all three axes together).** Walk each chain once and score the three
axis rubrics (§5). Record findings + a disposition per finding (fix-now / backlog / promote /
flagged-optional / leave) in `pipeline-refactor/findings.md`, one section per chain.

**Phase 2 — Synthesis & backlog.** Roll findings into `pipeline-refactor/synthesis.md`:
prioritized refactor backlog, recurring code anti-patterns, and a dedicated **"convention
nominations"** subsection (mirroring the existing audit's §10 "Candidate Upstream Changes") listing
project-grown QA checks worth promoting upstream. Triage the backlog into tasks in the project's
task system.

**Phase 3 — Execute & guard.** Refactors run through the normal task lifecycle (TDD). Axis-1 fixes
land as **structural** QA checks that regression-guard the defect (per the convention). Axis-3
promotions follow the multi-step procedure in §5 (create/verify the dataset entity → dry-run →
`--apply`), not a single command.

## 5. The three axis rubrics

Each axis scores PASS / WARN / FAIL per sub-dimension, with a disposition attached to each finding.

### Axis 1 — Data QA

- Does **every table analysis consumes** have a **wired-in** data-QA step (own pipeline rule on the
  default target), per `pipeline-qa-checkpoints.md`? This means the clean base table **and** each
  project-specific analysis table produced downstream from it — clean-base QA does not satisfy
  final-table QA (see §2). One QA step per substrate.
- Does each QA step split **structural** (build-fatal) vs **distribution** (surfaced-not-fatal)
  flags?
- Are bounds/allowed-codes/sentinels **config-driven** and shared with the cleaning step (no drift)?
- **Existing post-hoc checks:** which of the project's manual / pytest-only QA scripts should be
  promoted to wired-in structural checks on the clean table?
- **Companion DAG-validation check (not table-QA):** is each pipeline output produced by exactly one
  rule, with no orphaned or duplicately-owned outputs? This is a **workflow/DAG-level** structural
  checkpoint, scored alongside data-QA but explicitly *outside* the table-QA convention (see §7) —
  it inspects the rule graph, not a table.

Rubric reuses the `review-pipeline` → **QA Coverage** dimension, including its severity-split row,
plus the DAG-validation check above as its own line. Disposition: a missing structural check on an
already-fixed bug → **fix-now** (regression-guard); missing distribution checks → **backlog**.

### Axis 2 — Consistency, organization, code quality / reuse

- **Naming & layout** consistency across chains (e.g. `workflows/` vs `scripts/` vs an unused
  `code/`; config sprawl; versioned-config drift like `v8` / `v8.1`).
- **Config-driven over hardcoded:** flag scripts that bypass config with hardcoded data paths.
- **Duplication → shared helpers:** repeated datapackage boilerplate, effect-size/association logic,
  decode logic that wants a shared module.
- **Code → task back-links** per `code-task-backlinks.md`.

Disposition: extract shared helper / consolidate config / add back-links → **backlog** (mechanical,
TDD-guarded). **Package consolidation** (flat `scripts/` + `sys.path` hacks → an installable
package) is recorded as an **optional flagged finding**, not a default recommendation — it is a
large, opinionated refactor a project opts into deliberately.

### Axis 3 — Data portability / commons

- Per source: is the **base ingestion + cleaning** (clean state + good metadata, *no*
  project-specific processing) **disentangled** from downstream?
  - Entangled → refactor task to **split the chain at the clean-base-table boundary** (the same
    boundary axis 1 QAs — do them together).
  - Cleanly factored → is the clean base dataset (with `datapackage.json`) **promoted to the
    commons**? If not, promote it (procedure below).

Rubric: **PASS** (base separated *and* promoted) / **WARN** (separated, not promoted) / **FAIL**
(entangled). Disposition: split → promote.

**Promotion procedure (the axis-3 endpoint is not a one-liner).** `science commons promote dataset`
sources from the project's **dataset entity descriptors** (`promote.py` `PROMOTE_KIND_DATASET`:
`source_subdirs=("doc/datasets",)`, `filename_prefix="data-"`), requires the `--slug` flag, and
selects the source project with `--from <project-id>`. So promoting a clean base dataset has
prerequisites that are themselves refactor tasks:

1. **Create / verify the project dataset entity** at `doc/datasets/data-<slug>.md`, carrying the
   required `mixin-dataset-1.0` fields and a `datapackage:` pointer to the dataset's
   `datapackage.json` (the manifest the clean base table already produces).
2. **Dry-run** `science commons promote dataset --from <project-id> --slug <slug>` (apply omitted)
   and inspect the plan.
3. **Apply** with `--apply` (add `--mixin <bio.*>` where a structural/domain bio extension matches
   the dataset modality).

The rubric's "promoted" therefore presumes a valid dataset entity exists; "WARN (separated, not
promoted)" covers both *no entity yet* and *entity exists but not promoted*.

## 6. Analysis/result-QA — a named, deferred discipline

Some valuable project-grown QA checks validate **results**, not the input table, and are therefore
out of scope for the data-QA convention:

- **Leave-one-out / dataset-dropout stability** — re-run dropping each input dataset; flag results
  that hinge on a single dataset.
- **Permutation / empirical-null calibration and assumption sweeps** — is the null well-calibrated;
  do modeling assumptions hold across strata?

The playbook **names this as a distinct discipline ("analysis/result-QA")** and **nominates it as a
future convention**, but does not specify it here. It is surfaced during the sweep so it is not
forgotten; writing the convention is a separate decision.

## 7. Convention expansion (done as part of this work)

One **table-shaped** structural check observed in practice is **folded into
`docs/conventions/pipeline-qa-checkpoints.md` now** (a small addition to its structural-check list):

- **Registry / enum validation** — when a pipeline ships a *data registry* (allowed contrasts,
  enumerated codes) that the processed table is checked against, validate the table's values are a
  subset of that registry as a structural check. This generalizes the convention's existing
  `categoricals.allowed` check to a shared single-source-of-truth registry, consistent with its
  "config-driven, single source of truth" principle. It reads the built table — it stays inside the
  convention's "one script + one rule reads the table" contract.

**Pipeline output-ownership / dedup is deliberately *not* added to the table-QA convention.** Each
pipeline output being produced by exactly one rule (no orphaned or duplicately-owned outputs) is a
**DAG-level** property — and the convention's own contract states an end-table QA script "cannot see
between-stage" structure. Folding a DAG check into the table-QA structural bucket would contradict
that contract. Instead the playbook defines it as a **separate workflow/DAG-validation pipeline
audit item** (a distinct structural checkpoint that inspects the rule graph, not a table), and
nominates it as a candidate for its own future workflow-validation convention.

## 8. Scope / non-goals

- This design produces the **playbook + convention expansion only**. It does **not** audit any
  project; applying it to mm30 is a later effort with its own outputs under that project's
  `doc/audits/pipeline-refactor/`.
- The playbook describes the **method**, including the refactor step; it does not itself perform
  refactors. Execution happens per-application through the normal task lifecycle.
- No central cross-project synthesis document — cross-project data reuse is realized through the
  commons registry, not an audit roll-up.
- The analysis/result-QA convention (§6) and the workflow/DAG-validation convention (§7) are named
  and nominated, but not written. Only the table-shaped registry/enum check is folded into the
  existing convention now.

## 9. Deliverables

1. `docs/process/pipeline-audit-and-refactor.md` — the playbook, with embedded inventory / findings
   / synthesis report skeletons.
2. Small expansion of `docs/conventions/pipeline-qa-checkpoints.md` (§7) and its README index line.
3. Cross-links: from `pipeline-qa-checkpoints.md` and the `computational-analysis` aspect to the new
   playbook where appropriate.

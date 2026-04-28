# Analysis Planning and Skill Index Design

## Goal

Add a lightweight analysis-planning entry point that helps agents find and load
the right Science methodology skills before designing or running data analyses,
without advertising every leaf skill globally.

The design should improve skill discovery for specialized data, statistics,
curation, and provenance guidance while preserving context economy.

## Context

Science now has a growing set of focused skill leaves for transcriptomics,
somatic mutation QA, mutational signatures, functional genomics, embeddings,
protein sequence/structure data, curation QA, survival models, compositional
data, power floors, sensitivity arbitration, and bias/variance reasoning.

Those leaves are useful only if an agent remembers to load the relevant hub
first. Making every leaf a globally advertised Codex skill would increase
always-loaded metadata and dilute triggering. A compact index and a planning
command provide a middle path:

- keep leaves as markdown references loaded on demand,
- expose a small always-consulted index at analysis-design time,
- make the agent explicitly choose which domain leaves to read,
- keep `plan-pipeline` focused on orchestration rather than methodology.

## Problem

Agents currently have several ways to start analysis work:

- `science-plan-pipeline` for workflow/pipeline design,
- `science-pre-register` for expectations and verdict criteria,
- `science-specify-model` / `science-sketch-model` for formal model capture,
- ad hoc user requests to "run this analysis" or "check this dataset,"
- direct coding work in downstream projects.

None of these has a single mandatory step that says:

1. identify the analysis data modality,
2. inspect whether the relevant QA/preprocessing assumptions are known,
3. load the relevant Science skill leaves,
4. state the methodological readiness checks before implementation.

As the skill library grows, discovery by memory becomes unreliable.

## Approaches Considered

### 1. Add `science-plan-analysis` plus a compact `skills/INDEX.md`

Create a new command skill that plans the methodological shape of one analysis.
It reads a compact skill index, selects relevant leaves, and produces an
analysis readiness plan.

Pros:

- keeps all leaf skills opt-in and context-efficient,
- gives agents a clear place to look before analysis,
- separates methodological readiness from pipeline plumbing,
- can be implemented mostly as command/skill documentation,
- creates a natural future hook for CLI-backed skill search.

Cons:

- adds a new command surface,
- risks overlap with `plan-pipeline` unless boundaries are explicit.

### 2. Add `science-tool skills list/search` first

Extend the CLI with skill listing and search, then update key commands to call
or mention the search command.

Pros:

- provides reusable discovery tooling,
- can support structured search by domain, modality, and tags,
- avoids hardcoding a long index inside command docs.

Cons:

- requires a catalog/schema decision before the workflow is proven,
- may become a thin wrapper around grep unless the catalog is curated,
- adds implementation before validating the simpler workflow.

### 3. Promote all leaf skills to true Codex skills

Give each leaf frontmatter and install it as an independently advertised skill.

Pros:

- maximizes automatic triggering,
- no separate index/search step needed.

Cons:

- increases global skill metadata,
- makes specialized leaves compete for triggering,
- encourages agents to load too much guidance for broad requests,
- weakens the current hub-and-leaf progressive-disclosure pattern.

### 4. Keep hub-managed indices only

Let each hub own its own leaf table: `skills/data/SKILL.md` for data leaves,
`skills/statistics/SKILL.md` for statistics leaves, and so on. Do not add a
global index.

Pros:

- fits the current hub pattern,
- keeps ownership local to each domain.

Cons:

- analysis planning is cross-domain by default,
- agents must already know which hub to load,
- duplicate cross-domain trigger logic spreads across hubs.

## Decision

Use **Approach 1 now**: add `science-plan-analysis` and `skills/INDEX.md`,
implemented in two dependent steps:

1. Run the structural skills-library refactor in
   `docs/plans/2026-04-26-skills-library-refactor.md`. That refactor creates
   the lintable `skills/INDEX.md`, normalizes frontmatter IDs, fixes renamed
   research-package paths, and adds index-coverage linting.
2. Implement `science-plan-analysis` and command integrations against that
   normalized skill tree.

`skills/INDEX.md` is the canonical human-facing map for analysis planning.
Hubs should point to it rather than maintaining parallel comprehensive leaf
lists. Hubs may keep short local pointers for common leaves, but the index owns
the cross-domain analysis-readiness map.

Treat CLI search as a later enhancement after the markdown index has been used
in at least three downstream projects. Do not promote all leaves to
always-advertised skills.

## Command Boundary

### `science-plan-analysis`

Purpose: decide whether an individual analysis is methodologically ready to run.

Primary questions:

- What is the estimand?
- What data modalities and preprocessing states are involved?
- What is the independent unit?
- What QA, normalization, and input-inspection checks must pass?
- Which specialized Science skills should be loaded?
- What model/statistical assumptions are being made?
- What power floor, bias/variance, and sensitivity-arbitration rules apply?
- What output artifacts prove the analysis was run responsibly?

Default output: save an analysis plan at:

```text
doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md
```

Use frontmatter:

```yaml
---
type: analysis-plan
id: analysis-plan:<slug>
date: YYYY-MM-DD
related:
  - hypothesis:<id>
  - inquiry:<slug>
  - task:<id>
status: ready | ready-with-caveats | not-ready
---
```

The saved plan is suitable to feed into `science-pre-register`,
`science-plan-pipeline`, or implementation work. If the user explicitly asks
for terminal-only output, the command may avoid saving, but saving is the
default.

The saved plan must also record which skill IDs were loaded and why:

```yaml
skills_loaded:
  - id: data-expression-scrna-qa
    reason: single-cell/pseudobulk expression analysis
  - id: statistics-power-floor-acknowledgement
    reason: finite-sample null or weak-result interpretation
```

### `science-plan-pipeline`

Purpose: design orchestration for one or more tasks.

Primary questions:

- What files, scripts, workflows, and dependencies are needed?
- Should this be a notebook, script, Snakemake workflow, RunPod job, or other
  execution path?
- What are the task boundaries and artifacts?
- How will outputs be regenerated and validated?

Output: an implementation/pipeline plan.

### `science-specify-model` / `science-sketch-model`

Purpose: capture or refine formal inquiry/model structure.

If an inquiry slug is provided to `plan-analysis`, already-captured inquiry
fields should be reused rather than re-asked. `plan-analysis` layers data QA,
power/resolution, bias/variance, and sensitivity arbitration on top of the
model rather than duplicating model-specification work.

### Relationship

`plan-analysis` may recommend running `plan-pipeline` if the analysis requires
non-trivial orchestration. `plan-pipeline` should point back to `plan-analysis`
when the user asks for pipeline work but the methodological checks are not yet
specified.

They can be used in either order for mature projects, but the safer default for
new analysis is:

```text
plan-analysis -> pre-register -> plan-pipeline -> implement/run
```

For small analyses, `plan-analysis` may be enough and can directly produce a
checklist for implementation.

## `skills/INDEX.md`

Create a compact markdown index that is safe to load at analysis-planning time.
It should not duplicate leaf content. It should map common analysis signals to
the right hub or leaf.

The index is canonical for analysis-readiness discovery. It must be lintable as
a normal skill markdown file:

```yaml
---
name: science-skill-index
description: Source of truth for finding Science methodology skills during analysis-readiness planning.
---
```

It should end with a short `## Companion Skills` section linking to the core
hubs. Hub files should begin with a short pointer:

```md
For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.
```

Add that pointer to:

- `skills/data/SKILL.md`,
- `skills/data/expression/SKILL.md`,
- `skills/data/genomics/SKILL.md`,
- `skills/statistics/SKILL.md`,
- `skills/research/SKILL.md`,
- `skills/writing/SKILL.md`,
- `skills/pipelines/SKILL.md`.

`science-status` and `science-next-steps` should suggest `plan-analysis` when
an active hypothesis or task implies data analysis but has no linked
`analysis-plan:<slug>` artifact.

## Canonical IDs

For future migration to `skills/catalog.yaml`, every index entry should carry a
stable `id`. After the skills-library refactor, every indexed markdown file
should have frontmatter; reuse its `name` value verbatim. Do not use older
path-stem aliases in new content. Example:

```md
- `data-expression` -> `skills/data/expression/SKILL.md`
- `data-expression-scrna-qa` -> `skills/data/expression/scrna-qa.md`
```

Do not invent separate catalog IDs that differ from frontmatter names.

## Proposed Index Shape

```md
---
name: science-skill-index
description: Source of truth for finding Science methodology skills during analysis-readiness planning.
---

# Science Skill Index

Use this index before planning or running a data analysis. Load only the leaves
that match the current task. Do not load every leaf "just in case"; that defeats
progressive disclosure.

## Core Analysis Checks

- `data-management`: `skills/data/SKILL.md`
- `statistics`: `skills/statistics/SKILL.md`
- `research-methodology`: `skills/research/SKILL.md`
- `scientific-writing`: `skills/writing/SKILL.md`

## Data Modalities

- `data-expression`: `skills/data/expression/SKILL.md`
- `data-expression-bulk-rnaseq-qa`: `skills/data/expression/bulk-rnaseq-qa.md`
- `data-expression-microarray-qa`: `skills/data/expression/microarray-qa.md`
- `data-expression-scrna-qa`: `skills/data/expression/scrna-qa.md`
- `data-genomics`: `skills/data/genomics/SKILL.md`
- `data-genomics-somatic-mutation-qa`: `skills/data/genomics/somatic-mutation-qa.md`
- `data-genomics-mutational-signatures-and-selection`: `skills/data/genomics/mutational-signatures-and-selection.md`
- `data-functional-genomics-qa`: `skills/data/functional-genomics-qa.md`
- `data-protein-sequence-structure-qa`: `skills/data/protein-sequence-structure-qa.md`
- `data-embeddings-manifold-qa`: `skills/data/embeddings-manifold-qa.md`

## Data Sources and Provenance

- `data-frictionless`: `skills/data/frictionless.md`
- `data-source-openalex`: `skills/data/sources/openalex.md`
- `data-source-pubmed`: `skills/data/sources/pubmed.md`
- `research-package-spec`: `skills/research/research-package-spec.md`
- `research-package-rendering`: `skills/research/research-package-rendering.md`
- `research-proposition-schema`: `skills/research/proposition-schema.md`

## Statistics

- `statistics-replicate-count-justification`: `skills/statistics/replicate-count-justification.md`
- `statistics-bias-vs-variance-decomposition`: `skills/statistics/bias-vs-variance-decomposition.md`
- `statistics-power-floor-acknowledgement`: `skills/statistics/power-floor-acknowledgement.md`
- `statistics-sensitivity-arbitration`: `skills/statistics/sensitivity-arbitration.md`
- `statistics-survival-and-hierarchical-models`: `skills/statistics/survival-and-hierarchical-models.md`
- `statistics-compositional-data`: `skills/statistics/compositional-data.md`
- `statistics-prereg-amendment-vs-fresh`: `skills/statistics/prereg-amendment-vs-fresh.md`

## Curation and Evidence

- `research-annotation-curation-qa`: `skills/research/annotation-curation-qa.md`

## Execution / Orchestration

Load these only after methodology is clear or when execution planning is the
user's explicit request:

- `pipelines`: `skills/pipelines/SKILL.md`
- `pipeline-snakemake`: `skills/pipelines/snakemake.md`
- `pipeline-marimo`: `skills/pipelines/marimo.md`
- `pipeline-runpod`: `skills/pipelines/runpod.md`

## Companion Skills

- [`data/SKILL.md`](data/SKILL.md) — load when data acquisition, preprocessing, or QA is in scope.
- [`statistics/SKILL.md`](statistics/SKILL.md) — load when finite-sample quantitative interpretation is in scope.
- [`research/SKILL.md`](research/SKILL.md) — load when evidence evaluation, curation, or proposition schema is in scope.
- [`pipelines/SKILL.md`](pipelines/SKILL.md) — load only after methodology is clear and execution planning is needed.
```

## Leaf Selection Rubric

`plan-analysis` must apply this table before loading leaves. The table is not
exhaustive; it defines minimum required leaves for common signals. Multi-modal
tasks accumulate leaves from every matching row, then de-duplicate.

| Trigger phrase / data signal | Required leaves |
|---|---|
| RNA-seq DE, count matrix, TPM/FPKM, GEO expression cohort | `data-expression`, matching expression sub-leaf (`data-expression-bulk-rnaseq-qa`, `data-expression-microarray-qa`, or `data-expression-scrna-qa`), `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Single-cell RNA-seq, h5ad, pseudobulk, per-cell model | `data-expression`, `data-expression-scrna-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Cell-type proportions, deconvolution, mixture fractions | `data-expression-scrna-qa` when scRNA-derived, `statistics-compositional-data`, `statistics-power-floor-acknowledgement` |
| Microarray, probe IDs, Affymetrix/Agilent/Illumina | `data-expression`, `data-expression-microarray-qa`, `statistics-bias-vs-variance-decomposition` |
| Targeted-panel mutation frequency, cBioPortal, GENIE, MAF | `data-genomics-somatic-mutation-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| CRISPR/RNAi, DepMap, LINCS/L1000, drug response | `data-functional-genomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Survival, Cox, Weibull, censored outcomes across cohorts | `statistics-survival-and-hierarchical-models`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Fractions/proportions constrained to sum to one | `statistics-compositional-data`, `statistics-bias-vs-variance-decomposition` |
| Embedding clustering, UMAP, HDBSCAN, Mapper, CKA, Moran's I | `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Protein PLM, UniProt/Pfam/CATH/Foldseek/MMseqs labels | `data-protein-sequence-structure-qa`; add `data-embeddings-manifold-qa` when embeddings/manifolds are analyzed |
| Manual/LLM annotation, claim extraction, taxonomy labels | `research-annotation-curation-qa`, `research-methodology` |
| Literature-only synthesis or theory, no data analysis | route to `science-research-topic` or `science-research-papers`; stop `plan-analysis` unless the user explicitly asks for an analysis plan |

Anti-pattern guard: do not load every leaf from the index. Pick the minimum
leaf set justified by modality, estimand, and data signal classification.

## `science-plan-analysis` Workflow

1. Follow the Science command preamble.
2. Read `skills/INDEX.md`.
3. Read project context:
   - `science.yaml`,
   - `specs/research-question.md` if present,
   - relevant hypotheses, inquiries, or prior pre-registrations if named.
4. If the task is literature synthesis or theory without a data-analysis
   component, route to `science-research-topic` or `science-research-papers` and
   stop.
5. If `--inquiry <slug>` is provided or an inquiry slug is in scope, read the
   inquiry/model state and prefill estimand, variables, independent unit, and
   model/test fields from it. Ask only for missing pieces.
6. Classify the analysis:
   - data modalities (list, not singular),
   - independent unit,
   - estimand,
   - intended model/test,
   - confirmatory vs exploratory status.
7. Use the leaf-selection rubric to load the minimum relevant leaves.
8. Produce and save an analysis readiness plan with these sections:
   - Analysis Question
   - Related Hypotheses / Inquiries / Tasks
   - Data Inputs and Provenance
   - Required Input Inspection
   - Preprocessing / Normalization Checks
   - Independent Unit and Denominator
   - Estimand and Primary Metric
   - Model / Test Assumptions
   - Power Floor or Resolution Limit
   - Bias vs Variance Risks
   - Sensitivity Arbitration
   - Required Output Artifacts
   - Aspect-contributed Sections
   - Readiness Decision
   - Feedback Reflection
9. If orchestration is non-trivial, recommend `science-plan-pipeline` as the next
   step.

The output-section list is aspect-extensible. For example, `causal-modeling`
may add "Identification Strategy / DAG Check"; `software-development` may add
"Test Plan"; `computational-analysis` may add workflow or validation sections.

## Readiness Decisions

The command emits exactly one readiness state:

| State | Consequence |
|---|---|
| `ready` | Analysis may proceed to pre-registration, pipeline planning, or implementation. |
| `ready-with-caveats` | Caveats must be listed in a `Known Limitations To Carry Forward` section. `pre-register` ingests this section verbatim when linked. |
| `not-ready` | Halt before pre-registration. Create one task per blocking check with `science-tool tasks add` when task tooling is available; otherwise list exact task text in the plan. |

Blocking checks should be small and executable: "inspect `.X` scale and raw
count layer for GSE...", not "do better QA."

## Pre-Register Integration

`science-pre-register` should:

1. Check whether the user or context references an `analysis-plan:<slug>`.
2. If present, read the saved analysis plan.
3. Prefill estimand, independent unit, input QA, power floor, sensitivity
   arbitration, and known limitations from the plan.
4. Avoid re-asking those questions unless the user changes scope.
5. Recommend, but not require, an analysis-plan reference when none exists for a
   data-analysis pre-registration.

This gives users a tangible reason to run `plan-analysis` before
`pre-register` without making it a hard dependency for every project.

## Knowledge Graph Hook

The first implementation should create a minimal graph footprint when graph
tooling is available:

- link the saved analysis plan to referenced hypothesis/inquiry/task entities,
- create or update assumption records for each model/test assumption,
- link the analysis plan as consumed by the relevant hypothesis or inquiry,
- include power-floor and sensitivity-rule metadata either as structured
  assumption records or as linked plan sections.

The graph hook can start conservative. The key requirement is that the analysis
plan is queryable and not just a markdown island.

## Triggering Guidance

Use `science-plan-analysis` when the user asks to:

- plan a statistical or data analysis,
- inspect whether a dataset is fit for analysis,
- design a single analysis task before coding,
- decide preprocessing/normalization/model choices,
- prepare an analysis for pre-registration,
- troubleshoot suspicious results that may reflect data QA or modeling issues.

Prefer `science-plan-pipeline` when the user asks to:

- create a multi-step workflow,
- organize scripts, notebooks, or Snakemake rules,
- plan execution on local, cloud, or GPU infrastructure,
- define task boundaries and output packages after methodology is already clear.

If both apply, start with `plan-analysis` unless the user explicitly asks for
orchestration first.

## Future CLI Search

After `skills/INDEX.md` has been used in at least three downstream projects,
evaluate whether a structured catalog and CLI search are needed.

If implemented, the CLI should use `skills/catalog.yaml` rather than parsing
arbitrary markdown heuristically:

```bash
uv run science-tool skills list
uv run science-tool skills search "single-cell pseudobulk power"
```

Future `science-tool skills recommend --project .` can inspect `science.yaml`,
active aspects, file layout, and named task context. It should remain advisory:
it suggests candidate leaves, and the command still records which leaves were
actually loaded and why.

Proposed catalog shape:

```yaml
- id: data-expression
  path: skills/data/expression/SKILL.md
  domains: [data, transcriptomics]
  triggers: [RNA-seq, microarray, scRNA-seq, h5ad, GEO]
  related: [statistics, statistics-compositional-data]
```

`skills/INDEX.md` can then be generated from the catalog or kept as the human
readable entry point.

## Maintenance Protocol

Initial structural refactor:

- Maintain `skills/INDEX.md` by hand.
- Add a lightweight lint check that every `skills/**/*.md` file is either
  referenced from `skills/INDEX.md` or explicitly ignored.
- Keep the index under about 150 lines.

Later catalog phase:

- Introduce `skills/catalog.yaml`.
- Generate or validate `skills/INDEX.md` from the catalog.
- Reuse frontmatter `name` values as canonical IDs where present.

## Implementation Dependency

The implementation should not be a single mixed refactor. The structural work
is prerequisite plumbing; the command work is behavior. Use this dependency:

```text
skills-library refactor -> analysis-planning command implementation
```

The refactor plan owns:

- create `skills/INDEX.md`,
- normalize frontmatter IDs and renamed skill paths,
- add `skills/INDEX.md` frontmatter and `## Companion Skills`,
- add relative-link and index-coverage linting,
- update hub pointers to the index.

The `science-plan-analysis` implementation owns:

- create `commands/plan-analysis.md`,
- generate `codex-skills/science-plan-analysis/SKILL.md` via
  `scripts/generate_codex_skills.py`,
- update `commands/plan-pipeline.md` to mention `plan-analysis` when
  methodological readiness is unclear,
- update `commands/pre-register.md` to read linked analysis plans and recommend
  `plan-analysis` when analysis assumptions are underspecified,
- update `commands/status.md` and `commands/next-steps.md` to suggest
  `plan-analysis` when active analysis-facing work lacks an analysis-plan
  artifact,
- add a feedback/reflection block matching the existing Science command style,
- add command-level validation scenarios from this spec.

Do **not** consolidate the structural refactor and command implementation into
one giant execution plan. They touch overlapping files but have different
verification criteria. Keep this spec as the product/behavior contract, keep
`docs/plans/2026-04-26-skills-library-refactor.md` as the structural
prerequisite plan, then write a second implementation plan for
`science-plan-analysis` after the refactor lands. If a coordination artifact is
needed, make it a short checklist that points to the two plans rather than a
merged plan.

Out of scope for both initial steps:

- `science-tool skills search`,
- structured `skills/catalog.yaml`,
- converting all leaves into installable Codex skills,
- automatic modality detection from data files,
- downstream project migrations.

## Validation

Review the new behavior against four pressure scenarios. Each scenario has an
expected minimum leaf set so validation is auditable.

### 1. MM30 scRNA pseudobulk / entropy analysis

Expected leaves:

- `data-expression`
- `data-expression-scrna-qa`
- `statistics-replicate-count-justification`
- `statistics-power-floor-acknowledgement`
- `statistics-bias-vs-variance-decomposition`
- `statistics-sensitivity-arbitration`
- `statistics-compositional-data` if cell fractions or deconvolution enter the analysis

Required plan assertions:

- independent unit is donor/patient, not cell,
- raw-count layer and normalization state are inspected,
- depth/library-size confounding is addressed,
- replicate count is justified if downsampling is stochastic.

### 2. cBioPortal targeted-panel mutation frequency or dN/dS analysis

Expected leaves:

- `data-genomics-somatic-mutation-qa`
- `data-genomics-mutational-signatures-and-selection` for dN/dS, TMB, or driver ranking
- `statistics-power-floor-acknowledgement`
- `statistics-bias-vs-variance-decomposition`
- `statistics-sensitivity-arbitration`

Required plan assertions:

- missing vs zero mutation cells are distinguished,
- callable denominator is gene/panel aware,
- hypermutator handling is pre-specified,
- study/cancer/panel confounding is named.

### 3. Natural-systems annotation/curation agreement analysis

Expected leaves:

- `research-annotation-curation-qa`
- `research-methodology`
- `scientific-writing`
- `statistics-bias-vs-variance-decomposition` if agreement statistics are verdict-bearing
- `statistics-power-floor-acknowledgement` if null/low-agreement interpretation matters

Required plan assertions:

- schema version and annotator/model provenance are recorded,
- agreement metric is matched to label structure,
- prevalence and confusion matrix are inspected,
- adjudication rule is pre-specified.

### 4. Protein-landscape heldout benchmark or embedding-manifold analysis

Expected leaves:

- `data-protein-sequence-structure-qa`
- `data-embeddings-manifold-qa`
- `statistics-bias-vs-variance-decomposition`
- `statistics-power-floor-acknowledgement`
- `statistics-sensitivity-arbitration`

Required plan assertions:

- row universe and ID mapping are fixed,
- homology/taxonomy leakage is checked,
- length/taxonomy nuisance axes are inspected,
- projection/clustering seed and hyperparameter sensitivity are planned.

For every scenario, verify that:

- `plan-analysis` loads `skills/INDEX.md`,
- the expected leaves are selected or a recorded reason explains any omission,
- the plan includes input inspection and QA checks,
- the plan states independent unit, estimand, power/resolution, and sensitivity
  arbitration where applicable,
- `plan-pipeline` is recommended only when orchestration work is needed.

## Feedback Reflection

`science-plan-analysis` should end with the same kind of reflection hook used by
other Science commands:

- What analysis-planning question was hard to answer?
- Which relevant skill was missing or hard to find?
- Did any loaded skill provide too much or too little guidance?
- Should the skill index or leaf-selection rubric be updated?

When `science-tool feedback add` is available, write the reflection there;
otherwise include it in the saved plan.

## Resolved Questions

- `plan-analysis` saves by default to `doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md`.
- `not-ready` creates one task per blocking check when task tooling is available.
- `pre-register` recommends but does not require a linked analysis plan.
- `skills/INDEX.md` includes execution/pipeline skills under a clearly marked
  late-stage section, but methodology leaves remain the primary purpose.

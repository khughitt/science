---
name: science-plan-analysis
description: "Plan whether an individual data analysis is methodologically ready before pre-registration, pipeline planning, or implementation. Use when the user asks to plan a statistical/data analysis, inspect dataset fitness, choose preprocessing/model assumptions, or prepare an analysis for pre-registration."
---

# Plan Analysis Readiness

Converted from Claude command `/science:plan-analysis`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

> **Prerequisites:**
> - Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.
> - Read `skills/INDEX.md`.
> - Load only the skill leaves justified by the modality, estimand, and data-signal classification.

## Purpose

Decide whether one analysis is methodologically ready to run. This command owns
data modality classification, input QA, independent-unit checks, estimand and
metric clarity, power/resolution limits, bias-vs-variance risks, sensitivity
arbitration, and required output artifacts.

Use `science-plan-pipeline` after this command when execution orchestration is
non-trivial. Use `science-pre-register` after this command when the plan is
`ready` or `ready-with-caveats` and confirmatory criteria should be locked.

## When a Pre-Registration Already Exists

The default order is plan → pre-register, but the two can arrive reversed: a
pre-registration may already be committed — and possibly amended after a bias
audit — before this command runs. When that is the case, the plan's job
inverts. The verdict surface is already locked, so do **not** re-derive decision
criteria or thresholds; relitigating a committed criterion set here invites
HARKing. Instead, focus the plan on the *implementation* gates the pre-reg did
not enumerate: data access and provenance, common-time-axis / unit conversions,
numerical-precision audits, and leakage checks. If you believe a locked
criterion is actually wrong, treat it as an amendment question rather than a
planning decision — load `statistics-prereg-amendment-vs-fresh` to decide
whether the change warrants a formal amendment or a fresh pre-registration, and
route it there instead of silently re-planning around it.

## Setup

1. Read `science.yaml`.
2. Read `specs/research-question.md` if present.
3. Read relevant hypotheses, inquiries, tasks, prior pre-registrations, and existing plans named by the user.
4. **Pre-registration discovery.** Search for locked or draft pre-registrations in `entities/pre-registrations/` first, then in legacy project doc locations such as `doc/meta/` and `docs/meta/`, and finally in legacy `specs/` locations only if they exist; do not assume absence just because `entities/pre-registrations/` is empty.
5. If an inquiry slug is provided, read the inquiry/model state and reuse captured estimand, variables, independent unit, and model/test fields.
6. If the task is literature synthesis or theory without a data-analysis component, route to `science-research-topic` or `science-research-papers` unless the user explicitly wants an analysis plan.
7. Before drafting the plan, run a data-availability / metric-feasibility pre-check:
   - Are the needed inputs already represented by `dataset:<slug>` entities?
   - Is each input available now, explicitly acquisition-gated, or absent?
   - For identity-bearing inputs, is `identity_context` declared? Coordinate
     or bio identity-bearing profiles need taxon and assembly/tier declarations,
     or explicit UNKNOWN/unresolved declarations.
   - Can the primary metric be computed from the available columns, sample grain, and time axis?
   - If the answer is no, keep the plan in `not-ready` or design-stage mode and make acquisition/inspection the blocking checks instead of drafting a runnable analysis.

## Leaf Selection Rubric

Pick the minimum leaves justified by the task. Multi-modal analyses accumulate
rows and de-duplicate. Record every loaded skill in `skills_loaded` with a
reason.

| Trigger phrase / data signal | Required leaves |
|---|---|
| RNA-seq DE, count matrix, TPM/FPKM, GEO expression cohort | `data-expression`, matching expression sub-leaf (`data-expression-bulk-rnaseq-qa`, `data-expression-microarray-qa`, or `data-expression-scrna-qa`), `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Single-cell RNA-seq, h5ad, pseudobulk, per-cell model | `data-expression`, `data-expression-scrna-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Cell-type proportions, deconvolution, mixture fractions | `data-expression-scrna-qa` when scRNA-derived, `statistics-compositional-data`, `statistics-power-floor-acknowledgement` |
| Microarray, probe IDs, Affymetrix/Agilent/Illumina | `data-expression`, `data-expression-microarray-qa`, `statistics-bias-vs-variance-decomposition` |
| Targeted-panel mutation frequency, cBioPortal, GENIE, MAF | `data-genomics-somatic-mutation-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| CN segments, scWGS/DLP+ per-cell CN, SV/breakpoints, AmpliconArchitect/AmpliconClassifier, ecDNA | `data-genomics-copy-number-sv-qa`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Likelihood model fit, AIC/BIC/LRT, Wright-Fisher/Moran/binomial-segregation, selection-vs-neutral | `statistics-likelihood-model-comparison`, `statistics-population-genetics-likelihood`, `statistics-sensitivity-arbitration` |
| CRISPR/RNAi, DepMap, LINCS/L1000, drug response | `data-functional-genomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Survival, Cox, Weibull, censored outcomes across cohorts | `statistics-survival-and-hierarchical-models`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ | `data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling | `statistics-time-series-and-longitudinal-models`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration` |
| Network/graph edges, dyadic data, edge prediction, node-label permutation, QAP/MRQAP | `statistics-power-floor-acknowledgement`, `statistics-replicate-count-justification`, `statistics-sensitivity-arbitration`; treat dyads as dependent observations and do not use iid pair tests as the confirmatory inference |
| Fractions/proportions constrained to sum to one | `statistics-compositional-data`, `statistics-bias-vs-variance-decomposition` |
| Embedding clustering, UMAP, HDBSCAN, Mapper, CKA, Moran's I | `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Protein PLM, UniProt/Pfam/CATH/Foldseek/MMseqs labels | `data-protein-sequence-structure-qa`; add `data-embeddings-manifold-qa` when embeddings/manifolds are analyzed |
| Manual/LLM annotation, claim extraction, taxonomy labels | `research-annotation-curation-qa`, `research-methodology` |

## Workflow

1. Classify the analysis: modalities, independent unit, estimand, intended model/test, confirmatory vs exploratory status.
2. Load the minimum relevant leaves from `skills/INDEX.md`.
3. Identify required input inspection and preprocessing/normalization checks.
4. Build a **Per-Input Data Profile** with one row per input artifact or dataset. Include encoding / file format, row grain, join cardinality, missing-value sentinels, provenance / source version, checksum or immutable identifier, and identity declaration status for identity-bearing inputs.
5. State model/test assumptions, power floor or resolution limit, bias-vs-variance risks, and sensitivity-arbitration rules.
6. Decide exactly one readiness state: `ready`, `ready-with-caveats`, or `not-ready`.
7. Save the analysis plan by default.
8. If graph tooling is available, link the saved plan to referenced hypothesis, inquiry, and task entities.
9. If `not-ready`, create one task per blocking check when task tooling is available; otherwise list exact task text in the plan.
   Reuse task-scoped aspects from the triggering task or analysis context when
   they make the blocker easier to route, e.g. `science tasks add ... --aspects
   computational-analysis`. Task-scoped aspects are local task metadata; do not mutate `science.yaml` solely to create blocker tasks. Add a project-level
   aspect only when the whole project should load that aspect's command guidance.

### Design-stage causal plans with no dataset in hand

If the user is designing a causal analysis before a dataset has been selected,
do not invent a dataset entity or mark the analysis ready. Save a design-stage
analysis plan with `status: not-ready`, a `Data Inputs and Provenance` section
that states the required dataset properties, and `Blocking Checks Before
Pre-Registration` entries for dataset discovery, access verification, variable
availability, independent-unit validation, and metric feasibility. The plan may
still lock the estimand, adjustment strategy, negative controls, and sensitivity
arbitration rules, but execution and pre-registration remain gated on the data
checks.

## Output

Save to `entities/plans/<NNNN>-<slug>-analysis-plan.md` unless the user explicitly requests terminal-only output. Pick `<NNNN>` as the next free numeric prefix in `entities/plans/`; the filename stem and the `id` local part must match exactly.

Use this frontmatter:

```yaml
---
id: "plan:<NNNN>-<slug>-analysis-plan"
kind: "plan"
title: "<short title>"
status: ready | ready-with-caveats | not-ready
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
plan_kind: "analysis-plan"
related:
  - hypothesis:<id>
  - inquiry:<slug>
  - task:<id>
skills_loaded:
  - id: data-expression-scrna-qa
    reason: single-cell/pseudobulk expression analysis
---
```

Reference saved analysis plans as `plan:<NNNN>-<slug>-analysis-plan`. Do not emit
`kind: analysis-plan`, `id: analysis-plan:<slug>`, or a date-prefixed filename;
`analysis-plan` is not a registered entity kind, and non-numeric stems collide
with numeric entity validation in layout version 3 projects.

The body must include:

- Analysis Question
- Related Hypotheses / Inquiries / Tasks
- Data Inputs and Provenance
- Per-Input Data Profile
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

In `Per-Input Data Profile`, use one row per input artifact or dataset and include:

| Input | Encoding / file format | Row grain | Join cardinality | Missing-value sentinels | Provenance / source version | Checksum or immutable identifier | Identity declaration status |
|---|---|---|---|---|---|---|---|

Treat unknown profile fields as inspection blockers for `ready` decisions, not as blanks to ignore.
For identity-bearing inputs, exact resolution is required at the publish/promote
boundary, not necessarily during initial planning; unresolved identity must be
explicitly marked UNKNOWN/unresolved and carried as a caveat or blocker.

For `ready-with-caveats`, include `Known Limitations To Carry Forward`.
For `not-ready`, include `Blocking Checks Before Pre-Registration` — **but** when a
committed pre-registration already exists (the inverted order in *When a Pre-Registration
Already Exists*), title this section `Blocking Checks Before Execution` instead, since the
pre-reg is locked and the checks gate execution, not registration. For a data-gated pre-reg,
these blocking checks **are** that pre-reg's vehicle-admissibility G-gates — reference the
gate by name rather than restating it, so the two artifacts share one gate definition.

## Validation Pressure Scenarios

Use these as spot checks when applying the command:

1. **MM30 scRNA pseudobulk / entropy analysis** - include `data-expression`, `data-expression-scrna-qa`, `statistics-replicate-count-justification`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`, and `statistics-compositional-data` if cell fractions enter the analysis.
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection` for dN/dS/TMB/driver ranking, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, and `statistics-sensitivity-arbitration`.
3. **Natural-systems annotation/curation agreement analysis** - include `research-annotation-curation-qa`, `research-methodology`, `scientific-writing`, plus `statistics-bias-vs-variance-decomposition` and `statistics-power-floor-acknowledgement` when agreement statistics are verdict-bearing.
4. **Protein-landscape heldout benchmark or embedding-manifold analysis** - include `data-protein-sequence-structure-qa`, `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`.
5. **ecDNA selection-vs-neutral on per-cell scWGS (e.g. Bafna-style binomial segregation on DLP+)** - include `data-genomics-copy-number-sv-qa` for the per-cell CN calls, `statistics-population-genetics-likelihood` for the WF/Moran/segregation likelihoods, `statistics-likelihood-model-comparison` for the AIC/BIC/LRT comparison, plus `statistics-power-floor-acknowledgement` and `statistics-sensitivity-arbitration`. A single-cohort selection signal is cohort-scoped pending independent replication.
6. **Proteomics or phosphoproteomics cohort contrast** - include `data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`, and `statistics-sensitivity-arbitration`; add `statistics-power-floor-acknowledgement` when null or weak effects are verdict-bearing.
7. **Wearable/sensor or symptom-diary time-series analysis** - include `statistics-time-series-and-longitudinal-models`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`.
8. **Disease graph edge-prediction or dyadic network analysis** - include `statistics-power-floor-acknowledgement`, `statistics-replicate-count-justification`, and `statistics-sensitivity-arbitration`; require a permutation design such as QAP/MRQAP or node-label permutation when edges share nodes.

## Process Reflection

Reflect on the **template**, **skill index**, and **workflow** used above.

If you have feedback, report each item via:

```bash
science feedback add \
  --target "command:plan-analysis" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Skip if everything worked smoothly.

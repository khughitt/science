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
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
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
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
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
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

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

## Setup

1. Read `science.yaml`.
2. Read `specs/research-question.md` if present.
3. Read relevant hypotheses, inquiries, tasks, prior pre-registrations, and existing plans named by the user.
4. If an inquiry slug is provided, read the inquiry/model state and reuse captured estimand, variables, independent unit, and model/test fields.
5. If the task is literature synthesis or theory without a data-analysis component, route to `science-research-topic` or `science-research-papers` unless the user explicitly wants an analysis plan.

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
| CRISPR/RNAi, DepMap, LINCS/L1000, drug response | `data-functional-genomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Survival, Cox, Weibull, censored outcomes across cohorts | `statistics-survival-and-hierarchical-models`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Fractions/proportions constrained to sum to one | `statistics-compositional-data`, `statistics-bias-vs-variance-decomposition` |
| Embedding clustering, UMAP, HDBSCAN, Mapper, CKA, Moran's I | `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Protein PLM, UniProt/Pfam/CATH/Foldseek/MMseqs labels | `data-protein-sequence-structure-qa`; add `data-embeddings-manifold-qa` when embeddings/manifolds are analyzed |
| Manual/LLM annotation, claim extraction, taxonomy labels | `research-annotation-curation-qa`, `research-methodology` |

## Workflow

1. Classify the analysis: modalities, independent unit, estimand, intended model/test, confirmatory vs exploratory status.
2. Load the minimum relevant leaves from `skills/INDEX.md`.
3. Identify required input inspection and preprocessing/normalization checks.
4. State model/test assumptions, power floor or resolution limit, bias-vs-variance risks, and sensitivity-arbitration rules.
5. Decide exactly one readiness state: `ready`, `ready-with-caveats`, or `not-ready`.
6. Save the analysis plan by default.
7. If graph tooling is available, link the saved plan to referenced hypothesis, inquiry, and task entities.
8. If `not-ready`, create one task per blocking check when task tooling is available; otherwise list exact task text in the plan.

## Output

Save to `doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md` unless the user explicitly requests terminal-only output.

Use this frontmatter:

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
skills_loaded:
  - id: data-expression-scrna-qa
    reason: single-cell/pseudobulk expression analysis
---
```

The body must include:

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

For `ready-with-caveats`, include `Known Limitations To Carry Forward`.
For `not-ready`, include `Blocking Checks Before Pre-Registration`.

## Validation Pressure Scenarios

Use these as spot checks when applying the command:

1. **MM30 scRNA pseudobulk / entropy analysis** - include `data-expression`, `data-expression-scrna-qa`, `statistics-replicate-count-justification`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`, and `statistics-compositional-data` if cell fractions enter the analysis.
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection` for dN/dS/TMB/driver ranking, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, and `statistics-sensitivity-arbitration`.
3. **Natural-systems annotation/curation agreement analysis** - include `research-annotation-curation-qa`, `research-methodology`, `scientific-writing`, plus `statistics-bias-vs-variance-decomposition` and `statistics-power-floor-acknowledgement` when agreement statistics are verdict-bearing.
4. **Protein-landscape heldout benchmark or embedding-manifold analysis** - include `data-protein-sequence-structure-qa`, `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`.

## Process Reflection

Reflect on the **template**, **skill index**, and **workflow** used above.

If you have feedback, report each item via:

```bash
science-tool feedback add \
  --target "command:plan-analysis" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Skip if everything worked smoothly.

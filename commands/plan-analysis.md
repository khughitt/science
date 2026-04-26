---
description: Plan whether an individual data analysis is methodologically ready before pre-registration, pipeline planning, or implementation. Use when the user asks to plan a statistical/data analysis, inspect dataset fitness, choose preprocessing/model assumptions, or prepare an analysis for pre-registration.
---

# Plan Analysis Readiness

> **Prerequisites:**
> - Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
> - Read `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`.
> - Load only the skill leaves justified by the modality, estimand, and data-signal classification.

## Purpose

Decide whether one analysis is methodologically ready to run. This command owns
data modality classification, input QA, independent-unit checks, estimand and
metric clarity, power/resolution limits, bias-vs-variance risks, sensitivity
arbitration, and required output artifacts.

Use `/science:plan-pipeline` after this command when execution orchestration is
non-trivial. Use `/science:pre-register` after this command when the plan is
`ready` or `ready-with-caveats` and confirmatory criteria should be locked.

## Setup

1. Read `science.yaml`.
2. Read `specs/research-question.md` if present.
3. Read relevant hypotheses, inquiries, tasks, prior pre-registrations, and existing plans named by the user.
4. If an inquiry slug is provided, read the inquiry/model state and reuse captured estimand, variables, independent unit, and model/test fields.
5. If the task is literature synthesis or theory without a data-analysis component, route to `/science:research-topic` or `/science:research-papers` unless the user explicitly wants an analysis plan.

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

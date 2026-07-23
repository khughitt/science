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
planning decision — load `study-design-prereg-amendment-vs-fresh` to decide
whether the change warrants a formal amendment or a fresh pre-registration, and
route it there instead of silently re-planning around it.

## Setup

1. Read `science.yaml`.
2. Read relevant questions in `entities/questions/` when present.
3. Read relevant hypotheses, inquiries, tasks, prior pre-registrations, and existing plans named by the user.
4. **Pre-registration discovery.** Search for locked or draft pre-registrations in `entities/pre-registrations/`; do not assume absence just because no task mentions one.
5. If an inquiry slug is provided, read the inquiry/model state and reuse captured estimand, variables, independent unit, and model/test fields.
6. If the task is literature synthesis or theory without a data-analysis component, route to `/science:research-topic` or `/science:research-papers` unless the user explicitly wants an analysis plan.
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
| RNA-seq DE, count matrix, TPM/FPKM, GEO expression cohort | `transcriptomics`, matching expression sub-leaf (`transcriptomics-bulk-rnaseq-qa`, `transcriptomics-microarray-qa`, or `transcriptomics-scrna-qa`), `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition` |
| Single-cell RNA-seq, h5ad, pseudobulk, per-cell model | `transcriptomics`, `transcriptomics-scrna-qa`, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition` |
| Cell-type proportions, deconvolution, mixture fractions | `transcriptomics-scrna-qa` when scRNA-derived, `statistics-compositional-data`, `study-design-power-floor-acknowledgement` |
| Microarray, probe IDs, Affymetrix/Agilent/Illumina | `transcriptomics`, `transcriptomics-microarray-qa`, `study-design-bias-vs-variance-decomposition` |
| Targeted-panel mutation frequency, cBioPortal, GENIE, MAF | `genomics-somatic-mutation-qa`, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition` |
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-qa`, `genomics-driver-selection`, `study-design-power-floor-acknowledgement`, `study-design-sensitivity-arbitration` |
| CN segments, scWGS/DLP+ per-cell CN, SV/breakpoints, AmpliconArchitect/AmpliconClassifier, ecDNA | `genomics-copy-number-sv-qa`, `study-design-power-floor-acknowledgement`, `study-design-sensitivity-arbitration` |
| Likelihood model fit, AIC/BIC/LRT, Wright-Fisher/Moran/binomial-segregation, selection-vs-neutral | `statistics-likelihood-model-comparison`, `statistics-population-genetics-likelihood`, `study-design-sensitivity-arbitration` |
| CRISPR/RNAi, DepMap, LINCS/L1000, drug response | `functional-genomics-qa`, `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration` |
| Survival, Cox, Weibull, censored outcomes across cohorts | `statistics-survival-and-hierarchical-models`, `study-design-power-floor-acknowledgement`, `study-design-sensitivity-arbitration` |
| Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ | `proteomics-qa`, `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration` |
| Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling | `statistics-time-series-and-longitudinal-models`, `study-design-bias-vs-variance-decomposition`, `study-design-power-floor-acknowledgement`, and `study-design-sensitivity-arbitration` |
| Network/graph edges, dyadic data, edge prediction, node-label permutation, QAP/MRQAP | `study-design-power-floor-acknowledgement`, `study-design-replicate-count-justification`, `study-design-sensitivity-arbitration`; treat dyads as dependent observations and do not use iid pair tests as the confirmatory inference |
| Fractions/proportions constrained to sum to one | `statistics-compositional-data`, `study-design-bias-vs-variance-decomposition` |
| Embedding clustering, UMAP, HDBSCAN, Mapper, CKA, Moran's I | `ml-embeddings-manifold-qa`, `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration` |
| Protein PLM, UniProt/Pfam/CATH/Foldseek/MMseqs labels | `proteomics-protein-sequence-structure-qa`; add `ml-embeddings-manifold-qa` when embeddings/manifolds are analyzed |
| Manual/LLM annotation, claim extraction, taxonomy labels | `epistemics-annotation-curation-qa`, `literature-evaluation`, `literature-citation-discipline` |
| Profile likelihood, nuisance parameters, optimiser choice, ODE / numerical integration, parameter recovery, synthetic-recovery gate | `study-design-estimator-certification` |

## Workflow

1. Classify the analysis: modalities, independent unit, estimand, intended model/test, confirmatory vs exploratory status.
2. Load the minimum relevant leaves from `skills/INDEX.md`.
3. Identify required input inspection and preprocessing/normalization checks.
4. Build a **Per-Input Data Profile** with one row per input artifact or dataset. Include encoding / file format, row grain, join cardinality, missing-value sentinels, provenance / source version, checksum or immutable identifier, and identity declaration status for identity-bearing inputs.
5. State model/test assumptions, power floor or resolution limit, bias-vs-variance risks, and sensitivity-arbitration rules. If the analysis fits parameters numerically, also state the estimator certification plan (the four axes) and, for each validation probe, what result would make that probe fail.
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
status: draft
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
plan_kind: "analysis-plan"
related:
  - hypothesis:<id>
  - inquiry:<slug>
  - task:<id>
skills_loaded:
  - id: transcriptomics-scrna-qa
    reason: single-cell/pseudobulk expression analysis
---
```

`status` is the plan's **lifecycle** state (`draft` while authoring, then
`active`/`complete` per the plan status vocabulary) — it is **not** the readiness
verdict. The `ready | ready-with-caveats | not-ready` judgement is the analysis
plan's gate outcome and belongs in the **Readiness Decision** body section below,
never in the frontmatter `status` (those values are not in the plan vocabulary and
fail status-vocabulary validation).

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
- Estimator and Probe Design
- Power Floor or Resolution Limit
- Bias vs Variance Risks
- Sensitivity Arbitration
- Required Output Artifacts
- Aspect-contributed Sections
- Readiness Decision
- Feedback Reflection

**Estimator and Probe Design.** Include this section when the analysis fits parameters numerically —
an optimiser, a profile likelihood, an ODE or any other discretisation in the inferential path. Name
the estimator, and state how each certification axis will be established: well-posedness (is the
parameter estimable at all?), forward-map accuracy against a reference with a *different
error-generating mechanism*, reproducibility under perturbation of every inferentially irrelevant
choice, and calibration of the decision rule's null. Name the outer optimiser and why it is valid for
the profile's smoothness structure.

For **every validation probe** you plan, write the answer to: *what result would make this probe
fail?* A probe with no such answer is evidence-shaped ceremony — it will discharge the obligation
without ever having tested it. See
[`study-design-estimator-certification`](../skills/study-design/estimator-certification.md).

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

1. **MM30 scRNA pseudobulk / entropy analysis** - include `transcriptomics`, `transcriptomics-scrna-qa`, `study-design-replicate-count-justification`, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration`, and `statistics-compositional-data` if cell fractions enter the analysis.
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-qa` for TMB and signatures, `genomics-driver-selection` for dN/dS and driver ranking, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition`, and `study-design-sensitivity-arbitration`.
3. **Natural-systems annotation/curation agreement analysis** - include `epistemics-annotation-curation-qa`, `literature-evaluation`, `literature-citation-discipline`, `scientific-writing`, plus `study-design-bias-vs-variance-decomposition` and `study-design-power-floor-acknowledgement` when agreement statistics are verdict-bearing.
4. **Protein-landscape heldout benchmark or embedding-manifold analysis** - include `proteomics-protein-sequence-structure-qa`, `ml-embeddings-manifold-qa`, `study-design-bias-vs-variance-decomposition`, `study-design-power-floor-acknowledgement`, and `study-design-sensitivity-arbitration`.
5. **ecDNA selection-vs-neutral on per-cell scWGS (e.g. Bafna-style binomial segregation on DLP+)** - include `genomics-copy-number-sv-qa` for the per-cell CN calls, `statistics-population-genetics-likelihood` for the WF/Moran/segregation likelihoods, `statistics-likelihood-model-comparison` for the AIC/BIC/LRT comparison, plus `study-design-power-floor-acknowledgement` and `study-design-sensitivity-arbitration`. A single-cohort selection signal is cohort-scoped pending independent replication.
6. **Proteomics or phosphoproteomics cohort contrast** - include `proteomics-qa`, `study-design-bias-vs-variance-decomposition`, and `study-design-sensitivity-arbitration`; add `study-design-power-floor-acknowledgement` when null or weak effects are verdict-bearing.
7. **Wearable/sensor or symptom-diary time-series analysis** - include `statistics-time-series-and-longitudinal-models`, `study-design-bias-vs-variance-decomposition`, `study-design-power-floor-acknowledgement`, and `study-design-sensitivity-arbitration`.
8. **Disease graph edge-prediction or dyadic network analysis** - include `study-design-power-floor-acknowledgement`, `study-design-replicate-count-justification`, and `study-design-sensitivity-arbitration`; require a permutation design such as QAP/MRQAP or node-label permutation when edges share nodes.

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

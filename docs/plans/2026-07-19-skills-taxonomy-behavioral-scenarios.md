# Skills Taxonomy Behavioral Scenarios

**Status:** with-doctrine acceptance passed 2026-07-19

This record defines the behavioral scenario families used to evaluate the
skills-taxonomy and skill-authoring doctrine. The baseline was captured before
`skills/meta/` or `skills/meta/templates/` existed.

## Evaluation isolation

Each repetition ran in a fresh-context evaluator with no inherited
conversation. Evaluators were instructed to use only the supplied request and
artifact, not to use tools, and not to inspect files or a repository. They were
not given the design, implementation plan, doctrine, acceptance criteria,
expected verdicts, earlier outputs, or any other repository context.

All nine no-doctrine baseline repetitions followed that contract. No baseline
runs were discarded as contaminated.

## Scenario definitions

### S1 — Classification

**Exact request**

> Use only the context supplied in this message. Do not use tools, inspect
> files, or access any repository. Answer with your verdict and reasoning.
>
> Which of these six archetypes is this — measurement-qa, method-guide,
> analysis-discipline, normative-reference, tool-guide, practice-guide — and
> why?
>
> [The stripped `bias-vs-variance-decomposition.md` body in Appendix A followed
> verbatim.]

**With-doctrine acceptance criterion:** returns `analysis-discipline` in every
run and consistently applies the doctrine-specific boundary: the central
operation is to justify or audit through a method-independent,
pre-interpretation gate, rather than to select, construct, fit, estimate, or
compare a method. This reasoning consistency is the required improvement over
the already-correct baseline label.

### S2 — Authoring

**Exact request**

> Use only the context supplied in this message. Do not use tools, inspect
> files, or access any repository.
>
> We need guidance for QA-ing a new assay modality. Draft the skill's section
> skeleton.

**With-doctrine acceptance criterion:** produces the `measurement-qa` slot set:
sources and ingestion/construction; pre-flight checklist; QA metrics table;
common failure modes; halt-on conditions with an explicit disposition for each;
and a minimum output package shown as a fixed directory tree.

### S3 — Create, extend, or split

**Exact request**

> Use only the context supplied in this message. Do not use tools, inspect
> files, or access any repository. For each request, decide whether to CREATE a
> new skill, EXTEND the supplied skill, or SPLIT the supplied skill into
> separate skills, and explain why.
>
> Request A: add guidance on choosing the DE tool for bulk RNA-seq
>
> Supplied existing skill body:
>
> [The stripped `bulk-rnaseq-qa.md` body in Appendix B followed verbatim.]
>
> Request B: the frictionless skill also needs to teach the `frictionless
> validate` CLI end-to-end
>
> Supplied existing skill body:
>
> [The stripped `frictionless.md` body in Appendix C followed verbatim.]

**With-doctrine acceptance criterion:** applies the observable
create/extend/split criteria. Request A separates DE-tool selection into a
distinct `method-guide`: either SPLIT/extract the existing DE method content or
CREATE the distinct leaf, but never EXTEND the `measurement-qa` leaf. Request B
is SPLIT because the datapackage contract and operation of a named CLI are
distinct archetypes and independently loadable decisions.

## No-doctrine baseline results

### S1 results

#### Repetition 1 — verbatim

> **Verdict: analysis-discipline.**
>
> It imposes a cross-cutting reasoning and reporting discipline on analytical
> work: identify the estimand and estimator, decompose random versus systematic
> error, diagnose each term, and constrain conclusions accordingly. It is not a
> guide to executing one specific method; its examples span bootstrap,
> permutation, MCMC, entropy estimation, confounding, and model fit. The
> templates and decision rules exist to prevent a recurring analytical category
> error—treating added replication as a remedy for bias—and to govern
> interpretation across methods.

#### Repetition 2 — verbatim

> **Verdict: analysis-discipline.**
>
> It imposes a cross-cutting reasoning discipline on analyses: explicitly
> separate stochastic variance from systematic bias before choosing replicate
> counts, interpreting uncertainty, or making verdicts. The decomposition
> template, diagnostics, decision rules, and reporting requirements enforce
> sound inferential judgment across many methods.
>
> It is not a method-guide because it does not teach one specific statistical
> procedure; not measurement-QA because measurement bias is only one error
> category; and not a tool-, normative-, or general practice-guide because its
> central concern is analytical validity and interpretation.

#### Repetition 3 — verbatim

> **Verdict: analysis-discipline.**
>
> It establishes a cross-cutting reasoning framework for analyses: explicitly
> separate stochastic variance from systematic bias, identify which
> interventions affect each error term, run appropriate diagnostics, and
> calibrate conclusions and reporting accordingly.
>
> It is not a method-guide because it does not teach one specific statistical
> procedure; it governs how to reason about and interpret many
> methods—bootstrap, permutation tests, MCMC, entropy estimation, and confounded
> models.

**Observed spread:** 3/3 chose `analysis-discipline`. There was no verdict
variance. All three distinguished a cross-method reasoning discipline from a
specific statistical procedure.

### S2 results

#### Repetition 1 — verbatim

> ## QA for a New Assay Modality
>
> ### Purpose
>
> - Define what this QA process validates.
> - State what is outside its scope.
>
> ### Modality Profile
>
> - Assay name and scientific purpose
> - Input material and preparation
> - Measurement technology and output units
> - Expected controls, replicates, and metadata
> - Known platform-specific artifacts
>
> ### Acceptance Contract
>
> - Required input files and schema
> - Required sample and assay metadata
> - Supported instrument and pipeline versions
> - Explicit pass, warning, and fail criteria
> - Conditions requiring manual review
>
> ### Preflight Validation
>
> - File presence, readability, and integrity
> - Identifier consistency across files
> - Units, ranges, and controlled vocabularies
> - Sample-sheet and manifest completeness
> - Duplicate, missing, or unexpected records
>
> ### Assay-Level Quality Checks
>
> - Signal strength and dynamic range
> - Background, noise, and detection limits
> - Saturation and floor effects
> - Control performance
> - Calibration or normalization suitability
>
> ### Sample-Level Quality Checks
>
> - Per-sample completeness and yield
> - Outlier detection
> - Contamination or mixture indicators
> - Technical artifact detection
> - Biological plausibility checks
>
> ### Replicate and Batch Checks
>
> - Technical replicate concordance
> - Biological replicate consistency
> - Batch-effect assessment
> - Plate, lane, run, or operator effects
> - Cross-run comparability
>
> ### Reference and Truth-Set Validation
>
> - Positive and negative controls
> - Synthetic or benchmark datasets
> - Expected-value comparisons
> - Sensitivity, specificity, precision, and recall
> - Tolerance definitions and uncertainty
>
> ### Failure Classification
>
> - Input or metadata failure
> - Instrument or laboratory failure
> - Processing-pipeline failure
> - Quality-threshold failure
> - Ambiguous result requiring review
>
> ### Reporting
>
> - Required summary metrics
> - Per-sample and per-batch results
> - Diagnostic plots or tables
> - Machine-readable output schema
> - Human-readable interpretation
> - Provenance and software versions
>
> ### Test Fixtures
>
> - Minimal valid example
> - Representative production example
> - Boundary-value cases
> - Known failure cases
> - Corrupted and incomplete inputs
> - Regression fixtures
>
> ### Validation Procedure
>
> - Development validation
> - Independent review
> - Pilot-run acceptance
> - Production readiness criteria
> - Sign-off responsibilities
>
> ### Ongoing Monitoring
>
> - Drift detection
> - Threshold recalibration
> - New platform or protocol versions
> - Incident review
> - Regression-test maintenance
>
> ### Modality-Specific Open Questions
>
> - Unresolved scientific assumptions
> - Missing benchmarks
> - Provisional thresholds
> - Required domain-expert decisions
> - Follow-up experiments or analyses

#### Repetition 2 — verbatim

> ## QA for a New Assay Modality
>
> ### 1. Scope and Intended Use
>
> - Modality definition
> - Supported inputs and outputs
> - Intended users and decisions
> - Explicit non-goals
>
> ### 2. Assay Contract
>
> - Required metadata
> - Units, scales, and coordinate systems
> - Valid value ranges
> - Missing-data semantics
> - Replicate and batch representation
> - Failure states
>
> ### 3. Reference Fixtures
>
> - Minimal valid example
> - Representative real-world examples
> - Boundary cases
> - Known-invalid examples
> - Expected outputs or invariants
>
> ### 4. Validation Layers
>
> #### Schema and Structural Validation
>
> - Required fields
> - Types, shapes, identifiers, and dimensions
> - Cross-field consistency
>
> #### Scientific Validation
>
> - Biological or physical plausibility
> - Controls and calibration
> - Expected signal and background
> - Replicate agreement
>
> #### Pipeline Validation
>
> - Parsing and normalization
> - Transformations and derived values
> - Round-trip integrity
> - Determinism and provenance
>
> ### 5. Quality Metrics and Thresholds
>
> - Primary quality metrics
> - Warning thresholds
> - Hard-failure thresholds
> - Threshold rationale
> - Dataset-level versus sample-level criteria
>
> ### 6. Test Matrix
>
> - Happy path
> - Edge and boundary cases
> - Malformed inputs
> - Missing or partial metadata
> - Batch effects and outliers
> - Scale and performance
> - Regression cases
>
> ### 7. Acceptance Procedure
>
> - Required commands or checks
> - Expected artifacts
> - Pass, warn, and fail rules
> - Manual-review triggers
> - Sign-off evidence
>
> ### 8. Failure Triage
>
> - Symptom-to-cause guide
> - Diagnostic sequence
> - Actionable error reporting
> - Escalation criteria
> - Quarantine and rerun policy
>
> ### 9. Regression Protection
>
> - Golden fixtures
> - Snapshot or invariant tests
> - Versioning expectations
> - Backward-incompatible change policy
>
> ### 10. Reporting Template
>
> - Modality and implementation version
> - Test data and provenance
> - Results by validation layer
> - Deviations and limitations
> - Final disposition: pass, conditional pass, or fail
>
> ### 11. Extension Checklist
>
> - New instrument or protocol variant
> - New organism, tissue, or sample type
> - New output schema
> - Threshold recalibration
> - Documentation and fixture updates

#### Repetition 3 — verbatim

> ## QA for a New Assay Modality
>
> ### 1. Purpose and Scope
>
> - Define the modality and intended scientific use.
> - Identify specimen types, organisms, instruments, and pipeline stages in
>   scope.
> - State what this QA can and cannot establish.
>
> ### 2. Required Inputs
>
> - Assay protocol and instrument metadata
> - Raw and processed data
> - Sample sheet and experimental design
> - Positive, negative, blank, and technical controls
> - Expected reference ranges or benchmark datasets
>
> ### 3. Assay-Specific Quality Model
>
> - Define the unit of observation and expected signal.
> - Identify modality-specific failure modes.
> - Map each failure mode to observable diagnostics.
> - Separate technical quality, biological plausibility, and batch
>   comparability.
>
> ### 4. Quality Metrics and Acceptance Criteria
>
> For each metric, specify:
>
> - Definition and calculation
> - Pipeline stage and aggregation level
> - Expected range
> - Warning and failure thresholds
> - Scientific rationale
> - Required response when violated
>
> ### 5. Control Validation
>
> - Positive controls
> - Negative controls and blanks
> - Spike-ins or reference materials
> - Replicates
> - Contamination and carryover checks
> - Control failure policy
>
> ### 6. Sample-Level QA
>
> - Completeness and metadata consistency
> - Signal strength and sensitivity
> - Noise, background, and artifacts
> - Outlier detection
> - Sample exclusion criteria
>
> ### 7. Feature-Level QA
>
> - Detection or coverage requirements
> - Feature reliability and missingness
> - Saturation or dynamic-range checks
> - Problematic feature filtering
> - Annotation validity
>
> ### 8. Batch and Run-Level QA
>
> - Run acceptance criteria
> - Batch effects and drift
> - Instrument or operator effects
> - Cross-run comparability
> - Reprocessing and rerun criteria
>
> ### 9. Reproducibility and Concordance
>
> - Technical replicate agreement
> - Orthogonal assay concordance
> - Reference-sample stability
> - Expected biological relationships
> - Benchmark comparison
>
> ### 10. Diagnostic Workflow
>
> 1. Validate inputs and controls.
> 2. Evaluate run-level metrics.
> 3. Evaluate sample-level metrics.
> 4. Evaluate feature-level metrics.
> 5. Investigate outliers and batch structure.
> 6. Classify findings as pass, warn, fail, or unresolved.
> 7. Record exclusions, reruns, and deviations.
>
> ### 11. Reporting Requirements
>
> - Required tables and plots
> - Machine-readable QA results
> - Summary status and reasons
> - Excluded samples or features
> - Thresholds and software versions
> - Deviations and unresolved concerns
>
> ### 12. Validation Before Adoption
>
> - Test on known-good and known-bad datasets.
> - Confirm expected failures are detected.
> - Assess threshold sensitivity.
> - Review false-positive and false-negative QA calls.
> - Obtain domain-expert approval.
>
> ### 13. Escalation and Failure Handling
>
> - Conditions requiring rerun, re-extraction, or exclusion
> - Conditions requiring protocol or pipeline review
> - Rules for unresolved or contradictory indicators
> - Named decision owner
>
> ### 14. Modality-Specific Extension Points
>
> - Required custom metrics
> - Optional diagnostics
> - Instrument-specific checks
> - Specimen-specific checks
> - Known limitations and open validation questions
>
> ### 15. Worked Example
>
> - Minimal valid input
> - Representative metric calculations
> - Pass/warn/fail interpretation
> - Final QA disposition and rationale
>
> ### 16. Checklist
>
> - Inputs present
> - Controls valid
> - Thresholds justified
> - Run, sample, and feature checks complete
> - Batch effects assessed
> - Findings documented
> - Acceptance decision recorded

**Observed spread:** the runs produced 14, 11, and 16 top-level sections,
respectively. All three included scope or inputs, quality checks or metrics,
decision thresholds, reporting, and validation. None produced the complete
six-slot target skeleton: no run specified a minimum output package as a fixed
directory tree, and the exact organization and granularity varied substantially
across all three.

### S3 results

#### Repetition 1 — verbatim

> Request A: **EXTEND** the supplied Bulk RNA-Seq QA skill.
>
> Choosing a differential-expression tool is already part of its scope: the
> skill distinguishes counts from continuous inputs and has a “Counts-based
> testing” section naming DESeq2 and limma-voom. Add a decision guide there
> covering input scale, sample size/design complexity, contrasts, repeated
> measures, effect-size conventions, and meta-analysis consistency. Creating or
> splitting a skill would fragment a tightly coupled QA-to-analysis decision.
>
> Request B: **EXTEND** the supplied Frictionless Data Packages skill.
>
> The skill already teaches package creation and includes a short
> `frictionless validate` example. End-to-end CLI validation—installation,
> invocation at resource/package level, reading reports, fixing common failures,
> re-running, and choosing exit-code behavior in automation—is a direct
> expansion of that existing “Validation” section. Split only if the material
> grows into a broader CLI reference covering many Frictionless commands beyond
> data-package validation.

#### Repetition 2 — verbatim

> - **Request A — EXTEND.** Choosing a differential-expression tool is already
>   part of the “Counts-based testing” workflow. Expand that section with
>   decision criteria for DESeq2, edgeR, and limma-voom based on sample size,
>   design complexity, count properties, and cross-cohort consistency. A
>   separate skill would fragment one bulk RNA-seq QA and analysis decision.
>
> - **Request B — EXTEND.** End-to-end `frictionless validate` usage is central
>   to the existing Frictionless Data Packages skill and directly deepens its
>   current “Validation” section. Add installation, descriptor/resource
>   validation commands, report interpretation, common remediation steps,
>   re-validation, and exit-code/CI usage. Split only if the CLI material later
>   grows into a broader standalone Frictionless operations reference covering
>   many commands beyond package validation.

#### Repetition 3 — verbatim

> - **Request A — EXTEND the supplied skill.** Tool selection is already
>   introduced in “Counts-based testing,” so adding a decision guide for DESeq2,
>   edgeR, limma-voom, and continuous-scale alternatives deepens an existing
>   responsibility. A new skill would fragment the bulk RNA-seq workflow;
>   splitting is unnecessary unless the guidance grows into a platform-wide
>   differential-expression methodology covering multiple assay types.
>
> - **Request B — EXTEND the supplied skill.** End-to-end `frictionless
>   validate` usage is a core operational part of Frictionless Data Packages and
>   naturally expands the existing “Validation” section. It should cover
>   installation, validating a descriptor or resource, interpreting reports and
>   exit status, fixing common errors, and rerunning validation. Creating or
>   splitting a separate CLI skill would separate package concepts from their
>   primary validation workflow without a distinct reuse boundary.

**Observed spread:** Request A was 3/3 EXTEND. Request B was also 3/3 EXTEND;
no run chose SPLIT or CREATE for either arm. The reasoning for Request A
consistently treated tool choice as part of the existing counts-based-testing
workflow. The reasoning for Request B consistently treated end-to-end CLI
operation as a direct expansion of the existing validation section.

## Raw evaluator artifacts

### Appendix A — stripped `bias-vs-variance-decomposition.md` body

````markdown
# Bias vs Variance Decomposition

Use when choosing estimators, replicate counts, correction terms, simulation
designs, or sensitivity analyses where stochastic noise and systematic error
could be confused.

More replicates reduce variance. They do not remove estimator bias, measurement
bias, label bias, sampling bias, leakage, confounding, or model misspecification.
Before spending compute, name which error term the compute can actually shrink.

## Pre-Flight Questions

1. **What is the target estimand?** Population mean, treatment effect, hazard
   ratio, entropy, rank, p-value, posterior contrast, or classifier metric.
2. **What is the estimator?** Write the exact statistic or model output used to
   estimate the estimand.
3. **Which error terms are random?** Sampling variation, bootstrap noise, MCMC
   Monte Carlo error, downsampling noise, train/validation split noise.
4. **Which error terms are systematic?** Depth effects, unmeasured confounding,
   censoring bias, batch effects, label error, missing-not-at-random data.
5. **Which terms shrink with more replicates?** If the answer is "none of the
   concerning ones," do not solve the problem by increasing R.

## Decomposition Template

For each verdict-bearing statistic, write a compact table:

| Error term | Source | Shrinks with | Diagnostic | Mitigation |
|---|---|---|---|---|
| Sampling variance | finite independent units | more units | SE/CI/power | larger n, hierarchical model |
| Replicate variance | stochastic algorithm | more replicates | replicate pilot | lock R by precision rule |
| Estimator bias | mathematical estimator | better estimator | simulation/analytic bias | correction, alternate estimator |
| Measurement bias | assay/preprocessing | better measurement | negative controls | redesign, adjustment, caveat |
| Confounding | data-generating process | identification strategy | DAG/sensitivity | adjustment, stratification, downgrade |

Do this before interpreting nulls or deciding that a large replicate count is
"more rigorous."

## Common Examples

- **Bootstrap CI too wide:** more bootstrap draws stabilize the CI estimate, but
  independent-unit sample size determines the real CI width.
- **Permutation p near alpha:** more permutations reduce Monte Carlo uncertainty
  around the p-value, but do not strengthen the underlying effect.
- **Miller-Madow entropy bias:** repeated downsampling reduces stochastic noise,
  not finite-count plug-in entropy bias.
- **scRNA library-size confound:** averaging more cells can sharpen the wrong
  association if library size is systematically tied to disease stage.
- **Model misspecification:** MCMC effective sample size cannot repair a
  likelihood that cannot generate the observed data.

## Diagnostics

- Analytical bias term, if known.
- Simulation with known truth under realistic data-generating conditions.
- Negative-control outcome or exposure.
- Split-half or seed sensitivity for stochastic parts.
- Residual / posterior predictive checks for model fit.
- Sensitivity to measurement preprocessing, filters, and covariates.

## Decision Rules

- If the dominant uncertainty is replicate variance, use
  `replicate-count-justification.md`.
- If the dominant uncertainty is independent-unit sampling variance, use a power
  or precision calculation; do not increase algorithmic replicates.
- If the dominant uncertainty is bias, choose a correction, an alternate
  estimator, or a verdict downgrade. Do not report a narrow CI as strong
  evidence when bias is unbounded.
- If bias direction is known but magnitude is not, state the direction and run a
  sensitivity range.

## Reporting

Include:

- estimand and estimator,
- named error terms,
- which terms shrink with more data vs more replicates,
- bias diagnostics run,
- sensitivity checks,
- residual bias that remains after mitigation.

If the analysis cannot separate bias from signal, report the result as
confounded or measurement-limited rather than as a clean null or clean support.

## Companion Skills

- [`replicate-count-justification.md`](replicate-count-justification.md) - algorithmic replicate variance and resampling-count decisions.
- [`sensitivity-arbitration.md`](sensitivity-arbitration.md) - verdict downgrades when bias diagnostics disagree.
- [`power-floor-acknowledgement.md`](power-floor-acknowledgement.md) - independent-unit precision limits that cannot be repaired by more computation.
````

### Appendix B — stripped `bulk-rnaseq-qa.md` body

````markdown
# Bulk RNA-Seq QA

Practical QA for bulk RNA-Seq cohorts (TCGA, GTEx, recount3, ARCHS4,
GEO deposits, MMRF CoMMpass). For platform-general conventions see
[`SKILL.md`](./SKILL.md).

## Cohort acquisition checklist

1. **Counts vs TPM vs FPKM vs other.** This is the dominant source of
   silent bugs. Inspect the matrix yourself:
   - **Raw counts:** integer, library-size-dependent, range 0 to
     hundreds of thousands per gene. Required for DESeq2 / edgeR.
   - **TPM:** float, per-sample sums to ≈ 1M per sample. Library-size-
     normalised. Comparable across samples but not appropriate for
     count-based testing.
   - **FPKM / RPKM:** legacy, library-size + length-normalised. Avoid
     unless you have to.
   - **VST / rlog / log2(TPM+1):** depositor's variance-stabilised
     transform. Float, range ~[0, 20]. Comparable across samples for
     PCA / clustering / linear modelling.
   ```python
   # Assumes genes x samples. Transpose if rows are samples.
   col_sums = X.sum(axis=0)
   print(f"Per-sample sums: median={median(col_sums):.0f} CV={stdev(col_sums)/mean(col_sums):.3f}")
   # CV ≈ 0  → already normalised (TPM, library-size-corrected)
   # CV > 0.3 → raw counts (library size varies)
   ```
   Do not run DESeq2 / edgeR on TPM, FPKM, z-scores, or batch-corrected
   residuals. If raw counts are unavailable, switch to a continuous-scale
   model and state that count-based inference is out of scope.

2. **Gene model version.** GENCODE v27 vs v44 differ by thousands of
   gene-name renames and additions. Cross-cohort meta-analysis on
   different gene-model versions silently drops genes from the
   intersection. Lock the gene model at ingest; harmonise via Ensembl
   ID (stable across versions for the same biological gene) rather
   than gene symbol.

3. **Library preparation chemistry.** Poly-A selected, ribosomal-
   depleted, 3'-tag-only (Quant-seq, MARS-seq). 3'-tag protocols
   produce strong 3' bias and are NOT comparable to whole-transcript
   protocols at the gene-isoform level — only at the gene level. Old
   datasets (pre-2014) often used poly-A selection with degraded RNA,
   producing pronounced 3' bias even on "whole-transcript" protocols.

4. **Sample-level metadata completeness.** For every sample you intend
   to analyse, the cohort metadata must include: disease status,
   tissue, treatment, batch / sequencing run, collection date,
   library prep batch. Missing values in any of these become
   silent confounders.

5. **Technical replicates vs biological replicates.** A "sample" might
   be a single library, multiple libraries from the same patient, or
   multiple sequencing runs of the same library. Check the metadata
   schema before treating samples as independent.

## Minimum-viable per-sample QC

| Metric | Typical range | Red flag |
|---|---|---|
| Total reads / sample | 20–100M | < 5M → underpowered; > 200M → likely contamination |
| % reads aligned to genome | 70–95% | < 50% → contamination, mis-trimmed adapters |
| % reads aligned to gene model | 50–85% | < 30% → ribosomal contamination, intronic-heavy degradation |
| % rRNA contamination | < 5% | > 20% → poly-A selection failed or sample degraded |
| 3'/5' ratio (gene body coverage) | ~ 1.0 (uniform) | > 2.0 → 3' degradation; < 0.5 → 5' degradation |
| Median TIN (transcript integrity) | > 70 | < 50 → degraded RNA |
| Per-sample expressed genes | 12k–18k for Ensembl-coding | < 8k → low complexity / low depth |

## PCA / cohort structure

A first-pass PCA on log-transformed (or VST) expression coloured by:

- **Disease status / treatment / sex** — the biology you want to model.
- **Batch / sequencing run / library prep date** — confounders.
- **Tissue source / extraction protocol** — if mixed.

If batch separates more strongly than biology, you have a confound to
handle (model batch as a covariate, ComBat, RUVSeq, or — in extreme
cases — exclude). Document the choice in the cohort_audit sidecar.

For meta-analysis aggregating multiple cohorts: PCA per cohort
separately, never pool first. The cross-cohort PCA is dominated by
batch and is not informative for biology.

## Filter genes, don't filter aggressively

Standard filter: keep genes with ≥ 10 counts in ≥ N samples (where N
≈ smallest group size). This drops technical-zero / very-low-expression
genes without removing biology. Don't filter on detection rate alone
in cohorts with mixed cell-type composition (see SKILL.md "filter
steps must commute with the question").

## Counts-based testing

For raw count input, the default tools are DESeq2 (R) and limma-voom
(R). Choose one and stick with it across the analysis — both are
defensible; mixing produces incomparable effect-size scales.

For meta-analysis across cohorts:

- **Per-cohort DE → aggregate test statistics** is the MM30 default.
  Each cohort's per-gene effect size is z-scored within cohort before
  aggregation (see MM30 D1).
- **Pooled test on a common-reference normalisation** is appropriate
  when sample-size imbalance is small and platforms are similar.

State which strategy in the pre-registration.

## Continuous-covariate adjustment

When testing on continuous covariates (age, ISS stage as continuous,
purity), use the same model formula across all cohorts. Mixed-formula
adjustments (cohort A: `~ age`, cohort B: `~ age + sex`, cohort C:
unadjusted) produce incomparable effect sizes that cannot be
meaningfully meta-analysed.

For ordinal covariates (stage I / II / III), choose between treating
as continuous (linear assumption) or as factor (no linearity
assumption, more parameters). Document the choice.

## When to suspect pseudobulk vs true bulk

Some "bulk" RNA-Seq cohorts are actually scRNA-Seq pseudobulks. They
have:

- Per-sample read counts in the millions (not 20-100M).
- Per-sample gene counts < 8k.
- Per-cohort PCA showing extreme heterogeneity.

GSE106218 in MM30 is a documented pseudobulk that was incorrectly
treated as bulk in early analyses; it now is excluded (D7). When in
doubt, check the original publication's methods section.

## Halt-On Conditions

- Matrix scale is unverified and could be TPM, FPKM, z-scores, or residuals masquerading as counts.
- Gene-model version is unknown across cohorts that will be meta-analyzed.
- More than 10% of samples have `% rRNA > 20`.
- PCA shows batch dominating biology and no batch metadata are available for adjustment or exclusion.
- Per-sample read counts or expressed-gene counts suggest pseudobulk data being treated as true bulk RNA-seq.

## Output: a per-cohort QA package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/
├── cohort_audit.json         # filter steps, sample counts at each step
├── per_sample_metrics.tsv    # total_reads, % aligned, % rRNA, 3/5 ratio
├── pca_diagnostic.html       # PCA coloured by batch + biology
├── gene_filter_log.tsv       # which genes dropped, by which filter
├── counts_or_normalized.parquet  # the matrix used downstream
└── README.md                 # one-paragraph summary
```

## Companion Skills

- [`SKILL.md`](SKILL.md) - expression-data hub conventions for cross-platform cohort QA.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) - independent-unit and interval-resolution checks for cohort-level contrasts.
- [`../../statistics/bias-vs-variance-decomposition.md`](../../statistics/bias-vs-variance-decomposition.md) - separating preprocessing bias from estimator variance.
````

### Appendix C — stripped `frictionless.md` body

````markdown
# Frictionless Data Packages

## When To Use

- After downloading raw data to `data/raw/`
- Before connecting data to a pipeline or notebook
- When validating data quality and schema conformance
- When documenting dataset structure for reproducibility

## Core Concepts

A **Data Package** is a `datapackage.json` file describing one or more data **resources** (files) with their schemas, formats, and metadata.

A **resource** describes a single data file: its path, format, schema (field names, types, constraints), and encoding.

## Boundary With Dataset Entities

A Frictionless `datapackage.json` is a runtime/package descriptor for files that
exist in `data/raw/`, `data/processed/`, or result package directories. It is
not the local dataset entity lifecycle.

Use `science dataset add <slug>` and `science dataset verify-access <slug>` for
the durable `dataset:<slug>` entity. Use `science datasets validate --path data/raw/`, `science datasets infer-schema`, and `science datasets qa` for
runtime datapackage descriptors and file-level QA.

Use `science datasets validate` to validate the resolved project data root, or
`science datasets validate --path data/raw/` when intentionally checking an
explicit in-repo path. Respect `SCIENCE_DATA_ROOT` and `science.yaml`
`data.root`. Never commit files under the resolved data root.

## Creating a Data Package

### Option A: Auto-describe from existing files

```bash
# Generate descriptor from a CSV file
frictionless describe data/raw/observations.csv --json > data/raw/datapackage.json
```

Review and edit the generated descriptor — auto-detection may mis-type fields.

### Option B: Write manually

```json
{
  "name": "project-raw-data",
  "title": "Raw Data for <Project>",
  "description": "Downloaded from <source> on <date>",
  "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
  "resources": [
    {
      "name": "observations",
      "path": "observations.csv",
      "format": "csv",
      "encoding": "utf-8",
      "schema": {
        "fields": [
          {"name": "sample_id", "type": "string", "constraints": {"required": true}},
          {"name": "gene", "type": "string"},
          {"name": "expression", "type": "number"},
          {"name": "condition", "type": "string", "constraints": {"enum": ["control", "treated"]}}
        ],
        "primaryKey": "sample_id"
      }
    }
  ]
}
```

## Field Types

Use these Frictionless types:

| Type | Python equivalent | Use for |
|---|---|---|
| `string` | `str` | text, identifiers, categories |
| `number` | `float` | measurements, continuous values |
| `integer` | `int` | counts, indices |
| `boolean` | `bool` | flags |
| `date` | `datetime.date` | dates without time |
| `datetime` | `datetime.datetime` | timestamps |
| `array` | `list` | JSON arrays |
| `object` | `dict` | JSON objects |

## Validation

```bash
# Validate a runtime data package (built-in lightweight checks)
science datasets validate --path data/raw/

# For deeper validation, install frictionless CLI separately: uv add frictionless
frictionless validate data/raw/datapackage.json
```

Common validation errors:
- **Missing values** in required fields — add `missingValues: ["", "NA", "N/A"]` to resource
- **Type errors** — check if auto-detected types are correct
- **Extra/missing columns** — update schema to match actual file

## Connecting to Inquiry Variables

When a `datapackage.json` exists and an inquiry is active:

1. Map resource fields to inquiry variables in `entities/datasets/<slug>.md`
2. Manually check which inquiry variables are covered by available dataset fields
3. Document any transformations needed (unit conversions, normalization, filtering)

## Directory Conventions

```
data/
├── raw/                    # Immutable downloads
│   ├── datapackage.json    # Describes raw files
│   ├── observations.csv
│   └── metadata.csv
├── processed/              # Cleaned, transformed
│   ├── datapackage.json    # Describes processed files
│   └── normalized.csv
└── README.md               # Overview
```

**Rules:**
- Never modify files in `data/raw/` after download
- All transformations go to `data/processed/`
- Both directories get their own `datapackage.json`
- Record provenance: which script/pipeline produced each processed file

## Provenance in Data Packages

Add a `sources` field to track where data came from:

```json
{
  "name": "processed-data",
  "sources": [
    {"title": "GEO GSE12345", "path": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"},
    {"title": "Downloaded via science", "path": "science datasets download geo:GSE12345"}
  ],
  "resources": [...]
}
```

## Companion Skills

- [`SKILL.md`](SKILL.md) - data-management conventions that require descriptors for raw and processed datasets.
- [`../pipelines/snakemake.md`](../pipelines/snakemake.md) - workflow rules that generate package descriptors as terminal artifacts.
- [`../research/research-package-spec.md`](../research/research-package-spec.md) - research-package profile built on Frictionless data-package structure.
````

## With-doctrine results

### Evaluation isolation and discarded runs

Each counted repetition ran in a newly spawned evaluator with
`fork_turns="none"`. Every evaluator received only the corresponding Task 4
request/artifact plus the complete current `skill-taxonomy.md` and
`skill-authoring.md` contents. Evaluators were told to answer only from supplied
context without using tools, inspecting files, or accessing a repository. They
did not receive the design, implementation plan, acceptance criteria, expected
outcomes, baseline results, or other evaluator outputs.

All nine counted responses were uncontaminated. Two preliminary S1 runs were
discarded before scoring because the controller detected a prompt-fidelity
error: one clause (`else → leaf`) had been omitted while transcribing the
complete doctrine. Fresh agents repeated both runs with the corrected complete
payload. The discarded response bodies are not included below.

### S1 with-doctrine results

#### Repetition 1 — verbatim

````text
**Verdict: `analysis-discipline`.**

Its central operation is to **audit and justify the error decomposition before interpreting a result or increasing computation**. It requires analysts to name the estimand, estimator, random and systematic errors, determine which terms replicates can shrink, and then follow explicit decision and reporting rules.

It is not primarily a `method-guide`: it does not select or fit one particular estimator or model. Nor is it `measurement-qa`, because its scope extends well beyond measurement fidelity to estimator bias, sampling variance, Monte Carlo error, confounding, leakage, and misspecification. The decomposition is a required reasoning gate applied across methods, with downgrade and halt conditions—exactly the `analysis-discipline` contract.
````

#### Repetition 2 — verbatim

````text
**Verdict: `analysis-discipline`.**

Its central operation is to **audit and explicitly decompose bias versus variance before interpreting a result or allocating more computation**. It imposes a required pre-interpretation reasoning step: name the estimand and estimator, classify error terms, determine what replicates can shrink, run diagnostics, then downgrade or qualify the verdict when bias remains.

That matches the analysis-discipline contract:

- **Trigger:** stochastic noise and systematic error may be confused.
- **Required check:** complete the bias/variance decomposition.
- **Decision rules:** increase replicates, increase independent units, change estimator, mitigate bias, or downgrade the verdict.
- **Evidence/artifacts:** decomposition table, diagnostics, sensitivities, and residual-bias report.
- **Permitted reporting:** call inseparable effects confounded or measurement-limited rather than clean support/null.

It is not primarily `method-guide` because it does not select and fit one particular inferential procedure; the discipline applies across bootstrap, permutation, MCMC, entropy estimation, scRNA analysis, and other methods. It is broader than `measurement-qa`, since measurement bias is only one error class alongside confounding, estimator bias, misspecification, and algorithmic variance.
````

#### Repetition 3 — verbatim

````text
**Verdict: `analysis-discipline`.**

Its central requirement is to **audit and name bias and variance components before interpreting a result or allocating more computation**. It applies across estimators and procedures rather than selecting or fitting one specific method. The pre-flight questions, decomposition table, decision rules, verdict downgrades, halt condition (“do not solve…by increasing R”), and required reporting language align directly with the `analysis-discipline` contract.

It is not primarily:

- `method-guide`: it does not teach one model/procedure or fitting workflow.
- `measurement-qa`: measurement bias is only one error class; the scope includes sampling, algorithmic variance, confounding, and misspecification.
- `normative-reference`: the table is a reasoning template, not an artifact schema or conformance contract.
- `practice-guide`: the activity is specifically an interpretation gate, which the taxonomy assigns to `analysis-discipline`.
````

### S2 with-doctrine results

#### Repetition 1 — verbatim

````text
```markdown
---
name: <subject>-<assay>-qa
description: Use when assessing whether <assay> measurements are trustworthy for downstream inference, from ingestion through a documented QA verdict.
archetype: measurement-qa
provenance: internal
---

# <Assay> QA

## Scope

Define the measurement being assessed, the downstream assumptions it must support, and what this skill does not evaluate.

## Sources and ingestion/construction

- Accepted inputs and required metadata
- Provenance and sample identifiers
- Construction or preprocessing assumptions
- Input validation and normalization
- Traceability from source data to QA artifacts

## Pre-flight checklist

- Required files are present and readable
- Samples and identifiers reconcile
- Experimental design and controls are available
- Units, reference versions, and processing versions are explicit
- Known exclusions or transformations are recorded

## QA metrics

| Metric | What it tests | Calculation/input | Expected range or decision rule | Caveats |
|---|---|---|---|---|
| `<metric>` | `<measurement property>` | `<how derived>` | `<pass/warn/halt rule>` | `<limitations>` |

## Common failure modes

### `<failure mode>`

- Signal
- Likely causes
- Confirmation check
- Permitted remediation
- Effect on downstream interpretation

## Halt-on conditions

Halt downstream interpretation when any of the following apply:

- `<condition and threshold>`
- `<condition and threshold>`

For each condition, record `pass`, `fail`, or `not evaluated`, with supporting evidence. Do not silently continue after a failed or unevaluated mandatory condition.

## QA verdict

State:

- whether the assay faithfully measures or represents what downstream analysis assumes;
- the overall verdict: `pass`, `conditional`, or `halt`;
- failed or unevaluated halt-on conditions;
- limitations and permitted downstream uses;
- any required remediation or escalation.

## Minimum output package

```text
<assay>-qa/
├── README.md
├── summary.md
├── metrics.tsv
├── halt-conditions.tsv
├── figures/
└── provenance/
```

Required contents:

- `README.md` — package layout and reproduction instructions
- `summary.md` — verdict, limitations, and evaluated halt-on conditions
- `metrics.tsv` — metric values, rules, and statuses
- `halt-conditions.tsv` — every named halt condition with status and evidence
- `figures/` — diagnostic plots referenced by the summary
- `provenance/` — input inventory, versions, parameters, and processing trace

## Completion check

The QA package is complete only when all named files exist and `summary.md` explicitly states which halt-on conditions were evaluated and the resulting verdict.

## Companion Skills

- `<relative path>` — `<related routing or downstream-analysis skill>`
```

This is a `measurement-qa` leaf because its primary question is whether the assay’s observed or derived measurement is trustworthy for inference. Replace placeholders with modality-specific metrics and thresholds; if those are externally governed, replace `provenance: internal` with valid `sources:` rather than using both.
````

#### Repetition 2 — verbatim

````text
Classify it as `measurement-qa`: its primary question is whether the assay’s measurements faithfully support downstream inference.

```markdown
---
name: <subject-prefix>-<assay>-qa
description: Use when assessing whether <assay> measurements are trustworthy for downstream analysis.
archetype: measurement-qa
provenance: internal
---

# <Assay> QA

## Scope

What this skill evaluates, the measurement product covered, and what is explicitly out of scope.

## Sources and ingestion/construction

- Accepted inputs and formats
- Required metadata
- How the measurement product was generated
- Provenance and integrity checks
- Assumptions introduced during ingestion or construction

## Pre-flight checklist

- [ ] Required files are present and readable
- [ ] Sample identifiers reconcile across inputs and metadata
- [ ] Controls, batches, and assay-specific covariates are identified
- [ ] Units, transformations, and reference definitions are explicit
- [ ] Expected sample and feature counts are recorded

## QA metrics

| Metric | What it tests | Expected range/pattern | Warning condition | Halt condition | Required evidence |
|---|---|---|---|---|---|
| `<metric>` | `<measurement assumption>` | `<criterion>` | `<criterion>` | `<criterion>` | `<artifact>` |

## Cross-metric interpretation

How metrics combine into an overall verdict, including cases where one apparently acceptable metric cannot compensate for another failure.

## Common failure modes

### `<failure mode>`

- Signal:
- Likely causes:
- Checks:
- Corrective action:
- Effect on interpretation:

## Halt-on conditions

Stop downstream analysis when any of the following hold:

- `<condition>`
- `<condition>`
- `<condition>`

For every condition, record `evaluated: yes/no`, the evidence examined, and the resulting verdict. Unevaluated required conditions yield an indeterminate verdict, not a pass.

## Verdicts and permitted reporting

- **Pass:** `<criteria and permitted claim>`
- **Conditional pass:** `<criteria, restrictions, and required caveats>`
- **Fail:** `<criteria and prohibited downstream uses>`
- **Indeterminate:** `<missing evidence or unresolved condition>`

## Minimum output package

```text
<assay>-qa/
├── README.md
├── summary.md
├── verdict.yaml
├── metrics.tsv
├── halt-conditions.tsv
├── inputs/
│   └── manifest.tsv
├── figures/
└── logs/
```

Define the required contents and schema of each named file. `summary.md` must state the overall verdict and identify every halt-on condition evaluated.

## Completion check

- [ ] Every required QA metric was computed or explicitly marked unavailable
- [ ] Every halt-on condition was evaluated or marked unresolved
- [ ] The verdict follows the stated criteria
- [ ] The complete minimum output package exists
- [ ] Reporting language matches the verdict

## Companion Skills

- `<relative path>` — `<when it should also be loaded>`
```

Use the existing matching subject directory and its transitional subject prefix in `name`. If the guidance is externally sourced, replace `provenance: internal` with valid `sources:` metadata; never include both.
````

#### Repetition 3 — verbatim

````text
```markdown
---
name: <modality>-qa
description: Use when assessing whether <modality> measurements are trustworthy for downstream inference, from source ingestion through delivery of the QA package.
archetype: measurement-qa
provenance: internal
---

# <Modality> QA

## Scope

Define the measurement product being evaluated, the downstream assumptions it must support, and explicit exclusions.

## Sources and ingestion

- Accepted inputs and required metadata
- Input integrity and provenance checks
- Parsing, normalization, or construction steps that affect interpretation
- Expected units, identifiers, dimensions, and assay-specific controls

## Pre-flight checklist

- Sample and assay metadata complete
- Expected controls present
- Files readable and mutually consistent
- Sample identities and experimental design reconcile
- Required software/reference versions recorded

## QA metrics

| Metric | What it evaluates | Calculation/input | Expected range or decision rule | Caveats |
|---|---|---|---|---|
| `<metric>` | `<measurement property>` | `<method>` | `<rule>` | `<limitations>` |

## Common failure modes

### <Failure mode>

- **Signal:** What reveals the problem
- **Likely causes:** Plausible assay, ingestion, or construction causes
- **Impact:** Which downstream assumptions or analyses are compromised
- **Resolution:** Corrective action or escalation
- **Recheck:** Evidence required after correction

## Halt-on conditions

| Condition | Evidence | Required action | Permitted override |
|---|---|---|---|
| `<condition>` | `<metric/check>` | Halt `<affected inference/workflow>` | `<none or documented authority>` |

State explicitly that every condition must receive an `evaluated`, `not evaluable`, or `not applicable` disposition; silence is not a pass.

## Minimum output package

```text
<modality>-qa/
├── README.md
├── summary.md
├── metrics.tsv
├── sample-status.tsv
├── halt-conditions.tsv
├── figures/
└── provenance/
    ├── inputs.tsv
    └── methods.md
```

Define the required columns and contents of every named file. `summary.md` must state the overall verdict, limitations, and the disposition of every halt-on condition.

## Verdict and reporting

Define the allowed verdicts, their decision rules, and language permitted for downstream reporting. Distinguish failure, indeterminate assessment, and limited fitness for a particular use.

## Success check

Confirm that:

- every pre-flight check and QA metric has a recorded result;
- every halt-on condition has a recorded disposition;
- the verdict follows the stated decision rules; and
- the complete minimum output package exists with the required contents.

## Companion Skills

- `../INDEX.md` — the skill index.
- `<relevant downstream method or analysis-discipline skills>`
```

This should be a `measurement-qa` leaf because its primary decision is whether the assay’s observed or derived measurements faithfully support downstream inference. Extend an existing leaf only if it concerns the same modality/product, decision, and loading context; otherwise create a new leaf in the existing matching subject directory. Name it for the modality operation—such as `<modality>-qa`—without encoding the archetype in the name.
````

### S3 with-doctrine results

#### Repetition 1 — verbatim

````text
- **Request A — SPLIT.** The existing `Bulk RNA-Seq QA` skill is primarily `measurement-qa`: it evaluates whether expression measurements are trustworthy and produces a per-cohort QA package. Choosing a differential-expression tool is a separate `method-guide` decision involving applicability, estimands, assumptions, model selection, fitting, and diagnostics. Extract the existing “Counts-based testing” material and the new DE-tool guidance into a dedicated leaf, while leaving only a routing pointer in `bulk-rnaseq-qa`.

- **Request B — SPLIT.** The supplied Frictionless skill combines a `normative-reference`—what `datapackage.json` means and must contain—with a `tool-guide`—how to operate `frictionless validate`. The authoring guide explicitly identifies Frictionless’s datapackage contract versus CLI tooling as a split case. Keep descriptor schema, invariants, examples, and conformance requirements in one leaf; create a separate CLI leaf covering installation/version assumptions, end-to-end validation, interpreting output, correcting common failures, rerunning, and a verified smoke test.
````

#### Repetition 2 — verbatim

````text
Request A — CREATE a new skill.

`bulk-rnaseq-qa` is a `measurement-qa` skill whose primary artifact is the per-cohort QA package. Choosing among DESeq2, edgeR, limma-voom, or continuous-scale alternatives is a separate model-selection decision with the `method-guide` archetype. It may be needed after QA or independently, so it fails the “same archetype, decision, and load task” test for extension.

Keep only boundary-level rules in the QA skill—such as prohibiting count models on TPM—and link to the new differential-expression method guide. The existing “Counts-based testing” material can seed that guide.

Request B — SPLIT the supplied skill.

The current Frictionless skill combines two independent contracts:

- What a `datapackage.json` means and must contain: `normative-reference`.
- How to operate `frictionless validate` end-to-end: `tool-guide`.

This is the exact split case identified by `skill-authoring`: the datapackage contract and CLI tooling have different archetypes, primary outcomes, and success tests. Retain a descriptor/schema skill with explicit conformance rules, and create a separate Frictionless CLI guide covering setup/version assumptions, a representative validation run, interpretation of output, correction of a common failure, rerun, and successful verification.
````

#### Repetition 3 — verbatim

````text
Request A — CREATE a new skill.

Choosing a differential-expression procedure is a `method-guide` decision: select a model/tool based on the data scale, design, assumptions, contrasts, and diagnostic needs. The supplied bulk RNA-seq skill is primarily `measurement-qa`, producing a per-cohort QA package and deciding whether measurements are trustworthy. Because the archetypes and primary decisions differ, extending it would violate the exactly-one-archetype rule.

Create a leaf such as `bulk-rnaseq-differential-expression`, and keep only a concise routing boundary in the QA skill. The new guide should absorb or elaborate the existing “Counts-based testing” and model-formula guidance, covering choices such as DESeq2, edgeR, limma-voom, and continuous-scale alternatives when counts are unavailable.

Request B — SPLIT the supplied skill.

The current Frictionless skill already combines two independently loadable contracts:

- What `datapackage.json` means and must contain: `normative-reference`.
- How to operate `frictionless validate` end-to-end: `tool-guide`.

This is precisely the split case identified by `skill-authoring`: “the datapackage contract vs. the CLI tooling.” Retain or create a normative Data Package leaf for schemas, invariants, provenance, and conformance. Extract a separate Frictionless CLI leaf covering installation/version assumptions, descriptor creation, a complete validation run, interpreting reports, correcting common failures, rerunning validation, and a verified smoke test.
````

## Baseline comparison and acceptance verdict

| Scenario | No-doctrine baseline | With-doctrine | Comparison and verdict |
|---|---|---|---|
| S1 — classification | 3/3 `analysis-discipline`; reasoning varied but was already directionally correct | 3/3 `analysis-discipline`; 3/3 explicitly applied the audit/justify boundary and a method-independent pre-interpretation gate, and tied the verdict to contract slots | **PASS.** The label remains correct while the reasoning becomes doctrine-specific and consistent. |
| S2 — authoring | 0/3 complete six-slot skeletons; 0/3 fixed output-package trees | 3/3 supplied sources/ingestion, pre-flight, a QA metrics table, common failure modes, halt-on conditions with explicit disposition, and a fixed minimum output-package tree | **PASS.** The doctrine produced the required structural convergence absent from baseline. |
| S3 — create/extend/split | Request A: 3/3 EXTEND; Request B: 3/3 EXTEND | Request A: 1/3 SPLIT/extract and 2/3 CREATE, with 3/3 separating a distinct `method-guide` and 0/3 EXTEND; Request B: 3/3 SPLIT | **PASS.** Both arms apply the archetype and independent-load criteria: DE selection is separated from measurement QA, and Frictionless CLI operation is split from the datapackage contract. |

**Overall verdict: PASS.** All three with-doctrine scenario families reached
their adjudicated designed outcomes. S1 materially differs from its baseline
through consistent doctrine-specific classification reasoning; S2 materially
differs through complete slot coverage, explicit halt disposition, and fixed
output-package structure. S3 cleanly separates both cross-archetype additions.
No doctrine repair was needed.

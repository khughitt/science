---
name: genomics-driver-selection
description: Use when analyzing driver-gene enrichment, dN/dS, dNdScv, replication-timing bias, or positive/negative selection signals from somatic mutation data, before interpreting a gene rank as selection.
archetype: analysis-discipline
sources: [dndscv]
---

# Driver and Selection Inference

Answers: regardless of the method, what must hold before a gene rank may be
interpreted as selection? Mutation counts are not exchangeable across gene,
cancer type, assay, or mutational process; raw mutation frequency is not a
selection test.

## Triggering condition

Gene-level selection, driver-gene enrichment, dN/dS, dNdScv, replication-timing
bias, or positive/negative selection analysis on somatic mutation data.

## Required reasoning / check / precommitment

- **Opportunity model.** Coding length, trinucleotide context, and local
  mutation-rate covariates per gene, recorded before ranking.
- **Context-aware method.** dNdScv or another context-aware method; raw mutation
  frequency is not a selection test.
- **Pathway membership.** For pathway-level tests, membership defined before
  looking at results, with overlapping pathways handled explicitly.
- **Hypermutator handling.** Recorded treatment of MSI/POLE/APOBEC hypermutators,
  which can dominate rankings.
- **Known-driver lists as priors only.** Used as validation or priors, never as
  circular evidence for discovering the same drivers.
- **Cohort stage and study heterogeneity.** Primary-only and treated/relapse
  cohorts are not silently pooled — therapy shifts both burden and selection —
  and large studies are not allowed to dominate driver estimates without
  modeling per-study effects.

## Decision rule or reasoning criteria

Run these bias audits before interpreting ranks:

1. Correlate gene score with coding length.
2. Correlate gene score with replication timing (or a proxy if available).
3. Stratify by cancer type and assay class.
4. Repeat with hypermutators excluded.
5. Check whether genes absent from targeted panels were treated as zero.
6. Compare known-driver enrichment against a matched negative-control gene set.

Separate positive selection, negative selection, and passenger burden. An audit
whose covariate is unavailable (e.g. no replication-timing proxy) must be
declared unrun: a rank may not be reported as unconfounded along an axis that was
not tested. If any available technical covariate (coding length, replication
timing, expression, panel enrichment, cancer-type specificity) explains the
ranking as well as the biological hypothesis, the result is confounded unless the
model adjusts for it.

## Outcomes (pass / fail / indeterminate, or branch/threshold)

- **Pass.** The signal survives covariate adjustment and every applicable bias
  audit; a context-aware model separates selection from technical covariates.
- **Fail (confounded).** An available technical covariate explains the ranking as
  well as selection and the model does not adjust for it.
- **Indeterminate.** Counts are too low (rare genes, small cohorts) to
  distinguish selection from noise, OR a bias axis could not be tested — the rank
  is indeterminate along that untested axis and may not be reported as
  unconfounded there.

## Halt / escalation

- The opportunity model is missing or cannot be verified for the mutation set
  (per-gene callable territory, coding length, and context are prerequisites; a
  rank may not be interpreted without them).
- Driver ranks correlate with coding length and no length-aware model is run.
- Validation is circular: a method tuned on CGC/Bailey drivers cannot use those
  same drivers as independent evidence of success.

## Required evidence & artifacts

Record the method, the covariates in the selection model, the negative-control
comparison, and the sensitivity results that change verdict interpretation. Place
this step under the workflow-result package `results/<workflow>/<slug>/` (see
[`../../data-management/conventions.md`](../../data-management/conventions.md) for
placement) and generate a `datapackage.json` descriptor for the directory (see
[`../../data-management/frictionless.md`](../../data-management/frictionless.md)
for descriptor format):

```
results/<workflow>/<slug>/driver_selection/
  datapackage.json
  input_manifest.json
  opportunity_model.parquet
  selection_covariates.parquet
  selection_results.parquet
  bias_audit.parquet
  selection_summary.md
```

The summary should state whether input calls and denominators were already
audited. If not, load `somatic-mutation-qa.md` first and complete that audit
before treating selection tests as verdict-bearing.

## Permitted reporting language

- Report "under positive selection" / "under negative selection" only after
  covariate adjustment and passing every applicable bias audit.
- Otherwise report the result as "confounded", "cannot distinguish selection from
  coding-length / expression / replication-timing bias", or "underpowered".
- Never present raw mutation frequency or a length-adjusted rank alone as
  evidence of selection.

## Success test

The opportunity model and every applicable bias audit were run before any gene
was called a driver, and every selection claim in the report uses only the
reporting language permitted by its audit outcome.

## Companion Skills

- [`somatic-mutation-qa.md`](somatic-mutation-qa.md) - input-call and denominator QA required before selection verdicts.
- [`mutational-signatures-qa.md`](mutational-signatures-qa.md) - signature decomposition and burden on the same cohort.
- [`../../study-design/power-floor-acknowledgement.md`](../../study-design/power-floor-acknowledgement.md) - low-power driver tests for rare genes.
- [`../../study-design/sensitivity-arbitration.md`](../../study-design/sensitivity-arbitration.md) - pre-committed arbitration for hypermutator, panel, and low-count sensitivities.

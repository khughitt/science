---
name: statistics-power-floor-acknowledgement
description: Use before interpreting null, weak, or boundary results from finite-sample analyses, especially pre-registrations, replication attempts, subgroup tests, and negative findings.
---

# Power-Floor Acknowledgement

Use before interpreting null, weak, or boundary results from finite-sample
analyses, especially pre-registrations, replication attempts, subgroup tests,
and negative findings.

A null result is only evidence against a proposition if the analysis had enough
resolution to detect the effect size that would matter. Otherwise it is an
underpowered non-arbitration.

## Define the Floor Before the Run

For each verdict-bearing test, state:

1. **Independent-unit n.** Patients, donors, studies, genes, clusters, or
   samples. Do not count repeated cells or bootstrap replicates as n.
2. **Alpha / decision threshold.** Include multiplicity or one-sided choices.
3. **Estimator and variance model.** t-test, Cox model, mixed model, bootstrap
   CI, Bayesian posterior contrast, permutation test, etc.
4. **Minimum detectable effect.** The smallest effect detectable with the
   planned n, alpha, and target power or posterior precision.
5. **Biologically meaningful effect.** The smallest effect that would change the
   proposition or decision.

If the detectable effect is larger than the meaningful effect, the analysis can
find large effects but cannot rule out meaningful smaller ones.

## Quick Rules

- Use independent units, not observations nested inside units.
- Compute power on the same scale as the verdict: log hazard ratio, standardized
  effect, odds ratio, rank correlation, AUROC, absolute fraction change.
- For equivalence or "absence of effect" claims, use equivalence bounds or
  interval exclusion. A non-significant p-value is not enough.
- For high-dimensional screens, account for multiplicity or define a screening
  threshold rather than pretending each test is standalone.
- For Bayesian analyses, report posterior interval width and prior sensitivity,
  not only posterior probability of direction.

## Common Failure Modes

- **Cell n inflation.** Thousands of cells from a few donors produce tiny
  cell-level p-values while donor-level evidence is weak.
- **Subgroup underpowering.** A cohort has adequate total n, but each stratum is
  too small for the planned contrast.
- **Bootstrap confusion.** More bootstrap resamples stabilize the interval but
  do not increase independent-unit information.
- **Null overclaim.** "No association" is reported when the CI still includes
  effects large enough to matter.
- **Multiplicity drift.** A threshold chosen for one test is used after many
  genes, cohorts, or sensitivity variants are tested.

## Verdict Language

Use language tied to the floor:

| Evidence state | Reporting language |
|---|---|
| Adequate power, interval excludes meaningful effect | evidence against meaningful effect |
| Adequate power, interval supports effect | supports effect |
| Underpowered, interval wide | unresolved / non-arbitrating |
| Direction consistent but imprecise | suggestive, needs replication |
| Diagnostics failed | model/data-limited, not interpretable as power result |

## Reporting

Include:

- independent-unit n and exclusions,
- target effect scale,
- alpha or decision rule,
- minimum detectable effect or interval-resolution statement,
- biologically meaningful effect threshold,
- verdict label if the observed result is underpowered.

When exact power is hard to compute, provide a conservative simulation or
interval-resolution statement. Do not omit the power floor because the model is
complex.

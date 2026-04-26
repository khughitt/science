---
name: statistics-survival-and-hierarchical-models
description: Use when designing or reviewing Cox, Weibull, AFT, frailty, mixed-effects, Bayesian hierarchical, or multi-dataset causal models.
---

# Survival and Hierarchical Models

Use when designing or reviewing Cox, Weibull, accelerated-failure-time,
frailty, mixed-effects, Bayesian hierarchical, or multi-dataset causal models.

These models are powerful because they borrow strength across units. They fail
when censoring, grouping, identifiability, or prior assumptions are treated as
implementation details rather than analysis assumptions.

## Pre-Flight Checklist

1. **Define the time origin.** Diagnosis, treatment start, biopsy, enrollment,
   relapse, and sequencing date answer different questions.
2. **Validate event coding.** Confirm event indicator polarity, censoring date,
   left truncation, competing risks, and impossible times.
3. **Name the grouping structure.** Patient, study, cohort, batch, tissue,
   cancer type, gene, and cell donor are not interchangeable random effects.
4. **State the estimand.** Hazard ratio, survival-time ratio, posterior contrast,
   marginal effect, direct effect, or total effect.
5. **Check confounder timing.** Do not adjust for mediators or post-exposure
   variables unless the estimand requires a direct effect.
6. **Plan model adequacy.** Diagnostics are part of the design, not optional
   post-hoc reassurance.

## Survival-Specific QA

| Check | Failure mode |
|---|---|
| Kaplan-Meier by exposure/group | Gross non-PH, coding errors, empty tails |
| Censoring distribution by group | Informative censoring or study artifacts |
| Schoenfeld residuals / time interaction | Proportional hazards violation |
| Log-log survival plot | PH shape mismatch |
| Event count per parameter | Unstable estimates and separation |
| Follow-up truncation sensitivity | Late sparse tails drive effect |

If PH fails, pre-specify whether to use time-varying effects, stratified Cox,
restricted mean survival time, or parametric models. Do not keep a Cox HR as a
single-number verdict when hazards clearly cross.

## Hierarchical Model QA

- Draw the data-generating hierarchy before coding the model.
- Include varying intercepts before varying slopes unless slopes are required by
  the estimand.
- Check whether group-level variance is identifiable with the available number
  of groups and observations per group.
- Use non-centered parameterizations when group-level variance is weakly
  identified or sampling is difficult.
- Report shrinkage behavior. Extreme groups should move toward the population
  mean unless the model has strong evidence otherwise.
- Do not compare group-specific posterior means as if they were independent
  fixed-effect estimates.

## Bayesian Diagnostics

Minimum requirements:

- R-hat near 1.00 for all verdict-bearing parameters.
- Effective sample size adequate for posterior means, intervals, and tail
  probabilities used in the verdict.
- No unresolved divergent transitions.
- Trace plots for key parameters and group-level scales.
- Posterior predictive checks on the outcome scale.
- Prior predictive checks when priors influence scale or sign.
- Sensitivity to weakly informative vs domain-informed priors when the posterior
  is data-sparse.

If diagnostics fail, fix the model or downgrade the verdict. Do not increase
draws to hide divergences or non-identifiability.

## Common Failure Modes

- **Pseudoreplication.** Cells, variants, or genes are treated as independent
  when the real independent unit is donor, patient, or study.
- **Collider adjustment.** Adjusting for a downstream variable blocks or
  distorts the effect being estimated.
- **Sparse random effects.** A random slope per group with too few observations
  produces prior-driven effects.
- **Complete separation.** Logistic or survival models produce extreme
  estimates without explicit separation handling.
- **Post-hoc sensitivity arbitration.** Multiple sensitivity models are run,
  then the preferred story is chosen after seeing results.

## Reporting

Report:

- time origin, endpoint, censoring rules,
- grouping hierarchy and independence unit,
- formula and covariate timing,
- prior and parameterization if Bayesian,
- diagnostics and failed diagnostics,
- sensitivity-arbitration rule,
- verdict downgrades caused by model inadequacy.

## Minimum Artifacts

Generate a `datapackage.json` for this directory; see [`../data/frictionless.md`](../data/frictionless.md).

```
results/<analysis>/model_qa/
|-- input_manifest.json
|-- analysis_dataset.parquet
|-- model_formula_or_config.yaml
|-- censoring_and_event_audit.parquet
|-- survival_diagnostics.parquet
|-- posterior_or_fit_diagnostics.parquet
|-- posterior_predictive_or_residual_checks.parquet
|-- sensitivity_results.parquet
`-- qa_summary.md
```

The summary should state the independent unit, grouping structure, diagnostics
that failed, and any verdict downgrade caused by censoring, non-PH,
non-identifiability, divergences, or sensitivity disagreement.

## Companion Skills

- [`sensitivity-arbitration.md`](sensitivity-arbitration.md) - pre-committed verdict rules for model diagnostics and sensitivity runs.
- [`power-floor-acknowledgement.md`](power-floor-acknowledgement.md) - independent-unit power floors for survival and hierarchical models.
- [`compositional-data.md`](compositional-data.md) - denominator and zero-handling rules for fraction-valued model inputs.

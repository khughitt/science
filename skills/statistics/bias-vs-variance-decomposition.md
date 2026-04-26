---
name: statistics-bias-vs-variance-decomposition
description: Use when choosing estimators, replicate counts, correction terms, simulation designs, or sensitivity analyses where stochastic noise and systematic error could be confused.
---

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

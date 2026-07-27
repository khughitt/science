---
name: statistics-bayesian-workflow
description: Use when building, fitting, or reviewing a Bayesian/probabilistic model — prior choice, MCMC sampling, convergence diagnostics, posterior-predictive and calibration checks, prior sensitivity, and Bayesian model comparison.
archetype: method-guide
sources: [baygent-skills, gelman-bayesian-workflow, vehtari-loo]
---

# Bayesian Workflow

Use when building, fitting, or reviewing a Bayesian model. The workflow is a
gated sequence, not a menu: a downstream step is only meaningful once the earlier
gate has passed. Most of these steps an agent will skip unless prompted — that is
exactly why they are written down.

## The Gated Sequence

1. **Formulate the model and name the estimand.** What quantity carries the
   verdict — a contrast, a coefficient, a predicted quantity?
2. **Prior predictive check — before fitting.** Simulate parameters from the
   priors, push them through the likelihood, and confirm the *implied data* are
   physically plausible. Absurd prior-predictive ranges mean the priors are wrong;
   fix them before touching real data.
3. **Fit.** Sampler-agnostic (NUTS/nutpie, NumPyro, emcee). Two habits:
   - Use a **descriptive, reproducible seed** (e.g. `sum(map(ord, name))`), not a
     bare `42`, so the seed records which analysis it belongs to.
   - **Save the fitted object / InferenceData immediately** — diagnostics and
     comparison downstream depend on it.
4. **Convergence gate.** Do not read the posterior until: R-hat ≤ 1.01 on every
   verdict-bearing parameter, ESS ≥ 100·chains, zero divergences, tree-depth not
   saturated, E-BFMI healthy. A failed gate is fixed by re-parameterizing or
   re-specifying — **not** by raising the draw count to bury divergences.
5. **Model criticism vs calibration — keep them distinct.**
   - *Posterior predictive checks* assess in-sample fit (can the fitted model
     reproduce the observed data). Necessary, but **not** calibration.
   - *Calibration* is out-of-sample: **LOO-PIT** (distinct from ordinary in-sample
     PIT), **randomized PIT** for discrete outcomes, and **empirical coverage** on
     held-out or simulated data; **simulation-based calibration (SBC)** when a
     simulator exists. Never present a good posterior-predictive fit *as* evidence
     of calibration — a model can fit the data it was trained on and still be
     miscalibrated out of sample.
6. **Prior/likelihood sensitivity.** Power-scale the prior and the likelihood
   (PSIS, no refit) and flag any conclusion that hinges on the prior. See
   Load the `science-study-design` skill.
7. **Model comparison.** Out-of-sample predictive comparison, not variable
   selection. See the Bayesian arm of
   [`likelihood-model-comparison.md`](likelihood-model-comparison.md).
8. **Report the interval, not the point.** Report an HDI / credible interval; no
   interval width is magically "right". State the estimand, the priors, the failed
   gates, and any verdict downgrade they force.

## Common Failure Modes

- **Point estimate with no interval.** A posterior mean alone hides the width that
  is the whole reason to be Bayesian.
- **Raising draws to hide divergences.** Divergences are a geometry problem, not a
  sample-size problem; re-parameterize (see the non-centered fix in
  [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md)).
- **PPC passed, called it calibrated.** In-sample fit reported as out-of-sample
  calibration.
- **Prior smuggled into the verdict.** A conclusion that flips under a defensible
  alternate prior, reported as if prior-independent.

## Deeper Dive

The tool-specific version of this workflow — PyMC + ArviZ specifics (nutpie,
`arviz_stats.diagnose()`, PreliZ prior elicitation, regularized-horseshoe sparsity)
— is the upstream `bayesian-workflow` skill by Alexandre Andorra
([baygent-skills](https://github.com/Learning-Bayesian-Statistics/baygent-skills)).

## Companion Skills

- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) — non-centered parameterization and grouped-data diagnostics.
- Load the `science-study-design` skill — the power-scaling prior-sensitivity step and how it arbitrates the verdict.
- [`likelihood-model-comparison.md`](likelihood-model-comparison.md) — the LOO/ELPD/stacking model-comparison step.

---
name: statistics
description: Use when designing, building, fitting, comparing, or reviewing a finite-sample statistical model — survival / hierarchical / mixed-effects, compositional, time-series / longitudinal, likelihood model comparison (AIC/BIC/LRT, bootstrap CIs), population-genetics likelihood, or Bayesian workflow (priors, MCMC, convergence, calibration).
provenance: internal
---

# Statistics — Model-Fitting Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a finite-sample statistical model is being designed,
built, constructed, fit, compared, analyzed, or reviewed — distinct from the
rigor commitments and verdict certifications that route to
`../study-design/SKILL.md`.

## Scope boundary

Covers the model's structure, fit, and comparison across the six modeling
families below. Excludes the rigor wrapper — pre-registration, replicate/power
justification, estimator certification, sensitivity arbitration, causal
identification, and bias/variance reasoning (see `../study-design/SKILL.md`).
The two routers are composable axes: a task may load both — pre-registering a
Cox model loads this router for the model family and `study-design` for the
commitment.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `survival-and-hierarchical-models.md` | designing or reviewing Cox / Weibull / AFT / frailty / mixed-effects / Bayesian-hierarchical / multi-dataset models, or when repeated cells / genes / samples inside a donor or study are not independent observations | the outcome is not time-to-event and there is no grouping, censoring, hierarchical, or repeated-measure structure — a single-level i.i.d. model suffices |
| `compositional-data.md` | analyzing proportions, fractions, cell-type composition, microbiome relative abundance, clone fractions, topic mixtures, or deconvolution outputs — anything constrained to sum to one | features are unconstrained counts or continuous measurements |
| `time-series-and-longitudinal-models.md` | designing or reviewing repeated-measure, wearable, sensor, EMA, actigraphy, symptom-diary, cross-lag, or longitudinal analyses needing explicit time origin, cadence, lag, and within-unit dependence | measurements are cross-sectional (one row per unit, no time axis) |
| `likelihood-model-comparison.md` | comparing parametric models by likelihood — AIC / BIC / LRT, nested vs non-nested, identifiability and rare-event precision audits, bootstrap CIs, or Bayesian out-of-sample comparison (PSIS-LOO / ELPD / stacking) | fitting a single model with no competing model to rank |
| `population-genetics-likelihood.md` | constructing or fitting Wright-Fisher / Moran / binomial-segregation+selection likelihoods and testing selection against a neutral null | no allele-frequency, segregation, or selection-vs-drift question |
| `bayesian-workflow.md` | building, fitting, or reviewing a Bayesian / probabilistic model — priors, MCMC, convergence, posterior-predictive / calibration, prior sensitivity, Bayesian model comparison | a frequentist point estimate or test suffices and no posterior is needed |

## Decision / compose order

Leaves are independent; several may apply to one analysis. Choose by model
family and data structure, not by discipline.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring router: `../study-design/SKILL.md`

## Success test

A modeling task routes to the correct leaf with no methodology read from this
router.

## Companion Skills

- `../study-design/SKILL.md` — the rigor-commitment and verdict-certification axis; compose with this router.
- `../literature/SKILL.md`, `../epistemics/SKILL.md` — high-level research methodology; this router is the quantitative-modeling layer beneath them.
- `../writing/SKILL.md` — reporting statistical decisions in pre-regs and interpretations.
- `../data-management/SKILL.md` — input-data conventions; some modeling decisions depend on data shape (count vs continuous, zero-inflation).

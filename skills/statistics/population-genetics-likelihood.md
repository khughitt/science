---
name: statistics-population-genetics-likelihood
description: Use when constructing or fitting population-genetics likelihoods — Wright-Fisher, Moran, or binomial-segregation+selection models (e.g. ecDNA copy number) — and comparing selection against a neutral null.
---

# Population-Genetics Likelihood

Use when constructing or fitting population-genetics likelihoods — Wright-Fisher
(WF), Moran, or binomial-segregation+selection models (e.g. ecDNA copy-number
evolution) — and comparing a selection model against a neutral null.

This leaf owns *what likelihood to write and what it assumes*. The machinery for
comparing the resulting models (AIC/BIC/LRT, numerical precision, bootstrap) is
in [`likelihood-model-comparison.md`](./likelihood-model-comparison.md); load it
as a companion.

## Likelihood Construction

State the generative process explicitly before fitting:

- **Wright-Fisher.** Non-overlapping generations, multinomial/binomial sampling of
  the next generation; selection enters as a fitness reweighting. The diffusion
  approximation gives a tractable continuous likelihood with drift ∝ selection
  and variance ∝ the per-generation sampling scale.
- **Moran.** Overlapping generations, one birth-death per step; appropriate when
  the population turns over continuously rather than in discrete generations.
- **Binomial-segregation+selection (ecDNA).** Per division, copies segregate
  binomially to daughters; selection reweights cells by copy number. The
  continuous (Gaussian-diffusion) approximation parameterizes a drift term
  (selection) and a per-generation variance scale (segregation noise).

For each, write down: the state variable and its scale (keep it identical across
the models you will compare, for likelihood comparability), the transition
kernel, the selection parameter, and the variance/noise parameter.

## Neutral Null vs Selection Alternative

- The **neutral null** fixes the selection parameter at zero while still estimating
  the variance/noise scale. Drift alone must be given a fair chance to explain the
  data.
- The **selection alternative** frees the selection parameter.
- A **Wright-Fisher continuous-trait alternative** can serve as a non-nested rival
  to a discrete segregation model; compare it via AIC on a common response scale
  (see the companion leaf), not LRT.

## Independent Unit and Time Axis

- State the time axis — generations, cell-cycles, or sampling time — and how it
  maps to the data. The axis must be common across compared models.
- State the independent unit: per-cell, per-clone, or per-lineage. Cells sharing
  ancestry are not independent draws.
- State the effective population size assumption wherever the likelihood depends
  on it.

## Identifiability and Confounding

- **Drift vs selection are confounded** at small effective population size or few
  generations: strong drift mimics selection in a single trajectory. Confirm the
  data can separate them before reading a selection verdict.
- **Segregation variance vs selection.** A high per-generation variance scale can
  absorb apparent directional change; estimate the variance scale rather than
  fixing it by convention.

## Halt-On Conditions

- The transition variance scale / time axis is **neither identified from data nor
  pre-registered** as an estimated / profiled / sensitivity parameter. A model
  that *estimates* its per-generation variance scale on a stated
  per-cell-generation axis is ready — a known effective population size is not
  required.
- Drift and selection are not separable on the available data and the analysis is
  nonetheless being read as a selection verdict.

## Verdict Scope

A selection signal fit on a single cohort is scoped to that cohort: because drift
and selection are confounded at low effective size, a single-cohort fit cannot
rule out cohort-specific drift. Report the within-cohort verdict, and require
independent replication in another cohort before promoting a cross-cohort
selection claim.

## Companion Skills

- [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) — the AIC/BIC/LRT, numerical-precision, and bootstrap machinery for comparing these models.
- [`../data/genomics/copy-number-sv-qa.md`](../data/genomics/copy-number-sv-qa.md) — QA for the per-cell CN calls these likelihoods are fit to.
- [`power-floor-acknowledgement.md`](./power-floor-acknowledgement.md) — the minimum selection coefficient resolvable at the available cell/generation count.
- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-committing how drift-vs-selection sensitivity passes resolve the verdict.

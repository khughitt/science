---
name: statistics-likelihood-model-comparison
description: Use when comparing parametric models by likelihood — AIC, BIC, likelihood-ratio tests, nested vs non-nested comparison, identifiability and rare-event numerical-precision audits, and bootstrap confidence intervals on the selected model.
---

# Likelihood Model Comparison

Use when comparing parametric models by likelihood: AIC, BIC, likelihood-ratio
tests (LRT), nested vs non-nested comparison, bootstrap CIs, and the
identifiability / numerical-precision checks that decide whether a comparison is
even well-posed.

Model comparison is where a fitting bug or an incomparable likelihood quietly
becomes a verdict. The discipline is to confirm the comparison is well-posed —
same data, comparable likelihoods, identified parameters, converged optimizer —
before reading off AIC/BIC/LRT.

## Pre-Flight Checklist

1. **Enumerate the candidate set and name the null.** State every model being
   compared and which one is the null / reference.
2. **Classify nested vs non-nested.** Models are nested when one is a parameter
   restriction of another (e.g. a selection coefficient fixed at zero). Nesting
   decides whether LRT is available.
3. **Confirm identical data and response.** AIC/BIC are comparable only across
   models fit to the *same observations on the same response scale*. A model on
   log-CN and one on natural-scale CN are not AIC-comparable without a
   change-of-variable correction (below).
4. **Check identifiability.** Confirm each parameter is identified by the data
   (not at a boundary, not redundant). Unidentified parameters make the parameter
   count — and therefore AIC/BIC — meaningless.
5. **State which metric is verdict-bearing.** Pre-commit whether AIC, BIC, or LRT
   decides the verdict and which others are reported alongside.

## AIC vs BIC vs LRT

| Tool | Requires | Use for |
|---|---|---|
| LRT | strictly nested models + regularity (parameter not on a boundary) | a formal test of whether the extra parameter(s) improve fit |
| AIC | identical data + comparable likelihood normalization | predictive-accuracy ranking, including non-nested models |
| BIC | identical data + comparable normalization; meaningful n | consistency-oriented selection; penalizes parameters harder as n grows |

- LRT on a parameter at its boundary (e.g. a variance or selection coefficient
  fixed at zero) does **not** have the usual χ² null; use the appropriate mixture
  distribution or a parametric-bootstrap null.
- A small ΔAIC/ΔBIC is not a decision. Report the difference and its bootstrap
  stability, not just the argmin.

## Re-Expression for Comparability

Non-nested likelihoods are often expressed on different variable scales or time
axes. To compare them:

- Re-express all models onto a **common response scale / common time axis** before
  fitting, OR
- Apply the **change-of-variable Jacobian** to the log-likelihood when a model is
  fit on a transformed variable. Comparing AIC across an untransformed and a
  log-transformed response without the Jacobian term is a category error — the
  densities are not on the same measure.

State explicitly which models were re-expressed and what the Jacobian correction
was.

## Numerical-Precision Audit

Likelihoods that sum over rare events or large state spaces underflow silently.

- Evaluate and accumulate log-likelihoods in **log space** (logsumexp); never log a
  summed probability.
- Check for underflow / `-inf` contributions and for terms dominated by a single
  state.
- Confirm optimizer convergence (gradient norm / relative tolerance), not just a
  returned value. Re-fit from multiple starts for multimodal likelihoods.
- Record the minimum representable likelihood contribution and whether any
  verdict-bearing term is near it.

## Bootstrap Confidence and Selection Stability

- Report bootstrap CIs for the parameters and for the ΔAIC/ΔBIC between the top
  models (parametric bootstrap for generative models; nonparametric for
  exchangeable data).
- Report **selection stability**: across bootstrap resamples, how often does the
  selected model win? A model that wins by ΔAIC but only 55% of the time is not a
  confident selection.

## Common Failure Modes

- **Incomparable likelihoods.** Different data, different response scale, or a
  transform without its Jacobian.
- **LRT on non-nested or boundary models.** Wrong reference distribution.
- **Argmin worship.** Treating the lowest AIC as decisive regardless of ΔAIC size
  or selection stability.
- **Unconverged or single-start optimization.** A local optimum reported as the
  MLE.
- **Counting unidentified parameters.** Inflated or deflated penalties.

## Reporting

Report the candidate set, nesting structure, the data/response scale shared by
all models, any re-expression + Jacobian, the verdict-bearing metric and its
value, ΔAIC/ΔBIC with bootstrap CIs and selection stability, and the convergence
diagnostics. State any verdict downgrade caused by incomparability,
non-identifiability, or selection instability.

## Companion Skills

- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-commit which comparison metric is verdict-bearing and which are reported alongside.
- [`power-floor-acknowledgement.md`](./power-floor-acknowledgement.md) — the minimum effect a likelihood comparison can resolve at the available n.
- [`population-genetics-likelihood.md`](./population-genetics-likelihood.md) — a domain consumer: constructing the pop-gen likelihoods this leaf then compares.

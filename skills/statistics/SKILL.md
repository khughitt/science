---
name: statistics
description: Use when designing, pre-registering, or reviewing finite-sample quantitative analyses, especially bootstrap, permutation, Monte Carlo, downsampling, MCMC, power, bias-vs-variance, sensitivity arbitration, or any analysis that would otherwise choose a round-number default.
---

# Statistics

Practical guidance for designing and pre-registering quantitative analyses
in Science projects. The principles here apply across disciplines wherever
a quantitative claim is being made; the examples are drawn from
bioinformatics + meta-analysis but generalize.

## Principles

1. **Lock parameters by measurement, not convention.** Anywhere you would
   reach for a default like "1000 bootstrap replicates" or "10000
   permutations", first ask what precision you need. For point
   estimators, require replicate-induced SE to be small relative to the
   signal. For p-values or tail probabilities, require an explicit
   Monte Carlo SE / minimum-attainable-p check. If the answer is
   unknown, run a small pilot and lock the value with a pre-committed
   decision rule. See
   [`replicate-count-justification`](./replicate-count-justification.md).

2. **Distinguish bias from variance before you reach for an estimator.**
   Averaging cancels variance, not bias. Naming your estimator's bias
   structure prevents wasting compute and leads to better corrections.
   See [`bias-vs-variance-decomposition`](./bias-vs-variance-decomposition.md).

3. **Pre-commit sensitivity-arbitration rules.** A pre-registered analysis
   with N sensitivity passes can produce up to 2^N possible "interpretation
   stories" post hoc. State up front which flags caveat the verdict and
   which can override it, and what the override condition is. See
   [`sensitivity-arbitration`](./sensitivity-arbitration.md).

4. **Acknowledge the power floor explicitly.** Before running any
   verdict-bearing test, compute and state the minimum effect detectable
   at your planned n + α + estimator. This prevents post-hoc relabelling
   of nulls as "evidence of absence" and forces explicit choice between
   underpowered exploratory and adequately-powered confirmatory framings. See
   [`power-floor-acknowledgement`](./power-floor-acknowledgement.md).

5. **A pre-registration amendment is not a new pre-registration.** When a
   follow-up task tests the same hypothesis with the same contrasts but a
   different operationalisation, structure the new pre-reg as an
   amendment that inherits §-by-§ from the parent. Don't re-state what
   didn't change. See
   [`prereg-amendment-vs-fresh`](./prereg-amendment-vs-fresh.md).

6. **Model the independent unit.** Repeated cells, genes, mutations, or samples
   inside a donor/study are not independent observations. For survival,
   multi-cohort, mixed-effect, or Bayesian hierarchical analyses, see
   [`survival-and-hierarchical-models`](./survival-and-hierarchical-models.md).

7. **Respect compositional constraints.** Fractions, proportions, and mixture
   outputs require denominator, zero-handling, and log-ratio decisions before
   ordinary regression or correlation. See
   [`compositional-data`](./compositional-data.md).

## When to invoke

Use this skill any time you are:

- Pre-registering a quantitative analysis (especially under a Science
  project's `doc/pre-registrations/` flow).
- Reviewing or critiquing someone else's pre-registered analysis.
- Choosing values for resampling counts (bootstrap, permutation, MC),
  random seeds, or stopping rules.
- Deciding whether to apply a bias correction (Miller-Madow, jackknife,
  bootstrap-bias-correction, Hodges-Lehmann, etc.).
- Resolving conflicting sensitivity passes after a run.
- Designing survival, mixed-effect, or hierarchical Bayesian models.
- Analyzing proportions, cell fractions, deconvolution outputs, or other
  compositional measurements.

## Companion Skills

- [`research`](../research/SKILL.md) — high-level research methodology;
  this skill is the quantitative-design layer beneath it.
- [`writing`](../writing/SKILL.md) — how to report statistical
  decisions in pre-regs and interpretations.
- [`data`](../data/SKILL.md) — input-data conventions; some statistical
  decisions depend on data characteristics (e.g., zero-inflation,
  count vs continuous).

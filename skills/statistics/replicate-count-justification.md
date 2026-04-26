# Replicate-Count Justification

How to choose the number of replicates (R) for stochastic estimators
without falling back to "1000 because that's what the tutorial said".
This applies directly to point-estimate replication (bootstrap summaries,
Monte Carlo integration, multinomial downsampling) and gives separate
checks for p-values, MCMC, and multiple imputation.

## The problem

Whenever an analysis involves stochastic resampling, someone has to pick
how many replicates to draw. The default is almost always a round number
inherited from a tutorial: 1000 bootstrap iterations, 10,000 permutations,
4 chains × 2000 draws. These defaults are sometimes adequate, sometimes
wasteful, and sometimes too small — but the convention prevents anyone
from finding out which.

The fix is mechanical: **lock R via a measured stopping rule matched to
the estimand.** For point estimators, compare replicate-induced variance
to between-unit signal variance. For p-values, compare Monte Carlo
uncertainty to the alpha / decision margin. For MCMC and multiple
imputation, use their native diagnostics.

## Rule for point estimators

State this in your pre-registration before any verdict-bearing computation:

> For replicate count R, the smallest R such that
> `SE_replicates(R) / SD_signal ≤ θ` is locked, where:
> - `SE_replicates(R)` is the standard error introduced by stochastic
>   replication at R replicates,
> - `SD_signal` is the standard deviation of the signal of interest
>   across the relevant unit of analysis (subjects, cells, genes, …),
> - `θ` is the pre-committed threshold (default `0.20`).

Pilot the ratio empirically before committing. Lock R from the pilot,
then proceed.

## Why a ratio, not a target SE?

Absolute SE targets ("SE ≤ 0.005") look principled but are scale-
dependent and decouple from what actually matters for your verdict —
*can the resampling noise plausibly flip the inference?* If your between-
unit signal SD is 0.001 then SE = 0.005 is huge; if it is 1.0 then SE =
0.005 is wasteful. The ratio formulation auto-scales: it asks the right
question regardless of estimator units.

## Why θ = 0.20?

At ratio = 0.20, replicate noise contributes at most 4% to the variance
of the combined estimator (since variances add: `Var_total ≈ Var_signal +
Var_replicates = Var_signal × (1 + 0.04)`). That is small enough that
replicate noise is unlikely to flip a verdict at the magnitude any
realistic study can resolve, but not so tight (e.g., 0.05) that you burn
compute for no observable benefit.

Adjust θ for the application:
- **High-stakes confirmatory inference** with a single decisive test:
  consider 0.10.
- **Exploratory or pilot analyses** with many parallel tests: 0.30 is
  often acceptable.
- **Default in absence of strong reason:** 0.20.

State your θ in the pre-registration regardless.

## How to estimate `SE_replicates(R)`

For most point-estimate replication, this is `SE_single / sqrt(R)`,
where `SE_single` is the within-unit standard deviation across
replicates. Estimate `SE_single` from a pilot at `R_max` (e.g., 20) and
use that fixed `SE_single` to scale to any candidate R:

```python
# Pilot: for each unit (cell / patient / sample), draw R_MAX replicates
H[unit, replicate]  # shape (n_units, R_MAX)

SE_single = H.std(axis=1, ddof=1)  # per-unit single-replicate SD
SE_replicates_at_R = sqrt(mean(SE_single**2)) / sqrt(R)  # RMS noise, not mean absolute noise

mean_per_unit_at_Rmax = H.mean(axis=1)
SD_signal = mean_per_unit_at_Rmax.std(ddof=1)

ratio_at_R = SE_replicates_at_R / SD_signal
```

Pick the smallest R such that `ratio_at_R ≤ θ`. If even `R = 1` already
passes, lock R = 1 — no replication needed.

For non-linear verdict statistics (median of patients, max over genes,
thresholded classifier score), validate the locked R by rerunning the
whole verdict statistic on several independent replicate seeds. The
verdict should not change solely because of replicate seed.

## How to estimate `SD_signal`

`SD_signal` is the SD of your unit-level estimator across the population
you are inferring over. For a per-patient median entropy: SD across
patients of the per-patient mean estimate. For a per-gene effect size:
SD across genes of the per-gene point estimate. The pilot must include
enough units to estimate this stably (≥ 50 in most cases; the pilot
example below uses 200).

A subtle gotcha: if you compute `SD_signal` across only one stage / one
condition / one cluster, you can underestimate it. Compute over the
unit-level pool you are actually averaging across in the verdict-bearing
step.

## Point-estimator pilot pattern

```python
# 1. Sample units (cells, patients, …) to participate in the pilot.
pilot_units = sample(units, n=200, seed=PILOT_SEED)

# 2. For each unit, draw R_MAX = 20 independent replicates of the
#    estimator. Store H[unit, replicate].

# 3. Estimate SD_signal from all R_MAX replicates. For each candidate R
#    in {1, 2, 5, 10, 20}, compute SE_replicates(R) and the ratio.

# 4. Lock R = smallest R with ratio ≤ θ. Document the table in
#    the pre-registration.
```

This adds one short script to the pre-registration timeline (typically
< 5 minutes of compute) and replaces an arbitrary lock with a defensible
one. It also surfaces structural problems early — if no R passes at
R_max = 20, your stochastic noise is comparable to your biological
signal and you have a bigger problem than replicate counts.

## Rule for permutation / Monte Carlo p-values

The `SE_replicates / SD_signal` ratio is not the right diagnostic for a
p-value. For a Monte Carlo p-value estimated from B random permutations:

```text
p_hat = (b + 1) / (B + 1)
MCSE(p_hat) = sqrt(p_hat * (1 - p_hat) / (B + 1))
minimum attainable p = 1 / (B + 1)
```

Lock B so both are true:

- The minimum attainable p is below the smallest alpha you intend to
  interpret after multiplicity adjustment.
- `p_hat ± 2 * MCSE` cannot cross the pre-committed decision boundary,
  or the result is labelled Monte-Carlo-ambiguous and escalated to a
  larger B.

For example, B = 999 cannot support a claim at p < 0.001 because the
minimum attainable p is 0.001. That may be fine for an exploratory
screen and inadequate for a confirmatory tail claim.

## Worked example: per-cell scRNA-seq downsampling entropy

Context: per-cell Shannon entropy of a multinomial downsample of UMI
counts, used as a "potency" metric. R is the number of independent
multinomial draws per cell, averaged before downstream stats.

Pilot: 200 random plasma cells × R_max = 20 multinomial draws to UMI
budget = 1000.

| R  | SD_signal (between-cell) | SE_replicates(R) (per-cell, scaled) | ratio | passes (≤ 0.20) |
|----|--------------------------|-------------------------------------|-------|-----------------|
| 1  | 0.0281                   | 0.0039                              | 0.139 | ✓               |
| 2  | 0.0278                   | 0.0028                              | 0.100 | ✓               |
| 5  | 0.0276                   | 0.0018                              | 0.064 | ✓               |
| 10 | 0.0277                   | 0.0012                              | 0.045 | ✓               |
| 20 | 0.0277                   | 0.0009                              | 0.032 | ✓               |

R = 1 already passes. Lock R = 1. Saved ~5x compute over the conventional
"5 replicates" default with no precision cost.

## When the rule says "more replicates than you expected"

Sometimes the pilot reveals that even R = 100 doesn't pass θ = 0.20.
This is a real signal, not a problem with the rule:

- **Your single-unit estimator is noisier than you thought** relative
  to the cross-unit signal. Either find a better estimator, increase
  per-unit sample size (more cells per patient, more reads per cell),
  or accept that the analysis is fundamentally underpowered and
  reframe the verdict bins accordingly.
- **The signal you're trying to resolve is smaller than the
  measurement floor of your data.** Stop and reconsider whether the
  experiment has the resolution to answer the question.

In either case, the pilot has surfaced a problem that would otherwise
have appeared as a confusing null in the main run.

## What this rule does NOT cover

- **Bias, not variance.** Averaging cancels variance but not bias. If
  your estimator has a bias that doesn't shrink with R (e.g., the
  Miller-Madow bias of plug-in Shannon entropy is `−(K-1)/(2N)` for
  any number of replicates), R won't help. Write the bias term down
  explicitly before spending compute on more replicates.
- **MCMC convergence.** For Bayesian sampling, the right diagnostic is
  R-hat / ESS, not this ratio. The ratio rule applies to *post-warmup*
  effective sample size for posterior summary statistics — it does not
  replace convergence diagnostics, divergent-transition checks, trace
  inspection, or posterior predictive checks. The principle is the same:
  pilot, measure, lock.
- **Multiple imputation under MAR.** The Rubin total variance
  decomposition `T = V_within + (1 + 1/m) × V_between` gives a closed-
  form rule for choosing m; use it directly. The principle of
  "measure, don't pick a round number" still applies.

## Reporting in the pre-registration

In the pre-reg's `Operationalisation` section, include:

1. **The candidate range.** "R ∈ {1, 2, 5, 10, 20}" or whatever your
   pilot grid is.
2. **The threshold θ or p-value precision rule.** "Locked at θ = 0.20"
   for point estimators, or "B escalates until MCSE cannot cross alpha"
   for permutation / Monte Carlo p-values.
3. **The pilot procedure.** N units sampled, seed, R_max.
4. **The decision rule.** "Smallest R with ratio ≤ θ."
5. **The pilot table.** Locked at lock-down time, before any
   verdict-bearing computation.

The pilot itself does not need its own pre-registration if it produces
no verdict-bearing output and the decision rule is fully pre-committed.
It IS a pre-reg-relevant step and goes in the operationalisation
section as if it were a deviation log entry.

## Why this matters

Replicate counts are one of the most common silent assumptions in
quantitative analyses. "1000 bootstraps" appears in tens of thousands
of papers without justification. Most are fine; some are wasteful by an
order of magnitude; a few are dangerously underpowered. The cost of
making this rule explicit is one short script per analysis. The benefit
is a reviewer-defensible justification that scales to any resampling
procedure and reveals real measurement problems early instead of
producing confusing nulls late.

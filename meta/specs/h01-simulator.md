# H01 Simulator Spec

Design spec for the simulator used to test `hypothesis:h01-stochastic-revisiting`.
This is a design document, not an implementation plan — implementation choices that do not affect the comparability of policies are left to the build task.

## Purpose

Produce a minimal, self-contained simulator in which proposition-evidence allocation policies can be compared on known ground truth, under controlled noise regimes.
The simulator is the only instrument currently specified for testing H01; its results directly determine whether the hypothesis survives or is disconfirmed.

## Scope

**In scope**

- Synthetic propositions with binary ground-truth labels drawn from a configurable prior.
- Per-action noisy signals conditioned on each proposition's true label.
- Bayesian posterior update on accumulated signals.
- Fixed per-run evidence budget.
- At least three policies for allocating the budget:
  1. Hard-gating baseline.
  2. Constant-probability stochastic revisiting.
  3. Uncertainty-scaled stochastic revisiting (e.g. Thompson sampling or a UCB-style rule).
- Metric collection: recall of ground-truth-true propositions, calibration of final posteriors, cumulative regret relative to an oracle allocation.
- Parameter sweep over noise level, number of propositions, budget size, and prior skew.
- A correlated-bias variant (see below) to probe the H01 disputing-evidence path.

**Out of scope**

- Realistic domain content. Propositions are abstract; no actual science claims are being evaluated.
- Any modelling of human-researcher behaviour, workflow friction, or tool UX. This is a pure policy-comparison instrument.
- Inference from simulator results to real tools. That is a separate bet and belongs to interpretation, not to the simulator itself.

## Model

**Propositions.** `N` propositions indexed `0..N-1`, each with a latent Boolean truth value `t_i ∈ {0, 1}` drawn from `Bernoulli(π)` with `π` configurable (default `0.5`).

**Signal model.** An action on proposition `i` produces a signal `s ∈ {0, 1}` drawn from `Bernoulli(p_+)` if `t_i = 1`, else from `Bernoulli(p_-)`, with `p_+ > p_-`.
The pair `(p_+, p_-)` parameterises the per-action noise level; `p_+ = 0.9, p_- = 0.1` is a clean regime, `p_+ = 0.6, p_- = 0.4` is noisy.

**Posterior update.** Beta-Bernoulli conjugate update on each proposition independently, with a configurable per-proposition prior (default `Beta(1, 1)`).

**Budget.** A total of `B` actions per simulation run, each action applied to exactly one proposition.

**Correlated-bias variant.** A subset `C ⊂ propositions` shares a latent pipeline-bias variable that shifts their per-action signal probabilities by a common offset.
This directly tests the H01 disputing-evidence failure mode: stochastic revisiting should be expected to help less (or not at all) when errors on many propositions are correlated.

## Policies

Each policy is a function `(posteriors, history) -> proposition_index`.

1. **Hard-gate.** At initialisation, run a short warm-up phase sampling all propositions uniformly.
   After warm-up, permanently exclude any proposition whose posterior mean falls below a configurable threshold `τ_low`.
   Allocate remaining budget uniformly across un-gated propositions.

2. **Constant-revisit.** Same as hard-gate, but with probability `r` (configurable) sample from the gated set uniformly instead of the un-gated set.
   A `r = 0` run recovers hard-gate behaviour exactly.

3. **Uncertainty-scaled revisit.** Allocate the next action proportional to each proposition's posterior variance (or sample via Thompson sampling from the Beta posteriors).
   No explicit gating; exploration pressure emerges from posterior width.

Additional policies (oracle, round-robin) are useful as reference points and should be included if they are cheap to add.

## Metrics

For each run, report at the end-of-budget state:

- **Recall of truths.** Fraction of `t_i = 1` propositions whose final posterior mean exceeds a configurable decision threshold `τ_decide`. This is the primary H01 metric.
- **Calibration.** Brier score or reliability-diagram summary of final posteriors against ground truth. Secondary metric; relevant to the continuous-belief design principle.
- **Regret.** Cumulative expected reward of the chosen action sequence relative to an oracle that knew `t_i` in advance. Helpful for theoretical grounding; not the primary metric.
- **Budget allocation profile.** Per-proposition action counts over the run, useful for diagnosing policy behaviour.

Each metric should be reported with its per-run value and with aggregate summaries (mean, distribution) across many random seeds.

## Parameter Sweep

A minimal defensible sweep covers:

- Noise level: five settings from clean `(0.9, 0.1)` to very noisy `(0.55, 0.45)`.
- Budget size: three settings (small, medium, large relative to `N`).
- Proposition count: `N ∈ {20, 100}`.
- Prior skew: `π ∈ {0.3, 0.5}`.
- Policies: hard-gate, constant-revisit at two `r` values, uncertainty-scaled.
- Correlated-bias variant: on / off, with bias subset size `|C| = 0.3 · N`.
- Seeds: at least 100 per cell.

Sweep grid size is bounded so the whole sweep fits in a single-digit minute on a laptop.

## Deliverables

- `meta/src/h01_simulator/` — a small Python package implementing the model, policies, metrics, and sweep runner.
- `meta/code/notebooks/h01-simulator-results.py` — a marimo notebook that reproduces the headline figures from a saved sweep.
- `meta/results/h01-simulator/sweep-<date>.parquet` — tidy per-run results.
- `meta/doc/interpretations/h01-simulator-<date>.md` — interpretation writeup tying simulator results back to each H01 proposition.

## Open Design Questions

- Beta-Bernoulli is the minimal tractable signal model; a Gaussian-effect-size variant may be worth adding later if the binary-label abstraction feels too coarse for mapping onto real evidence.
- Whether to represent "evidence diversity" (independence groups) inside the simulator now or defer. Cleanest: defer to a follow-up hypothesis, keep this simulator focused on the exploration-exploitation claim.
- Choice of decision threshold `τ_decide` affects the recall metric. Report sensitivity curves rather than a single threshold value.

## Relationship to H01 Propositions

- **P1 (existence)** — tested directly by the sweep.
- **P2 (realistic regime)** — tested by whether the advantage appears within the defensible subset of the noise grid; requires cross-referencing `question:01-bioinformatics-generalizability` for plausibility of noise settings.
- **P3 (mechanism)** — tested by whether the recall gap scales monotonically with noise within the sweep.
- **P4 (safety)** — tested by the low-noise end of the sweep.
- **P5 (schedule)** — partially tested by comparing constant-revisit to uncertainty-scaled revisit.

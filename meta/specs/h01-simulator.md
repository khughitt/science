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

**Posterior update.** Beta-Bernoulli conjugate update on each proposition independently, with a configurable prior `Beta(α₀, β₀)` (default `Beta(1, 1)`). Prior parameters `prior_alpha` and `prior_beta` are first-class configuration values and are recorded in the run output.

**Budget.** A total of `B` actions per simulation run, each action applied to exactly one proposition.

**Bias model.** To distinguish independent analyst noise from shared-pipeline error (the H01 disputing-evidence route; see `question:01-bioinformatics-generalizability`), the signal model supports three modes:

- `none` — no bias; all propositions use the clean `(p_+, p_-)` regime.
- `independent` — each proposition in a biased subset `C` receives an independent per-proposition offset drawn from `Normal(0, σ_bias)` at run start. Errors are biased but uncorrelated across propositions.
- `shared` — a single latent offset `δ ~ Normal(0, σ_bias)` is drawn once per run and applied to every proposition in `C`. Errors are correlated across the subset.

The `shared` mode is the mode that probes H01's most discriminating disconfirmation route: if stochastic revisiting still helps under `shared`, it helps even when pipeline error is correlated across many claims; if it fails under `shared` but helps under `independent`, the advantage is confined to the independent-noise regime and H01 is bounded accordingly.

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

- **Recall of truths.** Fraction of `t_i = 1` propositions whose final posterior mean exceeds a decision threshold `τ_decide`. Recall at the default threshold (0.5) is stored in the per-run output; because the final posterior state is persisted (see below), recall at any other threshold is a derived quantity computable at analysis time. This is the primary H01 metric.
- **Calibration.** Brier score of final posterior means against ground truth. Reliability-diagram inputs (binned posteriors + ground-truth frequencies) are derivable from the persisted posterior state, so reliability diagrams are also an analysis-time product. Secondary metric; relevant to the continuous-belief design principle.
- **Regret.** Cumulative expected reward of the chosen action sequence relative to an oracle that knew `t_i` and the bias realisation in advance. Helpful for theoretical grounding; not the primary metric.
- **Budget allocation profile.** Per-proposition action counts over the run. Persisted alongside per-run scalar metrics so policy behaviour can be diagnosed without re-running.

**Persistence.** Per-run output records, at minimum, the `SimConfig`, the `PolicyConfig`, the scalar metrics above, the full allocation vector, and the final `(α, β)` arrays of the Beta posteriors. Aggregate summaries across seeds (means, distributions, reliability diagrams, threshold-swept recall curves) are produced at analysis time from this persisted output rather than precomputed, to avoid fixing choices that belong to interpretation.

## Parameter Sweep

A minimal defensible sweep covers:

- Noise level: five settings from clean `(0.9, 0.1)` to very noisy `(0.55, 0.45)`.
- Budget size: three settings (small, medium, large relative to `N`).
- Proposition count: `N ∈ {20, 100}`.
- Prior skew: `π ∈ {0.3, 0.5}`.
- Policies: hard-gate, constant-revisit at two `r` values, uncertainty-scaled.
- Bias mode: `none`, `independent`, `shared`, with bias subset size `|C| = 0.3 · N` and `σ_bias = 0.3` when bias is active.
- Seeds: at least 100 per cell.

Sweep grid size is bounded so the whole sweep fits in a single-digit minute on a laptop. If a preliminary benchmark (200 runs, extrapolated) indicates the full grid exceeds that budget, the sweep defaults are tightened rather than silently running over target; parallelisation is a follow-up only if necessary.

## Deliverables

- `meta/src/h01_simulator/` — a small Python package implementing the model, policies, metrics, and sweep runner, installable via `meta/pyproject.toml` and exposing an `h01-sim` CLI entry point.
- `meta/notebooks/h01_simulator_results.py` — a marimo notebook that reproduces the headline figures (recall-vs-noise curves per policy; reliability diagram; threshold-swept recall; `shared` vs `independent` bias comparison) from a saved sweep.
- `meta/results/h01-simulator/sweep-<date>.parquet` — tidy per-run results including allocation vectors and final posterior `(α, β)` arrays as list columns.
- `meta/doc/interpretations/h01-simulator-<date>.md` — interpretation writeup tying simulator results back to each H01 proposition.

The spec is considered met only when the dated sweep parquet and at least one real notebook figure exist on disk; an engine that passes invariant tests is necessary but not sufficient.

## Open Design Questions

- Beta-Bernoulli is the minimal tractable signal model; a Gaussian-effect-size variant may be worth adding later if the binary-label abstraction feels too coarse for mapping onto real evidence.
- Whether to represent "evidence diversity" (independence groups) inside the simulator now or defer. Cleanest: defer to a follow-up hypothesis, keep this simulator focused on the exploration-exploitation claim.
- Choice of decision threshold `τ_decide` affects the recall metric. Sensitivity curves are produced at analysis time from the persisted posterior arrays rather than by precomputing multiple per-run scalars.

## Relationship to H01 Propositions

- **P1 (existence)** — tested directly by the sweep.
- **P2 (realistic regime)** — tested by whether the advantage appears within the defensible subset of the noise grid; requires cross-referencing `question:01-bioinformatics-generalizability` for plausibility of noise settings.
- **P3 (mechanism)** — tested by whether the recall gap scales monotonically with noise within the sweep.
- **P4 (safety)** — tested by the low-noise end of the sweep.
- **P5 (schedule)** — partially tested by comparing constant-revisit to uncertainty-scaled revisit.

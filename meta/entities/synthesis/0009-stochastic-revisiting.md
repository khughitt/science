---
type: synthesis
title: Stochastic revisiting
status: active
created: '2026-05-06'
updated: '2026-05-06'
report_kind: hypothesis-synthesis
id: synthesis:0009-stochastic-revisiting
hypothesis: hypothesis:0001-stochastic-revisiting
generated_at: '2026-05-06T03:57:33Z'
source_commit: 591956fe223318a92c9b36ba01afefcfb1246b10
provenance_coverage: thin
---

## State

[hypothesis:0001-stochastic-revisiting] proposes that a stochastic revisiting policy — one that continues sampling down-weighted propositions rather than hard-gating them out — produces better final recall of ground-truth-true propositions under noisy early evidence, with the advantage growing as noise increases.

[interpretation:0001-simulator-2026-04-24] reports a 144,000-row Beta-Bernoulli simulator sweep and confirms the core propositions. P1 (existence): every exploration-based policy strictly outperforms hard-gating at every noise level and in every bias regime; UCB achieves 0.674 vs 0.320 recall at the noisiest setting. P2 (realistic regime): the largest absolute recall gaps occur at noise levels corresponding to defensible analogues of replication-crisis signal reliability. P3 (mechanism): the Thompson-vs-hard-gate recall gap declines monotonically as noise decreases, consistent with exploration-exploitation theory. P4 (safety): no revisiting policy reduces recall in low-noise regimes; revisiting strictly dominates hard-gating even when signals are informative.

The interpretation also delivers a mechanism refinement: UCB (deterministic upper-confidence-bound selection) outperforms Thompson (stochastic sampling) on both recall and Brier score across all conditions, indicating that the load-bearing mechanism is uncertainty-guided exploration rather than stochasticity per se — a narrowing of the literal P1 claim.

P5 (schedule) is not confirmed: the r-curve is monotonically increasing through the upper grid bound (r = 0.3), so whether the optimal revisit probability is uncertainty-adaptive or constant cannot yet be resolved ([interpretation:0001-simulator-2026-04-24]).

One open question from the bundle ([question:0001-bioinformatics-generalizability]) concerns whether the realistic-regime noise parameters, derived from cross-field replication-crisis estimates, apply in bioinformatics contexts where shared pipeline bias may dominate independent analyst noise.

---

## Arc

Arc reconstruction is limited because only one interpretation exists and no `prior_interpretations` chains are present; the full investigative history cannot be traced.

The investigation opened with [hypothesis:0001-stochastic-revisiting] framed as a bandit-theory argument: a fixed evidence budget shared across many propositions should benefit from continued sampling of low-posterior candidates, mirroring UCB and Thompson-sampling logic from multi-armed bandit settings. Because the simulator did not yet exist, the hypothesis was initially supported only by structural analogy to bandit theory and population-dynamics arguments from the publication-noise literature.

[task:t001] and [task:t020] built the simulator engine — a Beta-Bernoulli model with three bias regimes, three policies, and recall/Brier/regret metrics. [task:t002] executed the full sweep and produced [interpretation:0001-simulator-2026-04-24], which confirmed P1 through P4 and left P5 unresolved. The key epistemic move in the interpretation was comparing UCB to Thompson: because UCB, a deterministic exploration rule, outperforms Thompson, a stochastic one, at every point in the grid, the data support "structured uncertainty-based exploration" more strongly than "stochasticity per se." This shifts the mechanistic claim from the literal framing of H01's title toward a broader exploration-policy framing.

[task:t011] subsequently landed graph-layer weighted sampling for attention, operationalizing the simulator finding in the tool's epistemic dependency graph. The investigation is now at the transition from in-simulator validation to tool-layer implementation, with the Gaussian-signal generalization as the primary unresolved methodological question.

---

## Research fronts

**Open propositions.** P5 (whether the optimal revisit schedule is uncertainty-adaptive) cannot be resolved from the current sweep; the r-curve has not peaked within the tested range.

**Live tasks.**
- [task:t004] (P2) — extend the r-curve to r ∈ {0.3, 0.4, 0.5, 0.7, 0.9} to locate the recall peak and determine whether the optimal r varies by noise level or bias regime, resolving P5.
- [task:t005] (P3) — build a Gaussian effect-size variant of the simulator; the Beta-Bernoulli finding is not yet known to generalize to continuous signals, which are a better model of effect-size evidence.
- [task:t025] (P2) — extend H01-style revisiting with reason-coded uncertainty features (e.g., `underpowered-evidence`, `high-heterogeneity`, `publication-bias-risk`) so attention signals reflect structured evidence quality rather than posterior magnitude alone.
- [task:t016] (P3, deferred) — derive qualitative standing for epistemic entities; deferred pending evidence from [task:t011] weighted sampling on whether sampling-driven attention is sufficient.
- [task:t021] / [task:t022] (P1) — Evidence Payload Schema group; structured quantitative evidence payloads would give H01 attention signals richer inputs than binary support/dispute plus a scalar.
- [task:t024] (P2) — model heterogeneity and bias as explicit evidence-generation mechanisms, connecting the H01 simulator's bias-regime results to real evidence-edge semantics.
- [task:t032] (P2) — scope sequential / anytime-valid evidence as a graph aggregation primitive, potentially extending H01's static-budget framing to online evidence accumulation.

**Methodological boundary.** Whether H01's recall advantage persists under correlated (shared-pipeline) bias across many propositions simultaneously — the failure mode flagged in [question:0001-bioinformatics-generalizability] — remains untested by the current simulator.

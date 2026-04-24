---
id: "hypothesis:h01-stochastic-revisiting"
type: "hypothesis"
title: "Stochastic revisiting of down-weighted claims improves final recall under noisy early evidence"
status: "proposed"
source_refs: []
related:
  - "topic:analytic-flexibility-and-replication"
  - "question:01-bioinformatics-generalizability"
created: "2026-04-24"
updated: "2026-04-24"
---

# Hypothesis H01: Stochastic revisiting of down-weighted claims improves final recall under noisy early evidence

## Organizing Conjecture

In a research-assistance tool that allocates a fixed evidence budget across many candidate propositions, a policy that continues to sample down-weighted propositions with some probability — rather than hard-gating them out after they fall below a support threshold — produces better final recall of ground-truth-true propositions, with the advantage growing as early-evidence noise increases.
This is the exploration-exploitation trade-off of multi-armed bandit theory [@McElreath2015], applied at the proposition-allocation layer of a tool like `science-meta`.

Scope caveat up front: this hypothesis is about behaviour *inside a simulator with known ground truth*.
The separate step of mapping simulator findings to real researcher workflows is its own bet and is not included in the claims below.

## Proposition Bundle

### Core Propositions

**P1 (existence).**
In a simulator that allocates a fixed evidence budget over N propositions of known truth, with per-action signals drawn from a noise model, there exists a parameter regime in which a stochastic-revisiting policy achieves strictly higher final-state recall of the true propositions than a hard-gating policy at equal budget.

**P2 (realistic regime).**
That parameter regime is non-empty for noise levels comparable to published replication-crisis estimates of per-study signal reliability [@Ioannidis2005; @Errington2021; @Niepel2019] in the relevant domains.
A hypothesis that only held in implausibly noisy regimes would have limited tooling implications.

**P3 (mechanism).**
The advantage of stochastic revisiting over hard gating is monotonically increasing in early-signal noise within the realistic regime, consistent with bandit-theoretic results on the exploration-exploitation trade-off.
This tests that the effect is driven by exploration rather than by an artifact of any particular simulator parameterisation.

### Supporting Or Auxiliary Propositions

**P4 (safety).**
Stochastic revisiting does not meaningfully reduce final recall in low-noise regimes relative to hard gating.
This matters for tool design: a policy that helps in hard regimes but hurts in easy ones is less appealing than one that helps in hard regimes and is neutral in easy ones.

**P5 (schedule).**
The revisiting probability that performs best is a function of estimated per-proposition uncertainty rather than a constant.
This is weaker than P1-P3 and could fail even if the main claim holds.

## Current Uncertainty

- No direct empirical evidence specific to this tool context; the argument relies on transferring multi-armed bandit theory to proposition-evidence allocation, which is structurally close but not identical.
- Classical bandit settings assume stationary reward distributions; scientific evidence is better modelled by restless or contextual bandits, which have weaker theoretical guarantees.
- Realistic noise parameters for the "realistic regime" claim in P2 rely on cross-field generalisation of replication-crisis estimates (see `question:01-bioinformatics-generalizability`); those parameters are not tightly constrained.
- The simulator itself is not yet implemented, so the main test of this hypothesis is currently hypothetical rather than ongoing.

## Predictions

If the core propositions are roughly correct:

- In the simulator, increasing the per-action noise level will widen the recall gap between stochastic-revisiting and hard-gating policies, with both policies performing similarly at very low noise.
- The stochastic policy will recover more true propositions that are *initially* mis-estimated (lucky-bad or lucky-good early draws) at the cost of slightly more evidence spent on ultimately-false propositions.
- An uncertainty-scaled revisit probability (P5) will outperform a constant revisit probability in the high-noise regime; in the low-noise regime the two will be indistinguishable.

## Falsifiability

Results that would materially lower confidence in the core claims:

- **P1 disconfirmed:** under a realistic simulator sweep, no stochastic-revisiting policy produces higher final recall than hard gating at any noise level. This would be a clean null.
- **P2 disconfirmed:** an advantage exists only at noise levels far above any defensible estimate of early-evidence noise in target domains. The hypothesis would then be technically true but operationally irrelevant.
- **P3 disconfirmed:** the advantage exists but does not scale monotonically with noise, suggesting a non-exploration mechanism — possibly an artifact of the chosen simulator or policy specification.
- **P4 disconfirmed:** stochastic revisiting meaningfully hurts recall in low-noise regimes, turning the proposed policy into a trade-off that depends on the tool knowing the regime in advance — which it cannot.

## Supporting Evidence

- `literature_evidence` — Multi-armed bandit theory (Thompson sampling, UCB, successive-elimination variants) establishes that exploration-exploitation trade-offs favour continued sampling of low-reward arms in regimes with high per-sample noise relative to arm separation. The mapping to proposition-evidence allocation is structural rather than formal.
- `literature_evidence` — McElreath & Smaldino's population-dynamics model of scientific findings [@McElreath2015] shows that low replication rates are a stable equilibrium of selection + noise dynamics in the publication system, implying that tool-level reassessment of down-weighted claims would correct a real ecological bias, not a synthetic one.
- `literature_evidence` — Multi-centre cell-line studies [@Niepel2019] indicate that standardised protocols reduce but do not eliminate per-assay variability, bounding below the realistic-regime noise estimate.

## Disputing Evidence

- No direct disputing evidence yet identified; the closest relevant body of work would be ML systems literature on when pure exploration harms performance (e.g. contextual-bandit regret bounds under non-stationarity), which is suggestive rather than disputing per se.
- If evidence arises that the dominant failure mode in real research workflows is *shared* pipeline bias rather than *independent* analyst noise (see `question:01-bioinformatics-generalizability`), then stochastic revisiting of any one proposition may not help, because the error is correlated across many propositions at once. This is the most plausible route to disconfirmation.

## Evidence Needed To Shift Belief

- **First and cheapest:** a simulator sweep over noise levels, budget sizes, and revisiting policies, reporting recall of ground-truth-true propositions, calibration of final-state probabilities, and regret relative to an oracle allocation. This is a single self-contained experiment.
- **Secondary:** a literature sweep for formal results on restless or non-stationary bandits applied to evidence-aggregation problems; these would either strengthen the theoretical grounding or identify assumptions that break the mapping.
- **Most discriminating:** construction of a simulator variant in which a subset of propositions share a correlated bias (modelling shared-pipeline error). Does stochastic revisiting still help in that regime, or does the advantage disappear?

## Related Work

- `topic:analytic-flexibility-and-replication` — motivates the noise regime in which this hypothesis would, if true, pay off.
- `question:01-bioinformatics-generalizability` — constrains the noise parameters used in any realistic simulation sweep, and surfaces the shared-pipeline-bias failure mode noted under *Disputing Evidence*.
- `topic:structured-scientific-knowledge` — weakly related: the allocation-policy layer assumed here sits above the proposition representation layer that the structured-knowledge topic concerns.

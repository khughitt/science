---
id: hypothesis:h05-sequential-evidence-improves-attention
type: hypothesis
title: Sequential anytime-valid evidence improves attention and stopping decisions over fixed-N synthesis
status: proposed
phase: candidate
source_refs:
- paper:Mulder2026
- paper:Aitken2024
- paper:Maier2022
related:
- question:06-sequential-anytime-valid-evidence
- hypothesis:h01-stochastic-revisiting
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
created: '2026-05-05'
updated: '2026-05-05'
---
# Hypothesis H05: Sequential anytime-valid evidence improves attention and stopping decisions over fixed-N synthesis

## Organizing Conjecture

A graph that aggregates evidence with anytime-valid procedures - e-values, test martingales, or confidence sequences - will produce better calibrated attention and stopping behavior than one that aggregates with fixed-N Bayes factors, BMA, or BES, in workflows where evidence arrives sequentially and revisiting is unbounded [@Mulder2026; @Aitken2024; @Maier2022].
The conjecture is phase: speculative.
It rests on architectural argument from Batch 1 plus reading leads in `[t028]` rather than on direct evidence within the project.

## Proposition Bundle

### Core Propositions

**P1 (anytime-valid validity).**
Under sequential evidence accumulation with optional stopping and unbounded revisiting, anytime-valid procedures avoid the optional-stopping inflation that fixed-N Bayes factors and BMA suffer when applied repeatedly to the same proposition.

**P2 (attention compatibility).**
Replacing posterior magnitude with anytime-valid evidence levels in H01-style attention will preserve or improve recall, calibration, and contradiction discovery at equal review budget, without requiring new reason-code categories.

**P3 (workflow fit).**
Real research-assistance workflows in this project look more like sequential evidence accumulation with optional stopping than like closed-N meta-analysis, so the anytime-valid framing is the closer match for graph state.

### Supporting Or Auxiliary Propositions

**P4 (architectural compatibility).**
Anytime-valid aggregation operates as a different aggregation operator over the same payload schema (H02) and reason codes (H03), not as a parallel architecture.
It can coexist with fixed-N synthesis for closed batches.

**P5 (causal-guardrail neutrality).**
The causal-estimand guardrail (H04) applies the same way regardless of whether the synthesis operator is fixed-N or anytime-valid; H05 does not weaken the guardrail.

## Current Uncertainty

- No paper in Batches 1 or 2 directly establishes the anytime-valid framing for project workflows; t028 carries the reading leads.
- It is unclear which of e-values, test martingales, or confidence sequences is the right primary primitive for graph attention.
- Optional stopping is a real phenomenon in this project but has not been measured: how often does the same proposition actually receive sequential evidence over the project lifetime?
- Anytime-valid procedures sometimes lose statistical efficiency relative to fixed-N tests in benign regimes; the trade-off in research-assistance settings is unmeasured.
- It is unclear whether the schema and synthesis-node types proposed in t022 / t023 already accommodate anytime-valid outputs or need extension.

## Predictions

- In a sequential-evidence simulator with optional stopping, anytime-valid attention will produce higher recall and lower calibration error than fixed-N posterior attention at equal review budget.
- The advantage will widen as the gap between when evidence stops arriving and when evaluation occurs widens.
- In simulations where evidence arrives in one closed batch with no revisiting, fixed-N synthesis will match or beat anytime-valid synthesis.
- Reason codes from H03 (`prior-sensitive`, `source-dependent`, etc.) will continue to add value over either aggregation primitive.

## Falsifiability

- **P1 disconfirmed:** anytime-valid procedures provide no detectable benefit under the project's actual revisit cadence, because optional stopping rarely materializes.
- **P2 disconfirmed:** anytime-valid attention loses recall or calibration relative to posterior attention even in sequential regimes.
- **P3 disconfirmed:** project workflows are well-approximated by closed-N synthesis once batches are made explicit.
- **P4 disconfirmed:** anytime-valid aggregation requires schema or node-type changes incompatible with H02 / H03.

## Supporting Evidence

- `literature_evidence` - Mulder and van Aert support cumulative evidence monitoring under Bayes-factor frameworks but require explicit prior and stopping setups [@Mulder2026].
- `literature_evidence` - Aitken et al. note that Bayes-factor evaluation must specify alternatives and is sensitive to assumptions, which sequential reuse exacerbates [@Aitken2024].
- `literature_evidence` - RoBMA preserves model uncertainty under fixed evidence but does not address optional-stopping reuse [@Maier2022].
- The strongest direct support is expected from t028 follow-up reading on e-values and confidence sequences, not yet ingested.

## Disputing Evidence

- No project benchmark currently measures sequential-aggregation calibration.
- Anytime-valid procedures can be statistically conservative in low-noise closed-batch regimes, so blanket adoption could weaken updates that would otherwise be sound.
- If H02 + H03 already capture the benefits via reason codes and richer payload, H05 may add complexity without practical gain.

## Evidence Needed To Shift Belief

- Ingest t028 follow-up reading on e-values, test martingales, and confidence sequences; produce a topic note linking them to graph attention.
- Build a sequential-evidence simulator extending the H01 simulator: propositions receive evidence over time with optional stopping; compare fixed-N posterior, BMA-style, and anytime-valid attention.
- Audit project graph state to estimate revisit cadence and the realized prevalence of optional-stopping situations.
- Compare anytime-valid attention against H03 reason-coded attention at equal review budget.

## Related Work

- `question:06-sequential-anytime-valid-evidence` is the direct design question.
- `hypothesis:h01-stochastic-revisiting` and `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting` define the attention layer that H05 modifies.
- `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration` defines the payload layer that H05 reuses.
- `[t028]` carries the reading-lead pipeline; `[t032]` scopes the focused review and simulator extension.

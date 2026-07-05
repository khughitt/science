---
kind: question
title: Should Science treat evidence accumulation as sequential and anytime-valid
  rather than fixed-N synthesis?
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: question:0007-sequential-anytime-valid-evidence
ontology_terms: []
datasets: []
source_refs:
- cite:Mulder2026
- cite:Maier2022
- cite:Aitken2024
related:
- hypothesis:0001-stochastic-revisiting
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:0005-sequential-evidence-improves-attention
- question:0002-evidence-payload-schema
- topic:bayesian-methods-continuous-belief
---

# Should Science treat evidence accumulation as sequential and anytime-valid rather than fixed-N synthesis?

## Summary

Bayes factors, Bayesian model averaging, and Bayesian Evidence Synthesis assume a fixed evidence set or a pre-specified stopping rule.
A research-assistance graph does not work that way: evidence arrives over time, the agent or user chooses when to stop revisiting, and graph attention depends on cumulative state.
This question asks whether Science should adopt anytime-valid procedures (e-values, test martingales, confidence sequences) for sequential evidence accumulation, alongside or instead of fixed-N synthesis.

## Why It Matters

- Affects whether H01 / H03 attention policies can use accumulated evidence levels without optional-stopping pathologies.
- Affects whether t023 typed synthesis nodes need a sequential variant.
- Affects whether t028 follow-up reading should be elevated to a hypothesis-bearing research thread.
- Risk if unanswered: the project applies fixed-N Bayes-factor logic to inherently sequential workflows, producing miscalibrated cumulative evidence and biased revisit decisions.

## Current Evidence

- Mulder and van Aert's Bayes-factor meta-analysis supports cumulative evidence monitoring under explicit prior and stopping setups [@Mulder2026].
- Aitken et al. defend single-number Bayes factors as logically coherent but acknowledge sensitivity to assumptions [@Aitken2024].
- RoBMA preserves model uncertainty under fixed evidence sets but does not address optional-stopping inflation [@Maier2022].
- No paper in Batches 1 or 2 directly addresses e-values, test martingales, or confidence sequences. These leads are tracked in `[t028]`.

## Thoughts

- Best current interpretation: anytime-valid procedures are a strong candidate for the underlying aggregation operator on cumulative-evidence edges, especially where revisiting is stochastic and unbounded.
- A hybrid is plausible: fixed-N synthesis for closed batches (a meta-analysis with declared sources), anytime-valid synthesis for open-ended graph state (a proposition that keeps receiving evidence over the life of the project).
- The major remaining uncertainty is whether the e-value / confidence-sequence framing is operationally compatible with reason-coded attention (H03) and rich payloads (H02), or whether it requires a parallel evidence-accounting layer.

## Connections to Project

- Related hypotheses: `hypothesis:0001-stochastic-revisiting`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`, `hypothesis:0005-sequential-evidence-improves-attention`.
- Related tasks: `[t028]`, `[t032]`.
- Required data or analyses: focused literature review on e-values / anytime-valid inference and test martingales for Bayesian model classes; a small simulation comparing fixed-N versus anytime-valid attention on sequential evidence.
- Priority level: medium — important conceptually but does not block t022 / t023 / t026.

## Related

- Topic notes: `topic:bayesian-methods-continuous-belief`.
- Article notes: `paper:Mulder2026`, `paper:Aitken2024`, `paper:Maier2022`.

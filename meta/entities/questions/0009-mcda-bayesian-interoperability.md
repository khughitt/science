---
kind: question
title: How should MCDA-style decision scores interact with Bayesian belief states
  in the graph?
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: question:0009-mcda-bayesian-interoperability
ontology_terms: []
datasets: []
source_refs:
- cite:Linkov2017
- cite:Aitken2024
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0002-evidence-payload-schema
- topic:bayesian-methods-continuous-belief
---

# How should MCDA-style decision scores interact with Bayesian belief states in the graph?

## Summary

Linkov et al. argue that quantitative weight-of-evidence integration should aim for explicit Bayesian methods where likelihoods are available, with multicriteria decision analysis (MCDA) as a practical fallback when likelihoods are not [@Linkov2017].
Aitken et al. emphasize that evidential value is proposition-relative and Bayesian in form [@Aitken2024].
The Batch 2 synthesis surfaced this as an open question with no home: how should MCDA-style criterion scores interact with Bayesian posterior beliefs in the same graph without contaminating either?

## Why It Matters

- Affects whether MCDA scores can update propositions directly, only via decision-analytic synthesis nodes, or not at all.
- Affects t023 typed synthesis nodes: MCDA outputs are a distinct synthesis type and need explicit semantics.
- Affects how early-stage evidence ranking interacts with later Bayesian updates as likelihood-bearing evidence becomes available.
- Risk if unanswered: MCDA ranking outputs leak into Bayesian belief slots, producing artificial precision or false confidence in propositions that were only ranked, not measured.

## Current Evidence

- Linkov et al. describe MCDA as a principled fallback when probabilistic weight-of-evidence is not feasible, and recommend Bayesian methods where data permit [@Linkov2017].
- Aitken et al. require evidential support to be defined relative to alternative propositions, which is natively Bayesian and not native to MCDA [@Aitken2024].
- No project artifact currently uses MCDA, but early-stage proposition ranking, prioritization, and triage use scoring patterns that resemble MCDA in structure.

## Thoughts

- Best current interpretation: keep MCDA outputs in a typed `decision-analytic-score` synthesis node distinct from Bayesian posterior nodes.
  Allow MCDA scores to inform attention or prioritization without writing to belief fields.
  Allow controlled conversion paths only when explicit assumptions (e.g., score-to-likelihood mappings, ranking-to-prior) are recorded.
- A second-order use is to score curation effort: MCDA-style criteria over coverage, freshness, and risk could prioritize where to gather Bayesian evidence next.
- The major remaining uncertainty is whether the project will use MCDA enough to justify a typed synthesis node now, or whether the cleanest move is to defer it until a concrete use case appears.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`.
- Related tasks: `[t023]`.
- Required data or analyses: identify any current project workflows that resemble MCDA scoring (prioritization, triage, curation ranking) and decide whether to formalize them as decision-analytic nodes.
- Priority level: low-medium — captures an open question rather than blocking design work.

## Related

- Topic notes: `topic:bayesian-methods-continuous-belief`.
- Article notes: `paper:Linkov2017`, `paper:Aitken2024`.

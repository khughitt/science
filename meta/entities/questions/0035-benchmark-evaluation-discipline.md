---
id: question:0035-benchmark-evaluation-discipline
kind: question
title: Does Science's evaluation tooling enforce benchmark controls sufficient to
  avoid the fragmentation failures documented in domain GNN reviews?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Besharatifard2024
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
created: '2026-07-10'
updated: '2026-07-10'
---

# Does Science's evaluation tooling enforce benchmark controls sufficient to avoid the fragmentation failures documented in domain GNN reviews?

## Summary

Besharatifard and Vafaee (2024) document that direct comparison across 25 GNN-based drug synergy models is unreliable because studies vary arbitrarily in: synergy metric (Loewe, Bliss, ZIP, HSA), thresholding strategy, dataset, and cross-validation scheme.
The same failure mode can occur in any domain where multiple modeling approaches are evaluated without a shared controlled protocol.
This question asks whether Science's evaluation machinery (benchmark tooling, stochasticity tracking, dataset provenance) currently enforces the controls that would prevent this fragmentation when users compare methods or parameterizations.

## Why It Matters

- Affects decisions about what benchmark infrastructure Science should provide or require for fair within-project model comparisons.
- If left unanswered, Science could enable evaluations that look rigorous but are confounded by unlogged preprocessing or metric choices — the same problem the GNN review critiques at the domain level.

## Current Evidence

- The method-stochasticity umbrella (t087–t089) ships `science dataset stochasticity` tracking, which captures run-level stochastic variation — a necessary but not sufficient control.
- Science does not yet enforce a fixed-split / locked-preprocessing protocol across benchmark runs.
- The Besharatifard2024 review explicitly calls for a controlled benchmarking study as future work, implying the domain has no solution either.

## Thoughts

- Best current interpretation: Science partially addresses the problem via stochasticity tracking and dataset provenance, but does not yet enforce experiment-level controls (fixed splits, logged thresholds, evaluation-metric provenance).
- Major uncertainty: whether enforcing such controls is best done as a Science-level guardrail vs. left to individual project conventions.

## Connections to Project

- Related hypotheses: hypothesis:0002-rich-evidence-payloads-improve-graph-calibration (richer payloads only help if the evaluation itself is unbiased)
- Required data or analyses: audit of current benchmark tooling against the confounders listed in Besharatifard2024 Table 3.
- Priority level: medium — relevant whenever Science is used for comparative model evaluation.

## Related

- Topic notes:
- Article notes: paper:Besharatifard2024
- Methods/Datasets:

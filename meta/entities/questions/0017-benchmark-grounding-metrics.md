---
id: question:0017-benchmark-grounding-metrics
kind: question
title: How should Science use benchmark and dataset portfolios as external grounding
  to measure whether its knowledge representation improves over time?
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0002-evidence-payload-schema
- question:0013-robustness-reproducibility-evaluation
- question:0008-llm-agents-as-fallible-sources
- question:0016-reproducibility-validation
- question:0018-ordinal-continuous-belief-boundary
created: '2026-07-08'
updated: '2026-07-08'
---
# How should Science use benchmark and dataset portfolios as external grounding to measure whether its knowledge representation improves over time?

## Summary

If Science is building useful representations of the world, it should be able to
*predict* against them with increasing accuracy. This question asks how Science
should assemble a portfolio of numerous, diverse, relevant benchmarks (or dataset
collections used as benchmarks) as **external grounding** — producing the metrics
that measure whether the knowledge representation is improving over time, and
furnishing the ground truth the H02 rich-vs-flat calibration bakeoff needs.

The central design risk is not building the harness but keeping it honest:
avoiding leakage (evidence and ground truth drawn from the same source) and
Goodhart effects (a benchmark that becomes a target stops measuring).

## Why It Matters

- Decides whether "rich representation improves calibration" (`hypothesis:0002`)
  can move from a well-designed bet to a measured result.
- Provides a standing metric (calibration/accuracy over time) for the whole
  representation, not just per-proposition belief.
- Lets the continuous belief projection (meta D-003) be genuinely *calibrated*
  against outcomes rather than a bare monotone transform of the ordinal — ties to
  `question:0018`.
- Risk if unanswered: the framing's core value proposition stays unfalsified; and
  a naive benchmark setup contaminates its own measurement via leakage or overfits
  the representation to one benchmark's structure.

## Current Evidence

- Operational surface exists but does not score belief: the `science benchmark
  tests` command projects read-only candidate test rows and the
  `catalog-benchmarks` skill discovers benchmark-capable datasets; neither authors
  outcomes nor measures calibration.
- Reusable scoring machinery exists for a *different* hypothesis: `meta/src/
  h01_simulator/metrics.py` defines `brier`, and `sweep.py` scores posterior mean
  against `ground_truth` — but only for the H01 attention/revisiting simulator, not
  the rich-vs-flat payload contrast.
- `hypothesis:0002` and `question:0013` both *name* a replay/benchmark harness as
  future work; it has not been built or run. No H02 results artifact exists under
  `meta/results/`.
- Conflicting pressure: benchmark selection is itself a modeling choice; relevance,
  coverage, and leakage controls add cost and can bias the metric if done casually.

## Thoughts

- Best current interpretation: treat "benchmark used for grounding" as a
  first-class provenance fact, with an explicit **tune/eval split** (benchmarks
  used to tune the belief policy disjoint from those used to evaluate it) and a
  **held-out rotation** so no single benchmark becomes a durable target.
- Start the calibration-over-time metric by reusing the `h01_simulator` Brier/
  ground-truth loop, generalized to score belief snapshots against benchmark
  outcomes (Brier / ECE).
- The H02 bakeoff is the concrete milestone: same benchmark set, rich-payload
  aggregation vs a flat/scalar baseline, scored on held-out outcomes.
- Benchmark verdicts are another instance of the "QA-verdict-as-belief-input"
  pattern (`question:0016`, dataset-QA ceiling): grounding can inform belief, but
  the leakage rule must prevent an outcome from grounding a claim it was derived
  from.
- Major remaining uncertainty: how to detect leakage mechanically (shared source /
  dataset / paper between evidence and benchmark), how large and diverse the
  portfolio must be to avoid single-benchmark overfitting, and how to weight
  domain-relevant vs domain-adjacent benchmarks.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`.
- Related questions: `question:0002-evidence-payload-schema`,
  `question:0013-robustness-reproducibility-evaluation`,
  `question:0008-llm-agents-as-fallible-sources` (benchmark ground truth is what
  lets annotator calibration profiles be estimated),
  `question:0018-ordinal-continuous-belief-boundary`.
- Required analyses: benchmark portfolio + leakage provenance; calibration-over-time
  metric; the H02 rich-vs-flat bakeoff. Tracked as the `benchmark-grounding` task
  group.
- Priority level: high — Phase-1 lead of the reproducibility/grounding roadmap.

## Related

- Roadmap: `doc/plans/2026-07-08-epistemic-reproducibility-and-grounding-roadmap.md`.
- Methods/Datasets: Brier score, expected calibration error, held-out prediction,
  benchmark leakage/contamination controls, distribution-shift robustness suites.

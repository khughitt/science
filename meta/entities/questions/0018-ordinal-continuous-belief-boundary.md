---
id: question:0018-ordinal-continuous-belief-boundary
kind: question
title: Where is the load-bearing boundary between ordinal evidence state and continuous
  calibrated belief?
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0009-mcda-bayesian-interoperability
- hypothesis:0007-working-model
- question:0017-benchmark-grounding-metrics
created: '2026-07-08'
updated: '2026-07-08'
---
# Where is the load-bearing boundary between ordinal evidence state and continuous calibrated belief?

## Summary

The toolkit treats belief as **ordinal** (speculative / fragile / supported /
well_supported, with independence reduction and refutation caps), and treats the
log-odds scalar as an *optional derived projection* over that ordinal result
(`docs/user-guide/epistemic-model.md`). Meta D-003 asserts that operational
beliefs are **continuous probabilities** strictly bounded away from 0 and 1. Both
are defensible, but the boundary between them is currently implicit. This question
asks where that boundary should be **load-bearing**: which surface is durable
truth, which is a projection, and what keeps a downstream consumer from silently
assuming one while fed the other.

## Why It Matters

- Decides which representation is authoritative for which purpose — durable
  evidence state vs decision/attention scalar — and prevents accidental
  double-counting or false precision when the two are mixed.
- Affects whether the continuous projection can be *calibrated* (fit/validated
  against outcomes) rather than being a bare monotone transform of the ordinal.
- Risk if unanswered: ordinal and continuous drift apart; code paths assume a
  probability where only an ordinal magnitude exists (or vice versa), and D-003's
  continuous commitment and the toolkit's ordinal default read as contradictory.

## Current Evidence

- Toolkit: belief policy is ordinal (`core-default` v1); the log-odds scalar has
  its own config version and is documented as a derived projection that should not
  be treated as interchangeable with the ordinal policy version.
- Meta D-003: operational beliefs are continuous probabilities bounded away from
  0/1, and binary decisions are computed from the belief at the decision point.
- `task:t005` (Gaussian effect-size H01 variant) is explicitly framed as testing
  whether D-003's continuous-belief commitment has empirical footing beyond the
  Beta-Bernoulli regime — i.e. the continuous stance is itself under test.
- `question:0009-mcda-bayesian-interoperability` already circles the same seam
  (ordinal MCDA vs Bayesian scalar interoperability).

## Thoughts

- Best current interpretation: keep the **ordinal magnitude as durable evidence
  state** (auditable, policy-versioned, refutation-capped) and treat the
  **continuous value as a calibrated decision/attention projection** — explicitly
  derived, explicitly not the authoring surface.
- The projection becomes principled only once it can be validated against outcomes;
  this is where `question:0017` (benchmark grounding) supplies the calibration
  target.
- Make the boundary explicit in code: a single documented conversion point, with
  the projection carrying its own config identity (as the log-odds scalar already
  does) so consumers cannot mistake it for the ordinal truth.
- Major remaining uncertainty: whether any belief-eligibility or gating logic
  should ever consume the continuous value directly, or whether continuous is
  strictly downstream of every eligibility decision.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`,
  `hypothesis:0007-working-model`.
- Related questions: `question:0009-mcda-bayesian-interoperability`,
  `question:0017-benchmark-grounding-metrics`.
- Related decisions: meta D-003 (continuous operational beliefs).
- Required analyses: locate every ordinal↔continuous conversion; define the
  authoritative-vs-projection contract; tie projection calibration to benchmark
  outcomes. Tracked as a Phase-2 follow-up of the reproducibility/grounding
  roadmap.
- Priority level: medium-high — a clarity/consistency keystone rather than a build.

## Related

- Roadmap: `doc/plans/2026-07-08-epistemic-reproducibility-and-grounding-roadmap.md`.
- Methods/Datasets: ordinal vs cardinal belief, calibration, log-odds projection,
  MCDA/Bayesian interoperability.

---
id: hypothesis:0009-continuous-belief-is-overconfident-relative-to-ordinal
kind: hypothesis
title: Continuous belief is overconfident relative to ordinal
status: active
source_refs: []
origins:
- type: assistant
  ref: explore-ideas-contrarian
related:
- question:0018-ordinal-continuous-belief-boundary
created: '2026-07-25'
updated: '2026-07-25'
added_by: explore-ideas:claude-opus-5:cand-contrarian-false-calibration-continuous-belief
lens_views:
- lens: contrarian
  rationale: 'Converts an open boundary question into a testable claim that the project''s
    chosen side of the boundary is the miscalibrated one.

    '
  origin_ref: explore-ideas-contrarian
---
# Hypothesis: Continuous belief is overconfident relative to ordinal

## Organizing Conjecture

Representing beliefs as continuous probabilities bounded away from 0 and 1 and aggregating heterogeneous evidence lines produces estimates systematically miscalibrated in the overconfident direction — conveying quantitative precision the quality and heterogeneity of the underlying evidence does not warrant — compared with coarser ordinal epistemic states.

**Exploration rationale (one line per contributing lens):**

- _contrarian_: Converts an open boundary question into a testable claim that the project's chosen side of the boundary is the miscalibrated one.

## Proposition Bundle

<!--
List the key propositions that make up this hypothesis.
Prefer explicit sub-propositions, especially those with explicit S-P-O structure:
- subject
- predicate
- object
-->

### Core Propositions

<!-- Propositions that must be roughly true for the hypothesis to survive. -->

### Supporting Or Auxiliary Propositions

<!-- Propositions that strengthen or elaborate the hypothesis but are not essential. -->

## Current Uncertainty

<!--
What makes this hypothesis currently fragile, contested, or underspecified?
Note whether support is sparse, single-source, indirect, literature-only, etc.
-->

## Predictions

<!--
What should we observe if the core claims are true?
Distinguish strong discriminating predictions from weaker corollaries.
-->

## Falsifiability

The hypothesis is refuted if continuous belief estimates prove **as well or better
calibrated** than coarser ordinal states under the project's actual authoring conditions.

Specific results that would force revision:

- Proper scoring rules (Brier, log-loss) computed over a resolved-outcome corpus show the
  continuous representation matching or beating a mapped-ordinal baseline. That is the
  direct test and it decides the claim.
- Reliability diagrams showing no systematic bias toward the confident end — the claim is
  directional, so symmetric miscalibration refutes it as stated even though it would still
  be bad news for the continuous representation.
- Evidence that the observed overconfidence is an artifact of the aggregation rule rather
  than of the representation would relocate the fault without refuting the claim; the
  hypothesis should then be re-stated against the rule.

Two threats to the test itself, both of which must be handled before a negative result is
believable: beliefs bounded strictly away from 0 and 1 create floor and ceiling effects
that distort reliability diagrams near the extremes, and the resolved-outcome corpus must
not be assembled from evidence the graph already used — the leakage problem
`question:0017` names. A calibration result that fails either check is uninformative in
both directions.

This hypothesis directly challenges **D-003**, which asserts continuous bounded beliefs by
decision rather than by measurement. That is deliberate: it makes a standing constraint
falsifiable.

## Supporting Evidence

<!--
Existing evidence that supports one or more propositions in this bundle.
Note evidence type where possible:
- literature
- empirical-data
- simulation
- benchmark
-->

## Disputing Evidence

<!--
Existing evidence that weakens or contests one or more propositions.
Include null or conflicting findings here.
-->

## Evidence Needed To Shift Belief

<!--
What evidence would most efficiently increase or decrease confidence?
What is the most discriminating next test?
-->

## Related Work

<!--
Papers, topics, inquiries, and other hypotheses that bear on this hypothesis.
-->

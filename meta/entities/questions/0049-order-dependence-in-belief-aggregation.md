---
id: question:0049-order-dependence-in-belief-aggregation
kind: question
title: Order-dependence in belief aggregation
status: active
ontology_terms: []
datasets: []
source_refs: []
origins:
- type: assistant
  ref: explore-ideas-mechanism
  independent: true
- type: assistant
  ref: explore-ideas-temporal
  independent: true
related: []
created: '2026-07-25'
updated: '2026-07-25'
added_by: explore-ideas:claude-opus-5:cand-evidence-order-dependence
lens_views:
- lens: mechanism
  rationale: "Bayesian aggregation is order-independent given conditionally independent\
    \ evidence. The toolkit produces evidence assessments sequentially through an\
    \ LLM that has already processed earlier items. If the same raw evidence in a\
    \ different sequence yields different numeric contributions for later items, the\
    \ formal commutativity of the arithmetic is defeated upstream at the extraction\
    \ stage \u2014 an undisclosed violation of the conditional-independence assumption\
    \ the belief model rests on.\n"
  origin_ref: explore-ideas-mechanism
- lens: temporal
  rationale: "Read as a trajectory problem: storing only the current belief discards\
    \ the diagnostic information needed to detect hysteresis \u2014 belief that settled\
    \ high early and resisted later disconfirmation, or reversed on a single late\
    \ anchor. Recording trajectories would let the system audit for primacy effects\
    \ and lock-in to early framings.\n"
  origin_ref: explore-ideas-temporal
---
# Order-dependence in belief aggregation

## Summary

Even if the aggregation rule is mathematically commutative over evidence items, does the LLM-mediated assessment step — where framing of earlier evidence carries into how later evidence is characterized — make the aggregated belief practically order-dependent, and should the graph record the full belief trajectory rather than only the current state?

**Exploration rationale (one line per contributing lens):**

- _mechanism_: Bayesian aggregation is order-independent given conditionally independent evidence. The toolkit produces evidence assessments sequentially through an LLM that has already processed earlier items. If the same raw evidence in a different sequence yields different numeric contributions for later items, the formal commutativity of the arithmetic is defeated upstream at the extraction stage — an undisclosed violation of the conditional-independence assumption the belief model rests on.
- _temporal_: Read as a trajectory problem: storing only the current belief discards the diagnostic information needed to detect hysteresis — belief that settled high early and resisted later disconfirmation, or reversed on a single late anchor. Recording trajectories would let the system audit for primacy effects and lock-in to early framings.

## Why It Matters

<!-- Bulleted list. Cover at least:
- the decision this question affects
- the risk if the question is left unanswered
-->

## Current Evidence

<!-- Bulleted list. Cover at least:
- supporting evidence
- conflicting evidence
-->

## Thoughts

<!-- Bulleted list. Cover at least:
- the best current interpretation
- the major remaining uncertainty
-->

## Connections to Project

- Related hypotheses:
- Required datasets: list dataset IDs in frontmatter `datasets:`.
- Required analyses:
- Priority level:

## Related

- Topic notes:
- Article notes:
- Methods/Datasets:

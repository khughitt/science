---
id: question:0057-marginal-epistemic-return-per-authoring-cost
kind: question
title: Marginal epistemic return per unit authoring cost
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- question:0005-authoring-cost-audit
created: '2026-07-25'
updated: '2026-07-25'
---
# Marginal epistemic return per unit authoring cost

## Summary

`question:0005` asks what the evidence-payload schema *costs* to populate, and answered
the first version of that empirically. Nothing asks what a populated field is *worth*.
Those are the two halves of one decision, and only one half is instrumented.

This question asks for the return side: what is the marginal epistemic gain from the Nth
evidence line, the Nth schema field, or the Nth typed relation — and where does that
curve flatten enough that further structure is not worth authoring?

Surfaced during the 2026-07-25 `explore-ideas` triage rather than by a lens agent: the blind pass could not reach it, because the lens agents had no view of what the project already asks.

## Why It Matters

- Without a return estimate, schema-scope decisions default to "include it if it is
  epistemically defensible", which has no stopping rule and monotonically increases
  authoring burden.
- Supplies the missing term in `question:0005`'s minimality argument: H02 P3 asserts that
  calibration gains collapse if the schema is too heavy, which is a claim about a
  cost/benefit ratio whose numerator has never been estimated.
- Risk if unanswered: the schema grows until it is abandoned, and the failure is
  attributed to the authors rather than to the absent stopping rule — the outcome
  `question:0052` says the prior art already reached.

## Current Evidence

- The cost side has real local data: the completed `[t030]` audits measured extraction
  feasibility and pruned fields on that basis.
- The return side has none. `hypothesis:0002` predicts that rich payloads improve
  calibration, but as a directional claim, not as a curve with diminishing returns.
- `question:0017`'s benchmark-grounding work is the natural measurement substrate: if
  calibration can be measured at all, it can be measured as a function of how much of the
  payload is populated.

## Thoughts

- Best current interpretation: this is answerable by ablation rather than by theory —
  measure calibration with fields progressively withheld, on the same evidence base.
  That reuses the `question:0017` harness rather than needing a new one.
- Major remaining uncertainty: whether the return is per-field at all, or whether payload
  value is combinatorial, in which case ablation understates it and the curve is the wrong
  shape to look for.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
- Required analyses: field-ablation design over an existing evidence corpus.
- Priority level: medium-high — it supplies the stopping rule the schema currently lacks.

## Related

- Topic notes: `topic:structured-scientific-knowledge`

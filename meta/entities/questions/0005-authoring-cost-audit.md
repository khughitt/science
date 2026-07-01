---
type: question
title: How much of the proposed evidence-payload schema can authors and agents reliably
  populate?
status: active
created: '2026-05-05'
updated: '2026-07-01'
id: question:0005-authoring-cost-audit
ontology_terms: []
datasets: []
source_refs:
- cite:Williams2018
- cite:Maier2022
- cite:Klugkist2023
- cite:Allen2017
- cite:Thijssen2017
- cite:Han2026
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0002-evidence-payload-schema
- question:0004-source-and-pipeline-provenance
- topic:structured-scientific-knowledge
---

# How much of the proposed evidence-payload schema can authors and agents reliably populate?

## Summary

H02 P3 (minimality) asserts that calibration gains will collapse if the payload schema is too heavy for routine authoring.
Both Batch 1 and Batch 2 syntheses warn about authoring burden but do not measure it.
This question asks what fraction of the proposed t022 fields can be extracted from existing paper summaries and project artifacts without unreasonable effort, and which fields fail extraction in practice.

## Why It Matters

- Affects which fields belong in the required core of t022 versus optional typed extensions.
- Affects whether H02 is testable: if metadata coverage is sparse, the calibration prediction cannot be evaluated.
- Affects H03's reason-coded attention: reason codes can only fire when the underlying fields are populated.
- Risk if unanswered: the project ships a schema that looks epistemically correct but is rarely populated, so calibration gains are theoretical and graph behavior degrades to scalar-edge equivalents.

## Current Evidence

- The completed `[t030]` audit answered the first version of this question for the t022 v2 candidate schema. The narrow pass (`meta/doc/plans/historical/2026-05-06-t030-narrow-authoring-cost-audit.md`) produced v2.1 patches: `claim_source_ref`, an explicit out-of-scope section, a `validation_status` pitfall note, and generic evidence-quality reason codes.
- The full pass (`meta/doc/plans/historical/2026-05-06-t030-full-audit-results.md`) used a 12-paper main sample plus a 5-paper routing test. It produced v2.2 patches: remove `target_artifact_ref` from core, extend paper artifact enums, add `method-set`, add `framework-proposal`, make `uncertainty_summary` optional, and add proposition-cardinality and empty-list reason-code authoring rules.
- The two blind LLM passes disagreed within one rubric point on roughly 25-40% of rubric-ambiguous fields, with systematic pass-1-higher-than-pass-2 calibration drift. This is evidence that agent-assisted extraction needs a clearer rubric and independent evaluation before it can be treated as stable.
- Han et al. show that LLM-assisted extraction of priors and constraints is feasible with validation, but the local `[t030]` result shows model/rubric calibration remains a live risk for this project's schema [@Han2026].

## Thoughts

- The first t030-style sampling pass is complete; do not repeat it as if no local data exists.
- The major remaining uncertainty is the quality bar: extractable does not mean correct, and a permissive coding may overestimate coverage.
- The next useful increment is to run a true full-context human pass before any LLM output is visible, or to run a multi-model extraction audit that separates model-family calibration from rubric ambiguity.
- Outputs from that follow-up should feed back into t022/t033 as agent-authoring policy, not reopen the completed t030 field-pruning pass.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`.
- Related tasks: `[t022]`, `[t030]`.
- Required data or analyses: a sampling plan over existing paper summaries, a candidate field list from t022, and a scoring rubric.
- Priority level: high — this gates whether H02 can be evaluated at all.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: any of the 22 paper summaries from this commit serve as candidate sources.

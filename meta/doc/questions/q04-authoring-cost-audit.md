---
id: question:04-authoring-cost-audit
type: question
title: How much of the proposed evidence-payload schema can authors and agents reliably populate?
status: active
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
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- topic:structured-scientific-knowledge
created: '2026-05-05'
updated: '2026-05-05'
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

- The Batch 1 and Batch 2 paper summaries already exist in `doc/background/papers/` and contain implicit values for many proposed fields.
- No automated or semi-automated extraction has been attempted yet.
- Field-level missingness has not been characterized for any subset.
- Han et al. show that LLM-assisted extraction of priors and constraints is feasible with validation, but accuracy and effort are unmeasured for this project's schema [@Han2026].

## Thoughts

- Best current approach: sample 10-20 existing summaries, attempt manual extraction against a candidate t022 field list, and record per-field success rate, ambiguity, and inferred-vs-stated status.
- A second pass with an LLM extractor, scored against the manual pass, would give an early read on agent-assisted authoring.
- Outputs should feed back into t022 as a field-pruning signal: any field with <X% extractability without unreasonable effort is a candidate for "optional" rather than "core".
- The major remaining uncertainty is the quality bar: extractable does not mean correct, and a permissive coding may overestimate coverage.

## Connections to Project

- Related hypotheses: `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`.
- Related tasks: `[t022]`, `[t030]`.
- Required data or analyses: a sampling plan over existing paper summaries, a candidate field list from t022, and a scoring rubric.
- Priority level: high — this gates whether H02 can be evaluated at all.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: any of the 22 paper summaries from this commit serve as candidate sources.

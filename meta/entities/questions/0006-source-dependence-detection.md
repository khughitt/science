---
kind: question
title: Which evidence-source dependence patterns can be inferred mechanically rather
  than annotated by hand?
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: question:0006-source-dependence-detection
ontology_terms: []
datasets: []
source_refs:
- cite:Zhao2012
- cite:Li2016
- cite:Allen2017
- cite:Majumdar2022
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- question:0002-evidence-payload-schema
- question:0004-source-and-pipeline-provenance
- topic:structured-scientific-knowledge
---

# Which evidence-source dependence patterns can be inferred mechanically rather than annotated by hand?

## Summary

Truth-discovery and data-integration work treats source dependence — copying, shared extraction, citation-chain effects, shared datasets, shared pipelines, and shared prompts — as a primary failure mode for evidence aggregation [@Zhao2012; @Li2016; @Allen2017].
H02's P4 (source behavior) and H03's reason-code design both assume dependence is representable.
This question asks which dependence patterns the project can infer from observable graph and pipeline state, and which require human annotation or external signals.

## Why It Matters

- Affects whether the `source_dependency_refs` field proposed in t022 can be populated at all without exhaustive human labeling.
- Affects H02 calibration: aggregation that double-counts copied or pipeline-correlated evidence will look strong while being inflated.
- Affects H03 attention: dependence is one of the load-bearing reason codes (`source-dependent`, `shared-structure-assumption`).
- Risk if unanswered: dependence becomes a prose caveat rather than graph state, and aggregation overcounts in exactly the cases the literature flags as most dangerous.

## Current Evidence

- Zhao et al. and Li et al. survey source-dependence detection in truth discovery, including conditional probability of agreement, copying detectors, and dependency graphs over sources [@Zhao2012; @Li2016].
- Allen documents how shared preprocessing and batch effects across views create non-independence at the data-integration layer [@Allen2017].
- Majumdar and Michailidis use shared structure as an explicit grouping assumption, which is the inverse problem: prior-encoded dependence rather than inferred dependence [@Majumdar2022].
- The project currently records no dependence information on evidence edges or paper summaries.

## Thoughts

- Best current interpretation: stratify dependence by mechanical detectability.
  Mechanically detectable: shared dataset identifiers, shared author lists, citation chains, shared extractor or prompt versions, near-duplicate text, shared upstream synthesis nodes.
  Requires annotation: methodological convergence by independent groups, conceptual dependence through shared theoretical frameworks, prior-knowledge contamination across paper summaries.
- A staged design is plausible: capture mechanical dependence as graph edges produced automatically, leave conceptual dependence as optional annotation.
- The major remaining uncertainty is whether mechanical detectability covers enough of the practical dependence landscape to make aggregation honest.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Related tasks: `[t024]`, `[t025]`, `[t031]`.
- Required data or analyses: enumerate dependence patterns; score each on detectability; prototype detectors for a few high-leverage patterns.
- Priority level: medium-high — load-bearing for H02/H03 but not blocking the initial t022 schema.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: `paper:Zhao2012`, `paper:Li2016`, `paper:Allen2017`, `paper:Majumdar2022`.

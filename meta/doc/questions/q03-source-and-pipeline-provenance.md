---
id: question:03-source-and-pipeline-provenance
type: question
title: How should Science represent source behavior and pipeline provenance in evidence
  aggregation?
status: active
ontology_terms: []
datasets: []
source_refs:
- paper:Zhao2012
- paper:Li2016
- paper:Allen2017
- paper:Han2026
- paper:Dai2023
- paper:Zhang2017CancerGenomics
- paper:Maity2020
- paper:Vahabi2022
related:
- question:01-evidence-payload-schema
- question:11-graph-valued-synthesis-artifacts
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
created: '2026-05-05'
updated: '2026-05-06'
---
# How should Science represent source behavior and pipeline provenance in evidence aggregation?

## Summary

Batch 2 shows that evidence aggregation depends on source behavior and the pipeline that produced the evidence, not only on study outputs.
Batch 4 reinforces and extends the question: graph-valued and integration-valued artifacts also carry source/pipeline state in the form of matched-sample status, missingness handling, biological-condition scope, view-scope, external-knowledge use, and group-borrowing structure.
This question asks how Science should represent source reliability, source dependence, omission semantics, missingness, cleaning, extraction, preprocessing, imputation, automated prior generation, source-to-target transport, view scope, and shared-structure-induced source dependence in the graph.

## Why It Matters

- Affects the Evidence Payload Schema task group, especially whether source and pipeline fields live on evidence payloads, first-class graph nodes, or both.
- Affects H02 because calibration gains may depend on modeling false positives, false negatives, source copying, and transformed-data provenance.
- Affects H03 because source and pipeline states become reason-coded revisit signals.
- Risk if unanswered: Science may overcount copied evidence, treat omissions as negative results, trust repaired data as raw observations, or import external data without transport assumptions.

## Current Evidence

- Zhao et al. model source quality with separate sensitivity and specificity, showing that omitted true values and asserted false values are different failure modes [@Zhao2012].
- Li et al. survey source dependence, copying, input uncertainty, and scoring-vs-labeling as central design choices in truth discovery [@Li2016].
- Allen argues that multi-view data integration requires preserving view identity, preprocessing provenance, missing views, and batch effects [@Allen2017].
- Dai and Shao show that external datasets can help or bias target-population estimation depending on source-to-target population assumptions [@Dai2023].
- Han et al. show that Bayesian data cleaning and LLM-assisted prior or constraint generation are upstream evidence-generation steps that need validation and provenance [@Han2026].
- Zhang, Ouyang, and Zhao show that biological-condition scope and shared-regulation assumptions function as both source-scope metadata and a dependence mechanism across condition-specific outputs of a single joint model [@Zhang2017CancerGenomics].
- Maity et al. show that pan-cancer survival integration ties evidence to specific source datasets (TCPA) with censoring, tumor-group exchangeability, and prior-correlation structure that induce dependence across tumor-specific claims [@Maity2020].
- Vahabi and Michailidis catalog matched-sample assumptions, missingness handling, sequential vs data-ensemble vs model-ensemble pipelines, and external-knowledge use as load-bearing pipeline-provenance fields for multi-omics integration [@Vahabi2022].
- The main conflicting pressure is representation cost: making every source and pipeline step first-class may be too heavy for routine use.

## Thoughts

- Best current interpretation: use a hybrid design.
  Keep a compact payload core for common fields, but allow first-class source, transformation, cleaning, extraction, and transport nodes when the provenance itself bears on multiple downstream claims.
- The minimum vocabulary should distinguish positive assertion, asserted absence, in-scope omission, not measured, missing by design, missing by failure, imputed, and repaired.
- Source dependence should be explicit graph structure, not a note on individual evidence items, because dependence often spans multiple claims.
- Joint-model shared-structure assumptions (group lasso across data types, common/unique component decomposition, correlated priors across tumor groups) are a distinct source-dependence pattern: a single model's outputs are mechanically dependent because they share an estimation prior, not because of citation or copying. This pattern is mechanically detectable from method metadata and should be represented as source dependence rather than as an opaque caveat.
- The major remaining uncertainty is where the threshold lies between "field on payload" and "entity in graph."

## Connections to Project

- Related hypotheses: `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`, `hypothesis:h01-stochastic-revisiting`.
- Required data or analyses: schema design pass for `[t022]`, source/pipeline reason-code design for `[t025]`, and an audit of existing paper summaries for field extractability.
- Priority level: high, because this question changes the minimum evidence payload and H01 attention design.

## Related

- Topic notes: `topic:structured-scientific-knowledge`, `topic:bayesian-methods-continuous-belief`.
- Article notes: Batch 2 and Batch 4 paper summaries under `doc/background/papers/`.
- Methods/Datasets: truth discovery, Bayesian data cleaning, multi-view data integration, heterogeneous external-data regression, joint graphical models, integrative survival prediction, and multi-omics integration taxonomies.

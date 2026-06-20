---
type: question
title: How should Science represent source behavior and pipeline provenance in evidence
  aggregation?
status: active
created: '2026-05-05'
updated: '2026-05-06'
id: question:0004-source-and-pipeline-provenance
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
- paper:Ding2025
- paper:Gong2024
- paper:Jiang2024
- paper:Jin2025
- paper:Yu2026
- paper:Zhang2025ScientificMethod
related:
- question:0002-evidence-payload-schema
- question:0008-llm-agents-as-fallible-sources
- question:0011-graph-valued-synthesis-artifacts
- question:0012-agent-tool-kg-operations
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
---
# How should Science represent source behavior and pipeline provenance in evidence aggregation?

## Summary

Batch 2 shows that evidence aggregation depends on source behavior and the pipeline that produced the evidence, not only on study outputs.
Batch 4 reinforces and extends the question: graph-valued and integration-valued artifacts also carry source/pipeline state in the form of matched-sample status, missingness handling, biological-condition scope, view-scope, external-knowledge use, and group-borrowing structure.
Batch 5 adds an operational layer: agent operations, tool chains, KG filtering, correlation discovery, and graph evolution events themselves shape what evidence exists, with their own dependency edges, safety state, and validation status [@Ding2025; @Jin2025; @Jiang2024; @Gong2024; @Yu2026; @Zhang2025ScientificMethod].
This question asks how Science should represent source reliability, source dependence, omission semantics, missingness, cleaning, extraction, preprocessing, imputation, automated prior generation, source-to-target transport, view scope, shared-structure-induced source dependence, agent/tool-chain provenance, and derived-KG-view provenance in the graph.

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
- Ding et al. show that scientific tool agents have I/O contracts, tool dependency graphs, planning/execution/summarization roles, and safety levels that should be represented as pipeline provenance rather than implicit code [@Ding2025].
- Jin et al. show that knowledge graphs themselves evolve through proliferation, fact validation, property error detection, dynamic embedding, and versioning — every graph state has its own provenance [@Jin2025].
- Jiang et al. (DiffKG) show that task-specific KG filtering creates derived KG views shaped by downstream objectives, so the filtered subgraph is a derived artifact distinct from its source graph [@Jiang2024].
- Gong et al. (Nexus) show that correlation discovery for hypothesis generation depends on spatio-temporal alignment, missingness handling, and interestingness filtering before the output can be used as evidence [@Gong2024].
- Yu et al. (SciCUEval) define context-understanding competencies (relevant-information identification, information-absence detection, multi-source integration, context-aware inference) that map directly to per-source pipeline-provenance reliability [@Yu2026].
- Zhang et al. review LLMs across literature review, hypothesis generation, experiment planning, tool use, data analysis, and discovery, motivating role-typed pipeline records so that hypothesis-generation outputs are not confused with validation evidence [@Zhang2025ScientificMethod].
- The main conflicting pressure is representation cost: making every source and pipeline step first-class may be too heavy for routine use.

## Thoughts

- Best current interpretation: use a hybrid design.
  Keep a compact payload core for common fields, but allow first-class source, transformation, cleaning, extraction, and transport nodes when the provenance itself bears on multiple downstream claims.
- The minimum vocabulary should distinguish positive assertion, asserted absence, in-scope omission, not measured, missing by design, missing by failure, imputed, and repaired.
- Source dependence should be explicit graph structure, not a note on individual evidence items, because dependence often spans multiple claims.
- Joint-model shared-structure assumptions (group lasso across data types, common/unique component decomposition, correlated priors across tumor groups) are a distinct source-dependence pattern: a single model's outputs are mechanically dependent because they share an estimation prior, not because of citation or copying. This pattern is mechanically detectable from method metadata and should be represented as source dependence rather than as an opaque caveat.
- Joint-operator dependence is a Batch-5 parallel: many evidence items can share a single agent, prompt version, tool chain, or derived KG view, which couples their reliability mechanically. These should be represented as source-side provenance edges to operation records, with their own validation status.
- Derived KG views (RAG contexts, task-conditioned subgraphs, correlation-discovery outputs, KG-diffusion denoised graphs) should be first-class views with source-graph reference, filter objective, and removed-edge policy — not silent replacements that override the source graph at read time.
- The major remaining uncertainty is where the threshold lies between "field on payload" and "entity in graph."

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`, `hypothesis:0001-stochastic-revisiting`.
- Required data or analyses: schema design pass for `[t022]`, source/pipeline reason-code design for `[t025]`, and an audit of existing paper summaries for field extractability.
- Priority level: high, because this question changes the minimum evidence payload and H01 attention design.

## Related

- Topic notes: `topic:structured-scientific-knowledge`, `topic:bayesian-methods-continuous-belief`.
- Article notes: Batch 2, Batch 4, and Batch 5 paper summaries under `doc/background/papers/`.
- Methods/Datasets: truth discovery, Bayesian data cleaning, multi-view data integration, heterogeneous external-data regression, joint graphical models, integrative survival prediction, multi-omics integration taxonomies, scientific tool agents, KG evolution, KG filtering, correlation discovery, and scientific context-understanding evaluation.

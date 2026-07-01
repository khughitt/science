---
type: question
title: How should Science represent agent operations, tool graphs, KG transformations,
  and graph evolution events?
status: active
created: '2026-05-06'
updated: '2026-07-01'
id: question:0012-agent-tool-kg-operations
ontology_terms: []
datasets: []
source_refs:
- cite:Dai2024GraphAttention
- cite:Gong2024
- cite:Jiang2024
- cite:Ding2025
- cite:Jin2025
- cite:Si2025
- cite:Zhang2025ScientificMethod
- cite:Yu2026
related:
- question:0004-source-and-pipeline-provenance
- question:0008-llm-agents-as-fallible-sources
- question:0010-causal-graph-construction-pipeline
- question:0011-graph-valued-synthesis-artifacts
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
---

# How should Science represent agent operations, tool graphs, KG transformations, and graph evolution events?

## Summary

Batch 5 shows that Science's graph is not only a belief store.
It is also an operational substrate for LLM agents, tool execution, context retrieval, KG filtering, graph updates, safety checks, and scientific workflow provenance.
This question asks how Science should represent agent operations, tool/skill graphs, derived KG views, and graph evolution events so that generated evidence remains auditable.

## Why It Matters

- Affects Q07 because LLM agents are fallible sources and graph-governed operators.
- Affects t029 because the research-papers workflow needs batch manifests, agent provenance, validation outputs, and abstention/missingness records.
- Affects H02 because calibration depends on whether graph updates preserve operational provenance.
- Affects H03 because agent/tool/KG failures create revisit reasons: agent-source-unvalidated, context-retrieval-uncertain, graph-version-stale, and attention-not-evidence.
- Risk if unanswered: Science will treat agent-generated graph updates and tool-chain outputs as transparent facts, losing tool dependencies, prompt context, safety state, validation history, and graph-version semantics.

## Current Evidence

- SciToolAgent models tool dependencies, I/O formats, safety levels, planning, execution, and summarization as a scientific agent architecture [@Ding2025].
- Jin et al. show that KGs require evolution machinery: proliferation, fact validation, property error detection, dynamic embedding, and versioning [@Jin2025].
- DiffKG shows that task-specific KG filtering creates derived KG views shaped by downstream objectives [@Jiang2024].
- Nexus shows that correlation discovery depends on spatio-temporal alignment, missingness handling, and interestingness filtering before it can support hypothesis generation [@Gong2024].
- Si et al. show that LLM evaluation should distinguish absence of evidence from evidence of absence using Bayes factors [@Si2025].
- SciCUEval identifies scientific context-understanding competencies: relevant information identification, information-absence detection, multi-source information integration, and context-aware inference [@Yu2026].
- Zhang et al. review LLM roles across the scientific method and emphasize integration with human goals and clear evaluation metrics [@Zhang2025ScientificMethod].
- Dai highlights the need to distinguish causal graph structure, graph attention, and predictive outputs [@Dai2024GraphAttention].

## Thoughts

- Best current interpretation: add an operations layer with typed entities for `agent`, `tool`, `skill`, `tool_chain`, `execution_trace`, `kg_view`, and `graph_update_event`.
- The `[t037]` design/prototype pass completed the `agent-tool-operation` contract: operation records are provenance payloads, not direct evidence; successful operation records cannot `strengthen-belief` directly; blocking operation codes propagate into downstream payloads through provenance references or co-loaded extensions.
- Minimum fields should include agent role, model version, prompt/workflow reference, tool chain, I/O contract, safety policy, execution trace, KG source, KG filter objective, graph version, validation status, abstention reason, and evaluation protocol.
- Derived contexts and filtered subgraphs should be first-class views, not silent replacements for source graphs.
- The major uncertainty is implementation scope: the production registry, durable validator integration, `agent-evaluation` records, cross-payload propagation, and trace/frontmatter sidecars for project-local operation records are future work.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Related tasks: `[t029]`, `[t033]`, `[t037]`, `[t038]`.
- Required data or analyses: production operation-record registry and validator design, tool/skill graph schema, graph evolution event taxonomy, and project-local agent evaluation plan.
- Priority level: high for any automated graph-building or tool-execution workflow.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: Batch 5 summaries under `doc/background/papers/`.
- Methods/Datasets: scientific tool agents, KG evolution, KG filtering, RAG/context evaluation, Bayesian LLM evaluation, correlation discovery, graph attention.

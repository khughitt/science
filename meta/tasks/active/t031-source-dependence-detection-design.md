---
id: t031
project: ''
title: Source-dependence detection design
type: ''
aspects:
- software-development
- framework-design
- hypothesis-testing
priority: P2
status: proposed
blocked_by: []
related:
- task:t024
- task:t025
- task:t033
- task:t035
- task:t037
- task:t038
- question:0004-source-and-pipeline-provenance
- question:0006-source-dependence-detection
- question:0008-llm-agents-as-fallible-sources
- question:0011-graph-valued-synthesis-artifacts
- question:0012-agent-tool-kg-operations
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
parent: task:t021
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Stratify evidence-source dependence patterns by mechanical detectability and prototype detectors for the high-leverage cases.

Mechanically detectable candidates: shared dataset identifiers, shared author lists, citation chains, shared extractor or prompt versions, near-duplicate text, shared upstream synthesis nodes, joint-model shared-structure dependence (when multiple condition-, subtype-, view-, or platform-specific outputs come from a single estimator with group lasso, common/unique component decomposition, correlated priors across groups, or shared sparsity), shared posterior sampler / approximation runs (when multiple graph-feature claims are read from the same posterior chain or variational fit), joint-operator dependence (when multiple evidence items are produced by the same agent, model version, prompt or system-prompt version, or tool chain), and shared-KG-view dependence (when multiple downstream claims are derived from the same task-conditioned subgraph, RAG retrieval context, correlation graph, or KG-diffusion view, even when the ostensibly underlying source graph differs).
Annotation-required candidates: methodological convergence by independent groups, conceptual dependence through shared theoretical frameworks, prior-knowledge contamination across paper summaries.

Deliverables:
- a dependence-pattern taxonomy with detectability score per pattern;
- prototype detectors for two or three high-leverage patterns;
- a design note for how detected dependence attaches to evidence edges and propagates to aggregation operators;
- alignment notes with `[t024]` (heterogeneity / bias mechanisms) and `[t025]` (reason codes).

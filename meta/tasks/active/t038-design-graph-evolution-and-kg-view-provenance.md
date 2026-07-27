---
id: t038
project: ''
title: Design graph evolution and KG view provenance
type: ''
aspects:
- software-development
- framework-design
- causal-modeling
- hypothesis-testing
priority: P1
status: proposed
blocked_by: []
related:
- task:t021
- task:t035
- task:t037
- question:0012-agent-tool-kg-operations
- question:0004-source-and-pipeline-provenance
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
parent: ''
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-06'
completed: null
---

Design how Science records graph evolution, graph versions, KG filtering, derived KG views, and replayable graph update events.

Candidate event types:
- entity creation;
- evidence edge creation;
- graph edge creation;
- rename;
- merge;
- split;
- deprecation;
- validation;
- contradiction;
- derived-view generation;
- embedding-view generation;
- rollback or replay.

Deliverables:
- a `graph_update_event` taxonomy with strict enum candidates;
- a versioning model for graph state, derived KG views, embedding views, and batch-generated updates;
- provenance fields for `kg_view_ref`, `source_graph_ref`, `kg_filter_objective`, `subgraph_selection_method`, `removed_edge_policy`, `graph_version`, `graph_update_event_type`, `validation_status`, and `replay_command`;
- guidance for representing RAG contexts, task-conditioned subgraphs, correlation-discovery outputs, and KG diffusion/denoising views;
- H03 reason-code mapping for `kg-view-derived`, `graph-version-stale`, `attention-not-evidence`, and `context-retrieval-uncertain`.

Start from Batch 5 synthesis: `entities/synthesis/0006-synthesis-scientific-agents-and-knowledge-graph-infrastructure.md`.

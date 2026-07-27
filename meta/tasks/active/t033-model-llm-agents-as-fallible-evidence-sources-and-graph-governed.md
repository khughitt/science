---
id: t033
project: ''
title: Model LLM agents as fallible evidence sources and graph-governed operators
type: ''
aspects:
- software-development
- framework-design
- research
priority: P2
status: active
blocked_by: []
related:
- task:t022
- task:t024
- task:t031
- task:t037
- task:t038
- question:0008-llm-agents-as-fallible-sources
- question:0006-source-dependence-detection
- question:0012-agent-tool-kg-operations
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
parent: ''
group: agent-source-modeling
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Treat LLM agents (paper summarizers, claim extractors, batch synthesizers, attention samplers, curation assistants, tool-using science agents) as first-class fallible source entities AND as graph-governed operators, and design the minimum representation.

Deliverables:
- a taxonomy of agent roles in this project, with current and planned uses (source-side: summarizer, extractor, synthesizer, sampler; operator-side: planner, tool executor, KG mutator, retriever, evaluator);
- a minimal agent-source schema: agent identifier, model version, prompt or system-prompt version, tool version, validation history, and dependence links to other agents;
- an operator-side extension covering `tool_chain_ref`, `tool_io_contract`, `execution_trace_ref`, `safety_policy_ref`, `abstention_reason`, `agent_evaluation_protocol`, and Bayes-factor-style evaluation history (per Si2025) that distinguishes "no evidence of bias" from "evidence of no bias";
- a `derived_by` field design for evidence payloads, plus a `validation_status` field;
- an alignment note with `[t031]` on shared-prompt, shared-model, shared-tool-chain, and shared-KG-view dependence;
- alignment with `[t037]` (operations schema) so the source-side agent record links to operator-side records via shared identifiers rather than duplicating fields;
- a self-application pass: mark which existing artifacts in this project (including the Batch 1, Batch 2, Batch 3, Batch 4, and Batch 5 syntheses) should be retroactively annotated with agent provenance, and at what granularity.

Granularity is a key design decision; expect to defend the chosen level (per-prompt, per-tool-version, per-model) against alternatives.

**Inputs from `[t030]` D4 (2026-05-06)** at `meta/doc/plans/historical/2026-05-06-t030-full-audit-results.md`: two verbatim-identical blind-LLM extraction passes disagreed within-1 on ~25–40% of rubric-ambiguous fields, with systematic pass-1-higher-than-pass-2 calibration drift (17/25 cases). Implications for this task: (a) per-extraction confidence and per-call agent identity are needed in agent-source records; (b) ensemble-of-N or repeated-extraction-with-disagreement-flagging should be considered for high-stakes fields; (c) the deferred full-context-manual-vs-blind-LLM signal is required to fully ground this task and should be obtained via a fresh audit before agent-source modeling commits.

### Notes

- 2026-05-08: Scope reduced (2026-05-08): t037 v1.3 design absorbs source-side agent schema (agent/agent_role registry entities, validation_status, agent-evaluation extension with Si2025 Bayes-factor semantics). Residual t033 scope to re-evaluate when t037 closes: (a) self-application / retroactive agent-provenance pass on Batch 1-5 syntheses; (b) granularity decision (per-prompt vs per-tool-version vs per-model); (c) source-dependence integration with t031 (shared prompt/model/tool-chain/KG-view); (d) repeated-extraction-with-disagreement policy per t030 D4 calibration drift finding.

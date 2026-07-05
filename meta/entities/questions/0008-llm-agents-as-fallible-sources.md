---
kind: question
title: How should Science model LLM agents as fallible evidence sources and graph-governed
  operators?
status: active
created: '2026-05-05'
updated: '2026-05-06'
id: question:0008-llm-agents-as-fallible-sources
ontology_terms: []
datasets: []
source_refs:
- cite:Han2026
- cite:Zhao2012
- cite:Li2016
- cite:Allen2017
- cite:Ban2023
- cite:Jiralerspong2024
- cite:Liu2024HiddenWorld
- cite:Wan2025
- cite:Wang2025
- cite:Ding2025
- cite:Si2025
- cite:Zhang2025ScientificMethod
- cite:Yu2026
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0002-evidence-payload-schema
- question:0004-source-and-pipeline-provenance
- question:0006-source-dependence-detection
- question:0010-causal-graph-construction-pipeline
- question:0012-agent-tool-kg-operations
- topic:structured-scientific-knowledge
---

# How should Science model LLM agents as fallible evidence sources and graph-governed operators?

## Summary

Han et al. introduce LLM-assisted prior and constraint generation as upstream evidence, with explicit validation requirements [@Han2026].
Batch 3 adds a stronger causal-graph case: LLMs can propose variables, priors, constraints, graph structures, and post-refinements, but those outputs are weak prior or pipeline evidence rather than causal truth [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
Batch 5 adds an operational case: LLM agents can plan tool chains, execute tools, summarize results, generate hypotheses, and update knowledge graphs, so they are operators as well as sources [@Ding2025; @Zhang2025ScientificMethod].
The Science project itself uses LLM agents for paper summarization, claim extraction, batch synthesis, attention sampling, and many curation tasks.
Each agent is a Zhao2012-style fallible source with its own sensitivity, specificity, prompt-version dependence, and shared-pipeline correlations.
This question asks how the project should represent LLM agents as evidence sources and graph-governed operators whose reliability, tool use, context retrieval, safety status, and graph updates must be tracked, decomposed, and updated.

## Why It Matters

- Affects whether agent-produced paper summaries, extracted claims, and synthesis artifacts can be trusted as evidence inputs to downstream propositions.
- Affects H02 calibration: agent-produced fields inherit agent biases, and treating them as raw observations will overstate independence and underestimate failure modes.
- Affects H03 attention: agent-source reliability is a candidate reason code (`agent-extraction-uncertain`, `agent-prompt-version`, `agent-self-citation`).
- Affects the project's own self-model: many of the synthesis artifacts informing this question were produced by an LLM agent.
- Affects command/skill design: agent-produced artifacts should carry operation provenance, tool-chain references, validation outcomes, and abstention reasons.
- Risk if unanswered: the graph treats LLM agents as transparent extractors rather than as sources, and fails to detect agent-driven dependence across many ostensibly independent claims.

## Current Evidence

- Han et al. demonstrate that LLM-generated priors and constraints require validation diagnostics and provenance to function as evidence inputs [@Han2026].
- Ban, Jiralerspong, Liu, Wan, and Wang show several causal-graph roles for LLMs: direct graph elicitation, soft-prior construction, weak-prior decomposition, variable proposal, and post-refinement [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
- Ding et al. show that scientific tool agents need tool dependency graphs, I/O contracts, planning/execution/summarization roles, and safety checks [@Ding2025].
- Si et al. show that LLM bias can be evaluated with Bayesian hypothesis testing and Bayes factors, distinguishing no evidence from evidence of no bias [@Si2025].
- Yu et al. define scientific context-understanding competencies that map to agent evaluation: relevant information identification, information-absence detection, multi-source integration, and context-aware inference [@Yu2026].
- Zhao et al. and Li et al. provide the source-quality decomposition framework (sensitivity, specificity, copying, conditional dependence) that applies directly to LLM extractors [@Zhao2012; @Li2016].
- Allen's multi-view discussion implies that LLM extractors are themselves a "view" with their own measurement model and missingness behavior [@Allen2017].
- The project uses Anthropic Claude variants for the bulk of paper summaries and synthesis artifacts; prompt versions, model versions, and tool versions are not currently recorded as evidence-source metadata.

## Thoughts

- Best current interpretation: LLM agents should be modeled as first-class source entities with at least: agent identifier, model version, prompt or system-prompt version, tool version, validation history, and dependence links to other agents that share prompts or upstream tools.
- Agent-produced fields on evidence payloads should carry a `derived_by` reference to the agent and a `validation_status` field.
- LLM causal outputs should additionally record `prompt_provenance`, `variable_proposal_provenance`, `constraint_type`, `prior_role`, and whether the output is intended as a hard constraint, weak prior, hypothesis generator, or validated causal update.
- LLM tool operations should record `tool_chain_ref`, `tool_io_contract`, `execution_trace_ref`, `safety_policy_ref`, `abstention_reason`, and `agent_evaluation_protocol`.
- Shared prompts and shared models induce dependence across many evidence items; this overlaps with `question:0006-source-dependence-detection`.
- The major remaining uncertainty is granularity: is one agent-source-per-prompt-version too fine, and is one-per-model too coarse?

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Related questions: `question:0004-source-and-pipeline-provenance`, `question:0006-source-dependence-detection`, `question:0012-agent-tool-kg-operations`.
- Related tasks: `[t022]`, `[t024]`, `[t033]`, `[t037]`, `[t038]`.
- Required data or analyses: a taxonomy of agent roles in the project, a minimal agent-source/operator schema, and a small audit of how agent-produced content should mark itself.
- Priority level: medium-high — directly load-bearing for the project's own evidence chain.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: `paper:Han2026`, `paper:Zhao2012`, `paper:Li2016`, `paper:Allen2017`, `paper:Ding2025`, `paper:Si2025`, `paper:Yu2026`.

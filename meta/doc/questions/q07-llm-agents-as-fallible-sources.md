---
id: question:07-llm-agents-as-fallible-sources
type: question
title: How should Science model LLM agents (summarizers, extractors, synthesizers) as fallible evidence sources?
status: active
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
related:
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- question:05-source-dependence-detection
- question:10-causal-graph-construction-pipeline
- topic:structured-scientific-knowledge
created: '2026-05-05'
updated: '2026-05-06'
---

# How should Science model LLM agents (summarizers, extractors, synthesizers) as fallible evidence sources?

## Summary

Han et al. introduce LLM-assisted prior and constraint generation as upstream evidence, with explicit validation requirements [@Han2026].
Batch 3 adds a stronger causal-graph case: LLMs can propose variables, priors, constraints, graph structures, and post-refinements, but those outputs are weak prior or pipeline evidence rather than causal truth [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
The Science project itself uses LLM agents for paper summarization, claim extraction, batch synthesis, attention sampling, and many curation tasks.
Each agent is a Zhao2012-style fallible source with its own sensitivity, specificity, prompt-version dependence, and shared-pipeline correlations.
This question asks how the project should represent LLM agents as evidence sources whose reliability must be tracked, decomposed, and updated.

## Why It Matters

- Affects whether agent-produced paper summaries, extracted claims, and synthesis artifacts can be trusted as evidence inputs to downstream propositions.
- Affects H02 calibration: agent-produced fields inherit agent biases, and treating them as raw observations will overstate independence and underestimate failure modes.
- Affects H03 attention: agent-source reliability is a candidate reason code (`agent-extraction-uncertain`, `agent-prompt-version`, `agent-self-citation`).
- Affects the project's own self-model: many of the synthesis artifacts informing this question were produced by an LLM agent.
- Risk if unanswered: the graph treats LLM agents as transparent extractors rather than as sources, and fails to detect agent-driven dependence across many ostensibly independent claims.

## Current Evidence

- Han et al. demonstrate that LLM-generated priors and constraints require validation diagnostics and provenance to function as evidence inputs [@Han2026].
- Ban, Jiralerspong, Liu, Wan, and Wang show several causal-graph roles for LLMs: direct graph elicitation, soft-prior construction, weak-prior decomposition, variable proposal, and post-refinement [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
- Zhao et al. and Li et al. provide the source-quality decomposition framework (sensitivity, specificity, copying, conditional dependence) that applies directly to LLM extractors [@Zhao2012; @Li2016].
- Allen's multi-view discussion implies that LLM extractors are themselves a "view" with their own measurement model and missingness behavior [@Allen2017].
- The project uses Anthropic Claude variants for the bulk of paper summaries and synthesis artifacts; prompt versions, model versions, and tool versions are not currently recorded as evidence-source metadata.

## Thoughts

- Best current interpretation: LLM agents should be modeled as first-class source entities with at least: agent identifier, model version, prompt or system-prompt version, tool version, validation history, and dependence links to other agents that share prompts or upstream tools.
- Agent-produced fields on evidence payloads should carry a `derived_by` reference to the agent and a `validation_status` field.
- LLM causal outputs should additionally record `prompt_provenance`, `variable_proposal_provenance`, `constraint_type`, `prior_role`, and whether the output is intended as a hard constraint, weak prior, hypothesis generator, or validated causal update.
- Shared prompts and shared models induce dependence across many evidence items; this overlaps with `question:05-source-dependence-detection`.
- The major remaining uncertainty is granularity: is one agent-source-per-prompt-version too fine, and is one-per-model too coarse?

## Connections to Project

- Related hypotheses: `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Related tasks: `[t022]`, `[t024]`, `[t033]`.
- Related questions: `question:03-source-and-pipeline-provenance`, `question:05-source-dependence-detection`.
- Required data or analyses: a taxonomy of agent roles in the project, a minimal agent-source schema, and a small audit of how agent-produced content should mark itself.
- Priority level: medium-high — directly load-bearing for the project's own evidence chain.

## Related

- Topic notes: `topic:structured-scientific-knowledge`.
- Article notes: `paper:Han2026`, `paper:Zhao2012`, `paper:Li2016`, `paper:Allen2017`.

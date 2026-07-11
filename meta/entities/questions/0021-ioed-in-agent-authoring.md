---
id: question:0021-ioed-in-agent-authoring
kind: question
title: Does the illusion of explanatory depth affect AI-agent-drafted causal claims
  in Science, and how should the toolkit detect or bound it?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Keil2006
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0008-llm-agents-as-fallible-sources
- question:0005-authoring-cost-audit
created: '2026-07-10'
updated: '2026-07-10'
---

# Does the illusion of explanatory depth affect AI-agent-drafted causal claims in Science, and how should the toolkit detect or bound it?

## Summary

Keil (2006) documents that people reliably overestimate how deeply they understand causal
mechanisms — the "illusion of explanatory depth" (IOED). This miscalibration is specific
to mechanistic-causal knowledge and arises partly from confusing high-level functional
knowledge ("a carburetor mixes fuel and air") with genuine mechanistic understanding.
This question asks whether the same bias applies to LLM agents drafting causal evidence
statements or propositions in Science, and whether the toolkit can detect or structurally
bound it.

## Why It Matters

- Affects the design of evidence-payload requirements for mechanistic claims: if agents
  routinely express functional-level understanding as mechanistic confidence, belief
  calibration in the graph will be systematically inflated.
- Affects `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`: richer
  payloads (mechanism chain, evidence type, depth flag) may be the primary mitigation.
- Risk if unanswered: propositions authored by agents may carry surface-confident
  mechanistic claims that are actually only functional-level stubs, leading to
  overconfident causal edges that resist revision.

## Current Evidence

- Keil (2006) / Rozenblit & Keil (2002): robust empirical evidence for IOED in human
  subjects across artifact and device domains; specific to causal-mechanistic knowledge.
- `question:0008-llm-agents-as-fallible-sources`: current project thinking treats LLM
  agents as fallible evidence sources, but has not yet distinguished mechanism-depth
  failures from other error modes.
- `question:0005-authoring-cost-audit`: documents patterns of under-specification in
  agent-authored claims, which may overlap with IOED-like confusions.
- No direct experiment has probed IOED-equivalent calibration in LLM agents on causal
  mechanism tasks in this project.

## Thoughts

- Best current interpretation: IOED is plausibly present in LLM authoring because the
  function-for-mechanism confusion is a structural feature of how high-level descriptions
  are generated from pattern-matched training, not a uniquely human cognitive bias.
- The clearest mitigation is a typed evidence field that distinguishes `functional_relation`
  (A causes B, mechanism unspecified) from `mechanistic_support` (A causes B via
  identified mechanism M), which forces the distinction at authoring time rather than
  leaving it to downstream inference.
- Major uncertainty: whether agent-authored claims systematically show inflated mechanistic
  confidence or whether the error mode is qualitatively different (e.g., hallucinated
  mechanism rather than conflated functional/mechanistic depth).

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
  (evidence payload typed to mechanism depth as mitigation);
  `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`
  (reason code `function_for_mechanism` as a revisit trigger).
- Required data or analyses: audit a sample of agent-drafted propositions in the graph
  for functional-vs-mechanistic depth; compare confidence ratings to available mechanistic
  evidence.
- Priority level: medium — downstream of belief-payload schema design but load-bearing
  for agent-authoring quality.

## Related

- Topic notes: `paper:Keil2006` (primary source); Rozenblit & Keil (2002) for the
  original IOED experiments.
- Article notes: `question:0008-llm-agents-as-fallible-sources`,
  `question:0005-authoring-cost-audit`.
- Methods/Datasets: IOED probe adapted to proposition-generation tasks.

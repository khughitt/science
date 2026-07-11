---
id: question:0023-outsourced-explanation-provenance
kind: question
title: How should Science model the depth and delegation of explanatory understanding
  in agent-sourced evidence provenance?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Keil2006
related:
- question:0012-agent-tool-kg-operations
- question:0008-llm-agents-as-fallible-sources
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# How should Science model the depth and delegation of explanatory understanding in agent-sourced evidence provenance?

## Summary

Keil (2006) shows that human agents deal with the inevitable incompleteness of their own
explanatory understanding by outsourcing explanatory responsibility to identified experts,
while maintaining a coarse causal gist sufficient to know who to trust and what to ask.
This question asks how Science should represent this delegation in provenance: when an
agent cites an external source for a mechanistic claim, what does the provenance record
need to capture to distinguish (a) the agent verified the source, (b) the agent delegated
without verification, and (c) the agent merely forwarded a reference it did not interrogate?

## Why It Matters

- Affects the provenance schema for evidence lines: current provenance records source
  identity and access method, but not the depth of the authoring agent's own engagement
  with the source's mechanistic content.
- Affects `question:0012-agent-tool-kg-operations`: if agent operations in the KG include
  evidence delegation chains, the graph needs a way to represent delegation depth without
  conflating it with source credibility.
- Risk if unanswered: a citation to a mechanistic source is treated as equivalent to
  verified mechanistic understanding, masking shallow-outsourcing errors and inflating
  confidence in causal edges that rest on unverified delegation.

## Current Evidence

- Keil (2006): empirical and theoretical account of cognitive outsourcing; people
  maintain "who knows what" metadata that allows them to route explanatory queries to
  appropriate experts without understanding the mechanism themselves.
- `hypothesis:0007-working-model` (h00): the patchwork model explicitly carries
  provenance (ProvenanceType and PROV agent); but the current schema does not yet
  distinguish "authoring agent verified mechanism" from "authoring agent forwarded citation".
- `question:0008-llm-agents-as-fallible-sources`: motivates tracking agent fallibility
  but does not yet address depth-of-delegation.

## Thoughts

- Best current interpretation: provenance for mechanistic evidence lines should include a
  `delegation_depth` or `verification_mode` field with values such as:
  `self_verified` | `source_delegated` | `citation_forwarded` (unread primary source).
  This mirrors Keil's tripartite distinction between knowing a mechanism, knowing who
  knows a mechanism, and merely possessing a citation label.
- The framework for this already exists structurally in PROV-O (activity/agent modeling),
  but the Science schema has not specialized it for explanation depth.
- Major uncertainty: whether "delegation depth" is better captured as a provenance field
  on evidence lines or as a reason code on beliefs. The former is more compositional;
  the latter integrates better with the existing revisiting machinery.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (provenance as first-class field);
  `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration` (richer payload
  includes delegation depth).
- Required data or analyses: design a `verification_mode` extension to the evidence-line
  provenance schema; audit existing evidence lines for delegation depth.
- Priority level: medium — dependent on completing the evidence-payload schema work
  (`question:0002-evidence-payload-schema`) before specializing to delegation depth.

## Related

- Topic notes: `paper:Keil2006` (primary source; distributed cognition / outsourcing
  section); Hutchins (1995) on distributed cognition in groups.
- Article notes: `question:0012-agent-tool-kg-operations`,
  `question:0008-llm-agents-as-fallible-sources`,
  `question:0002-evidence-payload-schema`.
- Methods/Datasets: PROV-O activity/agent modeling as the underlying substrate.

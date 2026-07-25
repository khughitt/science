---
id: question:0054-adversarial-source-text-graph-poisoning
kind: question
title: Adversarial source text as a graph-poisoning vector
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- question:0008-llm-agents-as-fallible-sources
created: '2026-07-25'
updated: '2026-07-25'
---
# Adversarial source text as a graph-poisoning vector

## Summary

Annotation and extraction agents read source text — persisted `.source.md` paper bodies,
entity-annotation output, and web-fetched material — and write the results into the
graph as propositions, evidence lines, and relations. That source text is **untrusted
input**. A document crafted to carry instructions rather than only content can influence
what an annotating agent extracts, and the resulting claim enters the graph carrying full
provenance, which makes it look *more* credible rather than less.

This question asks what the threat model is, and what the toolkit should do about it.

Surfaced during the 2026-07-25 `explore-ideas` triage rather than by a lens agent: the blind pass could not reach it, because the lens agents had no view of what the project already asks.

## Why It Matters

- The graph's integrity assumption is currently that agents are *fallible*
  (`question:0008`) — noisy, miscalibrated, prompt-version dependent. It does not model
  agents as *manipulable by their inputs*, which is a different failure mode with a
  different mitigation.
- Provenance amplifies the harm: a poisoned claim that resolves to a real DOI with a real
  citekey and a recorded extraction run is indistinguishable, by every check the graph
  currently applies, from a sound one.
- Risk if unanswered: the sub-article annotation and paper-persistence pipelines scale up
  exactly the ingestion surface where this applies, with no boundary between "text to
  summarize" and "instructions to follow".

## Current Evidence

- The toolkit persists source text and runs extraction agents over it; the pipeline is
  established, and its inputs are arbitrary third-party documents.
- `question:0008` models LLM agents as fallible sources with sensitivity and specificity,
  which covers random error but not adversarially-chosen error.
- No project artifact currently records a trust boundary on source text, nor any check
  that an extracted claim is supported by a span of the source it claims to come from.

## Thoughts

- Best current interpretation: the cheapest structural mitigation is span-grounding —
  requiring an extracted claim to point at the source text that licenses it, so an
  assertion with no supporting span is detectable regardless of how it got in.
- Major remaining uncertainty: whether this is a live risk at current scale or a
  speculative one. It becomes materially more serious the moment ingestion is automated
  over sources the researcher did not personally select.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
- Required analyses: write the threat model; assess whether span-grounding is feasible in
  the current annotation path.
- Priority level: medium-high — low current exposure, poor current detectability.

## Related

- Topic notes: `topic:structured-scientific-knowledge`

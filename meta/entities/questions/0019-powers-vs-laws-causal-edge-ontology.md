---
id: question:0019-powers-vs-laws-causal-edge-ontology
kind: question
title: Should the Science toolkit's causal-edge semantics adopt a powers-based (dispositional)
  ontology rather than a regularity-based one?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Mumford2004
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the Science toolkit's causal-edge semantics adopt a powers-based (dispositional) ontology rather than a regularity-based one?

## Summary

When the Science toolkit places a directed edge in a causal graph, what is the edge
asserting? Two broad options exist: (a) a *regularity* — the source variable is
followed by the target variable across observed cases, summarized by an estimand;
or (b) a *power / disposition* — the source entity has an intrinsic causal capacity
that produces the target, independent of whether it has been observed to do so.
Mumford [@Mumford2004] and Cartwright (1999) argue against regularity-based accounts;
Mumford's positive account grounds causal necessity in modal properties rather than
governing laws. This question asks whether adopting (b) — even informally — would
improve edge semantics in the Science graph model.

## Why It Matters

- **Causal-edge label discipline**: if an edge means "power" rather than "regularity,"
  then a statistical association edge and a mechanistic causal edge must be
  represented differently — supporting the toolkit's existing causal-estimand
  guardrail work (`hypothesis:0004`).
- **Patchwork model grounding**: the working model (`hypothesis:0007`) describes
  patches as epistemic neighborhoods surrounding hypotheses/evidence clusters; a
  powers ontology grounds why patches are genuinely local (capacities are held by
  entities, not universal law instances).
- **Risk if unanswered**: conflating regularity-based and powers-based edges leaves
  the guardrail schema under-motivated philosophically, and may lead to inconsistent
  handling of mechanistic vs. statistical evidence.

## Current Evidence

- Mumford (2004) argues that powers supply all the work laws were supposed to do,
  and that a regularity account cannot non-trivially explain its own instances
  [@Mumford2004]. [INACCESSIBLE: Chapters 2–12 of the preview unavailable]
- Cartwright (1999) argues for capacities over laws on scientific grounds (nomological
  machines; ceteris paribus universality fails). [MISSING_CITATION: Cartwright 1999
  not yet in entities/papers/]
- The Science working model already informally uses dispositional language ("patches
  grow as evidence assesses specific beliefs") but has not committed to a formal
  ontological stance on edge semantics.
- The causal-estimand guardrail (H04) implicitly requires that evidence be matched
  to the mechanism it bears on — a powers framing supports this requirement directly.

## Thoughts

- **Best current interpretation**: the toolkit's existing edge vocabulary (association
  vs. causal) already reflects a practical powers/regularity distinction; the question
  is whether to make this philosophical grounding explicit in documentation and schema.
- **Major uncertainty**: whether the distinction between powers-based and
  regularity-based causal edges is operationally testable in the toolkit's workflows,
  or whether it remains purely conceptual scaffolding.
- A pragmatic first step would be to annotate existing causal edges with a
  `mechanism_class` field distinguishing statistical-regularity from mechanistic-power
  claims, deferring a full ontological commitment.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model`, `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`
- Required data or analyses: None immediately; a philosophical design discussion
  against the current graph schema would be needed first.
- Priority level: Low-medium (philosophical grounding; blocked on completing H04
  guardrail implementation before ontology stabilization makes sense).

## Related

- Topic notes: `hypothesis:0007-working-model` (patchwork model), `hypothesis:0004`
- Article notes: `paper:Mumford2004`; future intakes: Cartwright (1999), Molnar (2003), Ellis (2001)
- Methods/Datasets: N/A

---
id: question:0052-adoption-realism-for-structured-knowledge
kind: question
title: Adoption realism for structured scientific knowledge
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- topic:structured-scientific-knowledge
created: '2026-07-25'
updated: '2026-07-25'
---
# Adoption realism for structured scientific knowledge

## Summary

`topic:structured-scientific-knowledge` records that both prior lines of structured
scientific knowledge — nanopublications and research knowledge graphs — have absorbed
more than a decade of effort and substantial funding without becoming routine
infrastructure for working scientists, and states plainly that any new project in this
space "should treat adoption as the hard problem, not the data model." The topic then
says this adoption question "deserves its own entry under `doc/questions/`". That entry
was never written. This is it.

The question is not *why did they stall* — the topic already lists candidate factors.
It is: **what does Science do differently, and if the honest answer is "nothing
structural", does the project explicitly accept that it is betting on an ecosystem that
may not materialise?**

Surfaced during the 2026-07-25 `explore-ideas` triage rather than by a lens agent: the blind pass could not reach it, because the lens agents had no view of what the project already asks.

## Why It Matters

- Decides whether the project's long-range bets (forkable/shareable project packages,
  graph export, commons promotion) rest on a mechanism or on hope.
- Determines whether adoption cost should be a first-class design constraint that can
  *veto* an otherwise epistemically attractive schema addition — which would make this
  question load-bearing over `question:0005` and `question:0057`.
- Risk if unanswered: the project reproduces the prior art's outcome while believing it
  is doing something new, and only discovers the difference was cosmetic after the
  design has hardened.

## Current Evidence

- The two prior lines are documented in `topic:structured-scientific-knowledge`:
  nanopublications bet on per-claim atomicity and can be machine-generated;
  research knowledge graphs bet on per-contribution curation. Neither dominated, and
  adoption is thin outside biomedicine and computer science.
- One structural difference is already visible and unexamined: Science's structure is
  authored by an LLM agent as a side effect of work the researcher wanted done anyway,
  rather than by a human performing curation as a separate act. If authoring friction is
  the dominant barrier, that difference is the whole bet — and it is testable.
- Countervailing: `question:0043` raises the possibility that agent-authored structure
  degrades the researcher, and `question:0057` that its marginal return is low. If either
  holds, the friction argument does not rescue adoption.

## Thoughts

- Best current interpretation: the agent-authoring difference is real but unproven, and
  the project has never stated it as its adoption thesis. Stating it explicitly would make
  it falsifiable.
- Major remaining uncertainty: whether the barrier was ever really friction, or whether it
  was the absence of a cross-claim query valuable enough to justify the structure at all —
  in which case lowering authoring cost changes nothing.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model`
- Required analyses: articulate the adoption thesis explicitly; identify what observation
  would falsify it.
- Priority level: high — it bounds what the project can claim its tooling is for.

## Related

- Topic notes: `topic:structured-scientific-knowledge`

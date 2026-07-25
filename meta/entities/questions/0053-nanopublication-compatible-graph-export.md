---
id: question:0053-nanopublication-compatible-graph-export
kind: question
title: Nanopublication-compatible export of the evidence graph
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
# Nanopublication-compatible export of the evidence graph

## Summary

`topic:structured-scientific-knowledge` flags export format as a design decision the
project must reach rather than drift into: if Science ever exports a project's evidence
graph for external reuse, "nanopublication-compatible serialisation is a serious
candidate and should be evaluated against alternatives before an ad-hoc format is
chosen." No entity has held that decision until now.

The question is whether the graph's durable export target should be
assertion/provenance/publication-info named graphs with content-addressed identifiers,
or something else — and what the current TriG-plus-YAML serialisation would have to
change to make either possible.

Surfaced during the 2026-07-25 `explore-ideas` triage rather than by a lens agent: the blind pass could not reach it, because the lens agents had no view of what the project already asks.

## Why It Matters

- Export format is a one-way door in practice: once downstream consumers exist, the
  format is load-bearing and changing it breaks them.
- Ties directly to identity and immutability. The topic notes Science has **no
  immutability guarantee on proposition identity today**, and that this becomes
  load-bearing the moment projects share or fork — which the cross-project composition
  work already enables.
- Risk if unanswered: an ad-hoc export format gets chosen implicitly by whoever first
  needs one, and the trusty-URI-style identity question is answered by default rather
  than by decision.

## Current Evidence

- Current serialisation is TriG plus YAML frontmatter, built deterministically from
  canonical sources — structurally close to, but not identical with, the
  assertion/provenance/pubinfo split.
- Content-addressing already exists in the toolkit for *sources* (`SourceSnapshot`
  content-hashing), but not for propositions as citable units.
- The granularity question is genuinely open: the project sits between per-claim and
  per-paper granularity, and export forces a choice the internal model has been able to
  defer.

## Thoughts

- Best current interpretation: evaluate nanopublication-compatible export as the default
  candidate precisely because it forces the identity question, not because
  interoperability is currently in demand.
- Major remaining uncertainty: whether proposition identity can be made stable enough to
  content-address without freezing the graph's ability to revise claims — the tension
  between immutable citation and living belief.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model`
- Required analyses: compare nanopub serialisation against alternatives; determine what
  proposition-identity stability export would require.
- Priority level: medium — not blocking, but a one-way door once consumers exist.

## Related

- Topic notes: `topic:structured-scientific-knowledge`

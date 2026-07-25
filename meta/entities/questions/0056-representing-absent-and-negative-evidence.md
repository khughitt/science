---
id: question:0056-representing-absent-and-negative-evidence
kind: question
title: Representing absent and negative evidence
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- question:0012-agent-tool-kg-operations
created: '2026-07-25'
updated: '2026-07-25'
---
# Representing absent and negative evidence

## Summary

Most real research produces non-results: a search that returned nothing relevant, an
analysis that failed to separate the arms, a literature sweep that found no counterpart
study. The graph has rich machinery for representing evidence that *exists* and very
little for representing a search that *found nothing*.

This matters because absence of evidence and evidence of absence are different, and
collapsing them is one of the more consequential errors an aggregation system can make.

Surfaced during the 2026-07-25 `explore-ideas` triage rather than by a lens agent: the blind pass could not reach it, because the lens agents had no view of what the project already asks.

## Why It Matters

- Without representing the negative result, the same fruitless search gets repeated —
  the failure is invisible to the graph, so nothing records that it was already tried.
- Aggregation is affected directly: a proposition with three supporting lines and an
  unrecorded failed replication is not the same as one with three supporting lines, but
  the graph cannot tell them apart.
- Risk if unanswered: the graph is a record of what was found, and therefore inherits
  precisely the publication-selection bias the project's motivating literature is about.

## Current Evidence

- `question:0012` cites Si et al. on distinguishing absence of evidence from evidence of
  absence using Bayes factors, and `question:0004` records omission semantics as a
  source-behavior concern — omitted true values and asserted false values are different
  failure modes. The vocabulary exists; the representation does not.
- `question:0001` contains a concrete instance: it records that no many-analysts genomics
  study is known to exist, and asks that this be logged as a gap the project's evaluation
  cannot currently close. That negative finding lives in prose, not as graph state.

## Thoughts

- Best current interpretation: a searched-and-found-nothing record needs the same
  provenance a positive evidence line carries — what was searched, how, when, with what
  coverage — because a weak search and a thorough one license very different inferences.
- Major remaining uncertainty: whether this is a new entity kind, a status on an existing
  evidence line, or a property of the search operation itself.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
- Required analyses: enumerate the non-result types the project has already produced and
  buried in prose.
- Priority level: medium-high — cheap to represent, and it compounds silently.

## Related

- Topic notes: `topic:analytic-flexibility-and-replication`

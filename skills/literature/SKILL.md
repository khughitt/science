---
name: literature
description: Use when finding, evaluating, or citing scientific literature. Routes to the literature leaves.
provenance: internal
---

# Literature Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when sourcing, appraising, or citing literature is in scope — before drafting claims
that depend on sources.

## Scope boundary

Covers literature search tools, source evaluation, and citation conformance. Excludes proposition
schema/graph reasoning (see `../epistemics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `literature-evaluation.md` | assessing/recording source provenance and publication status | no external sources |
| `citation-discipline.md` | conforming a citation/source-pointer to the project contract | no citations at stake |
| `sources/openalex.md` | querying OpenAlex for ranked, provenance-tagged results | non-OpenAlex sourcing |
| `sources/pubmed.md` | querying PubMed/NCBI E-utilities for ranked results | non-PubMed sourcing |

## Decision / compose order

Search leaves feed evaluation; citation-discipline applies whenever a claim cites a source.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../epistemics/SKILL.md`, `../research-package/SKILL.md`

## Success test

A sourcing/citation task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.

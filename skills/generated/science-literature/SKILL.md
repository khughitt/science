---
name: science-literature
description: "Use when finding, evaluating, or citing scientific literature. Routes to the literature leaves."
---

# Literature Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when sourcing, appraising, or citing literature is in scope — before drafting claims
that depend on sources.

## Scope boundary

Covers literature search tools, source evaluation, and citation conformance. Excludes proposition
schema/graph reasoning (see `science-epistemics` skill).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `references/literature-evaluation.md` | assessing/recording source provenance and publication status | no external sources |
| `references/citation-discipline.md` | conforming a citation/source-pointer to the project contract | no citations at stake |
| `references/sources/openalex.md` | querying OpenAlex for ranked, provenance-tagged results | non-OpenAlex sourcing |
| `references/sources/pubmed.md` | querying PubMed/NCBI E-utilities for ranked results | non-PubMed sourcing |

## Decision / compose order

Search leaves feed evaluation; citation-discipline applies whenever a claim cites a source.

## Parent & neighbors

- Parent index: `science-command-preamble` skill's `references/methodology-index.md`
- Neighboring routers: `science-epistemics` skill, `science-research-package` skill

## Success test

A sourcing/citation task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `science-command-preamble` skill's `references/methodology-index.md` — the skill index.

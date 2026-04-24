---
id: "topic:structured-scientific-knowledge"
type: "topic"
title: "Structured Representations of Scientific Knowledge: Nanopublications and Research Knowledge Graphs"
status: "active"
ontology_terms: []
source_refs: []
related:
  - "topic:analytic-flexibility-and-replication"
created: "2026-04-24"
updated: "2026-04-24"
---

# Structured Representations of Scientific Knowledge: Nanopublications and Research Knowledge Graphs

## Summary

A decade-and-a-half of work on nanopublications and research knowledge graphs has attempted to make scientific claims machine-readable, provenance-aware, and composable, rather than treating the PDF article as the minimum unit of knowledge.
The two main lines — nanopublications [@Groth2010; @Kuhn2016; @Kuhn2018; @Bucur2023] and research knowledge graphs such as the Open Research Knowledge Graph [@Auer2018] — propose compatible but distinct granularities.
This topic is load-bearing for `science-meta` because the tool's data model (propositions, evidence edges, source references) is a close structural relative of these approaches; design choices here should be informed by what the prior art has tried, what has worked, and — importantly — what has stalled.

## Key Concepts

**Nanopublication.**
An atomic unit of scientific knowledge consisting of three named graphs: an *assertion* (the claim itself, expressed as RDF triples), *provenance* (how the assertion came to be — methods, citations, experimental context), and *publication info* (authorship, timestamps, trust signals) [@Groth2010].
The design move is to make each claim independently addressable, reusable, and citable, rather than locking it inside a published paper.

**Trusty URIs.**
Content-addressable identifiers for digital artifacts: the hash of the artifact's canonical form is embedded in its URI, so any modification yields a different URI [@Kuhn2016].
This gives nanopublications immutability and verifiability without requiring a central authority.

**Research Knowledge Graph (RKG).**
A graph whose nodes are scientific entities (papers, research contributions, methods, datasets, problems) and whose edges are structured relations (uses, compares-with, addresses, evaluated-on).
The Open Research Knowledge Graph [@Auer2018] is the most visible effort: per-paper "research contribution" records filled in against domain templates, with a compare view that aligns contributions from many papers on shared dimensions.

**Granularity trade-off.**
Nanopublications pick *per-claim* granularity: each assertion is independently addressable.
RKGs typically pick *per-paper* or *per-contribution* granularity: the paper remains the unit, and its internal structure is surfaced.
Both can coexist, and both have been implemented against the same linked-data stack (RDF, SPARQL, named graphs).

## Current State of Knowledge

**The nanopublication line.**
Groth, Gibson, and Velterop [@Groth2010] introduced the model in 2010 with an explicit motivation: bioinformatics data at scale was outstripping the article-as-unit abstraction.
Kuhn, Dumontier, and colleagues then built infrastructure — decentralised servers for publishing, trusty-URI-based immutability, and query endpoints [@Kuhn2016].
By 2018 a growing corpus had accumulated, on the order of millions of nanopublications sourced largely from biomedical data integration and workflow outputs [@Kuhn2018].
More recently, Bucur et al. [@Bucur2023] report a field study in which formalisation papers were structured as nanopublications during editorial review, with assertions, provenance, and the reviews themselves represented in the graph.

**The research knowledge graph line.**
Auer et al. [@Auer2018] set out the Open Research Knowledge Graph as infrastructure for machine-actionable representation of scholarly content, with templates filled per discipline and a comparison interface that tabulates research contributions across many papers.
The stated goal is to replace or augment the narrative literature survey with a structured, queryable resource.

**Points of agreement across both lines.**

- The published paper is insufficient as the granular unit of scientific knowledge; structured sub-paper representations are needed.
- Machine-readability, provenance, and trust markers should be first-class, not after-the-fact annotations.
- Linked-data technology is the reasonable substrate.

**Points of tension.**

- **Granularity.** Nanopubs bet on per-claim atomicity; RKGs bet on per-paper structured summaries. Neither has dominated.
- **Who writes the structure.** Nanopubs can be machine-generated from data pipelines; RKGs typically depend on human curation of each contribution. Adoption costs differ sharply.
- **Adoption itself.** Despite more than a decade of effort, neither approach has become routine infrastructure for working scientists in most fields. The corpora are substantial in biomedicine and computer science but thin elsewhere.

## Controversies & Open Questions

**Why adoption has stalled.**
This is the sharpest open question.
Plausible contributing factors (none individually decisive in the literature) include: authoring friction; no incentive to produce structured claims while the paper remains the career-progression unit; absence of a killer cross-claim query or analysis that structured data enables and prose search does not; and a chicken-and-egg problem in which sparse data makes early structured tools underperform prose search.
Any new project proposing structured scientific knowledge should treat adoption as the hard problem, not the data model.

**Whether structured claims capture the right thing.**
A sceptical view holds that much of what matters in a scientific argument — assumptions, hedges, context — does not survive atomisation into triples.
Nanopublications address part of this through provenance graphs, but the expressiveness ceiling of RDF assertion-plus-provenance may be real.

**Relationship to large language models.**
LLMs can now produce structured summaries of papers on demand.
Whether this makes curated RKGs redundant, or instead makes them more valuable as training and validation substrate, is actively debated and not settled.

## Relevance to This Project

The `science-meta` project's data model is a close structural relative of both lines.
Propositions with `claim_layer`, `identification_strength`, and `measurement_model` fields resemble nanopublication assertions with provenance; support / dispute evidence edges play the role that nanopublication provenance graphs play for individual assertions.
The `source_refs` and `related` fields encode a linked-data backbone even though the current serialisation is TriG plus YAML frontmatter rather than pure RDF assertion-provenance-pubinfo triples.

Four specific implications worth flagging as design decisions to reach — not as settled answers.

1. **Granularity.** `science-meta` currently sits between the two camps: hypotheses contain propositions, and propositions carry evidence.
   Whether propositions should be addressable as nanopublication-style units on export is an open design question directly informed by this topic.

2. **Identity and immutability.** Nanopublications rely on trusty URIs so that a claim cited by downstream work cannot silently change [@Kuhn2016].
   `science-meta` has no immutability guarantee on proposition identity today; this becomes load-bearing the moment projects begin to share or fork, which is one of the project's stated long-range bets.
   A trusty-URI-like scheme on export is a concrete option.

3. **Export format.** If `science-meta` eventually supports exporting a project's evidence graph for external reuse (another stated long-range bet), nanopublication-compatible serialisation is a serious candidate and should be evaluated against alternatives before an ad-hoc format is chosen.

4. **Adoption realism.** Both prior lines have invested more than a decade and attracted substantial funding without achieving mainstream adoption.
   The project should plan as if the same headwinds apply, and should articulate what it would do differently to avoid the same outcome — or explicitly accept that it, too, is betting on a future ecosystem that may not materialise.
   This adoption question deserves its own entry under `doc/questions/`.

## Key References

- Groth, Gibson & Velterop (2010) — the original nanopublication model [@Groth2010]
- Kuhn et al. (2016) — decentralised publishing, trusty URIs, nanopub infrastructure [@Kuhn2016]
- Kuhn et al. (2018) — growth and biomedical use of the nanopub corpus [@Kuhn2018]
- Bucur et al. (2023) — field study of nanopub-native semantic publishing and review [@Bucur2023]
- Auer et al. (2018) — Towards a Knowledge Graph for Science, the ORKG initiative [@Auer2018]

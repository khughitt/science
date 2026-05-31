---
id: paper:Vasilevsky2022
type: paper
title: "Mondo: Unifying diseases for the world, by the world"
status: active
ontology_terms:
  - "MONDO"
  - "disease ontology"
datasets: []
source_refs:
  - "cite:Vasilevsky2022"
related:
  - "question:q09-bioinformatics-generalizability"
created: "2026-05-31"
updated: "2026-05-31"
---

# Mondo: Unifying diseases for the world, by the world

- **Authors:** Nicole A. Vasilevsky, Nicolas A. Matentzoglu, Sabrina Toro, Joseph E. Flack IV, Harshad Hegde, Deepak R. Unni, Gioconda F. Alyea, Joanna S. Amberger, Larry Babb, James P. Balhoff, and others
- **Year:** 2022
- **Journal:** medRxiv preprint
- **DOI/URL:** https://doi.org/10.1101/2022.04.13.22273750
- **BibTeX key:** Vasilevsky2022
- **Source:** PDF

## Key Contribution

Vasilevsky et al. present Mondo as an open, community-driven disease ontology intended to unify disease concepts across heterogeneous biomedical terminologies [@Vasilevsky2022].
The core claim is that disease-name reconciliation needs stable, provenance-preserving identifiers and semantically typed mappings rather than ad hoc cross-references or text matching [@Vasilevsky2022].
For Science, the paper is useful because it frames MONDO terms as exactly the kind of graph-shaped reference collection that `bio.reference_graph` is meant to model.

## Methods

Mondo integrates disease knowledge from multiple source terminologies and ontologies, including resources such as OMIM, Orphanet, NCIt, ICD-related sources, Disease Ontology, MedGen, and others [@Vasilevsky2022].
The ontology represents disease concepts with permanent MONDO identifiers, multiple parentage, scoped synonyms, definitions, cross references, and mapping provenance [@Vasilevsky2022].
The authors describe a mapping workflow that combines labels, synonyms, existing cross-references, graph structure, source-specific priors, computational equivalence prediction, expert curation, and community review [@Vasilevsky2022].
The version summarized in the paper was released as `v2022-03-01`; the paper reports 22,157 disease concepts derived from approximately 90,000 source concepts across 17 disease resources [@Vasilevsky2022].

## Key Findings

Mondo addresses a real interoperability problem: disease resources overlap only partially and often disagree in classification, naming, synonym scope, and cross-reference semantics [@Vasilevsky2022].
The paper emphasizes that source cross-references can be non-exact, stale, ambiguous, or wrong, so a normalized ontology must preserve mapping semantics and provenance rather than treating all xrefs as identity [@Vasilevsky2022].
Mondo contains multiple disease categories, including rare diseases, infectious diseases, cancers, and Mendelian diseases; the paper reports 10,443 rare-disease concepts, 1,240 infectious-disease concepts, 4,298 cancer/neoplasm concepts, and 11,380 Mendelian-disease concepts in the analyzed release [@Vasilevsky2022].
The ontology supports multiple parentage, scoped synonyms (`exact`, `broad`, `narrow`, `related`), and database cross-references with more precise semantics for equivalent or related mappings [@Vasilevsky2022].
The resource is updated on a monthly cycle and is maintained through a broad contributor community, which makes lifecycle metadata and release pinning important for any downstream commons ingestion [@Vasilevsky2022].

## Relevance

This paper supports using MONDO as the first real `bio.reference_graph` commons recipe.
It exercises exactly the lifecycle and identity boundaries that RG1/RG2 were designed to handle: stable `MONDO:` keys, graph edges, term labels, synonyms, typed cross-resource mappings, provenance, and obsolete/replacement behavior.
It also cautions against treating xrefs as canonical identity.
In the Science model, `MONDO:` term equality should remain the member identity boundary, while relations such as equivalence, related mappings, synonym provenance, and broader/narrower relationships should remain explicit edges or metadata.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| MONDO identifier | `member_key` in `bio.reference_graph` | Stable addressable key for a disease term. |
| Disease concept / class | `bio.reference_graph` node | Node row should carry label, status, replacement, and usage/provenance hooks. |
| `is_a` / multiple parentage | `edge_resource` row | Direct graph edges should remain queryable, not collapsed into node metadata. |
| xref / equivalent / related mapping | Explicit edge, not identity rewrite | Matches the RG design decision that compatibility relations do not remint identity. |
| Scoped synonym | Node descriptor or edge-like annotation | Useful for later search/resolution, but not required for RG1/RG2 payload identity. |
| Monthly releases | Pinned commons artifact | Recipe should fetch archived/tagged release artifacts and lock hashes. |

## Limitations

The paper is a medRxiv preprint and should be treated as a source description rather than peer-reviewed evidence for clinical use [@Vasilevsky2022].
The summary statistics come from the `v2022-03-01` MONDO release, so a Science recipe should not hard-code those counts for current releases.
The paper motivates mapping semantics but does not provide a Science-ready extraction contract for which OWL/OBO predicates should become `node_index_resource` columns versus normalized `edge_resource` rows.
The recipe plan should therefore explicitly choose which predicates are in RG1 scope and which are deferred.

## Model / Tool Availability

Mondo releases are available from the Monarch Initiative GitHub repository and through ontology browsers such as OLS [@Vasilevsky2022].
The paper reports that ontology files and releases are available on GitHub, and the current Science recipe should use a pinned release tag or immutable release asset rather than a mutable latest URL [@Vasilevsky2022].
BioOntologies is worth evaluating as a possible extraction dependency because its README describes a Python interface that retrieves ontologies from OWL/OBO/Bioregistry prefixes and converts them to OBO Graph JSON using ROBOT (https://github.com/biopragmatics/bioontologies).
That could save custom parsing work, but the implementation plan should verify whether it preserves the MONDO lifecycle and mapping predicates needed for `nodes.csv` and `edges.csv`.

## Follow-up

Draft the MONDO commons ingestion plan around a pinned release, not the paper's 2022 counts.
Prototype two extraction paths before committing the recipe design: direct MONDO release artifact parsing versus BioOntologies-mediated OBO Graph JSON conversion.
The acceptance test should include at least one active disease term, one obsolete/deprecated term with replacement metadata, one `is_a` edge, and one xref/equivalence-like edge that remains a relation rather than an identity rewrite.

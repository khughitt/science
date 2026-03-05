---
name: knowledge-graph
description: Reference guide for the science knowledge graph ontology, entity types, CURIE conventions, and provenance patterns. This skill is loaded by create-graph and update-graph as background context.
---

# Knowledge Graph Ontology Reference

## Entity Types

When constructing graph entities from prose, use these types:

| Entity | CLI Command | When to use |
|--------|-------------|-------------|
| Concept | `science-tool graph add concept "<label>" --type <type> --ontology-id <CURIE>` | Any topic, gene, disease, drug, pathway, process |
| Paper | `science-tool graph add paper --doi "<DOI>"` | Published papers referenced in prose |
| Claim | `science-tool graph add claim "<text>" --source <source_ref> --confidence <0-1>` | Factual assertions from literature |
| Hypothesis | `science-tool graph add hypothesis <ID> --text "<text>" --source <source_ref>` | Falsifiable claims under investigation |
| Edge | `science-tool graph add edge <subj> <pred> <obj> --graph <layer>` | Any relation between entities |

## CURIE Conventions

Prefix format: `prefix:localname`. Supported prefixes:

| Prefix | Namespace | Example |
|--------|-----------|---------|
| `sci:` | Science vocab | `sci:relatedTo`, `sci:Concept`, `sci:Claim` |
| `scic:` | Causal vocab | `scic:causes`, `scic:Variable` |
| `biolink:` | Biolink Model | `biolink:Gene`, `biolink:Disease` |
| `schema:` | schema.org | `schema:author`, `schema:identifier` |
| `skos:` | SKOS | `skos:broader`, `skos:narrower` |
| `prov:` | PROV-O | `prov:wasDerivedFrom` |
| `rdf:` | RDF | `rdf:type` |

Project entity references: `paper:<slug>`, `concept:<slug>`, `claim:<slug>`, `hypothesis:<id>`, `dataset:<slug>`.

## Ontology Alignment Guidelines

1. **Always provide ontology IDs** for well-known entities (genes, diseases, drugs, pathways).
2. **Use Biolink types** for biomedical entities: `biolink:Gene`, `biolink:Disease`, `biolink:Drug`, `biolink:Pathway`, `biolink:BiologicalProcess`, `biolink:Phenotype`.
3. **Use `sci:Concept`** as the base type for all concepts; add domain-specific types as additional `rdf:type` values.
4. **Slugify labels** for entity URIs: lowercase, replace non-alphanumeric with `_`.

## Provenance Rules

- Every `sci:Claim` **must** have a `--source` pointing to a paper or document reference.
- Every `sci:Hypothesis` **must** have a `--source`.
- Use `--confidence` (0.0-1.0) for claims where strength of evidence varies.
- Epistemic status values: `established`, `hypothesized`, `disputed`, `retracted`.

## Relation Selection Guide

| Relationship | Predicate | Graph Layer |
|-------------|-----------|-------------|
| General association | `sci:relatedTo` | `graph/knowledge` |
| Hierarchy | `skos:broader` / `skos:narrower` | `graph/knowledge` |
| Evidence supports claim | `sci:supports` | `graph/knowledge` |
| Evidence refutes claim | `sci:refutes` | `graph/knowledge` |
| Paper addresses question | `sci:addresses` | `graph/knowledge` |
| Variable measured by dataset | `sci:measuredBy` | `graph/datasets` |
| Causal effect | `scic:causes` | `graph/causal` |
| Confounding | `scic:confounds` | `graph/causal` |

## Prose Annotation Format

**Frontmatter** -- add to research documents:

```yaml
---
ontology_terms:
  - "biolink:Gene"
  - "NCBIGene:672"      # BRCA1
  - "MONDO:0016419"     # breast cancer
---
```

**Inline** -- annotate key terms on first mention:

```markdown
BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with
breast cancer [`MONDO:0016419`].
```

Rules:
- Annotate each entity on **first mention only**.
- Use the format: `term [`CURIE`]`.
- CURIEs should match ontology IDs used in `graph add concept --ontology-id`.

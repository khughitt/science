---
name: knowledge-graph
description: Reference guide for the science knowledge graph ontology, entity types, CURIE conventions, and provenance patterns. This skill is loaded by create-graph and update-graph as background context.
---

# Knowledge Graph Ontology Reference

## Entity Types

| Entity | CLI Command | When to use |
|--------|-------------|-------------|
| Concept | `graph add concept "<label>" --type <type> [flags]` | Any topic, gene, disease, drug, pathway, process, model, method, tool |
| Paper | `graph add paper --doi "<DOI>"` | Published papers referenced in prose |
| Claim | `graph add claim "<text>" --source <ref> --confidence <0-1>` | Factual assertions from literature |
| Hypothesis | `graph add hypothesis <ID> --text "<text>" --source <ref>` | Falsifiable claims under investigation |
| Question | `graph add question <ID> --text "<text>" --source <ref>` | Open research questions |
| Edge | `graph add edge <subj> <pred> <obj> --graph <layer>` | Any relation between entities |

## Entity Properties

Concepts support rich metadata beyond label and type:

```bash
graph add concept "DNABERT-2 117M" \
  --type biolink:GeneticModel \
  --ontology-id "DNABERT2" \
  --note "12 layers; max context 2048 nt" \
  --definition "BPE-tokenized DNA foundation model" \
  --status selected-primary \
  --source paper:doi_10_1234_test \
  --property hasArchitecture "BERT encoder" \
  --property hasParameters "117M" \
  --property hasEmbeddingDim "768" \
  --property hasTokenization "BPE"
```

| Flag | Predicate | Notes |
|------|-----------|-------|
| `--note TEXT` | `skos:note` | Freeform annotation |
| `--definition TEXT` | `skos:definition` | Formal definition |
| `--status STATUS` | `sci:projectStatus` | `selected-primary`, `deferred`, `active`, `candidate`, `speculative` |
| `--source REF` | `prov:wasDerivedFrom` | Provenance link (in provenance layer) |
| `--property KEY VALUE` | `sci:KEY` or resolved CURIE | Repeatable; bare key defaults to `sci:` namespace |

## CURIE Conventions

Prefix format: `prefix:localname`. Supported prefixes:

| Prefix | Namespace | Example |
|--------|-----------|---------|
| `sci:` | Science vocab | `sci:evaluates`, `sci:Concept`, `sci:Claim` |
| `scic:` | Causal vocab | `scic:causes`, `scic:Variable` |
| `cito:` | Citation Typing Ontology | `cito:supports`, `cito:disputes`, `cito:discusses` |
| `dcterms:` | Dublin Core Terms | `dcterms:identifier`, `dcterms:description` |
| `biolink:` | Biolink Model | `biolink:Gene`, `biolink:Disease` |
| `schema:` | schema.org | `schema:author`, `schema:identifier` |
| `skos:` | SKOS | `skos:broader`, `skos:narrower`, `skos:related` |
| `prov:` | PROV-O | `prov:wasDerivedFrom` |
| `rdf:` | RDF | `rdf:type` |

Project entity references: `paper:<slug>`, `concept:<slug>`, `claim:<slug>`, `hypothesis:<id>`, `question:<id>`, `dataset:<slug>`.

## Ontology Alignment Guidelines

1. **Always provide ontology IDs** for well-known entities (genes, diseases, drugs, pathways).
2. **Use Biolink types** for biomedical entities: `biolink:Gene`, `biolink:Disease`, `biolink:Drug`, `biolink:Pathway`, `biolink:BiologicalProcess`, `biolink:Phenotype`.
3. **Use `sci:Concept`** as the base type for all concepts; add domain-specific types as additional `rdf:type` values.
4. **Slugify labels** for entity URIs: lowercase, replace non-alphanumeric with `_`.

## Provenance Rules

- Every `sci:Claim` **must** have a `--source` pointing to a paper or document reference.
- Every `sci:Hypothesis` **must** have a `--source`.
- Every `sci:Question` **must** have a `--source`.
- Use `--confidence` (0.0-1.0) for claims where strength of evidence varies.
- Epistemic status values: `established`, `hypothesized`, `disputed`, `retracted`.
- Concepts **should** have `--source` when the source document is known.

## Preferred Predicates

Use standard predicates over custom ones where they exist:

| Use case | Preferred | Avoid |
|----------|-----------|-------|
| General association | `skos:related` | `sci:relatedTo` |
| Evidence supports claim | `cito:supports` | `sci:supports` |
| Evidence disputes claim | `cito:disputes` | `sci:refutes` |
| Paper discusses topic | `cito:discusses` | `sci:addresses` |
| Extends prior work | `cito:extends` | -- |
| Uses method from work | `cito:usesMethodIn` | -- |
| Cites as data source | `cito:citesAsDataSource` | -- |

Keep `sci:` for domain-specific predicates: `sci:evaluates`, `sci:hasModality`, `sci:detectedBy`, `sci:storedIn`, `sci:measuredBy`, `sci:projectStatus`, `sci:confidence`, `sci:epistemicStatus`, `sci:maturity`.

Run `graph predicates` to see all supported predicates with descriptions.

## Relation Selection Guide

| Relationship | Predicate | Graph Layer |
|-------------|-----------|-------------|
| General association | `skos:related` | `graph/knowledge` |
| Hierarchy | `skos:broader` / `skos:narrower` | `graph/knowledge` |
| Evidence supports claim | `cito:supports` | `graph/knowledge` |
| Evidence disputes claim | `cito:disputes` | `graph/knowledge` |
| Paper discusses topic | `cito:discusses` | `graph/knowledge` |
| Extends prior work | `cito:extends` | `graph/knowledge` |
| Benchmark evaluates model | `sci:evaluates` | `graph/knowledge` |
| Model operates on modality | `sci:hasModality` | `graph/knowledge` |
| Feature detected by method | `sci:detectedBy` | `graph/knowledge` |
| Data stored in repository | `sci:storedIn` | `graph/knowledge` |
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

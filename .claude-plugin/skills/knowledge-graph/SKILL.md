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

## Predicate Reference

Run `graph predicates` to see all supported predicates. Only use predicates from this list.

| Relationship | Predicate | Graph Layer | Deprecated alternative |
|-------------|-----------|-------------|----------------------|
| General association | `skos:related` | `graph/knowledge` | ~~`sci:relatedTo`~~ |
| Hierarchy | `skos:broader` / `skos:narrower` | `graph/knowledge` | |
| Evidence supports claim | `cito:supports` | `graph/knowledge` | ~~`sci:supports`~~ |
| Evidence disputes claim | `cito:disputes` | `graph/knowledge` | ~~`sci:refutes`~~ |
| Paper discusses topic | `cito:discusses` | `graph/knowledge` | ~~`sci:addresses`~~ |
| Extends prior work | `cito:extends` | `graph/knowledge` | |
| Uses method from work | `cito:usesMethodIn` | `graph/knowledge` | |
| Cites as data source | `cito:citesAsDataSource` | `graph/knowledge` | |
| Benchmark evaluates model | `sci:evaluates` | `graph/knowledge` | |
| Model operates on modality | `sci:hasModality` | `graph/knowledge` | |
| Feature detected by method | `sci:detectedBy` | `graph/knowledge` | |
| Data stored in repository | `sci:storedIn` | `graph/knowledge` | |
| Variable measured by dataset | `sci:measuredBy` | `graph/datasets` | |
| Causal effect | `scic:causes` | `graph/causal` | |
| Confounding | `scic:confounds` | `graph/causal` | |

Keep `sci:` for domain-specific predicates: `sci:evaluates`, `sci:hasModality`, `sci:detectedBy`, `sci:storedIn`, `sci:measuredBy`, `sci:projectStatus`, `sci:confidence`, `sci:epistemicStatus`, `sci:maturity`.

If a relationship doesn't fit any predicate above, use `skos:related` and add a `--note`. Do **not** invent new predicates.

## URI Slugification Rules

All entity URIs are auto-slugified: **lowercase, non-alphanumeric characters → underscore, leading/trailing underscores stripped**.

This applies to:
- Entity creation: `graph add concept "Nucleotide Transformer v2"` → URI `concept/nucleotide_transformer_v2`
- Bare terms in edges: `graph add edge "My Concept" "skos:related" "Other Thing"` → `my_concept` and `other_thing`
- DOI slugs: `10.1234/arXiv.2301.01234` → `10_1234_arxiv_2301_01234` (note: `arXiv` → `arxiv`)

**Important for agents:** After `graph add concept`, check the echoed URI to know the exact slug for later `graph add edge` calls. CURIE-prefixed terms (`concept:my_slug`, `paper:doi_...`) and full URLs are NOT slugified — only bare terms without a `:` or `http` prefix.

Examples:
| Input | Resolved URI suffix |
|-------|-------------------|
| `"Nucleotide Transformer v2"` | `nucleotide_transformer_v2` |
| `"arXiv:2301.01234"` | Error — `arXiv` is not a known CURIE prefix. Use `concept/arxiv_2301_01234` or a DOI. |
| `concept/nucleotide_transformer_v2` | `concept/nucleotide_transformer_v2` (passed through) |
| `"DNABERT-2"` | `dnabert_2` |

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

## Inquiry Entities

Inquiries are named subgraphs that represent self-contained investigations. They connect data/observations to hypotheses through variables, assumptions, and transformations.

### Inquiry-Specific Entity Types

| Entity | CLI Command | When to use |
|--------|-------------|-------------|
| Inquiry | `inquiry init "<slug>" --label --target` | Named subgraph container for an investigation |
| Variable | `graph add concept "<label>" --type sci:Variable` | A quantity in the model (observed, latent, or computed) |
| Transformation | (via `/science:plan-pipeline`) | A computational/analytical step in the pipeline |
| Assumption | (via `add_assumption` or specify-model) | An explicit modeling assumption with provenance |
| Unknown | `graph add concept "<label>" --type sci:Unknown` | Placeholder for unidentified factors (sketch only) |
| ValidationCheck | `graph add concept "<label>" --type sci:ValidationCheck` | A criterion for verifying a step or result |

### Inquiry CLI Commands

```
inquiry init <SLUG> --label <LABEL> --target <HYPOTHESIS_OR_QUESTION>
inquiry add-node <SLUG> <ENTITY> [--role <BoundaryIn|BoundaryOut>]
inquiry add-edge <SLUG> <SUBJECT> <PREDICATE> <OBJECT>
inquiry add-assumption <SLUG> <LABEL> --source <REF>
inquiry add-transformation <SLUG> <LABEL> [--tool <TOOL>]
inquiry list [--format table|json]
inquiry show <SLUG> [--format table|json]
inquiry validate <SLUG> [--format table|json]
```

Note: `add-node` without `--role` adds an interior node (no boundary classification).

### Inquiry-Specific Predicates

| Predicate | Description | Layer |
|-----------|-------------|-------|
| `sci:target` | Links inquiry to its hypothesis/question | inquiry |
| `sci:boundaryRole` | Assigns BoundaryIn/BoundaryOut within an inquiry | inquiry |
| `sci:inquiryStatus` | Inquiry lifecycle status (sketch/specified/planned/in-progress/complete) | inquiry |
| `sci:feedsInto` | Data/information flow (A provides input to B) | inquiry |
| `sci:assumes` | Dependency on an assumption | inquiry |
| `sci:produces` | Transformation yields output | inquiry |
| `sci:validatedBy` | Step validated by criterion | inquiry |

### Boundary Roles

- `sci:BoundaryIn` — Given/observable input (datasets, measurements, known facts)
- `sci:BoundaryOut` — Produced output (test results, predictions, artifacts)
- Interior nodes have no boundary role — they are latent variables, transformations, assumptions

A node can appear in multiple inquiries with different boundary roles. The boundary classification is per-inquiry, not intrinsic to the node.

### Parameter Provenance Predicates

For annotating parameters with their evidence source (AnnotatedParam pattern):

| Predicate | Description |
|-----------|-------------|
| `sci:paramValue` | The parameter value |
| `sci:paramSource` | Source type: `literature`, `empirical`, `design_decision`, `convention`, `data_derived` |
| `sci:paramRef` | BibTeX key or doc path reference |
| `sci:paramNote` | Rationale note |

### Inquiry Validation Checks

`inquiry validate <SLUG>` runs these checks:

| Check | Description |
|-------|-------------|
| `boundary_reachability` | Every BoundaryOut reachable from some BoundaryIn via directed edges |
| `no_cycles` | No cycles in `sci:feedsInto`/`sci:produces` edges |
| `unknown_resolution` | `sci:Unknown` nodes allowed in sketch, must be resolved in specified+ |
| `target_exists` | Target hypothesis/question exists in the knowledge graph |
| `orphaned_interior` | Interior nodes should have both incoming and outgoing flow edges (warn) |
| `provenance_completeness` | Specified+ inquiries: all assumptions must have `prov:wasDerivedFrom` |

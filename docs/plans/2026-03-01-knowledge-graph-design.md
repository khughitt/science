# Science Agent Knowledge Graph — Design & Specification

*Date: 2026-03-01*
*Status: In Progress (Phase 3 execution refinements added 2026-03-03; Slice B enrichment merged 2026-03-05; status audit 2026-03-07)*

## 1. Overview

> This document is a companion to the main planning document [docs/plan.md](../plan.md), providing detailed specifications for the Phase 3 knowledge graph layer.

A knowledge graph layer for the science agent that serves as a **shared knowledge representation between the human researcher and the AI agent**. The graph encodes entities, semantic relations, causal structure, provenance, and links to available datasets — supporting research exploration, hypothesis development, and progression toward formal causal/Bayesian models.

### Design principles

- **Domain-agnostic core** — abstract schema (entities, relations, claims, evidence, provenance) applicable to any science. Domain-specific ontologies (Biolink Model, Gene Ontology, MeSH, etc.) layer on top as optional plugins.
- **Distilled snapshots** — pre-processed, cached, offline-browseable subgraphs of public KGs. No live API queries at research time.
- **RDF canonical + property graph runtime** — TriG as the source of truth for semantic interoperability; NetworkX as the runtime for graph algorithms, DAG validation, and PPL export.
- **Layered graphs with provenance** — separate named graphs for established knowledge, causal hypotheses, provenance metadata, and dataset links. Every assertion carries epistemic status.
- **CLI-first visualization** — Graphviz DOT as intermediate; kitty protocol for inline terminal rendering; SVG fallback.
- **Causal DAG progression** — the graph evolves from semantic knowledge → causal structure → exportable probabilistic models (PyMC, Pyro, ChiRHo).

### Non-goals (for now)

- Live API queries to external KGs at research time
- Web-based visualization UI
- OWL reasoning / inference engine
- Multi-user / collaborative editing

### Phase 3 scope guardrails (2026-03-03 refinement)

- **Execution order is fixed:** Slice A -> Slice B -> Slice C -> Slice D.
- **Acceptance is command-evidence based:** each slice must have reproducible command output and tests, not only qualitative notes.
- **CLI stability is in scope:** graph query commands must support both `--format table` and `--format json`.
- **Diff correctness is in scope:** staleness checks must use hybrid detection (mtime + content hash), not mtime-only heuristics.
- **Explicitly out of scope for Phase 3:** DAG export runtime, automated ontology matching, SHACL execution engine.

### Representative graph-based use cases (biomedical focus)

| Use case | Input | Graph operation | Output |
|---|---|---|---|
| Literature landscape map | Disease/topic prompt (e.g., "triple-negative breast cancer resistance") | Import distilled OpenAlex + paper/citation nodes, run neighborhood and centrality queries | Ranked concepts, key papers, and candidate subtopics to prioritize |
| Hypothesis traceability | A new hypothesis in `doc/07-hypotheses.md` | Materialize `sci:Hypothesis`, link to claims/evidence/provenance | Machine-checkable trail from hypothesis text to supporting/refuting sources |
| Data readiness check | Candidate variables for a causal question | Traverse `:graph/datasets` links (`sci:measuredBy`) and coverage metadata | "Can we estimate this?" report with observed/unobserved variables and missing data gaps |
| Causal model bootstrapping | Draft causal edges from researcher | Validate DAG + confounding structure, export to PyMC/Pyro | Executable starter model with explicit assumptions and provenance |
| Contradiction detection | New claim added from a paper summary | Query for existing `sci:refutes`/status conflicts on same subject-predicate-object | Flagged conflicts for review before model updates |

## 2. Architecture

### 2.1 Two-artifact structure

| Artifact | Type | Purpose |
|---|---|---|
| `science` plugin | Markdown/bash Claude Code plugin | Commands, skills, templates — tells the agent *what* to do |
| `science-tool` package | Python library (uv-managed) | Computational layer — graph storage, query, causal export, distillation, visualization |

The plugin invokes `science-tool` via CLI commands (`uv run science-tool ...`) or the agent imports it in generated code.

### 2.2 Named graph layers

All project knowledge lives in a single TriG file (`knowledge/graph.trig`) partitioned into named graphs:

```
┌───────────────────────────────────────────────────────┐
│  :graph/knowledge                                     │
│  Established facts from literature and public KGs.    │
│  Nodes: concepts, papers, people, organizations.      │
│  Edges: semantic relations (relatedTo, broader, etc.) │
├───────────────────────────────────────────────────────┤
│  :graph/causal                                        │
│  Researcher's hypothesized causal structure.           │
│  Nodes: causal variables (subclass of concepts).      │
│  Edges: causes, confounds, mediates, instruments.     │
├───────────────────────────────────────────────────────┤
│  :graph/provenance                                    │
│  Metadata about assertions in the other graphs.       │
│  Reified statements with PROV-O properties,           │
│  confidence scores, epistemic status.                 │
├───────────────────────────────────────────────────────┤
│  :graph/datasets                                      │
│  Available data sources linked to variables.           │
│  Which datasets measure which concepts/variables,     │
│  column mappings, quality notes.                      │
└───────────────────────────────────────────────────────┘
```

### 2.3 Runtime stack

```
                 ┌──────────────┐
  Agent / Human  │  CLI / REPL  │
                 └──────┬───────┘
                        │
              ┌─────────▼──────────┐
              │   science-tool API   │
              │  (Python library)  │
              └────┬─────────┬─────┘
                   │         │
         ┌─────────▼───┐ ┌──▼──────────┐
         │   rdflib     │ │  NetworkX   │
         │   Dataset    │ │  DiGraph    │
         │  (canonical) │ │ (runtime)   │
         └──────┬───────┘ └──────┬──────┘
                │                │
         ┌──────▼───────┐ ┌─────▼───────┐
         │  .trig files │ │  Graphviz   │
         │  (on disk)   │ │  pgmpy/PPL  │
         └──────────────┘ └─────────────┘
```

- **rdflib.Dataset** — loads/saves TriG, executes SPARQL queries, manages named graphs
- **NetworkX.DiGraph** — projected from RDF for graph algorithms (PageRank, centrality, community detection) and causal DAG operations (acyclicity validation, topological sort, d-separation)
- **Graphviz** — DOT rendering for both KG subgraph views and causal DAG diagrams
- **pgmpy** — `FunctionalBayesianNetwork` as the bridge from DAG to PPL code generation

### 2.4 Representation pipeline (text → graph → model)

The project uses a strict representation ladder so information can move from notes to executable models without losing provenance:

1. Natural language artifacts (`doc/`, `papers/summaries/`, `specs/`).
2. Structured assertions (`sci:Claim`, `sci:Evidence`, `sci:Hypothesis`) in TriG named graphs.
3. Causal structure (`scic:Variable`, `scic:causes`, `scic:confounds`) in `:graph/causal`.
4. Executable model artifacts (PyMC/Pyro code) generated from the DAG.

Every downward step must preserve links upward via IDs and provenance metadata.

### 2.5 Graph revision metadata contract

`graph diff` and `update-graph` depend on a stable revision stamp written after successful graph updates.
The stamp lives in `:graph/provenance` and is updated only when write + validation succeeds.

```turtle
GRAPH :graph/provenance {
    :graph_revision a prov:Entity ;
        schema:name "graph-revision" ;
        schema:dateModified "2026-03-03T00:00:00Z"^^xsd:dateTime ;
        schema:sha256 "6f9d...<graph-content-hash>..." ;
        prov:wasDerivedFrom :input_manifest_2026_03_03 .
}
```

`graph diff` compares project prose/data inputs against this revision using:
- file mtime checks (fast path), and
- file content hashes for changed or suspicious files (correctness path).

Hybrid mode is the Phase 3 default.

## 3. Ontology Specification

### 3.1 Prefix declarations

```turtle
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
@prefix schema:  <https://schema.org/> .
@prefix sci:     <http://example.org/science/vocab/> .
@prefix scic:    <http://example.org/science/vocab/causal/> .
@prefix biolink: <https://w3id.org/biolink/vocab/> .
@prefix cito:    <http://purl.org/spar/cito/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
```

> **Note:** The `sci:` and `scic:` namespaces are placeholders. Permanent URIs should be minted when the vocabulary stabilizes (e.g. via w3id.org or a project domain).

### 3.2 Tier 1 — Core ontology (`sci:`)

Domain-agnostic classes for representing scientific knowledge. Reuses standard vocabularies where applicable.

#### Classes

| Class | Superclass(es) | Description |
|---|---|---|
| `sci:Concept` | `skos:Concept` | Any topic, idea, or entity in the knowledge space |
| `sci:Paper` | `schema:ScholarlyArticle`, `prov:Entity` | A scientific publication |
| `sci:Dataset` | `schema:Dataset`, `prov:Entity` | An available data source |
| `sci:Hypothesis` | `prov:Entity` | A falsifiable claim under investigation |
| `sci:Question` | `prov:Entity` | An open research question |
| `sci:Claim` | `prov:Entity` | An asserted fact (with provenance) |
| `sci:Evidence` | `prov:Entity` | Something that supports or refutes a claim |
| `sci:ResearchAgent` | `prov:Agent` | Human researcher or AI agent |

#### Properties

| Predicate | Domain | Range | Superproperties | Description |
|---|---|---|---|---|
| `sci:relatedTo` | `sci:Concept` | `sci:Concept` | `skos:related` | General semantic association (**deprecated:** prefer `skos:related`) |
| `sci:supports` | `sci:Evidence` | `sci:Claim` | — | Evidence supports a claim (**deprecated:** prefer `cito:supports`) |
| `sci:refutes` | `sci:Evidence` | `sci:Claim` | — | Evidence contradicts a claim (**deprecated:** prefer `cito:disputes`) |
| `sci:addresses` | `sci:Paper` | `sci:Question` | — | Paper addresses a research question (**deprecated:** prefer `cito:discusses`) |
| `sci:projectStatus` | `prov:Entity` | `xsd:string` | — | Project relevance: `"selected-primary"`, `"deferred"`, `"active"`, `"candidate"`, `"speculative"` |
| `sci:maturity` | `sci:Question` | `xsd:string` | — | Question maturity: `"open"`, `"partially-resolved"`, `"resolved"` |
| `sci:measuredBy` | `sci:Concept` | `sci:Dataset` | — | Concept/variable has data in this dataset |
| `sci:proposedBy` | `sci:Hypothesis` | `sci:ResearchAgent` | `prov:wasAttributedTo` | Who proposed this hypothesis |
| `sci:epistemicStatus` | `prov:Entity` | `xsd:string` | — | `"established"`, `"hypothesized"`, `"disputed"`, `"retracted"` |
| `sci:confidence` | `prov:Entity` | `xsd:decimal` | — | Confidence score [0.0, 1.0] |

Standard reused properties (not redefined, just used directly):

| Predicate | Source | Usage |
|---|---|---|
| `skos:broader` / `skos:narrower` | SKOS | Concept hierarchy |
| `skos:related` | SKOS | Associative relation between concepts |
| `skos:prefLabel` | SKOS | Preferred human-readable label |
| `schema:author` | schema.org | Paper → Person |
| `schema:citation` | schema.org | Paper → Paper |
| `schema:datePublished` | schema.org | Paper → xsd:date |
| `schema:name` | schema.org | Display name for any entity |
| `schema:identifier` | schema.org | DOI, PMID, etc. |
| `prov:wasDerivedFrom` | PROV-O | Entity derivation chain |
| `prov:wasAttributedTo` | PROV-O | Entity → Agent attribution |
| `prov:wasGeneratedBy` | PROV-O | Entity → Activity |
| `prov:generatedAtTime` | PROV-O | Timestamp |

#### CiTO predicates (preferred for citation/evidence relations)

| Predicate | Source | Usage |
|---|---|---|
| `cito:supports` | CiTO | Evidence supports a claim/hypothesis (replaces `sci:supports`) |
| `cito:disputes` | CiTO | Evidence disputes a claim/hypothesis (replaces `sci:refutes`) |
| `cito:discusses` | CiTO | Paper discusses a topic (replaces `sci:addresses`) |
| `cito:extends` | CiTO | Work extends prior research |
| `cito:usesMethodIn` | CiTO | Uses method from another work |
| `cito:citesAsDataSource` | CiTO | Cites as data source |
| `dcterms:identifier` | Dublin Core | External identifier |

### 3.3 Tier 2 — Causal vocabulary (`scic:`)

Minimal vocabulary for causal graphical models. No standard RDF/OWL causal ontology exists; this is a custom vocabulary informed by SCM (Structural Causal Model) conventions.
The dedicated `scic:` prefix keeps causal terms concise and valid in Turtle/SPARQL examples.

#### Classes

| Class | Superclass | Description |
|---|---|---|
| `scic:Variable` | `sci:Concept` | A variable in a causal model. Participates in both knowledge and causal layers. |
| `scic:CausalRelation` | `rdf:Statement` | Reified causal edge with metadata (functional form, effect size) |

#### Causal role individuals

| Individual | Type | Description |
|---|---|---|
| `scic:Treatment` | `scic:Role` | Treatment / intervention variable |
| `scic:Outcome` | `scic:Role` | Outcome variable |
| `scic:Confounder` | `scic:Role` | Common cause of treatment and outcome |
| `scic:Mediator` | `scic:Role` | Variable on the causal path between treatment and outcome |
| `scic:Instrument` | `scic:Role` | Instrumental variable |

#### Properties

| Predicate | Domain | Range | Description |
|---|---|---|---|
| `scic:causes` | `scic:Variable` | `scic:Variable` | Direct causal effect (X → Y) |
| `scic:confounds` | `scic:Variable` | `scic:Variable` | Shared latent common cause (symmetric; rendered as bidirected arc) |
| `scic:mediates` | `scic:Variable` | `scic:Variable` | M mediates X → Y |
| `scic:instruments` | `scic:Variable` | `scic:Variable` | Z is an instrument for the X → Y effect |
| `scic:role` | `scic:Variable` | `scic:Role` | Role in the causal model |
| `scic:distributionFamily` | `scic:Variable` | `xsd:string` | `"Normal"`, `"Bernoulli"`, `"Beta"`, etc. |
| `scic:isObserved` | `scic:Variable` | `xsd:boolean` | Whether data is available for this variable |
| `scic:functionalForm` | `scic:CausalRelation` | `xsd:string` | `"linear"`, `"logistic"`, `"nonlinear"`, etc. |
| `scic:effectSize` | `scic:CausalRelation` | `xsd:decimal` | Estimated or hypothesized effect magnitude |

### 3.4 Tier 3 — Domain plugins

Domain ontologies are imported by adding prefix declarations and typing nodes with domain-specific classes. No changes to the core schema are needed.

**Example: Biolink Model (biomedical)**

```turtle
@prefix biolink: <https://w3id.org/biolink/vocab/> .

:gene_BRCA1 a sci:Concept, biolink:Gene ;
    biolink:category biolink:Gene ;
    skos:prefLabel "BRCA1" ;
    schema:identifier "NCBIGene:672" .

:disease_breast_cancer a sci:Concept, biolink:Disease ;
    biolink:category biolink:Disease ;
    skos:prefLabel "Breast cancer" ;
    schema:identifier "MONDO:0016419" .
```

Domain plugins that can be layered in:

| Plugin | Prefix | Covers |
|---|---|---|
| Biolink Model | `biolink:` | Genes, diseases, drugs, phenotypes, pathways |
| CiTO | `cito:` | Citation typing (supports, disputes, discusses, extends) — **now in core** |
| Dublin Core Terms | `dcterms:` | Metadata terms (identifier, description) — **now in core** |
| Gene Ontology | `go:` | Biological processes, molecular functions, cellular components |
| MeSH | `mesh:` | Medical Subject Headings (PubMed indexing) |
| Disease Ontology | `doid:` | Standardized disease classification |
| ChEBI | `chebi:` | Chemical entities of biological interest |
| schema.org | `schema:` | Papers, persons, organizations (already in core) |

### 3.5 Provenance pattern

Provenance metadata about individual assertions is stored via reified statements in `:graph/provenance`. (RDF-star would be preferred but is not yet supported by rdflib as of v7.6.0.)

```turtle
GRAPH :graph/knowledge {
    :aspirin sci:relatedTo :headache .
}

GRAPH :graph/provenance {
    :claim_001 a sci:Claim, prov:Entity ;
        rdf:subject :aspirin ;
        rdf:predicate sci:relatedTo ;
        rdf:object :headache ;
        prov:wasDerivedFrom :paper_doi_10_1234 ;
        prov:wasAttributedTo :agent_claude ;
        prov:generatedAtTime "2026-03-01T00:00:00Z"^^xsd:dateTime ;
        sci:confidence "0.85"^^xsd:decimal ;
        sci:epistemicStatus "established" .
}
```

When rdflib gains RDF-star / RDF 1.2 support, this can be migrated to the more compact annotation syntax:

```turtle
# Future RDF-star equivalent (not yet supported)
:aspirin sci:relatedTo :headache
    {| prov:wasDerivedFrom :paper_doi_10_1234 ;
       sci:confidence "0.85"^^xsd:decimal |} .
```

## 4. KG Distillation Pipeline

### 4.1 Goal

Pre-generate small, browseable snapshots of public knowledge graphs as Turtle files. These are static data that research projects import into their local graph.

**Target per snapshot:** 200–2,000 nodes, 1,000–20,000 triples, <3 MB Turtle. Loads in rdflib in <1 second.

### 4.2 Sources

#### OpenAlex Science Map

| Property | Value |
|---|---|
| Source | OpenAlex API (`api.openalex.org`) |
| Levels | 4 domains → 26 fields → 252 subfields → ~4,516 topics |
| Strategy | Direct API fetch of hierarchy; no graph algorithms needed |
| Compact snapshot | ~282 nodes (domains + fields + subfields), ~600 triples |
| Full snapshot | ~4,800 nodes (+ topics), ~10,000 triples |
| Node typing | `sci:Concept`, `skos:Concept` |
| Relations | `skos:broader`, `skos:narrower`, `skos:related` |

Each node carries: `skos:prefLabel`, `skos:broader` (parent), work count as `schema:size` or custom property.

#### PrimeKG (biomedical domain plugin)

| Property | Value |
|---|---|
| Source | Harvard Dataverse CSV (~129K nodes, ~4M edges, 10 node types, 30 edge types) |
| Strategy | Type-stratified PageRank |
| Process | 1) Load CSV → NetworkX; 2) Per node type: compute PageRank on induced subgraph; 3) Select top-N per type; 4) Retain inter-selected edges |
| Budget | ~170 nodes (~40 diseases, ~40 drugs, ~30 genes, ~15 pathways, ~15 anatomy, ~15 phenotypes, ~15 bio processes) |
| Output | ~170 nodes, ~2,000–5,000 triples |
| Node typing | `sci:Concept` + `biolink:` category |
| Alternative | Disease-centric ego graph: pick focal disease, extract 1-hop neighborhood, prune by relation type |

#### DBpedia (general knowledge plugin) *(deferred)*

> **Deferred** to a later phase. OpenAlex and PrimeKG are the Phase 3 priority sources. The design below is retained for future reference.

| Property | Value |
|---|---|
| Source | Public SPARQL endpoint (`dbpedia.org/sparql`) |
| Strategy | SPARQL CONSTRUCT with category path filter |
| Output | ~1,000–3,000 triples per category extract |
| Alternative | Download DBpedia ontology only (~768 classes, ~3K properties, ~2–5 MB TTL) for schema-level understanding |

Example query:

```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX dbo: <http://dbpedia.org/ontology/>

CONSTRUCT { ?s ?p ?o }
WHERE {
    ?s dct:subject/skos:broader* <http://dbpedia.org/resource/Category:Sciences> .
    ?s ?p ?o .
    FILTER(?p IN (rdfs:label, dbo:abstract, rdf:type, dbo:field, dbo:knownFor))
} LIMIT 3000
```

### 4.3 Pipeline structure

```
science-tool/
├── src/science_tool/distill/
│   ├── __init__.py
│   ├── openalex.py      # Fetch hierarchy via API → Turtle
│   └── primekg.py       # Download CSV → PageRank → distilled Turtle
└── data/snapshots/
    ├── openalex-science-map.ttl
    ├── openalex-topics.ttl       # (optional, larger)
    ├── primekg-core.ttl
    └── manifest.ttl              # PROV-O metadata: date, source, version, counts
```

CLI:

```bash
uv run science-tool distill openalex --level subfields    # compact
uv run science-tool distill openalex --level topics        # full
uv run science-tool distill primekg --budget 170
```

### 4.4 Manifest

```turtle
# data/snapshots/manifest.ttl
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix :       <http://example.org/science/snapshots/> .

:openalex-science-map a prov:Entity, schema:Dataset ;
    schema:name "OpenAlex Science Map (subfield level)" ;
    prov:generatedAtTime "2026-03-01T00:00:00Z"^^xsd:dateTime ;
    prov:wasDerivedFrom <https://api.openalex.org/subfields> ;
    schema:version "openalex:2026-03-01" ;
    schema:size "282 nodes, 600 triples" ;
    schema:sha256 "9aa9...<snapshot-hash>..." .

:primekg-core a prov:Entity, schema:Dataset ;
    schema:name "PrimeKG Core (type-stratified PageRank)" ;
    prov:generatedAtTime "2026-03-01T00:00:00Z"^^xsd:dateTime ;
    prov:wasDerivedFrom <https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IXA7BM> ;
    schema:version "primekg:doi-10.7910-DVN-IXA7BM" ;
    schema:size "170 nodes, 3000 triples" ;
    schema:sha256 "3370...<snapshot-hash>..." .
```

## 5. Causal Model → PPL Export

### 5.1 Pipeline

```
  :graph/causal        NetworkX        pgmpy FBN       Generated
  (RDF, TriG)    →     DiGraph    →    (optional)   →  .py code
                    (validate DAG)    (simulate/fit)   (PyMC/Pyro)
```

### 5.2 Step 1: RDF → NetworkX DAG

SPARQL extracts causal structure from `:graph/causal`:

```sparql
SELECT ?cause ?effect ?form ?dist ?obs
WHERE {
    GRAPH <:graph/causal> {
        ?cause scic:causes ?effect .
    }
    OPTIONAL { GRAPH <:graph/causal> { ?cause scic:distributionFamily ?dist } }
    OPTIONAL { GRAPH <:graph/causal> { ?cause scic:isObserved ?obs } }
    OPTIONAL { GRAPH <:graph/causal> {
        ?rel a scic:CausalRelation ;
            rdf:subject ?cause ; rdf:object ?effect ;
            scic:functionalForm ?form .
    }}
}
```

Confounding edges (`scic:confounds`) are extracted separately and stored as edge attributes on a parallel `confounding_edges` list (they are not DAG edges; they represent bidirected arcs / latent common causes).

Validation:

```python
assert nx.is_directed_acyclic_graph(G), f"Cycle detected: {nx.find_cycle(G)}"
```

### 5.3 Step 2: NetworkX → pgmpy (optional bridge)

`pgmpy.models.FunctionalBayesianNetwork` wraps the DAG with Pyro-distribution CPDs. This enables:

- `fbn.simulate(n_samples=1000)` — forward sampling
- `fbn.simulate(n_samples=1000, do={"X": 0.5})` — interventional sampling
- `fbn.fit(data, estimator="SVI", num_steps=100)` — parameter learning

This step is optional — the researcher may prefer to go directly to generated PyMC/Pyro code.

### 5.4 Step 3: Code generation

**PyMC export** — generates a `.py` file with a `pm.Model` context:

```python
# Generated from: knowledge/graph.trig, layer: :graph/causal
# Date: 2026-03-01
# Variables: 3, Causal edges: 2, Confounders: 1

import pymc as pm
import numpy as np

def build_model(data: dict[str, np.ndarray]) -> pm.Model:
    with pm.Model() as model:
        # --- Priors (edit these) ---
        beta_X_Y = pm.Normal("beta_X_Y", mu=0, sigma=1)
        sigma_Y = pm.HalfNormal("sigma_Y", sigma=1)

        # --- Latent confounders ---
        U_XY = pm.Normal("U_XY", mu=0, sigma=1, shape=len(data["Y"]))

        # --- Root variables ---
        X = pm.Normal("X", mu=U_XY, sigma=1, observed=data.get("X"))

        # --- Downstream variables ---
        Y = pm.Normal("Y",
            mu=beta_X_Y * X + U_XY,
            sigma=sigma_Y,
            observed=data.get("Y"))

    return model
```

**Pyro/ChiRHo export** — generates a model function:

```python
# Generated from: knowledge/graph.trig, layer: :graph/causal
import pyro
import pyro.distributions as dist
import torch

def causal_model(data: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    U_XY = pyro.sample("U_XY", dist.Normal(0, 1))
    X = pyro.sample("X", dist.Normal(U_XY, 1), obs=data.get("X"))
    Y = pyro.sample("Y", dist.Normal(X + U_XY, 1), obs=data.get("Y"))
    return {"U_XY": U_XY, "X": X, "Y": Y}
```

### 5.5 Confounder expansion

`scic:confounds` edges (symmetric) are expanded during export:

```
X confounds Y  →  latent U_XY;  U_XY → X,  U_XY → Y
```

In Graphviz rendering: dashed bidirected arc (standard ADMG convention).
In PPL export: explicit latent variable.

### 5.6 Visualization conventions

| Element | Graphviz rendering |
|---|---|
| Observed variable | Solid ellipse |
| Latent variable | Dashed ellipse |
| Direct causal edge | Solid arrow |
| Confounding (bidirected) | Dashed double-headed arc, blue |
| Treatment variable | Bold border |
| Outcome variable | Double border |

Rendering pipeline:

```python
# 1. Build DOT
dot_source = dag_to_dot(G, confounding_edges)

# 2. Render
if "KITTY_PID" in os.environ:
    # Render to PNG, display inline via kitty graphics protocol
    subprocess.run(["kitten", "icat", png_path])
else:
    # Fallback: save SVG, print path
    print(f"DAG saved to {svg_path}")
```

### 5.7 Identification and estimation guardrails

Before DAG export is treated as "model-ready", run these checks:

- **Acyclicity:** `nx.is_directed_acyclic_graph(G)` must pass.
- **Role completeness:** at least one `scic:Treatment` and one `scic:Outcome` must exist for effect-estimation workflows.
- **Observedness coverage:** all adjustment variables needed for the target estimand are either observed or explicitly marked missing with a warning.
- **Confounder handling:** each `scic:confounds` edge is expanded into an explicit latent variable in generated code.
- **Provenance completeness:** every causal edge has a linked source claim or is marked as hypothesis-only.

If any check fails, `science-tool dag export` should fail early and emit actionable errors.

## 6. Package Specification

### 6.1 `science-tool` Python package

```
science-tool/
├── pyproject.toml
├── src/
│   └── science_tool/
│       ├── __init__.py
│       ├── schema/
│       │   ├── __init__.py
│       │   ├── core.py              # URI constants, prefix map, namespace manager
│       │   ├── causal.py            # Causal vocabulary URI constants
│       │   └── ontology.ttl         # OWL definition of sci: vocabulary
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── store.py             # rdflib Dataset wrapper (load/save TriG, manage named graphs)
│       │   ├── query.py             # SPARQL query helpers (parameterized queries, result → dict)
│       │   └── project.py           # NetworkX projection (RDF named graph → DiGraph with attributes)
│       ├── causal/
│       │   ├── __init__.py
│       │   ├── dag.py               # DAG construction, validation, d-separation, adjustment sets
│       │   ├── export_pymc.py       # DAG → PyMC .py code generation
│       │   ├── export_pyro.py       # DAG → Pyro/ChiRHo .py code generation
│       │   └── export_pgmpy.py      # DAG → pgmpy FunctionalBayesianNetwork
│       ├── doi.py                   # DOI metadata lookup (CrossRef/OpenAlex)
│       ├── ontology/
│       │   ├── __init__.py
│       │   └── cache.py             # Download and cache controlled vocabularies
│       ├── distill/
│       │   ├── __init__.py
│       │   ├── openalex.py          # OpenAlex API → Turtle snapshot
│       │   └── primekg.py           # PrimeKG CSV → distilled Turtle snapshot
│       ├── viz/
│       │   ├── __init__.py
│       │   ├── dot.py               # Graph/DAG → Graphviz DOT source
│       │   ├── render.py            # DOT → SVG/PNG, kitty icat detection and rendering
│       │   └── cli.py               # Rich-based CLI graph summaries (tables, stats)
│       └── cli.py                   # Click CLI entry point
├── data/
│   └── snapshots/                   # Pre-generated distilled KG snapshots (shipped with package)
│       ├── openalex-science-map.ttl
│       ├── primekg-core.ttl
│       └── manifest.ttl
└── tests/
    ├── test_store.py
    ├── test_causal.py
    ├── test_distill.py
    └── fixtures/                    # Small test graphs in TriG format
```

### 6.2 Dependencies

```toml
[project]
name = "science-tool"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "rdflib>=7.0",        # RDF graph store, SPARQL, TriG serialization
    "networkx>=3.2",      # Graph algorithms, DAG validation, projection
    "graphviz",           # Python bindings for Graphviz DOT rendering
    "rich",               # CLI output (tables, colors, progress)
    "click",              # CLI framework
    "httpx",              # HTTP client (OpenAlex API, CrossRef API, ontology downloads)
    "polars",             # CSV loading (PrimeKG distillation)
]

[project.optional-dependencies]
causal = [
    "pgmpy",              # FunctionalBayesianNetwork bridge to PPL
    "pymc>=5",            # PyMC export target
]
ml = [
    "pykeen",             # KG embedding models
    "torch-geometric",    # GNN on graphs
]

[project.scripts]
science-tool = "science_tool.cli:main"
```

### 6.3 CLI commands

```bash
# --- Phase 3: Graph Foundation ---

# Graph management
science-tool graph init                                    # Initialize knowledge/graph.trig
science-tool graph stats                                   # Counts per named graph, entity types

# Entity authoring
science-tool graph add concept "BRCA1" --type biolink:Gene --ontology-id NCBIGene:672
science-tool graph add concept "DNABERT-2" --note "12 layers" --property hasArchitecture "BERT" --status selected-primary --source paper:doi_10_1234
science-tool graph add paper --doi "10.1038/s41586-023-06957-x"
science-tool graph add claim "X causes Y" --source paper:doi_10_1234 --confidence 0.8
science-tool graph add hypothesis H3 --text "..." --source paper:ref --status active
science-tool graph add question Q01 --text "..." --source paper:ref --maturity open --related-hypothesis hypothesis/h3
science-tool graph add edge <subject> <predicate> <object> --graph <layer>

# Use-case-driven queries (see agent query presets below)
science-tool graph neighborhood "BRCA1" --hops 2           # Entities and edges near a concept
science-tool graph claims --about "BRCA1"                  # Claims mentioning an entity
science-tool graph evidence H3                             # Evidence for/against a hypothesis
science-tool graph coverage                                # Variables with/without dataset links
science-tool graph gaps --center "BRCA1" --hops 2          # Low-coverage areas in neighborhood
science-tool graph uncertainty --top 10                    # Highest-uncertainty claims/entities

# Predicate reference
science-tool graph predicates                              # List all supported predicates with descriptions

# Change detection and validation
science-tool graph diff --mode hybrid                      # Hybrid mtime + content-hash staleness checks
science-tool graph stamp-revision                          # Update revision metadata
science-tool graph validate                                # Structural checks on graph.trig

# Prose scanning
science-tool graph scan-prose doc/                         # Scan markdown for ontology annotations

# Visualization
science-tool graph viz --center "BRCA1" --hops 2           # Render subgraph neighborhood
science-tool graph viz --layer knowledge --limit 200       # Render named graph subset

# DOI lookup
science-tool doi lookup 10.1038/s41586-023-06957-x         # Fetch metadata for validation

# Ontology caching (groundwork for future entity matching)
science-tool ontology cache biolink                        # Download and cache vocabulary
science-tool ontology list                                 # List cached vocabularies

# Distillation
science-tool distill openalex --level subfields
science-tool distill openalex --level topics
science-tool distill primekg --budget 170

# Snapshot import
science-tool graph import openalex-science-map             # Load snapshot into :graph/knowledge
science-tool graph import primekg-core

# --- Phase 4: Causal DAG ---

science-tool dag add-variable "X" --observed --distribution Normal
science-tool dag add-edge "X" "Y" --type causes --form linear
science-tool dag add-edge "X" "Y" --type confounds
science-tool dag show                                      # Render DAG inline (kitty) or save SVG
science-tool dag validate                                  # Check acyclicity, identification
science-tool dag export --format pymc --output code/models/model.py
science-tool dag export --format pyro --output code/models/model.py
science-tool dag export --format pgmpy
```

**Implementation status snapshot (2026-03-05)**

- Implemented now:
  - `graph init`
  - `graph stats` (with `--format table|json`)
  - `graph add concept` (with `--type`, `--ontology-id`, `--note`, `--definition`, `--property KEY VALUE`, `--status`, `--source`)
  - `graph add paper|claim|hypothesis|question|edge`
  - `graph add hypothesis` (with `--status`)
  - `graph add question` (with `--text`, `--source`, `--maturity`, `--status`, `--related-hypothesis`)
  - `graph predicates` (lists all supported predicates with descriptions and layers)
  - `graph validate` (with `--format table|json`, non-zero exit on failing checks)
  - `graph diff --mode hybrid|mtime|hash` (with `--format table|json`)
  - `graph stamp-revision` (update revision metadata without adding entities)
  - `graph scan-prose <dir>` (scan markdown for frontmatter and inline CURIE annotations)
  - `graph viz` (DOT output to stdout/file)
  - `graph import <snapshot.ttl>` (merge Turtle snapshot into `:graph/knowledge` with provenance)
  - `doi lookup` (Crossref-backed metadata fetch)
  - all query presets: `graph neighborhood`, `graph claims`, `graph evidence`, `graph coverage`, `graph gaps`, `graph uncertainty`
  - `distill openalex --level subfields|topics` (OpenAlex API → SKOS hierarchy → Turtle)
  - `distill pykeen <DatasetName> --budget N` (PyKEEN dataset → PageRank selection → Turtle)
  - manifest.ttl generation with PROV-O metadata alongside snapshots
  - strict CURIE prefix validation (unknown prefixes fail with explicit errors; supports `sci:`, `scic:`, `schema:`, `prov:`, `skos:`, `rdf:`, `biolink:`, `cito:`, `dcterms:`)
  - claim identity hardening (source-aware default ID generation + explicit `graph add claim --id`)
  - CiTO/dcterms namespace support for standard citation typing predicates
  - entity property flags: `--note` (skos:note), `--definition` (skos:definition), `--property` (repeatable key-value), `--status` (sci:projectStatus), `--source` (prov:wasDerivedFrom)
  - project status validation via `click.Choice` on concept, hypothesis, and question commands
  - agent-facing skills: `knowledge-graph` (ontology reference), `create-graph` (prose → graph workflow), `update-graph` (incremental update workflow)
- Implemented validation checks (v1):
  - `parseable_trig`
  - `provenance_completeness` for `sci:Claim` and `sci:Hypothesis`
  - `causal_acyclicity` over `scic:causes`

**Agent-facing query presets**

The CLI prioritizes use-case-driven query presets over raw SPARQL. The agent is the primary consumer of these commands during research workflows. All query commands support `--format table` (Rich-formatted, default) and `--format json` (machine-readable for agent consumption).

| Research question | CLI command | Returns |
|---|---|---|
| "What do we know about X?" | `graph neighborhood <X>` | Entities and edges within N hops, with provenance summary |
| "What claims exist about X?" | `graph claims --about <X>` | Claims mentioning entity, with epistemic status and sources |
| "What evidence supports H3?" | `graph evidence H3` | Evidence linked to hypothesis, grouped by supports/refutes |
| "Which variables lack data?" | `graph coverage` | Variables with/without `sci:measuredBy` links, observedness status |
| "What gaps exist near X?" | `graph gaps --center <X>` | Low-connectivity entities, missing provenance, low-confidence claims |
| "Where is uncertainty highest?" | `graph uncertainty` | Entities/claims ranked by epistemic uncertainty (disputed, hypothesized, low confidence) |
| "What changed since last update?" | `graph diff` | Project files that are stale by hybrid check (mtime + content hash) against latest graph revision stamp |

### 6.4 Delivery slices and acceptance criteria

| Slice | Maps to plan phase | Scope | Status | Acceptance criteria |
|---|---|---|---|---|
| Slice A: Graph foundation | 3a | TriG store, named graphs, query presets, viz, DOI lookup, CLI | DONE | Agent can init graph, add entities, run use-case queries in table/json, visualize neighborhoods, and fail fast on invalid writes |
| Slice B: Graph authoring | 3b | KG skill, `create-graph`, `update-graph`, prose annotations | DONE | Agent can construct graph from prose with provenance and ontology alignment, then detect/update stale areas via `graph diff --mode hybrid` |
| Slice C: KG bootstrapping | 3c | OpenAlex + PrimeKG distillers, `graph import`, biomedical starter profile | PARTIAL | Snapshots load in <1s, import works, manifest records source/version/checksum, biomedical examples are usable |
| Slice D: Validation + exemplar | 3d | Graph validation checks, exemplar project run-through | PARTIAL | One biomedical project passes all graph checks end-to-end and includes archived command evidence (`graph stats/validate/diff`, import logs, `validate.sh`) |
| Slice E: Causal core | 4 | DAG authoring, validation, visualization, confounder representation | PARTIAL | A DAG with confounding is validated and visualized with expected conventions |
| Slice F: Model export | 4 | PyMC/Pyro export with provenance metadata and guardrails | NOT STARTED | Exported model code executes for synthetic dataset, retains graph provenance |
| Slice G: Data linking | 4 | Dataset-variable mapping in `:graph/datasets`, observedness checks | PARTIAL | At least one exemplar maps real columns to variables with validation |

This slicing is intentionally additive. Later slices must consume earlier artifacts, not fork parallel formats.

Current progress note (2026-03-04): Slice A is complete. All query presets, snapshot distillation (OpenAlex API + PyKEEN datasets with PageRank budget selection), graph import with provenance, and manifest generation are implemented with tests. 38 tests passing, ruff clean, pyright clean.

Current progress note (2026-03-04): Slice B (initial) is complete. Three plugin skills (knowledge-graph, create-graph, update-graph) implemented in .claude-plugin/skills/. Prose scanner (`graph scan-prose`) and revision stamper (`graph stamp-revision`) CLI commands added with tests. 38 tests passing, ruff clean, pyright clean.

Current progress note (2026-03-05): Slice B (enrichment) is complete. Added CiTO and dcterms namespace prefixes. Concept `add` enriched with `--note`, `--definition`, `--property KEY VALUE` (repeatable), `--status`, `--source`. Hypothesis `add` enriched with `--status`. New `add question` command with `--maturity`, `--status`, `--related-hypothesis`. New `graph predicates` command listing all supported predicates. Status values validated via `click.Choice`. Skills and command docs updated with CiTO preferred predicates, entity properties, question workflow, and deferred entities guidance. 44 tests passing, ruff clean, pyright clean. Removed unused pyyaml dependency.

Current progress note (2026-03-07): Status audit performed across all slices. Summary:

- **Slice A:** DONE. All graph commands, query presets, viz, DOI lookup implemented with tests.
- **Slice B:** DONE. Skills, prose scanner, revision stamper, CiTO/dcterms enrichment, entity properties all implemented.
- **Slice C:** PARTIAL. OpenAlex distiller, generic PyKEEN distiller, `graph import` with provenance all implemented. Missing: no PrimeKG-specific distiller (generic PyKEEN covers this use case), no biomedical starter profile, no pre-generated snapshots shipped in `data/snapshots/`.
- **Slice D:** PARTIAL. `graph validate` (4 checks) and `validate.sh` (525 lines) both implemented. Missing: end-to-end biomedical exemplar project with archived command evidence.
- **Slice E:** PARTIAL (~60%). Causal namespace, `scic:causes`/`scic:confounds` predicates, DAG acyclicity validation (via `graph validate`), and causal layer visualization (via `graph viz`) all work. Missing: dedicated `dag` CLI subcommand group (`dag add-variable`, `dag add-edge`, `dag show`, `dag validate`), specialized confounder visualization.
- **Slice F:** NOT STARTED. No `export_pymc.py`, `export_pyro.py`, `export_pgmpy.py`, or `dag export` commands.
- **Slice G:** PARTIAL (~70%). `sci:measuredBy` predicate, `scic:isObserved` property, `query_coverage()`, and `graph coverage` CLI all work. Missing: exemplar mapping real dataset columns to variables, column-level validation.

Also missing from the design spec (§6.1):
- `schema/` module (exists but empty — no `core.py`, `causal.py`, `ontology.ttl`)
- `viz/` module (no dedicated module — DOT generation lives in `store.py`)
- `ontology cache` / `ontology list` commands

**Next priorities:**
- **Slice C remainder:** Biomedical starter profile, pre-generated snapshots.
- **Slice D remainder:** End-to-end exemplar project with archived command evidence.
- **Slice E remainder:** Dedicated `dag` CLI subcommand group, confounder visualization.
- **Slice F:** PyMC/Pyro/pgmpy export (full slice).
- **Slice G remainder:** Exemplar dataset-variable mapping with validation.

### 6.5 Phase 3 verification gate (must pass before "done")

```bash
uv run --frozen pytest science-tool/tests -q
uv run --frozen ruff check science-tool
uv run --frozen pyright science-tool
uv run science-tool graph validate
./validate.sh
```

Required evidence artifact for the exemplar:
- `graph stats` output
- `graph diff --mode hybrid` output
- snapshot import logs
- `graph validate` output
- `validate.sh` output

## 7. Research Project File Structure

When a project is scaffolded via `/science:create-project`, the `knowledge/` directory has this structure:

```
my-research-project/
├── knowledge/
│   ├── graph.trig              # Main project graph (all named graphs, single source of truth)
│   ├── snapshots/              # Imported public KG distillations
│   │   ├── openalex-science-map.ttl
│   │   └── primekg-core.ttl    # (if biomedical project)
│   └── exports/
│       └── causal_dag.dot      # Latest DOT export
├── code/
│   └── models/
│       └── causal_model.py     # Generated PyMC/Pyro code (edited by researcher)
└── ...
```

Initial `graph.trig`:

```turtle
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix sci:    <http://example.org/science/vocab/> .
@prefix scic:   <http://example.org/science/vocab/causal/> .
@prefix :       <http://example.org/project/my-project/> .

GRAPH :graph/knowledge {
    # Established facts — grows as research progresses
}

GRAPH :graph/causal {
    # Causal DAG — variables and causal/confounding edges
}

GRAPH :graph/provenance {
    # Provenance metadata for assertions in other graphs
}

GRAPH :graph/datasets {
    # Links between variables/concepts and available datasets
}
```

### 7.1 Prose Annotation Conventions

Research documents gain two annotation layers that serve as the bridge between narrative prose and the knowledge graph. These are added by the agent during `/science:create-graph` and `/science:update-graph`.

**Frontmatter metadata** — an `ontology_terms:` list of CURIEs relevant to the document:

```yaml
---
ontology_terms:
  - "biolink:Gene"
  - "NCBIGene:672"      # BRCA1
  - "MONDO:0016419"     # breast cancer
---
```

**Inline annotations** — key terms annotated with ontology CURIEs on first mention:

```markdown
BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with
breast cancer [`MONDO:0016419`].
```

These annotations enable:
- Traceability from prose claims to graph entities.
- Future automated entity matching against cached ontology vocabularies.
- Quick visual identification of ontology-linked terms during review.

The `skills/models/knowledge-graph.md` skill guides the agent on which entity types warrant ontology alignment and how to format CURIEs.

## 8. Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Canonical format | TriG | Named graph support in Turtle superset; rdflib full support |
| Runtime store | rdflib.Dataset | Pure Python, no server, SPARQL, named graphs; sufficient for project-scale (<100K triples) |
| Graph algorithms | NetworkX DiGraph | Mature, extensive algorithms, direct interop with PyG and pgmpy |
| Provenance | Reified statements + PROV-O | RDF-star not yet available in rdflib (pending RDF 1.2); reification is verbose but fully supported |
| Causal vocabulary | Custom `scic:` | No standard RDF causal ontology exists; minimal vocabulary mapping to SCM concepts |
| PPL bridge | pgmpy FunctionalBayesianNetwork | Uses Pyro distributions natively; supports do-operator and SVI; closest to a standard intermediate format |
| PPL export | Code generation (.py files) | Generated code is a starting point, not a black box; researcher edits priors, functional forms, plates |
| Visualization | Graphviz DOT → kitty icat / SVG | CLI-native, no browser dependency; DOT handles both KG subgraphs and causal DAGs |
| Domain ontologies | Optional prefix imports | Core schema is domain-agnostic; biolink:, go:, mesh: etc. added as needed with no code changes |
| Heavy deps | Optional extras (`[causal]`, `[ml]`) | Core package stays lightweight; PPL and ML deps installed only when needed |
| RDF-star migration | Planned for when rdflib supports it | Current reification approach is forward-compatible; migration path documented |
| No literature search in CLI | Agent-driven via LLM knowledge + web search | API-based lit search adds complexity with limited marginal value; agents already handle this well |
| Use-case-driven query presets | Named CLI commands, not raw SPARQL | Agent is the primary CLI consumer; presets map directly to research questions |
| Prose annotations as graph bridge | Frontmatter `ontology_terms:` + inline CURIEs | Anchors linking narrative text to graph entities; enables future automated entity matching |
| Graph revision tracking | Revision stamp (timestamp + hash) in `knowledge/graph.trig` | `science-tool graph diff` runs hybrid checks (mtime + content hash) against graph revision metadata |
| DBpedia distillation deferred | OpenAlex + PrimeKG are Phase 3 priority | Less immediately useful than domain-specific sources; design retained for future |

## 9. Future Considerations

- **RDF-star migration:** When rdflib implements RDF 1.2 triple terms, migrate provenance from reified statements to annotation syntax. The named graph structure is preserved; only the provenance encoding within `:graph/provenance` changes.
- **Oxigraph backend:** If graphs exceed ~100K triples (e.g., importing full PrimeKG), swap rdflib's in-memory store for `pyoxigraph` (Rust-based, same SPARQL interface, handles millions of triples).
- **KG embeddings:** Use PyKEEN to train embeddings on the project graph for link prediction ("what relations might exist that we haven't found?"). Embeddings stored as node properties.
- **GNN integration:** Use PyTorch Geometric for downstream ML tasks on the graph (node classification, link prediction with learned features). NetworkX → PyG conversion is built-in.
- **Automated distillation updates:** Periodic re-runs of the distillation pipeline to capture new entities in public KGs.
- **SHACL validation:** Define SHACL shapes for the core ontology to validate graph structure (e.g., every Claim must have provenance, every CausalVariable must have isObserved).
- **Collaborative graphs:** Multiple researchers sharing a project graph via git (TriG files are text, diffable, mergeable).
- **DBpedia distillation:** Add DBpedia as a third distillation source for general-knowledge enrichment (design documented in section 4.2, currently deferred).
- **Automated entity matching:** Build on ontology caching groundwork to scan prose documents for candidate entity matches against cached vocabularies, providing input context to the graph authoring agent.
- **DOI-based enrichment:** Extend DOI lookup to automatically populate graph nodes with structured metadata (authors, venues, concepts) from CrossRef/OpenAlex responses.

## References

1. [PrimeKG — Nature Scientific Data (2023)](https://www.nature.com/articles/s41597-023-01960-3)
2. [OpenBioLink — Bioinformatics (2020)](https://academic.oup.com/bioinformatics/article/36/13/4097/5825726)
3. [PyKEEN — JMLR (2021)](https://github.com/pykeen/pykeen)
4. [Biolink Model — PMC (2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9372416/)
5. [W3C PROV-O](https://www.w3.org/TR/prov-o/)
6. [W3C SKOS](https://www.w3.org/TR/skos-reference/)
7. [schema.org ScholarlyArticle](https://schema.org/ScholarlyArticle)
8. [pgmpy FunctionalBayesianNetwork](https://pgmpy.org/models/functionalbn.html)
9. [ChiRHo — Basis Research](https://github.com/BasisResearch/chirho)
10. [PyMC do-operator](https://www.pymc.io/projects/examples/en/latest/causal_inference/interventional_distribution.html)
11. [Extractive KG Summarization Survey — IJCAI 2024](https://arxiv.org/abs/2402.12001)
12. [OpenAlex Topics](https://docs.openalex.org/api-entities/topics)
13. [rdflib Documentation](https://rdflib.readthedocs.io/)
14. [Causal relationships in ontologies — PMC (2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9473331/)

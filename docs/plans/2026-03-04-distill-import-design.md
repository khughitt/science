# Snapshot Distillation & Import — Design

*Date: 2026-03-04*
*Status: DONE*
*Parent: [Knowledge Graph Design](2026-03-01-knowledge-graph-design.md) — Slice A completion*

## Overview

Pre-generate small, browseable Turtle snapshots of public knowledge graphs and import them into the project's `:graph/knowledge` layer. Completes the remaining Slice A work.

## Architecture

```
science-tool/
├── src/science_tool/
│   ├── distill/
│   │   ├── __init__.py          # Shared helpers (triples→Turtle, manifest writing)
│   │   ├── openalex.py          # OpenAlex API → Turtle (domains/fields/subfields/topics)
│   │   └── pykeen_source.py     # PyKEEN dataset → PageRank → distilled Turtle
│   └── cli.py                   # + distill group, graph import command
├── data/snapshots/              # Output dir for generated snapshots
└── tests/
    ├── test_distill.py          # Unit tests for distillers
    └── fixtures/                # Small synthetic triples for testing
```

## Components

### 1. OpenAlex distiller (`distill/openalex.py`)

Fetches the OpenAlex science concept hierarchy via API.

**Flow:**
1. Fetch `/domains`, `/fields`, `/subfields` (and optionally `/topics`) from `api.openalex.org`
2. Map to SKOS hierarchy: `skos:broader`/`skos:narrower` + `skos:prefLabel` + work counts
3. Type nodes as `sci:Concept, skos:Concept`
4. Write `.ttl` + update `manifest.ttl`

**CLI:**
```bash
science-tool distill openalex --level subfields     # ~282 nodes, ~600 triples
science-tool distill openalex --level topics         # ~4800 nodes, ~10000 triples
```

**Output:** `data/snapshots/openalex-science-map.ttl` (or `openalex-topics.ttl` for full)

### 2. PyKEEN-based distiller (`distill/pykeen_source.py`)

Generic distiller for any PyKEEN dataset. Supports budget-based distillation via type-stratified PageRank.

**Flow:**
1. Load dataset: `pykeen.datasets.get_dataset(dataset="PrimeKG")` → `TriplesFactory`
2. Build NetworkX graph from labeled triples
3. If `--budget` specified: run type-stratified PageRank, select top-N per entity type, retain inter-selected edges
4. If no budget: take all triples (for small datasets like DBpedia50)
5. Convert selected triples to RDF: entities become `sci:Concept` with `skos:prefLabel`, relations become predicates under `sci:` namespace
6. Write `.ttl` + update `manifest.ttl`

**CLI:**
```bash
science-tool distill pykeen PrimeKG --budget 170    # Type-stratified PageRank
science-tool distill pykeen DBpedia50               # Take all (small dataset)
```

**Output:** `data/snapshots/<dataset-slug>.ttl` (e.g., `primekg-core.ttl`, `dbpedia50.ttl`)

### 3. `graph import` command

Loads a `.ttl` snapshot into the project's `:graph/knowledge` layer.

**Flow:**
1. Parse the snapshot `.ttl` file
2. Merge all triples into the project's `:graph/knowledge` named graph
3. Record import provenance in `:graph/provenance` (source file, timestamp, triple count)
4. Save updated `graph.trig`

**CLI:**
```bash
science-tool graph import data/snapshots/openalex-science-map.ttl
science-tool graph import data/snapshots/primekg-core.ttl
```

## Dependencies

```toml
[project.optional-dependencies]
distill = [
    "pykeen",           # Dataset loading (PrimeKG, DBpedia50, etc.)
    "networkx>=3.2",    # PageRank for budget-based distillation
    "httpx",            # OpenAlex API fetching
]
```

Core graph commands remain lightweight (rdflib + click + rich only).

## Manifest format

Each snapshot gets a PROV-O entry in `data/snapshots/manifest.ttl`:

```turtle
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix :       <http://example.org/science/snapshots/> .

:openalex-science-map a prov:Entity, schema:Dataset ;
    schema:name "OpenAlex Science Map (subfield level)" ;
    prov:generatedAtTime "2026-03-04T00:00:00Z"^^xsd:dateTime ;
    prov:wasDerivedFrom <https://api.openalex.org/subfields> ;
    schema:version "openalex:2026-03-04" ;
    schema:size "282 nodes, 600 triples" ;
    schema:sha256 "<snapshot-hash>" .
```

## Testing strategy

- **OpenAlex**: mock HTTP responses with a small fixture (3 domains, 5 fields, 10 subfields). Verify SKOS hierarchy in output Turtle.
- **PyKEEN**: mock `pykeen.datasets.get_dataset` to return a small synthetic `TriplesFactory` (~20 triples). Verify PageRank selection and output Turtle.
- **`graph import`**: create a small `.ttl` fixture, import into a fresh `graph.trig`, verify triples land in `:graph/knowledge` and provenance is recorded.
- No live API calls in tests.

## Scope boundary

**In scope:**
- `distill openalex` (subfields + topics levels)
- `distill pykeen` (generic, works with any PyKEEN dataset, optional `--budget`)
- `graph import` (merge `.ttl` into project graph with provenance)
- `manifest.ttl` generation
- Tests for all of the above

**Out of scope:**
- Automated ontology matching / entity alignment
- Biolink-typed nodes (future enrichment step)
- Re-distillation / update detection for snapshots

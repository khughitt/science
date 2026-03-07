# Biomedical Knowledge Graph — Starter Profile

*Derived from the 3D Attention Bias exemplar project (2026-03-07)*

This reference documents the ontology types, predicates, CURIE prefixes, and patterns that proved useful when building a knowledge graph for a genomics/deep-learning research project.

## Recommended Ontology Prefixes

| Prefix | URI | Purpose |
|--------|-----|---------|
| `skos:` | `http://www.w3.org/2004/02/skos/core#` | Concept hierarchy, labels, definitions, notes |
| `cito:` | `http://purl.org/spar/cito/` | Citation typing (paper-to-concept relationships) |
| `prov:` | `http://www.w3.org/ns/prov#` | Provenance (who created what, when) |
| `schema:` | `https://schema.org/` | Paper metadata (name, author, datePublished) |
| `sci:` | `http://example.org/science/vocab/` | Project-specific vocabulary (Claim, Hypothesis, Question) |
| `biolink:` | `https://w3id.org/biolink/vocab/` | Biomedical entity types (optional, for richer typing) |

## Entity Types

### Core types (always available)

- `sci:Concept` + `skos:Concept` — All domain concepts (models, methods, biological entities)
- `sci:Paper` — Published papers (identified by DOI)
- `sci:Claim` — Assertions with provenance and confidence
- `sci:Hypothesis` — Testable hypotheses
- `sci:Question` — Open research questions

### Recommended Biolink types for bioinformatics projects

| Biolink Type | Use For | Example |
|-------------|---------|---------|
| `biolink:Gene` | Gene entities | CTCF, Cohesin |
| `biolink:GeneFamily` | Gene families, protein families | Transformer models (by analogy) |
| `biolink:BiologicalProcess` | Biological processes | Chromatin looping, transcription |
| `biolink:MolecularActivity` | Molecular functions | DNA binding, RNA folding |
| `biolink:ChemicalEntity` | Molecules, compounds | DNA, RNA, nucleotides |
| `biolink:NucleicAcidEntity` | DNA/RNA sequences | Enhancer sequences, promoter regions |
| `biolink:InformationContentEntity` | Datasets, databases | OpenAlex, PDB, Hi-C datasets |
| `biolink:Procedure` | Experimental methods | DMS-seq, SHAPE, Hi-C |

## Key Predicates

### SKOS (concept organization)
```
skos:prefLabel    — Primary label for a concept
skos:definition   — Formal definition
skos:note         — Informal annotation
skos:broader      — Parent concept
skos:narrower     — Child concept
skos:related      — Non-hierarchical association
```

### CiTO (citation typing)
```
cito:discusses       — Paper discusses a concept (most common)
cito:supports        — Paper provides evidence for a claim
cito:extends         — Paper builds on prior work
cito:usesMethodIn    — Paper uses a method from another paper
cito:cites           — Generic citation
```

### Project-specific (sci:)
```
sci:projectStatus    — active | candidate | selected-primary | deferred | speculative
sci:confidence       — 0.0–1.0 confidence score (for claims)
sci:usesComponent    — Model X uses component Y
sci:inspiredBy       — Concept X inspired by concept Y
sci:modifies         — Concept X modifies concept Y
sci:requiresInput    — Method X requires input Y
sci:partOf           — Component X is part of system Y
sci:mediates         — Process X mediates relationship Y
sci:targets          — Method X targets entity Y
sci:exemplifies      — Instance X exemplifies pattern Y
```

## Example Commands

### Add a concept with full metadata
```bash
science-tool graph add concept "DNABERT-2" \
  --type "biolink:InformationContentEntity" \
  --note "Multi-species genome foundation model using BPE tokenization" \
  --definition "Transformer-based DNA language model trained on multi-species genomes" \
  --status active \
  --source "paper:doi_10.48550/arXiv.2306.15006" \
  --property architecture "transformer-encoder" \
  --property parameters "117M" \
  --property tokenization "BPE" \
  --property positional_encoding "ALiBi"
```

### Add a paper
```bash
science-tool graph add paper --doi "10.1038/s41586-024-07487-w"
```

### Add a claim with provenance
```bash
science-tool graph add claim \
  "ALiBi achieves comparable performance to sinusoidal PE with better length extrapolation" \
  --source "paper:doi_10.48550/arXiv.2108.12409" \
  --confidence 0.9
```

### Add edges between entities
```bash
# Paper discusses a concept
science-tool graph add edge "paper:doi_10.48550/arXiv.2306.15006" "cito:discusses" "concept/dnabert_2"

# Concept uses a component
science-tool graph add edge "concept/dnabert_2" "sci:usesComponent" "concept/alibi"

# Broader/narrower hierarchy
science-tool graph add edge "concept/alibi" "skos:broader" "concept/attention_bias"
```

### Import external snapshot
```bash
science-tool graph import data/snapshots/openalex-science-map.ttl
```

## Graph Size Guidelines

For a typical research project with 15-25 papers:

| Entity Type | Target Count | Notes |
|------------|-------------|-------|
| Concepts | 30-50 | Include models, methods, biological entities, key terms |
| Papers | 15-25 | One per paper summary |
| Claims | 20-40 | Key findings with confidence scores |
| Hypotheses | 1-5 | Testable project hypotheses |
| Questions | 5-15 | Open questions linked to hypotheses |
| Edges | 50-100+ | CiTO + domain-specific predicates |

## Validation

After building the graph, always run:
```bash
science-tool graph validate              # 4 structural checks
science-tool graph stats --format json   # Triple counts per layer
SCIENCE_TOOL_PATH=/path/to/science-tool validate.sh  # Full project validation
```

All 4 validation checks should pass:
1. `parseable_trig` — Graph file is valid TriG
2. `provenance_completeness` — All claims/hypotheses have provenance
3. `causal_acyclicity` — Causal graph has no cycles
4. `orphaned_nodes` — All entities have at least one edge

---
description: Construct a knowledge graph from project prose documents. Reads research docs, extracts entities/relations/claims, populates the graph with provenance, and adds ontology annotations to source documents.
---

# Create Knowledge Graph from Prose

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This command walks through project prose documents (research notes, literature summaries, hypothesis documents) and constructs a knowledge graph with proper provenance and ontology alignment.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

> **Cache note:** If `uv run --with` reports missing commands or flags that should exist, the build cache may be stale. Run `uv cache clean science-tool` to clear it, then retry.

## Rules

- **MUST** use `cito:supports`/`cito:disputes` for evidence relations, NOT `sci:supports`/`sci:refutes`
- **MUST** use `skos:related` for general associations, NOT `sci:relatedTo`
- **MUST** run `science-tool graph predicates` before adding edges — only use listed predicates
- **MUST** use `--note`, `--property`, `--status`, `--source` flags on concepts — do NOT edit graph.trig directly
- **MUST** run `science-tool graph add question` for open questions — do NOT skip this step
- **MUST NOT** invent predicates — if a relationship doesn't fit an existing predicate, use `skos:related` and add a `--note`
- **SHOULD** keep build scripts in `knowledge/` for reproducibility — do NOT delete them after running
- **URI slugification:** Entity labels are auto-slugified (lowercase, non-alphanumeric → `_`). Bare terms in `graph add edge` follow the same rule. After `graph add concept`, check the echoed URI (e.g. `Added concept: http://example.org/project/concept/nucleotide_transformer_v2`) and use that slug in subsequent `graph add edge` calls. The CLI echoes resolved URIs for edges too, so you can verify the mapping.

## Prerequisites

This command **creates a graph from scratch**. If a graph already exists, use `update-graph` instead for incremental updates.

Research documents should exist in `doc/`, `specs/`, or `doc/papers/`.

## Workflow

### Step 1: Initialize graph and review predicates

```bash
science-tool graph init
science-tool graph predicates --format table
```

Initialize a fresh `knowledge/graph.trig`. Then review the full predicate list — only use predicates from this list when adding edges. If a relationship doesn't fit any predicate, default to `skos:related`.

### Step 2: Process each document

For each research document, in order:

1. **Read the document** to understand its content.
2. **Identify entities**: concepts, genes, diseases, drugs, pathways, papers, datasets, models, methods, tools.
3. **Identify relations**: associations, hierarchies, causal claims, evidence links. Use `cito:supports`/`cito:disputes` for evidence, `skos:related` for general associations (not `sci:relatedTo`).
4. **Identify claims**: factual assertions with their sources and confidence levels.
5. **Identify open questions**: unresolved research questions with their maturity status.
6. **Add entities to the graph** using `science-tool graph add` commands with rich metadata. Example:
   ```bash
   science-tool graph add concept "DNABERT-2" \
     --type biolink:GeneticModel \
     --ontology-id "DNABERT2" \
     --note "12 layers; max context 2048 nt; BPE tokenizer" \
     --definition "DNA foundation model pretrained on multi-species genomes" \
     --status selected-primary \
     --source paper:doi_10_1234_test \
     --property hasArchitecture "BERT encoder" \
     --property hasParameters "117M"
   ```
   - Use `--note` for contextual information (parameters, architecture, status notes)
   - Use `--property KEY VALUE` for structured metadata (hasArchitecture, hasParameters, hasTokenization, hasEmbeddingDim)
   - Use `--status` for project relevance (`selected-primary`, `deferred`, `active`, `candidate`, `speculative`)
   - Use `--source` for provenance on concepts, not just claims and hypotheses
7. **Add open questions** using `science-tool graph add question <ID> --text "<text>" --source <ref>`:
   - Use `--maturity open|partially-resolved|resolved` to indicate resolution status
   - Use `--related-hypothesis <hyp_ref>` to link questions to relevant hypotheses
   - Number questions sequentially (Q01, Q02, ...)
8. **Add prose annotations** to the document:
   - Add `ontology_terms:` frontmatter with relevant CURIEs.
   - Add inline `[`CURIE`]` annotations on first mention of each entity.

### Step 3: Entity extraction checklist

For each entity found in prose, determine:

- [ ] **Label**: human-readable name
- [ ] **Type**: `sci:Concept` + domain type (e.g., `biolink:Gene`)
- [ ] **Ontology ID**: standard identifier (e.g., `NCBIGene:672`, `MONDO:0016419`)
- [ ] **Relations**: how it connects to other entities already in the graph
- [ ] **Properties**: structured metadata (architecture, parameters, dimensions) via `--property`
- [ ] **Note**: freeform contextual annotations via `--note`
- [ ] **Status**: project relevance (`selected-primary`, `deferred`, `active`) via `--status`
- [ ] **Source**: provenance document reference via `--source`

### Step 4: Claim extraction checklist

For each factual assertion:

- [ ] **Text**: the claim statement
- [ ] **Source**: which paper/document supports it (use `paper:doi_<slug>` format)
- [ ] **Confidence**: estimated strength (0.0-1.0)
- [ ] **ID**: optional explicit claim ID for cross-referencing

### Step 5: Finalize

After processing all documents:

```bash
science-tool graph stamp-revision
science-tool graph validate --format json
science-tool graph stats --format json
```

All validation checks must pass. Report the final graph stats to the user.

## Output

At completion, the user should have:
1. A populated `knowledge/graph.trig` with entities, relations, and provenance.
2. Research documents annotated with frontmatter `ontology_terms:` and inline CURIEs.
3. A clean `graph validate` output.

## Important Notes

- **Do not invent claims.** Only add claims that are explicitly stated in the prose.
- **Always include provenance.** Every claim and hypothesis must have a `--source`.
- **Prefer existing ontology IDs** over invented ones. Use standard identifiers (NCBI Gene, MONDO, ChEBI, etc.).
- **Ask the user** if uncertain about entity types, confidence levels, or whether something is a claim vs. background knowledge.
- **Track deferred entities.** If an entity is identified but peripheral to current work, add it to `knowledge/deferred-entities.md` with a brief description rather than cluttering the graph. Add to the graph later when it becomes relevant.

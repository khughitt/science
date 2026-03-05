---
name: create-graph
description: Construct a knowledge graph from project prose documents. Reads research docs, extracts entities/relations/claims, populates the graph with provenance, and adds ontology annotations to source documents.
user_invocable: true
---

# Create Knowledge Graph from Prose

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This skill walks through project prose documents (research notes, literature summaries, hypothesis documents) and constructs a knowledge graph with proper provenance and ontology alignment.

## Prerequisites

Before running this skill:
1. The project must have `knowledge/graph.trig` initialized. If not: `uv run science-tool graph init`
2. Research documents should exist in `doc/`, `specs/`, `notes/`, or `papers/summaries/`.

## Workflow

### Step 1: Scan for existing annotations

```bash
uv run science-tool graph scan-prose doc/
uv run science-tool graph scan-prose specs/
uv run science-tool graph scan-prose notes/
```

Review the output. Files with existing annotations already have entity groundwork.

### Step 2: Check current graph state

```bash
uv run science-tool graph stats --format json
```

If the graph already has entities, note what exists to avoid duplicates.

### Step 3: Process each document

For each research document, in order:

1. **Read the document** to understand its content.
2. **Identify entities**: concepts, genes, diseases, drugs, pathways, papers, datasets.
3. **Identify relations**: associations, hierarchies, causal claims, evidence links.
4. **Identify claims**: factual assertions with their sources and confidence levels.
5. **Add entities to the graph** using `science-tool graph add` commands.
6. **Add prose annotations** to the document:
   - Add `ontology_terms:` frontmatter with relevant CURIEs.
   - Add inline `[`CURIE`]` annotations on first mention of each entity.

### Step 4: Entity extraction checklist

For each entity found in prose, determine:

- [ ] **Label**: human-readable name
- [ ] **Type**: `sci:Concept` + domain type (e.g., `biolink:Gene`)
- [ ] **Ontology ID**: standard identifier (e.g., `NCBIGene:672`, `MONDO:0016419`)
- [ ] **Relations**: how it connects to other entities already in the graph

### Step 5: Claim extraction checklist

For each factual assertion:

- [ ] **Text**: the claim statement
- [ ] **Source**: which paper/document supports it (use `paper:doi_<slug>` format)
- [ ] **Confidence**: estimated strength (0.0-1.0)
- [ ] **ID**: optional explicit claim ID for cross-referencing

### Step 6: Finalize

After processing all documents:

```bash
uv run science-tool graph stamp-revision
uv run science-tool graph validate --format json
uv run science-tool graph stats --format json
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

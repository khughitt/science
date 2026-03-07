---
description: Sketch a research model interactively. Captures variables, relationships, data sources, and unknowns as an inquiry subgraph. Use when the user wants to explore what variables matter, how things connect, or how to approach a question computationally. Also use when the user says "sketch", "what variables", "how would I model", or "what affects what".
---

# Sketch a Research Model

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This command helps the user sketch the shape of a research investigation: what variables matter, how they connect, what data is available, and what's unknown. The output is an inquiry subgraph in the knowledge graph — a rough model that can later be formalized with `/science:specify-model`.

Missing provenance, loose edge types, and `sci:Unknown` nodes are all fine at this stage. The goal is to capture the structure of the user's thinking, not to be precise.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** initialize the graph if it doesn't exist (`science-tool graph init`)
- **MUST** create the inquiry before adding nodes/edges (`science-tool inquiry init`)
- **MUST** add all entities to the knowledge graph (`graph add concept`) AND to the inquiry (`inquiry add-node`)
- **MUST** use `sci:feedsInto` for data flow edges, NOT `skos:related`
- **MAY** use `skos:related` for uncertain/associative relationships
- **MAY** use `sci:Unknown` type for unidentified variables
- **MUST NOT** require provenance — this is a sketch, not a specification
- **SHOULD** ask clarifying questions adaptively, not as a rigid questionnaire

## Workflow

### Step 1: Gather context

Read the following project files (skip any that don't exist):
- `specs/research-question.md` — project scope
- `specs/hypotheses/` — existing hypotheses
- `doc/08-open-questions.md` — open questions
- `knowledge/graph.trig` — existing graph (if any)
- `doc/inquiries/` — existing inquiries (if any)

If no graph exists, initialize one:
```bash
science-tool graph init
```

### Step 2: Interactive conversation

Have a natural, adaptive conversation. These questions are guidelines — skip ahead if the user provides enough context upfront.

1. **Target:** "What are you trying to test or answer?"
   - Identify the target hypothesis or question
   - If it doesn't exist yet, offer to create it with `/science:add-hypothesis`

2. **Variables:** "What variables or quantities matter here?"
   - What can you directly observe or measure?
   - What's latent — things you think matter but can't directly see?
   - What's computed — derived from other variables?

3. **Relationships:** "What do you think affects what?"
   - Don't worry about precision — rough arrows are fine
   - "Does A cause B, or are they just correlated? Don't know? That's fine too."

4. **Data:** "What data do you have or could get?"
   - Existing datasets, databases, measurements
   - What's available vs. what would need to be generated?

5. **Unknowns:** "What are you unsure about?"
   - Create `sci:Unknown` nodes for gaps
   - "Is there something that might affect the outcome but you're not sure what?"

### Step 3: Build the inquiry subgraph

From the conversation:

1. **Create the inquiry:**
```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>"
```

2. **Add entities to the knowledge graph** (if they don't already exist):
```bash
science-tool graph add concept "<variable name>" --type sci:Variable
science-tool graph add concept "<data source>" --type sci:Variable
science-tool graph add concept "<unknown factor>" --type sci:Unknown
```

3. **Add nodes to the inquiry with boundary roles:**
```bash
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryIn
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryOut
```

4. **Add edges within the inquiry:**
```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "sci:feedsInto" "concept:<to>"
```

5. **Add assumptions** (if the user mentions them):
```bash
science-tool inquiry add-edge "<slug>" "concept:<node>" "sci:assumes" "concept:<assumption>"
```

### Step 4: Visualize and summarize

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Save the inquiry document to `doc/inquiries/<slug>.md`.

Show the user the boundary nodes, data flow, and any unknowns.

### Step 5: Finalize

```bash
science-tool graph stamp-revision
```

Suggest next steps:
1. If the sketch looks good: `/science:specify-model <slug>` to add rigor
2. If more background needed: `/science:research-topic` or `/science:search-literature`
3. If hypotheses need work: `/science:add-hypothesis`

## Important Notes

- **Don't over-formalize.** A sketch with 5-10 nodes and rough edges is better than trying to capture everything.
- **Unknown nodes are valuable.** They make gaps explicit rather than leaving them implicit in prose.
- **Multiple sketches are fine.** A project can have several inquiry sketches exploring different approaches.
- **Reuse existing entities.** Check the graph for existing concepts before creating duplicates.

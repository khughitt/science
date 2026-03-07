---
description: Formalize a research model with full evidence provenance. Every variable gets a type, every edge gets evidence, every parameter gets a source. Use when the user wants to make a sketch rigorous, add provenance, resolve unknowns, or formalize assumptions. Also use when the user says "specify", "formalize", "add evidence", "make rigorous", or "resolve unknowns".
---

# Specify a Research Model

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This command takes an inquiry from sketch to specified status. Every variable gets a formal type, every edge gets evidence, every parameter gets provenance metadata (AnnotatedParam-style), and all `sci:Unknown` nodes are resolved or justified.

Can start from an existing sketch (preferred) or from scratch.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** read the existing inquiry before modifying it
- **MUST** assign formal types to all variables (not just `sci:Concept`)
- **MUST** replace `skos:related` edges with typed predicates where the relationship is known
- **MUST** add `--source` provenance to all assumptions and claims
- **MUST** resolve or justify all `sci:Unknown` nodes
- **MUST** run `inquiry validate` after specifying — all checks must pass
- **MUST** add AnnotatedParam metadata for all non-trivial parameter values
- **SHOULD** identify confounders for each causal/directional edge
- **SHOULD** justify edge direction (why A->B not B->A?)

## Workflow

### Step 1: Load and assess the inquiry

If `$ARGUMENTS` contains a slug:
```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Identify gaps:
- Variables without formal types
- Edges using `skos:related` that should be more specific
- Nodes without provenance
- `sci:Unknown` nodes needing resolution
- Missing confounders
- Parameters without AnnotatedParam metadata

If no slug provided, ask which inquiry to specify, or offer to create one from scratch.

### Step 2: Specify variables

For each variable in the inquiry, work through interactively:

1. **Type:** "What kind of thing is this?" -> assign `biolink:*`, `sci:Variable`, `sci:Transformation`, etc.
```bash
science-tool graph add concept "<name>" --type <CURIE> --definition "<definition>"
```

2. **Observability:** Is this observed, latent, or computed?

3. **Provenance:** Where does this come from?
```bash
science-tool graph add concept "<name>" --source "<ref>"
```

### Step 3: Specify edges

For each edge in the inquiry:

1. **Type:** Replace loose edges with typed predicates
   - `sci:feedsInto` -> data/information flow (keep if correct)
   - `scic:causes` -> causal claim (requires evidence)
   - `sci:assumes` -> dependency on assumption
   - `sci:produces` -> transformation output

2. **Evidence:** Create a claim justifying each non-obvious edge
```bash
science-tool graph add claim "X feeds into Y because..." --source "paper:doi_..." --confidence 0.8
```

3. **Direction justification:** For causal/directional edges, note why A->B not B->A

4. **Confounders:** "What else could explain this relationship?"
```bash
science-tool graph add concept "<confounder>" --type sci:Variable
science-tool graph add edge "concept:<confounder>" "scic:confounds" "concept:<edge-subject>"
```

### Step 4: Specify parameters

For each parameter-bearing node, add AnnotatedParam metadata. Source types: `literature`, `empirical`, `design_decision`, `convention`, `data_derived`.

### Step 5: Resolve unknowns

For each `sci:Unknown` node:
- **Resolve:** Replace with a real entity (new concept with proper type and provenance)
- **Justify:** Document why it remains unknown and what would resolve it
- **Remove:** If the unknown is no longer relevant

### Step 6: Validate and finalize

```bash
science-tool inquiry validate "<slug>" --format json
```

All checks must pass for a specified inquiry:
- boundary_reachability: pass
- no_cycles: pass
- unknown_resolution: pass
- target_exists: pass

Update the inquiry document in `doc/inquiries/<slug>.md`.

```bash
science-tool graph stamp-revision
```

### Step 7: Suggest next steps

1. `/science:plan-pipeline <slug>` — generate computational implementation plan
2. `/science:review-pipeline <slug>` — get a critical review before implementation
3. `/science:discuss` with `focus_ref: inquiry:<slug>` — structured discussion

## Important Notes

- **Evidence-driven.** Every edge should be justifiable. If you can't justify an edge, it might not belong in the model.
- **Parameters are first-class.** Every number in the eventual pipeline should trace back to a source: a paper, a dataset, a design decision, or a convention.
- **Confounders matter.** The specify step is where you catch missing variables.
- **Iterate with the user.** Don't specify everything silently — discuss non-obvious decisions.

---
description: Build a causal DAG interactively. Identifies treatment, outcome, confounders, and causal edges, then creates a causal inquiry with validation. Use when the user wants to model cause-and-effect, build a causal model, identify confounders, or estimate treatment effects. Also use when the user says "causal", "DAG", "what causes", "confounders", or "treatment effect".
---

# Build a Causal DAG

> **Prerequisite:** Load the `knowledge-graph` and `causal-dag` skills for ontology and causal modeling reference.

## Overview

This command guides the user through constructing a causal directed acyclic graph (DAG) for their research question. The output is a causal inquiry in the knowledge graph — variables connected by `scic:causes` and `scic:confounds` edges, with a defined treatment and outcome.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, examples write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** initialize the graph if it doesn't exist (`science-tool graph init`)
- **MUST** create the inquiry with `--type causal` (`science-tool inquiry init --type causal`)
- **MUST** add all variables to `graph/knowledge` (`graph add concept --type sci:Variable`) AND to the inquiry (`inquiry add-node`)
- **MUST** add causal edges to `graph/causal` (`graph add edge ... --graph graph/causal`)
- **MUST** set the estimand (`inquiry set-estimand --treatment ... --outcome ...`)
- **MUST** justify every causal edge with a claim that has provenance and confidence
- **MUST** ask about confounders for every proposed causal edge
- **MUST** run `inquiry validate` before finishing
- **SHOULD** suggest running `/science:critique-approach` as the next step

## Workflow

### Step 1: Gather context

Read the following project files (skip any that don't exist):
- `science.yaml` — project metadata
- `doc/01-research-question.md` — what the project investigates
- `doc/08-open-questions.md` — open questions
- `specs/hypotheses/*.md` — existing hypotheses
- `knowledge/graph.trig` — existing knowledge graph (run `science-tool graph stats`)
- `science-tool inquiry list` — existing inquiries

### Step 2: Identify the causal question

Ask the user (one question at a time, adaptively):

1. "What causal question are you investigating?" — identify the core research question
2. "What is the treatment or intervention? (What do you want to manipulate or study the effect of?)"
3. "What is the outcome? (What do you want to measure the effect on?)"
4. "What variables do you think affect both the treatment and the outcome? (These are potential confounders.)"

### Step 3: Identify variables

For each variable mentioned:
- Check if it already exists in the knowledge graph (`graph neighborhood <name>`)
- If not, add it: `graph add concept "<name>" --type sci:Variable --status active --property observability <observed|latent|computed>`
- Add it to the inquiry: `inquiry add-node "<slug>" "concept/<name>" --role <BoundaryIn|BoundaryOut>`
- Classify: treatment and confounders are typically BoundaryIn, outcome is BoundaryOut

### Step 4: Build causal edges

For each proposed causal relationship:

1. State the edge: "I'm proposing that A causes B."
2. Ask: "Why do you believe A causes B? What evidence supports this?"
3. Create a claim: `graph add claim "<justification>" --source "<ref>" --confidence <0-1>`
4. Add the edge: `graph add edge "concept/a" "scic:causes" "concept/b" --graph graph/causal`
5. Ask about confounders: "Is there anything else that affects both A and B?"
6. If yes, add the confounder variable and its edges

### Step 5: Set the estimand

```bash
science-tool inquiry set-estimand "<slug>" --treatment "concept/<treatment>" --outcome "concept/<outcome>"
```

### Step 6: Validate and visualize

```bash
science-tool inquiry validate "<slug>" --format json
science-tool graph viz --graph graph/causal
```

Check that:
- `causal_acyclicity` passes
- `boundary_reachability` passes
- All boundary nodes are classified

### Step 7: Summary and next steps

- Summarize the DAG: how many variables, edges, confounders
- Show the validation results
- Suggest: "Run `/science:critique-approach <slug>` to review this DAG for missing confounders and identifiability."
- Suggest: "Run `science-tool inquiry export-pgmpy <slug>` to check adjustment sets."

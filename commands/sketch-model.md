---
description: Sketch a research model interactively. Captures variables, relationships, data sources, and unknowns as an inquiry subgraph. Auto-detects causal mode when the causal-modeling aspect is active or user language signals causal intent. Use when the user wants to explore what variables matter, how things connect, or how to approach a question computationally. Also use when the user says "sketch", "what variables", "how would I model", "what affects what", "causal", "DAG", "confounders", or "treatment effect".
---

# Sketch a Research Model

> **Prerequisites:**
> - Load the `knowledge-graph` skill for ontology reference before starting.
> - If causal mode is active (see below): also load the `causal-dag` skill.

## Overview

This command helps the user sketch the shape of a research investigation: what variables matter, how they connect, what data is available, and what's unknown. The output is an inquiry subgraph in the knowledge graph — a rough model that can later be formalized with `/science:specify-model`.

Missing provenance, loose edge types, and `sci:Unknown` nodes are all fine at this stage. The goal is to capture the structure of the user's thinking, not to be precise.

## Causal Mode Detection

This command auto-detects causal intent and switches to causal DAG mode when appropriate. Causal mode activates when **any** of the following are true:

1. The `causal-modeling` aspect is active in `science.yaml`
2. User language in `$ARGUMENTS` signals causal intent: "causal", "DAG", "confounders", "treatment effect", "what causes", "intervention"
3. Existing causal inquiries exist in the project (check `science-tool inquiry list` for type=causal)

When causal mode is active:
- Load the `causal-dag` skill for pitfall patterns and ontology
- Create the inquiry with `--type causal` instead of default
- Use `scic:causes` and `scic:confounds` edges instead of `sci:feedsInto`
- Set the estimand (treatment → outcome) using `inquiry set-estimand`
- Require justification for every causal edge (claim with provenance and confidence)
- Ask about confounders for every proposed causal edge
- Suggest `/science:critique-approach` as the next step

When causal mode is NOT active:
- Follow the standard sketch workflow (variables, relationships, unknowns)
- Use `sci:feedsInto` for data flow edges, `skos:related` for uncertain associations
- Missing provenance and `sci:Unknown` nodes are fine
- Suggest `/science:specify-model` as the next step

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
- `doc/questions/` — open questions
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

**If causal mode is active, also ask:**

4. **Treatment:** "What is the treatment or intervention? (What do you want to manipulate or study the effect of?)"
5. **Outcome:** "What is the outcome? (What do you want to measure the effect on?)"
6. **Confounders:** "What variables affect both the treatment and outcome? (These are potential confounders.)"
7. **Evidence for causation:** For each proposed causal relationship: "Why do you believe A causes B? What evidence supports this?"

**For all modes, continue with:**

8. **Data:** "What data do you have or could get?"
   - Existing datasets, databases, measurements
   - What's available vs. what would need to be generated?

9. **Unknowns:** "What are you unsure about?"
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

**If causal mode:** create with `--type causal`:
```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --type causal
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

**If causal mode:** use causal predicates:
```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "scic:causes" "concept:<to>"
science-tool graph add claim "<justification>" --source "<ref>" --confidence <0-1>
```

And set the estimand:
```bash
science-tool inquiry set-estimand "<slug>" --treatment "concept/<treatment>" --outcome "concept/<outcome>"
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

The inquiry status is `sketch` at this stage.

Show the user the boundary nodes, data flow, and any unknowns.

### Step 5: Finalize

```bash
science-tool graph stamp-revision
```

Suggest next steps:
1. If causal mode: `/science:critique-approach <slug>` to review the DAG for missing confounders
2. If non-causal and sketch looks good: `/science:specify-model <slug>` to add rigor
3. If more background needed: `/science:research-topic` or `/science:search-literature`
4. If hypotheses need work: `/science:add-hypothesis`

## Important Notes

- **Don't over-formalize.** A sketch with 5-10 nodes and rough edges is better than trying to capture everything.
- **Unknown nodes are valuable.** They make gaps explicit rather than leaving them implicit in prose.
- **Multiple sketches are fine.** A project can have several inquiry sketches exploring different approaches.
- **Reuse existing entities.** Check the graph for existing concepts before creating duplicates.

## Process Reflection

Reflect on the **sketch workflow** and the **interactive conversation** process.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — sketch-model

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("causal mode detection was ambiguous when the user said X" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

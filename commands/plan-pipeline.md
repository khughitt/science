---
description: Generate a computational implementation plan from a specified inquiry. Translates the evidence-driven model into concrete pipeline steps with tools, configs, tests, and validation criteria. Use when the user wants to implement a model, build a pipeline, operationalize an inquiry, or make something computational. Also use when the user says "plan pipeline", "implement this", "build the pipeline", or "make this executable".
---

# Plan Pipeline from Inquiry

> **Prerequisites:**
> - Load the `knowledge-graph` skill for ontology reference
> - Load the `research-methodology` skill for evidence standards

## Overview

This command takes a specified inquiry and generates a concrete computational implementation plan. It adds `sci:Transformation` nodes to the inquiry subgraph, attaches tools and parameters, creates validation criteria, and writes an implementation plan document.

The plan bridges the evidence-driven model and code. Every transformation traces back through the inquiry to the data and assumptions that justify it.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to `uv run science-tool <command>` when executing.** See command-preamble step 8 for fallback if science-tool is not a project dependency.

## Rules

- **MUST** start from a specified inquiry or a task/question description (see Input Modes below)
- **MUST** write the plan to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md`
- **SHOULD** add `sci:Transformation` nodes when the project uses formal inquiries
- **SHOULD** connect transformations with `sci:feedsInto` edges
- **SHOULD** attach `sci:validatedBy` checks to each transformation
- **SHOULD** include AnnotatedParam metadata for all pipeline parameters
- **SHOULD** reference tool-specific skills where applicable
- **SHOULD** suggest a pilot/phased approach for complex pipelines
- **MUST NOT** embed tool-specific logic (Snakemake rules, etc.) — reference skills instead

## Input Modes

The plan-pipeline command works with two types of input:

- **Inquiry mode** (default when an inquiry slug is provided): Load the formal inquiry subgraph and translate it into a pipeline plan. Follow Steps 1, 3, and 5 for inquiry loading, graph annotation, and status updates.
- **Task mode** (when the project uses tasks/questions instead of formal inquiries, or when `$ARGUMENTS` is a task ID or description): Derive the plan directly from the task description, existing code, and project context. Skip inquiry-specific steps (1, 3, 5) — the plan document is the primary deliverable. Graph annotations are secondary.

## Workflow

### Step 1: Load and verify the inquiry (Inquiry mode only)

Skip this step in Task mode — proceed directly to Step 2.

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Verify status is `specified`. If it's `sketch`, warn the user and suggest `/science:specify-model` first.

If status is `specified` but not `critiqued`, warn: "This inquiry hasn't been through critique yet. Consider running `/science:critique-approach <slug>` first. Proceeding anyway."

**Fallback:** If `science-tool inquiry show` fails or times out, read the inquiry document directly from `doc/inquiries/<slug>.md`.

### Step 2: Identify computational requirements

Walk the inquiry subgraph and identify:

**Data acquisition steps** — for each `BoundaryIn` node:
- How is this data obtained? (Download, query, extract from reference)
- What format is it in? What format does it need to be in?
- Are there preprocessing steps?

**Transformation steps** — for each interior edge:
- What computation does this edge imply?
- What tool/library performs it?
- What are the input/output formats?
- What parameters does it need?

**Output steps** — for each `BoundaryOut` node:
- What format should the output be in?
- How is it validated?
- What does "success" look like?

### Step 3: Add computational nodes to the inquiry (Inquiry mode only)

Skip this step in Task mode — the plan document captures the same information.

For each identified step:

```bash
# Add transformation to knowledge graph and inquiry
science-tool graph add concept "<step name>" --type sci:Transformation \
  --note "<what this step does>"

science-tool inquiry add-node "<slug>" "concept:<step>" --role BoundaryIn
# or no --role for interior nodes (just add edges)

# Connect in the data flow
science-tool inquiry add-edge "<slug>" "concept:<input>" "sci:feedsInto" "concept:<step>"
science-tool inquiry add-edge "<slug>" "concept:<step>" "sci:produces" "concept:<output>"

# Add validation criterion
science-tool graph add concept "<check name>" --type sci:ValidationCheck \
  --note "<what to check>"
science-tool inquiry add-edge "<slug>" "concept:<step>" "sci:validatedBy" "concept:<check>"
```

### Step 4: Write the implementation plan

Save to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md` using the standard plan format:

```markdown
# <Inquiry Label> Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** <derived from inquiry target and description>

**Architecture:** <derived from transformation graph>

**Tech Stack:** <tools identified in steps 2-3>

**Inquiry:** `<slug>` — see `doc/inquiries/<slug>.md` and knowledge graph

---

## Task N: <Transformation step>
...
```

Each task should reference the inquiry node it implements and include TDD steps.

### Step 5: Update inquiry status and finalize (Inquiry mode only)

Skip this step in Task mode.

Update the inquiry status to `planned`. Regenerate `doc/inquiries/<slug>.md`.

```bash
science-tool graph stamp-revision
```

### Step 6: Suggest next steps

1. **Track plan tasks:** For each task in the plan that doesn't have a corresponding entry in `tasks/active.md`, offer to create one via `science-tool tasks add`. Implementation tasks buried in plan docs should be surfaced as trackable tasks.
2. If no pre-registration exists for the target hypothesis, suggest: `/science:pre-register` — to formalize expectations before running the analysis
3. `/science:review-pipeline <slug>` — get critical review before implementation
4. Execute the plan using `superpowers:executing-plans`
5. `/science:discuss` — discuss specific aspects of the plan

## Important Notes

- **Plans are tool-agnostic by default.** Reference tool-specific skills rather than embedding their conventions.
- **Pilot first.** For complex pipelines, suggest a pilot phase with reduced scope.
- **Validation criteria are mandatory.** Every transformation must have a way to verify it worked.
- **The inquiry is the source of truth.** The plan document is a rendering of the inquiry's computational layer.
- **When science-tool is unavailable:** If `science-tool` commands fail or time out (>15s), proceed with the plan document directly. Read inquiry and graph data from markdown files in `doc/inquiries/` instead. Graph annotations are secondary — the plan document is the primary deliverable. Note which graph commands were skipped so they can be run later.

## Process Reflection

Reflect on the **pipeline planning workflow** and the **task decomposition** process.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — plan-pipeline

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
- Be concrete and specific, not generic ("QA checkpoints were hard to define without knowing the data schema" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

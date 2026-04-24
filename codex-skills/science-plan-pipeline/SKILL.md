---
name: science-plan-pipeline
description: "Generate a computational implementation plan from an inquiry — pipeline steps, tools, configs, tests, and validation criteria. Use when the user wants to implement a model, build a pipeline, or make an inquiry executable."
---

# Plan Pipeline from Inquiry

Converted from Claude command `/science:plan-pipeline`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

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
- **SHOULD** suggest the RunPod pipeline skill as an option when the planned workflow appears GPU-intensive; keep this advisory and let the user decide whether to use it
- **SHOULD** keep plans tool-agnostic by default — reference tool-specific skills. However, when the user explicitly requests a specific orchestration tool (Snakemake, Nextflow, Make, etc.), include a tool-specific section with the workflow definition while keeping the rest of the plan tool-agnostic.

## Input Modes

The plan-pipeline command works with two types of input:

- **Inquiry mode** (default when an inquiry slug is provided): Load the formal inquiry subgraph and translate it into a pipeline plan. Follow Steps 1, 3, and 5 for inquiry loading, graph annotation, and status updates.
- **Task mode** (when the project uses tasks/questions instead of formal inquiries, or when the user input is a task ID or description): Derive the plan directly from the task description, existing code, and project context. Skip inquiry-specific steps (1, 3, 5) — the plan document is the primary deliverable. Graph annotations are secondary.

## Workflow

### Step 1: Load and verify the inquiry (Inquiry mode only)

Skip this step in Task mode — proceed directly to Step 2.

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Verify status is `specified`. If it's `sketch`, warn the user and suggest `science-specify-model` first.

If status is `specified` but not `critiqued`, warn: "This inquiry hasn't been through critique yet. Consider running `science-critique-approach <slug>` first. Proceeding anyway."

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

### Step 2a: Consider rented GPU execution when the workload looks GPU-intensive

Before continuing, check whether the planned workflow appears likely to need substantial GPU execution. Common signals include:

- explicit GPU / CUDA / remote pod / RunPod mentions
- large embedding generation or model inference workloads
- model training or fine-tuning steps
- dependency or runtime requirements that clearly imply GPU hardware

If those signals are present, tell the user that Science has a RunPod skill at `skills/pipelines/runpod.md` for rented GPU pod workflows, and ask whether they want to consider that path before finalizing the plan.

If the user says yes:

- read `skills/pipelines/runpod.md`
- reference `templates/runpod/push_to_runpod.sh`, `templates/runpod/setup.sh`, and `templates/runpod/run.sh` where relevant
- incorporate that guidance into the planning discussion or plan document

If the user says no, continue with the normal planning flow.

### Step 2b: Data-access gate (both modes)

For each input data source identified in Step 2:

1. Resolve to a `dataset:<slug>` entity. If no entity exists:
   - For external sources: invoke `science-find-datasets`. Do not proceed
     with a URL alone.
   - For derived sources: HALT with "no dataset entity found for `dataset:<slug>`;
     ensure the producing workflow has an `outputs:` block and run
     `science-tool dataset register-run <run-slug>`."
2. Check the gate per origin:
   - `origin: external`:
     - PASS if `access.verified: true`.
     - PASS if `access.verified: false` AND `access.exception.mode != ""`.
     - HALT otherwise with Branch A/B options:
       - **Branch A** — verifiable under current credentials → run verification
         (manual or future `science-tool dataset verify`), then re-run this step.
       - **Branch B** — requires credentials the project does not hold.
         Three sub-options:
         (a) **scope-reduce**: defer to a follow-up task; populate
             `access.exception` with `mode: "scope-reduced"`, `decision_date`,
             `followup_task`.
         (b) **expand**: add credential acquisition to the current task; populate
             `access.exception` with `mode: "expanded-to-acquire"`, `decision_date`.
         (c) **substitute**: pick an alternative dataset; populate
             `access.exception` with `mode: "substituted"`,
             `superseded_by_dataset: "dataset:<alternative>"`.
       After writing the structured exception + a prose log entry, re-run the gate.
   - `origin: derived`:
     - Check `derivation.workflow_run` resolves to a `workflow-run` entity. HALT if not.
     - Check that the workflow-run's `produces:` includes this dataset's ID. HALT if asymmetric.
     - Recursively check each ID in `derivation.inputs` passes the gate. HALT with the
       broken-link path if any input transitively fails. Cycle detection: maintain a
       visited-set; HALT on revisit.
3. Do NOT mutate `consumed_by` here. Backlink write is Step 4.5.

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

#### Register Workflow Entity

If this plan creates a new pipeline (not extending an existing one), register
a `workflow` entity:

1. Create `doc/workflows/workflow-<slug>.md` using the `workflow.md` template
2. Link to the method it realizes: `sci:realizes` → `method:<slug>`
3. Document the steps it contains: `sci:contains` → `workflow-step:<slug>` for each rule

### Step 4: Write the implementation plan

Save to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md` using the standard plan format:

```markdown
# <Inquiry Label> Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** <derived from inquiry target and description>

**Architecture:** <derived from transformation graph>

**New Dependencies:** <libraries, tools, or data sources not already in the project>

**Inquiry:** `<slug>` — see `doc/inquiries/<slug>.md` and knowledge graph

---

## Task N: <Transformation step>
...
```

#### Conditional Plan Sections

Include these sections when applicable:

- **Changes to Existing Code** (Task mode / extend-existing-workflow plans): Which existing files are modified and why? What's the diff from the current working pipeline? Omit when building from scratch.
- **Decision Criteria** (exploratory/research plans): What would change our mind about pursuing this? What result at what stage would make us stop or pivot? This is a top-level go/no-go, distinct from per-task validation criteria. Omit for straightforward implementation plans.
- **Reusable Infrastructure:** If any task produces infrastructure (tools, indices, data pipelines) with value beyond this specific analysis, flag it with `reusable: true` and briefly describe the broader applicability.

Each task should reference the inquiry node it implements and include TDD steps.

### Step 4.5: Register plan with consumed datasets (both modes)

The plan file now exists at a known path. Compute `plan:<plan-file-stem>` from the
filename (strip directory and `.md` extension).

For each dataset entity referenced in Step 2b, append `plan:<plan-file-stem>` to
`consumed_by`, deduplicated against existing entries. Also append any secondary
backlinks the planner has in scope (`task:<id>` if a task is being tracked;
`workflow:<slug>` if a new workflow is being registered). Do not rewrite existing
entries.

Append a short log entry to each dataset entity's verification log:

> "<YYYY-MM-DD> (<agent>): consumed by plan:<plan-file-stem>"

### Step 5: Update inquiry status and finalize (Inquiry mode only)

Skip this step in Task mode.

Update the inquiry status to `planned`. Regenerate `doc/inquiries/<slug>.md`.

```bash
science-tool graph stamp-revision
```

### Step 6: Suggest next steps

1. **Track plan tasks:** For each task in the plan that doesn't have a corresponding entry in `tasks/active.md`, offer to create one via `science-tool tasks add`. Implementation tasks buried in plan docs should be surfaced as trackable tasks.
2. If no pre-registration exists for the target hypothesis, suggest: `science-pre-register` — to formalize expectations before running the analysis
3. `science-review-pipeline <slug>` — get critical review before implementation
4. Execute the plan using `superpowers:executing-plans`
5. `science-discuss` — discuss specific aspects of the plan

## Important Notes

- **Plans are tool-agnostic by default.** Reference tool-specific skills rather than embedding their conventions. Exception: when the user explicitly requests a specific tool, include a dedicated tool-specific section.
- **RunPod is advisory, not automatic.** For GPU-intensive workflows, suggest the RunPod skill and let the user choose whether to incorporate it.
- **Pilot first.** For complex pipelines, suggest a pilot phase with reduced scope.
- **Validation criteria are mandatory.** Every transformation must have a way to verify it worked.
- **The inquiry is the source of truth.** The plan document is a rendering of the inquiry's computational layer.
- **When science-tool is unavailable:** If `science-tool` commands fail or time out (>15s), proceed with the plan document directly. Read inquiry and graph data from markdown files in `doc/inquiries/` instead. Graph annotations are secondary — the plan document is the primary deliverable. Note which graph commands were skipped so they can be run later.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:plan-pipeline" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead

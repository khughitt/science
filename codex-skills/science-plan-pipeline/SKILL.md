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
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

> **Prerequisites:**
> - Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics
> - Load the `science-research-methodology` Codex skill for evidence standards

## Overview

This command takes a specified inquiry and generates a concrete computational implementation plan. It adds `sci:Transformation` nodes to the inquiry subgraph, attaches tools and parameters, creates validation criteria, and writes an implementation plan document.

The plan bridges the evidence-driven model and code. Every transformation traces back through the inquiry to the data and assumptions that justify it.

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, the examples below write just `science <command>` — **always expand to `uv run science <command>` when executing.** See command-preamble step 8 for fallback if science is not a project dependency.

## Rules

- **MUST** start from a specified inquiry or a task/question description (see Input Modes below)
- **MUST** pick a plan mode (`probe` / `design` / `implementation`, see Plan Modes below) and let it dictate plan shape and section list. Right-size aggressively — over-spec'd 1-day probes are the most common drift.
- **MUST** write the plan to the project's plan filename convention. Do not blindly use `YYYY-MM-DD-<slug>` in projects whose `entities/plans/` use numeric `NNNN-` stems; in those projects, use `entities/plans/<NNNN>-<slug>.md` with the next unused sequence number. Date-prefixed plans are only appropriate when the project already uses date-prefixed plan entity stems.
- **MUST** check whether methodological readiness is already documented by an analysis-plan file under `entities/plans/*-analysis-plan.md` (a `type: plan` entity with `plan_kind: analysis-plan`, referenced as `plan:<stem>`). If not, and the user is asking for orchestration before data QA, independent unit, estimand, power/resolution, and sensitivity rules are clear, recommend `science-plan-analysis` before finalizing the pipeline plan.
- **SHOULD** include frontmatter linking the plan to its hypotheses / questions / decisions / tasks via `related: [hypothesis:..., rq:..., decision:..., plan:..., task:..., paper:...]`. For pure upstream design notes (in the science repo itself), a `Parent design / Predecessor / Status / Depends on` header block is an acceptable alternative to frontmatter.
- **SHOULD** in `design` mode, defend non-obvious choices in named `Key decision` subsections that name the rejected alternative — this replaces the older per-transformation Risks block.
- **SHOULD** add `sci:Transformation` graph nodes ONLY when the project uses formal inquiries (Step 3 below). Skip in `design` / `implementation` modes — the plan document is the canonical artifact and graph annotations are not load-bearing.
- **SHOULD** reference tool-specific skills where applicable
- **SHOULD** suggest a pilot/phased approach for complex pipelines (typically a `probe` precursor to a `design`)
- **SHOULD** suggest the RunPod pipeline skill as an option when the planned workflow appears GPU-intensive; keep this advisory and let the user decide whether to use it
- **SHOULD** keep plans tool-agnostic by default — reference tool-specific skills. However, when the user explicitly requests a specific orchestration tool (Snakemake, Nextflow, Make, etc.), include a tool-specific section with the workflow definition while keeping the rest of the plan tool-agnostic.

## Input Modes

The plan-pipeline command works with two types of input:

- **Inquiry mode** (default when an inquiry slug is provided): Load the formal inquiry subgraph and translate it into a pipeline plan. Follow Steps 1, 3, and 5 for inquiry loading, graph annotation, and status updates.
- **Task mode** (when the project uses tasks/questions instead of formal inquiries, or when the user input is a task ID or description): Derive the plan directly from the task description, existing code, and project context. Skip inquiry-specific steps (1, 3, 5) — the plan document is the primary deliverable. Graph annotations are secondary.

When an existing analysis plan is in scope, read `entities/plans/*-analysis-plan.md`
and reuse its methodological readiness checks. Reference it as `plan:<stem>`, not
`analysis-plan:<slug>`; `analysis-plan` is a plan kind, not a registered entity
kind. Do not re-decide those checks in the pipeline plan; focus on execution.

## Plan Modes

Orthogonal to input mode (above), the plan **shape** must match scope. Three shapes recur across recent Science plans; pick one before drafting. When in doubt, default to `probe` and grow only when scope demands it.

- **`probe` mode** — 1-page, 1-day experiments. Sections: `Goal` / `Background` / `Approach` / `Inputs` / `Tasks` (≤5) / `Decision criteria` (top-level go/no-go) / `Validation` (summary, not per-step) / `Out of scope` / `Notes on plan scope` (closing sentence documenting why this plan is this size). No Phase structure, no per-step validation tables, no testing matrix.
- **`design` mode** — engineering or strategic design, 5–15pp. Sections: `Purpose` / `Scope decomposition` (when splitting from a parent plan) / `Architecture` (inline ASCII directory/code-layout tree with `NEW`/`MODIFY`/`UNCHANGED` annotations — this is the canonical architecture-diagram primitive; do not scaffold SVG/Mermaid) / **`Key decisions`** (one named subsection per non-obvious choice; each names the chosen approach AND the rejected alternative with a one-sentence reason — this carries the weight a "Risks" section would in older templates) / `Phases` or `Work Packages` (each with `Depends on` / `Entry point` / `Definition of done`) / `Open questions` / `Non-Goals` / `Acceptance Criteria`. Pure upstream design notes may use a `Parent design / Predecessor / Status / Depends on` header block instead of frontmatter.
- **`implementation` mode** — companion to a settled design, 5–15pp. Sections: `Goal` / `Architecture` (link to parent design) / `File Structure` (enumerate modify/create with one-line intent) / `Task N → Step N` checkboxes with inline shell commands and expected outputs / Final validation task / Self-review checklist. This is the executable mode — one commit per task is the norm.

Validation lives differently per mode: `probe` → single `Decision criteria` + `Validation` summary; `design` → per-WP `Definition of done` + closing `Acceptance Criteria`; `implementation` → per-task checkbox steps with inline commands. **Do not emit per-transformation validation matrices** — they duplicate effort across modes.

## Workflow

### Step 1: Load and verify the inquiry (Inquiry mode only)

Skip this step in Task mode — proceed directly to Step 2.

```bash
science inquiry show "<slug>" --format table
science inquiry validate "<slug>" --format json
```

Verify status is `specified`. If it's `sketch`, warn the user and suggest `science-specify-model` first.

If status is `specified` but not `critiqued`, warn: "This inquiry hasn't been through critique yet. Consider running `science-critique-approach <slug>` first. Proceeding anyway."

**Fallback:** If `science inquiry show` fails or times out, read the graph-backed inquiry source directly from `entities/patches/<slug>.md`. If the project only has `entities/inquiries/<slug>.md`, treat it as prose context rather than a compiled inquiry source.

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

**Scale & resource behavior** — for any step that ingests real-world, heterogeneous, or externally-sourced input:
- What is the expected peak memory and wall-clock on *real* data, not the small fixtures used in tests? Heterogeneous real input — one pathological record, a super-linear parser — can inflate resource use by orders of magnitude even when the logic is correct.
- Plan an explicit scale/resource validation task (carried in the plan templates below): the pipeline is not "done" until it has run on a scale-representative slice (or the full corpus) with peak memory and wall-clock observed.

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
     `science dataset register-run <run-slug>`."
2. Check the gate per origin:
   - `origin: external`:
     - PASS if `access.verified: true`.
     - PASS if `access.verified: false` AND `access.exception.mode != ""`.
     - DEFER, without treating the plan as data-ready, if the dataset is public
       or registration-only and Work Package 1 is explicitly "retrieve and
       verify this dataset". In that case WP1 must end by setting
       `access.verified: true` plus enum-safe `verification_method` and
       `last_reviewed`; all downstream work packages depend on WP1 and must not
       consume the dataset before the gate is rerun.
     - For `access.level: mixed` with public-slice consumption, PASS/DEFER only for the named public slice.
       The plan must name the public artefact, table, cohort, endpoint, or sibling dataset it consumes and state
       that controlled or commercial siblings remain out of scope. HALT if the plan would consume any restricted sibling,
       or if the public slice is not distinguishable enough to verify independently.
     - HALT otherwise with Branch A/B options:
       - **Branch A** — verifiable under current credentials → run verification
         (manual or future `science dataset verify`), then re-run this step.
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

### Step 3: Add computational nodes to the inquiry (Inquiry mode only, optional)

Skip this step in Task mode — the plan document is the canonical artifact. Also skip in `design` / `implementation` plan modes regardless of input mode — graph annotations on every transformation are not load-bearing in those shapes and add ceremony without payoff.

Run only when (a) input mode is Inquiry, AND (b) the inquiry's downstream tooling (e.g. `science inquiry diagram`) actually consumes these nodes.

For each identified step, edit the source file at `entities/patches/<slug>.md`.
Add transformation records under `inquiry.transformations` and connect them with
`flow_edges`. Then run `science graph build` and re-run `science inquiry
validate`.

```yaml
inquiry:
  transformations:
    - ref: "transformation:<step>"
      tool: "<tool>"
      validated_by: "concept:<check>"
      params:
        - value: "<value>"
          source: "<literature|empirical|design_decision>"
          ref: "<source-ref>"
          note: "<why this parameter is justified>"
  flow_edges:
    - subject: "dataset:<input>"
      predicate: feedsInto
      object: "transformation:<step>"
      claim_refs: []
    - subject: "transformation:<step>"
      predicate: produces
      object: "dataset:<output>"
      claim_refs: []
```

#### Register Workflow Entity

If this plan creates a new pipeline (not extending an existing one), register
a `workflow` entity:

1. Create `entities/workflows/<slug>.md` (filename follows the entity id `workflow:<slug>`) using the `workflow.md` template
2. Link to the method it realizes: `sci:realizes` → `method:<slug>`
3. Document the steps it contains: `sci:contains` → `workflow-step:<slug>` for each rule

### Step 4: Write the plan

Save to the project-appropriate plan path: `entities/plans/<NNNN>-<slug>.md` for numeric-plan projects, or `entities/plans/YYYY-MM-DD-<slug>.md` for date-stem projects. Check existing `entities/plans/` filenames before writing; a validator that treats the leading number as the plan number will see every date-stemmed 2026 plan as duplicate `2026`. The plan shape is dictated by the chosen mode (see Plan Modes above). The frontmatter is the same across modes.

**Frontmatter (project-level plans):**

```yaml
---
id: "plan:<stem>"
type: "plan"
title: "<short title>"
status: "active"   # active | draft | merged | archived
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
related:
  - "hypothesis:<id>"   # if any
  - "rq:<id>"           # if any
  - "decision:<id>"     # if any
  - "plan:<id>"         # parent or sibling plan
  - "task:<id>"         # if filed
  - "paper:<id>"        # if any
---
```

Pure upstream design notes (in the science repo itself) may use a header block instead:

```markdown
**Parent design:** `<path or ref>`
**Predecessor:** `<path or ref>`
**Status:** Draft | Active | Merged
**Depends on:** `<list>`
```

**Body shape by mode:**

#### `probe` mode (1-page, 1-day experiments)

```markdown
# <Title>

## Goal
1-2 sentences.

## Background
What we know, what we are testing, why now. 1 paragraph.

## Approach
Method in 1-3 paragraphs.

## Inputs
Bullet list of data sources / prior probes / existing scripts.

## Tasks
Numbered ≤5 tasks, each 1-3 sentences. No checkbox sub-steps.

## Decision criteria
What result moves us in which direction (top-level go/no-go).

## Validation
Sanity checks (≤5 bullets). Not a per-task matrix.

## Out of scope
What we are NOT doing in this probe.

## Notes on plan scope
1-2 sentences documenting why this plan is this size (so future readers / agents don't re-expand it).
```

#### `design` mode (engineering or strategic, 5–15pp)

```markdown
# <Title>

## Purpose
Goal + guiding principle. 1-2 paragraphs.

## Scope decomposition (when splitting from a parent plan)
In scope / Out of scope (deferred) — bullets with reason per deferred item.

## Architecture
Inline ASCII directory/code-layout tree with NEW / MODIFY / UNCHANGED annotations.

## Key decisions
### Key decision N: <name>
- **Chosen approach:** ...
- **Rejected alternative:** ...
- **Reason:** one sentence.

(One subsection per non-obvious choice. This replaces a per-transformation Risks block.)

## Phases / Work Packages
### Phase N / WP N: <name>
- **Depends on:** ...
- **Entry point:** ...
- **Definition of done:** ...

## Open questions
Bullets.

## Non-Goals
Bullets.

## Acceptance Criteria
Closing checklist.
```

#### `implementation` mode (companion to a settled design)

```markdown
# <Title>

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task. One commit per task.

## Goal
1-2 sentences.

## Architecture
Reference parent design. 1 paragraph + link.

## File structure
Enumerate every file to modify / create with a one-line intent.

## Task N: <name>
- [ ] Step N.1: <action> — `<shell command>` — expected output: ...
- [ ] Step N.2: ...

## Final validation task
- [ ] Run test suite / smoke / linter.
- [ ] **Scale/resource run on real data** (for pipelines ingesting real heterogeneous input): execute on a scale-representative slice or the full corpus, observing peak memory + wall-clock. Fixtures validate logic, not resource behavior — do not declare done on green fixtures alone.
- [ ] Manual UI check (if applicable).
- [ ] Commit.

## Self-review checklist
Before declaring done: ...
```

#### Conditional Plan Sections (any mode)

Add when applicable:

- **Changes to Existing Code** (task-mode / extend-existing-workflow): which existing files are modified and why? Omit when building from scratch.
- **Reusable Infrastructure:** If any task produces infrastructure (tools, indices, data pipelines) with value beyond this specific analysis, flag it with `reusable: true` and briefly describe the broader applicability.

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

Update `inquiry.status` to `planned` in `entities/patches/<slug>.md`, then rebuild.

```bash
science graph build
science graph stamp-revision
```

### Step 6: Suggest next steps

1. **Track plan tasks:** For each task in the plan that doesn't have a corresponding entry in `tasks/active.md`, offer to create one via `science tasks add`. Implementation tasks buried in plan docs should be surfaced as trackable tasks.
2. If no pre-registration exists for the target hypothesis, suggest: `science-pre-register` — to formalize expectations before running the analysis
3. `science-review-pipeline <slug>` — get critical review before implementation
4. Execute the plan using `superpowers:executing-plans`
5. `science-discuss` — discuss specific aspects of the plan

## Important Notes

- **Plans are tool-agnostic by default.** Reference tool-specific skills rather than embedding their conventions. Exception: when the user explicitly requests a specific tool, include a dedicated tool-specific section.
- **RunPod is advisory, not automatic.** For GPU-intensive workflows, suggest the RunPod skill and let the user choose whether to incorporate it.
- **Pilot first.** For complex pipelines, suggest a `probe`-mode precursor before a `design`-mode plan.
- **Validation is mode-specific, not per-transformation.** `probe` plans carry a single `Decision criteria` block + `Validation` summary; `design` plans carry per-WP `Definition of done` plus closing `Acceptance Criteria`; `implementation` plans carry per-task checkbox steps with inline commands. Do not emit per-transformation validation matrices.
- **Fixtures validate logic, not scale.** "Reviewed + tests green" is not "validated against real data." Any pipeline that ingests real-world, heterogeneous, or externally-sourced input needs an explicit scale/resource validation task — a run on a representative slice or the full corpus, watching peak memory and wall-clock — *before* it is considered complete, not deferred entirely to the production run.
- **The plan document is the canonical artifact.** Inquiry-graph annotations (Step 3) are optional and only meaningful when downstream tooling consumes them; they are not the source of truth for the plan.
- **When science is unavailable:** If `science` commands fail or time out (>15s), proceed with the plan document directly. Read inquiry source from `entities/patches/` when present, or prose context from `entities/inquiries/` for legacy projects. Graph annotations are secondary — the plan document is the primary deliverable. Note which graph commands were skipped so they can be run later.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
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

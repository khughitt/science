---
name: science-sketch-model
description: "Sketch a research model interactively as an inquiry subgraph — variables, relationships, data sources, and unknowns. Use when exploring what variables matter, how they connect, or how to approach a causal question (DAG, confounders, treatment effect)."
---

# Sketch a Research Model

Converted from Claude command `/science:sketch-model`.

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
> - Read `docs/proposition-and-evidence-model.md` and `docs/specs/2026-03-01-knowledge-graph-design.md` for ontology reference before starting.
> - If causal mode is active: also read `references/dag-two-axis-evidence-model.md` and `docs/specs/2026-03-07-phase4b-causal-dag-design.md`.

## Overview

This command helps the user sketch the shape of an investigation: what variables matter, how they might connect, what data exists, and what remains unknown.

At sketch time:
- uncertainty is expected
- missing provenance is acceptable
- edges are tentative
- candidate `relation_claim`s are more important than polished formalism

The output is an inquiry subgraph plus a rough set of candidate claims that can later be formalized with `science-specify-model`.

## Causal Mode Detection

Switch to causal mode when any of the following are true:

1. The `causal-modeling` aspect is active in `science.yaml`
2. User language signals causal intent: "causal", "DAG", "confounders", "treatment effect", "what causes", "intervention"
3. Existing causal inquiries already exist in the project

When causal mode is active:
- create the inquiry with `--type causal`
- use `scic:causes` and `scic:confounds` as tentative causal structure
- set the estimand with `inquiry set-estimand`
- treat each causal edge as a candidate relation-claim, not an established fact
- ask what evidence would support or dispute each proposed causal edge

When causal mode is not active:
- use `sci:feedsInto` for flow or processing structure
- use loose associations only when the relationship is not yet clear
- keep the sketch lightweight and incomplete where needed

## Tool Invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

## Rules

- **MUST** initialize the graph if it does not exist (`science-tool graph init`)
- **MUST** create the inquiry before adding nodes or edges (`science-tool inquiry init`)
- **MUST** add entities to the knowledge graph and to the inquiry
- **SHOULD** name candidate `relation_claim`s explicitly in notes or prose when the user proposes a real scientific relationship
- **MUST NOT** treat sketch edges as validated
- **MUST NOT** require provenance or confidence at this stage
- **SHOULD** use `sci:Unknown` nodes to make uncertainty visible rather than hiding it in prose

## Workflow

### Step 1: Gather Context

Read these project files if they exist:
- `specs/research-question.md`
- `specs/hypotheses/`
- `doc/questions/`
- `knowledge/graph.trig`
- `doc/inquiries/`

If no graph exists:

```bash
science-tool graph init
```

### Step 2: Interactive Conversation

Have a natural, adaptive conversation.

1. **Target**
   - What question, hypothesis, or inquiry is this sketch meant to address?

2. **Variables**
   - What can be observed directly?
   - What is latent, inferred, or computed?
   - What datasets or assays touch these variables?
   - Which variables are only available through proxies and will later need `measurement_model`?

3. **Candidate Relations**
   - What seems related to what?
   - Which of these are merely associative, and which are candidate causal claims?
   - Where is the user confident, and where are they mostly guessing?

4. **Evidence Outlook**
   - What would count as literature support?
   - What empirical-data evidence would matter most?
   - Are any proposed edges especially fragile because they rest on one idea or one source?

5. **Unknowns**
   - What variables, confounders, or mechanisms are missing?
   - Where should `sci:Unknown` nodes be used?

If causal mode is active, also ask:
- What is the treatment?
- What is the outcome?
- What variables might confound both?
- Which causal arrows are most uncertain?

If the sketch is mostly formal or architectural rather than empirical, say so explicitly and treat the key propositions as likely `structural_claim`s rather than as causal or mechanistic claims.

### Step 3: Build the Inquiry Subgraph

1. **Create the inquiry**

```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>"
```

If causal mode:

```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --type causal
```

2. **Add entities to the knowledge graph**

```bash
science-tool graph add concept "<variable name>" --type sci:Variable
science-tool graph add concept "<unknown factor>" --type sci:Unknown
```

3. **Add nodes to the inquiry**

```bash
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryIn
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryOut
```

4. **Add tentative edges**

For flow or processing structure:

```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "sci:feedsInto" "concept:<to>"
```

For candidate causal structure:

```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "scic:causes" "concept:<to>"
```

Do not imply that this edge is proven.
Instead, record in the inquiry summary which candidate `relation_claim`s likely need to be formalized next.

5. **Set the estimand when relevant**

```bash
science-tool inquiry set-estimand "<slug>" --treatment "concept/<treatment>" --outcome "concept/<outcome>"
```

### Step 4: Visualize And Summarize

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Save the inquiry document to `doc/inquiries/<slug>.md`.

The summary should explicitly note:
- tentative relation-claims
- unresolved unknowns
- which parts are structurally useful but epistemically weak
- where `supports_scope` should later widen review output, while still remaining only a hint rather than a graph override

### Step 5: Finalize

```bash
science-tool graph stamp-revision
```

Suggest next steps:
1. `science-specify-model <slug>` to formalize claims and attach evidence
2. `science-critique-approach <slug>` if causal structure needs skeptical review
3. `science-add-hypothesis` if the sketch revealed a new organizing conjecture
4. `science-research-topic` or `science-search-literature` if the main gap is background evidence

## Important Notes

- A good sketch makes uncertainty explicit.
- A candidate edge is not a validated edge.
- Multiple sketches are fine; they are research tools, not final statements of truth.
- Prefer a small number of meaningful variables and candidate claims over a bloated diagram.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:sketch-model" \
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

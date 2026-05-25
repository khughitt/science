---
name: science-specify-model
description: "Formalize a research model with explicit claims, evidence provenance, and residual uncertainty. Use when the user wants to make a sketch rigorous, attach support/dispute to candidate relations, resolve unknowns, or formalize assumptions."
---

# Specify a Research Model

Converted from Claude command `/science:specify-model`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

> **Prerequisite:** Read `docs/proposition-and-evidence-model.md` and `docs/specs/2026-03-01-knowledge-graph-design.md` for ontology reference before starting.

## Overview

This command takes an inquiry from sketch to specified status.

In the skeptical model:
- variables get formal types
- non-trivial scientific relations become explicit `proposition` records, preferably with subject-predicate-object structure
- evidence lines update those propositions via support/dispute
- uncertainty remains explicit unless the evidence base is genuinely strong

The goal is not to convert every edge into a fact. The goal is to convert vague structure into explicit, reviewable propositions with provenance.

## Tool Invocation

All `science` commands below use:

```bash
uv run science <command>
```

## Rules

- **MUST** read the existing inquiry before modifying it
- **MUST** assign formal types to all important variables
- **MUST** identify which inquiry edges are structural only and which represent uncertain scientific claims
- **MUST** represent uncertain scientific relations as `proposition` entities
- **MUST** attach provenance to authored propositions and evidence lines
- **MUST** keep residual uncertainty visible when support is sparse, contested, or low-quality
- **MUST** run `inquiry validate` after specifying
- **SHOULD** identify confounders for directional or causal claims
- **SHOULD** ask what would materially change belief in each key claim

## Workflow

### Step 1: Load And Assess The Inquiry

If the user input contains a slug:

```bash
science inquiry show "<slug>" --format table
science inquiry validate "<slug>" --format json
```

Identify:
- variables lacking proper types
- vague edges that should become explicit claims
- unresolved unknowns
- unsupported causal assumptions
- places where the inquiry is structurally useful but epistemically fragile

If no slug is provided, ask which inquiry to specify.

### Step 2: Specify Variables

For each important variable:

1. **Type**
   - What kind of thing is this?
   - Use the most specific reasonable type.

2. **Observability**
   - Is this observed, latent, or computed?

3. **Provenance**
   - Where does this variable definition come from?

Use commands like:

```bash
science graph add concept "<name>" --type <CURIE> --definition "<definition>"
```

### Step 3: Convert Scientific Edges Into Explicit Propositions

For each non-trivial scientific relation in the inquiry:

1. Clarify the content of the proposition
   - What exactly is being asserted?
   - Is it `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`?
   - Is the observed evidence direct or proxy-mediated?

2. Create a durable proposition

```bash
science proposition create "<clear proposition title>" \
  --id "proposition:<id>" \
  --source-ref "<ref>"
```

Then fill the proposition file with explicit subject-predicate-object structure in prose and, when useful, frontmatter fields such as:

```yaml
subject: "concept:<subject>"
predicate: "<predicate>"
object: "concept:<object>"
claim_layer: "empirical_regularity|causal_effect|mechanistic_narrative|structural_claim"
```

3. Attach the proposition to the inquiry edge when the edge should remain in the model

```bash
science inquiry add-edge "<slug>" "concept:<subject>" "<predicate>" "concept:<object>" \
  --claim "proposition:<id>"
```

Use direct structural edges without propositions only when the edge is organizational or procedural rather than epistemic.

When the proposition is materially clearer with layered metadata, author it explicitly:
- `claim_layer`
- `identification_strength`
- `proxy_directness`
- `measurement_model`
- `supports_scope` as a review hint only
- `rival_model_packet` using optional `current_working_model`

### Step 4: Attach Support And Dispute

For each important proposition, ask:
- What currently supports it?
- What currently disputes it?
- What evidence is missing?
- Does the support come from one independence group only?
- Is any support actually a proxy that still needs a measurement model?

When the project has concrete supporting or disputing evidence, represent it as evidence-line entities:

```bash
science entity create evidence-line "<supporting or disputing evidence line>" \
  --id "evidence-line:<id>" \
  --source-ref "<ref>" \
  --related "proposition:<target>"
```

Then set `target: "proposition:<target>"`, `stance: "supports"` or `stance: "disputes"`, and fill in strength, method, independence, and caveats.

Do not force a flat verdict when the evidence is mixed or weak.

### Step 5: Resolve Unknowns And Assumptions

For each `sci:Unknown` node:
- resolve it to a real entity
- justify why it remains unknown
- or remove it if it no longer matters

For each assumption:
- note why the model currently relies on it
- note what evidence or analysis would reduce that reliance

### Step 6: Validate And Finalize

```bash
science inquiry validate "<slug>" --format json
```

Update the inquiry status to `specified` only when:
- the model structure is coherent
- the important claims are explicit
- the main evidence links are recorded
- major unknowns are either resolved or intentionally documented

Then:

```bash
science graph stamp-revision
```

### Step 7: Suggest Next Steps

1. `science-interpret-results` when new empirical results should update support/dispute
2. `science-compare-hypotheses` when competing claim bundles need head-to-head evaluation
3. `science-discuss` when a claim remains contested or structurally important but weakly evidenced

## Important Notes

- Specifying a model increases clarity, not certainty.
- A proposition with one weak line of evidence is still fragile.
- The main output of this command is a model whose uncertainty can be inspected, challenged, and improved.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:specify-model" \
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

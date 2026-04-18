---
name: science-compare-hypotheses
description: "Head-to-head evaluation of competing explanations. Use when 2+ hypotheses exist for the same phenomenon and need structured comparison at the proposition level. Also use when the user explicitly asks for `science-compare-hypotheses` or references `/science:compare-hypotheses`."
---

# Compare Hypotheses

Converted from Claude command `/science:compare-hypotheses`.

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

Perform a structured comparison of competing hypotheses from the user input.

The goal is not merely to pick a winner. The goal is to identify:
- which propositions each hypothesis depends on
- which propositions are supported or disputed
- where uncertainty is concentrated
- what evidence would actually shift belief

If no arguments are provided, scan `specs/hypotheses/` and propose a high-value pair.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `docs/proposition-and-evidence-model.md`.
2. Read `.ai/templates/comparison.md` first; if not found, read `templates/comparison.md`.
3. Read relevant hypotheses in `specs/hypotheses/`.
4. Read existing evidence in `doc/topics/`, `doc/papers/`, `doc/interpretations/`, and `doc/discussions/`.

## Workflow

### 1. Summarize Each Hypothesis As A Proposition Bundle

For each hypothesis:
- state the organizing conjecture
- list its key propositions or subpropositions
- identify which propositions are essential versus optional
- note each proposition's layer when it matters: `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`

### 2. Build A Proposition-Centric Evidence Inventory

For each major proposition:
- what supports it?
- what disputes it?
- what is merely suggestive?
- what is missing entirely?

Distinguish:
- literature support
- empirical-data support
- simulation support
- methodological objections

Also distinguish:
- direct observations versus proxy-mediated support that should carry `measurement_model`
- independent support versus support concentrated in one `independence_group`

### 3. Identify Discriminating Propositions And Predictions

Find places where the hypotheses genuinely diverge:
- propositions that cannot both be true as stated
- predictions that would separate them
- edges or mechanisms that would rise or fall differently under new evidence

If the comparison is really among bounded alternative models, represent that explicitly as a rival-model packet and treat `current_working_model` as optional rather than mandatory.

This is the most important section.

### 4. Propose Discriminating Evidence

Identify the most useful next evidence to gather:
- what would be measured
- which proposition it bears on
- how it would update each hypothesis
- whether the likely output is support, dispute, or just uncertainty reduction

Prefer evidence that:
- targets the most central uncertain propositions
- is empirically grounded
- has high discriminatory power

### 5. Assess The Current State

Summarize the comparison in skeptical terms:
- which hypothesis currently has the better-supported proposition bundle
- which one remains more fragile
- where both remain weakly supported
- where the real answer may still be “insufficient evidence”

Use verdict language carefully:
- `better supported`
- `more fragile`
- `contested`
- `insufficiently resolved`

Avoid overstating certainty.

### 6. Consider Synthesis

Ask whether the hypotheses are:
- truly competing
- complementary at different scales or contexts
- different bundles that share some valid propositions and differ only in a few decisive places

## Writing

Follow `.ai/templates/comparison.md` first, then `templates/comparison.md`.
Save to `doc/discussions/comparison-<slug>.md`.

## After Writing

1. Save the comparison document.
2. If discriminating evidence suggests concrete work, offer to create tasks.
3. If the comparison suggests a synthesis hypothesis, suggest `science-add-hypothesis`.
4. Suggest next steps:
   - `science-pre-register`
   - `science-discuss`
   - `science-interpret-results`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:compare-hypotheses" \
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

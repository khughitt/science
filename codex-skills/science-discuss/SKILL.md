---
name: science-discuss
description: "Structured critical discussion for a hypothesis, question, topic, or approach. Supports optional double-blind mode to reduce anchoring bias. Also use when the user explicitly asks for `science-discuss` or references `/science:discuss`."
---

# Discuss

Converted from Claude command `/science:discuss`.

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

Run a structured discussion on the user input.
If no argument is provided, sample a discussion focus from `doc/questions/`, `specs/hypotheses/`, or active tasks in `tasks/active.md`.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `discussant` role prompt.

Additionally:
1. Read `.ai/templates/discussion.md` first; if not found, read `templates/discussion.md`.
2. Read relevant context tied to the chosen focus:
   - `doc/topics/`
   - `specs/hypotheses/`
   - `doc/questions/`
   - `tasks/active.md`

## Discussion Modes

### Standard mode

1. Clarify the focal claim/question.
2. Surface strengths, weaknesses, assumptions, alternatives, confounders, and failure modes in a unified critical analysis. Do NOT create a separate "Alternative Explanations" section — alternatives belong within the critical analysis.
3. Propose concrete follow-up tasks.

If loaded aspects contribute additional discussion guidance (e.g., causal reasoning checks from `causal-modeling`), incorporate that guidance into the critical analysis.

### Q&A mode (automatic)

If the user provides multiple specific questions (e.g., "I have 5 questions about X"), use a Q&A structure instead of the standard template sections:

1. One section per user question, with a focused answer and supporting evidence.
2. A synthesis section at the end that ties the answers together.

This produces clearer output than forcing multiple questions through the generic Critical Analysis / Evidence Needed split. The Q&A structure is used *instead of* the standard sections (Focus / Current Position / Critical Analysis / Evidence Needed), not in addition to them. Still include Prioritized Follow-Ups and Synthesis.

### Double-blind mode (optional)

Use when the user asks for independent reasoning before synthesis.

1. Agree on focus.
2. Agent writes its draft analysis to file before seeing user draft.
3. User writes and shares independent draft.
4. Agent publishes a combined synthesis that compares, challenges, and refines both perspectives.

## Writing Output

Save to `doc/discussions/YYYY-MM-DD-<slug>.md`.

Populate frontmatter fields:
- `id`: `"discussion:YYYY-MM-DD-<slug>"`
- `related`: IDs of the focus entity and any hypotheses, questions, or topics discussed
- `source_refs`: IDs of papers cited during the discussion
- `focus_type` and `focus_ref`: from the user's input or inferred from context
- `mode`: `"standard"` or `"double-blind"` based on the user's choice

Sections:

1. `## Focus`
2. `## Current Position`
3. `## Critical Analysis` (includes alternative explanations and confounders — see template)
4. `## Evidence Needed`
5. `## Prioritized Follow-Ups`
6. `## Synthesis` (include side-by-side summary in double-blind mode)

## After Discussion

1. Add/adjust entries in `doc/questions/` using `.ai/templates/question.md` first, then `templates/question.md`.
2. Offer to create follow-up tasks via `science-tool tasks add` with appropriate priority and related entities.
3. If discussion changes hypothesis wording, update relevant file in `specs/hypotheses/`.
4. **Task reframing check:** Review whether the discussion reframes the meaning of any existing tasks. If a task's purpose or scope has changed, update its description in `tasks/active.md` to reflect the new framing.
5. Commit: `git add -A && git commit -m "doc: discuss <slug> and update priorities"`
6. **Actionable recommendations:** If the discussion produced a concrete, low-cost design change or implementation recommendation (something testable in under an hour), it should be flagged with `[actionable now]` in the Prioritized Follow-Ups table. Offer to implement it immediately rather than creating a task for later. This prevents useful small changes from being buried in discussion documents.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:discuss" \
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

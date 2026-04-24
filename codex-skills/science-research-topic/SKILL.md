---
name: science-research-topic
description: "Research and summarize a scientific topic with project-context linking."
---

# Research a Topic

Converted from Claude command `/science:research-topic`.

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

Write a structured background synthesis on the topic specified by the user.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-topic` slash command directly from the user.)

1. **Pre-dispatch check:** Look at `doc/topics/` for existing coverage of the topic. If a file likely overlaps, ask the user whether to overwrite, skip, or produce a supplementary synthesis. Pass their decision into the subagent prompt.
2. **Dispatch** the `topic-researcher` subagent via the Agent tool:
   - `subagent_type: topic-researcher`
   - `description`: a short identifier for the topic
   - `prompt`: the full the user input plus the overwrite decision, plus any scope narrowing the user has hinted at
3. Do **not** perform the Setup / Research Process / Writing / After Writing steps below yourself — those are the subagent's job and dispatching preserves the cost savings this command exists for.
4. When the subagent reports back, continue at **Orchestrator Post-Dispatch** below.

### If you are the `topic-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Research Process → Writing → After Writing. Then report back per the response contract in your agent definition.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/background-topic.md` first; if not found, read `templates/background-topic.md`.
2. Check `doc/topics/` for existing coverage; ask before overwriting.
3. Check `doc/papers/` for relevant summaries.

## Research Process

1. Start from LLM knowledge and draft core concepts, active debates, and project relevance.
2. Use web search to verify key references and capture recent changes.
3. Do not read PDFs unless user provides a file path.

## Writing

Follow `.ai/templates/background-topic.md` first, then `templates/background-topic.md`, and fill all sections.
Save to `doc/topics/<topic-slug>.md`.

The output should include:

- Key subtopics and how they connect.
- What is well-established vs uncertain.
- Links to existing hypotheses and open questions.
- Suggested follow-up research tasks.

If loaded aspects contribute additional sections (e.g., Tooling & Implementation from `software-development`), include them after the core sections.

## After Writing

1. Add new references to `papers/references.bib` (create with header if missing).
2. Add newly surfaced questions to `doc/questions/` using `.ai/templates/question.md` first, then `templates/question.md`.
3. Commit: `git add -A && git commit -m "doc: research topic <topic>"`

Note: "Offer to create follow-up tasks via `science-tool tasks add`" is intentionally deferred to the orchestrator — it is a user-interactive step and the subagent cannot prompt the user directly.

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review the scope the subagent settled on. If it narrowed too aggressively (or not enough), flag that to the user before moving on.
2. Review suggested follow-up research tasks in the subagent's report. Offer to create them via `science-tool tasks add`, grouping related items where sensible and including the rationale the subagent provided.
3. If the subagent flagged contradictions or open questions that overlap existing hypotheses in `specs/hypotheses/`, make small follow-up edits as a separate commit.
4. Read the written synthesis only if you need its content for downstream reasoning. Otherwise, trust the report.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:research-topic" \
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

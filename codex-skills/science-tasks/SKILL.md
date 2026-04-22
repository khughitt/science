---
name: science-tasks
description: "Manage research and development tasks — add, complete, defer, retire, list, and filter. Use when the user wants to track work items, mark things done, retire outdated tasks, or see what's on the backlog. Also use when the user explicitly asks for `science-tasks` or references `/science:tasks`."
---

# Tasks

Converted from Claude command `/science:tasks`.

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

Manage the project task queue in `tasks/active.md`.
the user input specifies the action (add, done, defer, retire, list, show, summary) and any parameters.

## Setup

Read `tasks/active.md` if it exists. If `tasks/` directory doesn't exist, create it.

## Actions

### No arguments or "list"

Show active tasks sorted by priority (P0 first). Use:

```bash
uv run science-tool tasks list
```

Filter by related entity or group:

```bash
uv run science-tool tasks list --related=concept:lens --group=visualization
```

### "add <description>"

Interactively create a task. Ask the user for:
- **Type:** research or dev
- **Priority:** P0-P3
- **Related entities:** (optional) typed refs for hypotheses, concepts, methods, domain entities, questions, etc. — e.g. hypothesis:h01, concept:protein-folding, method:umap
- **Group:** (optional) single group label for thematic clustering

Then run:

```bash
uv run science-tool tasks add "<title>" --type=<type> --priority=<priority> [--related=<ref>...] [--group=<group>]
```

### "done <task_id>"

Mark a task complete. Optionally ask for a completion note.

```bash
uv run science-tool tasks done <task_id> [--note="<note>"]
```

### "defer <task_id>"

Defer a task. Ask for a reason.

```bash
uv run science-tool tasks defer <task_id> [--reason="<reason>"]
```

### "retire <task_id>"

Close a task that is no longer a priority (not completed, just abandoned). Moves to done/ archive with `retired` status.

```bash
uv run science-tool tasks retire <task_id> [--reason="<reason>"]
```

### "block <task_id> --by <blocker_id>"

Mark a task as blocked by another task.

### "unblock <task_id>"

Remove all blockers and set status to active.

### "edit <task_id> [--priority P0] [--status active] [--type dev] [--related hypothesis:h01] [--related concept:lens] [--group viz]"

Update task fields. Supports `--related` (repeatable) and `--group` (single value).

### "show <task_id>"

Show full details of a single task.

### "summary"

Show task counts by status, type, priority, and group.

### Other actions

Pass through to `science-tool tasks`:

```bash
uv run science-tool tasks <action> [args...]
```

## Task Statuses

| Status | Meaning |
|--------|---------|
| `proposed` | Identified but not started |
| `active` | Currently being worked on |
| `blocked` | Waiting on another task |
| `deferred` | Deprioritized, may return |
| `done` | Completed successfully |
| `retired` | Closed without completion — no longer a priority |

## Execution Guidance

When working through tasks, follow these principles:

- **Respect `blocked-by` dependencies.** Don't start a blocked task until its blockers are complete. Run `science-tasks list --status=active` to see what's actionable.
- **Don't parallelize tasks that share environment state.** Tasks that install/change packages, modify shared config, or compete for GPU memory must run sequentially. Only parallelize truly independent work (e.g., two literature reviews).
- **Log failures into the task.** If a task fails, update its description with what went wrong: `science-tool tasks edit <id> --status=blocked`. This prevents repeating the same failed approach.
- **Check `AGENTS.md` before executing.** The project's operational guide may document known issues, environment constraints, or workarounds discovered in previous sessions.
- **Mark progress as you go.** Set tasks to `active` when starting, `done` when complete. Don't leave tasks in ambiguous states.
- **Retire rather than delete.** When a task is no longer relevant, use `retire` instead of deleting. This preserves the decision record.
- **Use groups for thematic clusters.** When multiple tasks share a theme (e.g., "lens-system", "formula-integration"), assign a group to enable filtered views.
- **Use `related` for cross-cutting connections.** Link tasks to hypotheses, concepts, methods, mechanisms, or other typed entities with `--related` (e.g., `--related=method:umap`, `--related=concept:lens`). Related entries become edges in the knowledge graph, and the same entity can appear across multiple groups. Use the `meta:` prefix for annotations you want to keep visible but exclude from the KG (e.g., `--related=meta:phase3b`).

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`

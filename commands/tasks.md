---
description: Manage research and development tasks — add, complete, defer, list, and filter. Use when the user wants to track work items, mark things done, or see what's on the backlog.
---

# Tasks

Manage the project task queue in `tasks/active.md`.
`$ARGUMENTS` specifies the action (add, done, defer, list, show, summary) and any parameters.

## Setup

Read `tasks/active.md` if it exists. If `tasks/` directory doesn't exist, create it.

## Actions

### No arguments or "list"

Show active tasks sorted by priority (P0 first). Use:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks list
```

### "add <description>"

Interactively create a task. Ask the user for:
- **Type:** research or dev
- **Priority:** P0-P3
- **Related entities:** (optional) e.g. hypothesis:h01, topic:protein-folding

Then run:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks add "<title>" --type=<type> --priority=<priority> [--related=<ref>...]
```

### "done <task_id>"

Mark a task complete. Optionally ask for a completion note.

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks done <task_id> [--note="<note>"]
```

### "defer <task_id>"

Defer a task. Ask for a reason.

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks defer <task_id> [--reason="<reason>"]
```

### Other actions

Pass through to `science-tool tasks`:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks <action> [args...]
```

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`

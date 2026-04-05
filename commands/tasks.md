---
description: Manage research and development tasks — add, complete, defer, retire, list, and filter. Use when the user wants to track work items, mark things done, retire outdated tasks, or see what's on the backlog.
---

# Tasks

Manage the project task queue in `tasks/active.md`.
`$ARGUMENTS` specifies the action (add, done, defer, retire, list, show, summary) and any parameters.

## Setup

Read `tasks/active.md` if it exists. If `tasks/` directory doesn't exist, create it.

## Actions

### No arguments or "list"

Show active tasks sorted by priority (P0 first). Use:

```bash
uv run science-tool tasks list
```

Filter by tag or group:

```bash
uv run science-tool tasks list --tag=lens --group=visualization
```

### "add <description>"

Interactively create a task. Ask the user for:
- **Type:** research or dev
- **Priority:** P0-P3
- **Related entities:** (optional) e.g. hypothesis:h01, topic:protein-folding
- **Tags:** (optional) multi-dimensional labels, e.g. lens-system, umap, formula
- **Group:** (optional) single group label for thematic clustering

Then run:

```bash
uv run science-tool tasks add "<title>" --type=<type> --priority=<priority> [--related=<ref>...] [--tags=<tag>...] [--group=<group>]
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

### "edit <task_id> [--priority P0] [--status active] [--type dev] [--related hypothesis:h01] [--tags lens] [--group viz]"

Update task fields. Supports `--tags` (multiple) and `--group` (single value).

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

- **Respect `blocked-by` dependencies.** Don't start a blocked task until its blockers are complete. Run `/science:tasks list --status=active` to see what's actionable.
- **Don't parallelize tasks that share environment state.** Tasks that install/change packages, modify shared config, or compete for GPU memory must run sequentially. Only parallelize truly independent work (e.g., two literature reviews).
- **Log failures into the task.** If a task fails, update its description with what went wrong: `science-tool tasks edit <id> --status=blocked`. This prevents repeating the same failed approach.
- **Check `AGENTS.md` before executing.** The project's operational guide may document known issues, environment constraints, or workarounds discovered in previous sessions.
- **Mark progress as you go.** Set tasks to `active` when starting, `done` when complete. Don't leave tasks in ambiguous states.
- **Retire rather than delete.** When a task is no longer relevant, use `retire` instead of deleting. This preserves the decision record.
- **Use groups for thematic clusters.** When multiple tasks share a theme (e.g., "lens-system", "formula-integration"), assign a group to enable filtered views.
- **Use tags for cross-cutting concerns.** Tags allow filtering across groups (e.g., `umap` tasks may span multiple groups).

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`

---
description: Manage research and development tasks — add, complete, defer, retire, list, and filter. Use when the user wants to track work items, mark things done, retire outdated tasks, or see what's on the backlog.
---

# Tasks

Manage the project task queue in `tasks/active.md`.
`$ARGUMENTS` specifies the action (add, done, defer, retire, list, show, summary) and any parameters.

> **Do not use Claude Code's built-in `TaskCreate` / `TaskUpdate` /
> `TaskList` tools** for science projects. The science task system is
> the authoritative store: it lives in the repo (`tasks/active.md`),
> survives clones, and integrates with the knowledge graph via
> `--related`. The Claude-Code task tools maintain a parallel,
> session-scoped store that is invisible to other agents and creates
> drift between what the conversation thinks is the task list and what
> the project actually tracks.

## Setup

Read `tasks/active.md` if it exists. If `tasks/` directory doesn't exist, create it.

## Task IDs And References

Task IDs are flat local identifiers in the form `tNNN`: `t001`, `t016`, `t335`, `t1000`. Do not encode hierarchy, revisions, or follow-up fragments in the ID. Use `parent: task:t001` for a local structural parent, and include the parent in `related` when it should remain visible in graph/search surfaces.

Bare `t123` always means a local task. `task:t123` is the canonical local task reference. Cross-project task and entity refs use namespace-first form: `natural-systems:task:t335`, `multiple-myeloma:hypothesis:h01`, `cbioportal:question:q006-ch-priority-gene-completeness`.

`tasks/archive.md` is for historical task aliases only. Use the same `## [tNNN] Title` heading shape when old documents still cite a task ID that no longer belongs in `tasks/active.md` or `tasks/done/YYYY-MM.md`; include brief metadata such as `status: archived` and `replacement: task:tNNN` when there is a successor. Do not use it for current operational task history.

## Actions

### No arguments or "list"

Show active tasks sorted by priority (P0 first). Use:

```bash
uv run science tasks list
```

Filter by related entity or group:

```bash
uv run science tasks list --related=topic:lens --group=visualization
```

### "add <description>"

Interactively create a task. Ask the user for:
- **Aspects:** (optional) project-declared analysis/work aspects, such as `software-development` or `hypothesis-testing`
- **Priority:** P0-P3
- **Related entities:** (optional) typed refs for hypotheses, themes, methods, questions, tasks, etc. Local refs use `<kind>:<slug>` such as `hypothesis:h01` or `task:t016`; cross-project refs use `<project-id>:<kind>:<slug>` such as `natural-systems:task:t335`.
- **Group:** (optional) single group label for thematic clustering

Then run:

```bash
uv run science tasks add "<title>" --aspects=<aspect> --priority=<priority> [--related=<ref>...] [--group=<group>]
```

### "done <task_id>"

Mark a task complete. Optionally ask for a completion note.

```bash
uv run science tasks done <task_id> [--note="<note>"]
```

### "defer <task_id>"

Defer a task. Ask for a reason.

```bash
uv run science tasks defer <task_id> [--reason="<reason>"]
```

### "retire <task_id>"

Close a task that is no longer a priority (not completed, just abandoned). Moves to done/ archive with `retired` status.

```bash
uv run science tasks retire <task_id> [--reason="<reason>"]
```

### "block <task_id> --by <typed-ref> [--by <typed-ref>...]"

Block a task by one or more **typed entity references** (`<kind>:<local-id>`).
Refs must resolve to known local entities. Repeatable.

- `--force` records the ref even if the entity is not yet known (e.g.
  you plan to create the dataset shortly). The unresolved reference will
  be flagged by `science graph audit`.
- Blockers are validated at write time. Untyped strings (legacy form) are
  rejected. Use `science tasks fix-blockers` to retype existing
  legacy blockers.

### "blockers <task_id>"

Show per-blocker readiness for a task. `--format json` for scripting.

### "fix-blockers"

Interactive sweep to retype legacy untyped blockers in `tasks/active.md`.
`--dry-run` lists what would change without modifying files.

### "unblock <task_id>"

Remove all blockers and set status to active.

### "edit <task_id> [--priority P0] [--status active] [--aspects software-development] [--related hypothesis:h01] [--related topic:lens] [--group viz]"

Update task fields. Supports `--aspects` and `--related` (repeatable) and `--group` (single value).

### "show <task_id>"

Show full details of a single task.

### "summary"

Show task counts by status, type, priority, and group.

### Other actions

Pass through to `science tasks`:

```bash
uv run science tasks <action> [args...]
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

- **Respect typed blocker dependencies.** Don't start a blocked task until its blockers are ready. Use `tasks blockers <task_id>` to inspect per-blocker readiness (e.g., embargoed datasets, incomplete workflow runs). Run `/science:tasks list --status=active` to see what's actionable overall.
- **Don't parallelize tasks that share environment state.** Tasks that install/change packages, modify shared config, or compete for GPU memory must run sequentially. Only parallelize truly independent work (e.g., two literature reviews).
- **Log failures into the task.** If a task fails, update its description with what went wrong: `science tasks edit <id> --status=blocked`. This prevents repeating the same failed approach.
- **Check `AGENTS.md` before executing.** The project's operational guide may document known issues, environment constraints, or workarounds discovered in previous sessions.
- **Mark progress as you go.** Set tasks to `active` when starting, `done` when complete. Don't leave tasks in ambiguous states.
- **Retire rather than delete.** When a task is no longer relevant, use `retire` instead of deleting. This preserves the decision record.
- **Use groups for thematic clusters.** When multiple tasks share a theme (e.g., "lens-system", "formula-integration"), assign a group to enable filtered views.
- **Use `related` for cross-cutting connections.** Link tasks to hypotheses, themes, methods, or other entities with `--related` (e.g., `--related=method:umap`). Related entries become edges in the knowledge graph, and the same entity can appear across multiple groups. Use the `meta:` prefix for annotations you want to keep visible but exclude from the KG (e.g., `--related=meta:phase3b`).

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`

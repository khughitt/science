<!--
templates/agents-md.md — canonical scaffold for a project's AGENTS.md.

CLAUDE.md is a single-line `@AGENTS.md` pointer. This file is what the agent
actually reads at session start.

Keep it short. References to core/overview.md and core/decisions.md belong in
the Pointers section, NOT as `@`-includes (those would inline hundreds of
lines per turn). The Load-bearing constraints section between the BEGIN/END
markers is managed by `/science:curate` — edit core/decisions.md instead and
let curate refresh the digest.

Update mechanism (read this before "fixing" the template for an existing
project): `/science:curate` only refreshes the load-bearing-constraints
digest between the BEGIN/END markers below, from that project's
`core/decisions.md`. The static body of this template — everything else on
this page — only applies at create/import time; it is written once when a
project is scaffolded via `/science:create-project` or `/science:import-project`.
There is no push-to-existing-projects mechanism for the boilerplate, and it
does not propagate to projects that already exist. To change an existing
project's `AGENTS.md` body, edit that project's file directly.
-->

# <project> — Agent Guide

## What this is

<1-2 sentence project description.>

## Profile

<software | research>, with <one-line elaboration if useful>.

## Validation

```bash
bash validate.sh --verbose
```

## Worktrees

This project consumes the `science` toolkit through a **relative editable** uv
source in `pyproject.toml` (`science = { path = "../.../science/science" }`),
resolved relative to the checkout's location on disk. A git worktree created
**inside** the repo (the default `.worktrees/<name>/`) sits deeper than the main
checkout, so that relative path no longer resolves and every `uv run` — the
pre-commit hook, `validate.sh`, and tests — fails with `Distribution not found`.

- **Isolated editing / docs-only commits:** a nested `.worktrees/` worktree is
  fine. The hook failure is expected and unrelated to your change — commit with
  `--no-verify`, or commit from the main checkout.
- **When you need `uv` / tests / `validate.sh` to run inside the worktree:**
  create it at the **same filesystem depth** as the main checkout (a sibling
  directory), not nested — e.g. `git worktree add ../<project>--<branch> <branch>`
  — so the relative `science` source still resolves.

## Conventions

- <bullets — operational rules an agent will need every turn>

## Task execution

- Tasks live in `tasks/active.md`, managed by `science tasks` (or
  the `/science:tasks` slash command). Completed/retired tasks archive
  to `tasks/done/YYYY-MM.md`.
- **Do not use Claude Code's built-in `TaskCreate` / `TaskUpdate` /
  `TaskList` tools.** They create a parallel task store outside the
  repo, invisible to other agents and to fresh clones, and they fight
  the science task system. Use `science tasks` exclusively for
  task management on this project.
- Common invocations (run from the project root):

  ```bash
  uv run science tasks list
  uv run science tasks add "TITLE" --priority P2 --description "..."
  uv run science tasks done <task_id> --note "..."
  ```

  The bare `uv run science ...` form requires the project's root
  `pyproject.toml` to list `science` as a dev dependency (see the
  create-project / import-project commands). If that fails, run
  `uv run science health` — it surfaces missing scaffold pieces
  with concrete fix commands.
- <other bullets — how tasks are run, where commits go, etc.>

## Known issues / nuances

- <bullets — gotchas not derivable from the code>

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
## Load-bearing constraints

<!-- One bullet per active decision in core/decisions.md, phrased as an
imperative rule. The "why" stays in core/decisions.md. -->

- _none yet — populated by `/science:curate` once `core/decisions.md` has entries._

<!-- END: load-bearing-constraints -->

## Pointers

- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `tasks/active.md`
- Hypotheses: `entities/hypotheses/`

<!--
templates/agents-md.md — canonical scaffold for a project's AGENTS.md.

CLAUDE.md is a single-line `@AGENTS.md` pointer. This file is what the agent
actually reads at session start.

Keep it short. References to core/overview.md and core/decisions.md belong in
the Pointers section, NOT as `@`-includes (those would inline hundreds of
lines per turn). The Load-bearing constraints section between the BEGIN/END
markers is managed by `/science:curate` — edit core/decisions.md instead and
let curate refresh the digest.
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
- Hypotheses: `specs/hypotheses/`

<!--
templates/agents-md.md — canonical scaffold for a project's AGENTS.md.

CLAUDE.md is a single-line `@AGENTS.md` pointer. This file is what the agent
actually reads at session start.

Keep it short. References to core/overview.md and core/decisions.md belong in
the Pointers section, NOT as `@`-includes (those would inline hundreds of
lines per turn). The Load-bearing constraints section between the BEGIN/END
markers is managed by the `science-curate` skill — edit core/decisions.md instead and
let curate refresh the digest.

Update mechanism (read this before "fixing" the template for an existing
project): The `science-curate` skill only refreshes the load-bearing-constraints
digest between the BEGIN/END markers below, from that project's
`core/decisions.md`. The static body of this template — everything else on
this page — only applies at create/import time; it is written once when a
project is scaffolded via the `science-create-project` skill or the `science-import-project` skill.
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

This project installs the `science` toolkit from its public Git source, with the
exact revision pinned in `uv.lock`. The dependency is location-independent, so
nested worktrees under `.worktrees/<name>/` are the preferred default and run
the same project-local toolchain as the main checkout.

After creating a worktree, initialize it from that checkout:

```bash
uv sync --frozen
uv run --frozen science --version
bash validate.sh --verbose
```

Do not route commands through the main checkout's `.venv`, rewrite the source
path, or move the worktree outside the repository. When deliberately testing
uncommitted toolkit code, overlay it for that invocation only:

```bash
uv run --with-editable ~/d/science/science <command>
```

## Conventions

- <bullets — operational rules an agent will need every turn>

## Task execution

- Open work lives as one YAML-frontmatter file per open task under
  `tasks/active/`, managed by `science tasks` (or the `science-tasks` skill). `done` and `retire` move terminal records directly to
  `tasks/done/YYYY-MM.md`; no separate archive step is needed.
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
  `uv run science health --severity error` — scoped to errors, it
  surfaces missing scaffold pieces with concrete fix commands; add
  `--output PATH` to write the complete report.
- <other bullets — how tasks are run, where commits go, etc.>

## Design docs and plans

Design docs and implementation plans are first-class `spec` / `plan` entities in
this project. When a brainstorming or planning skill would write a design doc or
plan, do NOT commit the loose file — import it so it gains a canonical id and an
`entities/` home:

1. Author the doc as a project-local **staging file** (e.g. `docs/_staging/x.md`,
   no frontmatter). This staging file is **not committed**.
2. Preview: `science entities import docs/_staging/x.md --kind spec --save-plan /tmp/p.json`
   (use `--kind plan` for implementation plans). **Inspect the manual-hit list** in
   the preview — plain prose/code path mentions are reported, not auto-repointed.
3. Apply: `science entities import --apply-plan /tmp/p.json --expected-plan-sha256 <plan_sha256>`
   (the `--save-plan` step prints `plan_sha256`; the apply refuses a plan edited after review),
   then delete the plan file.
4. **Commit the canonical entity** at `entities/specs/NNNN-slug.md` (or
   `entities/plans/NNNN-slug.md`), not the staging file — the staging file is moved
   away by apply.

This overrides any skill default that writes and commits the loose design doc.

## Known issues / nuances

- <bullets — gotchas not derivable from the code>

<!-- BEGIN: load-bearing-constraints (managed by the `science-curate` skill; edit core/decisions.md instead) -->
## Load-bearing constraints

<!-- One bullet per active decision in core/decisions.md, phrased as an
imperative rule. The "why" stays in core/decisions.md. -->

- _none yet — populated by the `science-curate` skill once `core/decisions.md` has entries._

<!-- END: load-bearing-constraints -->

## Pointers

- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `science tasks list` (`tasks/active/`, one file per open task)
- Hypotheses: `entities/hypotheses/`

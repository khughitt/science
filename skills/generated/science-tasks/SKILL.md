---
name: science-tasks
description: "Manage research and development tasks — add, complete, defer, retire, list, and filter. Use when the user wants to track work items, mark things done, retire outdated tasks, or see what's on the backlog."
user-invocable: true
---

# Tasks

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the emitted methodology router skills that own the relevant leaf guidance (for example, load the `science-literature` skill for `literature-evaluation` and `literature-citation-discipline` guidance, and load the `science-epistemics` skill for `epistemics-proposition-graph-reasoning` guidance).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Manage the project task queue in `tasks/active.md`.
the user input specifies the action (add, done, defer, retire, list, show, summary) and any parameters.

> **Do not use Claude Code's built-in `TaskCreate` / `TaskUpdate` /
> `TaskList` tools** for science projects. The science task system is
> the authoritative store: it lives in the repo (`tasks/active.md`),
> survives clones, and integrates with the knowledge graph via
> `--related`. The Claude-Code task tools maintain a parallel,
> session-scoped store that is invisible to other agents and creates
> drift between what the conversation thinks is the task list and what
> the project actually tracks.


## Setup

Run `science tasks list` to see the current queue. If the `tasks/` directory doesn't exist, create it (the first `science tasks add` scaffolds it).

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
- **Aspects:** (optional) task-scoped analysis/work aspects, such as `software-development` or `hypothesis-testing`
- **Priority:** P0-P3
- **Related entities:** (optional) typed refs for hypotheses, themes, methods, questions, tasks, etc. Local refs use `<kind>:<slug>` such as `hypothesis:h01` or `task:t016`; cross-project refs use `<project-id>:<kind>:<slug>` such as `natural-systems:task:t335`.
- **Group:** (optional) single group label for thematic clustering

Task-scoped aspects do not need to be declared in `science.yaml`; they only need
to use a known Science aspect name. Add an aspect to `science.yaml` only when
you want project-wide aspect behavior, not merely to label or reuse one task's
analysis/work category.

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

- **Respect typed blocker dependencies.** Don't start a blocked task until its blockers are ready. Use `tasks blockers <task_id>` to inspect per-blocker readiness (e.g., embargoed datasets, incomplete workflow runs). Run `science-tasks` skill list --status=active` to see what's actionable overall.
- **Don't parallelize tasks that share environment state.** Tasks that install/change packages, modify shared config, or compete for GPU memory must run sequentially. Only parallelize truly independent work (e.g., two literature reviews).
- **Log failures into the task.** If a task fails, update its description with what went wrong: `science tasks edit <id> --status=blocked`. This prevents repeating the same failed approach.
- **Check `AGENTS.md` before executing.** The project's operational guide may document known issues, environment constraints, or workarounds discovered in previous sessions.
- **Mark progress as you go.** Set tasks to `active` when starting, `done` when complete. Don't leave tasks in ambiguous states.
- **Retire rather than delete.** When a task is no longer relevant, use `retire` instead of deleting. This preserves the decision record.
- **Use groups for thematic clusters.** When multiple tasks share a theme (e.g., "lens-system", "formula-integration"), assign a group to enable filtered views.
- **Use `related` for cross-cutting connections.** Link tasks to hypotheses, themes, methods, or other entities with `--related` (e.g., `--related=method:umap`). Related entries become edges in the knowledge graph, and the same entity can appear across multiple groups. Use the `meta:` prefix for annotations you want to keep visible but exclude from the KG (e.g., `--related=meta:phase3b`).

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`

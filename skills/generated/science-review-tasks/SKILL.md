---
name: science-review-tasks
description: "Audit and reorganize the task backlog — check stale tasks, verify statuses against the codebase, adjust priorities, identify gaps, group related work. Use when the user wants to clean up the backlog."
user-invocable: true
---

# Review Tasks

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `science-literature`, `science-literature`, `science-epistemics`).
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

Structured review of the project task backlog. Validates statuses against actual codebase state, adjusts priorities to current project direction, and identifies gaps.


the user input optionally specifies scope (e.g., "P2 only", "research tasks", "lens-system group").

## Procedure

### 1. Load current state

```bash
uv run science tasks list --format=json
uv run science tasks summary
```

If `knowledge/graph.trig` exists, also run:

```bash
uv run science graph attention-sample --limit 8 --format json
```

Use `science tasks summary` (already run above) for the total count and distribution, and `science tasks show <id>` when you need a specific task's full description.

### 2. Identify review scope

If the user input specifies a filter (priority, type, group, related), apply it. Otherwise review all open tasks (non-done, non-retired).

### 3. Status verification

For each open task, check whether the codebase reflects completion:

- **Search for implementation evidence.** Use Grep/Glob to look for code, reports, or documents that the task describes. Check `entities/reports/`, `entities/interpretations/`, `scripts/`, `src/`, and `pipeline/` as appropriate.
- **Check git history.** Search recent commits for the task ID or key terms from the title.
- **Check for partial progress.** Some tasks may be in-progress rather than proposed.

Classify each task into one of:
- **Status correct** — no change needed
- **Should be `done`** — implementation evidence found
- **Should be `in-progress`** — partial work exists
- **Should be `retired`** — superseded, no longer relevant, or blocked indefinitely
- **Priority drift** — status correct but priority should change given current direction

### 4. Priority reassessment

Evaluate priorities against the current project trajectory:

- What was completed recently? (Check last ~20 commits)
- What are the active research questions and hypotheses?
- Which tasks have the highest strategic value right now?
- Which tasks are research rabbit holes with diminishing returns?
- Which weighted attention sample rows suggest neglected or needs-review epistemic targets that should influence task priority?

Recommend:
- **Promotions** (P2/P3 -> P1): tasks with high strategic value or that unblock important work
- **Demotions** (P1/P2 -> P3): tasks that are interesting but not urgent
- **Retirements**: tasks superseded by other work or no longer aligned with project goals

### 5. Gap identification

Look for:
- **Untracked work:** Recent commits or artifacts that don't correspond to any task
- **Missing follow-ups:** Completed tasks whose natural successors aren't tracked
- **Orphaned blockers:** Tasks blocked by something already completed (unblock them)
- **Dependency gaps:** Work that should be sequenced but isn't linked via `blocked-by`

### 6. Thematic grouping

If tasks lack `group` labels, suggest groupings based on shared themes. Common patterns:
- Tasks sharing the same `related` entities, especially `theme:` references for cross-cutting work and `method:` references for analytical procedures
- Tasks that form a dependency chain
- Tasks addressing the same system component or research question

For open questions, suggest theme connections via `related` (e.g., `theme:protein-folding-generalization`)
when they share themes with existing hypotheses, tasks, or other questions. Questions
should be linkable to the same entity graph used for tasks.

### 7. Present findings

Summarize as a structured report:

```
## Status Corrections
| Task | Current | Proposed | Evidence |
|------|---------|----------|----------|

## Priority Changes
| Task | Current | Proposed | Rationale |
|------|---------|----------|-----------|

## Suggested Retirements
| Task | Reason |
|------|--------|

## New Tasks
| Title | Aspects | Priority | Rationale |
|-------|------|----------|-----------|

## Suggested Groups
| Group | Tasks | Theme |
|-------|-------|-------|
```

### 8. Apply changes

After user confirmation, apply changes using:

```bash
# Status corrections
uv run science tasks done <id> --note="<evidence>"
uv run science tasks retire <id> --reason="<reason>"

# Priority changes
uv run science tasks edit <id> --priority=<new>

# Group assignments
uv run science tasks edit <id> --group=<group>

# Related entity links (replaces old --tags flag)
uv run science tasks edit <id> --related=topic:foo --related=topic:bar

# New tasks
uv run science tasks add "<title>" --aspects=<aspect> --priority=<priority> [--group=<group>] [--related=<ref>...]
```

### 9. Commit

```bash
git add tasks/ && git commit -m "tasks: backlog review — N status corrections, M priority changes, K new tasks"
```

## Tips

- Use subagents to parallelize codebase searches for multiple tasks
- Check recently completed tasks (`science tasks list --status done --since <window-start>`) for context that might inform gap analysis
- Cross-reference `entities/discussions/` and `entities/interpretations/` for research context
- The `science:next-steps` skill produces complementary forward-looking analysis; this skill is backward-looking (auditing what exists)
- For a broader project audit beyond just tasks (unresolved references, lingering tags, knowledge gaps), use `science-health`.

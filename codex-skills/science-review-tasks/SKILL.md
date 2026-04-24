---
name: science-review-tasks
description: "Audit and reorganize the task backlog — check stale tasks, verify statuses against the codebase, adjust priorities, identify gaps, group related work. Use when the user wants to clean up the backlog."
---

# Review Tasks

Converted from Claude command `/science:review-tasks`.

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

Structured review of the project task backlog. Validates statuses against actual codebase state, adjusts priorities to current project direction, and identifies gaps.

the user input optionally specifies scope (e.g., "P2 only", "research tasks", "lens-system group").

## Procedure

### 1. Load current state

```bash
uv run science-tool tasks list --format=json
uv run science-tool tasks summary
```

Read `tasks/active.md` for full task descriptions. Note the total count and distribution.

### 2. Identify review scope

If $ARGUMENTS specifies a filter (priority, type, group, related), apply it. Otherwise review all open tasks (non-done, non-retired).

### 3. Status verification

For each open task, check whether the codebase reflects completion:

- **Search for implementation evidence.** Use Grep/Glob to look for code, reports, or documents that the task describes. Check `doc/reports/`, `doc/interpretations/`, `scripts/`, `src/`, and `pipeline/` as appropriate.
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
- Tasks sharing the same `related` entities (especially topic references)
- Tasks that form a dependency chain
- Tasks addressing the same system component or research question

For open questions, suggest topic connections via `related` (e.g., `topic:protein-folding`)
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
| Title | Type | Priority | Rationale |
|-------|------|----------|-----------|

## Suggested Groups
| Group | Tasks | Theme |
|-------|-------|-------|
```

### 8. Apply changes

After user confirmation, apply changes using:

```bash
# Status corrections
uv run science-tool tasks done <id> --note="<evidence>"
uv run science-tool tasks retire <id> --reason="<reason>"

# Priority changes
uv run science-tool tasks edit <id> --priority=<new>

# Group assignments
uv run science-tool tasks edit <id> --group=<group>

# Related entity links (replaces old --tags flag)
uv run science-tool tasks edit <id> --related=topic:foo --related=topic:bar

# New tasks
uv run science-tool tasks add "<title>" --type=<type> --priority=<priority> [--group=<group>] [--related=<ref>...]
```

### 9. Commit

```bash
git add tasks/ && git commit -m "tasks: backlog review — N status corrections, M priority changes, K new tasks"
```

## Tips

- Use subagents to parallelize codebase searches for multiple tasks
- Check `tasks/done/` for recently completed tasks that might inform gap analysis
- Cross-reference `doc/discussions/` and `doc/interpretations/` for research context
- The `science:next-steps` skill produces complementary forward-looking analysis; this skill is backward-looking (auditing what exists)
- For a broader project audit beyond just tasks (unresolved references, lingering tags, knowledge gaps), use `science-health`.

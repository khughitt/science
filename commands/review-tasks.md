---
description: Audit and reorganize the task backlog — check stale tasks, verify statuses against the codebase, adjust priorities, identify gaps, group related work. Use when the user wants to clean up the backlog.
---

# Review Tasks

Structured review of the project task backlog. Validates statuses against actual codebase state, adjusts priorities to current project direction, and identifies gaps.

`$ARGUMENTS` optionally specifies scope (e.g., "P2 only", "research tasks", "lens-system group").

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
- For a broader project audit beyond just tasks (unresolved references, lingering tags, knowledge gaps), use `/science:health`.

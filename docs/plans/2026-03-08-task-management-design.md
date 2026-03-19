# Task Management System + `/science:next-steps` — Design

**Date:** 2026-03-08
**Status:** Approved

## Problem

`RESEARCH_PLAN.md` is overloaded: it serves as high-level strategic plan, task queue, progress log, and priority rationale. Tasks are narrative prose, making them hard to filter or query programmatically. Cross-references to hypotheses, questions, and inquiries are ad-hoc. There's no clean way to answer "what did I do last week?" vs "what should I do next?"

## Solution

A lightweight, file-based task management system with:

1. Structured markdown task entries in `tasks/active.md`
2. Monthly archival of completed tasks in `tasks/done/YYYY-MM.md`
3. A `science-tool tasks` CLI for programmatic task operations
4. A `/science:tasks` command for interactive task management
5. A `/science:next-steps` command replacing `/science:review-tasks`

`RESEARCH_PLAN.md` becomes a stable high-level strategic document (research direction, phases, long-term goals) — no longer a task queue.

## Task Storage

```
tasks/
  active.md         # current task queue (structured entries)
  done/
    2026-03.md      # completed tasks, archived monthly
```

## Task Entry Format

```markdown
## [t001] Reproduce DNABERT-2 baseline
- type: dev
- priority: P1
- status: active
- related: [hypothesis:h01, topic:dnabert2]
- blocked-by: [t003]
- created: 2026-03-08

Short description of what needs to happen and why.
- Optional sub-steps as bullets.
```

### Metadata Fields

| Field | Values | Required |
|---|---|---|
| `type` | `research`, `dev` | yes |
| `priority` | `P0`, `P1`, `P2`, `P3` | yes |
| `status` | `proposed`, `active`, `done`, `blocked`, `deferred` | yes |
| `related` | typed refs: `kind:slug` (e.g. `hypothesis:h01`, `question:q05`, `topic:protein-folding`) | no |
| `blocked-by` | task IDs (e.g. `t003`) | no |
| `created` | `YYYY-MM-DD` | yes |
| `completed` | `YYYY-MM-DD` (added on archival) | no |

### Entity Linking

Tasks use a generic `related` field with typed references (`kind:slug`). This is flexible and extensible — no schema changes needed when new entity types appear.

`blocked-by` is kept as a separate field because it has operational meaning: blocked tasks are excluded from "actionable" suggestions in `/science:next-steps`.

### Task IDs

Simple incrementing integers: `t001`, `t002`, etc. The next ID is determined by scanning active + done files. No nested task hierarchy — use bullet points in the description for sub-steps.

## `science-tool tasks` CLI

Subcommand on the existing `science-tool` Python CLI.

```
science-tool tasks add "Description" --type=dev --priority=P1 [--related=hypothesis:h01] [--blocked-by=t003]
science-tool tasks done t001 [--note="completed with X approach"]
science-tool tasks defer t001 [--reason="waiting on dataset"]
science-tool tasks block t001 --by=t003
science-tool tasks unblock t001
science-tool tasks edit t001 --priority=P0 --status=active
science-tool tasks list [--type=dev] [--priority=P1] [--status=active] [--related=h01]
science-tool tasks show t001
science-tool tasks summary
```

## Science Commands

### `/science:tasks` (NEW)

Interactive task management. Thin wrapper around `science-tool tasks` with conversational UX for filling in metadata when adding tasks.

### `/science:next-steps` (NEW, replaces `/science:review-tasks`)

Reads tasks, git history, hypotheses, open questions, and research gaps. Synthesizes a "state of the project" summary with recommended next actions. Does not modify anything unless asked.

**Input:** `$ARGUMENTS` as optional filters (e.g. "dev only", "this week", "related to h01").

**Reads:**
1. `tasks/active.md`
2. Recent git log (last 10-15 commits)
3. `specs/hypotheses/` status
4. `doc/questions/` (open, high-priority)
5. `doc/10-research-gaps.md` if present
6. Recently completed tasks in `tasks/done/`

**Output structure:**

```
## Recent Progress
Summary of what's been done (from git + recently completed tasks)

## Current State
Active tasks by priority (P0 first), blocked tasks and blockers, hypothesis status

## Suggested Next Steps
Top 3-5 recommended actions with rationale.
Flags stale tasks (active but no related commits in >7 days).
Flags newly unblocked tasks.
```

### `/science:status` (UPDATED)

Section 8 ("Next Steps") reads from `tasks/active.md` instead of `RESEARCH_PLAN.md`.

### `/science:review-tasks` (REMOVED)

Replaced by `/science:next-steps`.

## Integration with Other Commands

Commands that produce actionable items (`research-gaps`, `interpret-results`, `research-topic`) prompt the user: "Create tasks from these findings?" and use `science-tool tasks add` if accepted.

## Validation

`validate.sh` gets a new check: `tasks/active.md` exists and conforms to the entry format (valid task IDs, required metadata fields present).

## `RESEARCH_PLAN.md`

Stays as a high-level strategic document — research direction, phase descriptions, long-term goals. No longer serves as a task queue. Existing task content in current projects (seq-feats, 3d-attention-bias) will be manually migrated to `tasks/active.md`.

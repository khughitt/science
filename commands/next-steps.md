---
description: Synthesize recent progress, current project state, and suggest next actions. Use at session start, when the user says "what should I work on", "next steps", "priorities", or "what's next". Replaces the old review-tasks command.
---

# Next Steps

Synthesize the current state of the project and suggest next actions.
Use `$ARGUMENTS` as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. `specs/hypotheses/` — status of each hypothesis
4. `doc/questions/` — open, high-priority questions
5. `doc/10-research-gaps.md`

Also run: `git log --oneline -15 --format="%h %s (%cr)"`

## Output

### 1. Recent Progress

Summarize what's been accomplished recently by combining:
- Recently completed tasks from `tasks/done/`
- Recent git commits

Group by theme (research, development, documentation) rather than listing chronologically.
Keep to 5-8 bullet points maximum.

### 2. Current State

From `tasks/active.md`, show:
- **P0 tasks** (critical path) — full detail
- **P1 tasks** (active work) — title and status
- **Blocked tasks** — what's blocking them
- **Hypothesis status** — one-line summary per hypothesis from `specs/hypotheses/`

### 3. Suggested Next Steps

Recommend 3-5 actions based on:
- Unblocked tasks that were previously blocked
- Highest-priority active tasks without recent commits
- Stale tasks (active but no related activity in >7 days)
- Open high-priority questions that could become tasks
- Research gaps that haven't been addressed

For each suggestion, include:
- The task ID (if it exists) or "new task" if suggesting something not yet tracked
- A brief rationale (1 sentence)
- The suggested command to run (e.g. `/science:research-topic`, `/science:tasks add ...`)

## Format

Use rich terminal formatting:
- Section headers as `##`
- Tables for task lists
- Bullet lists for progress and suggestions
- Bold for emphasis on critical items

Do not modify any files. This is a read-only analysis command.

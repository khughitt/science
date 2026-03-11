---
description: Synthesize recent progress, analyze coverage gaps, and suggest next actions. Use at session start, when the user says "what should I work on", "next steps", "priorities", "what's next", "gaps", or "what am I missing". Replaces the former research-gaps command.
---

# Next Steps

Synthesize the current state of the project, analyze coverage gaps, and suggest prioritized next actions.
Use `$ARGUMENTS` as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`, `gaps only`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. `specs/hypotheses/` — status of each hypothesis
4. `specs/scope-boundaries.md` — project scope
5. Open questions: check `doc/questions/` first; if it doesn't exist, scan for `*questions*.md` or `*open-questions*.md` in the doc directory
6. `doc/topics/` or equivalent topic coverage files in the doc directory
7. `doc/papers/` — paper coverage
8. `doc/meta/next-steps-*.md` — prior next-steps analyses (most recent)

Also run: `git log --oneline -15 --format="%h %s (%cr)"`

## Workflow

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

### 3. Coverage Gap Analysis

Analyze project coverage across five dimensions:

1. **Concepts/topics:** What core topics are missing or too shallow?
2. **Evidence quality:** What claims rely on weak, old, or uncorroborated support?
3. **Contradictions:** Where do findings conflict without explicit resolution?
4. **Testability:** Which hypotheses lack falsifiability criteria or clear next tests?
5. **Data feasibility:** Where are key variables/questions blocked by missing datasets?

Focus on decision impact, not document volume.

Present as a coverage map: **Strong / Partial / Missing** for each major area.

### 3b. Newly Unblocked

If a prior next-steps analysis exists (`doc/meta/next-steps-*.md`), compare against it:
- Which tasks were previously blocked but are now unblocked?
- What changed to unblock them?

This longitudinal view makes progress visible and highlights newly actionable work.

### 3c. Task Tracking Gaps

Scan pipeline plans in `doc/plans/` for implementation tasks that are not tracked in `tasks/active.md`. Surface any development work buried in plan documents that should be trackable tasks.

### 4. Suggested Next Steps

Recommend 3-5 actions based on:
- High-impact gaps from the coverage analysis
- Unblocked tasks that were previously blocked
- Highest-priority active tasks without recent commits
- Stale tasks (active but no related activity in >7 days)
- Open high-priority questions that could become tasks

For each suggestion, include:
- The task ID (if it exists) or "new task" if suggesting something not yet tracked
- A brief rationale (1 sentence)
- The suggested command to run (e.g., `/science:research-topic`, `/science:tasks add ...`)

## Writing

Save output to `doc/meta/next-steps-<YYYY-MM-DD>.md` with these sections:

```markdown
# Next Steps — YYYY-MM-DD

## Recent Progress
<grouped bullet points>

## Current State
<task summary, hypothesis status>

## Coverage Gaps
### Coverage Map
| Area | Coverage | Key Gap |
|---|---|---|
| <area> | Strong/Partial/Missing | <gap> |

### High-Impact Gaps
<prioritized gap descriptions with evidence links>

## Newly Unblocked (if prior analysis exists)
<tasks that became actionable since last analysis>

## Task Tracking Gaps (if any)
<implementation work in plans not tracked as tasks>

## Recommended Next Actions
| Priority | Action | Rationale | Command |
|---|---|---|---|
| P1 | <action> | <why now> | <command> |
```

## Format

Display the output in the terminal using rich formatting:
- Section headers as `##`
- Tables for task lists and coverage maps
- Bullet lists for progress and suggestions
- Bold for emphasis on critical items

> **Note:** This command saves output to disk (unlike the previous read-only version). This is intentional — ephemeral analysis that disappears after the session is less useful than a versioned record.

## After Writing

1. Save to `doc/meta/next-steps-<YYYY-MM-DD>.md`.
2. Offer to create tasks from recommended items: "Create tasks from these suggestions?"
   - If accepted, run `science-tool tasks add` for each recommended task with appropriate priority, type, and related entities
3. Cross-link relevant items in `doc/questions/`.
4. Commit: `git add -A && git commit -m "doc: next steps and gap analysis <date>"`

## Process Reflection

Reflect on the **gap analysis framework** and the **prioritization workflow**.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — next-steps

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence
- If everything worked smoothly, a single "No friction encountered" is fine

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

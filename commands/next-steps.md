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

## Mode Detection

Check for a prior same-day analysis: scan `doc/meta/next-steps-<today's date>*.md`.

- **Full mode** (default): No same-day analysis exists, or the last analysis is >3 days old, or the user explicitly requests full analysis.
- **Delta mode**: A same-day analysis already exists. Focus on what changed:
  - New completions and commits since last analysis
  - Status transitions (tasks that changed state)
  - Newly unblocked items
  - Revised recommendations
  - Skip unchanged coverage map rows — show only areas where coverage level or direction changed.
  - Append as a `## Update — HH:MM` section to the existing file rather than creating a new file.

If a prior analysis exists from 1-3 days ago, default to full mode but reference the prior analysis for the "Direction" column in the coverage map.

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
- **Hypothesis / question status** — one-line summary per hypothesis from `specs/hypotheses/`, or per open question from `doc/questions/` if no formal hypotheses exist

#### Workflow Runs
- Scan `results/` for `datapackage.json` manifests
- Report: recent runs (last 7 days), superseded runs, runs with status `draft`
- Flag any workflow-run that has no corresponding interpretation document

### 3. Coverage Gap Analysis

Analyze project coverage across key dimensions. Use these five default dimensions, but adapt or replace them if the project's actual gaps are better described by different categories (e.g., "infrastructure built vs. exploited", "theoretical grounding", domain-specific axes):

1. **Concepts/topics:** What core topics are missing or too shallow?
2. **Evidence quality:** What claims rely on weak, old, or uncorroborated support?
3. **Contradictions:** Where do findings conflict without explicit resolution?
4. **Testability:** Which hypotheses lack falsifiability criteria or clear next tests?
5. **Data feasibility:** Where are key variables/questions blocked by missing datasets?

Focus on decision impact, not document volume.

Present as a coverage map with a **Direction** column when a prior analysis exists:

| Area | Coverage | Direction | Key Gap |
|---|---|---|---|
| _area_ | Strong/Partial/Missing | improving/stable/regressing/new | _gap_ |

The Direction column (improving / stable / regressing / new) shows momentum since the last analysis. This makes regressions and stale areas immediately visible.

### 3b. Status Transitions

If a prior next-steps analysis exists (`doc/meta/next-steps-*.md`), compare against it and surface all three directions:

- **Newly unblocked:** tasks that were blocked but are now actionable. What changed to unblock them?
- **Newly blocked:** tasks that lost a dependency or had assumptions invalidated since the last analysis.
- **Newly irrelevant:** tasks superseded by results or no longer decision-relevant. These are pruning opportunities — removing stale work from the queue is as valuable as adding new work.

This longitudinal view makes progress visible and highlights both forward momentum and pruning opportunities.

### 3c. Task Tracking Gaps

Scan pipeline plans in `doc/plans/` for implementation tasks that are not tracked in `tasks/active.md`. Surface any development work buried in plan documents that should be trackable tasks.

### 3d. Strategic Decision Point (if applicable)

If the project is at a fork — a moment where the next direction depends on a choice between competing approaches, depth-first vs breadth-first, or a go/no-go gate — add a "Strategic Decision Point" section that frames:
- What the decision is
- What evidence bears on it
- What the options are and their tradeoffs
- What the recommended path is and why

This captures strategic framing that individual task recommendations don't. Omit if no strategic decision is pending.

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

**Design constraints:** If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it as a row in the Recommended Next Actions table with a note to record it in project memory or a design doc.

## Writing

Save output to `doc/meta/next-steps-<YYYY-MM-DD>.md`. If a file for today already exists (delta mode), append an `## Update — HH:MM` section instead of creating a new file.

```markdown
# Next Steps — YYYY-MM-DD

## Recent Progress
<grouped bullet points>

## Current State
<task summary, hypothesis/question status>

## Coverage Gaps
### Coverage Map
| Area | Coverage | Direction | Key Gap |
|---|---|---|---|
| <area> | Strong/Partial/Missing | improving/stable/regressing/new | <gap> |

### High-Impact Gaps
<prioritized gap descriptions with evidence links>

## Status Transitions (if prior analysis exists)
<newly unblocked, newly blocked, newly irrelevant tasks since last analysis>

## Task Tracking Gaps (if any)
<implementation work in plans not tracked as tasks>

## Strategic Decision Point (if applicable)
<decision framing, options, tradeoffs, recommendation>

## Recommended Next Actions
| Priority | Action | Rationale | Command |
|---|---|---|---|
| P1 | <action> | <why now> | <command> |

## Session Summary (optional)
<brief narrative arc of the session — what happened, what changed, what was learned>
<useful for future orientation when the trajectory matters more than the snapshot>
```

## Format

Display the output in the terminal using rich formatting:
- Section headers as `##`
- Tables for task lists and coverage maps
- Bullet lists for progress and suggestions
- Bold for emphasis on critical items

> **Note:** This command saves output to disk (unlike the previous read-only version). This is intentional — ephemeral analysis that disappears after the session is less useful than a versioned record.

## Cross-Project Sync Check

Before writing, run `science-tool sync status` to check cross-project sync staleness.
If sync is stale, include a note in the Recommended Next Actions table:

| Priority | Action | Rationale | Command |
|---|---|---|---|
| P2 | Cross-project sync | Sync is N days stale; N projects may have relevant updates | `/science:sync` |

## After Writing

1. Save to `doc/meta/next-steps-<YYYY-MM-DD>.md`. In delta mode, append to the existing file rather than creating a new one — git tracks history, so overwriting the date-stamped file is acceptable.
2. Offer to create tasks from recommended items: "Create tasks from these suggestions?"
   - If accepted, run `science-tool tasks add` for each recommended task with appropriate priority, type, and related entities
3. Cross-link relevant items in `doc/questions/`.
4. Commit: `git add -A && git commit -m "doc: next steps and gap analysis <date>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:next-steps" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead

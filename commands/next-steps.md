---
description: Synthesize recent progress, analyze coverage gaps, and suggest next actions. Use at session start, when the user says "what should I work on", "next steps", "priorities", "what's next", "gaps", or "what am I missing". Replaces the former research-gaps command.
---

# Next Steps

Synthesize the current state of the project, analyze coverage gaps, and suggest prioritized next actions.
Use `$ARGUMENTS` as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`, `gaps only`.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

**Next-steps home.** Next-steps files are `type: meta` entities and live under
`entities/meta/`, named with a zero-padded numeric prefix:
`entities/meta/<NNNN>-next-steps-<YYYY-MM-DD>.md`. Pick `<NNNN>` as the next free
index in `entities/meta/`. The validator rejects `type: meta` entities placed
outside `entities/meta/`.

Throughout this command, **`<meta-home>`** means `entities/meta/` and
**`<meta-home>/*next-steps-*.md`** matches prior analyses (the glob tolerates the
optional `<NNNN>-` prefix). Resolve this once, up front, and use it for every
read, scan, and write below.

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. **Hypothesis and question status:** run `science project index --format json` to get a compact index of all hypotheses and questions with their titles and statuses. Only read individual files when you need full detail (e.g., to assess evidence quality for a specific hypothesis).
4. `specs/scope-boundaries.md` — project scope
5. `entities/topics/` or equivalent topic coverage files in the doc directory
6. `entities/papers/` — paper coverage
7. `<meta-home>/*next-steps-*.md` — prior next-steps analyses (most recent)

Also run: `git log --oneline -15 --format="%h %s (%cr)"`

## Mode Detection

Check for a prior same-day analysis: scan `<meta-home>/*next-steps-<today's date>*.md`.

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
- **Hypothesis / question status** — use the project index from setup (one-line summary per hypothesis/question). Read individual files only when deeper context is needed.

#### Workflow Runs
- Scan `results/` for `datapackage.json` manifests.
- Report: recent runs (last 7 days), superseded runs, runs with status `draft`.
- Flag any workflow-run that has no corresponding interpretation document.

**Fallback when no manifests exist.** Some projects have rich results without `datapackage.json` files. If `find results/ -name datapackage.json` returns nothing:
- Infer run bundles from `results/**/` directory conventions instead — most commonly dated subdirectories (`results/YYYY-MM-DD-<slug>/` or `results/<slug>/`) containing a `report.md` / `summary.md` / notebook outputs.
- Report: recent bundles by directory mtime (last 7 days), bundles whose name appears superseded by a later one with the same slug, bundles with no linking interpretation under `entities/interpretations/`.
- Be explicit in the output that these are inferred from directory conventions, not declared manifests — readers should not assume datapackage-grade provenance.
- Skip the section entirely if neither manifests nor a recognizable `results/` convention exists; do not pad with low-signal noise.

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

If a prior next-steps analysis exists (`<meta-home>/*next-steps-*.md`), compare against it and surface all three directions:

- **Newly unblocked:** tasks that were blocked but are now actionable. What changed to unblock them?
- **Newly blocked:** tasks that lost a dependency or had assumptions invalidated since the last analysis.
- **Newly irrelevant:** tasks superseded by results or no longer decision-relevant. These are pruning opportunities — removing stale work from the queue is as valuable as adding new work.

This longitudinal view makes progress visible and highlights both forward momentum and pruning opportunities.

### 3c. Task Tracking Gaps

Scan pipeline plans in `entities/plans/` for implementation tasks that are not tracked in `tasks/active.md`. Surface any development work buried in plan documents that should be trackable tasks.

Scan active analysis-facing tasks and inquiries for linked `analysis-plan:<slug>`
artifacts. If none exists and the task is about running, validating, or
pre-registering a data analysis, add a recommended next action to run
`/science:plan-analysis`. Check `entities/analysis-plan/*-analysis-plan.md` before
recommending a new one.

**Archive lag.** Run `science health --format json` and inspect `archive_lag`. When `archive_lag.done_in_active` or `archive_lag.retired_in_active` is non-zero, add a Recommended Next Action:

> Preview with `science tasks archive`, then run `science tasks archive --apply` to move the N done/retired entries from `tasks/active.md` to `tasks/done/YYYY-MM.md`.

If `archive_lag.missing_completed` is non-zero, call those entries out separately so the user backfills `completed:` first — otherwise they route to the current month rather than the month they were actually closed.

### Managed artifact updates

If `science health` shows any managed artifact with status `stale`, surface as a next-step:

> Update `<artifact-name>` from version `<from>` → `<to>`. Run:
>
> ```bash
> science project artifacts update <artifact-name>
> ```
>
> If a migration step ships with the bump, the CLI will surface it interactively.

If status is `locally_modified` or `missing`, point at the corresponding verb (`install` / `update --force --yes`).

### 3c-bis. Stale Task Status Detection (mandatory)

Before recommending next actions, audit task status against on-disk evidence. For each task in `tasks/active.md` with status `proposed`, `blocked`, or `in_progress`, check whether the work appears already done by scanning for any of:

- a result file under `results/` whose path or `datapackage.json` references the task ID
- a doc under `entities/interpretations/`, `entities/findings/`, `entities/reports/`, or `entities/discussions/` whose frontmatter `source_refs` includes the task ID
- recent git commits (since the task was added) whose message body mentions the task ID
- a workflow-run manifest whose `tasks` list includes the task ID

For each match, surface the task in a short `### Status Drift` table:

| Task | Current status | Evidence | Suggested update |
|---|---|---|---|
| t075 | proposed | results/2026-04-09-t075/datapackage.json | mark `done` and write interpretation |

**Also scan recent completions, not just `active.md`.** Work shipped in the current month lives in `tasks/done/<YYYY-MM>.md`, not `active.md` — and the analysis window usually overlaps the current month. Scan `tasks/done/<current-month>.md` (and `<previous-month>.md` when the window crosses a month boundary) for tasks completed inside the window. Without this, recently-shipped work is invisible: a run can wrongly conclude "no movement" or a "stalled program" when tasks in fact completed during the window. A completion found here is *positive* signal — surface it as progress, not drift.

**Cross-check the prior `next-steps` doc.** Read the previous `<meta-home>/*next-steps-*.md` and check each recommendation it made against subsequent commits and `tasks/done/` entries. A recommendation that has since shipped is a "recommendation shipped" win to record — the cross-check detects positive follow-through, not only stalls.

This detection is mandatory — a `next-steps` run that does not perform it must say so explicitly. Drift between code and task status is one of the most consistent failure modes; finding it once during analysis avoids re-litigating the same recommendations across sessions.

### 3d. Strategic Decision Point (if applicable)

If the project is at a fork — a moment where the next direction depends on a choice between competing approaches, depth-first vs breadth-first, or a go/no-go gate — add a "Strategic Decision Point" section that frames:
- What the decision is
- What evidence bears on it
- What the options are and their tradeoffs
- What the recommended path is and why

This captures strategic framing that individual task recommendations don't. Omit if no strategic decision is pending.

### 3e. Weighted Attention Sample

When the backlog is sparse or the user is otherwise blocked and `knowledge/graph.trig`
exists, run:

```bash
science graph attention-sample --limit 5 --format json
```

This samples epistemic entities using graph-derived attention weights:
incoming `bears_on` count, days since review, freshness state, evidence balance,
and an epsilon floor. Treat the sample as a revisiting queue, not a ranked
verdict. Frame `needs-review` or `stale` rows as a review prompt rather than as
evidence that a prior conclusion is wrong.

When recommending work on a `needs-review` entity, name the resolution path:
unchanged review (`science entity review <target-ref>`), amendment
(`sci:amends` from a new conclusion to the old conclusion), or replacement
(`sci:supersedes` plus `status: superseded` on the old conclusion). Propose one
as a candidate next step and add a corresponding task if accepted.

### 4. Suggested Next Steps

Recommend 3-5 actions based on:
- High-impact gaps from the coverage analysis
- Unblocked tasks that were previously blocked
- Highest-priority active tasks without recent commits
- Stale tasks (active but no related activity in >7 days)
- Open high-priority questions that could become tasks
- Weighted attention sample rows from `science graph attention-sample --limit 5 --format json` (when backlog is unclear)

For each suggestion, include:
- The task ID (if it exists) or "new task" if suggesting something not yet tracked
- A brief rationale (1 sentence)
- The suggested command to run (e.g., `/science:research-topic`, `/science:tasks add ...`)

**Design constraints:** If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it as a row in the Recommended Next Actions table with a note to record it in project memory or a design doc.

## Writing

Save output to `<meta-home>/<NNNN>-next-steps-<YYYY-MM-DD>.md` (use the resolved
`<meta-home>` and the `<NNNN>-` numeric prefix). If a file for today already
exists (delta mode), append an `## Update — HH:MM` section instead of creating a
new file.

Set the frontmatter `id` to match the filename-derived canonical id:
`meta:<NNNN>-next-steps-<YYYY-MM-DD>`.

```markdown
---
id: "meta:<NNNN>-next-steps-YYYY-MM-DD"
type: "meta"
title: "Next Steps — YYYY-MM-DD"
status: "active"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
prior: "meta:<NNNN>-next-steps-<predecessor-date>"  # canonical id of predecessor; see "Resolve prior link" below; omit if no predecessor
related: []
---

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

Before writing, run `science sync status` to check cross-project sync staleness.
If sync is stale, include a note in the Recommended Next Actions table:

| Priority | Action | Rationale | Command |
|---|---|---|---|
| P2 | Cross-project sync | Sync is N days stale; N projects may have relevant updates | `/science:sync` |

## After Writing

### Resolve prior link

Before writing the file, list `<meta-home>/*next-steps-*.md`. **Exclude any file dated today** (delta-mode appends to that file rather than creating a new one, so the predecessor must be the most recent file *strictly before* today). From the remaining files, select the one with the lexically-greatest `YYYY-MM-DD` in its filename. Set `prior:` to that file's canonical id — `meta:<NNNN>-next-steps-<that-date>` (read the predecessor's frontmatter `id` rather than reconstructing it). If no predecessor exists (this is the first next-steps file in the project), omit the `prior:` field entirely.

Delta mode (append `## Update — HH:MM` to today's existing file) does **not** change the file's `prior:` — the chain link is per-file, not per-update.

Projects that historically use `prior_analyses: [...]` (e.g. protein-landscape) need not migrate: the validator accepts both shapes and only warns on broken `prior:` links.

### Steps

1. Save to `<meta-home>/[<NNNN>-]next-steps-<YYYY-MM-DD>.md`. In delta mode, append to the existing file rather than creating a new one — git tracks history, so overwriting the date-stamped file is acceptable.
2. Offer to create tasks from recommended items: "Create tasks from these suggestions?"
   - If accepted, run `science tasks add` for each recommended task with appropriate priority, type, and related entities
3. Cross-link relevant items in `entities/questions/`.
4. Commit: `git add -A && git commit -m "doc: next steps and gap analysis <date>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
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

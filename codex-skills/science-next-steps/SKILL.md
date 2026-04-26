---
name: science-next-steps
description: "Synthesize recent progress, analyze coverage gaps, and suggest next actions. Use at session start, when the user says \"what should I work on\", \"next steps\", \"priorities\", \"what's next\", \"gaps\", or \"what am I missing\". Replaces the former research-gaps command."
---

# Next Steps

Converted from Claude command `/science:next-steps`.

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

Synthesize the current state of the project, analyze coverage gaps, and suggest prioritized next actions.
Use the user input as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`, `gaps only`.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. **Hypothesis and question status:** run `science-tool project index --format json` to get a compact index of all hypotheses and questions with their titles and statuses. Only read individual files when you need full detail (e.g., to assess evidence quality for a specific hypothesis).
4. `specs/scope-boundaries.md` — project scope
5. `doc/topics/` or equivalent topic coverage files in the doc directory
6. `doc/papers/` — paper coverage
7. `doc/meta/next-steps-*.md` — prior next-steps analyses (most recent)

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
- **Hypothesis / question status** — use the project index from setup (one-line summary per hypothesis/question). Read individual files only when deeper context is needed.

#### Workflow Runs
- Scan `results/` for `datapackage.json` manifests.
- Report: recent runs (last 7 days), superseded runs, runs with status `draft`.
- Flag any workflow-run that has no corresponding interpretation document.

**Fallback when no manifests exist.** Some projects have rich results without `datapackage.json` files. If `find results/ -name datapackage.json` returns nothing:
- Infer run bundles from `results/**/` directory conventions instead — most commonly dated subdirectories (`results/YYYY-MM-DD-<slug>/` or `results/<slug>/`) containing a `report.md` / `summary.md` / notebook outputs.
- Report: recent bundles by directory mtime (last 7 days), bundles whose name appears superseded by a later one with the same slug, bundles with no linking interpretation under `doc/interpretations/`.
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

If a prior next-steps analysis exists (`doc/meta/next-steps-*.md`), compare against it and surface all three directions:

- **Newly unblocked:** tasks that were blocked but are now actionable. What changed to unblock them?
- **Newly blocked:** tasks that lost a dependency or had assumptions invalidated since the last analysis.
- **Newly irrelevant:** tasks superseded by results or no longer decision-relevant. These are pruning opportunities — removing stale work from the queue is as valuable as adding new work.

This longitudinal view makes progress visible and highlights both forward momentum and pruning opportunities.

### 3c. Task Tracking Gaps

Scan pipeline plans in `doc/plans/` for implementation tasks that are not tracked in `tasks/active.md`. Surface any development work buried in plan documents that should be trackable tasks.

**Archive lag.** Run `science-tool health --format json` and inspect `archive_lag`. When `archive_lag.done_in_active` or `archive_lag.retired_in_active` is non-zero, add a Recommended Next Action:

> Preview with `science-tool tasks archive`, then run `science-tool tasks archive --apply` to move the N done/retired entries from `tasks/active.md` to `tasks/done/YYYY-MM.md`.

If `archive_lag.missing_completed` is non-zero, call those entries out separately so the user backfills `completed:` first — otherwise they route to the current month rather than the month they were actually closed.

### Managed artifact updates

If `science-tool health` shows any managed artifact with status `stale`, surface as a next-step:

> Update `<artifact-name>` from version `<from>` → `<to>`. Run:
>
> ```bash
> science-tool project artifacts update <artifact-name>
> ```
>
> If a migration step ships with the bump, the CLI will surface it interactively.

If status is `locally_modified` or `missing`, point at the corresponding verb (`install` / `update --force --yes`).

### 3c-bis. Stale Task Status Detection (mandatory)

Before recommending next actions, audit task status against on-disk evidence. For each task in `tasks/active.md` with status `proposed`, `blocked`, or `in_progress`, check whether the work appears already done by scanning for any of:

- a result file under `results/` whose path or `datapackage.json` references the task ID
- a doc under `doc/interpretations/`, `doc/findings/`, `doc/reports/`, or `doc/discussions/` whose frontmatter `source_refs` includes the task ID
- recent git commits (since the task was added) whose message body mentions the task ID
- a workflow-run manifest whose `tasks` list includes the task ID

For each match, surface the task in a short `### Status Drift` table:

| Task | Current status | Evidence | Suggested update |
|---|---|---|---|
| t075 | proposed | results/2026-04-09-t075/datapackage.json | mark `done` and write interpretation |

This detection is mandatory — a `next-steps` run that does not perform it must say so explicitly. Drift between code and task status is one of the most consistent failure modes; finding it once during analysis avoids re-litigating the same recommendations across sessions.

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
- The suggested command to run (e.g., `science-research-topic`, `science-tasks add ...`)

**Design constraints:** If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it as a row in the Recommended Next Actions table with a note to record it in project memory or a design doc.

## Writing

Save output to `doc/meta/next-steps-<YYYY-MM-DD>.md`. If a file for today already exists (delta mode), append an `## Update — HH:MM` section instead of creating a new file.

```markdown
---
id: "meta:next-steps-YYYY-MM-DD"
type: "meta"
title: "Next Steps — YYYY-MM-DD"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
prior: "meta:next-steps-<predecessor-date>"  # see "Resolve prior link" below; omit if no predecessor
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

Before writing, run `science-tool sync status` to check cross-project sync staleness.
If sync is stale, include a note in the Recommended Next Actions table:

| Priority | Action | Rationale | Command |
|---|---|---|---|
| P2 | Cross-project sync | Sync is N days stale; N projects may have relevant updates | `science-sync` |

## After Writing

### Resolve prior link

Before writing the file, list `doc/meta/next-steps-*.md`. **Exclude any file dated today** (delta-mode appends to that file rather than creating a new one, so the predecessor must be the most recent file *strictly before* today). From the remaining files, select the one with the lexically-greatest `YYYY-MM-DD` in its filename. Set `prior: meta:next-steps-<that-date>` in the new file's frontmatter. If no predecessor exists (this is the first next-steps file in the project), omit the `prior:` field entirely.

Delta mode (append `## Update — HH:MM` to today's existing file) does **not** change the file's `prior:` — the chain link is per-file, not per-update.

Projects that historically use `prior_analyses: [...]` (e.g. protein-landscape) need not migrate: the validator accepts both shapes and only warns on broken `prior:` links.

### Steps

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

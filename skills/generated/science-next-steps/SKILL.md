---
name: science-next-steps
description: "Synthesize recent progress, analyze coverage gaps, and suggest next actions. Use at session start, when the user says \"what should I work on\", \"next steps\", \"priorities\", \"what's next\", \"gaps\", or \"what am I missing\". Replaces the former research-gaps command."
user-invocable: true
---

# Next Steps

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
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

Synthesize the current state of the project, analyze coverage gaps, and suggest prioritized next actions.
Use the user input as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`, `gaps only`.

## Setup


**Next-steps home.** Next-steps files are transient project-state records, **not**
knowledge-graph entities: they live under `doc/meta/` (not `entities/`), carry
`doc_kind: meta` rather than an entity `kind:`, and are named
`doc/meta/next-steps-<YYYY-MM-DD>.md`. They contribute no triples and are excluded
from the graph revision manifest by default, so writing one never stales the graph.

Throughout this command, **`<meta-home>`** means `doc/meta/` and
**`<meta-home>/*next-steps-*.md`** matches prior analyses. Resolve this once, up
front, and use it for every read, scan, and write below.

**Boundary with tasks.** A next-steps run produces recommendations, not task
records. Do not treat `<meta-home>` files as the durable task queue. Convert
recommendations into `science tasks add ...` only after user acceptance.
Accepted work belongs in `science tasks ...` and `tasks/active.md`.

Additionally, gather (skip any source that doesn't exist):
1. Run `science tasks list --status active` (or `--all`) for the active task queue.
2. Recent completed tasks: run `science tasks list --status done --since <window-start>`.
3. **Hypothesis and question status:** run `science project index --format json` to get a compact index of all hypotheses and questions with their titles and statuses. Only read individual files when you need full detail (e.g., to assess evidence quality for a specific hypothesis).
4. Project scope — resolve the path with `science project spec-path --slug scope-boundaries`, then read it
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
- Recently completed tasks (`science tasks list --status done --since <window-start>`)
- Recent git commits

Group by theme (research, development, documentation) rather than listing chronologically.
Keep to 5-8 bullet points maximum.

### 2. Current State

From `science tasks list` output, show:
- **P0 tasks** (critical path) — full detail
- **P1 tasks** (active work) — title and status
- **Blocked tasks** — what's blocking them
- **Hypothesis / question status** — use the project index from setup (one-line summary per hypothesis/question). Read individual files only when deeper context is needed.

#### Workflow Runs
- List workflow-run entities with `science entity list workflow-run --format json`; read result
  details from each run's `manifest_path` manifest.
- Report: recent runs (last 7 days) and runs with status `failed`
  (`science entity list workflow-run --status failed --format json`).
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

Scan pipeline plans in `entities/plans/` for implementation tasks that are not tracked in the task queue (`science tasks list --all`). Surface any development work buried in plan documents that should be trackable tasks.

Scan active analysis-facing tasks and inquiries for linked `plan:<stem>` analysis
plans (`entities/plans/*-analysis-plan.md` with `plan_kind: analysis-plan`). If
none exists and the task is about running, validating, or pre-registering a data
analysis, add a recommended next action to run `science-plan-analysis`. Check
`entities/plans/*-analysis-plan.md` before recommending a new one.

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

Before recommending next actions, audit task status against on-disk evidence. For each task returned by `science tasks list --status proposed`, `--status blocked`, or `--status active` (or `science tasks list --all` to gather them together), check whether the work appears already done by scanning for any of:

- a result file under `results/` whose path or `datapackage.json` references the task ID
- a doc under `entities/interpretations/`, `entities/findings/`, `entities/reports/`, or `entities/discussions/` whose frontmatter `source_refs` includes the task ID
- recent git commits (since the task was added) whose message body mentions the task ID
- a workflow-run manifest whose `tasks` list includes the task ID

For each match, surface the task in a short `### Status Drift` table:

| Task | Current status | Evidence | Suggested update |
|---|---|---|---|
| t075 | proposed | results/2026-04-09-t075/datapackage.json | mark `done` and write interpretation |

**Also check recent completions, not just the active queue.** Work shipped in done files lives in `tasks/done/<YYYY-MM>.md`, not `active.md`; derive the recent-progress window first: use the date of the prior `next-steps` analysis when one exists, otherwise use the explicit lookback window for this run. Then run `science tasks list --status done --since <window-start>` — under the hood this will scan every `tasks/done/YYYY-MM.md` file whose month intersects that window, including prior-month files when the window crosses a month boundary, so you don't need to open the archive files yourself. Do not stop at the current month file or assume the prior month is irrelevant just because it is large. For each returned row whose `completed:` date falls inside the window, treat those rows as recent progress, not status drift. Without this, recently-shipped work is invisible: a run can wrongly conclude "no movement" or a "stalled program" when tasks in fact completed during the window.

**Cross-check the prior `next-steps` doc.** Read the previous `<meta-home>/*next-steps-*.md` and check each recommendation it made against subsequent commits and recently-closed tasks (`science tasks list --status done --since <window-start>`). A recommendation that has since shipped is a "recommendation shipped" win to record — the cross-check detects positive follow-through, not only stalls.

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

### 3f. Self-Improvement Loop (mandatory)

The reflection→improvement loop only compounds if the system prompts it, rather
than relying on the operator to remember. Surface two classes here, the way stale
entities are already surfaced above.

**Unreflected failures.** Scan for failure signatures that have no linked
reflection, and recommend `science-post-mortem` for each:

- a pre-registration amendment recording a **protocol deviation**, or observed
  values that leaked before the freeze point;
- a **gate failure** or an `inconclusive-for-protocol` verdict (a check that
  stopped an analysis);
- a workflow run with status `failed` (already surfaced under Workflow Runs above)
  with no interpretation and no post-mortem.

A failure is *reflected* when a feedback entry references it. Cross-check the
project's feedback with `science feedback list --project <project-id> --format json`
(post-mortem writes there). List every failure signature with **no** corresponding
feedback entry as an "unreflected failure" and add a Recommended Next Action:

> Reflect on `<failure>` with `science-post-mortem <failure>` — no lesson has been
> filed for it, so the fix-and-move-on pull will lose it.

If every failure signature already has a linked entry, say so; do not pad. If the
scan cannot run (no pre-registrations, no `results/` runs), state that explicitly.

**Unconsumed positives.** A `positive` feedback entry records a validated property
worth locking in, but the category has no consumption path on its own. Run:

```bash
science feedback regression-candidates --format json
```

For each row, recommend either seeding a regression test
(`science feedback scaffold-test <id>`, then replace the scaffold with a real
failing test) or, when the positive praises an *undocumented* property of a
command or template, routing it into that surface's guidance. Skip silently only
when there are no open positives.

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
- The suggested command to run (e.g., `science-research-topic`, `science-tasks add ...`)

**Design constraints:** If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it as a row in the Recommended Next Actions table with a note to record it in project memory or a design doc.

## Writing

Save output to `<meta-home>/next-steps-<YYYY-MM-DD>.md`. If a file for today
already exists (delta mode), append an `## Update — HH:MM` section instead of
creating a new file.

Set the frontmatter `id` to match the filename-derived canonical id:
`meta:next-steps-<YYYY-MM-DD>`.

```markdown
---
doc_kind: "meta"
id: "meta:next-steps-YYYY-MM-DD"
title: "Next Steps — YYYY-MM-DD"
status: "active"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
prior: "meta:next-steps-<predecessor-date>"  # canonical id of predecessor; see "Resolve prior link" below; omit if no predecessor
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

> **Note:** Next-steps output is a transient planning aid by default. Save it when the user asks, when it records a non-obvious project decision, or when another durable artifact needs to cite it.

## Cross-Project Sync Check

Before writing, run `science sync status` to check cross-project sync staleness.
If sync is stale, include a note in the Recommended Next Actions table:

| Priority | Action | Rationale | Command |
|---|---|---|---|
| P2 | Cross-project sync | Sync is N days stale; N projects may have relevant updates | `science-sync` |

## After Writing

### Resolve prior link

Before writing the file, list `<meta-home>/*next-steps-*.md`. **Exclude any file dated today** (delta-mode appends to that file rather than creating a new one, so the predecessor must be the most recent file *strictly before* today). From the remaining files, select the one with the lexically-greatest `YYYY-MM-DD` in its filename. Set `prior:` to that file's canonical id — `meta:next-steps-<that-date>` (read the predecessor's frontmatter `id` rather than reconstructing it). If no predecessor exists (this is the first next-steps file in the project), omit the `prior:` field entirely.

Delta mode (append `## Update — HH:MM` to today's existing file) does **not** change the file's `prior:` — the chain link is per-file, not per-update.

Projects that historically use `prior_analyses: [...]` (e.g. protein-landscape) need not migrate: the validator accepts both shapes and only warns on broken `prior:` links.

### Steps

1. Save to `<meta-home>/next-steps-<YYYY-MM-DD>.md`. In delta mode, append to the existing file rather than creating a new one — git tracks history, so overwriting the date-stamped file is acceptable.
2. Offer to create tasks from recommended items: "Create tasks from these suggestions?"
   - If accepted, run `science tasks add` for each recommended task with appropriate priority, type, and related entities
3. Cross-link relevant items in `entities/questions/`.
4. Do not commit routine next-steps files unless the user explicitly requested a commit. If a commit is requested, use `git add -A && git commit -m "doc: next steps and gap analysis <date>"`.

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

# Project Curation Sweep

**Date:** 2026-04-21
**Status:** Draft

## Motivation

Science projects accumulate durable research memory: questions, hypotheses, interpretations, paper summaries, topic notes, tasks, DAG edge annotations, discussions, pipeline plans, datasets, and synthesis reports. These artifacts are valuable, but over time their useful content can become effectively forgotten:

- older summaries are not linked to newer hypotheses or questions;
- one-off findings never become follow-up tasks, interpretations, or DAG evidence;
- tasks and hypotheses drift away from newer results;
- topics split into overlapping fragments;
- paper notes and discussions contain insights that later questions should surface but do not;
- graph and frontmatter links under-represent the real conceptual connections in the project.

`/science:big-picture` produces a high-level synthesis. `/science:next-steps` prioritizes future work. `/science:review-tasks` audits the backlog. None of these performs a systematic memory curation pass.

## Goal

Introduce `/science:curate`, an agent-led project memory curation command. Its purpose is to inspect the accumulated project corpus, repair obvious connective tissue when safe, and produce a durable curation ledger of forgotten insights, missed connections, drift, duplication, and follow-up decisions.

The command should behave like a careful research librarian and project maintainer, not like an automated linter. CLI helpers gather inventories and candidate signals; the agent performs the semantic judgement.

## Scope

### In scope (v1)

- New command `/science:curate`.
- New Codex skill `science-curate`.
- Agent-led workflow that reads targeted source artifacts and writes a curation ledger.
- Optional high-confidence, small curation edits after explicit user approval or an explicit apply flag.
- A narrow `science-tool curate inventory` helper for deterministic corpus inventory and candidate collection.
- Reuse of existing helpers: `science-tool health`, graph summaries, `big-picture resolve-questions`, task listing, DAG staleness/audit surfaces, sync status, and git history.
- Curation ledger under `doc/meta/curation/curation-sweep-YYYY-MM-DD.md`.
- End-of-run self-reflection section that captures possible improvements to the curation command, skill, prompts, or CLI helpers.

### Out of scope (v1)

- Fully automated semantic curation.
- Bulk rewrites across the corpus.
- Automatic hypothesis merging, task retirement, or DAG status changes without human approval.
- Replacing `/science:big-picture`, `/science:next-steps`, `/science:health`, or `/science:review-tasks`.
- Generating canonical project synthesis. Curation findings can feed synthesis, but the output is a ledger and action queue, not the project narrative.
- Building an embedding search index. Useful later, but not required for v1.

## Command Interface

```text
/science:curate [--dry-run] [--no-write] [--scope <scope>] [--since <date>] [--apply-obvious] [--commit]
```

- Default: run an agent-led sweep, do not mutate files unless the agent reaches an explicit approval checkpoint.
- `--dry-run`: no source-artifact edits; write the curation ledger unless `--no-write` is also set.
- `--no-write`: print the ledger preview only. Do not create or update `doc/meta/curation/`.
- `--scope <scope>`: restrict the sweep. Suggested scopes: `all`, `links`, `drift`, `forgotten-insights`, `tasks`, `dag`, `topics`, `papers`.
- `--since <date>`: bias toward artifacts or changes after a date while still allowing older linked artifacts to be read when relevant.
- `--apply-obvious`: permits direct application of high-confidence mechanical edits that meet the safety rules below. Every edit must be recorded in the ledger.
- `--commit`: after successful verification, commit the ledger and any approved edits.

## Safety Model

The command classifies findings by confidence and mutation risk.

### High-confidence mechanical fixes

Examples:

- a broken reference has exactly one alias-resolved canonical replacement;
- a document clearly cites a task or interpretation in prose but lacks the matching `source_refs` or `related` entry;
- a task is still active but directly references a result or interpretation proving completion;
- a duplicate topic alias is already represented in the local entity registry.

Allowed action:

- In default mode, present these as "obvious fixes" and ask for approval before editing.
- With `--apply-obvious`, apply them directly if each change is small, local, and non-judgmental.

### Medium-confidence curation proposals

Examples:

- an old paper summary appears relevant to a newer hypothesis;
- a discussion contains a useful insight that should become a question, task, or interpretation link;
- an interpretation probably belongs in a `prior_interpretations` chain;
- a DAG edge may need a newer task as evidence, but the edge status is unchanged.

Allowed action:

- Do not auto-apply.
- Record a proposed edit or follow-up task with evidence and rationale.

### Low-confidence research judgement

Examples:

- a hypothesis should be merged, split, or retired;
- a current project direction should change;
- an old result contradicts a working model;
- a topic taxonomy should be reorganized.

Allowed action:

- Never auto-apply.
- Record as a pending decision with the supporting artifacts and a concise framing.

## Artifact Layout

```text
doc/meta/curation/
└── curation-sweep-YYYY-MM-DD.md
```

The curation ledger is durable because otherwise the sweep itself becomes another forgotten analysis. The ledger should be concise but evidence-rich.

Suggested frontmatter:

```yaml
---
type: "curation-sweep"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
scope: "all"
since: null
mode: "dry-run" | "propose" | "apply-obvious"
applied_changes: <int>
pending_decisions: <int>
---
```

Suggested body:

1. **Executive Summary** - 5-8 bullets describing what changed, what was found, and what needs judgement.
2. **Corpus Inventory** - document counts and notable coverage gaps by artifact class.
3. **Forgotten Insights** - older artifacts that matter to current questions, hypotheses, or tasks.
4. **Missed Connections** - proposed or applied `related`, `source_refs`, `prior_interpretations`, task, DAG, or topic links.
5. **Drift** - places where current docs, tasks, DAGs, or summaries lag behind newer evidence.
6. **Duplication And Fragmentation** - overlapping topics, repeated questions, repeated paper summaries, or parallel notes.
7. **Actioned Fixes** - exact files changed, before/after summary, and rationale.
8. **Pending Decisions** - items that need user judgement.
9. **Suggested Follow-Ups** - task additions, commands to run, or synthesis updates.
10. **Self-Reflection** - improvements noticed for `/science:curate`, its skill, prompts, or CLI helpers.

## Workflow

### Phase 1: Setup and inventory

Follow the standard Science command preamble. Then run deterministic inventory and context commands:

```bash
uv run science-tool curate inventory --project-root . --format json
uv run science-tool health --project-root . --format json
uv run science-tool tasks list --format json
uv run science-tool big-picture resolve-questions --project-root .
uv run science-tool sync status
git log --oneline -30 --format="%h %s (%cr)"
```

If DAG tooling is present and the project has DAGs:

```bash
uv run science-tool dag audit --json
```

The inventory helper should not decide what to change. It should return compact facts:

- artifact counts by directory and type;
- recently modified and long-idle artifacts;
- frontmatter fields present or missing;
- unresolved refs and alias-resolvable refs if available;
- candidate duplicate titles or IDs;
- documents with dense outbound links and documents with none;
- candidate stale task evidence from direct source_refs or result manifests.

### Phase 2: Candidate triage

The agent groups candidates into curation themes and chooses a bounded reading set. The goal is not to read every file. The agent should read:

- artifacts named by inventory findings;
- high-priority or recently active hypotheses and questions;
- old artifacts with surprisingly high relevance to live entities;
- prior curation, next-steps, status, and synthesis docs if they exist;
- source docs needed to verify a proposed fix.

The agent should prefer source artifacts over generated reports when judging whether to edit canonical metadata.

### Phase 3: Semantic curation

For each finding, the agent records:

- finding class: forgotten insight, missed connection, drift, duplication, pending decision;
- source artifact(s);
- target artifact(s);
- proposed action;
- confidence: high, medium, low;
- whether it was applied;
- verification evidence.

For obvious fixes, the agent may apply small edits only when the safety model permits it. It must avoid "compatibility" layers, placeholder artifacts, and broad rewrites. It should preserve the original artifact's function and wording unless the curation target is explicitly metadata cleanup.

### Phase 4: Ledger write

Write or update `doc/meta/curation/curation-sweep-YYYY-MM-DD.md`.

If a same-day ledger exists, append a timestamped update section rather than overwriting earlier findings. This mirrors `next-steps` delta behavior and prevents losing decisions made earlier in the day.

### Phase 5: Verification

After any edits, run:

```bash
uv run --frozen ruff format .
uv run --frozen ruff check .
uv run --frozen pyright
uv run science-tool graph audit --project-root . --format json
```

For docs-only edits where Python files are untouched, the agent may skip Python format/type checks but must say so. It should always run the graph/source audit if metadata links changed.

### Phase 6: Self-reflection

At the end of the sweep, the agent must answer:

> What did this curation sweep make harder than it should have been? Note any improvements to `/science:curate`, the `science-curate` skill, agent prompts, inventory helpers, graph surfaces, entity metadata, or project conventions that would make future curation more accurate, less noisy, or easier to verify.

The response belongs in the ledger's **Self-Reflection** section. It should be operational: name the rough problem, where it appeared, and the smallest improvement that would help next time.

## Relationship To Existing Commands

| Command | Relationship |
|---|---|
| `/science:big-picture` | Consumes curated project memory better after `/science:curate`; remains the synthesis generator. |
| `/science:next-steps` | Uses curation findings as inputs to recommendations; remains forward-looking. |
| `/science:review-tasks` | Overlaps on stale task detection, but `/science:curate` is broader and semantic. |
| `/science:health` | Provides structural health signals consumed during inventory. |
| `/science:update-graph` | Applies graph/materialization repairs after curation changes source metadata. |
| `/science:dag-audit` | Handles detailed DAG evidence drift; `/science:curate` can surface candidates and defer to DAG audit. |

## Acceptance Criteria

- Running `/science:curate --dry-run` on a project creates or prints a ledger with the required sections.
- The sweep distinguishes applied fixes, proposed edits, and pending decisions.
- High-confidence edits are small, local, and evidence-backed.
- Medium- and low-confidence findings are not auto-applied.
- The command records enough provenance that a user can inspect any finding without rerunning the whole sweep.
- The self-reflection section exists and contains at least one concrete improvement opportunity or explicitly says no improvement was noticed.
- On fixture projects, the inventory helper produces deterministic JSON and does not require network access.

## Future Work

- Add embedding-backed semantic retrieval for older notes and paper summaries.
- Add a machine-readable curation ledger companion file for trend analysis across sweeps.
- Add a `science-tool curate diff` helper to compare two curation ledgers.
- Add project-level recurring curation cadence reminders.
- Feed high-quality forgotten-insight findings into `/science:big-picture` bundle assembly.

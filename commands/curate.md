---
description: Agent-led project memory curation sweep. Surfaces forgotten insights, missed links, drift, duplication, safe fixes, and pending decisions across a Science project.
---

# Project Curation Sweep

Run an agent-led curation pass across the project corpus. The CLI helpers are evidence-gathering tools; the agent performs semantic judgement and decides what, if anything, should change.

Use `$ARGUMENTS` as optional scope filters, for example: `all`, `links`, `drift`, `forgotten-insights`, `tasks`, `dag`, `topics`, `papers`, `--since 2026-04-01`, or `--apply-obvious`.

See the design spec at `docs/specs/2026-04-21-project-curation-design.md` for full semantics.

## Flags

Parse `$ARGUMENTS` for:

- `--dry-run` - do not write source edits; write the curation ledger unless `--no-write` is also set.
- `--no-write` - print the ledger preview only. Do not create or update `doc/meta/curation/`.
- `--scope <scope>` - restrict the sweep to a narrow curation slice.
- `--since <date>` - bias the sweep toward activity after `<date>` while still allowing older linked artifacts to be read.
- `--apply-obvious` - allow only high-confidence, small, local, evidence-backed metadata edits.
- `--commit` - stage written files and commit with `feat(curate)` / `doc(curate)`-style provenance as appropriate.

## Phase 1: Setup and inventory

Follow the standard Science command preamble.

Then gather deterministic evidence:

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

The inventory helper should return compact facts only:

- artifact counts by class;
- recently modified and long-idle artifacts;
- missing `related` / `source_refs` signals;
- documents with no outbound links;
- unresolved refs and obvious alias-resolutions if available;
- candidate stale-task evidence from direct source refs or result manifests.

## Phase 2: Candidate triage

Group findings into curation themes and choose a bounded reading set. Read targeted source artifacts, not the entire corpus.

Prefer source documents over generated summaries when deciding whether a metadata edit is warranted.

Useful targets include:

- the files named by inventory findings;
- high-priority hypotheses, questions, and tasks;
- old papers, topics, discussions, interpretations, and plans that look newly relevant;
- prior curation, status, next-steps, synthesis, and task-review docs when they help verify drift.

## Phase 3: Semantic curation

For each finding, record:

- finding class: forgotten insight, missed connection, drift, duplication, or pending decision;
- source artifact(s);
- target artifact(s);
- proposed action;
- confidence: high, medium, low;
- whether it was applied;
- verification evidence.

Safety rules:

- High-confidence mechanical fixes are approval-gated by default. With `--apply-obvious`, only small, local, evidence-backed edits are allowed.
- Medium-confidence proposals are recorded, not auto-applied.
- Low-confidence research judgement is never auto-applied.

Keep fixes narrow. Do not introduce compatibility layers, placeholders, or broad rewrites. Preserve the artifact's existing role unless the change is explicitly metadata cleanup.

## Phase 4: Ledger write

Write or update `doc/meta/curation/curation-sweep-YYYY-MM-DD.md`.

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

- **Executive Summary** - 5-8 bullets on what changed, what drift was found, and what still needs judgement.
- **Corpus Inventory** - counts and notable coverage gaps by artifact class.
- **Forgotten Insights** - older artifacts that matter to current questions, hypotheses, or tasks.
- **Missed Connections** - proposed or applied `related`, `source_refs`, `prior_interpretations`, task, DAG, or topic links.
- **Drift** - docs, tasks, DAGs, or summaries that lag behind newer evidence.
- **Duplication and Fragmentation** - overlapping topics, repeated questions, repeated summaries, or parallel notes.
- **Actioned Fixes** - exact files changed, with rationale.
- **Pending Decisions** - items that need user judgement.
- **Suggested Follow-Ups** - tasks, commands, or synthesis updates to queue next.
- **Self-Reflection** - improvements noticed for `/science:curate`, the skill, prompts, inventory helpers, graph surfaces, entity metadata, or conventions.

If a same-day ledger already exists, append a timestamped update section rather than overwriting prior observations.

## Phase 5: Verification

After edits:

```bash
uv run --frozen ruff format .
uv run --frozen ruff check .
uv run --frozen pyright
uv run science-tool graph audit --project-root . --format json
```

If the run is docs-only and no Python files changed, note that format/type checks were skipped. If metadata links changed, still run the graph/source audit.

## Phase 6: Self-reflection

At the end of the sweep, answer this prompt in the ledger's **Self-Reflection** section:

> What did this curation sweep make harder than it should have been? Note any improvements to `/science:curate`, the `science-curate` skill, agent prompts, inventory helpers, graph surfaces, entity metadata, or project conventions that would make future curation more accurate, less noisy, or easier to verify.

Be concrete. Name the friction, where it appeared, and the smallest improvement that would help next time.

## After Writing

1. Save the ledger to `doc/meta/curation/curation-sweep-YYYY-MM-DD.md` unless `--no-write` is set.
2. If `--dry-run` is set, do not mutate source files; only print the intended ledger and action summary.
3. If the sweep produced safe obvious fixes, ask before applying them unless `--apply-obvious` was explicitly given.
4. If `--commit` is set, commit the written files after verification.

## Relationship To Existing Commands

| Command | Relationship |
|---|---|
| `/science:big-picture` | Uses curated project memory as input to synthesis; `/science:curate` repairs the memory layer. |
| `/science:next-steps` | Consumes curation findings as one input to future priorities. |
| `/science:review-tasks` | Overlaps on stale tasks, but `/science:curate` is broader and semantic. |
| `/science:health` | Supplies structural health signals during inventory. |
| `/science:update-graph` | Applies graph/materialization repairs after curation changes source metadata. |
| `/science:dag-audit` | Handles detailed DAG drift; `/science:curate` can surface candidates and defer to DAG audit. |


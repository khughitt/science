---
name: science-curate
description: "Run an agent-led project memory curation sweep. Use when the user says curate, curation sweep, forgotten insights, missed connections, drift, cleanup research memory, or explicitly references `science-curate` or `/science:curate`."
---

# Project Curation Sweep

Converted from Claude command `/science:curate`.

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

Run an agent-led curation pass across the project corpus. The CLI helpers are
evidence-gathering tools; the agent performs semantic judgement and decides what,
if anything, should change.

Use `$ARGUMENTS` as optional scope filters, for example: `all`, `links`, `drift`,
`forgotten-insights`, `tasks`, `dag`, `topics`, `papers`, `--since 2026-04-01`,
or `--apply-obvious`.

See the design spec at `docs/specs/2026-04-21-project-curation-design.md` for
full semantics.

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

Group findings into curation themes and choose a bounded reading set. Read targeted
source artifacts, not the entire corpus.

Prefer source documents over generated summaries when deciding whether a metadata
edit is warranted.

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

Keep fixes narrow. Do not introduce compatibility layers, placeholders, or broad
rewrites. Preserve the artifact's existing role unless the change is explicitly
metadata cleanup.

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

If a same-day ledger already exists, append a timestamped update section rather
than overwriting prior observations.

## Phase 5: Verification

After edits:

```bash
uv run --frozen ruff format .
uv run --frozen ruff check .
uv run --frozen pyright
uv run science-tool graph audit --project-root . --format json
```

If the run is docs-only and no Python files changed, note that format/type checks
were skipped. If metadata links changed, still run the graph/source audit.

## Phase 6: Self-reflection

At the end of the sweep, answer this prompt in the ledger's **Self-Reflection** section:

> What did this curation sweep make harder than it should have been? Note any improvements to `/science:curate`, the `science-curate` skill, agent prompts, inventory helpers, graph surfaces, entity metadata, or project conventions that would make future curation more accurate, less noisy, or easier to verify.

Be concrete. Name the friction, where it appeared, and the smallest improvement that would help next time.

## After Writing

1. Save the ledger to `doc/meta/curation/curation-sweep-YYYY-MM-DD.md` unless `--no-write` is set.
2. If `--dry-run` is set, do not mutate source files; the ledger may still be written unless `--no-write` is set, and the output should summarize the intended ledger and action plan.
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

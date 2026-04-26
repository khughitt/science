---
name: science-status
description: "Show a curated project orientation — active hypotheses, open questions, uncertainty hotspots, recent activity, and next steps. Use at the start of a session or when the user says \"where are we\", \"what's the status\", or \"catch me up\"."
---

# Project Status

Converted from Claude command `/science:status`.

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

Print a curated orientation for the current research project.

The default stance is skeptical:
- hypotheses are organizing conjectures
- claims carry uncertainty
- evidence updates belief
- sparse or contested regions deserve attention

Output goes to the terminal unless the user input contains `--save`.

## Setup

1. Read `specs/research-question.md`.
2. Read `science.yaml`.
3. If present, read `docs/proposition-and-evidence-model.md`.

## Sections

Keep output under ~100 lines.

### 1. Project Identity

From `science.yaml` and `specs/research-question.md`:
- project name and status
- research question
- tags

### 2. Active Hypotheses

From `specs/hypotheses/*.md`:
- list each hypothesis with ID, short title, and current status
- describe it briefly as an organizing conjecture, not a proven result
- highlight which ones are under active investigation

### 3. Open Questions

From `doc/questions/*.md`:
- list the top 5 by priority
- include the question text and type

### 4. Claim And Graph Uncertainty

When `knowledge/graph.trig` exists:

1. Run:

```bash
science-tool graph project-summary --format json
science-tool graph question-summary --format json  # full by default; add --top to narrow
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph neighborhood-summary --format json
science-tool graph uncertainty --format json
science-tool graph gaps --format json
```

For `software` projects, skip `project-summary` for now and start from `question-summary` / `inquiry-summary`.

2. Surface:
- research project summary
- high-priority questions from the full question rollup
- high-priority inquiries
- contested claims
- single-source claims
- claims lacking empirical data evidence
- evidence-type mix when relevant
- high-uncertainty neighborhoods
- structurally fragile areas

3. Prefer the higher-level drill path:
- `project-summary` for the top-level rollup on `research` projects only
- `question-summary` for the full question rollup; add `--top` to narrow it
- `inquiry-summary` for research-thread prioritization
- `dashboard-summary` and `neighborhood-summary` for exact weak points
- `uncertainty` and `gaps` as secondary support views rather than the main dashboard

4. If the graph does not expose claim-backed evidence summaries yet, say that the project appears only partially migrated and treat the uncertainty section as provisional.

Also run:

```bash
science-tool health --project-root . --format json
```

Surface, at minimum:

- proposition `claim_layer` coverage,
- causal-leaning proposition `identification_strength` coverage,
- unsupported mechanistic narratives still flagged by the migration helper,
- proxy-mediated propositions still missing `measurement_model`,
- rival-model packets missing discriminating predictions or overstating a `current_working_model` without real adjudication evidence.

Treat `science-tool graph migrate` as an audit-first command. Reach for `--apply` only after the
preview confirms that the proposed rewrites and local-source scaffolding are actually wanted.

If high-impact claims still carry only one visible `independence_group`, call that out explicitly as a fragility note even if the project has not yet promoted it into a first-class dashboard metric.

### 5. Recent Activity

Run:

```bash
git log --oneline -10 --format="%h %s (%cr)"
```

Show recent project movement.

### 6. Staleness Warnings

Flag:
- stale tasks
- old untouched hypotheses
- graph/doc drift if the graph changed but interpretation/docs did not
- **task archive lag**: when `science-tool health --format json` shows non-zero
  `archive_lag.done_in_active` or `archive_lag.retired_in_active`, surface it as:
  > N done/retired task(s) still in `tasks/active.md`. Run `science-tool tasks archive --apply`
  > to move them to `tasks/done/YYYY-MM.md`.
  If `archive_lag.missing_completed` is non-zero, call out that those entries need a
  `completed:` date backfilled before archiving so they route to the correct month.

### Managed artifacts

If `science-tool health` reports any managed artifact whose status is not `current` (or `pinned`), surface it:

- `<artifact-name>: <status>` — `<detail>`
  - For `stale`: "Run `science-tool project artifacts update <name>` to refresh."
  - For `locally_modified`: "Run `science-tool project artifacts diff <name>` to inspect; `update --force --yes` to overwrite."
  - For `missing`: "Run `science-tool project artifacts install <name>` to install."
  - For `pinned_but_locally_modified`: "Pin no longer protects what was pinned. Run `diff` then either `update --force --yes` or `unpin`."

The list comes from the `managed_artifacts` field of the health report.

**Cross-project sync staleness:**

Run `science-tool sync status` to check when the last cross-project sync was performed.
If sync is stale (over the configured threshold), mention it:

> Cross-project sync is N days stale. Run `science-sync` to align with N other registered projects.

If the current project has new entities since last sync, also mention:

> This project has N new entities since last sync.

### 7. Document Inventory

Count key document classes:
- topics
- papers
- questions
- methods
- datasets
- discussions
- interpretations
- hypotheses

### 8. Next Steps

From tasks, graph uncertainty, and recent activity, show:
- the top few high-value next actions
- where uncertainty reduction is most likely to pay off
- blocked tasks or missing evidence
- which findings belong in `doc/reports/` or `doc/interpretations/`
- which follow-up actions should be added under `tasks/`

## Output Format

Use rich terminal output:
- section headers
- tables where useful
- compact graph summaries when relevant

## Optional `--save`

If the user explicitly asks to save the output or includes `--save`:
- save to `doc/meta/status-snapshot-YYYY-MM-DD.md`
- commit the snapshot

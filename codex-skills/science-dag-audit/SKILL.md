---
name: science-dag-audit
description: "Audit causal DAG freshness — runs drift detection read-only, surfaces stale edges + unpropagated tasks + broken refs, and applies fixes only on explicit user approval. Use on a 4-weekly cadence or after any major verdict interpretation lands. Also use when the user explicitly asks for `science-dag-audit` or references `/science:dag-audit`."
---

# DAG Audit

Converted from Claude command `/science:dag-audit`.

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

Run a drift-based audit of the project's causal DAG figures. Surface edges that
have drifted out of date (new evidence exists that hasn't been cited) and tasks
that have landed but not been propagated into any DAG.

Use the user input to scope the audit to a specific DAG slug (e.g.
`h1-prognosis`). If no scope is provided, audit all DAGs discovered under the
project's `dag_dir` (default: `doc/figures/dags/`).

## Setup

Follow `references/command-preamble.md` (role:
`research-assistant`).

Additionally:
1. Check that `science-tool dag --help` runs — if not, the upstream `dag`
   subcommand group is not installed; tell the user and stop.
2. Confirm the project has a valid `science.yaml` with either a `dag:` block
   or `profile: research` (which triggers research-profile defaults).

## Workflow

### 1. Run the audit read-only

```
science-tool dag audit --json
```

This re-renders every DAG (idempotent) and runs drift-based staleness detection.
Parse the JSON; **do not invoke `--fix`** yet. Exit code 0 = clean; 1 = findings
present.

### 2. Present the four finding classes separately

Surface them in this order, each with its own header:

- **Drifted edges (evidence freshness)** — new evidence has landed since the
  edge's newest cited task. For each drifted edge, show:
  - `{dag}#{id}: {source} → {target}`
  - `last_cited_date` (or "never" if none)
  - `candidate_drift_tasks`: list task IDs with their completion dates + a
    one-line title summary
- **Under-reviewed edges (curation freshness)** — only included if the user
  passes `--include-curation-freshness` or the project uses `last_reviewed:`
  attestations.
- **Unresolved refs** — `{dag}#{id}: {kind}={value} — {reason}`. Broken IDs
  in `data_support` / `lit_support` / `eliminated_by`.
- **Unpropagated recent tasks** — tasks completed in the last 28 days whose
  `related:` field names a hypothesis/inquiry/proposition but whose ID is not
  cited by any edge.

### 3. Propose actions per finding (read-only — do NOT execute)

For each drifted edge, assess whether the candidate drift task(s) support a
concrete YAML update:

- **Direct citation** — the task clearly validates / invalidates the edge at the
  current status. Propose adding it to `data_support[]`.
- **Status change** — the task changes the edge's epistemic status (e.g., moves
  from `tentative` → `supported`, or from any status → `eliminated`). Propose
  the status change with the task cited in `eliminated_by` if applicable.
- **New caveat** — the task doesn't change the status but adds a meaningful
  caveat (e.g., "perturbation-mechanism-dependent"). Propose extending
  `caveats[]`.
- **Unclear** — the task's relationship to the edge is ambiguous. Propose
  opening a review task (`science-tool tasks add --priority P2 --group dag-refresh
  --title "Review {dag}#{id}: drift candidate {task_id}"`).

For unpropagated tasks: read the task's own `related:` field and propose
citing it in the most relevant edge, OR acknowledge why it doesn't belong in
any current edge (e.g., it tests a novel relationship that belongs in a new
edge — in which case propose scoping a new-edge task).

For unresolved refs: flag as potential typos or retired IDs. Propose either
fixing the ID or removing the stale ref.

### 4. Await user approval before mutating

Do NOT call `science-tool dag audit --fix` without explicit user confirmation.
Present the proposal summary, then ask:

> "Apply all proposed changes, apply selectively, or stop here?"

On approval:
- For YAML edits: edit the `<dag>.edges.yaml` file directly with the proposed
  changes. Run `science-tool dag render --project <project>` afterwards to
  refresh the `-auto.dot` / `-auto.png` artifacts.
- For new review tasks: call `science-tool tasks add` (or
  `science-tool dag audit --fix` which routes through the same API).
- For ref fixes: edit the `<dag>.edges.yaml` directly.

### 5. Commit

On success, commit with a message in the pattern:

```
doc: refresh DAGs (<slug> + <slug> + ...)

<one-line summary of what changed>

- drifted edges reviewed: N (resolved: M, deferred: N-M)
- unpropagated tasks: K (cited: J, deferred: K-J)
- unresolved refs: R (fixed: F, deferred: R-F)
```

## Scheduling

Run this skill:

- **On a 4-weekly cadence** — add to the project's recurring-task schedule
  (e.g., via `/loop 4w /dag-audit`). Prevents drift accumulation.
- **After any major verdict interpretation lands** — terminal verdicts often
  retroactively change the status of multiple edges. Running the audit right
  after a verdict write-up captures the propagation before it becomes stale.
- **Before writing a synthesis report** — ensures the DAG figures the report
  references are current. `science-big-picture` invokes this skill
  read-only as part of its Phase 3 rollup.

## Non-goals

- Do NOT use this skill to **reorganize** DAG topology (add/remove nodes/edges).
  That is a design-level activity; use `science-sketch-model` or
  `science-critique-approach` instead. This skill only reconciles existing
  edges with new evidence.
- Do NOT use `--fix` unattended. The mutations include opening tasks and
  editing YAML — both need human judgement on each specific proposal.
- Do NOT audit eliminated edges. They are intentionally frozen; the `dag
  staleness` command already excludes them.

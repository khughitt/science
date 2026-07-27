---
name: science-dag-audit
description: "Audit causal DAG freshness — runs drift detection read-only, surfaces stale edges + unpropagated tasks + broken refs, and applies fixes only on explicit user approval. Use on a 4-weekly cadence or after any major verdict interpretation lands."
user-invocable: true
---

# DAG Audit

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the emitted methodology router skills that own the relevant leaf guidance (for example, load the `science-literature` skill for `literature-evaluation` and `literature-citation-discipline` guidance, and load the `science-epistemics` skill for `epistemics-proposition-graph-reasoning` guidance).
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

Run a drift-based audit of the project's causal DAG figures. Surface edges that
have drifted out of date (new evidence exists that hasn't been cited) and tasks
that have landed but not been propagated into any DAG.

Use the user input to scope the audit to a specific DAG slug (e.g.
`h1-prognosis`). If no scope is provided, audit all DAGs discovered under the
project's `dag_dir` (default: `doc/figures/dags/`).

## Setup


Additionally:
1. Check that `science dag --help` runs — if not, the upstream `dag`
   subcommand group is not installed; tell the user and stop.
2. Confirm the project has a valid `science.yaml` with either a `dag:` block
   or `profile: research` (which triggers research-profile defaults).

## Workflow

### 1. Run the audit read-only

```
science dag audit --format json
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
  opening a review task (`science tasks add --priority P2 --group dag-refresh
  --title "Review {dag}#{id}: drift candidate {task_id}"`).

For unpropagated tasks: read the task's own `related:` field and propose
citing it in the most relevant edge, OR acknowledge why it doesn't belong in
any current edge (e.g., it tests a novel relationship that belongs in a new
edge — in which case propose scoping a new-edge task).

For unresolved refs: flag as potential typos or retired IDs. Propose either
fixing the ID or removing the stale ref.

### 4. Await user approval before mutating

Do NOT call `science dag audit --fix` without explicit user confirmation.
Present the proposal summary, then ask:

> "Apply all proposed changes, apply selectively, or stop here?"

On approval:
- For DAG semantic edits: edit the backing `proposition:` and `evidence-line:`
  entities. Run `science dag validate --project <project>` and
  `science dag render --project <project>` afterwards to refresh the
  `-auto.dot` / `-auto.png` artifacts.
- For new review tasks: call `science tasks add` (or
  `science dag audit --fix` which routes through the same API).
- For ref fixes: edit the proposition/evidence-line entity that owns the ref.

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
  references are current. The `science-big-picture` skill invokes this skill
  read-only as part of its Phase 3 rollup.

## Non-goals

- Do NOT use this skill to **reorganize** DAG topology (add/remove nodes/edges).
  That is a design-level activity; use the `science-sketch-model` skill or
  the `science-critique-approach` skill instead. This skill only reconciles existing
  edges with new evidence.
- Do NOT use `--fix` unattended. The mutations include opening tasks and
  editing YAML — both need human judgement on each specific proposal.
- Do NOT audit eliminated edges. They are intentionally frozen; the `dag
  staleness` command already excludes them.

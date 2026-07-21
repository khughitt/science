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
3. Load the `science-scientific-writing` Codex skill. For research methodology, read `../../skills/INDEX.md` and load the leaves relevant to the task (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
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
   `templates/<name>.md`. If neither exists, warn the
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

Print a curated orientation for the current research project.

The default stance is skeptical:
- hypotheses are organizing conjectures
- claims carry uncertainty
- evidence updates belief
- sparse or contested regions deserve attention

Output goes to the terminal unless the user input contains `--save`.

## Setup

## Peer Context

If `science.yaml` declares `peers:`, include a brief cross-project context
before the per-project flow:

```bash
science peers list
```

Print the peer list, then continue with the existing per-project status flow
below. Do not attempt to read peer project files yourself; the CLI resolves peer
paths and statuses consistently.

For projects without `peers:`, proceed directly with the per-project status
flow below.

1. Read `specs/research-question.md`.
2. Read `science.yaml`.
3. If present, read `docs/user-guide/epistemic-model.md`.

## Sections

Keep output under ~100 lines.

### 1. Project Identity

From `science.yaml` and `specs/research-question.md`:
- project name and status
- research question
- tags

### 2. Active Hypotheses

From `entities/hypotheses/*.md`:
- list each hypothesis with ID, short title, and current status
- describe it briefly as an organizing conjecture, not a proven result
- highlight which ones are under active investigation

### 3. Open Questions

From `entities/questions/*.md`:
- list the top 5 by priority
- include the question text and type

### 4. Proposition And Graph Uncertainty

When `knowledge/graph.trig` exists:

1. Run:

```bash
science graph project-summary --format json
science graph question-summary --format json
science graph inquiry-summary --format json
science graph attention-sample --limit 5 --format json
science graph dashboard-summary --format json
science graph neighborhood-summary --format json
science graph uncertainty --format json
science graph gaps --format json
```

For `software` projects, skip `project-summary` for now and start from `question-summary` / `inquiry-summary`.

2. Surface:
- research project summary
- high-priority questions from the full question rollup
- high-priority inquiries
- weighted attention sample rows as a stochastic revisiting queue
- contested claims
- single-source claims
- claims lacking empirical data evidence
- evidence-type mix when relevant
- high-uncertainty neighborhoods
- structurally fragile areas

3. Prefer the higher-level drill path:
- `project-summary` for the top-level rollup on `research` projects only
- `question-summary` for the full question rollup; use `attention-sample` to narrow what gets close reading
- `inquiry-summary` for research-thread prioritization
- `dashboard-summary` and `neighborhood-summary` for exact weak points
- `uncertainty` and `gaps` as secondary support views rather than the main dashboard

4. If the graph does not expose claim-backed evidence summaries yet, say that the project appears only partially migrated and treat the uncertainty section as provisional.

Also run:

```bash
science health --project-root . --format json
```

Surface, at minimum:

- proposition `claim_layer` coverage,
- causal-leaning proposition `identification_strength` coverage,
- unsupported mechanistic narratives still flagged by the migration helper,
- proxy-mediated propositions still missing `measurement_model`,
- rival-model packets missing discriminating predictions or overstating a `current_working_model` without real adjudication evidence.

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
- **attention sample**: run `science graph attention-sample --limit 5 --format json`
  to sample epistemic entities by observable graph weight. Include sampled
  `needs-review` or `stale` entities when they are relevant to the current status.
- When a sampled entity is `needs-review`, frame it as a review workflow candidate:
  the next action is to inspect `sci:triggeredBy` evidence, then either record an
  unchanged review with `science entity review <target-ref>` or author a new
  conclusion linked by `sci:amends` / `sci:supersedes`. Do not describe the
  freshness state as a conclusion that the old standing is wrong.
- **task archive lag**: when `science health --format json` shows non-zero
  `archive_lag.done_in_active` or `archive_lag.retired_in_active`, surface it as:
  > N done/retired task(s) still in `tasks/active.md`. Run `science tasks archive --apply`
  > to move them to `tasks/done/YYYY-MM.md`.
  If `archive_lag.missing_completed` is non-zero, call out that those entries need a
  `completed:` date backfilled before archiving so they route to the correct month.

### Managed artifacts

If `science health` reports any managed artifact whose status is not `current` (or `pinned`), surface it:

- `<artifact-name>: <status>` — `<detail>`
  - For `stale`: "Run `science project artifacts update <name>` to refresh."
  - For `locally_modified`: "Run `science project artifacts diff <name>` to inspect; `update --force --yes` to overwrite."
  - For `missing`: "Run `science project artifacts install <name>` to install."
  - For `pinned_but_locally_modified`: "Pin no longer protects what was pinned. Run `diff` then either `update --force --yes` or `unpin`."

The list comes from the `managed_artifacts` field of the health report.

**Cross-project sync staleness:**

Run `science sync status` to check when the last cross-project sync was performed.
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
- which findings belong in `entities/reports/` or `entities/interpretations/`
- which follow-up actions should be added under `tasks/`
- If active hypothesis, inquiry, or task work implies a data analysis but no
  linked `plan:<stem>` analysis plan or `entities/plans/*-analysis-plan.md`
  exists, suggest `science-plan-analysis` before pre-registration or pipeline
  planning.

## Output Format

Use rich terminal output:
- section headers
- tables where useful
- compact graph summaries when relevant

## Optional `--save`

If the user explicitly asks to save the output or includes `--save`:
- save to `entities/meta/status-snapshot-YYYY-MM-DD.md`
- commit the snapshot

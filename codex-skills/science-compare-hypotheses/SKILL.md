---
name: science-compare-hypotheses
description: "Head-to-head evaluation of competing explanations. Use when 2+ hypotheses exist for the same phenomenon and need structured comparison at the proposition level."
---

# Compare Hypotheses

Converted from Claude command `/science:compare-hypotheses`.

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

Perform a structured comparison of competing hypotheses from the user input.

The goal is not merely to pick a winner. The goal is to identify:
- which propositions each hypothesis depends on
- which propositions are supported or disputed
- where uncertainty is concentrated
- what evidence would actually shift belief

**Upstream pre-reg stress test.** When an analysis's verdict turns on a single
dataset, run this command on the pre-registration's flagged alternative as a
standard step in the pre-register → bias-audit → compare-hypotheses chain.
Forcing that alternative into a *parallel* proposition bundle — rather than
leaving it a footnote in the pre-reg or bias audit — surfaces the specific
discriminating tests that would adjudicate it, which the upstream documents
rarely expose on their own.

If no arguments are provided, scan `entities/hypotheses/` and propose a high-value pair.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `docs/user-guide/epistemic-model.md`.
2. Read `.ai/templates/comparison.md` first; if not found, read `templates/comparison.md`.
3. Read relevant hypotheses in `entities/hypotheses/`.
4. Read existing evidence in `entities/topics/`, `entities/papers/`, `entities/interpretations/`, and `entities/discussions/`.

## Workflow

### 1. Summarize Each Hypothesis As A Proposition Bundle

For each hypothesis:
- state the organizing conjecture
- list its key propositions or subpropositions
- identify which propositions are essential versus optional
- note each proposition's layer when it matters: `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`

### 2. Build A Proposition-Centric Evidence Inventory

For each major proposition:
- what supports it?
- what disputes it?
- what is merely suggestive?
- what is missing entirely?

Distinguish:
- literature support
- empirical-data support
- simulation support
- methodological objections

Also distinguish:
- direct observations versus proxy-mediated support that should carry `measurement_model`
- independent support versus support concentrated in one `independence_group`

### 3. Identify Discriminating Propositions And Predictions

Find places where the hypotheses genuinely diverge:
- propositions that cannot both be true as stated
- predictions that would separate them
- edges or mechanisms that would rise or fall differently under new evidence

If the comparison is really among bounded alternative models, represent that explicitly as a rival-model packet and treat `current_working_model` as optional rather than mandatory.

This is the most important section.

### 4. Propose Discriminating Evidence

Identify the most useful next evidence to gather:
- what would be measured
- which proposition it bears on
- how it would update each hypothesis
- whether the likely output is support, dispute, or just uncertainty reduction

Prefer evidence that:
- targets the most central uncertain propositions
- is empirically grounded
- has high discriminatory power

### 5. Assess The Current State

Summarize the comparison in skeptical terms:
- which hypothesis currently has the better-supported proposition bundle
- which one remains more fragile
- where both remain weakly supported
- where the real answer may still be “insufficient evidence”

Use verdict language carefully:
- `better supported`
- `more fragile`
- `contested`
- `insufficiently resolved`

Avoid overstating certainty.

### 6. Consider Synthesis

Ask whether the hypotheses are:
- truly competing
- complementary at different scales or contexts
- different bundles that share some valid propositions and differ only in a few decisive places

## Writing

Follow `.ai/templates/comparison.md` first, then `templates/comparison.md`.
Save to `entities/discussions/<NNNN>-comparison-<slug>.md` with frontmatter `id: "discussion:<NNNN>-comparison-<slug>"`. Pick `<NNNN>` as the next free discussion number so the filename stem and discussion id local part match layout-v3 entity conformance.

## After Writing

1. Save the comparison document.
2. If discriminating evidence suggests concrete work, offer to create tasks.
3. If the comparison suggests a synthesis hypothesis, suggest `science-add-hypothesis`.
4. Suggest next steps:
   - `science-pre-register`
   - `science-discuss`
   - `science-interpret-results`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:compare-hypotheses" \
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

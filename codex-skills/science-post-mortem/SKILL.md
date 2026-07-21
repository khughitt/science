---
name: science-post-mortem
description: "Post-hoc reflection after an analysis failed or behaved unexpectedly. Investigate the root cause, identify what would have surfaced it sooner, and file the generalized methodology lesson as feedback. Use after a surprising result, a failed run, or a violated assumption."
---

# Post-Mortem

Converted from Claude command `/science:post-mortem`.

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

Run a structured post-hoc reflection on an analysis that failed or behaved unexpectedly, described by the user input, and capture any **generalized** methodology lesson as feedback.

If no argument is provided, ask the user which analysis, run, or result to reflect on.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

## When to use

Use this after the fact, when something did not go as planned: a QA issue surfaced late, an analysis design did not fit the data's constraints, a statistical method was applied in violation of its assumptions, or a result contradicted a pre-registered expectation. The goal is not to fix the one analysis — it is to improve the guidance so the next analysis surfaces the issue sooner.

Also use it when **a gate fired and nothing was lost** — a pre-registered check stopped the analysis before any observed data was read. Nothing surfaced late, and no result exists: that is the system working. **A post-mortem on a gate that fired is the cheapest kind, and its lessons are the most transferable, because nothing is entangled with a finding anyone wants to defend.** In this mode, read step 1's "gap between expectation and outcome" as *the gap between what the plan assumed about its own instruments and what was true*.

## Reflection

Work through these steps with the user. Keep the project-specific incident in the project (as an interpretation, note, or task); only a cross-project lesson goes to the global feedback store.

1. **Scope.** What was attempted, what was expected, and what actually happened? Be concrete about the gap between expectation and outcome.

2. **Root cause.** Why did it happen — the actual technical or methodological reason, not the symptom? Distinguish a one-off data/code mistake from a reasoning or process flaw.

3. **Earlier signal.** What would have surfaced this sooner? A QA check, an assumption test, a design review, a different pre-registration question? This is the core of the reflection.

4. **Generalize gate.** Is the lesson cross-project, or specific to this project? If it is purely project-local, **stop**: record it in the project and file nothing globally. Only continue for lessons that should change shared guidance.

   Then separate **the failing thing** (usually local — a specific model, a specific optimiser) from **the reason it was not caught sooner** (usually global — a check that could not fail, a threshold with no stated domain, a probe confounded with its own target). **File on the latter.** The mechanism generalises to nothing; the blind spot generalises to everyone.

5. **Target the surface.** Which guidance artifact should change so the earlier signal becomes routine? `--target` is **free text**; the resolvable namespaces are `skill:`, `command:`, `aspect:`, `template:`, and `cli:` — e.g. `skill:statistics`, `command:plan-analysis`, `aspect:computational-analysis`, `template:pre-registration`, `cli:validate`. Name the surface that should have caught it, not the nearest one on a list. Pick the `concern`:
   - `methodology:statistics` — assumptions, inference validity, model/finite-sample choices
   - `methodology:qa` — data/quality checks that should have caught it
   - `methodology:design` — analysis/study design vs. the question or data constraints
   - `methodology:data-fitness` — dataset suitability, preprocessing, provenance
   - `methodology:reasoning` — interpretation / causal / epistemic errors

6. **File the lesson.** For each distinct generalized lesson, run:

   ```bash
   science feedback add \
     --target "skill:statistics" \
     --concern methodology:statistics \
     --category <gap|guidance|suggestion|positive> \
     --summary "<the generalized lesson, one line>" \
     --detail "<what happened in this project as evidence; link the project entity>"
   ```

   - The `summary` is the improvement to shared guidance, not the incident.
   - The `detail` carries the incident as evidence and a pointer (path or id) to the project entity where the failure lives.
   - One entry per distinct lesson, not one big dump. The tool detects recurrence automatically.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:post-mortem" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- Skip if everything worked smoothly — no feedback is valid feedback

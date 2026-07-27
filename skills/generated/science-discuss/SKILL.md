---
name: science-discuss
description: "Structured critical discussion for a hypothesis, question, topic, or approach. Supports optional double-blind mode to reduce anchoring bias."
user-invocable: true
---

# Discuss

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/discussant.md` role prompt and its aspect definitions.
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

Run a structured discussion on the user input.
If no argument is provided, sample a discussion focus from `entities/questions/`, `entities/hypotheses/`, or active tasks (`science tasks list --status active`).

## Setup


Additionally:
1. Read `.ai/templates/discussion.md` first; if not found, read `references/templates/discussion.md`.
2. If the discussion may create follow-up questions, read `.ai/templates/question.md`
   first; if not found, read `references/templates/question.md`.
3. Read relevant context tied to the chosen focus:
   - `entities/topics/`
   - `entities/hypotheses/`
   - `entities/questions/`
   - Active tasks (`science tasks list --status active`)

## Discussion Modes

### Standard mode

1. Clarify the focal claim/question.
2. Surface strengths, weaknesses, assumptions, alternatives, confounders, and failure modes in a unified critical analysis. Do NOT create a separate "Alternative Explanations" section — alternatives belong within the critical analysis.
3. Propose concrete follow-up tasks.

If loaded aspects contribute additional discussion guidance (e.g., causal reasoning checks from `causal-modeling`), incorporate that guidance into the critical analysis.

### Q&A mode (automatic)

If the user provides multiple specific questions (e.g., "I have 5 questions about X"), use a Q&A structure instead of the standard template sections:

1. One section per user question, with a focused answer and supporting evidence.
2. A synthesis section at the end that ties the answers together.

This produces clearer output than forcing multiple questions through the generic Critical Analysis / Evidence Needed split. The Q&A structure is used *instead of* the standard sections (Focus / Current Position / Critical Analysis / Evidence Needed), not in addition to them. Still include Prioritized Follow-Ups and Synthesis.

### Double-blind mode (optional)

Use when the user asks for independent reasoning before synthesis.

1. Agree on focus.
2. Agent writes its draft analysis to file before seeing user draft.
3. User writes and shares independent draft.
4. Agent publishes a combined synthesis that compares, challenges, and refines both perspectives.

## Writing Output

Create the discussion with `science discussions create`. The tool builds the canonical ID, writes canonical frontmatter (`id`, `kind`, `title`, `status`, `related`, `source_refs`, `created`, `updated`), runs prospective validation, and places the file in the discussion home `entities/discussions/`.

```bash
uv run science discussions create "<short title>" \
  --focus <hypothesis:hNN-...|question:qNN-...|topic:...> \
  --source-ref <paper-or-package-ref>
```

`--focus` is repeatable and maps to `related`. `--source-ref` is repeatable. The command prints the chosen ID and the file path. After creation, open the file and fill in the body sections below; preserve the frontmatter the tool produced.

The default `status` is `active`. Switch to `complete` once the discussion is wrapped up via `science entity edit <ref> --status complete` (or `science entity edit`); use `superseded` if a later discussion replaces this one. Add `focus_type`, `focus_ref`, or `mode` fields by editing the frontmatter directly — these are project-specific and survive the audit.

Sections (in the body):

1. `## Focus`
2. `## Current Position`
3. `## Critical Analysis` (includes alternative explanations and confounders — see template)
4. `## Evidence Needed`
5. `## Prioritized Follow-Ups`
6. `## Synthesis` (include side-by-side summary in double-blind mode)

Use `.ai/templates/discussion.md` first, then `references/templates/discussion.md` as the writing reference.

## After Discussion

1. **New questions surfaced:** create them with `science questions create "<text>" [--related <ref>] [--source-ref <ref>]`. To attach a question to an existing discussion or hypothesis, use `science entity edit <question-ref> --related <other-ref>` (additive — preserves existing related entries).
2. **Existing question updates:** if the discussion changes the framing of an existing question, edit its body in place; for metadata, use `science entity edit <ref>` / `science entity edit <ref>`.
3. Offer to create follow-up tasks via `science tasks add` with appropriate priority and related entities.
4. **Hypothesis wording changes:** for metadata (status, related), use `science entity edit <ref> --status ...`. For body changes, edit the file in place.
5. **Task reframing check:** Review whether the discussion reframes the meaning of any existing tasks. If a task's purpose or scope has changed, update its description in `tasks/active.md` to reflect the new framing.
6. Commit: `git add -A && git commit -m "doc: discuss <slug> and update priorities"`
7. **Actionable recommendations:** If the discussion produced a concrete, low-cost design change or implementation recommendation (something testable in under an hour), it should be flagged with `[actionable now]` in the Prioritized Follow-Ups table. Offer to implement it immediately rather than creating a task for later. This prevents useful small changes from being buried in discussion documents.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:discuss" \
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

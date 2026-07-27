---
name: science-research-topic
description: "Research and summarize a scientific topic with project-context linking."
user-invocable: true
---

# Research a Topic

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
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

Write a structured background synthesis on the topic specified by the user.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-topic` slash command directly from the user.)

1. **Pre-dispatch check:** Look at `entities/topics/` for existing coverage of the topic. If a file likely overlaps, ask the user whether to overwrite, skip, or produce a supplementary synthesis. Pass their decision into the subagent prompt.
2. **Dispatch** the `topic-researcher` subagent via the Agent tool:
   - `subagent_type: topic-researcher`
   - `description`: a short identifier for the topic
   - `prompt`: the full the user input plus the overwrite decision, plus any scope narrowing the user has hinted at
3. Do **not** perform the Setup / Research Process / Writing / After Writing steps below yourself — those are the subagent's job and dispatching preserves the cost savings this command exists for.
4. When the subagent reports back, continue at **Orchestrator Post-Dispatch** below.

### If you are the `topic-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Research Process → Writing → After Writing. Then report back per the response contract in your agent definition.

## Setup


Additionally:
1. Read `.ai/templates/background-topic.md` first; if not found, read `references/templates/background-topic.md`.
2. Check `entities/topics/` for existing coverage; ask before overwriting.
3. Check `entities/papers/` for relevant summaries.

## Research Process

1. Start from LLM knowledge and draft core concepts, active debates, and project relevance.
2. Use web search to verify key references and capture recent changes.
3. Do not read PDFs unless user provides a file path.

## Writing

Follow `.ai/templates/background-topic.md` first, then `references/templates/background-topic.md`, and fill all sections.
Save to `entities/topics/<topic-slug>.md`.

Set `origins` in the topic frontmatter to reflect where the framing came from —
`{type: literature, ref: paper:<key>}` for each seed review, or `{type: literature, ref: cite:<key>}`
if it's a bibliography-only reference, or `{type: user}` if the user named the topic. Write the
full `cite:<key>` or `paper:<key>` prefix yourself — there is no CLI-side normalization for
hand-authored topic frontmatter. Set `added_by: "llm:<model>:research-topic"`.
Provenance only; does not affect belief.

The output should include:

- Key subtopics and how they connect.
- What is well-established vs uncertain.
- Links to existing hypotheses and open questions.
- Suggested follow-up research tasks.

If loaded aspects contribute additional sections (e.g., Tooling & Implementation from `software-development`), include them after the core sections.

## After Writing

1. Add new references to `papers/references.bib` (create with header if missing).
2. Add newly surfaced questions to `entities/questions/` using `.ai/templates/question.md` first, then `references/templates/question.md`.
3. Commit: `git add -A && git commit -m "doc: research topic <topic>"`

Note: "Offer to create follow-up tasks via `science tasks add`" is intentionally deferred to the orchestrator — it is a user-interactive step and the subagent cannot prompt the user directly.

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review the scope the subagent settled on. If it narrowed too aggressively (or not enough), flag that to the user before moving on.
2. Review suggested follow-up research tasks in the subagent's report. Offer to create them via `science tasks add`, grouping related items where sensible and including the rationale the subagent provided.
3. If the subagent flagged contradictions or open questions that overlap existing hypotheses in `entities/hypotheses/`, make small follow-up edits as a separate commit.
4. Read the written synthesis only if you need its content for downstream reasoning. Otherwise, trust the report.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:research-topic" \
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

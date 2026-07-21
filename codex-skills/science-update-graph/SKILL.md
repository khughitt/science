---
name: science-update-graph
description: "Re-audit and re-materialize the knowledge graph after canonical source changes."
---

# Update Knowledge Graph

Converted from Claude command `/science:update-graph`.

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

> **Prerequisite:** Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics before starting.

## Overview

This command updates the graph by changing canonical source files, not by editing triples directly. The workflow is: detect source changes, fix any unresolved references, then re-materialize `knowledge/graph.trig`.

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, the examples below write just `science <command>`; always expand them to `uv run science <command>` when executing.

## Cross-Project Registry Check

When adding new entities as part of the update, the cross-project registry is consulted during `graph build` to detect potential duplicates across projects. If matches are found, prefer reusing existing canonical IDs and aliases from the registry.

## Workflow

### Step 1: Check whether canonical inputs changed

Run:

```bash
science graph diff --mode hybrid --format json
```

Review the output. If no files are stale, report "Graph is up to date" and stop.

### Step 2: Triage stale inputs by source type

Typical categories:

- typed markdown entity owners in `entities/`
- task files in `tasks/`
- local extension files in `knowledge/sources/<local-profile>/`
- removed source files that may require entity retirement or migration

### Step 3: Update the canonical sources

For each stale source:

1. Re-read the source file.
2. Update frontmatter IDs, `related`, `source_refs`, and task links to canonical IDs.
3. Add or revise local-profile entities and alias mappings when the project introduces new local semantics.
4. Use `theme:<slug>` for durable cross-cutting organizing frames. Do not use `topic:<slug>` for new semantic authoring; use `concept` for atomic vocabulary and `theme` for the project-level lens that organizes other entities.
5. If a file was removed, decide whether the represented entity should also be removed or replaced by another canonical source. Do not silently orphan it.

Use a fix-on-touch policy for non-canonical entity IDs encountered during the
update: when a stale source already requires editing, apply the safe
rename/xref addition needed to move it toward canonical identity instead of
leaving known bad references behind.

### Step 4: Audit before rebuild

Run:

```bash
science graph audit --project-root . --format json
```

`graph audit` is read-only: it reports unresolved canonical source references before
materialization without mutating the project. Resolve anything it flags in the upstream
sources first (apply the fix-on-touch policy above to any non-canonical IDs it
surfaces). Do not build until the audit is clean.

### Step 5: Re-materialize and validate

Run:

```bash
science graph build --project-root .
science graph validate --format json
science graph stats --format json
```

### Step 6: Keep project-local source files current when needed

If the update involved ID cleanup or new project-local semantics, keep the
project-local source files current:

- `knowledge/sources/<local-profile>/mappings.yaml`
New durable entity owners belong under `entities/`.

## Important Notes

- Incremental updates still happen at the source layer; `graph.trig` is always regenerated.
- Tasks are graph entities and must stay linked canonically.
- `<local-profile>` comes from `science.yaml` `knowledge_profiles.local` and defaults to `local`.
- If `graph diff` reports staleness after a rebuild, inspect the source file change rather than patching the graph output.

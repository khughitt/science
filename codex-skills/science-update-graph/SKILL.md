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

> **Prerequisite:** Load the `knowledge-graph` skill before starting.

## Overview

This command updates the graph by changing canonical source files, not by editing triples directly. The workflow is: detect source changes, fix any unresolved references, then re-materialize `knowledge/graph.trig`.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

For brevity, the examples below write just `science-tool <command>`; always expand them to `uv run science-tool <command>` when executing.

## Cross-Project Registry Check

When adding new entities as part of the update, the cross-project registry is consulted during `graph build` to detect potential duplicates across projects. If matches are found, prefer reusing existing canonical IDs and aliases from the registry.

## Workflow

### Step 1: Check whether canonical inputs changed

Run:

```bash
science-tool graph diff --mode hybrid --format json
```

Review the output. If no files are stale, report "Graph is up to date" and stop.

### Step 2: Triage stale inputs by source type

Typical categories:

- typed markdown docs in `specs/` or `doc/`
- task files in `tasks/`
- local extension files in `knowledge/sources/<local-profile>/`
- removed source files that may require entity retirement or migration

### Step 3: Update the canonical sources

For each stale source:

1. Re-read the source file.
2. Update frontmatter IDs, `related`, `source_refs`, and task links to canonical IDs.
3. Add or revise local-profile entities and alias mappings when the project introduces new local semantics.
4. If a file was removed, decide whether the represented entity should also be removed or replaced by another canonical source. Do not silently orphan it.

### Step 4: Audit before rebuild

Run:

```bash
science-tool graph migrate --project-root . --format json
science-tool graph audit --project-root . --format json
```

Use `graph migrate` first as a dry-run audit. It previews alias-resolvable rewrites, layered-claim
migration gaps, and projected cleanup without mutating the project.

If the preview looks correct, re-run with:

```bash
science-tool graph migrate --project-root . --format json --apply
```

Only `--apply` writes alias rewrites, scaffolds local-profile source files, and persists
`knowledge/reports/kg-migration-audit.json`. If unresolved references remain after the audit or
apply pass, fix the upstream sources first. Do not build until the audit is clean.

### Step 5: Re-materialize and validate

Run:

```bash
science-tool graph build --project-root .
science-tool graph validate --format json
science-tool graph stats --format json
```

### Step 6: Record project-local migration state when needed

If the update involved legacy ID cleanup or new project-local semantics, keep the migration artifacts current:

- `knowledge/sources/<local-profile>/entities.yaml`
- `knowledge/sources/<local-profile>/mappings.yaml`
- `knowledge/reports/kg-migration-audit.json`

## Important Notes

- Incremental updates still happen at the source layer; `graph.trig` is always regenerated.
- Tasks are graph entities and must stay linked canonically.
- `<local-profile>` comes from `science.yaml` `knowledge_profiles.local` and defaults to `local`.
- If `graph diff` reports staleness after a rebuild, inspect the source file change rather than patching the graph output.

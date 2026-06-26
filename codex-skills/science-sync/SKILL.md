---
name: science-sync
description: "Synchronize knowledge model and content across registered science projects. Use when the user says \"sync projects\", \"cross-project sync\", \"align projects\", or \"sync\"."
---

# Cross-Project Sync

Converted from Claude command `/science:sync`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Run a cross-project sync to align the registry — a shared index of entities across
all registered science projects. The registry enables cross-project awareness (e.g.,
querying which projects reference a given gene or concept) without copying content
between projects.

## Setup

1. Read `science.yaml` for the current project context.
2. Run `science sync status` to check current sync state.
3. Run `science sync projects` to list registered projects.

### Pre-sync managed-artifact check

Before performing project sync operations, query `science health` for any managed artifact whose status is not `current` or `pinned`. If any are found, surface a warning at the top of sync output:

> ⚠️  N managed artifact(s) require attention:
> - `<artifact-name>`: `<status>` — `<detail>`
>
> Sync proceeds; consider `science project artifacts update` after sync completes.

The warning does NOT block sync; it surfaces alongside other top-of-sync warnings.

## Execution

Run the sync:

```bash
science sync run
```

If the user wants to preview without writing changes:

```bash
science sync run --dry-run
```

## Presenting Results

After sync completes, present the report:

### Registry Updates

- How many entities are now tracked across projects
- How many are new since last sync

### Drift Warnings

- Same entity with conflicting metadata across projects
- Scope mismatches where one project treats an entity as `scope: shared` and
  another treats the same identity as `scope: project`
- Any primary_external_id collision, especially when two canonical IDs claim
  the same external identifier

## Follow-Up

Suggest the user:
1. Resolve any drift warnings by updating entity metadata
2. Run `science graph build` if entity metadata changed

## Rebuild

If the user wants to rebuild the registry from scratch:

```bash
science sync rebuild
```

---
name: science-create-graph
description: "Build a project knowledge graph from canonical upstream sources, then materialize graph.trig."
---

# Create Knowledge Graph

Converted from Claude command `/science:create-graph`.

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

This command does **not** author triples directly. It organizes project knowledge into canonical upstream sources, audits reference resolution, and materializes `knowledge/graph.trig` as a generated artifact.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

For brevity, the examples below write just `science-tool <command>`; always expand them to `uv run science-tool <command>` when executing.

## Rules

- **MUST NOT** edit `knowledge/graph.trig` directly.
- **MUST** define `knowledge_profiles` in `science.yaml` before building the graph.
- **MUST** treat markdown docs, task files, and `knowledge/sources/` files as the canonical graph inputs.
- **MUST** add project-local entities and aliases under `knowledge/sources/<local-profile>/`, not as ad hoc triples.
- **MUST** run `science-tool graph audit` before `science-tool graph build`.
- **MUST** keep tasks as graph entities; do not treat them as out-of-band metadata.

## Cross-Project Registry Check

Before adding new entities, check the cross-project registry for existing definitions. Run `science-tool sync status` to see if the registry is populated. If it is, new entities added during graph creation will be checked against the registry during `graph build` to detect potential duplicates across projects. If a match is found, prefer reusing the existing canonical ID and aliases rather than creating a new entity.

## Canonical Inputs

Build the graph from these upstream sources:

- Typed markdown entities in `specs/` and `doc/` with YAML frontmatter (`id`, `type`, `title`, `related`, `source_refs`, etc.)
- Task files in `tasks/active.md` and `tasks/done/*.md`
- Structured local extensions in:
  - `knowledge/sources/<local-profile>/entities.yaml`
  - `knowledge/sources/<local-profile>/relations.yaml`
  - `knowledge/sources/<local-profile>/mappings.yaml`

Use `science-model/core` semantics for shared entity and relation types. Declare domain ontologies (e.g., `biolink`) in `science.yaml` to enable vocabulary for entity types and relation predicates. Put anything project-local but still useful in the configured local profile directory, which defaults to `local`.

## Workflow

### Step 1: Configure profiles

Ensure `science.yaml` declares the ontologies and profiles you want to compose:

```yaml
ontologies: [biolink]
knowledge_profiles:
  local: local
```

`ontologies` declares which community ontologies provide vocabulary for entity types and relation predicates. Currently available: `biolink`. `core` is always implied.
`local` also determines the directory name under `knowledge/sources/`; if omitted, use `local`.

### Step 2: Author canonical sources

For each project entity:

1. Put first-class research objects in typed markdown docs:
   - hypotheses in `specs/hypotheses/`
   - questions in `doc/questions/`
   - interpretations, discussions, pre-registrations, bias audits, methods, datasets, and similar entities in their typed `doc/` locations
2. Keep task links in `tasks/*.md` `related:` / `blocked-by:` fields using canonical IDs.
3. Put unresolved but legitimate project-local semantics in `knowledge/sources/<local-profile>/`:
   - `entities.yaml` for local entities such as project topics or legacy questions not yet migrated into standalone docs
   - `mappings.yaml` for explicit aliases during migration
   - `relations.yaml` only when you need project-local relation declarations

Example `entities.yaml` entry:

```yaml
entities:
  - canonical_id: topic:evaluation
    kind: topic
    title: Evaluation
    profile: local
    source_path: knowledge/sources/local/entities.yaml
```

### Step 3: Audit canonical reference resolution

Run:

```bash
science-tool graph audit --project-root . --format json
```

Fix every unresolved reference in the canonical sources before building:

- add missing frontmatter to existing docs
- convert legacy short IDs to canonical IDs
- add explicit aliases in `mappings.yaml` when a temporary migration bridge is still needed
- add missing local-profile entities for legitimate project-local concepts

### Step 4: Materialize the graph

Once audit is clean:

```bash
science-tool graph build --project-root .
science-tool graph validate --format json
science-tool graph stats --format json
```

`science-tool graph build` generates `knowledge/graph.trig` deterministically from the upstream sources. That file is a view over the canonical inputs, not the place to curate knowledge manually.

## Output

At completion, the project should have:

1. Canonical entity/task/source files with resolved IDs
2. `knowledge/sources/<local-profile>/` for local extensions and explicit aliases
3. A generated `knowledge/graph.trig`
4. Clean `graph audit` and `graph validate` output

## Important Notes

- Prefer fixing the upstream source over adding a temporary alias.
- If you feel compelled to hand-edit `graph.trig`, stop and add or repair the missing upstream source instead.
- Ontology declarations enable standard vocabulary; use them when the project works with domain entities.

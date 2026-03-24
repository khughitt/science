---
description: Build a project knowledge graph from canonical upstream sources, then materialize graph.trig.
---

# Create Knowledge Graph

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

Use `science-model/core` semantics for shared entity and relation types. Enable curated domain profiles such as `bio` through `science.yaml`. Put anything project-local but still useful in the configured local profile directory, which defaults to `local`.

## Workflow

### Step 1: Configure profiles

Ensure `science.yaml` declares the graph profiles you want to compose:

```yaml
knowledge_profiles:
  curated: [bio]
  local: local
```

`core` is always implied. Add more curated profiles only when the project genuinely uses them.
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
- Curated domain profiles should stay opinionated and small; do not mirror whole external ontologies into a project repo.

---
description: Re-audit and re-materialize the knowledge graph after canonical source changes.
---

# Update Knowledge Graph

> **Prerequisite:** Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics before starting.

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

- typed markdown docs in `specs/` or `doc/`
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

Use a fix-on-touch policy for legacy entity IDs encountered during the update:
when a stale source already requires editing, apply the safe rename/xref addition
needed to move it toward canonical identity instead of leaving known legacy
references behind.

### Step 4: Audit before rebuild

Run:

```bash
science graph audit --project-root . --format json
```

`graph audit` is read-only: it reports unresolved canonical source references before
materialization without mutating the project. Resolve anything it flags in the upstream
sources first (apply the fix-on-touch policy above to any legacy IDs it surfaces). Do not
build until the audit is clean.

### Step 5: Re-materialize and validate

Run:

```bash
science graph build --project-root .
science graph validate --format json
science graph stats --format json
```

### Step 6: Keep project-local source files current when needed

If the update involved legacy ID cleanup or new project-local semantics, keep the
project-local source files current:

- `knowledge/sources/<local-profile>/entities.yaml`
- `knowledge/sources/<local-profile>/mappings.yaml`

## Important Notes

- Incremental updates still happen at the source layer; `graph.trig` is always regenerated.
- Tasks are graph entities and must stay linked canonically.
- `<local-profile>` comes from `science.yaml` `knowledge_profiles.local` and defaults to `local`.
- If `graph diff` reports staleness after a rebuild, inspect the source file change rather than patching the graph output.

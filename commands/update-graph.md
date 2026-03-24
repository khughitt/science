---
description: Re-audit and re-materialize the knowledge graph after canonical source changes.
---

# Update Knowledge Graph

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

Use `graph migrate` when you want the tool to rewrite alias-resolvable refs, scaffold local-profile
source files, and persist `knowledge/reports/kg-migration-audit.json` before the final audit. If any
unresolved references remain after migration, fix the upstream sources first. Do not build until the audit is clean.

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
- `<local-profile>` comes from `science.yaml` `knowledge_profiles.local` and defaults to `project_specific`.
- If `graph diff` reports staleness after a rebuild, inspect the source file change rather than patching the graph output.

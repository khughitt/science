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
- local extension files in `knowledge/sources/project_specific/`
- removed source files that may require entity retirement or migration

### Step 3: Update the canonical sources

For each stale source:

1. Re-read the source file.
2. Update frontmatter IDs, `related`, `source_refs`, and task links to canonical IDs.
3. Add or revise `project_specific` entities and alias mappings when the project introduces new local semantics.
4. If a file was removed, decide whether the represented entity should also be removed or replaced by another canonical source. Do not silently orphan it.

### Step 4: Audit before rebuild

Run:

```bash
science-tool graph audit --project-root . --format json
```

If any unresolved references remain, fix the upstream sources first. Do not build until the audit is clean.

### Step 5: Re-materialize and validate

Run:

```bash
science-tool graph build --project-root .
science-tool graph validate --format json
science-tool graph stats --format json
```

### Step 6: Record project-local migration state when needed

If the update involved legacy ID cleanup or new project-local semantics, keep the migration artifacts current:

- `knowledge/sources/project_specific/entities.yaml`
- `knowledge/sources/project_specific/mappings.yaml`
- `knowledge/reports/kg-migration-audit.json`

## Important Notes

- Incremental updates still happen at the source layer; `graph.trig` is always regenerated.
- Tasks are graph entities and must stay linked canonically.
- If `graph diff` reports staleness after a rebuild, inspect the source file change rather than patching the graph output.

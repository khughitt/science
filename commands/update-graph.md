---
description: Detect stale areas in the knowledge graph and selectively update from changed documents. Uses graph diff to find changes, then re-processes affected documents.
---

# Update Knowledge Graph

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

> **Cache note:** If `uv run --with` reports missing commands or flags that should exist, the build cache may be stale. Run `uv cache clean science-tool` to clear it, then retry.

## Overview

This command detects which project documents have changed since the last graph update, re-processes them, and updates the graph accordingly.

## Workflow

### Step 1: Run diff to find stale inputs

```bash
science-tool graph diff --mode hybrid --format json
```

Review the output. Each row shows a file path, status (`stale`), and reason (`new_file`, `hash_changed`, `mtime_changed`, `removed_file`).

If no files are stale, report "Graph is up to date" and stop.

### Step 2: Triage changed files

Group stale files by type:

- **New files**: need full entity/claim extraction (same as create-graph Step 3).
- **Changed files**: re-read, compare against existing graph entities, add new/update existing.
- **Removed files**: flag to user -- entities sourced from removed files may need review.

### Step 3: Process each stale file

For each stale file:

1. **Read the document** and understand what changed.
2. **Scan for annotations**: `science-tool graph scan-prose <directory>`
3. **Check existing graph entities** related to this document:
   ```bash
   science-tool graph claims --about "<relevant term>" --format json
   science-tool graph neighborhood "<relevant entity>" --format json
   ```
4. **Add new entities/claims** that don't already exist.
5. **Update prose annotations** if new entities were added.

### Step 4: Handle removed files

For files with reason `removed_file`:
- List graph entities that were sourced from the removed file.
- Ask the user whether to keep or remove those entities.
- Do not silently delete graph entities.

### Step 5: Finalize

```bash
science-tool graph stamp-revision
science-tool graph validate --format json
science-tool graph stats --format json
```

Report:
- Number of files processed
- New entities/claims added
- Validation status
- Updated graph stats

## Important Notes

- **Incremental updates only.** Do not re-process unchanged files.
- **Preserve existing entities.** Do not remove or modify entities unless the source document changed.
- **Ask before removing.** Never silently delete graph entities, even if their source was removed.
- **Use standard predicates.** Same rules as create-graph: prefer `cito:supports`/`cito:disputes` over `sci:supports`/`sci:refutes`, and `skos:related` over `sci:relatedTo`. Run `science-tool graph predicates` for the full list.

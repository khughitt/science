---
name: update-graph
description: Detect stale areas in the knowledge graph and selectively update from changed documents. Uses graph diff to find changes, then re-processes affected documents.
user_invocable: true
---

# Update Knowledge Graph

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This skill detects which project documents have changed since the last graph update, re-processes them, and updates the graph accordingly.

## Workflow

### Step 1: Run diff to find stale inputs

```bash
uv run science-tool graph diff --mode hybrid --format json
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
2. **Scan for annotations**: `uv run science-tool graph scan-prose <directory>`
3. **Check existing graph entities** related to this document:
   ```bash
   uv run science-tool graph claims --about "<relevant term>" --format json
   uv run science-tool graph neighborhood "<relevant entity>" --format json
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
uv run science-tool graph stamp-revision
uv run science-tool graph validate --format json
uv run science-tool graph stats --format json
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

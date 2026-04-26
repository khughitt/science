---
description: Synchronize knowledge model and content across registered science projects. Use when the user says "sync projects", "cross-project sync", "align projects", or "sync".
---

# Cross-Project Sync

Run a cross-project sync to align the registry — a shared index of entities across
all registered science projects. The registry enables cross-project awareness (e.g.,
querying which projects reference a given gene or concept) without copying content
between projects.

## Setup

1. Read `science.yaml` for the current project context.
2. Run `science-tool sync status` to check current sync state.
3. Run `science-tool sync projects` to list registered projects.

### Pre-sync managed-artifact check

Before performing project sync operations, query `science-tool health` for any managed artifact whose status is not `current` or `pinned`. If any are found, surface a warning at the top of sync output:

> ⚠️  N managed artifact(s) require attention:
> - `<artifact-name>`: `<status>` — `<detail>`
>
> Sync proceeds; consider `science-tool project artifacts update` after sync completes.

The warning does NOT block sync; it surfaces alongside other top-of-sync warnings.

## Execution

Run the sync:

```bash
science-tool sync run
```

If the user wants to preview without writing changes:

```bash
science-tool sync run --dry-run
```

## Presenting Results

After sync completes, present the report:

### Registry Updates

- How many entities are now tracked across projects
- How many are new since last sync

### Drift Warnings

- Same entity with conflicting metadata across projects

## Follow-Up

Suggest the user:
1. Resolve any drift warnings by updating entity metadata
2. Run `science-tool graph build` if entity metadata changed

## Rebuild

If the user wants to rebuild the registry from scratch:

```bash
science-tool sync rebuild
```

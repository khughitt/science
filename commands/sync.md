---
description: Synchronize knowledge model and content across registered science projects. Use when the user says "sync projects", "cross-project sync", "align projects", or "sync".
---

# Cross-Project Sync

Run a full cross-project sync to align knowledge models and propagate relevant content between registered science projects.

## Setup

1. Read `science.yaml` for the current project context.
2. Run `science-tool sync status` to check current sync state.
3. Run `science-tool sync projects` to list registered projects.

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
- Any shared entity kinds promoted to the cross-project profile

### Alignment

- Entities deduplicated across projects
- Drift detected (same entity, conflicting metadata)

### Propagated Content

- What was propagated and where (questions, claims, hypotheses, evidence)
- Propagated files land in `doc/sync/` in each target project

### Fuzzy Matches for Review

- Near-matches that couldn't be auto-resolved (tier 4)
- Present these for the user to review and decide

## Follow-Up

Suggest the user:
1. Review propagated entities in `doc/sync/` — remove any that aren't relevant
2. Resolve drift warnings by updating entity metadata
3. Review fuzzy matches and decide whether to merge or keep separate
4. Run `science-tool graph build` to incorporate propagated entities into the knowledge graph

## Rebuild

If the user wants to rebuild the registry from scratch:

```bash
science-tool sync rebuild
```

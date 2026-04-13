---
description: Run the science-tool health check and triage findings interactively. Use when the user says "check project health", "find issues", "what's broken", or after running migrations.
---

# Health Triage

Aggregate project health diagnostics and walk the user through cluster-level cleanup.

`$ARGUMENTS` optionally specifies the project root (default: current directory).

## Procedure

### 1. Run the health command

```bash
uv run science-tool health --project-root <root> --format=json
```

Parse the JSON output. Fields:
- `unresolved_refs`: list of `{target, mention_count, sources, looks_like}`
- `lingering_tags_lines`: list of `{file, values}`

### 2. Cluster issues

Group `unresolved_refs` by `looks_like` heuristic:
- **looks_like=task**: refs like `topic:t143`, `topic:t146` — likely mis-prefixed task IDs
- **looks_like=hypothesis**: refs like `topic:h01` — likely mis-prefixed hypothesis IDs
- **looks_like=topic**: refs like `topic:genomics`, `topic:phase3b` — could be real topics or operational markers
- **looks_like=unknown**: anything else

For the `topic` cluster, sub-cluster by user judgment hint:
- Date-shaped values (`pivot-2026-03-18`): likely operational markers
- Pure short words (`genomics`, `protein`): likely real topics
- State-like (`blocked`, `phase3b`, `cycle1`): likely operational

### 3. Present findings

Show a structured summary:

```
Health Report for <project>
================================
Unresolved References (N total):
  - 5 look like task IDs (would be better as task: refs)
  - 12 look like real topics (need entity stubs)
  - 8 look like operational markers (consider meta: prefix)

Lingering tags: lines: M files

Total issues: X
```

### 4. Propose batch actions

For each cluster, propose ONE action covering the whole cluster, not per-ref decisions. Examples:

**Task-id cluster:**
> "5 refs look like task IDs being mis-prefixed: topic:t143, topic:t146, topic:t147, topic:t149, topic:t150. Rewrite all as task: refs?"

**Real topics cluster:**
> "12 refs look like domain topics: topic:genomics, topic:protein, topic:embeddings, ... Create stub topic entity files for these in doc/topics/?"

**Operational markers cluster:**
> "8 refs look like operational markers (phase, cycle, milestone): topic:phase3b, topic:cycle1, ... Rewrite as meta: refs (preserved as metadata, excluded from KG)?"

**Lingering tags cluster:**
> "M files still have `tags:` lines (residual from old templates). Run `science-tool graph migrate-tags --apply` to clean them up?"

### 5. Apply chosen actions

For each cluster the user approves, use the appropriate CLI to apply:
- Rewriting refs: edit frontmatter or task markdown directly (find files via the `sources` field of each ref)
- Creating topic stubs: write minimal entity files matching the existing template structure
- Migrating tags: `science-tool graph migrate-tags --apply` (default meta:)
- Migrating tags as topics: `science-tool graph migrate-tags --apply --as-topic`

### 6. Verify

Re-run `science-tool health` after applying actions to confirm the issue counts dropped. Show the user the delta.

### 7. Commit

```bash
git add <changed files>
git commit -m "chore(health): triage <N> issues — <brief description per cluster>"
```

## Tips

- ALWAYS propose at the cluster level, never per-ref. The user shouldn't make 47 decisions.
- ALWAYS get confirmation before applying changes.
- For ambiguous clusters, ask the user to classify before proposing actions.
- The `looks_like` heuristic is just a hint — let the user override it if they disagree.

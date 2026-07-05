---
description: Run the science health check and triage findings interactively. Use when the user says "check project health", "find issues", "what's broken", or after running migrations.
---

# Health Triage

Aggregate project health diagnostics and walk the user through cluster-level cleanup.

`$ARGUMENTS` optionally specifies the project root (default: current directory).

## Procedure

### 1. Run the health command

```bash
uv run science health --project-root <root> --format=json
```

Parse the JSON output. Fields:
- `unresolved_refs`: list of `{target, mention_count, sources, looks_like}`
- `lingering_tags_lines`: list of `{file, values}`
- `layered_claims`: object with:
  - `proposition_claim_layer_coverage`
  - `causal_leaning_identification_coverage`
  - `rival_model_packets_missing_discriminating_predictions`
  - `migration_issues`

### 2. Cluster issues

Group `unresolved_refs` by `looks_like` heuristic:
- **looks_like=task**: refs like `topic:t143`, `topic:t146` — likely mis-prefixed task IDs
- **looks_like=hypothesis**: refs like `topic:h01` — likely mis-prefixed hypothesis IDs
- **looks_like=question**: refs like `topic:q05` — likely mis-prefixed question IDs
- **looks_like=semantic-triage**: refs like `topic:genomics`, `topic:phase3b` — legacy topic refs that need semantic triage
- **looks_like=unknown**: anything else

For the `semantic-triage` cluster, sub-cluster by intended semantics:
- Catalog-backed entity (`gene`, `protein`, `disease`, `pathway`, etc.)
- Analytical method (`method`)
- Project concept (`concept`, as an `entities/concepts/*.md` owner)
- Structured explanatory bundle (`mechanism`)
- Existing project kind (`question`, `hypothesis`, `interpretation`, `story`, `theme`)
- Metadata or prose-only note

Use the text after `topic:` only as a clue. Do not create `topic:*` stubs as
the default fix.

For legacy topic-shaped refs, user judgment hints can help route the cluster:
- Date-shaped values (`pivot-2026-03-18`): likely operational markers
- Pure short words (`genomics`, `protein`): likely domain entities, concepts, or methods
- State-like (`blocked`, `phase3b`, `cycle1`): likely operational

For refs that look like legitimate new entities, read `docs/process/entity-creation-cookbook.md`
before proposing action. Apply its identity policy triage explicitly: check the
external-id requirement, decide whether the item belongs in a shared registry kind
or a project-local kind, and use the prose-only fallback when the mention should
remain prose rather than become a graph entity.

### 3. Present findings

Show a structured summary:

```
Health Report for <project>
================================
Unresolved References (N total):
  - 5 look like task IDs (would be better as task: refs)
  - 12 legacy topic-shaped refs need semantic triage
  - 8 look like operational markers (consider meta: prefix)

Lingering tags: lines: M files

Total issues: X
```

Include the layered-claim section explicitly:

- authored `claim_layer` coverage across propositions
- authored `identification_strength` coverage across causal-leaning propositions
- unsupported mechanistic narratives still lacking lower-layer support
- proxy-mediated propositions still lacking `measurement_model`
- rival-model packets missing discriminating predictions

If the project is using `independence_group` on only one visible support line for a high-impact proposition, mention that as a fragility note even if it is still being surfaced manually rather than by a dedicated metric.

### 4. Propose batch actions

For each cluster, propose ONE action covering the whole cluster, not per-ref decisions. Examples:

**Task-id cluster:**
> "5 refs look like task IDs being mis-prefixed: topic:t143, topic:t146, topic:t147, topic:t149, topic:t150. Rewrite all as task: refs?"

**Semantic-triage cluster:**
> "12 refs are legacy topic-shaped refs: topic:genomics, topic:protein, topic:embeddings, ... Triage them into catalog-backed entities, methods, concepts in terms.yaml, mechanisms, metadata, or prose-only notes?"

**Operational markers cluster:**
> "8 refs look like operational markers (phase, cycle, milestone): topic:phase3b, topic:cycle1, ... Rewrite as meta: refs (preserved as metadata, excluded from KG)?"

**Lingering tags cluster:**
> "M files still have `tags:` lines (residual from old templates). Remove the `tags:` lines, or replace each with the intended `meta:` or field-scoped `tag:` ref, by hand?"

### 5. Apply chosen actions

For each cluster the user approves, use the appropriate CLI to apply:
- Rewriting refs: edit frontmatter or task markdown directly (find files via the `sources` field of each ref)
- Semantic triage: create or reuse the typed entity chosen by the cookbook, create a concept entity with `science entity create concept "<title>"` when a durable project-local concept is needed, rewrite as `meta:` or field-scoped `tag:` when the mention is classification metadata, or remove the graph ref and keep prose-only notes out of the graph.
- Cleaning up lingering tags: remove the `tags:` lines from the frontmatter, or replace each with the intended `meta:` or field-scoped `tag:` ref, by hand

### 6. Verify

Re-run `science health` after applying actions to confirm the issue counts dropped. Show the user the delta.

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
- **Never clear a belief/evidence check by overstating evidence.** For `belief.fragile-single-line`
  and similar belief/validation warnings, do NOT relabel weak/indirect lines as `strong`/`direct_test`,
  split genuinely-dependent lines (same cohort/instrument/source) into separate `independence_group`s,
  or otherwise misrepresent stance/strength/independence to force a check green. The only valid moves
  are: add *genuine* independent evidence, correct an *actual* mislabeling, or accept the residual flag
  and record why. A check may legitimately stay yellow — never present "overstate to clear it" as an
  option. See [`../docs/user-guide/evidence-lines.md`](../docs/user-guide/evidence-lines.md)
  → *Evidence Integrity (Non-Negotiable)*.

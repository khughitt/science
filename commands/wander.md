---
description: Serendipitous random-sample review loop. Draws N epistemic entities (default 3) from the project graph, reviews each for gaps, looks for unappreciated pairwise connections, and writes a short walk report. Read-only by default; --apply may create tasks. See docs/plans/2026-05-09-wander-design.md.
---

# Wander · Random-sample review loop

Run a small, serendipitous review pass across the project's epistemic
entities. Sampling is weighted by the existing attention machinery
(freshness, time since last review, evidence balance). The agent reviews
each sampled entity for gaps, looks for unappreciated pairwise connections,
flags stub candidates, and writes a short report.

Use `$ARGUMENTS` for optional flags. Recognized:

- `--apply` — consumed by this slash command; permits exactly one side
  effect (creating tasks via `science tasks add`). Without it: report-only.
- `--n N` — number of entities to sample (default 3). Forwarded to CLI.
- `--seed N` — reproducibility seed. Forwarded.
- `--kind K` — restrict to entity kind(s); may repeat. Forwarded.
- `--epsilon F` — sampler weight floor. Forwarded.
- `--graph-path PATH` — override default `knowledge/graph.trig`. Forwarded.

## Phase 1: Materialize the skeleton

Generate a walk path and run the CLI:

```bash
WALK_ID="$(date +%Y-%m-%d-%H%M)"
WALK_PATH="doc/meta/walks/walk-${WALK_ID}.md"
mkdir -p doc/meta/walks
uv run science wander --format markdown --out "${WALK_PATH}" \
  <forwarded flags from $ARGUMENTS, EXCLUDING --apply>
```

If `science wander` exits non-zero with the message about `science graph
build`, surface that to the user and stop — there is no graph to walk.

## Phase 2: Read the skeleton

Read `${WALK_PATH}`. The frontmatter lists the sampled entity IDs. Each
per-entity section already contains a **Context** block (kind, weight,
source path, created date, mtime, length, neighbor counts, active
references) and a **Stub-smell signals** block with four booleans plus
`is_stub_candidate`. Use these — do not re-query the graph.

For each sampled entity, also read its source file (if `source` is set) so
the per-entity review can reference actual content, not just metadata.

## Phase 3: Per-entity review

Fill in the **Gaps:** line under each entity. Categories:

- **Text gaps:** prose quality, missing citations or provenance, broken
  cross-refs, weak or disconnected annotation.
- **Code/data gaps:** *only when the entity references implementation*
  (e.g., a hypothesis pointing at a pipeline). Look for silent failures,
  magic numbers, drift from claimed behavior. Skip if not grounded in code.
- **Epistemic gaps:** unstated assumptions, claims without support edges,
  propositions with stale verdicts.

Brief is correct. If nothing surfaces, write "no gaps surfaced."

## Phase 4: Pairwise connections

For each pair (the skeleton has one heading per pair), write one paragraph
answering:

> Is there an unappreciated connection between these two? If so, what
> would tracking it look like?

Most pairs will be "no obvious connection." Say so in one line and move
on. **Do not invent connections to fill the section.**

## Phase 5: Prune candidates

Replace the **Prune candidates** placeholder with a list of every entity
where `is_stub_candidate: true` in its Stub-smell block. Format:

```
- <entity-id> — <one-line rationale> [first flagged YYYY-MM-DD]
```

If none qualify, write `- none`.

## Phase 6: --apply (only if passed)

If `--apply` is in `$ARGUMENTS`, you may make exactly one kind of side
effect: create tasks via `science tasks add`. Two cases:

1. For pairwise connections you judge worth tracking, add a task:
   `investigate connection: <id-a> ↔ <id-b> — <one-line summary>`.
2. For each prune candidate, add a task:
   `review for deprecation: <entity-id> — reconsider on YYYY-MM-DD`
   (where the date is `today + 30 days`).

Tag each task description with `source: wander/${WALK_ID}` so it traces
back to this walk. Append the resulting task IDs under
**Spawned tasks** in the walk file.

Without `--apply`: leave **Spawned tasks** empty.

## Phase 7: Verify and report

Re-read the walk file end-to-end. Confirm:

- Every per-entity section has a non-empty `Gaps:` line.
- Every pairwise heading has a paragraph.
- `Prune candidates` and `Spawned tasks` are filled (even if "none" or empty).

Print the path of the walk file to the user.

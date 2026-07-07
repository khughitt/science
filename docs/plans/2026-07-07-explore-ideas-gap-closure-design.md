# explore-ideas gap closure — design

**Date:** 2026-07-07
**Target:** `fb-2026-07-04-006`
**Surface:** `science explore-ideas`, `command:explore-ideas`

`science explore-ideas apply` now creates durable question, hypothesis, topic,
and theme entities from kept exploration candidates. That closes the write path,
but it leaves a workflow gap: newly-created entities are intentionally sparse
scaffolds, and the command gives no deterministic next step for closing the
gaps it just exposed.

## Problem

Apply is deliberately mechanical. It validates the report, writes entities,
preserves provenance, and marks candidate blocks as applied. It should not also
make research judgments or author prose. But after apply succeeds, the user has
to manually inspect the report and the new entity files to answer basic
follow-up questions:

- Which applied candidates still have unresolved literature anchors?
- Did expected supporting anchors land as `source_refs`?
- Did `related_existing` land as `related` links?
- Did multi-lens candidates keep their `lens_views`?
- Which created entities are still only scaffold bodies?

That manual inspection is the feedback issue. The fix should expose a reliable
no-write gap report, not auto-fill scientific content.

## Decision

Add a read-only subcommand:

```bash
uv run science explore-ideas gaps --from <report-path-or-id> [--format text|json]
```

The command inspects applied candidate blocks from one exploration report and
reports deterministic gaps on the entities those blocks created. It does not
write files, create tasks, mutate the report, or infer missing scientific prose.

## Scope

In scope:

- Parse the same report format used by `apply`.
- Select only blocks with `decision: applied`.
- Require `applied_as: <entity-id>` to connect a block to its created entity.
- Resolve the entity from local markdown entities.
- Emit one result row per applied block, including missing-entity rows.
- Detect a small, deterministic set of gap codes.
- Provide text and JSON output.

Out of scope:

- Creating tasks or modifying entities.
- Auto-resolving anchors or authoring prose.
- Inspecting non-applied `keep` candidates.
- Cross-report discovery of all explore-created entities.
- Ranking the scientific importance of gaps.

## Gap Codes

The first version should report only gaps that can be derived from the report and
created entity without external judgment.

`missing_applied_as`:
An applied block has no non-empty `applied_as`. Severity `error`. Suggested
action: repair the report block with the created entity id before using the gap
report.

`missing_entity`:
`applied_as` does not resolve to a local entity markdown file. Severity `error`.
Suggested action: check whether the entity was moved, renamed, or never created.

`empty_body`:
The entity body is still only scaffold headings and comments, with no substantive
non-heading prose. Severity `warn`. Suggested action: fill the entity body from
the candidate rationale and supporting evidence.

`unresolved_anchors`:
The candidate has `literature_anchors[]` entries with empty or missing `ref`.
Severity `warn`. Suggested action: run
`science explore-ideas resolve-anchors --from <report>`.

`missing_source_refs`:
The candidate has one or more resolved supporting anchors
(`literature_anchors[].ref` where `note` does not start with `predates:`), but
the created entity has no `source_refs`. Severity `warn`. Suggested action:
apply or manually add the resolved supporting refs.

`missing_related`:
The candidate has `related_existing`, but the created entity has no `related`.
Severity `warn`. Suggested action: rerun apply on a repaired report or add the
canonical related refs.

`missing_lens_views`:
The candidate has explicit `lens_views`, or the older single-lens `lens` plus
`rationale` shape, but the created entity has no `lens_views`. Severity `warn`.
Suggested action: backfill lens views from the report.

## JSON Contract

`--format json` returns a stable object:

```json
{
  "report": "doc/explorations/explore-2026-07-07.md",
  "counts": {
    "entities": 1,
    "gaps": 2,
    "errors": 0,
    "warnings": 2
  },
  "entities": [
    {
      "candidate_id": "cand-x",
      "entity_id": "question:0012-example",
      "kind": "question",
      "path": "entities/questions/0012-example.md",
      "gaps": [
        {
          "code": "unresolved_anchors",
          "severity": "warn",
          "message": "1 literature anchor is unresolved",
          "suggested_action": "Run science explore-ideas resolve-anchors --from doc/explorations/explore-2026-07-07.md"
        }
      ]
    }
  ]
}
```

Path strings are relative to the project root when possible. Missing entities use
`kind: null`, `path: null`, and still include the `entity_id` from `applied_as`.

## Text Contract

Text output should be compact and action-oriented:

```text
2 applied entities inspected, 3 gaps (1 error, 2 warnings)

cand-x -> question:0012-example (question)
  WARN unresolved_anchors: 1 literature anchor is unresolved
    next: Run science explore-ideas resolve-anchors --from doc/explorations/explore-2026-07-07.md
  WARN empty_body: entity body is still scaffold-only
    next: Fill the entity body from the candidate rationale and supporting evidence
```

If no gaps are found, print:

```text
2 applied entities inspected, 0 gaps
```

## Implementation Shape

Keep the implementation in `science_tool.explore_ideas` beside apply and anchor
resolution. Add small dataclasses:

- `GapItem`
- `GapEntity`
- `GapReportResult`

Add a pure-ish orchestration function:

```python
inspect_gaps_report(project_root: Path, from_value: str) -> GapReportResult
```

The function resolves the report, parses blocks, inspects applied blocks, reads
frontmatter/body for each created entity, and returns a structured result. The
CLI layer only renders text or JSON.

Entity lookup should use existing entity iteration/frontmatter utilities rather
than ad hoc path guessing, because ids can be numeric, slug-based, or relocated
by policy.

## Error Handling

The command should fail only on invalid report access or malformed YAML already
handled by `parse_report`. Per-block problems such as missing `applied_as` or
missing entity files are reported as gap rows instead of aborting, because the
point of the command is to surface repair work.

## Alternatives Considered

### Extend `apply --check`

Rejected. `--check` is a pre-write validator and planner. Gap closure is
post-apply inspection. Combining them would make the `apply` command harder to
reason about and blur its zero-write validation semantics.

### Create tasks automatically

Rejected for this slice. Task creation would require deciding task kinds,
owners, ids, duplicate policy, and project backlog conventions. A no-write gap
report is the smaller, safer contract.

### Infer and patch missing content

Rejected. Filling entity prose is scientific authorship. The CLI can identify
deterministic gaps, but an agent or user should decide how to close them.

## Testing

Focused tests should cover:

- JSON shape and text rendering for a clean applied entity.
- `missing_applied_as` for applied blocks with no entity id.
- `missing_entity` when `applied_as` is stale.
- `empty_body` on scaffold-only created entities.
- `unresolved_anchors` for anchors without `ref`.
- `missing_source_refs` when resolved supporting anchors did not land.
- `missing_related` when `related_existing` did not land.
- `missing_lens_views` when report lens views did not land.
- CLI command behavior for `--format text` and `--format json`.

Verification should include the focused explore-ideas tests, command/skill docs
tests, `ruff check`, and `pyright` on touched modules.

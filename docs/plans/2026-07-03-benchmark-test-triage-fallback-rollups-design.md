# Benchmark Test Triage Fallback Rollups Design

## Status

Proposed.

## Context

Recent benchmark calibration across active projects showed that fallback task
support annotation solved the previous "unknown fallback" problem. Visible
fallback rows now have explicit support metadata:

- `ccle-proteomics-nusinow-2020`: `supported`, runnable.
- `cptac-proteogenomics`: `candidate`, metadata-only.
- `dream4-in-silico-network`: `candidate`, metadata-only.

The remaining problem is presentation. In the sampled projects,
`science benchmark test-triage --commons` still reports hundreds of
`fallback-diagnostic` rows, but those rows collapse to the same three
benchmark/task records. The per-entity rows are useful for JSON consumers and
debugging, but they are too repetitive for the default table view.

Current implementation facts:

- `benchmark_tests_report()` emits per-entity `BenchmarkTestRow` rows.
- `benchmark_test_triage_report()` groups those rows into buckets after normal
  filters and blocked-support fallback suppression.
- `fallback_diagnostics` is already a projection over visible
  `fallback-diagnostic` rows.
- The default table currently renders one aggregate fallback diagnostics table
  with `top_benchmarks`, `top_facets`, readiness counts, dataset-class counts,
  and task-support counts.

## Goals

- Make fallback diagnostics actionable by grouping repeated fallback rows by
  benchmark/task.
- Preserve existing per-entity fallback rows in
  `buckets["fallback-diagnostic"]`.
- Keep matching, scoring, sorting, filters, buckets, and suppression behavior
  unchanged.
- Keep the change additive for JSON consumers.
- Make the default table show the grouped fallback records instead of a single
  coarse aggregate row.

## Non-Goals

- Do not change benchmark opportunity or gap matching.
- Do not change fallback candidate scoring.
- Do not hide candidate fallback rows by default.
- Do not replace the existing `top_benchmarks`, `top_facets`, readiness,
  dataset-class, or task-support diagnostic fields.
- Do not change commons metadata.

## Design

Add `fallback_diagnostics.rollups`, a deterministic list of grouped visible
fallback rows. A rollup represents one benchmark/task/readiness/support group
within the already-filtered `fallback-diagnostic` bucket.

The grouping key is:

```text
benchmark_id
task_id
task_support_state
readiness_label
dataset_class
test_plan_state
```

`task_support_reason` is not part of the key because it is determined by the
task support state for a task; the rollup should fail loudly if a group contains
multiple non-empty reasons. That protects against accidental metadata drift
instead of silently picking one.

Each rollup row has this shape:

```json
{
  "benchmark_id": "dataset:cptac-proteogenomics",
  "benchmark_title": "CPTAC proteogenomics",
  "task_id": "dataset:cptac-proteogenomics#protein-rna-cross-modal",
  "task_type": "cross-modal-prediction",
  "count": 297,
  "entity_count": 297,
  "task_support_state": "candidate",
  "task_support_reason": "requires-study-specific-staging",
  "readiness_label": "metadata-only",
  "dataset_class": "reference",
  "test_plan_state": "concrete",
  "top_facets": [
    {"facet": "proteomics", "count": 297},
    {"facet": "multimodal", "count": 297}
  ],
  "example_entities": [
    "hypothesis:...",
    "question:..."
  ],
  "reason_notes": [
    "fallback:high-baseline",
    "task-support:candidate:requires-study-specific-staging"
  ]
}
```

Field notes:

- `count` is the number of fallback rows in the group.
- `entity_count` is the number of distinct `entity_id` values in the group.
  It usually equals `count`, but keeping it explicit prevents ambiguity if
  future multi-task rows create repeated entity/group combinations.
- `top_facets` is computed from `matched_facets` inside the group, sorted by
  count descending and existing facet ordering.
- `example_entities` is capped at three distinct entity ids, sorted by existing
  row order after the current triage sort.
- `reason_notes` is the sorted union of row reason notes in the group.

## JSON Contract

The existing payload remains valid:

```json
{
  "summary": {},
  "buckets": {
    "fallback-diagnostic": []
  },
  "fallback_diagnostics": {
    "top_benchmarks": [],
    "top_facets": [],
    "readiness_counts": {},
    "dataset_class_counts": {},
    "task_support_counts": {},
    "top_benchmarks_by_readiness": {},
    "top_benchmarks_by_dataset_class": {},
    "rollups": []
  }
}
```

`rollups` is always present. When there are no visible fallback rows it is an
empty list. If `--exclude-fallback` removes all fallback rows, `rollups` is
empty. If `--include-blocked-fallback` is supplied, blocked-support fallback
rows are visible and therefore included in `rollups`.

The existing optional `fallback_diagnostics.suppressed_blocked_support` remains
unchanged and continues to describe rows hidden by default. Suppressed rows do
not appear in `rollups` unless `--include-blocked-fallback` makes them visible.

## Table Output

For non-fallback buckets, keep the current top-10 row table behavior.

For `fallback-diagnostic`, replace the current one-row aggregate diagnostics
table with a rollup table:

```text
Benchmark Test Triage: fallback-diagnostic
rows | benchmark | task | support | readiness | class | facets | examples
```

The title remains the same so users recognize the bucket. The first row can
show, for example:

```text
307 | dataset:ccle-proteomics-nusinow-2020 | protein-lineage-association | supported | runnable | deposit | proteomics:307, multimodal:307 | hypothesis:...
```

The table should render at most 10 rollups, sorted by `count` descending with
stable tie-breakers. If total fallback rows exceed visible rollup rows, the
table title or first column text should make the grouping obvious, for example:
`898 fallback rows grouped into 3 rollups`.

The current aggregate counts remain available in JSON and the review artifact.
The table may omit the old aggregate counts because the rollups now carry the
actionable summary.

## Review Artifact

`science benchmark test-triage --write-review-file` should include
`fallback_diagnostics.rollups` automatically because it serializes the same
payload. The full per-entity rows remain in `buckets["fallback-diagnostic"]`.

No separate review schema is introduced in this slice.

## Sorting

Rollups sort by:

1. `count` descending.
2. benchmark id ascending.
3. task id, with `null` rendered/sorted as empty string.
4. support state sort order: `supported`, `candidate`, `blocked`, `none`.
5. readiness order: `runnable`, `stage-needed`, `metadata-only`, `blocked`.

This prioritizes repeated fallback patterns while keeping output stable.

## Error Handling

Rollup construction should fail early if rows in one group disagree on fields
that should be group-invariant:

- `benchmark_title`
- `task_type`
- `task_support_reason`

This should raise `ValueError` from the report builder, matching the existing
fail-loud behavior for invalid benchmark task support metadata.

Missing task support is represented as `task_support_state: null` in row data
and as a `none` count in existing diagnostics. Rollups should preserve
`task_support_state: null` for the row shape rather than inventing a new string
value.

## Testing

Add focused tests for:

- Fallback rollups group repeated fallback rows by benchmark/task and preserve
  existing per-entity rows.
- Rollups carry support state, support reason, readiness label, dataset class,
  test-plan state, top facets, and capped example entities.
- `--exclude-fallback` produces empty rollups.
- `--include-blocked-fallback` includes blocked-support fallback rows in
  rollups, while default output keeps them only under
  `suppressed_blocked_support`.
- The default table renders grouped fallback rollups rather than the old single
  aggregate row.
- Review-file YAML includes `fallback_diagnostics.rollups`.

## Alternatives Considered

### Add `--rollup-fallback`

This would avoid changing the default table, but the default is exactly where
the calibrated noise appears. Users should not need to discover another flag to
make fallback diagnostics readable.

### Replace fallback rows in JSON with rollups

This would make the payload smaller, but it is a breaking change and would
remove useful per-entity debugging evidence. Keeping rows and adding rollups is
safer.

### Stage CPTAC or DREAM4 first

Staging remains valuable, but the calibration showed the current report is now
mostly repeated presentation of known support states. Improving rollups first
will make later staging decisions easier to evaluate.

## Success Criteria

- In real-project calibration, `fallback_diagnostics.rollups` reduces hundreds
  of visible fallback rows to a handful of benchmark/task groups.
- The default table lets a user identify the actionable fallback records without
  reading raw JSON.
- Existing JSON consumers can continue reading `buckets["fallback-diagnostic"]`
  unchanged.
- No benchmark matching, scoring, or bucket counts change.

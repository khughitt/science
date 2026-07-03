# Benchmark Blocked-Fallback Triage Design

## Status

Draft for review.

## Context

`science benchmark tests` is the raw benchmark-test projection. It should keep
emitting every opportunity, gap candidate, and fallback row because downstream
calibration work depends on the full row set.

`science benchmark test-triage` is the action queue. After adding task-local
`tasks[].support`, rows for blocked tasks are correctly routed to
`blocked-or-reference` when they are non-fallback. However, fallback rows are
classified first as `fallback-diagnostic`, so a blocked task such as
`dataset:mmrf-commpass#progression-risk` can still contribute hundreds of broad
fallback diagnostics. In the multiple myeloma calibration run, the useful fact
is that the task is blocked by missing open progression endpoints; listing many
fallback rows for the same blocked task adds noise rather than work.

This slice changes triage presentation only. It does not change matching,
scoring, task support metadata, or the raw `benchmark tests` report.

## Goals

- Make `science benchmark test-triage` less noisy when fallback rows point at a
  task with `task_support_state: blocked`.
- Keep non-fallback blocked rows visible in `blocked-or-reference`.
- Keep raw `science benchmark tests` output unchanged.
- Account for suppressed rows explicitly in JSON and review artifacts; do not
  silently discard them.
- Preserve deterministic local-first behavior and existing filters.

## Non-Goals

- No changes to `gaps_report()` candidate scoring.
- No changes to `benchmark_tests_report()` row generation.
- No new benchmark metadata fields.
- No automatic task promotion or support-state inference from recipe outputs.
- No embedding or semantic matching changes.

## Command Surface

Add one opt-in flag to `science benchmark test-triage`:

```bash
science benchmark test-triage --include-blocked-fallback
```

Default behavior suppresses fallback rows where:

- `priority_source == "gap-fallback"`;
- `task_support_state == "blocked"`.

`--include-blocked-fallback` restores the current behavior for debugging and
calibration. It affects only triage output. It does not affect
`science benchmark tests`, `science benchmark gaps`, or any matching/scoring
helpers.

This is a global default behavior change for `science benchmark test-triage`,
not an MMRF-specific special case. Any blocked task-support fallback row is
hidden from the default action queue and accounted for in suppression
diagnostics.

The existing `--exclude-fallback` flag still wins by removing all fallback rows
before triage bucket assignment. If `--exclude-fallback` is set,
`--include-blocked-fallback` has no visible effect because there are no fallback
rows left to include.

## Data Flow

`benchmark_test_triage_report()` remains a projection over
`benchmark_tests_report()`.

1. Build the raw test rows by calling `benchmark_tests_report()` with the
   existing filters.
2. Partition fallback rows into:
   - visible fallback rows;
   - suppressed blocked-support fallback rows.
3. Bucket visible rows using the existing bucket rules.
4. Add explicit suppression diagnostics to the payload.

The partition happens only inside triage. It should not be pushed down into
`_filter_benchmark_test_rows()` because that helper is shared by the raw test
report and should keep source semantics simple.

`summary.test_plan_rows`, `source_counts`, `fallback_rows`,
`fallback_row_ratio`, and `readiness_counts` are computed over the upstream
`benchmark_tests_report()` rows after normal filters, before blocked-fallback
suppression. `bucket_counts` is computed over displayed triage buckets after
suppression.

## JSON Contract

Additive fields:

```json
{
  "summary": {
    "bucket_counts": {
      "fallback-diagnostic": 27
    },
    "suppressed_blocked_support_fallback_rows": 449
  },
  "fallback_diagnostics": {
    "top_benchmarks": [],
    "top_facets": [],
    "suppressed_blocked_support": {
      "rows": 449,
      "top_benchmarks": [
        {"benchmark_id": "dataset:mmrf-commpass", "count": 449}
      ]
    }
  },
  "filters": {
  }
}
```

`summary.test_plan_rows`, `source_counts`, `fallback_rows`, and
`fallback_row_ratio` continue to describe the upstream `benchmark_tests_report()`
row set after normal filters. `bucket_counts` describes the displayed triage
buckets after blocked-fallback suppression. The new suppression count explains
the difference between those populations.

Only `summary.suppressed_blocked_support_fallback_rows` is added for v1. A
generic `suppressed_fallback_rows` field would be identical in this slice
because blocked task support is the only suppression reason; do not add it until
there is a second suppression class.

`fallback_diagnostics.suppressed_blocked_support.top_benchmarks` aggregates by
`benchmark_id`, which is a stable row field. Do not add `top_reasons` in v1:
`task_support_reason` is free text, and `reason_notes` are mixed-purpose notes,
so neither is a clean controlled histogram source.

`filters` keeps the existing sparse-filter convention. Add
`include_blocked_fallback: true` only when the flag is provided; omit it for the
default false case.

When `--include-blocked-fallback` is used:

- `filters.include_blocked_fallback` is `true`;
- suppressed counts are zero;
- blocked-support fallback rows appear in `fallback-diagnostic` as they do
  today.

## Table Output

Default table output should not render the suppressed rows as fallback work. If
suppressed rows exist, print a compact diagnostic line/table after the normal
fallback diagnostics:

```text
Suppressed 449 fallback rows for blocked task support
top benchmarks: dataset:mmrf-commpass (449)
```

This keeps the existence of the data visible without letting it dominate the
work queue. Render this suppression note behind its own
`suppressed_blocked_support_fallback_rows > 0` gate, independent of whether the
visible `fallback-diagnostic` bucket is empty.

## Review Artifact

`--write-review-file` should include the same suppression diagnostics as JSON.
Suppressed rows should not be expanded into the review buckets by default; the
artifact is meant to be an actionable queue, not a dump of known-blocked
fallback matches.

If a reviewer needs the old full diagnostic list, they can regenerate with
`--include-blocked-fallback`.

## Error Handling

No new error states are introduced. The new flag is orthogonal to `--format`,
`--write-review-file`, `--readiness`, and `--source`.

One interaction is worth making explicit in tests:

- `--source gap-fallback --include-blocked-fallback` shows blocked fallback
  rows;
- `--source gap-fallback` without the flag suppresses blocked fallback rows but
  reports their suppressed count;
- `--exclude-fallback --include-blocked-fallback` returns no fallback rows and
  no suppressed rows because fallback rows were intentionally excluded.

## Testing

Add focused tests for:

- `benchmark_test_triage_report()` suppresses `gap-fallback` rows with
  `task_support_state == blocked` by default.
- The same rows are restored with `include_blocked_fallback=True`.
- Non-fallback blocked rows still route to `blocked-or-reference`.
- Non-blocked fallback rows still appear in `fallback-diagnostic`.
- Summary suppression counts explain the gap between upstream fallback counts
  and displayed fallback bucket counts.
- `readiness_counts` still include suppressed rows because they describe the
  upstream post-filter row set, not only visible buckets.
- CLI `--include-blocked-fallback` is reflected in JSON `filters` when true and
  omitted when false.
- Table output includes a compact suppression diagnostic when rows are hidden.
- Review YAML includes suppression diagnostics and does not expand suppressed
  rows by default.

## Calibration Check

After implementation, rerun:

```bash
science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --benchmark mmrf-commpass \
  --format json
```

Expected qualitative result:

- non-fallback MMRF rows remain in `blocked-or-reference`;
- `fallback-diagnostic` no longer dominates the queue for the blocked
  progression task;
- suppression diagnostics report the hidden blocked-support fallback rows;
- `--include-blocked-fallback` restores the previous diagnostic volume.

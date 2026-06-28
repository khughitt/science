# Benchmark Fallback Diagnostics Design

## Goal

Make benchmark gap fallback candidates explainable without changing matching,
candidate scores, or ranking. The batch calibration report should show whether
fallback rows are mostly generic task-ready suggestions, baseline-quality
suggestions, or concentrated repeats of the same few benchmarks.

## Non-Goals

- Do not change candidate scores.
- Do not change candidate ordering.
- Do not add project-specific heuristics.
- Do not require `--calibration-report`; this is summary-level diagnostics.

## Candidate Row Contract

Fallback candidates currently replace all score notes with
`["high-baseline-fallback"]`. Replace that one-note marker with fallback-specific
reason notes derived from the same `CandidateScore.components` used to compute
the existing `candidate_score`:

- `fallback:task-ready` when `task_readiness > 0`
- `fallback:baseline-quality` when `baseline_quality > 0`
- `fallback:positive-score` when the candidate has a positive score but neither
  of the above applies
- `fallback:available-benchmark` when the fallback has no positive score

Entity-specific candidates keep their existing `missing-facet:*`,
`entity-hint:*`, `task-ready`, and `high-baseline` notes. A candidate is a
fallback candidate when any `reason_notes[]` entry starts with `fallback:`.

This keeps `candidate_score` intact and makes the explanation live where users
already look: `reason_notes`.

## Summary Contract

Extend `GapCalibrationSummary` additively with:

```json
{
  "top_fallback_reasons": [
    {"reason": "fallback:task-ready", "count": 12}
  ],
  "top_fallback_benchmark_shares": [
    {"benchmark_id": "dataset:cptac-proteogenomics", "count": 12, "share": 0.333}
  ],
  "fallback_concentration_warning": true
}
```

`share` is the benchmark's fallback count divided by all fallback candidate rows
in the same summary, rounded to three decimals. The concentration warning is
`true` when there are fallback rows and the top fallback benchmark accounts for
at least half of them.

Extend the batch aggregate with the same three fields, computed from all gap
rows across projects. Per-project rows inherit the extended
`calibration_summary` shape automatically.

## CLI Contract

`science benchmark gaps --calibration-summary --format json` and
`science benchmark gap-calibration --format json` expose the new fields.

Table output adds compact rows:

- `top_fallback_reasons`
- `top_fallback_benchmark_shares`
- `fallback_concentration_warning`

The existing `top_fallback_benchmarks` field remains for compatibility.

## Error Handling

No new error cases. Fallback diagnostics are pure projections over existing
rows. Empty fallback sets produce:

- `top_fallback_reasons: []`
- `top_fallback_benchmark_shares: []`
- `fallback_concentration_warning: false`

## Testing

Tests should verify:

- Fallback candidates use `fallback:*` reason notes while preserving score.
- `gap_calibration_summary()` reports fallback reason counts and benchmark
  shares.
- Batch aggregate merges fallback diagnostics across projects.
- CLI JSON and table outputs include the new diagnostics.


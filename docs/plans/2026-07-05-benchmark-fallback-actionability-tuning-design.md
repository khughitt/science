# Benchmark Fallback Actionability Tuning Design

## Context

The second context-fit calibration pass across active projects showed that the
direct-fit warning leak is fixed, but benchmark reports are still dominated by
generic fallback:

- gap candidates: `1801 / 2453` are `generic-fallback` (`0.73`);
- triage rows: `1493 / 1786` are `generic-fallback` (`0.84`);
- the top fallback benchmarks are high-quality shared benchmarks such as
  `dataset:mmrf-commpass`, `dataset:dream4-in-silico-network`,
  `dataset:ccle-proteomics-nusinow-2020`, `dataset:cptac-proteogenomics`, and
  `dataset:cptac-gbm-2021-proteogenomics`;
- warned direct-fit rows are now `0`, so the next bottleneck is report
  actionability, not direct-fit classification.

Current behavior is intentionally conservative:

- `gaps_report()` keeps fallback candidates when an entity has no
  entity-specific benchmark evidence;
- `_candidate_rows()` returns either entity-specific candidates or fallback
  candidates, never a mixed row;
- fallback candidates are already labeled through `reason_notes` such as
  `fallback:baseline-quality`, `fallback:task-ready`, and selection notes;
- benchmark-test rows also carry `context_fit`, where low-evidence fallback rows
  commonly classify as `generic-fallback`;
- `benchmark test-triage` already suppresses blocked task-support fallback rows
  by default and reports that suppression explicitly.

The remaining issue is that generic fallback rows still take too much terminal
and review attention. They are useful diagnostic evidence about the benchmark
catalog, but they are rarely the next action for a project.

## Goals

- Make default terminal and review-artifact output emphasize actionable
  benchmark rows before generic fallback diagnostics.
- Preserve raw report semantics: do not remove fallback rows from
  `gaps_report()` or `benchmark_tests_report()`.
- Reuse existing fallback evidence (`priority_source`, `context_fit`,
  `reason_notes`, task support, readiness) instead of introducing another
  matcher or score.
- Account for hidden/collapsed fallback rows explicitly in summaries and
  diagnostics.
- Keep the behavior deterministic, local-first, and compatible with current JSON
  consumers.

## Non-Goals

- Do not change `baseline_score`, `candidate_score`, `relative_score`, or
  fallback selection.
- Do not change entity-token matching, facet hinting, or context-fit
  classification in this slice.
- Do not edit benchmark metadata or project entities.
- Do not hide fallback rows from explicit diagnostic views.
- Do not add embeddings, ontology lookups, or model calls.

## Decision

Add a small **fallback presentation layer** over existing rows.

The raw gap/test reports continue to produce the same candidate/test rows. The
presentation layer classifies fallback rows into display groups, hides the most
generic groups from default terminal detail, and reports counts/rollups so the
omitted rows are visible as diagnostics.

The primary rule is:

> Raw reports answer "what did the system consider?" Actionability views answer
> "what should a project look at first?"

This means default table output and review artifacts may collapse generic
fallback, but JSON fields that currently contain raw rows stay populated unless
a user explicitly requests a filtering option that already exists
(`--exclude-fallback`, `--context-fit`, `--source`, etc.).

## Fallback Display Groups

Introduce an internal display grouping derived from existing row fields.

For benchmark-test rows, fallback status is `priority_source == "gap-fallback"`.
For gap-candidate rows, fallback status is the existing reason-note predicate
used by `_is_fallback_candidate()` because public gap candidates do not carry a
`priority_source` field.

| Group | Predicate | Meaning |
| --- | --- | --- |
| `specific-fallback` | `priority_source == "gap-fallback"` and `context_fit != "generic-fallback"` | A fallback row has some contextual signal despite coming from fallback selection. |
| `blocked-support-fallback` | existing blocked task-support predicate | A fallback row is blocked by task support and should stay suppressed by default. |
| `generic-baseline-fallback` | `context_fit == "generic-fallback"` and reason notes include `fallback:baseline-quality` or `selected:generic-baseline` | High-quality benchmark with no project/entity-specific evidence. |
| `generic-task-ready-fallback` | `context_fit == "generic-fallback"` and reason notes include `fallback:task-ready` or `selected:task-ready`, but not baseline-generic | Task metadata/readiness drove selection without entity evidence. |
| `generic-available-fallback` | `context_fit == "generic-fallback"` and neither generic-baseline nor generic-task-ready predicates match | Catch-all generic fallback selected because it was available. |

The groups are presentation categories, not new scientific claims. They should
be computed from row fields at the edge where tables, review artifacts, and
diagnostic summaries are built.

If a row satisfies multiple generic predicates, precedence is:

1. `blocked-support-fallback`;
2. `generic-baseline-fallback`;
3. `generic-task-ready-fallback`;
4. `generic-available-fallback`.

`specific-fallback` applies only to non-blocked fallback rows whose
`context_fit` is not `generic-fallback`.

## Benchmark Gaps Output

### JSON

Keep `benchmark_gaps[].candidate_benchmarks` unchanged.

Add a top-level `fallback_diagnostics` object to the gap payload:

```json
{
  "fallback_diagnostics": {
    "candidate_rows": 2274,
    "generic_fallback_candidate_rows": 1801,
    "specific_fallback_candidate_rows": 0,
    "groups": {
      "generic-baseline-fallback": 1200,
      "generic-task-ready-fallback": 550,
      "generic-available-fallback": 51,
      "blocked-support-fallback": 308,
      "specific-fallback": 0
    },
    "top_generic_fallback_benchmarks": [
      {"benchmark_id": "dataset:mmrf-commpass", "count": 758}
    ]
  }
}
```

Counts are computed over the row set after normal gap filters, including
`--context-fit`. This makes diagnostics explain the current payload, not a
separate global universe.

### Table

The `benchmark gaps` table should stop printing generic fallback benchmark ids
as if they were ordinary candidates.

For each gap row:

- entity-specific candidates: show as today;
- `specific-fallback`: show candidate ids with their context-fit labels;
- all-generic fallback rows: show a compact label, e.g.
  `generic fallback: 3 candidates (top: dataset:mmrf-commpass)`;
- mixed generic/specific fallback should not occur with the current
  `_candidate_rows()` contract, but if it appears, fail loudly rather than
  silently choosing one representation.

The table may show a footer line when generic fallback was collapsed:

`Collapsed 1801 generic fallback candidates; use --calibration-summary or --format json for diagnostics.`

This is presentation-only. `--format json` remains raw and machine-readable.

## Benchmark Test Triage Output

### JSON

Keep existing bucket rows intact, except for the existing default suppression of
blocked task-support fallback rows. Keep existing
`fallback_diagnostics.rollups` intact as the complete fallback rollup list for
the visible row set; changing that field to contain only terminal-visible
rollups would be a semantic break for JSON consumers.

Extend `fallback_diagnostics` with display-group counts and presentation
metadata:

```json
{
  "fallback_diagnostics": {
    "display_group_counts": {
      "specific-fallback": 0,
      "generic-baseline-fallback": 900,
      "generic-task-ready-fallback": 500,
      "generic-available-fallback": 93,
      "blocked-support-fallback": 0
    },
    "hidden_generic_fallback_rows": 1493,
    "shown_fallback_rows": 0,
    "top_generic_fallback_benchmarks": [
      {"benchmark_id": "dataset:mmrf-commpass", "count": 758}
    ],
    "terminal_visible_rollup_count": 0,
    "terminal_hidden_rollup_count": 18,
    "rollups": [
      {
        "benchmark_id": "dataset:mmrf-commpass",
        "count": 758,
        "display_group": "generic-baseline-fallback"
      }
    ]
  }
}
```

`hidden_generic_fallback_rows` means "hidden from default terminal detail," not
"removed from JSON." For default JSON output, the existing bucket rows stay in
`buckets["fallback-diagnostic"]` unless the user supplies an existing filter
that removes them, and `fallback_diagnostics.rollups` remains the complete
diagnostic rollup list.

### Table

Default `benchmark test-triage` should render fallback detail only for
non-generic fallback rollups. Generic fallback remains present in JSON rollups
but gets only a compact terminal diagnostic summary:

- rows hidden from detailed fallback table;
- top generic fallback benchmarks;
- top generic fallback reason notes;
- instruction to use `--context-fit generic-fallback` or `--format json` for
  full diagnostics.

This keeps the terminal action queue focused on:

1. run-now;
2. stage-next;
3. metadata-needed;
4. blocked/reference;
5. non-generic fallback diagnostics;
6. compact generic fallback summary.

The existing `--include-blocked-fallback` flag continues to control blocked
task-support fallback visibility. It does not force generic fallback rollups to
expand.

## Explicit Diagnostic Views

Do not add a new command in this slice.

Existing filters are enough for explicit diagnostics:

- `science benchmark gaps --context-fit generic-fallback --format json`
- `science benchmark tests --source gap-fallback --context-fit generic-fallback`
- `science benchmark test-triage --source gap-fallback --context-fit generic-fallback`
- `science benchmark test-triage --exclude-fallback`

In v1, full generic fallback detail is a JSON/debug surface, not a default table
surface. If users repeatedly need expanded generic fallback tables, a later
slice can add an explicit `--include-generic-fallback-detail` flag. V1 should
avoid a new flag until the table-summary behavior is calibrated.

## Error Handling

- Fallback group derivation must be total for fallback rows. Unknown combinations
  raise `ValueError` with the benchmark id and reason notes.
- Non-fallback rows must not be passed to fallback group helpers; doing so raises
  immediately.
- If a table path receives a fallback row set that mixes
  `specific-fallback` and generic groups in a single gap row, raise an error.
  Current `_candidate_rows()` makes this impossible, so a mixed row would signal
  a contract change.
- Diagnostics counts must reconcile with the raw row counts they summarize.
  Mismatches fail tests.

## Testing

Add focused tests for:

- fallback group derivation from reason notes and `context_fit`;
- `gaps_report()` includes `fallback_diagnostics` whose counts reconcile with
  `benchmark_gaps[].candidate_benchmarks`;
- `benchmark gaps` table collapses all-generic fallback candidates while JSON
  still includes raw candidate ids;
- `benchmark test-triage` fallback diagnostics split hidden generic rows from
  shown non-generic fallback rows;
- blocked task-support fallback suppression still works and is counted
  separately from generic fallback collapse;
- existing filters (`--context-fit generic-fallback`, `--source gap-fallback`,
  `--exclude-fallback`) interact deterministically with diagnostics.

Run at minimum:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py -q
```

After implementation, rerun the four-project calibration report or a smaller
smoke pass to confirm:

- generic fallback counts are still visible;
- default tables are shorter and more actionable;
- no warned direct-fit rows reappear;
- raw JSON counts still match the pre-change calibration envelope except for
  additive diagnostics.

## Success Criteria

- `benchmark gaps` and `benchmark test-triage` no longer spend most default
  terminal rows on generic fallback ids.
- JSON consumers can still inspect every fallback row they could inspect before.
- Generic fallback is counted explicitly, not silently discarded.
- The active-project smoke pass shows the same raw fallback dominance but better
  default presentation: generic fallback is summarized, while run/stage/metadata
  rows and non-generic fallback remain visible.

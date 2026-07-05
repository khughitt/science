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

Introduce an internal display grouping derived from existing row fields. The
group is a **per-row** function, `display_group(row)`, computed by one pure
helper in the report layer and consumed by both JSON payloads and tables.

### Normalized inputs

The two row types expose different fields, so the helper reads a normalized view
rather than a single field:

| Signal | Gap-candidate row (`GapCandidateBenchmarkRow`) | Benchmark-test row (`BenchmarkTestRow`) |
| --- | --- | --- |
| `is_fallback` | `_is_fallback_candidate(row)` (reason-note predicate; gap rows have no `priority_source`) | `priority_source == "gap-fallback"` |
| `context_fit` | present | present |
| `blocked` | `"blocked-support-fallback" in context_fit_warnings` | `_is_blocked_support_fallback(row)` (`priority_source == "gap-fallback" and task_support_state == "blocked"`) |

Both row types can express the blocked signal, but through different fields. Gap
candidates carry no `task_support_state`; instead their `context_fit_warnings`
inherit `blocked-support-fallback` because `_summarize_gap_candidate_test_rows`
**unions** the warnings across the candidate's per-task test rows. So a gap
candidate is `blocked` iff any of its underlying test rows was a blocked-support
fallback. `blocked-support-fallback` is therefore derivable on **both** row types,
and the gaps `fallback_diagnostics.groups` includes it.

Caveat (gap side): because the gap candidate aggregates across tasks (min
`context_fit`, unioned warnings), one blocked task marks the whole benchmark
`blocked-support-fallback` (precedence 1), even if the candidate is actionable on
another task. This is an accepted consequence of benchmark-level gap aggregation;
per-task actionability remains visible in `benchmark test-triage`.

### Groups (per-row, precedence order)

`display_group(row)` is total over fallback rows. Precedence resolves overlaps —
the first matching rule wins:

| Precedence | Group | Predicate | Row types |
| --- | --- | --- | --- |
| 1 | `blocked-support-fallback` | `is_fallback and blocked` (see the normalized `blocked` signal) | both |
| 2 | `specific-fallback` | `is_fallback and context_fit != "generic-fallback"` | both |
| 3 | `generic-baseline-fallback` | `is_fallback and context_fit == "generic-fallback" and "fallback:baseline-quality" in reason_notes` | both |
| 4 | `generic-task-ready-fallback` | `is_fallback and context_fit == "generic-fallback" and "fallback:task-ready" in reason_notes` | both |
| 5 | `generic-available-fallback` | `is_fallback and context_fit == "generic-fallback"` (catch-all) | both |

Notes:

- Keying `generic-baseline-fallback` on `fallback:baseline-quality` alone is
  sufficient — `_selection_reason_note` only emits `selected:generic-baseline`
  when `fallback:baseline-quality` is already present, so the `selected:*` spelling
  is redundant. Same for the task-ready pair.
- `specific-fallback` (precedence 2) sits above the generic rules by construction:
  a non-generic `context_fit` cannot also be `generic-fallback`. It captures only
  **non-blocked** fallback rows with a real context signal, because
  `blocked-support-fallback` (precedence 1) claims blocked rows first.
- The three `generic-*` groups are the **collapsible** set. `specific-fallback`
  and `blocked-support-fallback` are handled separately (on the test side,
  blocked-support rows are additionally suppressed before bucketing by default).

### Rollups must be group-homogeneous

`_benchmark_test_fallback_rollups` currently keys on
`(benchmark_id, task_id, task_support_state, readiness_label, dataset_class,
test_plan_state)` and unions `reason_notes`. That key omits `context_fit`, and the
`fallback-diagnostic` bucket is filled purely by `priority_source == "gap-fallback"`
(`_benchmark_test_triage_bucket`), so a single rollup can currently span
`specific-fallback` **and** `generic-*` rows. Attaching one `display_group` per
rollup is only well-defined if the rollup is homogeneous.

Therefore: **add `display_group` to the rollup grouping key.** Each rollup then
carries exactly one group, and the presentation layer can render or collapse it by
group. (In practice this splits a benchmark/task rollup into at most two — a
`specific-fallback` rollup and one `generic-*` rollup — since baseline/task-ready
notes are constant per benchmark/task and only `context_fit` varies across
entities.)

## Reconciliation Invariants

The five groups are a precedence **partition** of the fallback rows, so counts
reconcile by construction. State these invariants and test them:

- `Σ display_group_counts == total_fallback_rows` in the scope being summarized.
- `generic_fallback_rows := generic-baseline + generic-task-ready +
  generic-available`. This is the collapsible count. **Define it as the sum of the
  three generic groups, not as a raw `context_fit == "generic-fallback"` scan.**
  The two differ: a blocked, no-context fallback row has
  `context_fit == "generic-fallback"` yet belongs to `blocked-support-fallback` by
  precedence, so a raw `context_fit` scan double-counts it.
- `hidden_generic_fallback_rows == generic_fallback_rows` (all three generic
  groups are hidden from default terminal detail).
- `shown_fallback_rows == specific-fallback` count.
- `generic_fallback_rows` and a raw `context_fit == "generic-fallback"` scan
  differ by the blocked, no-context rows (which are `context_fit ==
  "generic-fallback"` but grouped `blocked-support-fallback` by precedence). This
  holds on **both** row types now that gap candidates derive blocked-support from
  the unioned warning. On the test side, blocked-support rows are additionally
  partitioned out before bucketing by default, so the default-visible test set has
  no blocked-support rows at all.

## Benchmark Gaps Output

### JSON

Keep `benchmark_gaps[].candidate_benchmarks` unchanged.

Add a top-level `fallback_diagnostics` object to the gap payload. `groups` carries
all five display groups, including `blocked-support-fallback` (derived from the
`blocked-support-fallback` warning unioned onto gap candidates):

```json
{
  "fallback_diagnostics": {
    "candidate_rows": 2274,
    "entity_specific_candidate_rows": 473,
    "fallback_candidate_rows": 1801,
    "generic_fallback_candidate_rows": 1801,
    "specific_fallback_candidate_rows": 0,
    "groups": {
      "specific-fallback": 0,
      "blocked-support-fallback": 0,
      "generic-baseline-fallback": 1200,
      "generic-task-ready-fallback": 550,
      "generic-available-fallback": 51
    },
    "top_generic_fallback_benchmarks": [
      {"benchmark_id": "dataset:mmrf-commpass", "count": 758}
    ]
  }
}
```

The example reconciles (per Reconciliation Invariants):

- `fallback_candidate_rows` (`1801`) `== Σ groups` (`0 + 0 + 1200 + 550 + 51`);
- `generic_fallback_candidate_rows` (`1801`) `==` the three `generic-*` groups;
- `candidate_rows` (`2274`) `== entity_specific_candidate_rows` (`473`) `+
  fallback_candidate_rows` (`1801`).

Counts are computed over the row set after normal gap filters, including
`--context-fit`. This makes diagnostics explain the current payload, not a
separate global universe.

### Table

The `benchmark gaps` table should stop printing generic fallback benchmark ids
as if they were ordinary candidates.

`_candidate_rows()` guarantees a gap row's `candidate_benchmarks` is either all
entity-specific **or** all fallback — never a mix of those two. It does **not**
guarantee that the fallback set is display-group-homogeneous: `_select_fallback_rows`
can return several fallback candidates for one entity, and they may differ in
`context_fit` (one shares a project/entity context token → `specific-fallback`;
others do not → `generic-*`). So a single gap row can legitimately carry both
`specific-fallback` and generic fallback candidates, and the table must render
each candidate by its own group rather than assume a single representation:

- entity-specific candidates: show as today;
- `specific-fallback` candidates: show candidate ids with their context-fit
  labels (shown individually even when generic candidates are present in the same
  row);
- generic fallback candidates (`generic-*`): collapse into one compact label per
  row, e.g. `generic fallback: 3 candidates (top: dataset:mmrf-commpass)`.

The only contract that warrants a loud failure is the one `_candidate_rows()`
actually enforces: a row that mixes **entity-specific and fallback** candidates
signals a contract change and should raise (see Error Handling). Mixed display
groups *within the fallback set* are expected and are rendered per bullet above.

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

Each rollup now carries a single `display_group` because the rollup grouping key
gains `display_group` (see "Rollups must be group-homogeneous"). `rollups`
therefore partitions cleanly into terminal-visible (`specific-fallback`) and
terminal-hidden (`generic-*`) rollups; `terminal_visible_rollup_count` and
`terminal_hidden_rollup_count` count those two partitions of the full `rollups`
list.

This example reconciles: `display_group_counts` sums to `1493`
(`0 + 900 + 500 + 93 + 0`); `hidden_generic_fallback_rows` (`1493`) equals the
three `generic-*` groups; `shown_fallback_rows` (`0`) equals `specific-fallback`.
`blocked-support-fallback` is `0` here because blocked task-support rows are
partitioned out before bucketing by default (`_partition_blocked_support_fallback_rows`)
and reported under the existing `suppressed_blocked_support` key, not folded into
the generic collapse.

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

- Fallback group derivation must be total for fallback rows: every fallback row
  matches exactly one of the five groups (the `generic-available-fallback`
  catch-all guarantees totality). A fallback row that somehow matches none raises
  `ValueError` with the benchmark id and reason notes.
- Non-fallback rows must not be passed to `display_group(...)`; doing so raises
  immediately.
- `blocked-support-fallback` must not be requested for gap-candidate rows (they
  carry no `task_support_state`). Asking for it on the gap side raises.
- Raise only on the contract `_candidate_rows()` actually enforces: a gap row
  whose `candidate_benchmarks` mixes **entity-specific and fallback** candidates
  signals a contract change and must raise. Do **not** raise on mixed *display
  groups within the fallback set* — that is expected (see Benchmark Gaps Table).
- Diagnostics counts must reconcile with the raw row counts they summarize, per
  Reconciliation Invariants (`Σ display_group_counts == total_fallback_rows`;
  `generic_fallback_rows` is the sum of the three generic groups, never a raw
  `context_fit` scan). Mismatches fail tests.

## Testing

Add focused tests for:

- `display_group(...)` per-row derivation on **both** row types, including the
  precedence partition (blocked-support > specific > generic-baseline >
  generic-task-ready > generic-available) and totality via the catch-all;
- `display_group(...)` raises on a non-fallback row, and
  `blocked-support-fallback` is derived for gap candidates from the
  `blocked-support-fallback` warning unioned across underlying task rows;
- `gaps_report()` includes `fallback_diagnostics` whose counts satisfy the
  Reconciliation Invariants (`fallback_candidate_rows == Σ groups`;
  `generic_fallback_candidate_rows ==` the three generic groups; gaps `groups`
  includes all five display groups);
- a single gap row whose fallback candidates mix `specific-fallback` and
  `generic-*`: the table shows the specific candidate(s) individually and
  collapses the generic ones — it does **not** raise;
- a gap row mixing entity-specific and fallback candidates **does** raise (the
  real `_candidate_rows()` contract);
- `benchmark gaps` table collapses generic fallback candidates while JSON still
  includes raw candidate ids;
- `benchmark test-triage` rollups are group-homogeneous (each rollup has exactly
  one `display_group`) and diagnostics split hidden generic rows from shown
  `specific-fallback` rows;
- blocked task-support fallback suppression still works, is reported under
  `suppressed_blocked_support`, and is counted separately from generic collapse;
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

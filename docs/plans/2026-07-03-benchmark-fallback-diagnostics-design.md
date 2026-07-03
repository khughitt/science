# Benchmark Fallback Diagnostics Design

Date: 2026-07-03

## Context

`science benchmark test-triage` now suppresses fallback rows whose benchmark task support is explicitly blocked, which fixed the MMRF `progression-risk` noise without changing the raw `science benchmark tests` report.

A calibration sweep across active projects showed that the remaining problem is not another blocked-task case. Visible fallback rows are dominated by broad, reusable benchmarks:

- `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association` is a runnable deposit fallback.
- `dataset:cptac-proteogenomics#protein-rna-cross-modal` is a metadata-only reference fallback.
- `dataset:dream4-in-silico-network#network-reconstruction` is a metadata-only pointer fallback.

These are different action classes, but the current fallback diagnostic table reports only total rows, top benchmarks, and top facets. The result is too flat: a valid runnable broad fallback looks like the same problem as a reference/pointer fallback that cannot be run yet.

## Goals

1. Make `fallback-diagnostic` output explain the remaining fallback rows by actionability class.
2. Preserve current `benchmark tests` output and current blocked-support fallback suppression.
3. Keep the JSON contract additive for existing consumers.
4. Avoid changing benchmark scoring, matching, suppression policy, or commons metadata.
5. Provide enough diagnostics to decide whether the next benchmark slice should be seed metadata, task support annotation, or report ergonomics.

## Non-Goals

- Do not suppress metadata-only fallback rows by default.
- Do not demote runnable broad fallback rows like CCLE.
- Do not edit commons benchmark records in this slice.
- Do not introduce embeddings, semantic matching, or new relevance scoring.
- Do not change `benchmark_tests_report()` row inclusion semantics.

## Design

### Row Metadata

Add `dataset_class` to `BenchmarkTestRow`.

Read it directly from `context.dataset.dataset_class` in the row builder. That field is already normalized via `dataset_class_for` at dataset construction, so the row builder must not re-call `dataset_class_for(fm)` — reusing the field keeps a single classification path (see Data Flow, "No second matching path"). It is emitted unchanged as one of:

- `deposit`
- `reference`
- `pointer`

This is additive JSON surface on `science benchmark tests` and `science benchmark test-triage`. It makes downstream consumers able to distinguish staged/stageable data packages from reference portals and tracked pointers without reloading benchmark metadata.

### Fallback Diagnostics

Extend `BenchmarkTestTriageFallbackDiagnostics` with additive fields computed only from visible `fallback-diagnostic` rows:

```yaml
fallback_diagnostics:
  top_benchmarks: []
  top_facets: []
  readiness_counts:
    runnable: 0
    stage-needed: 0
    metadata-only: 0
    blocked: 0
  dataset_class_counts:
    deposit: 0
    reference: 0
    pointer: 0
  task_support_counts:
    supported: 0
    candidate: 0
    blocked: 0
    none: 0
  top_benchmarks_by_readiness:
    runnable: []
    stage-needed: []
    metadata-only: []
    blocked: []
  top_benchmarks_by_dataset_class:
    deposit: []
    reference: []
    pointer: []
```

`top_benchmarks` and `top_facets` keep their existing meaning and ordering. The new counts and grouped top benchmarks are projections over the same visible fallback rows. Suppressed blocked-support fallback rows remain reported separately under `suppressed_blocked_support` and are not included in these visible fallback diagnostics.

Each count block enumerates the *full* domain of its field so it always sums to the visible fallback row count:

- `readiness_counts` — all four `ReadinessLabel` values (`runnable`, `stage-needed`, `metadata-only`, `blocked`).
- `dataset_class_counts` — all three `DatasetClass` values (`deposit`, `reference`, `pointer`).
- `task_support_counts` — all three `BenchmarkTaskSupportState` values (`supported`, `candidate`, `blocked`) plus `none`.

`task_support_state` is `BenchmarkTaskSupportState | None`, so a visible fallback row can carry `supported` — gap-fallback rows are built from `context.dataset.tasks`, and only `blocked`-support rows are partitioned into the suppressed block. `supported` must therefore have its own bucket, not be folded into `none`; a `supported` benchmark surfacing only as a fallback match is itself a signal worth counting. Use `none` only for rows where `task_support_state` is missing (`None`).

This `readiness_counts` is scoped to visible fallback rows and is intentionally distinct from the existing `summary.readiness_counts`, which is computed over all rows. Keep both; they are at different nesting levels and do not collide.

### Table Output

Keep the existing compact fallback diagnostic table — a single aggregate row (`rows | top benchmarks | top facets`) — and add three columns:

- `readiness`
- `class`
- `support`

Each new column renders its corresponding `*_counts` map inline as a compact `key:count` distribution (omit or show zero-count keys consistently, matching how `top benchmarks`/`top facets` render today). The table stays a single aggregate row; it does not enumerate individual fallback rows. Watch the fixed `Console(width=200)`: six folded columns are tight, so keep the distributions terse.

It should make cases like these readable at a glance:

- mostly `runnable` + `deposit`: likely valid broad fallback coverage
- mostly `metadata-only` + `reference`: may need staged deposit alternatives or clearer reference expectations
- mostly `metadata-only` + `pointer`: may need promotion, support metadata, or continued tracking only

The suppressed blocked fallback table stays independent and appears only when rows were suppressed.

### Sorting And Counting

Use the existing deterministic count-row ordering:

1. descending count
2. lexical key

Grouped top benchmark lists should use the same ordering as `top_benchmarks`, scoped to each group.

Counts must be total over visible fallback rows only:

- `sum(readiness_counts.values()) == fallback bucket row count`
- `sum(dataset_class_counts.values()) == fallback bucket row count`
- `sum(task_support_counts.values()) == fallback bucket row count`

If there are no visible fallback rows, counts should still be emitted with zero values and grouped top lists should be empty. This keeps the JSON shape stable.

## Data Flow

1. `benchmark_test_triage_report()` calls `benchmark_tests_report()` unchanged.
2. Existing filters run unchanged.
3. Blocked-support fallback partitioning runs unchanged.
4. Visible rows are bucketed unchanged.
5. Fallback diagnostics are computed from `buckets["fallback-diagnostic"]`.
6. Suppressed blocked-support diagnostics are computed from the suppressed partition unchanged.

No second matching path should be introduced.

## Error Handling

The new diagnostics should not add new user-facing error cases.

`dataset_class` should be sourced from already-normalized benchmark dataset metadata. If an invalid dataset class exists, it should fail through the existing dataset loading/classification path rather than being silently bucketed into an `unknown` class.

`task_support_state` should continue to use the existing parsed support state. Missing support is represented as `none` only in aggregate diagnostics; it should not rewrite the row field.

## Testing

Add focused tests for:

1. `BenchmarkTestRow` includes `dataset_class` (and existing row-shape fixtures/goldens are updated for the additive key).
2. Fallback diagnostics include readiness, dataset class, and task support counts, and each block's values sum to the visible fallback row count.
3. A visible fallback row with `task_support_state == "supported"` is counted under `task_support_counts.supported`, not folded into `none` or dropped.
4. Grouped top benchmark lists are scoped to each readiness/class group and sorted deterministically.
5. Suppressed blocked-support fallback rows are not counted in visible fallback diagnostics.
6. Empty visible fallback buckets still emit stable zero-count diagnostics.
7. CLI table output includes the new aggregate columns without changing the existing suppression table behavior.

## Acceptance Criteria

- `science benchmark test-triage --format json` exposes the new fallback diagnostic fields.
- Existing JSON fields remain present and keep their current semantics.
- `science benchmark tests` includes additive `dataset_class` on each row.
- The table view distinguishes runnable deposit fallbacks from metadata-only reference/pointer fallbacks.
- No benchmark scoring, matching, or suppression behavior changes.

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

The value is already available on `DatasetOpportunityContext.dataset.dataset_class` and should be emitted unchanged as one of:

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
    none: 0
    candidate: 0
    blocked: 0
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

Use `none` for rows where `task_support_state` is missing.

### Table Output

Keep the existing compact fallback diagnostic table, but add summary columns:

- `readiness`
- `class`
- `support`

The table should remain a diagnostic aggregate, not list individual fallback rows. It should make cases like these readable at a glance:

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

1. `BenchmarkTestRow` includes `dataset_class`.
2. Fallback diagnostics include readiness, dataset class, and task support counts.
3. Grouped top benchmark lists are scoped to each readiness/class group and sorted deterministically.
4. Suppressed blocked-support fallback rows are not counted in visible fallback diagnostics.
5. Empty visible fallback buckets still emit stable zero-count diagnostics.
6. CLI table output includes the new aggregate columns without changing the existing suppression table behavior.

## Acceptance Criteria

- `science benchmark test-triage --format json` exposes the new fallback diagnostic fields.
- Existing JSON fields remain present and keep their current semantics.
- `science benchmark tests` includes additive `dataset_class` on each row.
- The table view distinguishes runnable deposit fallbacks from metadata-only reference/pointer fallbacks.
- No benchmark scoring, matching, or suppression behavior changes.

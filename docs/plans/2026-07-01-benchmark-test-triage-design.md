# Benchmark Test Triage Design

## Status

Draft for review.

## Context

`science benchmark tests` now exposes benchmark validation opportunities with
useful labels:

- `test_plan_state`: `concrete` vs. `draft-needed`;
- `priority_source`: `opportunity-relative`, `gap-candidate`, or
  `gap-fallback`;
- `readiness_label`: `runnable`, `stage-needed`, `metadata-only`, or
  `blocked`;
- task fields and `needs` for incomplete benchmark tasks.

This is enough to identify candidate benchmark work, but the table is still a
raw report. It does not create a stable review queue, and it does not preserve
human decisions about which suggested tests should be run, staged, enriched, or
ignored.

The next useful slice is an explicit triage surface over the existing report:
read-only by default, optionally writing a durable review artifact under the
project's canonical documentation tree.

## Goals

- Add a purpose-built benchmark-test triage command that helps choose concrete
  next benchmark work.
- Reuse `benchmark_tests_report()` as the source of truth; do not introduce a
  second matcher, scorer, or readiness model.
- Keep the default command read-only.
- Add an explicit review artifact option for durable project-local triage.
- Preserve deterministic, local-first behavior.
- Make fallback rows visible as diagnostics without letting them dominate the
  human work queue.

## Non-Goals

- No automatic creation of benchmark-test entities.
- No apply mode.
- No changes to benchmark matching or scoring formulas.
- No embeddings or semantic search.
- No commons metadata changes in this slice.
- No attempt to record final benchmark-test execution results.

## Command

Add a new command:

```bash
science benchmark test-triage
```

The command is a projection over `benchmark_tests_report()` and accepts the same
core filters where they naturally apply:

- `--domain`
- `--entity`
- `--facet`
- `--state`
- `--source`
- `--exclude-fallback`
- `--readiness`
- `--runnable-only`
- `--benchmark`
- `--commons`
- `--project-root`
- `--format table|json`

Add review-artifact options:

- `--write-review-file`: write the YAML review artifact.
- `--output <path>`: override the artifact path; valid only with
  `--write-review-file`.

Default behavior is table output only. `--write-review-file` is always explicit
so normal report usage does not create git noise.

When a file is written, print the resolved path to stderr:

```text
wrote benchmark test triage review: doc/audits/benchmark-test-triage/2026-07-01-mm30.yaml
```

## Review Artifact Path

The default review path uses the project's canonical documentation directory via
`resolve_paths(project_root).doc_dir`, matching other Science tooling:

```text
doc/audits/benchmark-test-triage/YYYY-MM-DD-<project>.yaml
```

`<project>` is derived from `science.yaml` `name` when available, otherwise the
project root leaf directory. The path is project-relative in emitted metadata.

If a project uses an unusual convention, `--output` provides an explicit escape
hatch. Relative `--output` paths resolve under the project root. Absolute output
paths are rejected unless an existing command-level path policy already supports
them for comparable review artifacts.

## Triage Buckets

Rows are bucketed after `benchmark_tests_report()` applies its existing filters
and sort order. Within each bucket, preserve the report's row order.

### `run-now`

Rows where:

- `test_plan_state == concrete`;
- `readiness_label == runnable`;
- `priority_source != gap-fallback`.

These are the primary action rows. They have concrete task metadata and enough
readiness to run or directly plan execution.

### `stage-next`

Rows where:

- `readiness_label == stage-needed`;
- `priority_source != gap-fallback`.

These are relevant benchmark tests whose next action is access, staging,
datapackage work, or runtime setup rather than task design.

### `metadata-needed`

Rows where:

- `test_plan_state == draft-needed`;
- `priority_source != gap-fallback`;
- `readiness_label` is not `blocked`.

These rows are relevant but need missing test-plan details such as prediction
target, held-out unit, metric, baseline, or ground truth.

### `blocked-or-reference`

Rows where:

- `readiness_label in {"metadata-only", "blocked"}`;
- `priority_source != gap-fallback`;
- not already classified into a higher bucket.

These rows should remain visible but should not compete with runnable or
stageable rows.

### `fallback-diagnostic`

Rows where:

- `priority_source == gap-fallback`.

Fallback rows are diagnostics and coarse inventory signals. The default table
should summarize them instead of listing every fallback row. JSON and YAML may
include capped examples for review.

## Summary

The triage payload includes a summary object:

```json
{
  "rows_total": 248,
  "bucket_counts": {
    "run-now": 42,
    "stage-next": 61,
    "metadata-needed": 80,
    "blocked-or-reference": 38,
    "fallback-diagnostic": 27
  },
  "source_counts": {
    "opportunity-relative": 122,
    "gap-candidate": 99,
    "gap-fallback": 27
  },
  "readiness_counts": {
    "runnable": 42,
    "stage-needed": 61,
    "metadata-only": 90,
    "blocked": 55
  },
  "top_facets": [
    {"facet": "perturbation", "count": 24}
  ]
}
```

The numbers above are illustrative. They are not expected to reproduce exactly
across projects or future commons metadata.

## Row Shape

Each bucket row is a thin projection of `BenchmarkTestRow`:

```yaml
- entity_id: hypothesis:0005-dynamic-homeostasis
  entity_title: Dynamic homeostasis predicts perturbation recovery
  benchmark_id: dataset:l1000-cmap
  benchmark_title: LINCS L1000 Connectivity Map
  task_id: dataset:l1000-cmap#drug-response-ranking
  test_plan_state: concrete
  readiness_label: runnable
  priority_source: opportunity-relative
  priority_score: 83
  matched_facets: [perturbation]
  needs: []
  reason_notes: [facet-overlap:perturbation, related-belief-id]
  prediction_target: drug-induced expression response
  metric: rank correlation
  review:
    decision: ""
    owner: ""
    next_action: ""
    notes: ""
```

`review` fields are empty placeholders for humans. They are not interpreted by
v1 tooling.

## Table Output

The default table should show a compact queue rather than all rows. Proposed
sections:

1. `run-now`
2. `stage-next`
3. `metadata-needed`
4. `blocked-or-reference`
5. `fallback-diagnostic`

Each non-fallback section shows the top rows, capped per bucket. The default cap
should be small enough to stay readable, such as 10 rows per bucket. JSON output
contains all rows after filters.

The table columns should be practical for triage:

- bucket
- entity
- benchmark
- task
- readiness
- score
- facets
- needs

For `fallback-diagnostic`, show aggregate counts by benchmark and facet rather
than every row. This keeps fallback signal available without presenting it as
immediate work.

## JSON Contract

JSON output contains:

```json
{
  "summary": {},
  "buckets": {
    "run-now": [],
    "stage-next": [],
    "metadata-needed": [],
    "blocked-or-reference": [],
    "fallback-diagnostic": []
  },
  "fallback_diagnostics": {
    "top_benchmarks": [],
    "top_facets": []
  },
  "filters": {},
  "review_file": null,
  "commons_notice": null
}
```

`review_file` is `null` unless `--write-review-file` is used. When present, it
is project-relative if the path is under the project root.

## YAML Review Artifact

The YAML artifact uses the JSON contract with a small header:

```yaml
generated_at: "2026-07-01"
project_root: "."
source_command: "science benchmark test-triage --exclude-fallback --commons"
filters:
  exclude_fallback: true
summary: {}
buckets: {}
fallback_diagnostics: {}
```

The `source_command` is best-effort context, not an exact shell history record.
It should include the command and filters that affect the report where practical.

## Error Handling

- Entity resolution errors reuse the existing `resolve_entity_ref()` behavior
  and are reported as Click errors.
- Unknown facet filters reuse the existing benchmark test facet normalization
  behavior.
- Commons degradation mirrors `science benchmark tests`: print the notice to
  stderr and include `commons_notice` in JSON/YAML.
- `--output` without `--write-review-file` is an error.
- Existing output files are overwritten only when `--write-review-file` is
  explicitly supplied. The command should not silently create artifacts in
  default mode.

## Testing

Add tests for:

- bucket classification for runnable, stage-needed, metadata-needed,
  blocked/reference, and fallback rows;
- preservation of `benchmark_tests_report()` row ordering within buckets;
- JSON shape and summary counts;
- default table caps non-fallback buckets and summarizes fallback diagnostics;
- `--write-review-file` writes under canonical `doc/` and prints the path to
  stderr;
- `--output` requires `--write-review-file`;
- commons notice behavior matches `science benchmark tests`;
- existing `benchmark tests` behavior remains unchanged.

## Calibration Check

After implementation, run the command on active projects:

- `~/d/health/processes/post-acute-infection`
- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

The useful outcome is not a specific row count. The useful outcome is that the
top `run-now` and `stage-next` sections identify a small, plausible work queue
for benchmark execution or staging, while fallback rows remain visible only as
diagnostics.

## Alternatives Considered

### Add `--write-review-file` to `science benchmark tests`

This is the smallest CLI surface, but `benchmark tests` is already the raw
report with many filters. Adding triage buckets and review fields there would
make one command serve two different purposes.

### Add first-class benchmark-test entities immediately

Durable entities are likely useful later, but creating them before reviewing
real triage output risks locking in the wrong fields. A review artifact is a
lower-friction way to learn what decisions and next-action states are actually
needed.

### Build a new scorer for triage

Rejected. The current report already computes priority score, source,
readiness, test-plan state, facets, and needs. Triage should organize those
signals, not introduce another ranking model.

## Self-Review

- No placeholder sections or unresolved TODOs remain.
- The command is read-only by default and writes only behind an explicit flag.
- The design reuses `benchmark_tests_report()` as the source of truth and avoids
  a second matcher or scorer.
- The artifact path follows the canonical `doc/` resolver rather than inventing
  a new docs/doc heuristic.
- The scope stops before authored benchmark-test entities or apply behavior.

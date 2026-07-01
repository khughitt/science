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

`--runnable-only` and `--readiness` compose exactly as in `science benchmark
tests`: replicate its conflict guard so `--runnable-only` together with
`--readiness <label>` (for any label other than `runnable`) fails with
`--runnable-only conflicts with --readiness <label>`.

The YAML review artifact is always written as YAML regardless of `--format`.
`--format` controls only stdout (`table` vs. `json`); it does not change the
artifact.

When a file is written, print the resolved (absolute) path to stderr, matching
the `science benchmark hint-candidates` message form:

```text
wrote benchmark test triage review file: /home/user/project/doc/audits/benchmark-test-triage/2026-07-01-mm30.yaml
```

## Review Artifact Path

The default review path uses the project's canonical documentation directory via
`resolve_paths(project_root).doc_dir`, matching other Science tooling:

```text
doc/audits/benchmark-test-triage/YYYY-MM-DD-<project>.yaml
```

`<project>` is the project root leaf directory, matching
`science benchmark hint-candidates`.

If a project uses an unusual convention, `--output` provides an explicit escape
hatch. The output path policy should match
`_resolve_hint_candidates_output_path()` exactly: relative paths resolve under
the project root; absolute paths are accepted only when they resolve under the
project root; paths that escape the project root are rejected with
`--output must stay under project root`.

The review artifact should store:

- `project: <project_root.name>`;
- `project_root: <display path>`, using the same `_display_project_path()`
  rendering as `benchmark hint-candidates`.

## Triage Buckets

Rows are bucketed after `benchmark_tests_report()` applies its existing filters
and sort order. Bucket assignment is ordered and first-match-wins, using the
sections below in their listed order:

1. `run-now`
2. `stage-next`
3. `metadata-needed`
4. `blocked-or-reference`
5. `fallback-diagnostic`

Within each bucket, preserve the report's row order.

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

If a row is both `draft-needed` and `stage-needed`, it lands in `stage-next`.
The staging/access work is the gating action; task details can be filled in
after the benchmark can be reached or staged.

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

The `fallback_diagnostics.top_benchmarks` and `fallback_diagnostics.top_facets`
aggregates are computed over the fallback rows only. They are distinct from the
summary's `top_facets`, which is inherited from `benchmark_tests_report()` and
spans all rows; do not reuse the summary computation here.

Because `fallback-diagnostic` is evaluated last, a fallback row is never placed
in `run-now`, `stage-next`, `metadata-needed`, or `blocked-or-reference` even if
its readiness or task fields would otherwise satisfy those predicates.

## Summary

The triage payload includes a summary object built on top of
`benchmark_tests_report()["summary"]`. Preserve the existing report summary
fields, including `entities_total`, `test_plan_rows`, `concrete_rows`,
`draft_needed_rows`, `entities_with_test_plans`, `entities_without_test_plans`,
`source_counts`, `fallback_rows`, `fallback_row_ratio`, and `top_facets`.

Then add the two triage-specific aggregate fields, `bucket_counts` and
`readiness_counts`. `bucket_counts` partitions rows across the five buckets, so
its `fallback-diagnostic` entry is the only place fallback rows are counted.
`readiness_counts` is a raw histogram over **all** rows (including fallback
rows), so it intentionally counts a different population than the non-fallback
buckets; the two are not expected to line up.

The merged summary therefore looks like:

```json
{
  "test_plan_rows": 248,
  "concrete_rows": 122,
  "draft_needed_rows": 126,
  "source_counts": {
    "opportunity-relative": 122,
    "gap-candidate": 99,
    "gap-fallback": 27
  },
  "fallback_rows": 27,
  "fallback_row_ratio": 0.109,
  "bucket_counts": {
    "run-now": 42,
    "stage-next": 61,
    "metadata-needed": 80,
    "blocked-or-reference": 38,
    "fallback-diagnostic": 27
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

`task_id` is nullable. Rows projected from a facets-only or taskless benchmark
should render `task_id: null` in JSON/YAML and `-` in table output.

## Table Output

The default table should show a compact queue rather than all rows. Proposed
sections:

1. `run-now`
2. `stage-next`
3. `metadata-needed`
4. `blocked-or-reference`
5. `fallback-diagnostic`

Each non-fallback section shows the top rows, capped per bucket. Because buckets
preserve `benchmark_tests_report()` order and that report sorts by descending
`priority_score` once state/source/readiness are fixed, the capped rows are the
highest-priority rows in the bucket. The default cap should be small enough to
stay readable, such as 10 rows per bucket. JSON output contains all rows after
filters.

Because rows are grouped under per-bucket section headers, the bucket is already
implied by the section and is not repeated as a column. The table columns should
be practical for triage:

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

`filters` records the effective non-default filter values that shaped the report
(for example `{"exclude_fallback": true, "readiness": "runnable"}`). It is
best-effort context, like `source_command`, not a full option dump.

`review_file` is `null` unless `--write-review-file` is used. When present, it
is the resolved (absolute) path of the written artifact, matching the
`review_file` value emitted by `science benchmark hint-candidates`. (The path is
always under the project root, since escapes are rejected.)

## YAML Review Artifact

The YAML artifact uses the JSON contract with a small header:

```yaml
generated_at: "2026-07-01"
project: multiple-myeloma
project_root: "~/d/cancer/cancer-types/multiple-myeloma"
review_file: "/home/user/d/cancer/cancer-types/multiple-myeloma/doc/audits/benchmark-test-triage/2026-07-01-multiple-myeloma.yaml"
source_command: "science benchmark test-triage --exclude-fallback --commons"
filters:
  exclude_fallback: true
summary: {}
buckets: {}
fallback_diagnostics: {}
commons_notice: null
```

`project_root` is the `~`-style display path (as in `benchmark
hint-candidates`), while `review_file` is the resolved absolute path of the
artifact itself.

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
- Existing output files are never overwritten. Match
  `_write_hint_candidates_review_file()`: if the review path already exists,
  fail with `review file already exists: <path>`. This avoids discarding human
  review decisions in a same-day rerun.
- The command should not create artifacts in default mode.

## Testing

Add tests for:

- bucket classification for runnable, stage-needed, metadata-needed,
  blocked/reference, and fallback rows;
- bucket precedence for the reachable `draft-needed` + `stage-needed`
  combination, which must land in `stage-next`;
- preservation of `benchmark_tests_report()` row ordering within buckets;
- JSON shape and summary counts;
- default table caps non-fallback buckets and summarizes fallback diagnostics;
- `--write-review-file` writes under canonical `doc/` and prints the path to
  stderr;
- existing review files are refused rather than overwritten;
- absolute `--output` paths are accepted only under the project root;
- `--output` requires `--write-review-file`;
- `--runnable-only` combined with a non-`runnable` `--readiness` is rejected,
  matching `science benchmark tests`;
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

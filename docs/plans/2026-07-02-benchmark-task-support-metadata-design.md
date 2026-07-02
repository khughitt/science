# Benchmark Task Support Metadata v1

## Status

Draft for review.

## Context

`science benchmark tests` currently treats a benchmark task as concrete when the
task metadata has a prediction target, held-out unit, metric, baseline, and
ground-truth description. That is necessary but not sufficient. A task can be
well described and still not be usable as stated.

The MMRF CoMMpass commons record exposes the problem. Its benchmark entity
contains a concrete `progression-risk` task, so benchmark reports surface rows
such as `dataset:mmrf-commpass#progression-risk` as concrete metadata-only test
plans. The staging recipe diagnostics are more precise: open GDC metadata is
currently `survival-only`, `progression-risk` is blocked because progression or
relapse endpoints are unavailable or incomplete, and `overall-survival` is a
distinct buildable candidate task rather than a fallback ground truth.

The benchmark report should not depend on local generated recipe artifacts such
as `~/d/science-commons-data/mmrf-commpass/reports/validation.json`. Reports
need stable behavior from durable benchmark entity metadata, with recipe
artifacts cited as evidence when useful.

## Goals

- Add durable task-local support metadata to benchmark tasks.
- Let benchmark reports surface why a task is supported, candidate-only, or
  blocked.
- Keep the report additive for JSON consumers.
- Keep recipe validation artifacts as cited evidence, not runtime inputs to
  benchmark report generation.
- Make MMRF `progression-risk` visibly blocked instead of an apparently clean
  concrete metadata-only test plan.

## Non-Goals

- Do not promote MMRF to `deposit` or `runnable`.
- Do not read local recipe validation output from `science benchmark tests`.
- Do not infer task support from prose limitations.
- Do not add embeddings, semantic matching, or external lookups.
- Do not make `overall-survival` a fallback ground truth for `progression-risk`.

## Data Model

Add an optional `support` block to `BenchmarkTask`.

```yaml
support:
  state: blocked
  reason: open-metadata-missing-progression-endpoint
  checked_at: "2026-07-02"
  evidence:
    - "recipe/manifest.schema.yaml#task_support"
    - "recipe/reports/validation.json#task_support.progression-risk"
  notes:
    - "Open GDC metadata currently exposes survival endpoints but not progression/relapse endpoints."
```

Fields:

- `state`: one of `supported`, `candidate`, `blocked`.
- `reason`: lowercase kebab-case reason code. Required when `state` is
  `candidate` or `blocked`; optional for `supported`.
- `checked_at`: `YYYY-MM-DD` date for the support assessment.
- `evidence`: relative paths or path fragments that identify the diagnostic
  source. These are citations only; reports do not read them.
- `notes`: short human-readable details.

State semantics:

- `supported`: the task is usable as described, subject to normal dataset
  access and runtime readiness.
- `candidate`: the task appears buildable or plausible, but should not be
  treated as a concrete run-now test until an explicit review promotes it.
- `blocked`: the task should not be presented as actionable until the stated
  blocker changes.

Missing `support` means no explicit task-support assessment is available and
preserves current behavior.

Validation ownership:

- The Pydantic model and JSON schema own structure: state enum, reason-code
  shape, required-when-`candidate`/`blocked`, and `checked_at` date format.
- The benchmark report loader also validates `support` when reading raw
  frontmatter. `science benchmark tests` currently uses
  `_dataset_from_source` -> `_tasks` -> `_task_from_mapping`, not Pydantic
  entity instances, so invalid support metadata must fail loudly on the report
  path. Unknown states must not degrade to "missing support".
- The `benchmark_metadata` validation check owns additional project-facing
  diagnostics and any cross-field warnings that are clearer as validation
  messages than as model errors.

`checked_at` is advisory provenance for the assessment. V1 does not apply a
freshness or staleness policy.

## Report Contract

Extend `BenchmarkTestRow` with additive fields:

- `task_support_state`: `supported | candidate | blocked | ""`
- `task_support_reason`: string
- `task_support_checked_at`: string
- `task_support_evidence`: list of strings
- `task_support_notes`: list of strings

The table output should keep its current columns initially, but `reason_notes`
should include concise support notes:

- `task-support:blocked:<reason>`
- `task-support:candidate:<reason>`

JSON consumers get the structured fields directly.

## Readiness and Triage Rules

Task support is an axis separate from dataset access/runtime readiness.
`readiness_label` should remain the dataset-access verdict produced from
`runtime_state_for` and `readiness_for`. Do not overwrite it to represent task
support; use the structured task-support fields and `reason_notes` for that.

Triage combines the axes with explicit support-state branches. The implementation
seam is `_benchmark_test_triage_bucket`, not `_readiness_label`.

Rules:

1. If `priority_source == "gap-fallback"`, keep the row in
   `fallback-diagnostic`. Fallback rows are diagnostic clutter by definition;
   task support should still be visible in row fields, but it should not promote
   a fallback into an action bucket.
2. If `task.support.state == "blocked"`, route the row to
   `blocked-or-reference` and include the support reason in `reason_notes`.
3. If `task.support.state == "candidate"`, do not allow the row into
   `run-now`. If `readiness_label == "stage-needed"`, route it to
   `stage-next`; if `readiness_label == "runnable"`, route it to
   `metadata-needed`; otherwise route it to `blocked-or-reference`.
4. If `task.support.state == "supported"` or support is missing, preserve the
   current readiness and triage behavior.

This keeps blocked tasks visible for review while preventing them from being
misread as actionable test plans.

## MMRF Application

For `dataset:mmrf-commpass`:

- `progression-risk` should carry `support.state: blocked` with reason
  `open-metadata-missing-progression-endpoint` or a more precise
  `open-metadata-incomplete-progression-outcome-coverage` if the dry-run
  diagnostics show partial but incomplete progression endpoint coverage.
- `overall-survival` may be added as a separate task with
  `support.state: candidate` only if the entity explicitly describes it as a
  distinct task. It must not replace or silently satisfy `progression-risk`.
- The dataset remains `dataset_class: pointer` until a separate promotion
  review verifies a staged package and access/redistribution terms.

Expected report behavior after the metadata update:

- `science benchmark tests --commons --benchmark mmrf-commpass` still shows
  MMRF rows. `progression-risk` rows retain their dataset-level
  `readiness_label` but include `task_support_state: blocked` and a support
  reason note.
- `science benchmark test-triage --commons --benchmark mmrf-commpass` places
  non-fallback `progression-risk` rows in `blocked-or-reference`. This is not a
  large bucket movement for today's pointer-class MMRF record, because it
  already lands there as `metadata-only`; the visible delta is the durable
  reason for the blocker and future-proof behavior if the dataset is later
  promoted.
- Candidate `overall-survival` rows, if present, are visible as candidate task
  plans and cannot enter `run-now`.

## Implementation Touchpoints

- `science/model/src/science_model/packages/schema.py`
  - Add a strict `BenchmarkTaskSupport` model.
  - Add optional `support: BenchmarkTaskSupport | None` to `BenchmarkTask`.
- `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
  - Add the JSON schema for `benchmark_task.support`.
- `science/src/science_tool/benchmark_opportunities.py`
  - Extend `OpportunityTask` and `_task_from_mapping`.
  - Extend `BenchmarkTestRow`.
  - Validate task support while parsing raw frontmatter; invalid support should
    raise instead of silently behaving like missing support.
  - Add support-state branches in triage without changing dataset readiness
    semantics.
- `science/src/science_tool/validate/checks/benchmark_metadata.py`
  - Add focused validation for reason codes and support-state consistency if
    schema validation does not already cover a case.
- `~/d/science-commons/datasets/mmrf-commpass/entity.md`
  - Add durable task support metadata for MMRF task status.

## Testing

Add tests that cover:

- Model and JSON schema accept valid `support` and reject unknown states.
- The report parser rejects invalid raw-frontmatter support state rather than
  silently treating it as missing support.
- Benchmark metadata validation rejects malformed support reason codes.
- `benchmark_tests_report` projects support fields into rows.
- `blocked` support routes non-fallback rows to `blocked-or-reference` while
  preserving the dataset-level `readiness_label`.
- `candidate` support remains visible and does not enter the `run-now` triage
  bucket, including the concrete-task case where `metadata-needed` would not be
  reached by the existing draft-needed predicate.
- MMRF-style `progression-risk` rows carry a blocked support reason rather than
  appearing as clean metadata-only actionability.

## Alternatives Considered

### Prose-only limitations

The task could describe its blocker in `interpretation_limits` or
`benchmark.limitations`. This avoids schema work but is not machine-actionable.
It would leave benchmark reports showing the same misleading concrete rows
unless the code parsed prose, which would be brittle.

### Recipe artifact loading

`science benchmark tests` could read local files such as
`reports/validation.json`. That would make reports dependent on local generated
state and fail for consumers that have the commons metadata but not the staged
data directory. Durable entity metadata is the better report source of truth.

### Dataset-level support state

The blocker could live at `benchmark.support` rather than on individual tasks.
This does not fit MMRF: `progression-risk` is blocked while `overall-survival`
may be a candidate over the same source dataset. Support is task-local.

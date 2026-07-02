# MMRF Task Variants And Cohort Aggregation Design

Date: 2026-07-02

## Goal

Define how `dataset:mmrf-commpass` should represent benchmark task support when
the source data supports a nearby validation task, but not the originally named
task.

The first MMRF staging recipe proved two facts that should shape the next
benchmark slice:

- GDC open clinical metadata currently exposes overall-survival fields for
  MMRF CoMMpass, but not progression/relapse fields needed for the existing
  `progression-risk` task.
- The open expression manifest contains multiple files for some
  `case_submitter_id` values, so a patient-level benchmark package needs an
  explicit cohort aggregation policy before it can be promoted.

This design keeps `progression-risk` honest, introduces an explicit path for an
`overall-survival` task candidate, and defines the aggregation contract required
before any MMRF task becomes runnable.

## Non-Goals

- Do not promote `dataset:mmrf-commpass` from `pointer` to `deposit` in this
  slice.
- Do not treat overall survival as a fallback ground truth for
  `progression-risk`.
- Do not silently deduplicate multiple expression files per patient.
- Do not stage controlled-access MMRF files.
- Do not add a new benchmark command unless existing `benchmark tests` and
  `benchmark test-triage` cannot represent the distinction.

## Decision

Use explicit task variants under the same dataset record.

`progression-risk` remains the task for progression or relapse prediction. It
is blocked for GDC-open staging until progression/relapse endpoint fields are
available from an open source or a controlled-access staging path is designed.

Add or prepare a distinct `overall-survival` task only if it is labeled as a
separate benchmark task:

```yaml
id: overall-survival
task_type: outcome-prediction
prediction_target: overall survival from baseline molecular and clinical features
held_out_unit: patient
metric: concordance-index
baseline: clinical covariates
ground_truth:
  type: measured-outcome
  description: vital_status with days_to_death or days_to_last_follow_up censoring
```

The recipe must report support per task, not per dataset:

```yaml
task_support:
  progression-risk:
    state: blocked-missing-endpoint
    endpoint_status: survival-only
    reason: GDC open clinical metadata lacks progression_or_recurrence / days_to_recurrence fields.
  overall-survival:
    state: buildable-candidate
    endpoint_status: survival-fields-present
    reason: GDC demographic vital_status and days_to_death fields are present.
```

This avoids the most important false positive: a dataset can be buildable for
one benchmark task while still blocked for another.

## Cohort Aggregation Contract

The next recipe iteration must stop treating duplicate `case_submitter_id`
values as either a generic error or something to collapse implicitly. It should
classify the manifest into one of three explicit modes.

### `patient-level-single-sample`

Exactly one selected expression sample/file per patient after applying a
declared selection rule. This is the preferred mode for patient-level survival
or progression benchmarks.

The selection rule must be recorded in the validation report and datapackage
metadata before promotion. Candidate rule:

1. Restrict to bone marrow tumor / CD138-positive samples where the GDC sample
   metadata exposes that distinction.
2. Prefer baseline / earliest disease-course sample where timepoint metadata is
   available.
3. If multiple candidate files remain for a patient, fail with
   `ambiguous-patient-expression-files` rather than choosing first by sort
   order.

### `sample-level-with-patient-outcomes`

Multiple expression samples per patient are retained, and outcomes remain
patient-level. This is allowed as an intermediate staged resource, but a
patient-level benchmark task stays `draft-needed` until the evaluation protocol
states how correlated samples from one patient are handled.

Required safeguards:

- held-out split unit remains patient;
- no samples from the same patient cross train/validation/test boundaries;
- the resource schema identifies both `sample_submitter_id` and
  `case_submitter_id`;
- benchmark task notes disclose that multiple samples can share one outcome.

### `unresolved-cohort`

The manifest has duplicate or ambiguous patient/sample mappings and the recipe
cannot classify them under a declared policy. In this state, the recipe may
write the manifest and diagnostics but must not build a runnable benchmark
package.

## Benchmark Metadata Representation

The commons entity should eventually carry both tasks only when the
overall-survival task has passed review as a true benchmark target. Until then,
the recipe can report the task candidate in validation output without modifying
`entity.md`.

When added, `progression-risk` and `overall-survival` are sibling tasks. They
must not share a task id, and each task must carry its own ground-truth
description and interpretation limits.

Suggested task-specific limits:

- `progression-risk`: blocked for GDC-open staging unless progression or relapse
  endpoints are available.
- `overall-survival`: open clinical survival labels are useful but less
  specific to disease progression; interpretation should avoid claiming
  progression-free survival, treatment response, or causal treatment effects.

## Recipe Output Contract

The recipe validation report should add task-aware fields:

```yaml
endpoint_status: survival-only
cohort_mode: unresolved-cohort
task_support:
  progression-risk:
    state: blocked-missing-endpoint
    required_fields_missing:
      - progression_or_recurrence
      - days_to_recurrence
  overall-survival:
    state: buildable-candidate
    required_fields_present:
      - vital_status
      - days_to_death
      - days_to_last_follow_up
cohort_aggregation:
  duplicate_case_submitter_id_count: 208
  selected_policy: null
  blocking_reason: ambiguous-patient-expression-files
```

If a future implementation selects a valid aggregation policy, the report should
change `cohort_mode` to `patient-level-single-sample` or
`sample-level-with-patient-outcomes` and record the exact policy.

## Benchmark Command Behavior

No command behavior change is required for the first implementation if the
dataset entity remains unchanged.

After an `overall-survival` task is added to the commons entity:

- `science benchmark tests` should show a row for
  `dataset:mmrf-commpass#overall-survival` separately from
  `dataset:mmrf-commpass#progression-risk`.
- `progression-risk` should remain `metadata-only` / non-runnable until a
  progression endpoint package exists.
- `overall-survival` may become `stage-needed` or `runnable` only after a
  datapackage exists or a recipe-derived artifact is declared.
- `science benchmark test-triage` should place the runnable/stageable task in
  the appropriate bucket without implying that all MMRF benchmark tasks are
  unblocked.

If current reporting cannot make that distinction clearly, the fix should be in
row labeling or task-level filtering, not in dataset-level readiness semantics.

## Alternatives Considered

### Promote overall survival as a fallback for `progression-risk`

Rejected. This would make a row look runnable while changing the meaning of the
task. Overall survival and progression-free survival can use similar survival
metrics, but they test different claims.

### Keep only `progression-risk` and ignore overall survival

Rejected. GDC-open survival labels are still a useful benchmark signal for
multiple myeloma projects, especially when paired with expression data. Ignoring
them would throw away a buildable validation opportunity.

### Solve aggregation only

Rejected as incomplete. Aggregation is necessary, but without task variants the
recipe still cannot explain why it discovered a useful survival endpoint while
refusing to promote `progression-risk`.

## Validation Gates

Before adding `overall-survival` to the commons entity:

- dry-run validation proves survival fields are present in the GDC open cases
  response;
- the task definition is reviewed as a distinct benchmark, not a fallback;
- cohort aggregation mode is known, even if it remains `unresolved-cohort`;
- `dataset:mmrf-commpass` remains `pointer`.

Before promoting any MMRF task to runnable:

- a datapackage exists and validates;
- expression resources join to outcomes under the declared aggregation policy;
- train/validation/test splits are patient-disjoint;
- duplicate or ambiguous patient mappings are either resolved by policy or fail
  loudly;
- the datapackage records which task ids it supports.

## Testing Strategy

Implementation should add tests proving:

- OS-only GDC fixture produces `overall-survival: buildable-candidate` and
  `progression-risk: blocked-missing-endpoint`;
- OS-only fields never mark `progression-risk` promotable;
- duplicate patient expression files produce an explicit cohort-mode result;
- patient-level selection refuses ambiguous ties;
- sample-level resources keep patient-disjoint splits;
- benchmark report rows preserve task identity when a dataset has both blocked
  and buildable tasks.

## Success Criteria

The next implementation slice succeeds if it makes MMRF's current state
machine-readable:

- `progression-risk` is visibly blocked by missing open progression endpoints;
- `overall-survival` is visible as a distinct candidate task;
- duplicate case/sample mappings are explained by a cohort mode and policy
  status;
- no dataset-level promotion occurs until a specific task and aggregation
  policy are validated.


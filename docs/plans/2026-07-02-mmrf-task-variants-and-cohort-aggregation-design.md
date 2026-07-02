# MMRF Task Variants And Cohort Aggregation Design

Date: 2026-07-02

## Goal

Define how the existing `dataset:mmrf-commpass` recipe and commons entity
should represent benchmark task support when the source data supports a nearby
validation task, but not the originally named task.

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

This is an amendment to existing work, not a greenfield recipe design. The
commons repo already has:

- `~/d/science-commons/datasets/mmrf-commpass/entity.md`, with
  `dataset_class: pointer` and one `progression-risk` benchmark task;
- `~/d/science-commons/datasets/mmrf-commpass/recipe/`, with
  `fetch_manifest.py`, `build.py`, `build_datapackage.py`, fixtures, and tests;
- a validation report contract that already emits dataset-level
  `endpoint_status`, `buildable_manifest`, and `promotable`.

Implementation should migrate those existing surfaces rather than introduce a
parallel recipe or entity model.

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

The benchmark tooling already supports this shape. `OpportunityDataset` carries
`tasks: list[OpportunityTask]`, and `science benchmark tests` renders each task
as `dataset:<slug>#<task-id>`. Adding `overall-survival` as a sibling task
should require no schema change in the benchmark command layer.

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

The recipe must keep endpoint discovery dataset-level and report support per
task as a derived diagnostic. Endpoint fields present in a GDC manifest are a
property of the data, so `endpoint_status` remains single-valued with the
existing recipe vocabulary:

- `progression-ready`
- `survival-only`
- `missing-endpoint`

Task support is then derived from `endpoint_status`, the task's required
fields, and cohort aggregation state:

```yaml
endpoint_status: survival-only
task_support:
  progression-risk:
    state: blocked-missing-endpoint
    reason: GDC open clinical metadata lacks progression_or_recurrence / days_to_recurrence fields.
  overall-survival:
    state: buildable-candidate
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

The dry run must probe whether the required sample-selection fields are present
in the open GDC response before committing to this mode. The first recipe only
proved that `sample_type` and submitter ids were available for the selected
files. A future selection policy that depends on CD138 status, baseline status,
collection time, treatment line, or disease-course labels must report those
field probes explicitly. If the needed fields are absent, this mode is
unreachable for GDC-open staging and the recipe should report either
`sample-level-with-patient-outcomes` or `unresolved-cohort`.

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

The task id remains local to the dataset. The benchmark command layer derives
the canonical row id as `dataset:mmrf-commpass#overall-survival`; no shared task
registry is required for this slice.

Current benchmark reporting parses task identity, target, held-out unit, metric,
baseline, and ground truth, but it does not parse or display per-task
`interpretation_limits`. Those limits are documentation-only until
`OpportunityTask` and the benchmark row contract are extended. If
implementation needs those limits in `science benchmark tests`, that parser
change should be an explicit task.

Suggested task-specific limits:

- `progression-risk`: blocked for GDC-open staging unless progression or relapse
  endpoints are available.
- `overall-survival`: open clinical survival labels are useful but less
  specific to disease progression; interpretation should avoid claiming
  progression-free survival, treatment response, or causal treatment effects.

## Recipe Output Contract

For an ambiguous manifest, the recipe validation report should add task-aware
fields with this shape:

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
  duplicate_case_submitter_id_count: 1
  duplicate_case_submitter_id_values: ["MMRF_0001"]
  affected_case_submitter_id_count: 1
  selected_policy: null
  blocking_reason: ambiguous-patient-expression-files
```

If a future implementation selects a valid aggregation policy, the report should
change `cohort_mode` to `patient-level-single-sample` or
`sample-level-with-patient-outcomes` and record the exact policy.

Counts in `cohort_aggregation` are runtime measurements from the current
manifest. The design does not bake in the duplicate counts observed in one dry
run because they can change with GDC release, query filters, or sample-selection
policy.

The existing `buildable_manifest` and `promotable` fields should remain during
the migration:

- `buildable_manifest` stays false whenever `cohort_mode` is
  `unresolved-cohort`.
- `promotable` remains false unless a specific task is endpoint-supported and
  the cohort mode is compatible with that task's evaluation protocol.
- duplicate manifest values should become diagnostics written to the validation
  report before the command exits. They should not be silently accepted, and
  they should not disappear behind a generic hard failure that hides task
  support diagnostics.

This changes today's duplicate handling from "write a validation report and
raise only `Manifest is not buildable`" to "write a validation report with
cohort mode, task support, duplicate counts, and then raise a precise
non-promotable reason when the caller requested a promotable progression
package."

## State Crosswalk

The recipe-layer task-support states are diagnostics. They feed benchmark
readiness, but they do not replace the existing command vocabularies.

| Recipe state | Meaning | Expected benchmark surface before datapackage promotion |
| --- | --- | --- |
| `blocked-missing-endpoint` | Required endpoint fields are absent for this task. | Existing task remains `readiness_label: metadata-only`; `test-triage` keeps it in `blocked-or-reference` while the dataset is a pointer. |
| `buildable-candidate` | Endpoint fields exist, but cohort policy or datapackage promotion is not complete. | Candidate task may be documented, but should not become `runnable`; if added to entity before datapackage promotion it should still report `metadata-only` while the dataset remains a pointer. |
| `buildable-with-policy` | Endpoint fields and cohort aggregation policy are defined, but runtime artifacts are recipe-derived or unstaged. | After entity/datapackage update, expected bucket is `stage-next` unless local runtime artifacts exist. |
| `runnable` | Datapackage exists, validates, and supports this task id. | `science benchmark tests` may report `readiness_label: runnable`; `test-triage` may place rows in `run-now`. |

The recipe's dataset-level `endpoint_status` is still the single source of truth
for endpoint discovery. The task-support state is a projection over that status
and task requirements.

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
- the recipe records `case_submitter_id` and `sample_submitter_id` for every
  expression row so downstream splitting can enforce patient-level separation;
- if the recipe writes splits, train/validation/test splits are
  patient-disjoint;
- duplicate or ambiguous patient mappings are either resolved by policy or fail
  loudly;
- the datapackage records which task ids it supports.

## Testing Strategy

Implementation should add tests proving:

- OS-only GDC fixture produces `overall-survival: buildable-candidate` and
  `progression-risk: blocked-missing-endpoint`;
- OS-only fields never mark `progression-risk` promotable;
- duplicate patient expression files produce an explicit cohort-mode result;
- dry-run field probes report whether sample-selection fields needed by a
  patient-level policy are present;
- patient-level selection refuses ambiguous ties;
- sample-level resources preserve patient identifiers needed for patient-level
  splitting;
- any recipe-written splits are patient-disjoint;
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

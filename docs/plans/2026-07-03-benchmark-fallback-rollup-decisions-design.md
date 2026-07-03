# Benchmark Fallback Rollup Decisions Design

## Status

Proposed.

## Context

`science benchmark test-triage` now groups fallback diagnostics into rollups.
Across the active calibration projects, the visible fallback rows collapse to
the same three benchmark/task records:

- `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association`
- `dataset:cptac-proteogenomics#protein-rna-cross-modal`
- `dataset:dream4-in-silico-network#network-reconstruction`

The blocked MMRF progression task is already suppressed from the default
fallback table through task-support metadata:

- `dataset:mmrf-commpass#progression-risk`

The remaining issue is not table presentation. The report is now clear enough
to show that repeated fallback rows need explicit human decisions: which rows
represent useful broad fallback benchmarks, which need staging work, which
should remain reference/pointer metadata, and which are poor fits for the
projects where they appear.

## Goals

- Calibrate the dominant fallback rollups across active projects.
- Record conservative, reviewable decisions for each recurring benchmark/task.
- Apply only high-confidence metadata changes to `~/d/science-commons`.
- Avoid changing benchmark matching, scoring, sorting, or fallback selection.
- Use the current rollup output to decide whether the next slice should be
  metadata, staging, or review-tooling work.

## Non-Goals

- Do not build a new review command in this slice.
- Do not stage large benchmark datasets.
- Do not convert reference or pointer records into deposits unless they are
  demonstrably stageable.
- Do not suppress fallback rows merely because they are common.
- Do not bulk-edit benchmark metadata outside the recurring rollup records.

## Decision

Treat this as a calibration and metadata-cleanup slice.

For each dominant fallback rollup, assign one decision label:

- `keep-supported-fallback`: the benchmark is a useful broad fallback and its
  current metadata is accurate.
- `needs-staging-recipe`: the benchmark is useful, but needs a concrete
  datapackage or recipe before it should be treated as actionable.
- `valid-reference-only`: the record should stay as reference/pointer metadata;
  fallback visibility is diagnostic, not a staging prompt.
- `poor-fit-suppress-later`: the benchmark is repeatedly suggested but not
  useful for the sampled project context; do not suppress in this slice, but
  record the reason for a future suppression design.
- `needs-task-support`: the task support metadata is missing or too vague to
  explain its actionability.

The expected initial classification is:

| Benchmark task | Current state | Likely decision |
| --- | --- | --- |
| `ccle-proteomics-nusinow-2020#protein-lineage-association` | `supported`, runnable deposit | `keep-supported-fallback` unless real-project examples show it is too generic |
| `cptac-proteogenomics#protein-rna-cross-modal` | `candidate`, metadata-only reference | `needs-staging-recipe` or `valid-reference-only`, depending on whether a concrete CPTAC package can be named |
| `dream4-in-silico-network#network-reconstruction` | `candidate`, metadata-only pointer | `valid-reference-only` unless the exact DREAM4 package and access path are ready to stage |
| `mmrf-commpass#progression-risk` | `blocked`, suppressed fallback | `keep-blocked-support`; no visible fallback action expected |

## Calibration Procedure

Run `science benchmark test-triage` against the active projects with commons
enabled:

```bash
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json
science benchmark test-triage --project-root ~/d/health/processes/post-acute-infection --commons --source gap-fallback --format json
science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json
science benchmark test-triage --project-root ~/d/cancer/data-sources/cbioportal --commons --source gap-fallback --format json
```

For each rollup, inspect:

- `count`: whether the pattern is broad and repeated.
- `task_support_state` and `task_support_reason`: whether metadata already
  explains actionability.
- `readiness_label` and `dataset_class`: whether the issue is staging,
  reference-only metadata, or task support.
- `top_facets`: whether the benchmark is being suggested for a coherent
  modality/signal reason.
- `example_entities`: whether the benchmark is plausibly relevant to actual
  project beliefs, not just generic vocabulary.

The first pass should produce a short decision table, not code. If a decision
requires source checking, record the source and whether it supports staging.

## Metadata Changes

Only make commons metadata changes when the calibration exposes a specific,
high-confidence gap.

Examples of acceptable changes:

- Tighten `tasks[].support.notes` to explain why a supported fallback remains
  broad rather than project-specific.
- Change `support.state` from `candidate` to `blocked` only when a task is not
  currently buildable for a concrete, durable reason.
- Add a more precise `support.reason` when `candidate` is correct but too vague.
- Add or refine `benchmark.limitations` to prevent over-reading a fallback row.

Examples of changes to avoid in this slice:

- Adding a datapackage without actually staging or validating it.
- Marking a portal/reference record as a deposit to improve report ranking.
- Suppressing broad fallback rows without a separate suppression policy.
- Editing project entities to make a benchmark look better or worse.

## Expected Outcomes

This slice may result in no code changes. A successful pass can be:

- A committed design/decision note documenting why the current metadata is
  correct.
- A small set of commons metadata commits with clear validation.
- A follow-up implementation plan for one staging recipe if a high-value
  benchmark is ready to promote.
- A follow-up design for review tooling if manual decisions are repetitive.

## Validation

Before and after any commons metadata edits, run:

```bash
science commons validate
science commons index rebuild
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback
science benchmark test-triage --project-root ~/d/health/processes/post-acute-infection --commons --source gap-fallback
science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback
science benchmark test-triage --project-root ~/d/cancer/data-sources/cbioportal --commons --source gap-fallback
```

The expected report behavior depends on the decision:

- `keep-supported-fallback`: row remains visible with accurate support metadata.
- `needs-staging-recipe`: row remains visible as candidate; reason becomes more
  specific if needed.
- `valid-reference-only`: row remains visible as metadata-only unless a future
  suppression policy is designed.
- `poor-fit-suppress-later`: no behavior change in this slice; record evidence.
- `needs-task-support`: task-support counts should improve after metadata edits.

## Alternatives Considered

### Build Review Tooling First

Rejected for this slice. The current rollup table already narrows the problem to
three visible records plus suppressed MMRF rows. A new command is premature until
we see repeated decisions that cannot be handled with a small metadata pass.

### Promote One Benchmark Immediately

Rejected as the default path. Promotion requires source/access audit and staging
work. If calibration shows that CPTAC or DREAM4 has a ready, durable package, it
should become its own staging slice.

### Suppress Candidate Fallback Rows By Default

Rejected. Candidate fallback rows are diagnostic: they show high-value benchmark
directions that are not yet runnable. Suppression should be a separate,
evidence-backed policy, not a response to high row counts.

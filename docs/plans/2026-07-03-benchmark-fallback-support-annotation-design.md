# Benchmark Fallback Support Annotation Design

## Status

Proposed.

## Context

`science benchmark test-triage` now reports visible fallback diagnostics by
readiness, dataset class, and task-support state. A calibration pass over active
projects showed that the remaining visible fallback rows are not mainly blocked
tasks. They are mostly broad fallback benchmark tasks with no explicit
`tasks[].support` metadata.

The highest-count visible fallback benchmarks were:

- `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association`
- `dataset:cptac-proteogenomics#protein-rna-cross-modal`
- `dataset:dream4-in-silico-network#network-reconstruction`

Those rows are useful only if the report can distinguish runnable, supported
fallbacks from plausible but not-yet-stageable benchmark candidates. The right
place for that distinction is task-local benchmark metadata in
`~/d/science-commons`, not another presentation rule in `science`.

## Goals

- Add task-local support metadata to the three top visible fallback benchmark
  tasks.
- Reduce `fallback_diagnostics.task_support_counts.none` across active project
  calibration runs.
- Preserve current benchmark matching, scoring, fallback selection, and
  suppression behavior.
- Keep support labels evidence-backed and conservative.

## Non-Goals

- Do not change `science benchmark tests`, `science benchmark test-triage`, or
  benchmark matching logic.
- Do not stage new datasets or convert reference/pointer records into deposits.
- Do not bulk annotate every commons benchmark task.
- Do not infer support automatically from `dataset_class`; support is a
  task-local judgment.

## Decision

Annotate only the top three fallback benchmark tasks in
`~/d/science-commons/datasets/*/entity.md`.

### CCLE Proteomics

Task:
`dataset:ccle-proteomics-nusinow-2020#protein-lineage-association`

Decision: `support.state: supported`

Rationale:

- The record is already a deposit with `datapackage: datapackage.yaml`,
  verified public access, and a concrete protein-abundance task.
- It is useful as a broad protein-level fallback benchmark for cancer
  cell-line settings.
- Its limitations are known and already documented: cell-line context,
  limited multiple-myeloma subset size, and TMT/batch constraints.

Suggested support block:

```yaml
support:
  state: supported
  checked_at: "2026-07-03"
  evidence:
    - datapackage.yaml
    - datapackage.yaml#resources
  notes:
    - Runnable deposit benchmark for protein-level association checks across CCLE cancer cell lines.
    - Use as broad cell-line proteomics validation, not as a primary-tumor or causal benchmark.
```

### CPTAC Proteogenomics

Task:
`dataset:cptac-proteogenomics#protein-rna-cross-modal`

Decision: `support.state: candidate`

Reason: `requires-study-specific-staging`

Rationale:

- The task is benchmark-relevant for cross-modal protein/RNA validation.
- The record is currently `dataset_class: reference`, so the commons metadata
  points to a portal rather than a stageable datapackage.
- Study selection, access terms, and package layout need to be resolved before
  the task should be treated as actionable.

Suggested support block:

```yaml
support:
  state: candidate
  reason: requires-study-specific-staging
  checked_at: "2026-07-03"
  evidence:
    - entity.md#benchmark.limitations
    - https://proteomic.datacommons.cancer.gov/pdc/
  notes:
    - Benchmark-relevant portal record; a concrete study/package must be selected and staged before use.
    - Keep visible as a candidate for proteogenomic cross-modal validation, not as a runnable fallback.
```

### DREAM4 In Silico Network

Task:
`dataset:dream4-in-silico-network#network-reconstruction`

Decision: `support.state: candidate`

Reason: `requires-challenge-package-staging`

Rationale:

- The task is benchmark-relevant for mechanism inference and time-series or
  perturbation behavior checks.
- The record is currently `dataset_class: pointer`, so it tracks a known
  benchmark but does not identify a local datapackage or staged challenge
  package.
- Exact Synapse package layout and current download terms should be resolved
  before this becomes actionable.

Suggested support block:

```yaml
support:
  state: candidate
  reason: requires-challenge-package-staging
  checked_at: "2026-07-03"
  evidence:
    - entity.md#benchmark.limitations
    - https://www.synapse.org/Synapse:syn3049712
  notes:
    - Relevant synthetic benchmark for network reconstruction behavior checks.
    - Stage and document the exact DREAM4 challenge package before treating this task as runnable.
```

## Expected Report Behavior

After the commons metadata changes, active project runs such as:

```bash
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json
science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json
```

should show fewer visible fallback rows under
`fallback_diagnostics.task_support_counts.none`.

Rows for CCLE Proteomics should report:

```yaml
task_support_state: supported
```

Rows for CPTAC and DREAM4 should report:

```yaml
task_support_state: candidate
```

No **fallback** row should move because of this metadata: `gap-fallback` rows
are bucketed into `fallback-diagnostic` before any support-state check, and
blocked support is the only state suppressed by default, so `supported` and
`candidate` fallback rows stay visible in `fallback-diagnostic`.

Non-fallback rows are a different matter. `candidate` support has established
bucketing semantics for `opportunity-relative`/`gap-candidate` rows
(`_benchmark_test_triage_bucket`): a `candidate` row with `metadata-only`
readiness routes to `blocked-or-reference`, whereas the same row with no support
(`none`) and a `draft-needed` plan routes to `metadata-needed`. CPTAC
(`reference`) and DREAM4 (`pointer`) both resolve to `metadata-only` readiness,
so **if either benchmark also matches an entity as a non-fallback row**, adding
`candidate` support will move that row `metadata-needed → blocked-or-reference`
in the default (unfiltered) triage output. CCLE (`supported`) is bucket-neutral —
`supported` falls through to the same default path as `none`.

This slice intends that non-fallback bucketing does **not** change, which means
either CPTAC/DREAM4 produce no non-fallback rows in the target projects, or any
such movement must be surfaced and accepted deliberately. The validation below
checks this explicitly with an unfiltered run; a `--source gap-fallback` smoke
alone cannot see it, because the filter drops exactly the rows at risk.

## Validation

Implementation should run:

Capture the unfiltered baseline **before** editing commons metadata:

```bash
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --format json > /tmp/mm-triage-before.json
science benchmark test-triage --project-root ~/d/natural-systems --commons --format json > /tmp/ns-triage-before.json
```

Then apply the metadata and run:

```bash
science validate --project-root ~/d/science-commons
# Fallback-scoped smoke (intended effect):
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json
science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json
# Unfiltered smoke (guardrail against non-fallback bucket movement):
science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --format json > /tmp/mm-triage-after.json
science benchmark test-triage --project-root ~/d/natural-systems --commons --format json > /tmp/ns-triage-after.json
```

The validation pass should catch malformed support state, missing reasons for
candidate/blocked states, non-kebab-case reasons, invalid dates, and unknown
support fields.

The fallback-scoped smoke should confirm:

- `fallback_diagnostics.task_support_counts.none` decreases.
- `supported` increases for CCLE Proteomics fallback rows.
- `candidate` increases for CPTAC and DREAM4 fallback rows.
- `suppressed_blocked_support` is unchanged by this slice.

The unfiltered smoke should confirm the non-fallback bucketing guardrail:

- `summary.bucket_counts` is identical between the before/after unfiltered runs
  for each project. Any delta means CPTAC or DREAM4 surfaced as a non-fallback
  row and `candidate` support moved it (expected direction:
  `metadata-needed → blocked-or-reference`). If that happens, stop and decide
  whether the movement is acceptable before committing the commons edit, rather
  than discovering it later in a default `test-triage` run.

## Alternatives Considered

### Add Another Triage Filter

Rejected. The current issue is missing benchmark task metadata, not a report
projection bug. More filtering would hide the reason these rows are ambiguous.

### Stage CPTAC And DREAM4 First

Deferred. Staging is valuable but larger and more uncertain. Candidate support
metadata is the conservative interim state until access, package layout, and
license details are resolved.

### Annotate All Commons Benchmark Tasks

Rejected for this slice. Bulk annotation would mix calibrated judgments with
guesswork. The top-three pass is small enough to review carefully and measure.

## Implementation Notes

- Work in an isolated worktree for the `science` repo planning artifacts.
- Apply commons metadata edits in `~/d/science-commons`, which is a separate
  repository and should be committed separately if changes are made there.
- Do not edit benchmark command code unless validation reveals a real bug.
- Preserve existing frontmatter style in each target `entity.md`.

# Dataset Capability-Fit Gating Design

## Status

Implemented for coverage gating. Validation warnings and user-guide examples
remain follow-up rollout work.

## Context

`science dataset prioritize --coverage` currently credits a target when a
linked dataset has an acceptable runtime state. The target link can come from
question or hypothesis frontmatter, dataset `related`, paper `dataset_usage`, or
materialized graph reach. This is useful for topical reach, but it is not enough
for data-fitness.

The reported failure is cross-modality over-credit. A runnable scRNA dataset can
make chromatin-accessibility or proteomics questions look `covered-runnable`
because the dataset is linked and staged, even when the assay cannot produce the
required evidence. Manual de-linking fixes one target at a time but leaves the
same failure mode available for the next scRNA/scATAC/proteomics mismatch.

Current implementation facts:

- `prioritize()` builds dataset rows with `reaches` from `merged_reach()`.
- `target_coverage()` inverts those rows and counts runtime states for every
  reached target.
- `_coverage_state_and_reason()` promotes any runnable reached dataset to
  `covered-runnable`.
- `runtime_state_for()` intentionally answers only whether the dataset is
  staged/runnable/reference/pointer/gated, not whether it matches a target's
  evidence requirements.

## Goals

- Gate dataset-to-target coverage credit on data capability fit.
- Preserve topical reach as a separate signal from coverage credit.
- Make missing capability metadata conservative: do not silently over-credit.
- Keep the first implementation small enough to cover assay/modality fit without
  introducing a broad ontology dependency.
- Make JSON output explain why linked datasets did not count.

## Non-Goals

- Do not replace the existing reach graph.
- Do not change dataset ranking score in the first implementation.
- Do not infer assay fit from prose.
- Do not require every historical dataset and target to be fully annotated
  before the command remains useful.
- Do not solve sub-cohort, sample-type, disease-stage, perturbation, or endpoint
  compatibility in this slice. Those can extend the same contract later.

## Decision

Introduce an explicit capability contract:

- Targets may declare `required_capabilities`.
- Datasets may declare `provided_capabilities`.
- A dataset gets coverage credit for a target only when at least one provided
  capability set satisfies at least one required capability set.

Use an AND-within-set / OR-across-sets model:

```yaml
required_capabilities:
  - assay: chromatin-accessibility
    modality: scATAC
  - assay: chromatin-accessibility
    modality: multiome
```

```yaml
provided_capabilities:
  - assay: gene-expression
    modality: scRNA
  - assay: chromatin-accessibility
    modality: scATAC
```

Compatibility is exact by default. A provided set satisfies a required set when
every key/value pair in the required set is present with the same value in the
provided set. This supports the motivating "provided assay superset required"
case without needing a hierarchy on day one. If hierarchy is needed later, it
should be represented in one resolver module, not spread through callers.

## Authoring Contract

Supported first-slice keys:

- `assay`
- `modality`

Values are lowercase slugs. The initial implementation should reject malformed
shapes only when validation is explicitly run; `dataset prioritize --coverage`
should instead report capability metadata as missing or invalid in row details
and avoid crediting that pair.

Targets without `required_capabilities` are capability-unassessed. To avoid a
flag day, they can still be reported, but linked datasets should not count as
`covered-runnable`; their gap reason should explain that target requirements are
missing. This is conservative and prevents silent false coverage.

Datasets without `provided_capabilities` are capability-unassessed. They remain
visible in `datasets`, but they do not contribute to runtime credit for targets
with requirements.

## Coverage Semantics

`target_coverage()` should split reached datasets into two groups:

- `compatible_datasets`: reached datasets whose capabilities satisfy the target.
- `incompatible_datasets`: reached datasets that fail or cannot evaluate the
  capability-fit check.

Only `compatible_datasets` feed runtime-state counts. `datasets` can remain the
full reached list for backwards visibility, but JSON must include enough detail
to distinguish linked-but-not-creditable datasets.

Proposed per-target JSON additions:

```json
{
  "datasets": ["dataset:tirier-2021-mm-rrmm-scrna"],
  "compatible_datasets": [],
  "incompatible_datasets": [
    {
      "dataset": "dataset:tirier-2021-mm-rrmm-scrna",
      "reason": "capability-mismatch",
      "required_capabilities": [{"assay": "chromatin-accessibility", "modality": "scATAC"}],
      "provided_capabilities": [{"assay": "gene-expression", "modality": "scRNA"}]
    }
  ],
  "coverage_state": "capability-mismatch",
  "gap_reason": "capability-mismatch"
}
```

Add gap reasons:

- `missing-required-capabilities`: target has linked datasets but no authored
  requirement, so coverage is unassessed.
- `missing-provided-capabilities`: all linked datasets lack provided capability
  metadata.
- `capability-mismatch`: at least one linked dataset has provided capabilities,
  but none satisfy the target requirement.

Priority order for coverage state should become:

1. Runtime states among compatible datasets, using the existing order:
   `covered-runnable`, `covered-unstaged`, `covered-reference`,
   `covered-pointer`, `blocked-access`, `unverified`.
2. Capability-specific gap states when linked datasets exist but none are
   compatible.
3. `no-candidate` when no dataset reaches the target at all.

The first implementation can use `coverage_state == gap_reason` for the three
capability-specific states. If UI consumers later need a smaller state enum, the
state can collapse to `no-compatible-candidate` while preserving detailed
`gap_reason`.

## Implementation Shape

Add a small pure module, for example
`science_tool.datasets.capabilities`, containing:

- `capability_sets_from(value: object) -> list[dict[str, str]]`
- `capability_fit(required: object, provided: object) -> CapabilityFit`
- `compatible(required_sets, provided_sets) -> bool`

`CapabilityFit` should carry:

- `compatible: bool`
- `reason: str`
- normalized `required` and `provided` capability sets

`target_coverage()` should load target frontmatter from the existing
`targets` map and dataset frontmatter via `_frontmatter_for_row()`. It should
evaluate capability fit per target-row pair before incrementing runtime counts.

Keep the fit logic pure and independent of graph materialization. The same
frontmatter-only path must work when the graph is missing or stale, matching the
existing coverage behavior.

## Validation

Add lightweight validation in the existing checks layer after implementation:

- Warn when a question or hypothesis has `datasets`/dataset reach but no
  `required_capabilities`.
- Warn when a dataset has runtime artifacts or is linked to targets but no
  `provided_capabilities`.
- Error only for malformed capability structures, not for absence during the
  adoption window.

This lets projects migrate incrementally while making unassessed fit visible.

## Test Plan

Add focused tests before implementation:

- A runnable scRNA dataset linked to an scATAC/chromatin-accessibility question
  yields `capability-mismatch`, not `covered-runnable`.
- A multiome dataset with both gene-expression and chromatin-accessibility
  provided capabilities satisfies a chromatin-accessibility target.
- A target with linked datasets but no `required_capabilities` yields
  `missing-required-capabilities`.
- A required target linked to a dataset with no `provided_capabilities` yields
  `missing-provided-capabilities`.
- Existing runtime-state coverage behavior remains unchanged when capability fit
  succeeds.
- CLI JSON includes compatible and incompatible dataset details.

## Rollout

1. Implement the pure capability parser and matcher with unit tests.
2. Thread capability fit into `target_coverage()` only.
3. Add CLI JSON/table rendering for compatible and incompatible counts.
4. Add validation warnings for missing/malformed capability fields.
5. Update user docs with the new frontmatter examples.

Dataset ranking can remain unchanged until coverage gating proves stable. If
future ranking should prefer capability-fit datasets, add that as a separate
design because it changes prioritization rather than coverage truth.

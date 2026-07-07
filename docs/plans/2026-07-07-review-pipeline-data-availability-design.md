# review-pipeline data availability tightening — design

**Date:** 2026-07-07
**Targets:** `fb-2026-07-03-004`, `fb-2026-07-04-003`
**Surface:** `command:review-pipeline`, `science-review-pipeline`

`review-pipeline` already treats data availability as a stageability gate: plan
inputs must resolve to dataset entities, access evidence must be current, and
runtime artifacts must exist unless the plan explicitly uses a WP1 retrieval
probe. Recent feedback exposed two gaps in that rubric.

## Problem

First, the rubric reviews the inputs a pipeline plan declares, but it does not
force the reviewer to compare those declared inputs with a locked
pre-registration model. A plan can therefore omit covariates, strata, adjustment
variables, or signature inputs that the pre-registration says are required.
That makes the plan look stageable even though the locked analysis cannot run.

Second, Dimension 3 has a retrieval-probe exception for primary datasets such
as summary statistics, but no separate treatment for reference-class inputs
such as LD panels, genome builds, annotation releases, or benchmark/reference
resources. A probe can reasonably defer those reference inputs to a follow-on
design/staging work package, but the current wording makes that deferral
ambiguous.

## Decision

Keep this as a review-rubric guidance change. There is no executable
`review-pipeline` validator in the toolkit today; the command and Codex skill
are the public surface. Add doc tests to lock in the new requirements.

Dimension 3 should now require a cross-check between:

- every plan-declared input data source; and
- every data requirement implied by the locked pre-registration model,
  including covariates, adjustment variables, strata, subgroup labels,
  endpoint/timing variables, score inputs, and signature features.

Any locked-model requirement that is absent from the plan input inventory is a
**FAIL**. The failure reason is not "missing metadata"; it is that the plan is
not stageable for the analysis it claims to execute.

Dimension 3 should also distinguish reference-class inputs from primary
analytic inputs. Reference-class inputs may be deferred only when the plan:

- labels them as reference-class inputs;
- names a follow-on design or staging work package that owns acquisition;
- requires version pinning, checksums or equivalent identity evidence, and
  compatibility checks before downstream analysis runs.

This carve-out does not apply to primary analytic datasets, ordinary covariates,
or locked-model variables. Those still need to resolve and stage before the
pipeline can pass Dimension 3.

## Scope

In scope:

- Update `commands/review-pipeline.md` Dimension 3 wording.
- Update `codex-skills/science-review-pipeline/SKILL.md` with the same
  operational rubric.
- Add source-doc tests for both surfaces.
- Preserve the existing WP1 retrieval-probe exception for primary datasets.

Out of scope:

- Building an executable `review-pipeline` validator.
- Inferring pre-registration requirements from arbitrary prose.
- Changing pre-registration templates or plan-pipeline authoring guidance.
- Supporting silent fallback when the pre-registration is absent.

## Scoring Semantics

PASS requires that declared inputs and locked-model requirements are reconciled.
If the plan cites a locked pre-registration, the reviewer should extract the
required analysis variables and confirm that each one is represented by a
plan-declared input source or a derived input with traceable upstream sources.

WARN remains appropriate for stale access evidence, missing backlinks, and
metadata drift that does not block staging.

FAIL now explicitly includes:

- A locked pre-registration model requires a covariate, adjustment variable,
  stratum/subgroup label, endpoint/timing variable, score input, or signature
  feature that the plan never declares as an input or derived input.
- A plan defers a reference-class input without naming the follow-on
  design/staging owner and the required version, checksum, identity, and
  compatibility checks.

## Alternatives Considered

### Build a parser-backed validator now

Rejected for this slice. The current review-pipeline surface is guidance-driven,
and project plans/pre-registrations do not yet expose a stable machine-readable
schema for locked model variables. A parser would risk false certainty and
ad-hoc string matching.

### Treat all undeclared reference inputs as FAIL

Rejected. Reference-class resources often require careful version/compatibility
selection that belongs in a staging design, not in the first plan review. The
carve-out is acceptable when it is explicit and owned.

### Allow reference-class deferral for covariates

Rejected. Covariates and locked-model variables are analysis inputs, not
reference resources. Deferring them would recreate the original data-fitness
gap.

## Testing

Focused source-doc tests should assert that both the Claude command and Codex
skill:

- require comparing declared plan inputs to locked pre-registration model
  requirements;
- name covariates, adjustment variables, strata, endpoint/timing variables,
  score inputs, and signature features;
- classify undeclared locked-model requirements as `FAIL`;
- describe the reference-class input carve-out;
- require a follow-on design/staging owner plus version pinning, checksums or
  identity evidence, and compatibility checks; and
- state that the carve-out does not apply to primary analytic datasets,
  covariates, or locked-model variables.

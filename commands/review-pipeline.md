---
description: Critically review a pipeline plan against an evidence rubric — coverage, assumptions, data availability, identifiability, reproducibility, validation, scope. Use when the user wants to review or audit a pipeline before implementation.
---

# Review Pipeline

> **Prerequisites:**
> - Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics
> - Load the `research-methodology` skill
> - Read the `discussant` role prompt from `prompts/roles/discussant.md` (if available)

## Overview

This command performs a systematic review of an inquiry and its pipeline plan. It operates as a critical discussant — looking for weaknesses, missing evidence, and unjustified assumptions.

The review is NOT a rubber stamp. It should surface problems the user hasn't considered.

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

## Rules

- **MUST** run structural validation first (`inquiry validate`)
- **MUST** evaluate all 9 rubric dimensions
- **MUST** be critical — surface weaknesses, don't just confirm the plan is good
- **MUST** provide specific, actionable recommendations for each issue
- **MUST** save review report under `doc/reviews/<stem>-pipeline-review.md` with a frontmatter backlink to the reviewed inquiry or plan (see *Resolve the target* below)
- **SHOULD** cross-reference claims against existing literature (LLM knowledge + web search)
- **MUST NOT** change the inquiry or plan — only report findings

## Workflow

### Step 1: Load inquiry and plan

**Resolve the target first.** Not every project routes plans through `inquiry`. If the
artifact under review is a graph-backed inquiry (a compiled `inquiry:<slug>` whose
source normally lives at `entities/patches/<slug>.md`), use the inquiry commands
below. If it is a prose-first inquiry (`entities/inquiries/<slug>.md`) or a
standalone `kind: plan` document (e.g. `entities/plans/<stem>.md`
with no inquiry slug), the `science inquiry show/validate <slug>` calls do **not** resolve — skip
them and instead drive the review from the plan document itself plus its frontmatter `related:`
entities. Save the review outside the entity tree as `doc/reviews/<stem>-pipeline-review.md` so layout
v3 entity-conformance does not treat the review as a malformed plan entity.

For an inquiry target:

```bash
science inquiry show "<slug>" --format table
science inquiry validate "<slug>" --format json
```

Also read (whichever exist):
- `entities/patches/<slug>.md` — graph-backed inquiry source, if present
- `entities/inquiries/<slug>.md` — prose-first or legacy inquiry document, if present
- `entities/plans/<stem>.md` and its `related:` entities — plan document (plan target)
- `entities/plans/*<slug>*` — implementation plan (if exists)
- `specs/scope-boundaries.md` — project scope

**Sub-plan handling:** If the plan being reviewed is a sub-plan of a larger inquiry (e.g., Tasks 2-3 of a broader inquiry), the inquiry-level validation may pass trivially. In this case:
- Apply the rubric dimensions to the plan's internal consistency, not just the parent inquiry's structure.
- Dimensions 1 (Evidence Coverage) and 7 (Scope Check) may be marked **N/A — inherited from parent plan** if the parent plan has already passed review on these dimensions. Reference the parent plan's review document.
- Focus review effort on dimensions specific to the sub-plan: validation criteria (Dim 6), assumption audit (Dim 2), integration boundaries (Dim 8).

### Step 2: Evaluate each rubric dimension

#### Dimension 1: Evidence Coverage

- Does every non-trivial parameter have `sci:paramSource` and `sci:paramRef`?
- Are there `[UNVERIFIED]` markers in the inquiry doc?
- Do any `sci:Unknown` nodes remain?

**Scoring:** PASS (all params sourced), WARN (some missing refs), FAIL (unsourced causal claims)

#### Dimension 2: Assumption Audit

For each `sci:Assumption` and `scic:causes` edge:
- Is the assumption justified with evidence?
- Could confounders explain the relationship?
- Is the causal direction justified?

**Scoring:** PASS (all justified), WARN (minor gaps), FAIL (unjustified causal claims)

#### Dimension 3: Data Availability

For each input data source (every `BoundaryIn` node or data-acquisition step
in the plan):

- Does it resolve to a `dataset:<slug>` entity?
- Per origin (verification gate):
  - `external`: `access.verified: true` OR `access.exception.mode != ""`.
    `access.source_url` populated when verified.
    `access.last_reviewed` within the last 12 months.
  - `derived`: `derivation.workflow_run` exists; symmetric `produces:` edge present;
    `derivation.inputs` transitively pass.
- Runtime stageability (separate gate, runs in addition to verification):
  - At least one of `entity.datapackage` or `entity.local_path` is populated AND
    the referenced runtime file exists on disk.
  - Exception for retrieval probes: if `access.verified: true` and the plan says
    WP1 is the staging step ("retrieve and verify this dataset"), treat the
    absent runtime file as **PASS-with-note** / deferred-to-WP1; do not score
    absent runtime files as FAIL in this pattern; instead require WP1 to end by
    producing the runtime artifact, datapackage/checksums, and any updated
    `last_reviewed` evidence before downstream work runs.
  - `consumed_by` includes `plan:<this-plan-file-stem>`.
  - The dataset lifecycle contract in `docs/user-guide/entities.md` holds:
    external records use `access:`, derived records use `derivation:`, and
    resource-level metadata lives in the runtime datapackage.
- Access verification should be current: if a public, registration-only, or
  credentialed external dataset is obtainable but has stale or missing evidence,
  require `science dataset verify-access <slug>` before downstream stages consume
  it.

**Scoring:**

- **PASS** — all sources resolve; verification gate satisfied per origin; runtime
  stageability satisfied, or runtime stageability is explicitly deferred to WP1
  under the retrieval-probe exception above; backlink present; freshness OK;
  invariants hold.
- **WARN** — stale `last_reviewed` (> 12 months); missing canonical `plan:<stem>`
  backlink; cached-field drift between entity and runtime
  (`ontology_terms`/`license`/`update_cadence` only); lineage drift.
- **FAIL** — any of:
  - A source does not resolve to a dataset entity.
  - External `access.verified: false` with `access.exception.mode: ""`.
  - External `access.verified: true` but `verification_method: ""` or no
    `last_reviewed`.
  - Derived missing `workflow_run` entity, asymmetric `produces:` edge, or broken
    transitive input chain.
  - Runtime stageability fails outside the retrieval-probe exception: neither
    `datapackage` nor `local_path` populated, OR the referenced runtime file
    does not exist on disk.
  - A plan references an umbrella entity (non-empty `siblings:`).
  - Origin/block-exclusion violation (#7 or #8).
  - research-package symmetry violation (#11).

#### Dimension 4: Identifiability

- Is every `BoundaryOut` reachable from `BoundaryIn` via directed edges?
- Are there disconnected components?
- Can the target hypothesis actually be tested?

**Scoring:** PASS (fully connected), FAIL (disconnected or unreachable)

#### Dimension 5: Reproducibility

- Are random seeds specified?
- Are software versions pinned?
- Are environments reproducible?

**Scoring:** PASS (fully specified), WARN (partial), FAIL (no reproducibility measures)

#### Dimension 6: Validation Criteria

- Does every `sci:Transformation` have a `sci:validatedBy` check?
- Is the check specific enough to catch failures?
- For steps that ingest real-world/heterogeneous input: does validation include a **scale/resource run on real data** (representative slice or full corpus, peak memory + wall-clock), not just fixture-based logic checks? Green fixtures do not prove resource behavior on real input.

**Scoring:** PASS (all steps validated, incl. scale/resource on real data where applicable), WARN (gaps, or scale validation deferred entirely to production), FAIL (no validation)

#### Dimension 7: Scope Check

- Does the inquiry stay within `specs/scope-boundaries.md`?
- Are there scope-creep risks?

**Scoring:** PASS (in scope), WARN (borderline), FAIL (out of scope)

#### Dimension 8: Integration Boundary Check

- Does the plan's output format match the consuming module's input format?
- Check tensor dimensions, data schemas, and API contracts across module boundaries
- Verify that intermediate representations are compatible between pipeline stages
- Read the actual code at integration points (model input shapes, data loader expectations, etc.)

**Scoring:** PASS (all boundaries verified), WARN (some unchecked), FAIL (mismatches found)

#### Dimension 9: Manifest Completeness

- Does the workflow produce a `datapackage.json` manifest in its output directory?
- Are all output resources listed?
- Are entity cross-references specified?
- Is provenance DAG included?

**Scoring:** PASS (complete manifest with resources + entities + provenance) /
WARN (manifest present but incomplete) / FAIL (no manifest generation)

### Step 3: Write review report

Save under `doc/reviews/<stem>-pipeline-review.md`, where `<stem>` is the reviewed inquiry or plan
file stem. Include a `reviews:` backlink to the reviewed entity or file path:

```markdown
# Pipeline Review: {{label}}

- **Reviews:** {{reviewed-ref-or-path}}
- **Date:** {{date}}
- **Overall:** {{PASS|WARN|FAIL}}

## Summary

{{2-3 sentence assessment}}

## Rubric Results

| Dimension | Score | Issues |
|---|---|---|
| Evidence coverage | {{score}} | {{brief}} |
| Assumption audit | {{score}} | {{brief}} |
| Data availability | {{score}} | {{brief}} |
| Identifiability | {{score}} | {{brief}} |
| Reproducibility | {{score}} | {{brief}} |
| Validation criteria | {{score}} | {{brief}} |
| Scope check | {{score}} | {{brief}} |
| Integration boundaries | {{score}} | {{brief}} |
| Manifest completeness | {{score}} | {{brief}} |

## Detailed Findings

### {{Dimension with issues}}

{{Specific findings with actionable recommendations}}

## Recommendations

1. {{Highest priority action}}
2. {{Next priority}}

## Strengths

{{What's done well}}
```

Update the inquiry status to `reviewed`.

### Step 4: Present to user

Show the summary table and top recommendations. Ask if they want to:
1. Address the findings (modify inquiry/plan)
2. Accept the risks and proceed
3. Discuss specific findings in more depth

## Important Notes

- **Be genuinely critical.** The value is in finding problems before implementation.
- **Cross-check claims.** Use LLM knowledge and web search to verify factual claims.
- **Look for circular reasoning.** If A justifies B and B justifies A, flag it.
- **Consider failure modes.** For each transformation: what happens if it fails?

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:review-pipeline" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead

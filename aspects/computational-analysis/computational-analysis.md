---
name: computational-analysis
description: Computational and exploratory data analysis
---

# Computational Analysis

Projects involving computational experiments, exploratory analysis, benchmarks, or pipeline-driven results.

## interpret-results

### Additional section: Sub-group Analysis (optional)

(insert after: Additional Observations)

If results reveal sub-groups, clusters, or decompositions within the data:
- Characterize each sub-group with quantitative descriptors
- Compare sub-groups systematically (table format preferred)
- Note whether sub-groups are stable across methods or parameters
- Flag sub-groups that may be artifacts of the analysis method

Only include this section when decomposition results are present.

### Additional guidance

For computational/exploratory results:
- Distinguish between confirmatory analysis (testing a pre-specified hypothesis) and exploratory analysis (pattern discovery)
- When results are exploratory, note what would be needed to confirm the patterns
- For benchmark results, include baseline comparisons and report relative as well as absolute performance

## discuss

### Additional guidance

When discussing computational results:
- Consider whether findings are method-dependent (would a different algorithm produce the same pattern?)
- Distinguish between statistical artifacts and genuine structure
- For pipeline results, consider sensitivity to parameter choices

## research-topic

### Additional guidance

When researching computational methods or tools:
- Note implementation maturity and community adoption
- Compare alternative approaches systematically
- Include practical resources (libraries, frameworks, example code)

## plan-pipeline

### Additional section: QA Checkpoints

(insert after: the last Task in the pipeline plan)

For each pipeline stage (each `sci:Transformation` node), define:

**Input assertions:**
- Expected row counts or data dimensions
- Value ranges and type constraints
- Missingness rates and schema conformance
- Distribution checks (if known expectations exist)

**Inter-stage invariants:**
- No silent row drops: row count before/after each transformation with allowed tolerance
- Referential integrity: foreign keys and join conditions verified
- Value conservation: aggregation totals match, no data loss in reshaping
- Cardinality checks: one-to-many, many-to-many relationships as expected

**Sanity checks:**
- Known-answer tests: run on synthetic or known data where the correct answer is predetermined
- Spot checks: sample N records and verify by hand
- Summary statistics: mean, median, range before/after each stage

**Failure mode:**
- Default: hard stop (assertion failure halts the pipeline)
- Document any stages where a logged warning is acceptable instead, with justification
- **Manifest generation:** verify `datapackage.json` is produced and passes
  `frictionless validate`

Add QA checkpoints as first-class steps in the pipeline plan, not as afterthoughts. Each transformation task should include its assertions alongside the implementation steps.

### Additional guidance

When planning computational pipelines:
- Suggest a "dry run on small data" step before full execution
- For each transformation, ask: "How would I know if this step silently produced wrong results?"
- Include a final end-to-end sanity check that validates the complete output against known properties

## review-pipeline

### Additional rubric dimension: QA Coverage

(insert after: Dimension 7: Scope Check)

Evaluate QA discipline across the pipeline:

- **Assertion coverage:** Does every `sci:Transformation` have input/output assertions? Score: PASS (all covered) / WARN (gaps) / FAIL (no assertions)
- **Intermediate checkpoints:** Are there checks between stages, or is it black-box end-to-end? Score: PASS (intermediate checks) / WARN (only final check) / FAIL (no checks)
- **Failure handling:** What happens when an assertion fails? Is it hard stop or silent? Score: PASS (hard stop default) / WARN (mixed) / FAIL (all silent)
- **Dry run step:** Is there a "run on small/synthetic data" step before full execution? Score: PASS (present) / WARN (suggested but not planned) / FAIL (absent)
- **Edge case coverage:** Are edge cases documented (empty inputs, missing values, extreme values)? Score: PASS (documented) / WARN (partial) / FAIL (not considered)

Include QA Coverage as an additional row in the rubric results table.

## Signal categories

- **Descriptive** — structure observed but not statistically testable (e.g., UMAP clusters, NMF factors, visualization patterns)

## Available commands

(none)

## Workflow Lifecycle

Computational projects track work through a formal lifecycle:

1. **Method definition** — conceptual approach documented as a `method` entity
2. **Workflow registration** — executable pipeline registered as a `workflow` entity
   with `sci:realizes` link to the method
3. **Run execution** — each invocation creates a `workflow-run` entity with
   `sci:executes` link to the workflow
4. **Manifest generation** — run produces `datapackage.json` with resources,
   entity cross-references, and provenance DAG
5. **Interpretation** — results interpreted via `interpret-results` command,
   linked back to the run via `workflow_run` field
6. **Supersession** — when a run is re-executed with updated parameters, the new
   run uses `sci:supersedes` to link to the prior run

### QA Checkpoint: Manifest Validation

After each workflow run, validate the manifest:
- All output files listed as resources
- Entity cross-references present and valid
- Config snapshot matches actual config used
- Provenance DAG covers all rules that executed

---
description: Critically review a pipeline plan against an evidence rubric. Checks evidence coverage, assumption validity, data availability, identifiability, reproducibility, validation criteria, and scope. Use when the user wants to review, audit, or check a pipeline before implementation. Also use when the user says "review pipeline", "check my plan", "audit assumptions", or "is this ready".
---

# Review Pipeline

> **Prerequisites:**
> - Load the `knowledge-graph` skill
> - Load the `research-methodology` skill
> - Read the `discussant` role prompt from `prompts/roles/discussant.md` (if available)

## Overview

This command performs a systematic review of an inquiry and its pipeline plan. It operates as a critical discussant — looking for weaknesses, missing evidence, and unjustified assumptions.

The review is NOT a rubber stamp. It should surface problems the user hasn't considered.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

## Rules

- **MUST** run structural validation first (`inquiry validate`)
- **MUST** evaluate all 9 rubric dimensions
- **MUST** be critical — surface weaknesses, don't just confirm the plan is good
- **MUST** provide specific, actionable recommendations for each issue
- **MUST** save review report to `doc/inquiries/<slug>-review.md`
- **SHOULD** cross-reference claims against existing literature (LLM knowledge + web search)
- **MUST NOT** change the inquiry or plan — only report findings

## Workflow

### Step 1: Load inquiry and plan

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Also read:
- `doc/inquiries/<slug>.md` — inquiry document
- `doc/plans/*<slug>*` — implementation plan (if exists)
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

For each `BoundaryIn` node:
- Is the data source specified?
- Is the data actually accessible?
- Is the format specified?

**Scoring:** PASS (all accessible), WARN (some unspecified), FAIL (inaccessible sources)

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

**Scoring:** PASS (all steps validated), WARN (gaps), FAIL (no validation)

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

Save to `doc/inquiries/<slug>-review.md`:

```markdown
# Pipeline Review: {{label}}

- **Inquiry:** {{slug}}
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

Reflect on the **review rubric** and the **audit workflow**.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — review-pipeline

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("QA coverage rubric was hard to score without seeing actual assertion code" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

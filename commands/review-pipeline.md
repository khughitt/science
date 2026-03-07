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
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

## Rules

- **MUST** run structural validation first (`inquiry validate`)
- **MUST** evaluate all 7 rubric dimensions
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

## Detailed Findings

### {{Dimension with issues}}

{{Specific findings with actionable recommendations}}

## Recommendations

1. {{Highest priority action}}
2. {{Next priority}}

## Strengths

{{What's done well}}
```

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

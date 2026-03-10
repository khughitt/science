---
description: Critically review a causal DAG inquiry for missing confounders, identifiability issues, and structural problems. Use when the user wants to review a causal model, check for confounders, audit assumptions, or validate their causal reasoning. Also use when the user says "critique", "review my DAG", "check confounders", "is this identifiable", or "what am I missing".
---

# Critique a Causal Approach

> **Prerequisite:** Load the `knowledge-graph` and `causal-dag` skills for ontology and causal modeling reference.

## Overview

This command provides a critical, adversarial review of a causal inquiry. The agent operates as a **discussant** — looking for weaknesses, missing confounders, and threats to validity. This is not a rubber stamp; the goal is to surface problems before the researcher invests in analysis.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, examples write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** operate in discussant/critic role — be skeptical, not supportive
- **MUST** run structural validation first (`inquiry validate`)
- **MUST** challenge every causal edge for reverse causation and alternative explanations
- **MUST** check for missing confounders systematically
- **MUST** assess identifiability (can the target effect be estimated from observables?)
- **MUST** write review report to `doc/inquiries/<slug>-critique.md`
- **MUST NOT** dismiss concerns as "minor" or "unlikely" — surface all issues
- **SHOULD** reference the causal-dag skill for pitfall patterns

## Workflow

### Step 1: Load the inquiry

The user provides an inquiry slug (e.g., `/science:critique-approach my-dag`).

```bash
science-tool inquiry show "<slug>" --format json
science-tool inquiry validate "<slug>" --format json
```

Verify:
- The inquiry exists and is type `causal`
- Structural validation passes (or note failures)
- Treatment and outcome are set

### Step 2: Graph-theoretic analysis

Export to pgmpy and analyze:

```bash
science-tool inquiry export-pgmpy "<slug>" --output /tmp/dag_analysis.py
```

Read the generated script. Identify:
- **Adjustment sets**: What should be conditioned on to identify the causal effect?
- **Testable implications**: What conditional independencies does the DAG predict?
- **Identifiability**: Is the target effect (treatment → outcome) identifiable given observed variables?

If there are latent (unobserved) variables, note that the back-door criterion may not be satisfied.

### Step 3: Challenge each causal edge

For every `scic:causes` edge in the DAG, ask:

1. **Reverse causation**: "Could B actually cause A instead of A causing B?"
2. **Mediation**: "Is there an unmeasured mediator M such that A → M → B? Does this matter for identification?"
3. **Selection bias**: "Could the study design or data collection process condition on a descendant of this edge?"
4. **Temporal ordering**: "Does A occur before B? Is there evidence for temporal precedence?"
5. **Evidence quality**: "What is the confidence and source for this edge? Is it well-established or speculative?"

### Step 4: Check for missing confounders

For every pair of variables (X, Y) connected by a causal edge:
- "What else could affect both X and Y?"
- "Are there environmental, genetic, or methodological factors that influence both?"
- "Would a domain expert immediately identify a missing common cause?"

For each identified missing confounder:
- Note it in the review
- Suggest adding it to the DAG
- Assess whether it's observable or latent

### Step 5: Check for structural problems

- **Collider bias**: Is the user conditioning on (adjusting for) a collider? This creates spurious associations.
- **M-bias**: Is there a path where adjusting for a seemingly innocuous variable opens a non-causal path?
- **Overadjustment**: Is the user adjusting for a mediator on the causal path? This blocks the effect being estimated.
- **Circular reasoning**: Does evidence for edge A → B rely on the assumption that A → B?

### Step 6: Assess overall validity

Rate each dimension:

| Dimension | Assessment |
|-----------|-----------|
| Completeness | Are all plausible confounders included? |
| Identifiability | Can the target effect be estimated from observables? |
| Evidence quality | Are causal edges well-supported by literature/data? |
| Structural validity | No collider bias, M-bias, or overadjustment? |
| Temporal coherence | Does the causal ordering make temporal sense? |
| Sensitivity | How robust are conclusions to assumption violations? |

### Step 6b: Sensitivity analysis

For each key assumption or causal edge identified in steps 3-5, assess sensitivity:

1. **What if this assumption is violated?**
   - State the assumption explicitly
   - Describe how conclusions change if it's wrong
   - Rate impact: high (conclusions reverse) / moderate (conclusions weaken) / low (conclusions robust)

2. **What if this relationship doesn't hold or is reversed?**
   - For causal edges: what if A doesn't cause B, or B causes A?
   - For conceptual models: what if this link is spurious or mediated?

3. **Unmeasured variables**
   - For causal DAGs: for each critical path, what unmeasured confounder could explain the relationship?
   - For conceptual models: what hidden mediator or moderator could alter the relationship?

4. **Robustness**
   - What's the minimum effect size that would survive the identified threats?
   - How sensitive are conclusions to parameter choices?

5. **Boundary conditions**
   - Under what conditions does the model break down entirely?
   - Are there population, temporal, or contextual limits to applicability?

Include a sensitivity summary table in the review report:

| Assumption | If Violated | Impact | Robustness |
|---|---|---|---|
| <assumption> | <consequence> | high/moderate/low | <assessment> |

### Step 7: Write review report

Save to `doc/inquiries/<slug>-critique.md`:

```markdown
# Causal DAG Critique: <label>

**Inquiry:** <slug>
**Treatment:** <treatment>
**Outcome:** <outcome>
**Reviewed:** <date>

## Structural Validation
<inquiry validate results>

## Identifiability Assessment
<adjustment sets, back-door criterion>

## Edge-by-Edge Review
<for each edge: evidence, challenges, confidence>

## Missing Confounders
<identified gaps>

## Structural Issues
<collider bias, M-bias, overadjustment>

## Sensitivity Analysis
<sensitivity summary table and key findings>

## Overall Assessment
<summary table with pass/warn/fail per dimension>

## Recommendations
<specific actionable items>
```

Update the inquiry status to `critiqued`.

Note: this status indicates the inquiry has been through critical review, NOT that it passed. The review report documents what was found.

### Step 8: Present findings

Summarize the key findings to the user:
- Critical issues (must fix before analysis)
- Important concerns (should investigate)
- Minor notes (awareness items)
- Recommended next steps

## Process Reflection

Reflect on the **critique rubric** (structural checks, confounder identification, edge review).

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — critique-approach

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
- Be concrete and specific, not generic ("the M-bias check was hard to apply without a visual DAG rendering" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

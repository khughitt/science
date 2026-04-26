---
description: Critically review a causal DAG inquiry for missing confounders, identifiability issues, and structural problems. Use when the user wants to review a causal model, check confounders, or validate causal reasoning.
---

# Critique a Causal Approach

> **Prerequisite:** Read `docs/proposition-and-evidence-model.md`, `docs/specs/2026-03-01-knowledge-graph-design.md`, `references/dag-two-axis-evidence-model.md`, and `docs/specs/2026-03-07-phase4b-causal-dag-design.md` for ontology and causal modeling reference.

## Overview

This command provides a critical, adversarial review of a causal inquiry. The agent operates as a **discussant** — looking for weaknesses, missing confounders, and threats to validity. This is not a rubber stamp; the goal is to surface problems before the researcher invests in analysis.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

For brevity, examples write just `science-tool <command>` — **always expand to `uv run science-tool <command>` when executing. See command-preamble step 8 for fallback.**

## Rules

- **MUST** operate in discussant/critic role — be skeptical, not supportive
- **MUST** run structural validation first (`inquiry validate`)
- **MUST** challenge every causal edge for reverse causation and alternative explanations
- **MUST** check for missing confounders systematically
- **MUST** assess identifiability (can the target effect be estimated from observables?)
- **MUST** write review report to `doc/inquiries/<slug>-critique.md`
- **MUST NOT** dismiss concerns as "minor" or "unlikely" — surface all issues
- **SHOULD** reference `references/dag-two-axis-evidence-model.md` for pitfall patterns

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
6. **Measurement path**: "Is this edge supported by a direct observation, or by a proxy that should have `measurement_model` and `proxy_directness` called out explicitly?"

### Step 4: Check for missing confounders

For every pair of variables (X, Y) connected by a causal edge:
- "What else could affect both X and Y?"
- "Are there environmental, genetic, or methodological factors that influence both?"
- "Would a domain expert immediately identify a missing common cause?"

For each identified missing confounder:
- Note it in the review
- Suggest adding it to the DAG
- Assess whether it's observable or latent

Also check whether supposedly independent support lines really collapse into one `independence_group`.

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

For mixed empirical / mechanistic arguments, ask whether the inquiry is silently promoting an empirical regularity into a mechanistic narrative without enough lower-layer support.

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

If `science-tool health --format json` surfaces proxy gaps, unsupported mechanistic narratives, or rival-model packet issues related to this inquiry, mention them explicitly in the critique summary.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:critique-approach" \
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

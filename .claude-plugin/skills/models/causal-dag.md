---
name: causal-dag
description: Reference guide for causal DAG modeling within the science inquiry framework. Covers causal structure, common pitfalls, provenance discipline, and export to pgmpy/ChiRho. Loaded by build-dag and critique-approach as background context.
---

# Causal DAG Modeling Reference

## When to Use Causal vs. General Inquiries

| Use case | Inquiry type |
|----------|-------------|
| Exploring data flow, variables, computational steps | `general` |
| Modeling cause-and-effect relationships between variables | `causal` |
| Estimating treatment effects, testing interventions | `causal` |
| Identifying confounders and adjustment sets | `causal` |

A **general inquiry** uses `sci:feedsInto` edges for data/computational flow. A **causal inquiry** uses `scic:causes` and `scic:confounds` edges in `graph/causal` to represent believed causal relationships.

## Causal Structure

### Key roles

| Role | Predicate | Description |
|------|-----------|-------------|
| Treatment | `sci:treatment` | The intervention variable (what you manipulate) |
| Outcome | `sci:outcome` | The effect variable (what you measure) |
| Confounder | `scic:confounds` | Affects both treatment and outcome |
| Mediator | — | On the causal path between treatment and outcome |
| Collider | — | Caused by two or more variables (dangerous to condition on) |

### Edge types

| Predicate | Layer | Meaning |
|-----------|-------|---------|
| `scic:causes` | `graph/causal` | A causally influences B |
| `scic:confounds` | `graph/causal` | A confounds the relationship between two variables |

Causal edges live in `graph/causal` (shared, reusable across inquiries). The inquiry subgraph contains boundary roles and membership only.

## Common Pitfalls

### Conditioning on a collider
If X → Z ← Y, conditioning on Z (e.g., including it in a regression) creates a spurious association between X and Y. Never adjust for a collider.

### M-bias
If there is a path W → X ← U → Y ← V, adjusting for U can open a non-causal path. Draw the full DAG before deciding what to adjust for.

### Selection bias
If study inclusion depends on a collider, the sample itself introduces bias. Check whether your data source conditions on a descendant of both treatment and outcome.

### Reverse causation
For every proposed edge A → B, ask: "Could B actually cause A?" If plausible, this needs explicit justification with evidence.

### Overadjustment
Adjusting for a mediator on the causal path blocks the effect you're trying to estimate. Only adjust for confounders, not mediators.

## Provenance Discipline

Every `scic:causes` edge should have an associated claim:

```bash
# Add the causal edge
science-tool graph add edge "concept/smoking" "scic:causes" "concept/lung_cancer" --graph graph/causal

# Add a supporting claim with provenance
science-tool graph add claim "Smoking causes lung cancer via carcinogenic tar compounds" \
  --source "paper:doi_10.xxxx/yyyy" --confidence 0.95
```

Confidence scores reflect evidence strength:
- **0.9-1.0**: Well-established, multiple independent replications
- **0.7-0.9**: Strong evidence, few studies or single methodology
- **0.5-0.7**: Suggestive evidence, plausible mechanism
- **0.3-0.5**: Weak evidence, mainly theoretical
- **< 0.3**: Speculative, researcher's hypothesis

## Workflow

```
/science:build-dag  →  /science:critique-approach  →  inquiry export-pgmpy / export-chirho
   (construct)              (review)                        (export)
```

1. **Build**: `/science:build-dag` guides interactive construction of a causal DAG
2. **Critique**: `/science:critique-approach` reviews for confounders, identifiability, bias
3. **Export**: CLI commands generate scaffold code for analysis

## CLI Reference

### Creating a causal inquiry

```bash
# Initialize causal inquiry
science-tool inquiry init "my-dag" --type causal --label "Treatment Effect" \
  --target "hypothesis:h01"

# Add variables as boundary nodes
science-tool inquiry add-node "my-dag" "concept/treatment" --role BoundaryIn
science-tool inquiry add-node "my-dag" "concept/outcome" --role BoundaryOut
science-tool inquiry add-node "my-dag" "concept/confounder" --role BoundaryIn

# Set the estimand (treatment → outcome)
science-tool inquiry set-estimand "my-dag" \
  --treatment "concept/treatment" --outcome "concept/outcome"

# Add causal edges to graph/causal
science-tool graph add edge "concept/treatment" "scic:causes" "concept/outcome" --graph graph/causal
science-tool graph add edge "concept/confounder" "scic:causes" "concept/treatment" --graph graph/causal
science-tool graph add edge "concept/confounder" "scic:causes" "concept/outcome" --graph graph/causal
```

### Validation

```bash
science-tool inquiry validate "my-dag" --format json
```

Causal inquiries get additional checks:
- `causal_acyclicity` — no cycles in `scic:causes` edges among inquiry members

### Export

```bash
# pgmpy — graph-theoretic analysis (d-separation, adjustment sets)
science-tool inquiry export-pgmpy "my-dag" --output code/causal/dag.py

# ChiRho/Pyro — probabilistic causal inference (do-calculus, counterfactuals)
science-tool inquiry export-chirho "my-dag" --output code/causal/model.py
```

## When to Use pgmpy vs. ChiRho

| Question | Tool |
|----------|------|
| "Is the causal effect identifiable?" | pgmpy |
| "What should I adjust for?" | pgmpy |
| "What are the testable implications?" | pgmpy |
| "What is P(Y \| do(X=x))?" | ChiRho |
| "What would Y have been if X had been different?" | ChiRho |
| "How sensitive is the estimate to model misspecification?" | ChiRho |

**Use pgmpy first** for graph-theoretic analysis (no data needed). Then use **ChiRho** when you have data and want to estimate effects.

## Example: Simple 3-Variable DAG

Research question: "Does drug X improve recovery time, after accounting for disease severity?"

```
severity ──→ drug_choice ──→ recovery
    └────────────────────────→ recovery
```

- **Treatment**: `drug_choice` (observed)
- **Outcome**: `recovery` (observed)
- **Confounder**: `severity` (observed) — affects both drug choice and recovery

pgmpy will report: adjustment set = {severity}. Adjusting for severity identifies the causal effect of drug_choice on recovery.

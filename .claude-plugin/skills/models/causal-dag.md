---
name: causal-dag
description: Reference guide for causal DAG modeling within the science inquiry framework. Covers causal structure, common pitfalls, provenance discipline, and export to pgmpy/ChiRho. Loaded by sketch-model (causal mode) and critique-approach as background context.
---

# Causal DAG Modeling Reference

## When to Use Causal vs. General Inquiries

| Use case | Inquiry profile |
|----------|-------------|
| Exploring data flow, variables, computational steps | `investigation` |
| Modeling cause-and-effect relationships between variables | `causal` |
| Estimating treatment effects, testing interventions | `causal` |
| Identifying confounders and adjustment sets | `causal` |

An **investigation inquiry** uses `feedsInto`, `produces`, and similar
flow edges for data or computational structure. A **causal inquiry** uses
`causes` flow edges in the authored inquiry source; graph build materializes
them as `scic:causes` in the compiled inquiry graph. Reusable project-level
causal structure can also live in the generated `graph/causal` layer.

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
| `causes` / `scic:causes` | inquiry source / compiled graph | A causally influences B |
| `scic:confounds` | compiled graph / graph/causal | A confounds the relationship between two variables |

Causal inquiries are source-first. Edit `entities/patches/<slug>.md`, then run
`science graph build`; do not hand-edit `knowledge/graph.trig`.

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

Every causal edge should have an associated proposition when it has explicit
support. In the inquiry source, attach those propositions through `claim_refs`:

```yaml
flow_edges:
  - subject: "concept:smoking"
    predicate: causes
    object: "concept:lung_cancer"
    claim_refs:
      - "proposition:smoking-causes-lung-cancer"
```

Confidence scores reflect evidence strength:
- **0.9-1.0**: Well-established, multiple independent replications
- **0.7-0.9**: Strong evidence, few studies or single methodology
- **0.5-0.7**: Suggestive evidence, plausible mechanism
- **0.3-0.5**: Weak evidence, mainly theoretical
- **< 0.3**: Speculative, researcher's hypothesis

## Workflow

```
/science:sketch-model (causal mode)  →  /science:critique-approach  →  inquiry export-pgmpy / export-chirho
   (construct)              (review)                        (export)
```

1. **Build**: `/science:sketch-model` (causal mode) guides interactive construction of a causal DAG
2. **Critique**: `/science:critique-approach` reviews for confounders, identifiability, bias
3. **Export**: CLI commands generate scaffold code for analysis

## CLI Reference

### Creating a causal inquiry

```bash
# Initialize causal inquiry
science inquiry init "my-dag" \
  --label "Treatment Effect" \
  --target "hypothesis:h01" \
  --profile causal \
  --treatment "concept:treatment" \
  --outcome "concept:outcome"
```

Then edit `entities/patches/my-dag.md`:

```yaml
inquiry:
  profile: causal
  treatment: "concept:treatment"
  outcome: "concept:outcome"
  boundary_roles:
    - ref: "concept:treatment"
      role: BoundaryIn
    - ref: "concept:outcome"
      role: BoundaryOut
    - ref: "concept:confounder"
      role: BoundaryIn
  flow_edges:
    - subject: "concept:treatment"
      predicate: causes
      object: "concept:outcome"
      claim_refs: []
    - subject: "concept:confounder"
      predicate: causes
      object: "concept:treatment"
      claim_refs: []
    - subject: "concept:confounder"
      predicate: causes
      object: "concept:outcome"
      claim_refs: []
```

Build the compiled graph view:

```bash
science graph build
```

### Validation

```bash
science inquiry validate "my-dag" --format json
```

Causal inquiries get additional checks:
- `causal_acyclicity` — no cycles in `scic:causes` edges among inquiry members

### Export

```bash
# pgmpy — graph-theoretic analysis (d-separation, adjustment sets)
science inquiry export-pgmpy "my-dag" --output code/causal/dag.py

# ChiRho/Pyro — probabilistic causal inference (do-calculus, counterfactuals)
science inquiry export-chirho "my-dag" --output code/causal/model.py
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

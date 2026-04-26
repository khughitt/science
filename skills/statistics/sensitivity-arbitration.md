---
name: statistics-sensitivity-arbitration
description: Use when an analysis includes multiple robustness checks, alternate operationalisations, filters, covariate sets, priors, models, or negative controls whose results could change interpretation.
---

# Sensitivity Arbitration

Use when an analysis includes multiple robustness checks, alternate
operationalisations, filters, covariate sets, priors, models, or negative
controls whose results could change interpretation.

Sensitivity analyses are not a menu. If the rule for interpreting disagreement
is chosen after seeing outputs, the analysis becomes post-hoc story selection.

## Pre-Commit the Arbitration Rule

Before running verdict-bearing code, define:

1. **Primary analysis.** The one result that carries the main verdict if no
   pre-committed override fires.
2. **Mandatory sensitivities.** Checks that must run for the verdict to stand.
3. **Optional diagnostics.** Informative checks that do not change the verdict
   unless a named threshold is crossed.
4. **Override conditions.** Exact conditions that downgrade, reverse, or halt
   the verdict.
5. **Failure labels.** Names such as `batch_confounded`, `phase_confounded`,
   `underpowered`, `model_inadequate`, or `not_reproducible`.

## Sensitivity Types

| Type | Example | Typical arbitration |
|---|---|---|
| Measurement | alternate gene set, entropy metric, panel definition | disagreement downgrades measurement confidence |
| Model | Cox vs Weibull, Student-t vs Normal, prior sensitivity | diagnostics decide if primary model stands |
| Covariate | adjusted vs unadjusted, direct vs total effect | disagreement changes estimand label |
| Filter | low-depth exclusion, hypermutator exclusion | large shifts flag selection sensitivity |
| Negative control | shuffled labels, irrelevant gene set | positive control failure halts or downgrades |
| Replication | independent cohort or platform | failed replication limits scope |

## Arbitration Patterns

- **All-must-pass:** Use for high-stakes confirmatory claims. Any named failure
  downgrades or halts.
- **Primary plus veto:** Primary verdict stands unless a specific diagnostic
  veto fires.
- **Tiered verdicts:** Strong/supportive/fragile/null labels are assigned from
  a rule table.
- **Scope downgrade:** Primary result remains true only for a narrower cohort,
  platform, or operationalisation.
- **Estimand split:** Adjusted and unadjusted results answer different
  questions; report both instead of forcing agreement.

## Anti-Patterns

- Running many sensitivities and emphasizing whichever agrees with the desired
  story.
- Calling a sensitivity "exploratory" after it contradicts the primary.
- Averaging incompatible results without checking that they estimate the same
  quantity.
- Treating failed diagnostics as caveats while keeping an unchanged verdict.
- Adding new sensitivities after seeing results without labeling them post-hoc.

## Decision Table Template

```text
Primary verdict:
  strong_support if primary passes and all mandatory checks pass
  supportive if primary passes and only non-veto diagnostics fail
  fragile if primary passes but one measurement sensitivity disagrees
  null if primary effect is absent and power floor is adequate
  unresolved if power/model adequacy/data QA fail

Vetoes:
  batch_confounded if batch effect explains >= primary effect
  model_inadequate if PPC/residual diagnostics fail named thresholds
  non_replicating if independent replication has opposite sign with adequate power
```

Use project-specific labels, but keep the table explicit.

## Reporting

Include:

- primary analysis ID,
- complete sensitivity list,
- thresholds and vetoes,
- result of each sensitivity,
- final verdict label produced mechanically by the rule,
- post-hoc analyses clearly separated from pre-committed arbitration.

## Companion Skills

- [`power-floor-acknowledgement.md`](power-floor-acknowledgement.md) - determining whether a null sensitivity can arbitrate.
- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) - diagnostics for model adequacy and grouped data.
- [`compositional-data.md`](compositional-data.md) - sensitivity rules for denominator, zero-handling, and basis choices.

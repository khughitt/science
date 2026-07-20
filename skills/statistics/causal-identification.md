---
name: statistics-causal-identification
description: Use when estimating a causal effect from observational data — choosing an adjustment set, checking the backdoor criterion, distinguishing confounders from mediators/colliders, avoiding over-adjustment and M-bias, or deciding what to do when the effect is not identified.
archetype: analysis-discipline
sources: [baygent-skills, hernan-robins-whatif, pearl-primer, vanderweele-ding-evalue, rosenbaum-sensitivity]
---

# Causal Identification

Use before estimating any causal effect from observational data. Identification
is a question about the **DAG and the estimand**, decided before any model is fit;
a regression coefficient is not a causal effect until identification licenses it.

## DAG First

- **Draw the DAG.** The missing edges are the strongest assumptions you are
  making — they assert "no direct effect", "no common cause". Make them explicit.
- **State the estimand before choosing a design.** Total effect and direct effect
  need *different* adjustment sets; "the effect of X on Y" is ambiguous until you
  say which.

## Adjustment-Set Derivation

- Apply the **backdoor criterion**: block every backdoor path, adjusting for no
  descendant of the treatment.
- **Confounder vs mediator is about role, not timing.** A pre-treatment variable
  is *not* automatically safe to adjust for: conditioning on a collider (or a
  descendant of one) — **M-bias** — opens a path that was closed. The DAG, not the
  measurement order, is the authority.
- **Over-adjustment is a real failure, not caution.** Adjusting for a mediator
  removes part of the total effect you meant to estimate; adjusting for a collider
  induces bias. A *locked* adjustment set that quietly includes a mediator is a
  common, hard-to-catch error — verify the set against the DAG and the estimand,
  not against a covariate wishlist.

## When the Effect Is Not Point-Identified by Adjustment

Keep these four responses distinct — they are not interchangeable, and conflating
them overstates what the analysis can claim:

1. **Alternative identification strategy** (conditional on its own assumptions) —
   an instrument (IV), the front-door criterion. These can *point-identify* an
   effect, but often a **different estimand**: an IV under monotonicity identifies
   a LATE/CACE (the complier effect), not the ATE. **Re-state the estimand
   explicitly** when you switch strategy; never answer an ATE question with a LATE
   without saying so.
2. **Formal partial identification** — set-identifying bounds (Manski-style) that
   bracket the target effect under weaker assumptions.
3. **Sensitivity analysis** that leaves the effect **non-identified** but
   quantifies robustness to hidden bias — scoped to where each tool applies. The
   **E-value** describes how strong unmeasured confounding would have to be to
   explain away an *association*, on its compatible (ratio-scale) effect measures;
   it is not an identification device. **Rosenbaum bounds** apply to
   matched/stratified observational designs. Neither identifies the effect nor
   supplies causal-effect bounds — do not file them under partial identification.
4. **Fail-closed verdict** — when none of the above licenses a causal claim at the
   current operating point, say so plainly rather than reporting an adjusted
   association as if it were the effect.

## Executable Path

The Science toolkit derives adjustment sets and identifiability from the DAG
rather than leaving them to be argued by hand. Three distinct entry points, doing
three different things:

- **`science inquiry validate <slug>`** — runs the identifiability and
  adjustment-set checks **in-process**: it builds the DAG, checks whether the
  estimand is identifiable via the back-door criterion, and reports the valid
  adjustment sets (via `CausalInference.get_all_backdoor_adjustment_sets`). This is
  the command that actually computes and reports the verdict.
- **`science inquiry export-pgmpy <slug>`** — **generates a pgmpy script** that
  computes those same backdoor adjustment sets *when you run it*. Use it to inspect
  or extend the computation; the command emits the script, it does not run it. (Author
  the DAG first via `science inquiry` / `sketch-model` / `specify-model`.)
- **`/science:critique-approach`** — an *agentic* adversarial pass over the DAG for
  missing confounders, colliders, M-bias, and over-adjustment. It critiques the
  model's assumptions; it does not compute identifiability.
- **Caveat:** the in-process identifiability checks (`inquiry validate`) require
  `pgmpy`; if it is absent the check currently **skips rather than fails**, so
  confirm it is installed before trusting a clean result.

## Deeper Dive

For quasi-experimental designs (difference-in-differences, RDD, interrupted time
series, IV, synthetic control), design-specific refutation recipes, and the
calibrated causal-language ladder, see the upstream `causal-inference` skill by
Alexandre Andorra
([baygent-skills](https://github.com/Learning-Bayesian-Statistics/baygent-skills)).

## Companion Skills

- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) — confounder timing and collider adjustment inside survival/hierarchical models.
- [`bias-vs-variance-decomposition.md`](bias-vs-variance-decomposition.md) — confounding as a bias term that averaging does not remove.
- [`bayesian-workflow.md`](bayesian-workflow.md) — once identification licenses the estimand, the fitting/diagnostic discipline for estimating it.

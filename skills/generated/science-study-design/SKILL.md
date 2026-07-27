---
name: science-study-design
description: "Use when analysis rigor must be pre-committed or a numeric verdict certified / arbitrated — pre-registration, replicate / permutation / bootstrap / Monte-Carlo / downsampling count justification (over a round-number default), power-floor acknowledgement, bias-vs-variance decomposition, sensitivity arbitration, defensive instrumentation, estimator certification, or causal identification. Routes to the discipline leaves."
---

# Study-Design & Inference-Discipline Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a design commitment, certification, or arbitration governs how a result may be
claimed — before interpretation.

## Scope boundary

Covers pre-registration, replicate/power justification, estimator certification, sensitivity
arbitration, causal identification, and bias/variance reasoning. Excludes model fitting (see
the `science-statistics` skill).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `references/prereg-amendment-vs-fresh.md` | deciding amendment vs fresh pre-reg for a follow-up | no prior pre-reg exists |
| `references/prereg-defensive-instrumentation.md` | locking universe/candidate/tripwire/decision tables | exploratory-only work |
| `references/replicate-count-justification.md` | choosing R/B/m from a pilot rule | count already externally fixed |
| `references/power-floor-acknowledgement.md` | wording a null/weak result under a detectability floor | strong positive effect |
| `references/estimator-certification.md` | certifying a numeric fit against the E ≤ ρ·σ_null budget | no numeric verdict at stake |
| `references/sensitivity-arbitration.md` | applying a pre-committed sensitivity/veto table | no pre-committed table |
| `references/causal-identification.md` | certifying an adjustment set / identification | purely descriptive analysis |
| `references/bias-vs-variance-decomposition.md` | deciding whether more replicates vs bias correction is legitimate | no error-source ambiguity |

## Decision / compose order

Leaves are independent; several may apply to one analysis. Apply design/pre-commitment leaves before
data are seen, certification/arbitration leaves at verdict time.

## Parent & neighbors

- Parent index: the `science-command-preamble` skill's `references/methodology-index.md`
- Neighboring routers: the `science-statistics` skill

## Success test

A rigor commitment or verdict routes to the correct leaf with no methodology read from this router.

## Companion Skills

- the `science-command-preamble` skill's `references/methodology-index.md` — the skill index.

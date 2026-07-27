---
name: study-design
description: Use when analysis rigor must be pre-committed or a numeric verdict certified / arbitrated — pre-registration, replicate / permutation / bootstrap / Monte-Carlo / downsampling count justification (over a round-number default), power-floor acknowledgement, bias-vs-variance decomposition, sensitivity arbitration, defensive instrumentation, estimator certification, or causal identification. Routes to the discipline leaves.
provenance: internal
---

# Study-Design & Inference-Discipline Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a design commitment, certification, or arbitration governs how a result may be
claimed — before interpretation.

## Scope boundary

Covers pre-registration, replicate/power justification, estimator certification, sensitivity
arbitration, causal identification, and bias/variance reasoning. Excludes model fitting (see
`../statistics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `prereg-amendment-vs-fresh.md` | deciding amendment vs fresh pre-reg for a follow-up | no prior pre-reg exists |
| `prereg-defensive-instrumentation.md` | locking universe/candidate/tripwire/decision tables | exploratory-only work |
| `replicate-count-justification.md` | choosing R/B/m from a pilot rule | count already externally fixed |
| `power-floor-acknowledgement.md` | wording a null/weak result under a detectability floor | strong positive effect |
| `estimator-certification.md` | certifying a numeric fit against the E ≤ ρ·σ_null budget | no numeric verdict at stake |
| `cost-gate-certification.md` | a schedule / budget / feasibility gate decides affordability | no cost or schedule decision at stake |
| `sensitivity-arbitration.md` | applying a pre-committed sensitivity/veto table | no pre-committed table |
| `causal-identification.md` | certifying an adjustment set / identification | purely descriptive analysis |
| `bias-vs-variance-decomposition.md` | deciding whether more replicates vs bias correction is legitimate | no error-source ambiguity |

## Decision / compose order

Leaves are independent; several may apply to one analysis. Apply design/pre-commitment leaves before
data are seen, certification/arbitration leaves at verdict time.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../statistics/SKILL.md`

## Success test

A rigor commitment or verdict routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.

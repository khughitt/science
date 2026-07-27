---
name: study-design-cost-gate-certification
description: Use when a sampling schedule, compute budget, or feasibility gate decides whether an analysis is affordable — especially when the benchmark, pilot, or schedule was measured at a different batch size, concurrency, substrate, or run phase than the one that will execute.
archetype: analysis-discipline
provenance: internal
---

# Cost-Gate Certification

A cost gate must be evidence about the execution it authorizes. A measurement
taken at a different execution geometry is not evidence about that geometry.
The mismatch has **no fixed direction**: a compile-dominated pilot overstates
per-unit cost, while a batched benchmark charged to a sequential workload
understates it. The reliably optimistic bias comes from **favourable probe
selection**, not from the mismatch itself.

## Freeze the Geometry Before Measuring (`fb-2026-07-13-001`)

Define the batch size, concurrency, substrate, work size, run phase, and
threading geometry from the budget being decided *before* measuring. Choosing
the geometry after measuring is circular: the measurement selects its own
authorizing conditions, and that circularity always resolves favourably.

## The Monotonicity Tell (`fb-2026-07-13-001`)

Throughput must be monotone in the work parameter. If `N=64` measures faster
than `N=32`, the measurement tracks per-call dispatch overhead rather than the
computation. Do not use it to authorize a work-sized schedule until the probe
measures the computation at the geometry that will run.

## Near-Worst, One Geometry (`fb-2026-07-13-002`)

Use p90 over `R ≥ 5` repeats at the single geometry that executes. Never use
the best result across a sweep: a cost gate exists to **REFUSE** work, so
selecting the favourable configuration is the selection effect that makes it
unable to refuse.

## Steady State and Target Concurrency (`fb-2026-07-12-014`)

Warmup adapts to parameters the run does not ultimately use, and JIT/compile
can mask contention. Pin intra-op threads (`XLA_FLAGS=intra_op_parallelism_threads=1`,
`OMP_NUM_THREADS=1`) and treat throughput at target concurrency as an empirical
result, never a projection. The mechanism is **compile amortisation**, not
estimator choice.

## A Schedule's Calibration Domain (`fb-2026-07-25-009`)

A burn-in/thinning schedule validated on one substrate is a hypothesis about a
different substrate until it is probed. Run a cheap single-chain ACT probe up
front to size the schedule for the substrate that will execute it.

## Profile Before Ordering a Remedy Ladder (`fb-2026-07-25-010`)

A remedy targeting a negligible cost fraction cannot help regardless of its
theoretical merit. Profile first, order remedy rungs by the measured bottleneck,
and give the decision-maker the cost split together with the options.

## What Works (`fb-2026-07-25-011`)

Verdict-blind viability and mixing gates evaluated before observed-data exposure
make repeated sampler failures cost nothing epistemically. Record this as the
positive pattern, not only as a list of failures.

## Companion Skills

- [`estimator-certification.md`](estimator-certification.md) — certifies the estimator; cost is the axis it does not cover.
- [`replicate-count-justification.md`](replicate-count-justification.md) — justifies the repeat count used to establish p90.

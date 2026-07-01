# Bio Meta Scaffold Brief

This brief is the durable `t058` output for the proposed `~/d/bio/meta`
project. It replaces the active role of
`doc/plans/historical/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md`.

## Status

- Scaffold status: not scaffolded
- Decision status: valid candidate, pending `t057` topology pilot
- Owner before scaffold: `~/d/science/meta`
- Candidate project path: `~/d/bio/meta`
- Related topology note: `core/adaptive-project-topology.md`

`~/d/bio/meta` is a candidate Science project for reusable biological modeling
primitives. It should not be scaffolded from this brief alone. The remaining
gate is the topology pilot: compare the candidate against concrete topology
harms and decide whether promotion reduces misrouting or merely adds another
world-model home.

## Research Question

Candidate initial question:

> What biological model best represents organisms as nested, multiscale
> dynamical systems under partial observation?

This is a framing and methodology question, not a narrow empirical question.
If scaffolded, `~/d/bio/meta` should be tagged as a meta-role synthesis project
from day one. Its job is to define reusable modeling primitives and organize
evidence that constrains those primitives, not to produce primary biological
findings.

## Boundary With Health Meta

The load-bearing boundary is:

- `~/d/bio/meta` owns the **substrate model**: multiscale biological systems,
  state spaces, time and space, reachability, path dependence, control regimes,
  perturbation response, observability, sampling, and resolution.
- `~/d/health/meta` owns the **applied health lens**: homeostasis, disease,
  intervention, health-state axes, family coordination, and decisions about
  which child health projects should exist.

Cancer, cycles, pre-cancer, and health-family projects may link to both layers
for different reasons. They use `bio/meta` for general biological modeling
primitives and `health/meta` when the question is specifically about health,
disease, homeostatic failure, intervention, or health-project coordination.

If this boundary fails during the pilot, `bio/meta` should remain unscaffolded
and the biological substrate material should stay as a theme under the existing
health/meta or Science/meta surfaces until the boundary is sharper.

## Initial Topic Set

Candidate initial topics:

- nested biological systems model;
- state-space reachability and path dependence;
- sampling, resolution, and observability;
- perturbation response as health observable;
- timebase-aware causal inference;
- control regimes, feedback, cycles, and attractors.

These are starting topics, not child projects.

## Projects That Would Link To Bio Meta

If scaffolded, the initial link set should include:

- `~/d/health/meta` for the applied health lens and family coordination;
- cycles projects for timebase, feedback, periodicity, and control-regime
  questions;
- cancer-evolution for state trajectories, selection, path dependence, and
  perturbation response;
- pre-cancer for state-space transitions, observability, and early detection;
- pan-disease where shared biological axes or disease-family federation need a
  substrate model.

The link direction matters: downstream projects should cite `bio/meta` for
reusable biological primitives, not delegate their domain-specific questions to
it.

## Minimum Scaffold Gate

Before creating `~/d/bio/meta`, the topology pilot should confirm:

- at least one concrete topology harm would be reduced by a separate
  biological substrate project;
- the health/meta boundary can be stated without overlapping ownership;
- the candidate has at least one active question, one candidate hypothesis or
  proposition bundle, and a small task set;
- the initial links to health, cycles, cancer-evolution, pre-cancer, and
  pan-disease are provenance-preserving;
- the project will not become a dumping ground for every interesting biology
  theme.

## Candidate Initial Tasks

If the scaffold gate passes, create a minimal task set:

- reserve the initial `bio/meta` question above;
- draft one organizing hypothesis about nested biological systems under partial
  observation;
- inventory existing linked material from health/meta, cycles, cancer-evolution,
  pre-cancer, and pan-disease;
- write the boundary decision into `bio/meta/core/decisions.md`;
- create backlink tasks in affected projects rather than moving their existing
  histories.

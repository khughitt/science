---
id: t100
project: ''
title: DAG workbench generation conflates bundle routing with core membership
type: ''
aspects:
- framework-design
priority: P2
status: proposed
blocked_by: []
related: []
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-07-17'
completed: null
---

A bundle hypothesis composes its verdict by conjunctive weakest-link over its CORE members
([bundle_belief.py](../../../science/src/science_tool/graph/bundle_belief.py):75). A bare
`discusses` ref means CORE ([epistemic-model.md](../../../docs/user-guide/epistemic-model.md):434),
while workbench `focal_hypothesis` currently handles routing by emitting that bare membership
([workbench.py](../../../science/src/science_tool/dag/workbench.py):221). Generation therefore
silently makes every routed DAG relation-edge a load-bearing member.

MM30 t900 exposed why neither universal role is correct. Its two flagship hypotheses had 41
and 50 core members. The audit found a mixed population: 18 generated relation-edges (6 H1,
12 H2) were confirmed scaffold — empty-bodied and without evidence-lines — while most other
generated `concept-*` / `protein-*` edges had targeted evidence and were intended to remain
load-bearing. The unsupported scaffold alone was enough to hold the weakest-link conjunction
at speculative. MM30 manually reclassified only those 18 confirmed-scaffold edges to
`role: background`; classifying by generated naming or assigning every generated edge the same
role would have been wrong.

Proposed direction: keep the global meaning of bare `discusses` unchanged, but make the DAG
generation path assign membership roles explicitly instead of deriving epistemic role from
`focal_hypothesis` routing. Evaluate either:

1. a file-/frame-level focal membership declaration carrying both frame and default role, with
   explicit per-row role overrides for mixed patches; or
2. a required explicit role on every migrated/generated row, failing early when generation can
   resolve a frame but not its membership role.

Do not infer role from identifier prefixes, body emptiness, or current evidence count: those are
useful audit signals, not stable semantics. Generated proposition output should serialize an
explicit `{frame, role}` membership. Acceptance coverage must include a mixed patch with core and
background rows, bridge rows routed to multiple hypotheses, and a failure case for unresolved
generation-time role. See MM30 t900/t903 for the concrete audit, manual correction, and remaining
evidence-wiring work.

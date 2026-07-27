---
id: t068
project: ''
title: Cross-project entity reference syntax (single addressable world)
type: ''
aspects:
- software-development
priority: P1
status: proposed
blocked_by: []
related:
- hypothesis:0007-working-model
- hypothesis:0006-adaptive-project-topology-improves-research-fit
- question:0014-adaptive-project-topology
- task:t043
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-05-31'
completed: null
---

Design a VALIDATING cross-project entity reference syntax. Surfaced by fb-2026-05-31-012 (writing h00): a foreign 'type:id' ref resolves against the local repo so it reads as broken, and the refs-checker even resolves the bare token locally — forcing honest foreign mentions into untyped prose (the interim h00 policy), which defeats validation, graph linkage, and cross-boundary freshness.

K.H. framing (load-bearing): all projects live in ONE WORLD; a project is sub-structure, itself decomposable into hypothesis/domain neighborhoods (h00 patches). A cross-project ref is a same-world ref crossing a sub-structure boundary, not a foreign ref needing a bridge — the resolver should treat project scope as a grouping level in one addressable space.

This is the single primitive the recurring 'cross-project address syntax' open item in t015 (freshness propagation), t018 (typed blockers), and t043 (cross-project blockers spec) each separately defer; land it once. Design questions to settle: address grammar (project-qualified id e.g. pan-disease::task:t071 vs URN), resolver source of truth (live sibling-repo sweep vs federated graph snapshot), behavior when the target project is not locally available, validation severity (resolvable-vs-unresolvable vs warn-on-stale), and how refs-checker stops greedily resolving bare local tokens. Aligns h00 (multi-scale patch<=project<=collection), h06/q14 (adaptive topology), and the project-peers group (t043-t052).

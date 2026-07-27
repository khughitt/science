---
id: t018
project: ''
title: Cross-project typed blockers
type: ''
aspects:
- software-development
- federation
priority: P3
status: proposed
blocked_by: []
related: []
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Extend typed task blockers from local entity refs to cross-project refs: a task in project A blocked by an entity in project B, including parent/child/sibling project shapes.

Open design questions: cross-project address syntax, resolver source (live entity-store sweep vs. federated graph snapshot), stale-graph behavior, audit semantics, and how `validate_blocker_refs` / `ReadinessResolver` grow a project-scope parameter without weakening the current strict local validation.

Surfaced by: typed-entity-blockers trajectory item 1.

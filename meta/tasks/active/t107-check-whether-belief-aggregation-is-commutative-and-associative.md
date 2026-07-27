---
id: t107
project: ''
title: Check whether belief aggregation is commutative and associative
type: ''
aspects: []
priority: P2
status: proposed
blocked_by: []
related:
- question:0044-is-cross-project-belief-merge-a-join-semilattice
parent: ''
group: toolkit-evaluation
artifacts: []
findings: []
created: '2026-07-25'
completed: null
---

Answers half of question:0044 by inspection rather than study: read the aggregation implementation and test whether merging evidence sets in different orders yields identical belief. If it does not, cross-project composition can produce divergent belief states. Cheapest high-value item from explore-2026-07-25.

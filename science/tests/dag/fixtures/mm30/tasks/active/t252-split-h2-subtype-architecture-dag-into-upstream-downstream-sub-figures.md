---
id: t252
project: ''
title: Split h2-subtype-architecture DAG into upstream + downstream sub-figures; expose
  lineage-conditioned branches per proposition p13
type: ''
aspects:
- causal-modeling
priority: P2
status: proposed
blocked_by: []
related:
- discussion:2026-04-19-dag-iteration-and-refinement
- inquiry:h2-subtype-architecture
parent: ''
group: dag-refresh
artifacts: []
findings: []
created: '2026-04-20'
completed: null
---

Per discussion:2026-04-19-dag-iteration-and-refinement Q2/Q3. 43 edges in a single rankdir=TB graph is too dense. Share node identifiers across the split. Make the three lineage-conditioned branches first-class (gain(1q) PHF19/IFN-silencing + HD CTA/chrXp + t(11;14) APOBEC3B/BCL2) per the p13 reframing. Candidate: keep `h2-subtype-architecture.dot` as upstream half; add `h2-subtype-outcomes.dot` for downstream half.

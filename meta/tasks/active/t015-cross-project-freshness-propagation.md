---
id: t015
project: ''
title: Cross-project freshness propagation
type: ''
aspects:
- software-development
- federation
- framework-design
priority: P3
status: proposed
blocked_by: []
related:
- hypothesis:0001-stochastic-revisiting
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Extend epistemic freshness beyond a single project: a paper, dataset, workflow-run, observation, proposition, or other epistemic upstream added in a parent/child/sibling project should be able to mark downstream hypotheses, questions, propositions, inquiries, and interpretations as `needs-review` across project boundaries.

This is distinct from current federation graph assembly/status. The missing design pieces are cross-project entity address syntax, resolver source of truth (live child sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics when a downstream project is not locally available.

Surfaced by: EDG design trajectory item 2.
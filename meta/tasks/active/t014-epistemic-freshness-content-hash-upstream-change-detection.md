---
id: t014
project: ''
title: 'Epistemic freshness: content-hash upstream change detection'
type: ''
aspects:
- software-development
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

Phase 1 freshness uses frontmatter `updated` / `created` dates as the upstream change marker. `docs/plans/historical/2026-05-03-epistemic-dependency-graph-design.md` explicitly deferred content-hash-based change detection to a later phase. Add a graph/materialization path that can detect upstream content changes even when authors forget to bump `updated:`, without replacing the current date-based convention prematurely.

Scope to design first: which authored fields participate in the hash, whether hashes live in the graph only or in a sidecar manifest, how to avoid noise from formatting-only edits, and how this interacts with existing managed-artifact hash utilities.

Surfaced by: EDG design § Decisions, item 5.
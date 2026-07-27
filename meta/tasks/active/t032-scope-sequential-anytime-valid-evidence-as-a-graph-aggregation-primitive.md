---
id: t032
project: ''
title: Scope sequential / anytime-valid evidence as a graph aggregation primitive
type: ''
aspects:
- research
- framework-design
- hypothesis-testing
priority: P2
status: proposed
blocked_by: []
related:
- task:t028
- question:0007-sequential-anytime-valid-evidence
- hypothesis:0005-sequential-evidence-improves-attention
- hypothesis:0001-stochastic-revisiting
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
parent: ''
group: sequential-evidence
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Resolve t028's anytime-valid reading lead into either a topic note + simulator extension or a deferred-with-reason record.

Steps:
- ingest the e-value / test-martingale / confidence-sequence references queued in `[t028]`;
- write a topic note `entities/topics/sequential-evidence.md` linking these methods to H01 / H03 attention and H02 payload state;
- audit current and likely-future project graph state for the realized prevalence of optional stopping and unbounded revisiting;
- propose a sequential-evidence extension to the H01 simulator: propositions receive evidence over time, attention policies compare fixed-N posterior, BMA-style, and anytime-valid evidence levels;
- decide whether H05 graduates to an active simulation track or stays speculative pending stronger upstream evidence.
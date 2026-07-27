---
id: t083
project: ''
title: Run the H02 rich-vs-flat calibration bakeoff (milestone)
type: ''
aspects:
- hypothesis-testing
- software-development
- computational-analysis
priority: P1
status: proposed
blocked_by: []
related:
- task:t076
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0002-evidence-payload-schema
- question:0017-benchmark-grounding-metrics
parent: task:t076
group: benchmark-grounding
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

The milestone that converts H02 from a bet into a measurement: on a fixed benchmark set, compare rich-payload aggregation against a flat/scalar baseline scored on held-out outcomes. hypothesis:0002 itself says support is literature/architectural not benchmark-based; this closes that. Reusable pieces exist (h01_simulator scoring, t034_validator / evidence_payload.py schema validators) but have never been combined into a calibration comparison. Depends on t076 grounding + calibration metric.

---
id: t082
project: ''
title: 'Calibration-over-time metric: score belief against benchmark outcomes (Brier/ECE)'
type: ''
aspects:
- software-development
- hypothesis-testing
- computational-analysis
priority: P2
status: proposed
blocked_by: []
related:
- task:t076
- question:0017-benchmark-grounding-metrics
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
parent: task:t076
group: benchmark-grounding
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Generalize the h01_simulator Brier/ground-truth scoring loop (meta/src/h01_simulator) to score belief snapshots against benchmark outcomes with Brier and ECE, producing a standing calibration-over-time metric for the whole representation, not just per-proposition belief.

---
id: t081
project: ''
title: Benchmark/dataset portfolio as first-class grounding with leakage provenance
type: ''
aspects:
- software-development
- computational-analysis
priority: P1
status: proposed
blocked_by: []
related:
- task:t076
- question:0017-benchmark-grounding-metrics
parent: task:t076
group: benchmark-grounding
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Register a diverse, relevant benchmark/dataset portfolio as first-class external grounding. Treat benchmark-used-for-grounding as a provenance fact with an explicit tune/eval split (benchmarks used to tune the belief policy disjoint from those used to evaluate it) and held-out rotation so no single benchmark becomes a durable target. Leakage = shared source/dataset/paper between an evidence line and its benchmark ground truth, made mechanically detectable. Builds on the read-only science benchmark tests command and the catalog-benchmarks skill, which today do not author outcomes or score calibration.
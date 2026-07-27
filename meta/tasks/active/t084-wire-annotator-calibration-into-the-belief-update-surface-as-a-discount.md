---
id: t084
project: ''
title: Wire annotator calibration into the belief-update surface as a discount
type: ''
aspects:
- software-development
- hypothesis-testing
priority: P2
status: proposed
blocked_by: []
related:
- task:t033
- question:0008-llm-agents-as-fallible-sources
- question:0017-benchmark-grounding-metrics
- task:t076
parent: ''
group: agent-source-modeling
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Phase-2 follow-up. Today the ordinal magnitude consumes authored strength/independence/evidence_role at face value regardless of whether a calibrated human or an agent assigned them (only expert_judgment has a confidence gate/ceiling). Discount agent-assigned fields by an estimated per-annotator calibration profile (human-expert vs specific agent+prompt+model-version). Profiles are estimable only once external ground truth exists, so this depends on the benchmark grounding group (t076/question:0017). Extends question:0008 / task:t033, which represent agent fallibility but do not wire it into belief.

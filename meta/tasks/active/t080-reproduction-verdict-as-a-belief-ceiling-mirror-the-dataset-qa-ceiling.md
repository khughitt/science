---
id: t080
project: ''
title: Reproduction verdict as a belief ceiling (mirror the dataset-QA ceiling)
type: ''
aspects:
- software-development
- hypothesis-testing
priority: P2
status: proposed
blocked_by: []
related:
- task:t075
- question:0016-reproducibility-validation
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
parent: task:t075
group: reproducibility-validation
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Turn the reproduction verdict into a belief cap, mirroring the qa_failed_dataset ceiling: empirical support resting on a failed or unverified reproduction is capped unless independently-reproduced support stands alone. New explicit belief-policy version; phase warn-only then gate. This is the run-level instance of the QA-verdict-as-belief-input pattern.

### Notes

- 2026-07-08 (K.H. caution): the eventual policy must preserve a distinction between "not yet checked" (`unverified`) and "checked and failed" (`failed`) — they are directionally similar but must not collapse to the same cap. Warn-only rollout first is the right posture before any eligibility gate.
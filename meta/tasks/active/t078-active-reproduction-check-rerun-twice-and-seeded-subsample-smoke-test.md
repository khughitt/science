---
id: t078
project: ''
title: 'Active reproduction check: rerun-twice and seeded-subsample smoke test with
  a verdict'
type: ''
aspects:
- software-development
- computational-analysis
priority: P2
status: proposed
blocked_by: []
related:
- task:t075
- question:0016-reproducibility-validation
parent: task:t075
group: reproducibility-validation
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Dynamic tier: re-execute a workflow and compare outputs; for computationally expensive workflows use a seeded subsample as a reproduction smoke test. Emit a verdict token (unverified, self-consistent, independently-reproduced, failed) tracked at run/dataset/evidence level. Open design points: same-result tolerance (bitwise vs within-tolerance numeric) and how to bound subsample cost while preserving indicativeness.

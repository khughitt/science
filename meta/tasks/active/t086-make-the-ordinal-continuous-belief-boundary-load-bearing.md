---
id: t086
project: ''
title: Make the ordinal-continuous belief boundary load-bearing
type: ''
aspects:
- software-development
priority: P2
status: proposed
blocked_by: []
related:
- question:0018-ordinal-continuous-belief-boundary
- question:0009-mcda-bayesian-interoperability
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
parent: ''
group: belief-representation
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Phase-2 follow-up. Keep the ordinal magnitude as durable, policy-versioned evidence state and treat the continuous value as a calibrated decision/attention projection. Locate every ordinal-to-continuous conversion; define a single documented conversion point where the projection carries its own config identity (as the log-odds scalar already does) so consumers cannot mistake it for the ordinal truth. Tie projection calibration to benchmark outcomes (question:0017). Relates meta D-003 (continuous operational beliefs) and question:0009.

---
id: t085
project: ''
title: Standing inert-field audit and norm-to-check conversion
type: ''
aspects:
- software-development
priority: P2
status: proposed
blocked_by: []
related:
- task:t030
- task:t021
parent: ''
group: schema-hygiene
artifacts: []
findings: []
created: '2026-07-08'
completed: null
---

Phase-2 follow-up. Audit whether each optional schema field is actually consumed by a validator, belief policy, query, or dashboard; flag inert fields that invite performative filling. Separately, convert do-not-do-X authoring norms (do not relabel weak as strong, do not fake independence groups) into checks, starting as visibility warnings unless the field affects belief eligibility. Extends the t030 authoring-cost audit and the t021 core/extension discipline.
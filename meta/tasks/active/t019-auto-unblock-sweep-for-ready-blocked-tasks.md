---
id: t019
project: ''
title: Auto-unblock sweep for ready blocked tasks
type: ''
aspects:
- software-development
- task-management
priority: P3
status: proposed
blocked_by: []
related: []
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Add a command that flips `status: blocked` to `status: active` for tasks whose typed blockers all report `ready`. Current behavior only nudges in display output (`all ready — run 'tasks unblock <id>'`), which was the right manual-first implementation.

Design before implementation: dry-run by default, explicit `--apply`, clear audit output, no action on unresolved/forced blockers, and a policy for preserving notes about why the task had been blocked. This should land only after the manual readiness workflow has proven stable enough to automate.

Surfaced by: typed-entity-blockers trajectory item 2.
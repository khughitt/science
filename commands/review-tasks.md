---
description: Review and reprioritize research tasks using explicit rationale tied to impact, uncertainty reduction, and dependencies.
---

# Review Tasks

Review and reprioritize `RESEARCH_PLAN.md`.
Use `$ARGUMENTS` as optional scope filters, for example: `next 2 weeks`, `only P1`, `modeling-related`, `dataset-related`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `RESEARCH_PLAN.md`.
2. Read recent changes in:
   - `doc/topics/`
   - `specs/hypotheses/`
   - `doc/questions/`
   - `doc/papers/`
3. Read `doc/10-research-gaps.md` if present.

## Prioritization Method

Apply the expand/compress loop:

1. Expand: ensure candidate tasks cover key open areas.
2. Compress: select a focused set of near-term priorities.

Score tasks qualitatively on:

- Expected impact on research question.
- Uncertainty reduction potential.
- Feasibility (time/data/tooling).
- Dependency order.

## Writing Output

Update `RESEARCH_PLAN.md` with:

1. `## Current Priorities`
2. `## Priority Rationale`
3. `## Deferred / Parked Tasks`
4. `## Blockers and Dependencies`
5. `## Next Review Trigger`

Keep plan compact and decisive.
Prefer fewer, well-justified active tasks over long unmanaged queues.

## After Review

1. Ensure each active priority has explicit rationale and a next action.
2. Cross-link relevant open questions/hypotheses where needed.
3. Commit: `git add RESEARCH_PLAN.md && git commit -m "plan: reprioritize research tasks"`

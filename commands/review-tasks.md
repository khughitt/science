---
description: Review and reprioritize research tasks using explicit rationale tied to impact, uncertainty reduction, and dependencies.
---

# Review Tasks

Review and reprioritize `RESEARCH_PLAN.md`.
Use `$ARGUMENTS` as optional scope filters, for example: `next 2 weeks`, `only P1`, `modeling-related`, `dataset-related`.

## Before Review

1. Read `prompts/roles/research-assistant.md` if present; otherwise read `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/research-assistant.md`.
2. Read `RESEARCH_PLAN.md`.
3. Read `specs/research-question.md`.
4. Read recent changes in:
   - `doc/background/`
   - `doc/07-hypotheses.md`
   - `doc/08-open-questions.md`
   - `papers/summaries/`
5. Read `doc/10-research-gaps.md` if present.

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
3. Commit: `git add RESEARCH_PLAN.md doc/08-open-questions.md && git commit -m "plan: reprioritize research tasks"`

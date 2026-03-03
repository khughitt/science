---
description: Review current project research coverage, identify missing areas, and generate prioritized gap-closing tasks.
---

# Research Gaps

Analyze project coverage and identify high-value research gaps.
Use `$ARGUMENTS` as optional scope, for example: `background only`, `hypotheses only`, `causal assumptions`, or a specific topic/domain.

## Before Analysis

1. Read `prompts/roles/research-assistant.md` if present; otherwise read `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/research-assistant.md`.
2. Read the `research-methodology` skill.
3. Read the `scientific-writing` skill.
4. Read `specs/research-question.md` and `specs/scope-boundaries.md`.
5. Read current materials:
   - `doc/background/`
   - `doc/07-hypotheses.md`
   - `doc/08-open-questions.md`
   - `papers/summaries/`
   - `RESEARCH_PLAN.md`

## Gap Analysis Method

Perform coverage analysis across:

1. Concepts/topics: what core topics are missing or too shallow?
2. Evidence quality: what claims rely on weak/old/uncorroborated support?
3. Contradictions: where do findings conflict without explicit resolution?
4. Testability: which hypotheses lack falsifiability criteria or clear next tests?
5. Data feasibility: where are key variables/questions blocked by missing datasets?

Focus on decision impact, not document volume.

## Writing Output

Write to `doc/10-research-gaps.md` with these sections:

1. `## Scope Reviewed`
2. `## Coverage Map (Strong / Partial / Missing)`
3. `## High-Impact Gaps`
4. `## Recommended Next Tasks (Prioritized)`
5. `## Rationale and Evidence Links`

For each recommended task, include:

- Priority: `P1`, `P2`, or `P3`
- Why now: expected impact and uncertainty reduction
- Dependencies
- Suggested command/capability (`research_topic`, `research_paper`, `discuss`, etc.)

## After Writing

1. Update `RESEARCH_PLAN.md` with prioritized tasks and rationale.
2. Cross-link relevant items in `doc/08-open-questions.md`.
3. Commit: `git add -A && git commit -m "plan: research gap analysis and priorities"`

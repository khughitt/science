---
description: Structured critical discussion for a hypothesis, question, topic, or approach. Supports optional double-blind mode to reduce anchoring bias.
---

# Discuss

Run a structured discussion on `$ARGUMENTS`.
If no argument is provided, sample a discussion focus from `doc/08-open-questions.md`, `specs/hypotheses/`, or recent priorities in `RESEARCH_PLAN.md`.

## Before Discussion

1. Read `prompts/roles/discussant.md` if present; otherwise read `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/discussant.md`.
2. Read the `research-methodology` skill.
3. Read `specs/research-question.md`.
4. Read `templates/discussion.md` for required output structure.
5. Read relevant context tied to the chosen focus:
   - `doc/background/`
   - `specs/hypotheses/`
   - `doc/08-open-questions.md`
   - `RESEARCH_PLAN.md`

## Discussion Modes

### Standard mode

1. Clarify the focal claim/question.
2. Surface strengths, weaknesses, assumptions, and alternatives.
3. Identify confounders, failure modes, and missing evidence.
4. Propose concrete follow-up tasks.

### Double-blind mode (optional)

Use when the user asks for independent reasoning before synthesis.

1. Agree on focus.
2. Agent writes its draft analysis to file before seeing user draft.
3. User writes and shares independent draft.
4. Agent publishes a combined synthesis that compares, challenges, and refines both perspectives.

## Writing Output

Save to `doc/discussions/YYYY-MM-DD-<slug>.md` with sections:

1. `## Focus`
2. `## Current Position`
3. `## Critical Analysis`
4. `## Alternative Explanations / Confounders`
5. `## Evidence Needed`
6. `## Prioritized Follow-Ups`
7. `## Synthesis` (include side-by-side summary in double-blind mode)

## After Discussion

1. Add/adjust entries in `doc/08-open-questions.md`.
2. Update `RESEARCH_PLAN.md` with prioritized follow-up tasks and rationale.
3. If discussion changes hypothesis wording, update relevant file in `specs/hypotheses/`.
4. Commit: `git add -A && git commit -m "doc: discuss <slug> and update priorities"`

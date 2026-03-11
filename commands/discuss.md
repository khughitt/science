---
description: Structured critical discussion for a hypothesis, question, topic, or approach. Supports optional double-blind mode to reduce anchoring bias.
---

# Discuss

Run a structured discussion on `$ARGUMENTS`.
If no argument is provided, sample a discussion focus from `doc/questions/`, `specs/hypotheses/`, or active tasks in `tasks/active.md`.

## Setup

Follow `references/command-preamble.md` (role: `discussant`).

Additionally:
1. Read `templates/discussion.md`.
2. Read relevant context tied to the chosen focus:
   - `doc/topics/`
   - `specs/hypotheses/`
   - `doc/questions/`
   - `tasks/active.md`

## Discussion Modes

### Standard mode

1. Clarify the focal claim/question.
2. Surface strengths, weaknesses, assumptions, and alternatives.
3. Identify confounders, failure modes, and missing evidence.
4. Propose concrete follow-up tasks.

If loaded aspects contribute additional discussion guidance (e.g., causal reasoning checks from `causal-modeling`), incorporate that guidance into the critical analysis.

### Double-blind mode (optional)

Use when the user asks for independent reasoning before synthesis.

1. Agree on focus.
2. Agent writes its draft analysis to file before seeing user draft.
3. User writes and shares independent draft.
4. Agent publishes a combined synthesis that compares, challenges, and refines both perspectives.

## Writing Output

Save to `doc/discussions/YYYY-MM-DD-<slug>.md`.

Populate frontmatter fields:
- `id`: `"discussion:YYYY-MM-DD-<slug>"`
- `related`: IDs of the focus entity and any hypotheses, questions, or topics discussed
- `source_refs`: IDs of papers cited during the discussion
- `focus_type` and `focus_ref`: from the user's input or inferred from context
- `mode`: `"standard"` or `"double-blind"` based on the user's choice

Sections:

1. `## Focus`
2. `## Current Position`
3. `## Critical Analysis` (includes alternative explanations and confounders — see template)
4. `## Evidence Needed`
5. `## Prioritized Follow-Ups`
6. `## Synthesis` (include side-by-side summary in double-blind mode)

## After Discussion

1. Add/adjust entries in `doc/questions/` using `templates/question.md`.
2. Offer to create follow-up tasks via `science-tool tasks add` with appropriate priority and related entities.
3. If discussion changes hypothesis wording, update relevant file in `specs/hypotheses/`.
4. Commit: `git add -A && git commit -m "doc: discuss <slug> and update priorities"`

## Process Reflection

Reflect on the **discussion template** sections and the **standard vs double-blind mode** guidance.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — discuss

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("the Critical Analysis section felt too broad when covering both methodological and empirical weaknesses" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

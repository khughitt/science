---
description: Structured critical discussion for a hypothesis, question, topic, or approach. Supports optional double-blind mode to reduce anchoring bias.
---

# Discuss

Run a structured discussion on `$ARGUMENTS`.
If no argument is provided, sample a discussion focus from `doc/questions/`, `specs/hypotheses/`, or active tasks in `tasks/active.md`.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `discussant`).

Additionally:
1. Read `.ai/templates/discussion.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/discussion.md`.
2. Read relevant context tied to the chosen focus:
   - `doc/topics/`
   - `specs/hypotheses/`
   - `doc/questions/`
   - `tasks/active.md`

## Discussion Modes

### Standard mode

1. Clarify the focal claim/question.
2. Surface strengths, weaknesses, assumptions, alternatives, confounders, and failure modes in a unified critical analysis. Do NOT create a separate "Alternative Explanations" section — alternatives belong within the critical analysis.
3. Propose concrete follow-up tasks.

If loaded aspects contribute additional discussion guidance (e.g., causal reasoning checks from `causal-modeling`), incorporate that guidance into the critical analysis.

### Q&A mode (automatic)

If the user provides multiple specific questions (e.g., "I have 5 questions about X"), use a Q&A structure instead of the standard template sections:

1. One section per user question, with a focused answer and supporting evidence.
2. A synthesis section at the end that ties the answers together.

This produces clearer output than forcing multiple questions through the generic Critical Analysis / Evidence Needed split. The Q&A structure is used *instead of* the standard sections (Focus / Current Position / Critical Analysis / Evidence Needed), not in addition to them. Still include Prioritized Follow-Ups and Synthesis.

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

1. Add/adjust entries in `doc/questions/` using `.ai/templates/question.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/question.md`.
2. Offer to create follow-up tasks via `science-tool tasks add` with appropriate priority and related entities.
3. If discussion changes hypothesis wording, update relevant file in `specs/hypotheses/`.
4. **Task reframing check:** Review whether the discussion reframes the meaning of any existing tasks. If a task's purpose or scope has changed, update its description in `tasks/active.md` to reflect the new framing.
5. Commit: `git add -A && git commit -m "doc: discuss <slug> and update priorities"`
6. **Actionable recommendations:** If the discussion produced a concrete, low-cost design change or implementation recommendation (something testable in under an hour), it should be flagged with `[actionable now]` in the Prioritized Follow-Ups table. Offer to implement it immediately rather than creating a task for later. This prevents useful small changes from being buried in discussion documents.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:discuss" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead

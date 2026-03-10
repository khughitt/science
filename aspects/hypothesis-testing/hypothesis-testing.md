---
name: hypothesis-testing
description: Formal hypothesis development, tracking, and evaluation
---

# Hypothesis Testing

Projects with formal, falsifiable hypotheses tracked through status transitions.

## interpret-results

### Additional section: Hypothesis Evaluation

(insert after: Evidence vs. Open Questions)

For each active hypothesis in `specs/hypotheses/`:
- Is it relevant to these results?
- If relevant: does the evidence support, refute, or leave it unchanged?
- Propose a status update if warranted: `proposed` → `supported` / `refuted` / `revised` / `under-investigation`
- If revising, draft the revised statement

Present the evaluation table to the user. **Do not update hypothesis files until the user confirms each proposed change.**

| Hypothesis | Prior Status | Evidence Summary | Proposed Status | Confidence |
|---|---|---|---|---|
| H01 — short title | proposed | brief evidence | supported / refuted / revised / unchanged | high / moderate / low |

### Additional workflow

After writing the interpretation document:
- Update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence in the "Current Evidence" section.

## discuss

### Additional guidance

When discussing hypotheses:
- Reference the specific hypothesis ID and current status
- Distinguish between evidence that updates the hypothesis vs evidence that refines it
- Consider whether the hypothesis needs to be split into sub-hypotheses

## Signal categories

(none — uses core categories)

## Available commands

- `add-hypothesis` — develop and refine a new research hypothesis interactively

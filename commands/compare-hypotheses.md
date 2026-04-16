---
description: Head-to-head evaluation of competing explanations. Use when 2+ hypotheses exist for the same phenomenon and need structured comparison at the proposition level.
---

# Compare Hypotheses

Perform a structured comparison of competing hypotheses from `$ARGUMENTS`.

The goal is not merely to pick a winner. The goal is to identify:
- which propositions each hypothesis depends on
- which propositions are supported or disputed
- where uncertainty is concentrated
- what evidence would actually shift belief

If no arguments are provided, scan `specs/hypotheses/` and propose a high-value pair.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md`.
2. Read `.ai/templates/comparison.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/comparison.md`.
3. Read relevant hypotheses in `specs/hypotheses/`.
4. Read existing evidence in `doc/topics/`, `doc/papers/`, `doc/interpretations/`, and `doc/discussions/`.

## Workflow

### 1. Summarize Each Hypothesis As A Proposition Bundle

For each hypothesis:
- state the organizing conjecture
- list its key propositions or subpropositions
- identify which propositions are essential versus optional
- note each proposition's layer when it matters: `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`

### 2. Build A Proposition-Centric Evidence Inventory

For each major proposition:
- what supports it?
- what disputes it?
- what is merely suggestive?
- what is missing entirely?

Distinguish:
- literature support
- empirical-data support
- simulation support
- methodological objections

Also distinguish:
- direct observations versus proxy-mediated support that should carry `measurement_model`
- independent support versus support concentrated in one `independence_group`

### 3. Identify Discriminating Propositions And Predictions

Find places where the hypotheses genuinely diverge:
- propositions that cannot both be true as stated
- predictions that would separate them
- edges or mechanisms that would rise or fall differently under new evidence

If the comparison is really among bounded alternative models, represent that explicitly as a rival-model packet and treat `current_working_model` as optional rather than mandatory.

This is the most important section.

### 4. Propose Discriminating Evidence

Identify the most useful next evidence to gather:
- what would be measured
- which proposition it bears on
- how it would update each hypothesis
- whether the likely output is support, dispute, or just uncertainty reduction

Prefer evidence that:
- targets the most central uncertain propositions
- is empirically grounded
- has high discriminatory power

### 5. Assess The Current State

Summarize the comparison in skeptical terms:
- which hypothesis currently has the better-supported proposition bundle
- which one remains more fragile
- where both remain weakly supported
- where the real answer may still be “insufficient evidence”

Use verdict language carefully:
- `better supported`
- `more fragile`
- `contested`
- `insufficiently resolved`

Avoid overstating certainty.

### 6. Consider Synthesis

Ask whether the hypotheses are:
- truly competing
- complementary at different scales or contexts
- different bundles that share some valid propositions and differ only in a few decisive places

## Writing

Follow `.ai/templates/comparison.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/comparison.md`.
Save to `doc/discussions/comparison-<slug>.md`.

## After Writing

1. Save the comparison document.
2. If discriminating evidence suggests concrete work, offer to create tasks.
3. If the comparison suggests a synthesis hypothesis, suggest `/science:add-hypothesis`.
4. Suggest next steps:
   - `/science:pre-register`
   - `/science:discuss`
   - `/science:interpret-results`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:compare-hypotheses" \
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

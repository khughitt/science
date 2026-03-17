---
description: Head-to-head evaluation of competing explanations. Use when 2+ hypotheses exist for the same phenomenon and need structured comparison at the claim level.
---

# Compare Hypotheses

Perform a structured comparison of competing hypotheses from `$ARGUMENTS`.

The goal is not merely to pick a winner. The goal is to identify:
- which claims each hypothesis depends on
- which claims are supported or disputed
- where uncertainty is concentrated
- what evidence would actually shift belief

If no arguments are provided, scan `specs/hypotheses/` and propose a high-value pair.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `docs/claim-and-evidence-model.md`.
2. Read `templates/comparison.md`.
3. Read relevant hypotheses in `specs/hypotheses/`.
4. Read existing evidence in `doc/topics/`, `doc/papers/`, `doc/interpretations/`, and `doc/discussions/`.

## Workflow

### 1. Summarize Each Hypothesis As A Claim Bundle

For each hypothesis:
- state the organizing conjecture
- list its key subclaims or relation-claims
- identify which claims are essential versus optional

### 2. Build A Claim-Centric Evidence Inventory

For each major claim:
- what supports it?
- what disputes it?
- what is merely suggestive?
- what is missing entirely?

Distinguish:
- literature support
- empirical-data support
- simulation support
- methodological objections

### 3. Identify Discriminating Claims And Predictions

Find places where the hypotheses genuinely diverge:
- claims that cannot both be true as stated
- predictions that would separate them
- edges or mechanisms that would rise or fall differently under new evidence

This is the most important section.

### 4. Propose Discriminating Evidence

Identify the most useful next evidence to gather:
- what would be measured
- which claim it bears on
- how it would update each hypothesis
- whether the likely output is support, dispute, or just uncertainty reduction

Prefer evidence that:
- targets the most central uncertain claims
- is empirically grounded
- has high discriminatory power

### 5. Assess The Current State

Summarize the comparison in skeptical terms:
- which hypothesis currently has the better-supported claim bundle
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
- different bundles that share some valid claims and differ only in a few decisive places

## Writing

Follow `templates/comparison.md`.
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

Reflect on whether the comparison stayed focused on:
- claims rather than slogans
- evidence quality rather than evidence count
- uncertainty reduction rather than premature verdicts

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md`.

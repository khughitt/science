---
id: "discussion:{{YYYY-MM-DD-slug}}"
type: "discussion"
title: "{{title}}"
status: "active"
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
focus_type: "question | hypothesis | topic | approach"
focus_ref: "{{optional ID or file path}}"
mode: "standard | double-blind"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "discussion" }
    title: { from: title }
    status: { from: status }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
    focus_type: { default: "question" }
    focus_ref: { omit: true }
    mode: { default: "standard" }
  sections:
    - { key: focus, name: "Focus", required: true }
    - { key: current-position, name: "Current Position", required: true }
    - { key: critical-analysis, name: "Critical Analysis", required: true }
    - { key: evidence-needed, name: "Evidence Needed", required: true }
    - { key: prioritized-follow-ups, name: "Prioritized Follow-Ups", required: true }
    - { key: synthesis, name: "Synthesis", required: true }
    - { key: double-blind-addendum, name: "Double-Blind Addendum", required: false }
---

# Discussion: {{title}}

## Focus

<!-- What is being discussed and why? Reference the focus entity. -->

## Current Position

<!-- Current project stance, assumptions, and context. -->

## Critical Analysis

<!-- Strengths, weaknesses, assumptions, and likely failure modes.
Include alternative explanations and confounding factors.
If the alternatives are central to the analysis, integrate them directly
rather than splitting into a separate section. -->

## Evidence Needed

<!-- What evidence would help decide between alternatives? -->

## Prioritized Follow-Ups

<!-- Fill the table with concrete next steps. Suggested priority bands:
- P1: must do soon
- P1 [actionable now]: low-cost change verifiable immediately
- P2: important but not urgent
Each row should state the action, why it matters now, and any dependencies.
-->

| Priority | Action | Why now | Dependencies |
|---|---|---|---|
| P1 |  |  |  |
| P1 [actionable now] |  |  | none |

## Synthesis

<!-- Integrated conclusion and decision-oriented next steps. -->

## Double-Blind Addendum

<!-- Include this section only when mode = "double-blind". -->

### Agent Independent Draft

(Agent draft written before reading user draft.)

### User Independent Draft

(User draft.)

### Comparison

- Agreements:
- Disagreements:
- Novel points:

### Combined Synthesis

(Final synthesis considering both drafts.)

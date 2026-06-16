---
id: "synthesis:{{nn}}-{{slug}}"    # synthesis:<hyp-id> | synthesis:rollup | synthesis:emergent-threads
type: "synthesis"
title: "{{title}}"
status: "active"
report_kind: "hypothesis-synthesis"   # hypothesis-synthesis | synthesis-rollup | emergent-threads | cluster-digest
generated_at: "{{YYYY-MM-DD}}"
source_commit: ""                  # 40-char sha
phase: "active"
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "synthesis" }
    title: { from: title }
    status: { from: status }
    report_kind: { default: "hypothesis-synthesis" }
    generated_at: { from: created }
    source_commit: { default: "" }
    phase: { from: phase, default: "active" }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: tldr, name: "TL;DR", required: true }
    - { key: state, name: "State", required: true }
    - { key: arc, name: "Arc", required: true }
    - { key: research-fronts, name: "Research fronts", required: true }
    - { key: candidate-frames, name: "Candidate frames", required: true }
    - { key: knowledge-gaps, name: "Knowledge Gaps", required: true }
    - { key: emergent-threads, name: "Emergent threads", required: true }
---

# Synthesis: {{title}}

<!--
  Body skeleton — `science:big-picture` writes these procedurally. Hand-edits
  may populate the same headings to keep the shape consistent across runs.
-->

## TL;DR

<!-- Two-sentence summary: what the synthesis finds, what it leaves open. -->

## State

<!-- Current evidence weight per claim/hypothesis covered by this synthesis. -->

## Arc

<!-- How the picture has changed over time — earlier vs. later evidence. -->

## Research fronts

<!-- Open lines of inquiry the synthesis surfaces. -->

## Candidate frames

<!-- Alternative interpretations or models that fit the evidence. -->

## Knowledge Gaps

<!-- What's missing that would change the picture. -->

## Emergent threads

<!-- Cross-hypothesis patterns; only on rollup / emergent-threads kinds. -->

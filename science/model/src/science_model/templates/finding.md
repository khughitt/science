---
id: "finding:{{nn}}-{{slug}}"
kind: "finding"
title: "{{title}}"
status: "active"
propositions: []
observations: []
related: []
source_refs: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "finding" }
    title: { from: title }
    status: { from: status }
    propositions: { default: [] }
    observations: { default: [] }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: observations, name: "Observations", required: true }
    - { key: propositions, name: "Propositions", required: true }
    - { key: evidence, name: "Evidence", required: true }
    - { key: source, name: "Source", required: true }
---

# {{title}}

## Summary

<!-- Brief description of what was found. -->

## Observations

<!-- List the concrete empirical facts this finding is based on, e.g.:
- observation:<obs-id> -- <description of observation>
-->

## Propositions

<!-- List the interpretive claims this finding makes, e.g.:
- proposition:<prop-id> -- <claim text>
-->

## Evidence

<!-- How do the observations bear on the propositions? e.g.:
- observation:<obs-id> **supports** proposition:<prop-id> (strength: <moderate>)
  - Caveats: <any limitations>
-->

## Source

<!--
Data from: dataset:<source-id>
Analysis: workflow-run:<run-id> (if applicable)
-->

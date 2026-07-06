---
id: "mechanism:{{nn}}-{{slug}}"
kind: "mechanism"
title: "{{title}}"
status: "{{status}}"
participants: []
propositions: []
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "mechanism" }
    title: { from: title }
    status: { from: status }
    participants: { default: [] }
    propositions: { default: [] }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: participants, name: "Participants", required: true }
    - { key: propositions, name: "Propositions", required: true }
---

# {{title}}

## Summary

<!-- The explanatory structure this mechanism names. -->

## Participants

<!-- List the typed entities (concepts, variables) this mechanism links, e.g.:
- concept:<id>
-->

## Propositions

<!-- List the proposition refs this mechanism explains, e.g.:
- proposition:<id>
-->

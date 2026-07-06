---
id: "mechanism:{{nn}}-{{slug}}"
kind: "mechanism"
title: "{{title}}"
status: "{{status}}"
summary: ""
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
    summary: { default: "" }
    participants: { default: [] }
    propositions: { default: [] }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: notes, name: "Supplementary Notes", required: false }
---

# {{title}}

## Supplementary Notes

<!-- Author parsed mechanism fields in frontmatter: `summary`, `participants`, and `propositions`. Use this section only for explanatory notes that do not need typed parsing. -->

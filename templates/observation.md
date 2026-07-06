---
id: "observation:{{slug}}"
kind: "observation"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "observation" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: observation, name: "Observation", required: true }
    - { key: source, name: "Source", required: true }
---

# {{title}}

## Observation

<!-- The concrete empirical fact: metric, value, and conditions in prose. -->

## Source

<!-- Data from: data-package:<id> or dataset:<id> (authored via source_refs). -->

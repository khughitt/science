---
id: "prose-source:{{slug}}"
kind: "prose-source"
title: "{{title}}"
status: "active"
source_path: ""
content_hash: ""
latest_decomposition_artifact: ""
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "prose-source" }
    title: { from: title }
    status: { from: status }
    source_path: { default: "" }
    content_hash: { default: "" }
    latest_decomposition_artifact: { default: "" }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: source, name: "Source", required: true }
    - { key: notes, name: "Notes", required: true }
---

# {{title}}

## Source

## Notes

---
id: "concept:{{slug}}"
kind: "concept"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "concept" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: definition, name: "Definition", required: true }
    - { key: notes, name: "Notes", required: false }
---

# {{title}}

## Definition

<!-- One or two sentences naming this concept as the project uses it. -->

## Notes

<!-- Optional: scope, synonyms, ontology cross-references (author ontology CURIEs via `ontology_terms:` for a sci:about bridge edge). -->

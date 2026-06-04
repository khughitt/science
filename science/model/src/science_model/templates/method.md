---
id: "method:{{nn}}-{{slug}}"
type: "method"
title: "{{title}}"
status: "active"
ontology_terms: []
datasets: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "method" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    datasets: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: inputs-and-outputs, name: "Inputs and Outputs", required: true }
    - { key: thoughts, name: "Thoughts", required: true }
    - { key: connections-to-project, name: "Connections to Project", required: true }
    - { key: related, name: "Related", required: true }
---

# {{title}}

## Summary

<!-- What this method does, typical use cases, and assumptions. -->

## Inputs and Outputs

- Inputs:
- Outputs:
- Failure modes:

## Thoughts

- <fit for this project>
- <known caveat>

## Connections to Project

- Where it may be used:
- Needed tooling/libraries:
- Validation considerations:

## Related

- Topic notes:
- Article notes:
- Dataset notes:

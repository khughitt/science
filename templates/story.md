---
id: "story:{{slug}}"
kind: "story"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "story" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: synthesis, name: "Synthesis", required: true }
    - { key: relations, name: "Relations", required: false }
    - { key: gaps, name: "Gaps", required: false }
---

# Story: {{title}}

## Summary

<!--
What question does this story address, and what do the accumulated findings suggest?
-->

## Synthesis

<!--
Connective prose -- the "so what" that ties the interpretations together.
What picture emerges? What patterns repeat? Where do the findings converge?
-->

## Relations

<!--
Story edges are NOT emitted from frontmatter. Author them in
knowledge/sources/<local>/relations.yaml:

relations:
  - { subject: "story:{{slug}}", predicate: "sci:organizedBy", object: "hypothesis:<h-id>" }
  - { subject: "story:{{slug}}", predicate: "sci:synthesizes", object: "interpretation:<interp-id>" }

Then run `science graph build`.
-->

## Gaps

<!-- What's missing? What findings would strengthen this story? -->

- [ ] {{Description of missing evidence or analysis}}

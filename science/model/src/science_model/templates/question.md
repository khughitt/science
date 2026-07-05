---
id: "question:{{nn}}-{{slug}}"
kind: "question"
title: "{{title}}"
status: "active"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
ontology_terms: []
datasets: []
source_refs: []
# origins: known originators (user | assistant | literature). Provenance only;
# does not affect belief. literature ref must be paper:<key> or cite:<key>.
origins: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "question" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    datasets: { default: [] }
    source_refs: { from: source_refs }
    origins: { from: origins, default: [] }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: why-it-matters, name: "Why It Matters", required: true }
    - { key: current-evidence, name: "Current Evidence", required: true }
    - { key: thoughts, name: "Thoughts", required: true }
    - { key: connections-to-project, name: "Connections to Project", required: true }
    - { key: related, name: "Related", required: true }
---

# {{title}}

## Summary

<!-- What is being asked and why it is important. -->

## Why It Matters

<!-- Bulleted list. Cover at least:
- the decision this question affects
- the risk if the question is left unanswered
-->

## Current Evidence

<!-- Bulleted list. Cover at least:
- supporting evidence
- conflicting evidence
-->

## Thoughts

<!-- Bulleted list. Cover at least:
- the best current interpretation
- the major remaining uncertainty
-->

## Connections to Project

- Related hypotheses:
- Required datasets: list dataset IDs in frontmatter `datasets:`.
- Required analyses:
- Priority level:

## Related

- Topic notes:
- Article notes:
- Methods/Datasets:

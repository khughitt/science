---
id: "falsification:{{slug}}"
kind: "falsification"
title: "{{title}}"
status: "{{status}}"
falsifies: "proposition:CHANGEME"
predicted: ""
observed: ""
decision: ""
source_of_prediction: ""
supersedes_claim: ""
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "falsification" }
    title: { from: title }
    status: { from: status }
    falsifies: { default: "proposition:CHANGEME" }
    predicted: { default: "" }
    observed: { default: "" }
    decision: { default: "" }
    source_of_prediction: { default: "" }
    supersedes_claim: { omit: true }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: prediction, name: "What was predicted", required: true }
    - { key: observation, name: "Observation", required: true }
    - { key: decision, name: "Decision", required: true }
---

# Falsification: {{title}}

## What was predicted

<!--
State the prediction that followed from the target proposition.
-->

## Observation

<!--
State the observation that failed to match the prediction.
-->

## Decision

<!--
Record the resulting decision about the proposition or interpretation.
-->

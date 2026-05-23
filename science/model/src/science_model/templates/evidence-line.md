---
id: "evidence-line:{{slug}}"
type: "evidence-line"
title: "{{title}}"
status: "{{status}}"
stance: "supports"
target: "proposition:CHANGEME"
source: ""
strength: "moderate"
independence: "independent"
independence_group: ""
evidence_role: "direct_test"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "evidence-line" }
    title: { from: title }
    status: { from: status }
    stance: { default: "supports" }
    target: { default: "proposition:CHANGEME" }
    source: { default: "" }
    strength: { default: "moderate" }
    independence: { default: "independent" }
    independence_group: { default: "" }
    evidence_role: { default: "direct_test" }
    dispute_scope: { omit: true }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: what-this-line-shows, name: "What this line shows", required: true }
    - { key: why-it-is-independent, name: "Why it is independent", required: true }
    - { key: caveats-scope, name: "Caveats / scope", required: true }
    - { key: measurement-model, name: "Measurement Model", required: false }
---

# Evidence Line: {{title}}

## What this line shows

<!--
Summarize what this evidence line demonstrates in 1-3 sentences.
State the observation or finding clearly, including the source if known.
Indicate whether the line supports or disputes the target claim, and how directly.
-->

## Why it is independent

<!--
Explain why this evidence line is independent of others in the same bundle (or note if it is not).
If independence is "shared-source" or "circular", document the overlap explicitly.
Independence category: independent | shared-source | circular
-->

## Caveats / scope

<!--
Known limitations, boundary conditions, and threats to the inference.
Note the strength (strong / moderate / weak) and dispute_scope if this line disputes a claim
(whole_claim | generalization | mechanism | boundary).
-->

## Measurement Model

<!--
Optional. Use when the evidence is proxy-mediated.
Describe the proxy relation explicitly:
- observed_entity: which observation grounds this line
- latent_construct: what the claim is really about
- measurement_relation: how the observation is interpreted as a proxy
- rationale: why this interpretation is reasonable
- known_failure_modes: ways the proxy could mislead
-->

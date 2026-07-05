---
id: "proposition:{{slug}}"
kind: "proposition"
title: "{{title}}"
status: "{{status}}"
claim_layer: "empirical_regularity"
identification_strength: "observational"
proxy_directness: "direct"
supports_scope: "local_proposition"
# Bundle membership. Bare string = core member (enters the bundle's belief
# conjunction). Use {frame: <hyp/mech>, role: rival|background} to exclude a
# non-load-bearing member. See research-proposition-schema for role semantics.
discusses: []
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "proposition" }
    title: { from: title }
    status: { from: status }
    claim_layer: { default: "empirical_regularity" }
    identification_strength: { default: "observational" }
    proxy_directness: { default: "direct" }
    supports_scope: { default: "local_proposition" }
    discusses: { default: [] }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: claim, name: "Claim", required: true }
    - { key: evidence-summary, name: "Evidence Summary", required: true }
    - { key: caveats, name: "Caveats", required: true }
    - { key: measurement-model, name: "Measurement Model", required: false }
    - { key: related-propositions, name: "Related Propositions", required: false }
---

# Proposition: {{title}}

## Claim

<!--
State the proposition in 1-3 sentences. Prefer explicit subject-predicate-object form.
This is the primary truth-apt unit; uncertainty attaches here, not at the hypothesis level.
-->

## Evidence Summary

<!--
Briefly summarize what supports or disputes this proposition.
Note evidence type where possible:
- literature_evidence
- empirical_data_evidence
- simulation_evidence
- benchmark_evidence
- expert_judgment
Detailed observation and evidence-edge attachment lives in the graph; this section is the human-readable summary.
-->

## Caveats

<!--
Known limitations, scope boundaries, proxy gaps, and conditions under which the claim could fail.
If the claim is proxy-mediated, also fill in the Measurement Model section below.
-->

## Measurement Model

<!--
Optional. Required when proxy_directness is "indirect" or "derived".
Describe the proxy relation explicitly:
- observed_entity: which observation grounds this claim
- latent_construct: what the claim is really about
- measurement_relation: how the observation is interpreted as a proxy
- rationale: why this interpretation is reasonable
- known_failure_modes: ways the proxy could mislead
-->

## Related Propositions

<!--
Optional. Sibling propositions in the same bundle, or parent/child propositions for decomposed claims.
-->

---
id: evidence-line:guardrails-proxy-almodovar2025
kind: evidence-line
title: DeCaFlow operationalizes proxy-identifiability tiers
status: active
stance: supports
target: proposition:guardrails-check-structural-identity-and-proxy-identifiability
source: paper:Almodovar2025
strength: moderate
independence: independent
independence_group: ''
evidence_role: background_constraint
evidence_type: literature
related: []
source_refs:
- paper:Almodovar2025
created: '2026-07-10'
updated: '2026-07-10'
---
# Evidence Line: DeCaFlow operationalizes proxy-identifiability tiers

## What this line shows

Almodóvar et al. (DeCaFlow) recover correct interventional/counterfactual estimates
under hidden confounding via proxy variables, with an explicit identifiability tier
(do-calculus / proxy-identifiable / unidentifiable) [@Almodovar2025]. This supports
the proposition's proxy-identifiability half: a guardrail should record whether an
estimand is identified at all, motivating `identification_status` and
`proxy_vars`/`null_proxy_vars` payload fields.

## Why it is independent

A machine-learning causal-estimation method (normalizing-flow deconfounding),
independent of Hoover's structural-identity argument; distinct method and literature.

## Caveats / scope

Moderate strength: proxy-identifiability results assume the proxy structure is
correctly specified — a misspecified proxy set can make an unidentifiable effect
look identified, so the field must record the assumed proxy structure, not just a
boolean. Validated in ML settings, not on Science's symbolic evidence graph.

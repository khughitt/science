---
id: proposition:guardrails-check-structural-identity-and-proxy-identifiability
kind: proposition
title: Causal-estimand guardrails must check structural-identity and proxy-identifiability,
  not only statistical estimand mismatch
status: active
claim_layer: structural_claim
identification_strength: observational
proxy_directness: direct
supports_scope: local_proposition
discusses:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
related: []
source_refs:
- paper:Hoover2009
- paper:Almodovar2025
created: '2026-07-10'
updated: '2026-07-10'
---
# Proposition: Causal-estimand guardrails must check structural-identity and proxy-identifiability, not only statistical estimand mismatch

## Claim

The `hypothesis:0004` causal-estimand guardrail must guard against more than
statistical estimand mismatch. It must also check (a) **structural-identity
mismatch** — evidence gathered under a different causal structure targets a
different system and must not strengthen the same proposition, where two systems
are identical only if they share variables, parameter space, and functional form
(Hoover) — and (b) **proxy-identifiability** — whether an interventional or
counterfactual estimand is do-calculus-identifiable, proxy-identifiable, or
unidentifiable under hidden confounding (DeCaFlow). A guardrail that checks only
whether two estimands are the *statistical* quantity, while ignoring whether they
concern the *same causal system* and whether that system's effect is identified at
all, will let structurally-mismatched or unidentifiable evidence strengthen an edge.

## Evidence Summary

*Evidence type: literature_evidence (methodological).*
Hoover grounds causal order in a privileged (variation-free) parameterization: two
causal systems are identical iff they share variables, parameter space, and
functional form, and modularity can hold at the parameter level yet fail at the
mechanism level (carburetors, the Lucas critique) — so "same estimand" is
insufficient for "same system" [@Hoover2009]. Almodóvar et al. (DeCaFlow)
operationalize the estimand side, recovering correct interventional/counterfactual
estimates under hidden confounding via proxy variables and making the
identifiability tier (do-calculus / proxy-identifiable / unidentifiable) explicit
[@Almodovar2025]. Together they motivate concrete new payload fields:
`identification_status`, `proxy_vars`/`null_proxy_vars`, a `structural_only` /
structural-hypothesis evidence role, `hidden_confounder` annotation, and a
`modularity-failure` reason code (task t096).

## Caveats

Both sources are pre-computational relative to Science's schema; the field list is a
design proposal, not a validated guardrail. Structural identity requires knowing the
parameterization, which is often unavailable for literature-derived evidence, so the
check may be inapplicable exactly where it is most needed and must degrade to an
explicit "structure unknown" state rather than defaulting to "same system."
Proxy-identifiability results (DeCaFlow) assume the proxy structure is correctly
specified; a misspecified proxy set can make an unidentifiable effect look
identified, so the field must record the assumed proxy structure, not just a boolean.

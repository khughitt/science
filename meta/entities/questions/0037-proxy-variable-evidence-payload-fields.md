---
id: question:0037-proxy-variable-evidence-payload-fields
kind: question
title: What fields should the evidence payload require for proxy-identified causal
  claims?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Almodovar2025
related:
- question:0003-causal-synthesis-guardrails
- question:0002-evidence-payload-schema
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
created: '2026-07-10'
updated: '2026-07-10'
---

# What fields should the evidence payload require for proxy-identified causal claims?

## Summary

When a causal estimate is produced via proxy-variable adjustment (proximal causal inference) rather than standard do-calculus identification, what additional evidence-payload fields are required to distinguish such claims from do-calculus-identified or unidentified ones? DeCaFlow [@Almodovar2025] shows that proxy-identified claims require knowing which observed variables served as proxies, whether a null-proxy structure exists, what the latent confounder dimensionality assumption was, and whether the completeness condition was approximately satisfied. Without these fields, the toolkit cannot distinguish proxy-identified causal claims from unverified ones in the guardrail.

## Why It Matters

- Affects the evidence-payload schema (question:0002) and the causal guardrail (question:0003): a claim tagged as `identification_status: proxy_identified` is valid only if proxy metadata is recorded; without it, the guardrail cannot evaluate the claim's assumptions.
- Risk if unanswered: proxy-identified claims may enter the graph indistinguishably from do-calculus-identified claims, hiding the stronger assumptions (proxy informativeness, confounder dimensionality) they depend on.

## Current Evidence

- DeCaFlow [@Almodovar2025] makes explicit four minimal conditions for proxy identifiability: existence of proxy variable w, null-proxy n, blocking set b, and informative confounded variables satisfying a completeness condition.
- The completeness condition is untestable from data; proxy count and diversity are the only available proxies for it.
- Petersen and van der Laan ([@Petersen2014], cited in H04) separately document the distinction between statistical estimand, identification, and causal model — consistent with needing an explicit identification-tier field.
- No current Science schema distinguishes `do_calculus_identified`, `proxy_identified`, `IV_identified`, or `unidentified` as identification status values.

## Thoughts

- Best interpretation: the evidence payload for any CGM-based causal output should carry: `identification_method` (one of: do_calculus, proxy, IV, front_door, unidentified), `proxy_vars` (list), `null_proxy_vars` (list), `blocking_set` (list, may be empty), `confounder_dim_assumption` (integer or range), and `completeness_checked` (boolean with note).
- Major uncertainty: whether these fields belong on the evidence artifact itself, on the source-model node, or on a separate identification record. The current schema has no precedent for method-level identification metadata distinct from the estimand fields.

## Connections to Project

- Related hypotheses: hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening (P2, P4a — identification-status field is one of the minimum guardrail fields).
- Required data or analyses: draft a schema extension for the evidence payload with the fields above; test against the Sachs and Ecoli70 DeCaFlow outputs as example cases.
- Priority level: medium — depends on whether DeCaFlow-style models are integrated before or after the guardrail schema is finalized.

## Related

- Topic notes: proximal causal inference (Miao et al., Wang & Blei), identifiability under hidden confounding.
- Article notes: paper:Almodovar2025 (DeCaFlow — source of this question); paper:Deleu2023 (GFlowNet for graph structure — related CGM class without hidden confounders).
- Methods/Datasets: Sachs protein-signaling network (public), Ecoli70 gene network (public).

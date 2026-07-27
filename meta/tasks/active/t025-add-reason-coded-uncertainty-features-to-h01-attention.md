---
id: t025
project: ''
title: Add reason-coded uncertainty features to H01 attention
type: ''
aspects:
- software-development
- framework-design
- hypothesis-testing
priority: P2
status: proposed
blocked_by: []
related:
- task:t021
- hypothesis:0001-stochastic-revisiting
- question:0002-evidence-payload-schema
parent: task:t021
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Extend H01-style revisiting beyond posterior/support magnitude by adding reason-coded uncertainty features.
Candidate reasons from Batch 1: `underpowered-evidence`, `high-heterogeneity`, `publication-bias-risk`, `model-uncertainty`, `prior-sensitive`, `imperfect-label`, `boundary-case`, `complex-hypothesis-penalty`, and `estimand-mismatch`.
Candidate reasons from Batch 2: `source-unreliable`, `source-dependent`, `omission-ambiguous`, `missing-view`, `source-target-mismatch`, `prior-resolved-nonidentifiability`, `cleaning-unvalidated`, `repair-uncertain`, `shared-structure-assumption`, and `debiased-inference-missing`.
Candidate reasons from Batch 3: `causal-sufficiency-assumption`, `latent-variable-risk`, `llm-prior-unvalidated`, `prior-data-disagreement`, `graph-object-ambiguous`, `self-incompatible`, `identification-missing`, `weak-prior-only`, `instrument-assumption-risk`, and `mediation-estimand-ambiguous`.
Candidate reasons from Batch 4: `graph-posterior-uncertain`, `edge-inclusion-unstable`, `shared-structure-dependent`, `view-scope-mismatch`, `variational-approximation-risk`, `pseudo-likelihood-risk`, `clustering-unvalidated`, `selected-feature-unstable`, and `exploratory-integration-only`.
Candidate reasons from Batch 5: `agent-source-unvalidated`, `tool-chain-unvalidated`, `safety-check-missing`, `context-retrieval-uncertain`, `information-absence-undetected`, `kg-view-derived`, `graph-version-stale`, `agent-bias-risk`, and `attention-not-evidence`.
Candidate reasons from Batch 6: `robustness-target-ambiguous`, `modifier-domain-missing`, `tolerance-unspecified`, `replication-metric-mismatch`, `reproducibility-dimension-ambiguous`, `checklist-incomplete`, `analysis-plan-missing`, `deviation-unreported`, `code-or-data-unavailable`, and `null-results-omitted`.
Generic evidence-quality codes (added 2026-05-06 from `[t030]` narrow audit; not extension-specific): `single-source-evidence`, `simulated-data-only`, `peer-reviewed-only`, `self-validated-method`, and `legacy-unverified-payload`. These arise on paper-extracted-claim payloads regardless of aspect; mark `peer-reviewed-only` non-blocking, `legacy-unverified-payload` blocking (per v2.1 migration spec), and the others non-blocking-by-default with extension override allowed.

Design how these reasons are recorded on evidence/synthesis artifacts and how `science graph attention-sample` could incorporate them without using LLM-estimated probabilities.
This should follow `[t022]` enough to avoid inventing a parallel schema.
Aspect-extension design tasks (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) each declare their own H03 reason codes; this task is the canonical registry — when those tasks formalize a code, mirror it here with batch provenance.
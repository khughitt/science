---
id: t021
project: ''
title: Evidence Payload Schema task group
type: ''
aspects:
- software-development
- framework-design
- hypothesis-testing
- causal-modeling
priority: P1
status: proposed
blocked_by: []
related:
- question:0002-evidence-payload-schema
- question:0003-causal-synthesis-guardrails
- hypothesis:0001-stochastic-revisiting
- topic:bayesian-methods-continuous-belief
parent: ''
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Coordinate the post-Batch-1 work on quantitative evidence representation.
Batch 1 showed that evidence updates need more than `supports` / `disputes` plus a scalar: they need comparison target, estimand, model family, prior, heterogeneity, bias model, study power, diagnostics, causal target population, aggregation operator, and sensitivity deltas.
Batch 2 extends this with source behavior and pipeline provenance: source reliability, source dependence, omission semantics, missingness class, cleaning/extraction/preprocessing provenance, source population, target population, transport assumptions, prior provenance, identifiability, and validation role.
Batch 3 extends this with causal graph construction provenance: causal model reference, observed-data link, counterfactual target, graph object type, discovery algorithm, method assumption set, prior role, constraint type, prompt and variable-proposal provenance, self-compatibility score, causal-sufficiency assumption, latent-variable risk, mediation estimand, instrument set, and graph posterior.
Batch 4 extends this with graph-valued and integration-valued artifacts: integration objective, graph artifact type, context scope, view scope, shared-structure assumption, borrowing structure, approximation class, posterior summary role, edge inclusion probability, cluster count, feature relevance posterior, and validation role.
Batch 5 extends this with agent/tool/KG operational provenance: agent role, model version, prompt/workflow reference, tool-chain reference, tool I/O contract, safety policy, execution trace, KG view, KG filter objective, subgraph selection method, graph update event type, graph version, validation status, abstention reason, agent evaluation protocol, and Bayes-factor evidence.
Batch 6 extends this with robustness/reproducibility evaluation semantics: evaluation target, robustness target, robustness modifier, modifier domain, intervention type, target tolerance, replication design, reproducibility dimension, metric family, metric question, metric assumptions, checklist reference, lifecycle stage, evaluation result, and validation role.

This parent task tracks the group.
Concrete implementation/design tasks are `[t022]` through `[t026]` plus `[t030]` through `[t041]`.
Do not implement a schema directly from this parent; use it to keep the work visible and grouped.

**Architecture decision (2026-05-06):** the schema is layered — `[t022]` produces the **core** (small, mandatory) plus the **extension contract**; `[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]` produce **typed extensions** that conform to that contract.
Without this split, every batch silently widened the "minimum" schema (~50 fields after Batch 6) and aspect tasks competed as P1 siblings.
`[t025]` is the canonical H03 reason-code registry — aspect tasks declare codes locally and mirror them there with batch provenance.
Lit follow-up tasks (`[t028]`, `[t036]`, `[t039]`, `[t041]`) are P3 so they do not compete with the schema work.

**State (2026-07-01):** `[t022]` shipped and is now carried by the durable
contract at `meta/evidence/t022-core-contract.md`, with generic implementation
coverage in `science/src/science_tool/evidence_payload.py` and
`science/tests/test_evidence_payload_contract.py`. `[t030]` validated the
structural pruning that produced the compact core. Aspect extensions
(`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) remain the place for
family-specific fields and validators.
Carry-forwards: each aspect extension declaring an evaluation/audit/operation
type owns its own target field (no longer in core); paper-extracted claims use
`claim_source_ref`; `partial_fields` marks partially enumerated list fields; and
`uncertainty_summary` is optional so authors do not synthesize qualitative prose
as if it were canonical uncertainty.

Surfaced by: `entities/synthesis/0001-synthesis-bayesian-evidence-synthesis-and-meta-analysis.md`.

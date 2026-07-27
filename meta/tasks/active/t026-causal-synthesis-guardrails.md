---
id: t026
project: ''
title: Causal synthesis guardrails
type: ''
aspects:
- software-development
- framework-design
- causal-modeling
- hypothesis-testing
priority: P2
status: active
blocked_by: []
related:
- task:t021
- question:0003-causal-synthesis-guardrails
- question:0002-evidence-payload-schema
parent: task:t021
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Design guardrails for when meta-analytic, synthesized, integrated, discovered, or LLM-elicited evidence can strengthen causal propositions or causal edges.
Require explicit target population, source population where relevant, causal contrast, effect measure, aggregation rule, covariate coverage, transport or exchangeability assumptions, evidence role, validation role, graph object type, discovery method, method assumption set, prior role, hidden-variable assumption, diagnostic status, and identification status before a synthesis or graph-construction node can update a causal proposition.

Special attention:
- non-collapsible measures such as odds ratios;
- target-population mismatch;
- source-population and covariate-coverage mismatch;
- arm-based versus contrast-based aggregation;
- graph estimates versus debiased inferential edge claims;
- LLM priors versus causal evidence;
- discovered adjacencies versus identified causal effects;
- DAG / CPDAG / PAG / ADMG / graph posterior distinctions;
- causal-sufficiency and hidden-variable assumptions;
- self-compatibility diagnostics and variable-subset stability;
- mediation estimands and MR instrument assumptions;
- whether missing metadata should produce a warning, validation error, or H01 revisit signal.

Start from `paper:Berenfeld2026`, `paper:Dai2023`, `paper:Thijssen2017`, `paper:Majumdar2022`, `paper:Petersen2014`, `paper:Shi2022`, `paper:Dong2023`, `paper:Faller2024`, `paper:Zheng2024`, `paper:Zuber2025`, and the causal-modeling aspect.

### Notes

- 2026-05-08: Scope narrowed (2026-05-08): t034 v1.3 design absorbs per-payload schema (graph-object taxonomy, edge-role typing, causal-sufficiency, mediation, MR, self-compatibility, identification). t026 now owns the cross-payload policy layer: non-collapsibility / odds ratios, arm-based vs contrast-based aggregation, source-population transport, and the decision rule for when t034 graph + t023 synthesis + t040 robustness jointly strengthen a causal proposition (warning vs validation error vs H01 revisit signal).
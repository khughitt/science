---
id: t024
project: ''
title: Represent heterogeneity and bias as evidence-generation mechanisms
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
- question:0002-evidence-payload-schema
- hypothesis:0001-stochastic-revisiting
parent: task:t021
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Model heterogeneity and bias as explicit mechanisms that bear on evidence interpretation rather than as prose-only caveats.
Candidate mechanism classes include publication bias, p-hacking / selection, model uncertainty, imperfect reference labels, study dependence, source copying, shared pipeline bias, extraction uncertainty, data-cleaning bias, batch effects, missing views, source-target population mismatch, prior-resolved non-identifiability, agent search bias, causal-sufficiency violations, latent-variable misspecification, prior/data conflict, prompt-induced graph bias, variable-proposal bias, self-incompatibility, instrument invalidity, shared-structure bias, graph-posterior uncertainty, variational-approximation risk, pseudo-likelihood risk, clustering instability, selected-feature instability, and view-scope mismatch.

Deliverables:
- propose entity kinds or payload fields for these mechanisms;
- define how they attach to studies, evidence edges, synthesis nodes, propositions, and H01 attention signals;
- identify which mechanisms are general enough for core Science versus project-specific extensions.

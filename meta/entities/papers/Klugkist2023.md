---
kind: paper
title: 'Bayesian Evidence Synthesis for Informative Hypotheses: An Introduction'
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Klugkist2023
ontology_terms: []
source_refs:
- cite:Klugkist2023
related: []
---

# Bayesian Evidence Synthesis for Informative Hypotheses: An Introduction

- **Authors:** Irene Klugkist and Thom Benjamin Volker
- **Year:** 2023
- **Journal:** Psychological Methods
- **DOI/URL:** https://doi.org/10.1037/met0000602
- **BibTeX key:** Klugkist2023
- **Source:** PDF

## Key Contribution

Klugkist and Volker introduce Bayesian evidence synthesis (BES) as a way to combine Bayes factors for informative hypotheses across multiple studies that address a common theory but may use different designs, measurements, parameters, or statistical models [@Klugkist2023].

The paper clarifies that BES answers a different question than Bayesian sequential updating (BSU): BES asks whether each independent study supports the theory, while BSU asks whether pooled compatible data support the same hypothesis [@Klugkist2023].

This distinction makes BES especially relevant for conceptual replications whose heterogeneity prevents ordinary data pooling or meta-analysis [@Klugkist2023].

## Methods

The authors use Bayesian informative hypothesis testing, where a theory is formalized as equality or inequality constraints on model parameters and evaluated with Bayes factors against alternatives such as the unconstrained model, the complement hypothesis, or the null hypothesis [@Klugkist2023].

They illustrate Bayes factor behavior analytically with a binomial example for an inequality-constrained hypothesis on a success probability [@Klugkist2023].

They compare BES with BSU by aggregating repeated binomial studies under different alternatives and showing how the posterior model probabilities diverge because the aggregation questions differ [@Klugkist2023].

They run two R simulations over 1,000 iterations per condition, with OLS, logistic, and probit regression studies at sample sizes 50, 100, 200, 400, and 800 and effect sizes R2 = 0.02, 0.09, and 0.25 [@Klugkist2023].

Simulation 1 varies outcome variables and statistical models while keeping the informative hypothesis structurally equivalent across studies [@Klugkist2023].

Simulation 2 varies both outcomes and predictor operationalizations, so study-specific hypotheses differ while representing the same underlying theory [@Klugkist2023].

## Key Findings

When exact replications share hypotheses and model parameters, BSU is preferable because it pools data coherently, increases statistical power, and can overcome weak individual studies [@Klugkist2023].

BES does not pool observations, so underpowered individual studies can accumulate support for a simpler competitor, including the null or complement, rather than rescuing the target hypothesis [@Klugkist2023].

When individual studies have sufficient power, BES can aggregate support for theoretically equivalent hypotheses over heterogeneous studies, and aggregated support increases with larger effects, larger samples, and more supporting studies [@Klugkist2023].

The choice of alternative matters: testing an informative hypothesis against its complement is recommended when the goal is to evaluate one focal informative hypothesis, while comparisons among multiple informative hypotheses should compare those hypotheses directly [@Klugkist2023].

Study-specific operationalizations and hypothesis complexity affect Bayes factors, so the final BES aggregate can hide important variation in how strongly individual studies contribute [@Klugkist2023].

## Relevance

BES gives Science a concrete pattern for evidence aggregation over graph nodes that represent a shared theoretical proposition but are backed by heterogeneous local models, measurements, or study designs.

The paper supports Decision D-003 because posterior model probabilities provide continuous belief states rather than binary accept/reject decisions [@Klugkist2023].

The paper is directly relevant to H01 because it shows that weak or underpowered evidence can down-weight a claim for structural reasons, not necessarily because the claim is false.

For H01, BES implies that revisiting down-weighted claims should consider whether the down-weighting came from noisy underpowered studies, from model-complexity penalties, or from genuinely contrary evidence.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Informative hypothesis | Proposition with parameter constraints | A theory-backed claim can be encoded as equality or inequality constraints over model parameters. |
| Bayes factor | Evidence edge weight | A study contributes a likelihood-ratio-like support measure between a target hypothesis and a named competitor. |
| Posterior model probability | Operational belief | PMPs fit the continuous probability requirement in Decision D-003. |
| Bayesian evidence synthesis | Evidence aggregation over heterogeneous studies | BES aggregates study-level Bayes factors when raw data, parameters, or effect sizes cannot be pooled. |
| Bayesian sequential updating | Belief update over compatible repeated observations | BSU applies when studies share hypotheses and model parameters closely enough to update the same model. |
| Conceptual replication | Heterogeneous evidence subgraph | Different study designs can still connect to one underlying theory if each local hypothesis is explicitly mapped. |
| Hypothesis complexity | Model/prior complexity penalty | Complexity affects evidence weights and can bias aggregate influence across differently formalized study nodes. |

## Limitations

BES assumes all target studies investigate the same underlying common theory and provide independent evidence for that theory [@Klugkist2023].

BES is not a remedy for underpowered studies because it aggregates the study-level evidence that each study actually produced [@Klugkist2023].

The method does not by itself expose heterogeneity, publication bias, or moderator effects in the way meta-analysis can [@Klugkist2023].

The authors note that more research is needed on how differences in hypothesis complexity and sample size affect BES aggregation [@Klugkist2023].

The simulations are illustrative rather than a comprehensive validation of BES performance across practical research settings [@Klugkist2023].

## Model / Tool Availability

The paper reports that all analysis and simulation code is publicly available at https://github.com/thomvolker/bes-intro-paper [@Klugkist2023].

The analyses use R and the BFpack package, with the appendix specifying BFpack Version 1.0.0 for the simulations [@Klugkist2023].

The PDF states that the simulations used R Version 4.2.1 [@Klugkist2023].

License, maintenance status, and reproducibility state of the GitHub repository were not checked during the initial summary pass; tracked by task:t074.

## Follow-up

Model claim-belief updates so that each evidence edge records the comparator hypothesis, because a Bayes factor against the complement, null, or unconstrained model has a different interpretation.

Track per-study contribution diagnostics alongside any aggregate belief so that hypothesis complexity, sample size, and operationalization effects are not hidden by a single posterior probability.

Use BES-like aggregation only when the orchestrator can justify a common-theory mapping across heterogeneous studies; otherwise fail early instead of silently combining unrelated evidence.

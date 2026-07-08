---
kind: paper
title: 'Combining Support for Hypotheses over Heterogeneous Studies with Bayesian
  Evidence Synthesis: A Simulation Study'
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Volker2023
ontology_terms: []
source_refs:
- cite:Volker2023
related:
- topic:bayesian-methods-continuous-belief
---

# Combining Support for Hypotheses over Heterogeneous Studies with Bayesian Evidence Synthesis: A Simulation Study

- **Authors:** Thom Benjamin Volker and Irene Klugkist
- **Year:** 2023
- **Journal:** arXiv preprint
- **DOI/URL:** https://arxiv.org/abs/2312.15032
- **BibTeX key:** Volker2023
- **Source:** PDF

## Key Contribution

Volker and Klugkist evaluate Bayesian Evidence Synthesis (BES), a Bayes-factor-based method for combining support for conceptually similar informative hypotheses across studies whose effect sizes or models are too heterogeneous for conventional meta-analysis [@Volker2023].
The central contribution is a simulation-based account of when BES works well and when hypothesis complexity, low power, and the choice of alternative hypothesis can make aggregation misleading.

## Methods

The paper uses Monte Carlo simulations over generalized linear model settings, including OLS, logistic, and probit regressions.
The simulations vary sample size, effect size, number of studies, hypothesis complexity, data-handling choices, and whether the informative hypothesis is evaluated against an unconstrained or complement hypothesis.
BES aggregates study-level Bayes factors that test study-specific statistical hypotheses intended to instantiate the same overarching theory.

## Key Findings

BES can aggregate support across studies with different analysis models and operationalizations when individual studies have sufficient statistical power.
It does not behave like data pooling: adding more underpowered studies can amplify support for an alternative rather than rescue a true but weakly supported hypothesis.
More specific hypotheses require more power because each additional constraint creates another way for noisy estimates to violate the hypothesis.
Evaluating an informative hypothesis against its complement is often more powerful than evaluating it against an unconstrained hypothesis, but boundary cases can remain unstable.

## Relevance

This paper is directly relevant to Science's proposition-centric evidence graph.
It supports the idea that evidence should often attach to explicit hypotheses or propositions rather than to pooled effect-size summaries, especially when studies use incompatible operationalizations.
It also cautions against naive multiplicative accumulation of evidence edges: evidence aggregation should track study power, hypothesis complexity, and whether a proposition is decomposed into separable constraints.
For H01, the paper strengthens the case that down-weighted claims should not be hard-gated merely because early or underpowered evidence provides weak Bayes-factor support.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Overarching theory | hypothesis bundle | The theory is tested through multiple study-specific hypotheses. |
| Informative hypothesis | proposition or constrained proposition set | BES works best when propositions are explicit enough to test. |
| Study-specific Bayes factor | evidence edge weight | The edge should record comparison class and power context. |
| Hypothesis complexity | proposition decomposition burden | Complex claims may need decomposition before aggregation. |

## Limitations

The simulations use relatively stylized data-generating processes and focus on inequality-constrained hypotheses.
The paper does not solve dependence among studies or correlated methodological biases, both of which matter for Science's graph model.
It also shows that BES is vulnerable to underpowered studies, so BES-style aggregation should not be treated as a general replacement for pooled modeling.

## Model / Tool Availability

The paper references simulation scripts and results being available on GitHub, but the summary did not check repository persistence beyond the PDF text during the initial pass; tracked by task:t074.

## Follow-up

Science should represent an evidence edge's comparison target, hypothesis complexity, and study power rather than storing only a scalar support value.
Complex propositions should be decomposed into smaller proposition units before aggregation when a study can support only part of the full constraint.

---
type: paper
title: Bayesian meta-analysis now - let's do it
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Hackenberger2020
ontology_terms: []
source_refs:
- cite:Hackenberger2020
related: []
---

# Bayesian meta-analysis now - let's do it

- **Authors:** Branimir K. Hackenberger
- **Year:** 2020
- **Journal:** Croatian Medical Journal
- **DOI/URL:** https://doi.org/10.3325/cmj.2020.61.564
- **BibTeX key:** Hackenberger2020
- **Source:** PDF

## Key Contribution

Hackenberger argues that Bayesian meta-analysis is now practical enough for routine research use and should be treated as a complement to frequentist meta-analysis rather than a rival paradigm [@Hackenberger2020].
The paper's core contribution for Science is its framing of meta-analysis as a mechanism for producing new aggregate evidence while preserving uncertainty about model parameters, heterogeneity, and prior commitments [@Hackenberger2020].
It also provides a compact survey of available Bayesian meta-analysis software, including OpenBUGS, JAGS, Stan, PyMARE, metaBMA, bamdit, meta4diag, NMADiagT, BayesCombo, bmeta, brms, and jarbes [@Hackenberger2020].

## Methods

The article is a narrative methodological overview, not an empirical benchmark or new algorithm paper [@Hackenberger2020].
It contrasts fixed-effect and random-effects meta-analysis, then explains Bayesian meta-analysis as a framework in which both data and model parameters are treated as random variables [@Hackenberger2020].
It summarizes software ecosystems and examples from COVID-19 research, medicine, psychology, environmental science, agriculture, ecology, economics, and social science [@Hackenberger2020].
The methodological emphasis is on prior probability distributions, likelihood functions, posterior probability distributions, MCMC, HMC, INLA, Bayes factors, posterior predictive checks, and leave-one-out cross-validation [@Hackenberger2020].

## Key Findings

Bayesian meta-analysis can explicitly propagate uncertainty in heterogeneity variance, whereas frequentist approaches often use a point estimate of heterogeneity variance as a fixed quantity and can underestimate variability [@Hackenberger2020].
Bayesian models support sensitivity analysis by changing distributional assumptions and prior specifications [@Hackenberger2020].
Bayesian model averaging can combine fixed-effect and random-effects models or models with and without moderators using posterior model probabilities or Bayes factors [@Hackenberger2020].
Hierarchical meta-regression is presented as a way to incorporate the data collection process and address internal and external validity bias when combining different study types [@Hackenberger2020].
The article treats subjective beliefs as a legitimate input to prior construction while emphasizing that Bayesian and frequentist methods can both be useful under appropriate conditions [@Hackenberger2020].

## Relevance

The paper directly supports Decision D-003 because its operational quantities are continuous probability distributions and posterior probabilities, not binary accepted/rejected states [@Hackenberger2020].
It is relevant to H01 because it gives a statistical rationale for revisiting down-weighted claims when prior assumptions, heterogeneity estimates, moderators, or new evidence change the posterior landscape [@Hackenberger2020].
For graph-oriented research workflows, Bayesian meta-analysis suggests that evidence aggregation nodes should store posterior distributions, heterogeneity estimates, model-comparison weights, and sensitivity-analysis outputs rather than only scalar summary effects.
For research-agent behavior, the paper supports workflows where agents inspect uncertainty and heterogeneity before deciding whether a low-ranked claim should be retired, retained, or resampled.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Prior probability distribution | Operational belief prior | Encodes pre-existing belief or domain knowledge before new evidence is aggregated. |
| Likelihood function | Evidence update model | Connects observed study results to hypothesized parameters. |
| Posterior probability distribution | Continuous operational belief | Aligns with D-003 by keeping beliefs in probabilistic form. |
| Heterogeneity variance | Cross-study uncertainty / evidence-noise structure | Useful for deciding whether disagreement is noise, context dependence, or model misspecification. |
| Bayesian model averaging | Multi-model belief aggregation | Provides a candidate mechanism for combining competing graph models or effect models. |
| Sensitivity analysis | Revisit trigger / robustness check | Changes in priors or distributional assumptions can identify claims that deserve renewed attention under H01. |
| Hierarchical meta-regression | Causal/contextual evidence model | Maps study design, moderators, and collection process into aggregation rather than treating all evidence as exchangeable. |

## Limitations

The article is introductory and persuasive rather than a formal comparison of Bayesian and frequentist meta-analysis performance [@Hackenberger2020].
It does not provide a reproducible worked example, code, dataset, or detailed decision protocol for choosing priors [@Hackenberger2020].
It surveys many applied examples but does not deeply evaluate their model diagnostics, calibration, or robustness [@Hackenberger2020].
It does not address automated research-agent workflows, graph data models, or proposition-level evidence representations.

## Model / Tool Availability

No reusable model, dataset, or new software artifact is released by the article [@Hackenberger2020].
The paper points readers to existing tools, especially R and Python packages and Bayesian engines such as Stan, JAGS, and OpenBUGS [@Hackenberger2020].

## Follow-up

Read Thompson and Semma (2020) for a worked Bayesian meta-analysis demonstration with R code in adolescent development research [@Hackenberger2020].
Inspect Pappalardo et al. (2020) for a domain comparison of traditional and Bayesian ecological meta-analysis under substantial among-study variation [@Hackenberger2020].
Prototype a Science aggregation node that records posterior effect distributions, heterogeneity uncertainty, model weights, and sensitivity-analysis deltas as first-class graph properties.

---
type: paper
title: Scalable Bayesian Structure Learning for Gaussian Graphical Models Using Marginal
  Pseudo-likelihood
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Mohammadi2025
ontology_terms: []
source_refs:
- cite:Mohammadi2025
related:
- question:0002-evidence-payload-schema
- question:0010-causal-graph-construction-pipeline
---

# Scalable Bayesian Structure Learning for Gaussian Graphical Models Using Marginal Pseudo-likelihood

- **Authors:** Reza Mohammadi, Marit Schoonhoven, Lucas Vogels, and S. Ilker Birbil
- **Year:** 2025
- **Journal/Venue:** arXiv
- **DOI/URL:** https://arxiv.org/abs/2307.00127
- **BibTeX key:** Mohammadi2025
- **Source:** PDF

## Key Contribution

Mohammadi et al. develop scalable Bayesian structure learning for Gaussian graphical models by targeting the graph posterior directly using a marginal pseudo-likelihood approximation [@Mohammadi2025].
The key contribution is graph-space posterior exploration at larger scale without sampling precision matrices at every iteration.

## Methods

The framework integrates out the precision matrix, approximates the marginal likelihood with marginal pseudo-likelihood, and uses birth-death and reversible-jump MCMC algorithms over graph space.
The paper provides posterior concentration, convergence, and graph selection consistency arguments, plus simulation and gene-expression applications.

## Key Findings

The paper reports substantial computational gains over state-of-the-art Bayesian GGM structure-learning methods while retaining graph recovery performance and uncertainty quantification [@Mohammadi2025].
It emphasizes edge inclusion probabilities and graph characteristics as posterior summaries.

## Relevance

Science needs to distinguish graph posterior summaries from point graph estimates.
A scalable approximation can make large graph uncertainty feasible, but its pseudo-likelihood assumption and graph prior should be represented explicitly.
This strengthens the need for `approximate_likelihood`, `graph_prior`, `edge_inclusion_probability`, and `posterior_summary_role` fields.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Marginal pseudo-likelihood | approximation provenance | Affects calibration of graph posterior. |
| Birth-death / RJ MCMC | posterior sampler | Sampling method and convergence diagnostics matter. |
| Edge inclusion probability | graph posterior summary | Should not be confused with causal confidence. |
| Graph prior | prior provenance | Encodes structural assumptions. |

## Limitations

The model concerns undirected Gaussian graphical models, so output edges are conditional-dependence evidence, not causal edges.
Pseudo-likelihood improves scalability but remains an approximation.
Graph posterior summaries can be overinterpreted if convergence and prior sensitivity are not tracked.

## Model / Tool Availability

The PDF reports implementation in the R package `BDgraph`.

## Follow-up

Represent edge inclusion probabilities as posterior graph features with sampler, prior, convergence, and approximation metadata.

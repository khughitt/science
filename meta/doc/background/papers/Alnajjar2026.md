---
id: "paper:Alnajjar2026"
type: "paper"
title: "A Fast Integrative Clustering and Feature Selection Approach for High-Dimensional Multiview Data"
status: "active"
ontology_terms: []
datasets: []
source_refs:
  - "cite:Alnajjar2026"
related:
  - "question:01-evidence-payload-schema"
  - "question:03-source-and-pipeline-provenance"
created: "2026-05-06"
updated: "2026-05-06"
---

# A Fast Integrative Clustering and Feature Selection Approach for High-Dimensional Multiview Data

- **Authors:** Abdalkarim Alnajjar, Helen Bian, and Zihang Lu
- **Year:** 2026
- **Journal/Venue:** Statistical Methods in Medical Research
- **DOI/URL:** https://doi.org/10.1177/09622802251406584
- **BibTeX key:** Alnajjar2026
- **Source:** PDF

## Key Contribution

Alnajjar et al. propose iClusterVB, a variational Bayesian approach for integrative clustering and feature selection in high-dimensional multiview data [@Alnajjar2026].
The contribution is a scalable model-based clustering method for mixed continuous, categorical, and count views.

## Methods

The method uses a finite mixture model with latent cluster memberships and feature-relevance indicators.
It supports mixed data types from exponential-family distributions and uses variational Bayesian inference to approximate the posterior distribution.
The paper evaluates iClusterVB in simulations and real biomedical studies, with an R package and tutorial.

## Key Findings

The paper reports favorable clustering and feature-selection performance compared with competing integrative clustering methods [@Alnajjar2026].
It demonstrates use cases where selected features and inferred cancer subtypes are associated with distinct survival probabilities.

## Relevance

Science should represent clustering and feature-selection outputs as typed integration artifacts, not as direct evidence for mechanistic or causal propositions.
Cluster labels, feature relevance, posterior uncertainty, data-view coverage, and mixed-type likelihood assumptions are all part of the evidence payload.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Integrative clustering | typed synthesis node | Produces subtype hypotheses and prioritization evidence. |
| Feature relevance indicators | selected-feature evidence | Selection rule and posterior uncertainty are load-bearing. |
| Multiview mixed data | source/pipeline scope | Each view has distribution and missingness semantics. |
| Variational posterior | approximate uncertainty | Approximation status should be explicit. |

## Limitations

Cluster assignments and selected features are exploratory unless validated externally.
Variational inference can understate posterior uncertainty.
The finite mixture and conditional-independence assumptions should be recorded before using clusters to update biological propositions.

## Model / Tool Availability

The PDF reports an R package named `iClusterVB`.

## Follow-up

Add clustering and feature-selection synthesis node types with fields for views, distributions, cluster count, relevance posterior, validation role, and downstream survival or phenotype association.

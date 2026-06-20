---
type: paper
title: Bayesian Data Integration and Variable Selection for Pan-Cancer Survival Prediction
  Using Protein Expression Data
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Maity2020
ontology_terms: []
source_refs:
- cite:Maity2020
related:
- question:0002-evidence-payload-schema
- question:0004-source-and-pipeline-provenance
---

# Bayesian Data Integration and Variable Selection for Pan-Cancer Survival Prediction Using Protein Expression Data

- **Authors:** Arnab Kumar Maity, Anirban Bhattacharya, Bani K. Mallick, and Veerabhadran Baladandayuthapani
- **Year:** 2020
- **Journal/Venue:** Biometrics
- **DOI/URL:** https://doi.org/10.1111/biom.13132
- **BibTeX key:** Maity2020
- **Source:** PDF

## Key Contribution

Maity et al. develop Bayesian hierarchical survival models for pan-cancer protein-expression data, combining data integration, variable selection, censored survival outcomes, and cross-tumor borrowing of strength [@Maity2020].
The central contribution is an integrative model that links tumor groups through correlated prior structure while retaining tumor-specific survival regression.

## Methods

The paper uses hierarchical Bayesian accelerated failure time survival models with sparse horseshoe priors over regression coefficients.
Tumor groups borrow strength through a correlation structure among prior distributions.
Posterior inference supports survival prediction and selection of major proteomic drivers using TCPA reverse-phase protein array data.

## Key Findings

The paper argues that integrative hierarchical modeling can improve survival prediction and variable selection compared with separate tumor-group analyses [@Maity2020].
It frames protein-expression integration as a way to find both shared and tumor-specific prognostic structure.

## Relevance

This paper adds a supervised predictive integration pattern to Science's evidence payload schema.
It shows that an evidence artifact may include a predictive target, censoring model, shrinkage prior, group borrowing structure, and variable-selection rule.
These are distinct from graph edge evidence but still affect scientific belief updates.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| AFT survival model | typed predictive synthesis | Evidence target is survival prediction, not causal effect by default. |
| Horseshoe prior | sparsity / prior provenance | Variable selection depends on shrinkage assumptions. |
| Correlated priors across tumors | source/group dependence | Borrowing strength induces dependence across group-specific claims. |
| TCPA data | source dataset | Requires provenance and population scope. |

## Limitations

The model is predictive and associative unless causal assumptions are added.
Censoring assumptions, prior choices, and tumor-group exchangeability are load-bearing.
Variable selection from posterior samples can be sensitive to thresholding and model specification.

## Model / Tool Availability

The PDF reports an R package named `hsaft`.
Package maintenance status and license were not checked in this pass.

## Follow-up

Add predictive-integration payload fields for outcome target, censoring model, shrinkage prior, group-borrowing structure, and variable-selection decision rule.

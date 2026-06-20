---
type: paper
title: 'Causal Models and Learning from Data: Integrating Causal Modeling and Statistical
  Estimation'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Petersen2014
ontology_terms: []
source_refs:
- cite:Petersen2014
related:
- question:0003-causal-synthesis-guardrails
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
---

# Causal Models and Learning from Data: Integrating Causal Modeling and Statistical Estimation

- **Authors:** Maya L. Petersen and Mark J. van der Laan
- **Year:** 2014
- **Journal:** Epidemiology
- **DOI/URL:** https://doi.org/10.1097/EDE.0000000000000078
- **BibTeX key:** Petersen2014
- **Source:** PDF

## Key Contribution

Petersen and van der Laan provide a practical roadmap for integrating formal causal modeling with statistical estimation in epidemiology [@Petersen2014].
The central contribution is a seven-step separation between causal model, observed data, target causal quantity, identification, statistical estimand, estimation, and interpretation.
For Science, the paper is a foundational guardrail: causal graph construction should not jump directly from data to a causal edge.

## Methods

The paper is a methodological tutorial and perspective.
It explains structural causal models, causal graphs, counterfactual quantities, observed-data links, identification, statistical estimation, and interpretation.
The workflow explicitly asks investigators to encode background knowledge and its limits, then translate a scientific question into a counterfactual target before estimating anything.

## Key Findings

The paper argues that formal causal thinking helps sharpen scientific questions, expose assumptions, distinguish causal inference from statistical estimation, and respect the limits of available data [@Petersen2014].
It emphasizes that causal graphs can encode uncertainty and assumptions through included and omitted arrows, independence restrictions, and links between causal variables and observed measurements.
It also warns that causal models do not make assumptions true; they make assumptions visible enough to assess.

## Relevance

This paper directly strengthens H04.
Science's graph should separate four layers: domain causal model, observed data, identified estimand, and statistical estimator.
Evidence payloads should therefore carry `causal_model_ref`, `observed_data_link`, `counterfactual_target`, `identification_assumptions`, `statistical_estimand`, and `estimator_diagnostics` rather than treating estimated associations as causal edges.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Structural causal model | causal graph layer | Encodes background knowledge and limits. |
| Observed-data link | measurement / sampling payload | Connects graph variables to available data. |
| Counterfactual quantity | causal estimand | Defines what the graph update claims. |
| Identification | causal guardrail | Determines whether data can answer the causal question. |
| Statistical estimation | evidence computation | Comes after identification, not before. |

## Limitations

The paper is a conceptual roadmap rather than an empirical benchmark.
It focuses on epidemiology, though the causal-modeling workflow is broadly applicable.
It does not provide an automated schema for representing the full roadmap in a knowledge graph.

## Model / Tool Availability

No standalone software is released with the paper.

## Follow-up

Use this roadmap as the structural backbone for `t026`: causal updates require causal target, observed-data link, identification assumptions, and estimator provenance.

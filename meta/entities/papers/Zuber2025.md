---
kind: paper
title: Bayesian Causal Graphical Model for Joint Mendelian Randomization Analysis
  of Multiple Exposures and Outcomes
status: active
created: '2026-05-06'
updated: '2026-07-08'
id: paper:Zuber2025
ontology_terms: []
source_refs:
- cite:Zuber2025
related:
- question:0003-causal-synthesis-guardrails
---

# Bayesian Causal Graphical Model for Joint Mendelian Randomization Analysis of Multiple Exposures and Outcomes

- **Authors:** Verena Zuber, Toinet Cronje, Na Cai, Dipender Gill, and Leonardo Bottolo
- **Year:** 2025
- **Journal:** The American Journal of Human Genetics
- **DOI/URL:** https://doi.org/10.1016/j.ajhg.2025.03.005
- **BibTeX key:** Zuber2025
- **Source:** PDF

## Key Contribution

Zuber et al. introduce MrDAG, a Bayesian causal graphical model for summary-level Mendelian randomization across multiple exposures and outcomes [@Zuber2025].
The contribution is joint modeling of dependencies within exposures, within outcomes, and from exposures to outcomes before estimating causal effects.

## Methods

MrDAG combines genetic instruments, structure learning over exposures and outcomes, and interventional calculus to estimate causal effects.
The method assumes the direction from exposures to outcomes is known and excludes reverse causation from outcomes to exposures.
It is evaluated in simulations and a mental-health application involving lifestyle/behavioral exposures and mental-health phenotypes.

## Key Findings

The paper reports that MrDAG outperforms compared MR and causal graphical model approaches in simulation settings [@Zuber2025].
In the mental-health application, it highlights education and smoking as important intervention points and identifies complex pathways involving smoking, schizophrenia liability, and cognition.
The paper argues that these pathways require modeling multiple exposures and outcomes jointly.

## Relevance

This paper is a concrete example of Bayesian causal graph synthesis with constrained directionality.
Science should represent instrument assumptions, exposure/outcome direction constraints, graph uncertainty, interventional estimand, and summary-statistic provenance when using MR evidence.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Genetic instruments | instrumental-variable evidence | Requires validity assumptions. |
| Exposure/outcome graph | constrained causal graph | Directionality is assumed, not learned. |
| Graph uncertainty | posterior graph payload | Fits continuous belief design. |
| Interventional calculus | causal effect computation | Needs estimand provenance. |

## Limitations

MrDAG assumes no reverse causation from outcomes to exposures.
Mendelian randomization depends on instrument validity and pleiotropy handling.
The real-data application remains observational and model-dependent.

## Model / Tool Availability

Code availability was checked on 2026-07-08.
The article and supplemental material point to the MrDAG R package at `https://github.com/lb664/MrDAG`.
The GitHub API showed a public R repository, GPL-2.0 license, not archived, last pushed 2025-04-04.
The repository README describes MrDAG version 0.1.1 and states that it includes the real-data application data and run instructions.

## Follow-up

Add MR-specific causal synthesis fields: `instrument_set`, `instrument_validity_assumptions`, `pleiotropy_model`, `direction_constraint`, and `graph_posterior`.

---
id: paper:VanWonderen2024
type: paper
title: 'Bayesian Evidence Synthesis as a Flexible Alternative to Meta-Analysis: A
  Simulation Study and Empirical Demonstration'
status: active
ontology_terms: []
source_refs:
- cite:VanWonderen2024
related:
- topic:bayesian-methods-continuous-belief
created: '2026-05-05'
updated: '2026-05-05'
---

# Bayesian Evidence Synthesis as a Flexible Alternative to Meta-Analysis: A Simulation Study and Empirical Demonstration

- **Authors:** Elise van Wonderen, Mariëlle Zondervan-Zwijnenburg, and Irene Klugkist
- **Year:** 2024
- **Journal:** Behavior Research Methods
- **DOI/URL:** https://doi.org/10.3758/s13428-024-02350-2
- **BibTeX key:** VanWonderen2024
- **Source:** PDF

## Key Contribution

Van Wonderen, Zondervan-Zwijnenburg, and Klugkist position Bayesian Evidence Synthesis (BES) as a flexible alternative when conventional meta-analysis is difficult or impossible because studies are too heterogeneous to pool effect sizes [@VanWonderen2024].
The paper clarifies the different research question BES answers and uses simulation plus an empirical demonstration to show where BES and meta-analysis agree or diverge.

## Methods

The paper formulates study-specific informative hypotheses, evaluates them with Bayes factors, and aggregates study-level support into posterior model probabilities.
The simulation varies effect size, sample size, between-study variation, number of studies, and alternative hypotheses.
The empirical demonstration reanalyzes a meta-analysis on statistical learning in people with and without developmental language disorder.

## Key Findings

BES behaves similarly to meta-analysis in many settings: support for the correct hypothesis increases with larger sample sizes and more studies.
Major divergences occur when studies are underpowered and when the true parameter is on a hypothesis boundary.
BES does not solve power problems by pooling data; if most individual studies are underpowered, aggregating them can strengthen support for the null or unconstrained alternative.
The authors recommend using BES when effect sizes are not meaningfully comparable and emphasize inspecting study-level evidence rather than only the aggregate result.

## Relevance

This paper is a strong design warning for Science's evidence aggregation.
Graph-level aggregation should not blindly increase confidence because many weak studies point in the same direction; the aggregation rule must know whether those studies are underpowered, incomparable, or testing boundary-adjacent hypotheses.
It also supports representing synthesis intent explicitly: pooling for estimation, BES for proposition support, and conceptual replication for robustness are different graph operations.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| BES | hypothesis-level evidence synthesis | Useful when effect sizes cannot be pooled. |
| Posterior model probability | normalized proposition support among alternatives | Should carry the tested hypothesis set. |
| Underpowered studies | fragile evidence edge source | Repeated weak evidence can mislead. |
| Boundary hypothesis | ambiguous proposition threshold | Boundary cases should be marked high-uncertainty. |

## Limitations

The paper focuses on psychological-style simulation settings and does not solve dependency among studies.
It also emphasizes that BES does not estimate effect sizes or heterogeneity, so it cannot replace meta-analysis where those are the actual questions.

## Model / Tool Availability

The paper reports R scripts, simulated datasets, and supplementary figures available on OSF at `https://osf.io/gbtyk/`.

## Follow-up

Science should make synthesis nodes type-specific: effect-size synthesis, hypothesis-support synthesis, and conceptual-replication synthesis should not be conflated.
Evidence aggregation should retain per-study support values so users can inspect whether the aggregate is driven by one strong study or many fragile ones.

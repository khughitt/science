---
kind: paper
title: 'Causal Meta-Analysis: Rethinking the Foundations of Evidence-Based Medicine'
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Berenfeld2026
ontology_terms: []
source_refs:
- cite:Berenfeld2026
related:
- topic:bayesian-methods-continuous-belief
---

# Causal Meta-Analysis: Rethinking the Foundations of Evidence-Based Medicine

- **Authors:** Clément Berenfeld, Ahmed Boughdiri, Bénédicte Colnet, Wouter van Amsterdam, Aurélien Bellet, Rémi Khellaf, Erwan Scornet, and Julie Josse
- **Year:** 2026
- **Journal:** arXiv preprint
- **DOI/URL:** https://arxiv.org/abs/2505.20168
- **BibTeX key:** Berenfeld2026
- **Source:** PDF

## Key Contribution

Berenfeld et al. argue that conventional fixed- and random-effects meta-analysis often lacks a clear causal estimand and target population [@Berenfeld2026].
They propose causal aggregation formulas for aggregate trial data, showing that classical estimators have causal interpretations for risk differences but can fail for nonlinear measures such as risk ratios and odds ratios.

## Methods

The paper formalizes meta-analysis in a causal framework with trial populations, treatment arms, potential outcomes, and target populations defined as convex combinations of trial populations.
It derives arm-based causal aggregation formulas that aggregate treated and control outcome risks separately before applying the causal contrast.
The authors compare classical and causal estimators in simulations and apply the methods to hundreds of published Cochrane meta-analyses.

## Key Findings

For linear contrasts such as risk difference, classical meta-analysis can admit a causal interpretation under certain weighting conditions.
For nonlinear contrasts, averaging study-specific risk ratios or odds ratios can target no well-defined population-level causal effect.
In simulations and real examples, classical and causal approaches often align but can diverge enough to reverse substantive conclusions, including cases where a treatment appears beneficial conventionally but harmful under the causal estimand.
The method is implemented in the `CaMeA` R package.

## Relevance

This paper is central to Science's causal graph ambitions.
It shows that an evidence synthesis node must record not just "effect" and "confidence" but the estimand, target population, causal contrast, and aggregation rule.
It also supports separating statistical synthesis from causal interpretation: an aggregated effect estimate is not automatically a causal claim.
For graph construction, this means causal edges should require explicit estimand metadata and target-population assumptions before evidence updates are allowed to strengthen a causal proposition.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Target population | scope / applicability metadata | Needed for causal proposition identity. |
| Causal contrast | proposition estimand | Risk difference, risk ratio, and odds ratio are not interchangeable. |
| Arm-based aggregation | evidence synthesis operator | May be safer for aggregate trial data. |
| Non-collapsibility | aggregation failure mode | Should trigger warnings on causal evidence edges. |

## Limitations

The paper is a recent preprint and should be treated as methodologically important but not yet settled consensus.
Its framework is specialized to trial-style aggregate data and binary outcomes, although the conceptual lesson generalizes.
It depends on assumptions such as no study effect / response consistency that may be strong when only aggregate data are available.

## Model / Tool Availability

The authors report an R package, `CaMeA`, available on CRAN.

## Follow-up

Science should treat causal estimands as first-class graph entities or proposition fields.
Evidence aggregation should reject or warn on causal edge updates when the source effect measure is non-collapsible and the target population is unspecified.

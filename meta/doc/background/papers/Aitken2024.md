---
id: "paper:Aitken2024"
type: "paper"
title: "The Role of the Bayes Factor in the Evaluation of Evidence"
status: "active"
ontology_terms: []
datasets: []
source_refs:
  - "cite:Aitken2024"
related:
  - "topic:bayesian-methods-continuous-belief"
created: "2026-05-05"
updated: "2026-05-05"
---

# The Role of the Bayes Factor in the Evaluation of Evidence

- **Authors:** Colin Aitken, Franco Taroni, and Silvia Bozza
- **Year:** 2024
- **Journal:** Annual Review of Statistics and Its Application
- **DOI/URL:** https://doi.org/10.1146/annurev-statistics-040522-101020
- **BibTeX key:** Aitken2024
- **Source:** PDF

## Key Contribution

Aitken, Taroni, and Bozza review the Bayes factor as a coherent measure of evidential value, with forensic evidence as the motivating domain [@Aitken2024].
The paper is valuable for Science because it treats evidence evaluation as comparison between explicit competing propositions, not as isolated support for a single claim.

## Methods

The paper is a methodological review.
It defines the Bayes factor as the multiplier that converts prior odds into posterior odds, surveys its logical and philosophical properties, and discusses Bayesian networks for complex bodies of evidence.
It also reviews controversies around reporting uncertainty in Bayes factors, including interval-valued reporting, sensitivity analysis, calibration, and model-dependence.

## Key Findings

The review argues that evidence has meaning only relative to at least one alternative proposition.
Bayes factors satisfy desirable properties for evidential value, including symmetry, logical coherence, and multiplicative combination for multiple items of evidence.
Bayesian networks extend the same evidential logic to interacting, dependent, or multi-item evidence structures.
The authors defend single-number Bayes-factor reporting against interval-reporting proposals, but still emphasize sensitivity analyses and transparency about assumptions.

## Relevance

This paper sharpens Science's evidence-edge semantics.
An edge labeled "supports" should specify support for which proposition over which alternative, because a Bayes factor is contrastive rather than absolute.
The Bayesian-network discussion also points toward representing evidence dependencies explicitly instead of multiplying edge weights as if all evidence were independent.
The paper reinforces D-003's continuous-belief stance while warning that communication and calibration are separate obligations.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Prosecution and defense propositions | competing proposition set | Evidence support is meaningful only over alternatives. |
| Bayes factor / likelihood ratio | evidence edge strength | Edge weight should encode a comparison, not a free-floating score. |
| Bayesian network | causal/evidential graph | Dependencies among evidence items need graph structure. |
| Sensitivity analysis | uncertainty audit | Assumption sensitivity should be part of evidence metadata. |

## Limitations

The review is forensic-science oriented, so its legal-role distinctions do not transfer directly to research-tool workflows.
Its defense of single-number Bayes factors is useful but may understate the UX need for communicating model and prior uncertainty to scientific users.

## Model / Tool Availability

No reusable software artifact is central to the paper.

## Follow-up

Science should consider adding explicit `comparison_target` or `alternative_proposition` metadata to evidence edges.
It should also distinguish evidential-value computation from decision thresholds, mirroring the paper's separation between expert evaluation and factfinder decision.

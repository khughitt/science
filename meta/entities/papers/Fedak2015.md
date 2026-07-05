---
kind: paper
title: 'Applying the Bradford Hill Criteria in the 21st Century: How Data Integration
  Has Changed Causal Inference in Molecular Epidemiology'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Fedak2015
ontology_terms: []
source_refs:
- cite:Fedak2015
related:
- question:0003-causal-synthesis-guardrails
---

# Applying the Bradford Hill Criteria in the 21st Century

- **Authors:** Kristen M. Fedak, Autumn Bernal, Zachary A. Capshaw, and Sherilyn Gross
- **Year:** 2015
- **Journal:** Emerging Themes in Epidemiology
- **DOI/URL:** https://doi.org/10.1186/s12982-015-0037-4
- **BibTeX key:** Fedak2015
- **Source:** PDF

## Key Contribution

Fedak et al. reinterpret the Bradford Hill viewpoints for causal inference in an era of molecular, genomic, toxicological, biomarker, and mechanistic evidence [@Fedak2015].
The core contribution is to show that causal evidence integration must combine heterogeneous evidence streams rather than repeat only one classical epidemiologic pattern.

## Methods

The paper is an analytic perspective.
It walks through Hill's criteria and discusses how modern molecular epidemiology changes the interpretation of strength, consistency, specificity, temporality, biological gradient, plausibility, coherence, experiment, and analogy.
It uses examples from exposure-response and disease-causation settings to show how mechanistic and molecular evidence can support or complicate causal interpretation.

## Key Findings

Modern causal assessment needs context-sensitive interpretation of evidence strength.
Statistical significance alone is not sufficient, and small effects can still be meaningful when embedded in coherent mechanistic evidence [@Fedak2015].
Consistency can now mean convergence across epidemiology, toxicology, molecular biology, and mechanistic experiments, not only repeated observational associations.
Specificity is weaker as a one-exposure/one-disease criterion but can be useful when specific molecular mechanisms are identified.

## Relevance

This paper complements the formal causal-graph literature by emphasizing evidential pluralism.
Science should represent causal evidence as a typed bundle: epidemiologic association, molecular mechanism, exposure-response gradient, temporal ordering, experimental perturbation, and analogy may each bear on a causal proposition differently.
This supports typed synthesis nodes and H03 reason codes for `mechanism-missing`, `temporal-order-unclear`, and `cross-stream-incoherence`.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Bradford Hill viewpoints | causal evidence facets | Useful as qualitative causal-synthesis fields. |
| Data integration | heterogeneous causal evidence synthesis | Multiple streams jointly bear on causal standing. |
| Mechanistic toxicology | mechanism evidence node | Can support plausibility and coherence. |
| Consistency across disciplines | cross-stream agreement | Stronger than repeated same-design associations. |

## Limitations

The paper is not a formal identification framework.
It does not provide quantitative weighting rules for integrating the criteria.
The Bradford Hill criteria can be misused as a checklist if not tied to explicit causal estimands.

## Model / Tool Availability

No software artifact is released with the paper.

## Follow-up

Consider adding a qualitative causal-evidence facet vocabulary to `t026`, separate from quantitative estimand guardrails.

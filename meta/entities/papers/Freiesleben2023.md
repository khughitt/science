---
kind: paper
title: 'Beyond Generalization: A Theory of Robustness in Machine Learning'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Freiesleben2023
ontology_terms: []
source_refs:
- cite:Freiesleben2023
related:
- question:0013-robustness-reproducibility-evaluation
- question:0002-evidence-payload-schema
- topic:analytic-flexibility-and-replication
---

# Beyond Generalization: A Theory of Robustness in Machine Learning

- **Authors:** Timo Freiesleben and Thomas Grote
- **Year:** 2023
- **Journal/Venue:** Synthese
- **DOI/URL:** https://doi.org/10.1007/s11229-023-04334-9
- **BibTeX key:** Freiesleben2023
- **Source:** PDF

## Key Contribution

Freiesleben and Grote provide a conceptual theory of robustness for machine learning [@Freiesleben2023].
They define robustness as the relative stability of a specified robustness target under relevant interventions on a robustness modifier.
The useful move for Science is that "robustness" becomes a typed relation, not a generic quality label.

## Methods

The paper is a conceptual and philosophical analysis.
It compares robustness in ML with robustness analysis in science and computer simulation, then proposes target/modifier/domain/tolerance machinery for classifying robustness claims.
It also distinguishes robustness from extrapolation, i.i.d. generalization, out-of-distribution generalization, and uncertainty quantification.

## Key Findings

Robustness has at least four load-bearing components: robustness target, robustness modifier, modifier domain, and target tolerance.
Deployment performance, individual predictions, and explanations can each be robustness targets.
Training data, deployment distribution, feature values, algorithms, hyperparameters, and task conceptualization can function as modifiers when they causally precede the target.
The paper argues that robustness presupposes ordinary i.i.d. generalization but goes beyond it because it asks whether a target remains stable under specified shifts or interventions.

## Relevance

This directly informs Science's evidence payload schema.
A claim like "model X is robust" should not update graph confidence unless it records what target is stable, what modifier changed, what intervention/domain was considered, and what tolerance defined stability.
The same pattern applies beyond ML: reproducibility and robustness claims in scientific workflows should preserve evaluation target, perturbation/intervention, tolerance, and validation role.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Robustness target | evaluation target | Could be proposition, model, prediction, explanation, pipeline result, or graph update. |
| Robustness modifier | perturbation/intervention source | Distribution shift, data split, preprocessing choice, analyst path, prompt, tool version, or population. |
| Modifier domain | evaluation scope | Defines what changes were actually tested. |
| Target tolerance | success criterion | Prevents vague "robust" labels from becoming scalar support. |

## Limitations

The paper is conceptual rather than empirical.
It does not provide a ready-made metric registry or implementation schema, so Science must translate the target/modifier framework into graph fields and validation rules.

## Model / Tool Availability

No reusable software artifact is central to the paper.

## Follow-up

Add robustness evaluation payload fields: `robustness_target`, `robustness_modifier`, `modifier_domain`, `intervention_type`, `target_tolerance`, and `robustness_result`.

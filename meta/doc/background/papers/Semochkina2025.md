---
id: paper:Semochkina2025
type: paper
title: 'Incorporating Additional Evidence as Prior Information to Resolve Non-Identifiability
  in Bayesian Disease Model Calibration: A Tutorial'
status: active
ontology_terms: []
source_refs:
- cite:Semochkina2025
related:
- question:01-evidence-payload-schema
created: '2026-05-05'
updated: '2026-05-05'
---

# Incorporating Additional Evidence as Prior Information to Resolve Non-Identifiability in Bayesian Disease Model Calibration: A Tutorial

- **Authors:** Daria Semochkina and Cathal D. Walsh
- **Year:** 2025
- **Journal:** Statistics in Medicine
- **DOI/URL:** https://doi.org/10.1002/sim.70039
- **BibTeX key:** Semochkina2025
- **Source:** PDF

## Key Contribution

Semochkina and Walsh show how informative priors derived from expert knowledge or external data can help resolve non-identifiability in Bayesian disease-model calibration [@Semochkina2025].
The core lesson for Science is that prior information is not merely subjective decoration; it can be the difference between an identifiable and non-identifiable model.

## Methods

The paper is a tutorial using two disease-modeling examples: a simple susceptible-infected-susceptible model and a more complex HPV/cervical-cancer agent-based model.
It explains Bayesian calibration with MCMC, diagnoses non-identifiability through broad/flat posteriors and chain behavior, and demonstrates how informative priors can constrain otherwise degenerate parameter spaces.
The authors emphasize sensitivity analysis over prior choices.

## Key Findings

Non-identifiability arises when multiple parameter settings produce indistinguishable model outputs.
In disease models, this can occur because population-level data cannot distinguish paired mechanisms such as fast progression plus fast recovery versus slow progression plus slow recovery.
Informative priors can improve convergence, constrain parameter space, and improve interpretability, but results may become strongly prior-dependent.
Sensitivity analysis is essential when priors resolve non-identifiability.

## Relevance

Science's evidence graph should represent identifiability as a first-class property of models, not as an afterthought.
If a proposition depends on a model parameter that is non-identifiable without external evidence, the evidence payload should record the source and strength of prior information that makes the inference possible.
This directly informs `[t022]`: prior provenance and sensitivity deltas are mandatory for model-based evidence updates in underidentified settings.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Non-identifiability | model/evidence failure mode | Should trigger uncertainty or revisit flags. |
| Informative prior | prior evidence source | Needs provenance and sensitivity checks. |
| Calibration | model-fitting workflow | Output should include diagnostics, not just parameters. |
| Sensitivity analysis | evidence robustness metadata | Should affect confidence and attention weights. |

## Limitations

The tutorial focuses on disease models, so the exact examples do not transfer directly to every Science domain.
Informative priors can resolve non-identifiability only when the prior information is itself credible.
The paper's examples illustrate practical behavior but do not provide a general automated identifiability checker.

## Model / Tool Availability

The paper discusses MCMC implementation concepts and common tools such as R, Stan, and WinBUGS, but no dedicated reusable package is central to the summary.

## Follow-up

Add `non-identifiability` and `prior-resolved-identifiability` as candidate reason codes for H01 revisiting.
Evidence payloads for calibrated models should include prior source, identifiability diagnostics, chain diagnostics, and sensitivity-analysis deltas.

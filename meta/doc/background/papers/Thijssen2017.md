---
id: paper:Thijssen2017
type: paper
title: Bayesian Data Integration for Quantifying the Contribution of Diverse Measurements
  to Parameter Estimates
status: active
ontology_terms: []
source_refs:
- cite:Thijssen2017
related: []
created: '2026-05-05'
updated: '2026-05-05'
---

# Bayesian Data Integration for Quantifying the Contribution of Diverse Measurements to Parameter Estimates

- **Authors:** Bram Thijssen, Tjeerd M. H. Dijkstra, Tom Heskes, and Lodewyk F. A. Wessels
- **Year:** 2017
- **Journal:** Bioinformatics
- **DOI/URL:** https://doi.org/10.1093/bioinformatics/btx666
- **BibTeX key:** Thijssen2017
- **Source:** PDF

## Key Contribution

Thijssen et al. show that Bayesian parameter inference can integrate diverse biological measurements into a single mechanistic model while quantifying how much each measurement type reduces posterior uncertainty [@Thijssen2017].
The paper's central contribution is not only tighter parameter estimation, but a workflow for discovering when jointly fitted evidence exposes model deficiencies that are invisible under any single measurement type [@Thijssen2017].
The case study uses a budding yeast cell-cycle ODE model and integrates literature-derived priors, relative mRNA time courses, absolute mRNA concentrations, and absolute protein concentrations [@Thijssen2017].

## Methods

The authors construct a sparse ODE model for cyclic expression of yeast cyclins CLN3, CLN2, CLB5, and CLB2, with explicit mRNA and protein species and rate equations for transcription, translation, degradation, and inhibitory regulation [@Thijssen2017].
They specify the model in physical units of concentration and time so that inferred kinetic rates can be compared with independent measurements [@Thijssen2017].
Prior distributions are uniform on a log10 scale, with bounds derived from biochemical limits or published datasets such as protein concentration, mRNA concentration, elongation-rate, footprinting, and cell-size measurements [@Thijssen2017].
The main inference data combine relative mRNA time-course microarray data from synchronized cells with absolute steady-state mRNA and protein concentration measurements from multiple studies [@Thijssen2017].
Relative time-course observations are modeled as log ratios against the modeled time-average transcript concentration, while absolute concentrations are modeled on a log10 scale against time-averaged model trajectories [@Thijssen2017].
The likelihood uses a t-distribution with three degrees of freedom to make the fit robust to outlying observations [@Thijssen2017].
Posterior distributions are sampled with parallel-tempered MCMC using BCM, automated parameter blocking, adaptive proposal scaling, and convergence checks based on traces, autocorrelation, and prior-to-posterior round trips [@Thijssen2017].
Model adequacy is assessed with posterior predictive checks and coefficients of determination, and inferred kinetic parameters are compared against independent validation measurements for mRNA degradation, transcription, and translation rates [@Thijssen2017].

## Key Findings

The initial sparse model could not explain the relative cyclin mRNA time courses, with median R2 values only about 0.07 to 0.19 across the four cyclins [@Thijssen2017].
Iterative model refinement added HCM1, YOX1 negative feedback, and NDD1 degradation by the anaphase-promoting complex, producing a model that fit all four cyclin expression patterns more adequately [@Thijssen2017].
Steady-state absolute concentration data alone were weakly informative for most dynamic parameters, but they substantially reduced uncertainty when combined with relative time-course data [@Thijssen2017].
With all data types included, 45 of 54 parameters had 90% posterior confidence intervals smaller than half the prior range, compared with 14 parameters for time-course data alone and one parameter for steady-state data alone [@Thijssen2017].
Some parameters, such as the CLN3 degradation rate, were already constrained by relative time-course data, while others, such as translation rate and transcription rates, required the joint information from relative dynamics and absolute scale [@Thijssen2017].
Independent validation supported the inferred mRNA degradation scale and most transcription-rate estimates, with seven of eight transcription measurements inside the 90% confidence interval and the remaining one within the same order of magnitude [@Thijssen2017].
The inferred translation rate under all data was roughly two orders of magnitude higher than a polysome-profiling validation estimate, suggesting a missing regulatory mechanism rather than merely noisy data [@Thijssen2017].
The translation-rate mismatch arose only when relative timing and absolute concentration constraints were combined, demonstrating that multi-source integration can falsify or stress-test a model in ways unavailable to isolated evidence streams [@Thijssen2017].

## Relevance

This paper is directly relevant to science-meta's evidence aggregation theme because it treats evidence payloads as model-conditioned contributions to posterior uncertainty rather than as interchangeable support counts [@Thijssen2017].
It gives a concrete example of evidence nodes carrying measurement scale, normalization, likelihood form, prior assumptions, validation target, and diagnostics as first-class metadata.
The work supports representing comparison targets explicitly, because relative expression, absolute concentration, and kinetic-rate validation constrain different model quantities even when they concern the same biological system.
It also supports graph workflows where inconsistent integrated evidence triggers causal-graph or mechanism refinement instead of being collapsed into a single aggregate score.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Diverse measurement types | Evidence payload heterogeneity | Relative time courses, absolute concentrations, and validation rates each require distinct observation models. |
| Bayesian prior from literature data | Prior/model assumptions | External datasets enter either as priors or as likelihood terms, so provenance and role must be explicit. |
| Posterior confidence interval shrinkage | Evidence contribution diagnostic | The contribution of evidence is measured by uncertainty reduction under a specified model. |
| Relative time-course likelihood | Comparison target | The estimand is a log ratio against a modeled time average, not an absolute concentration. |
| Absolute steady-state likelihood | Scale anchoring evidence | Absolute measurements constrain concentration scale and make kinetic-rate comparisons possible. |
| Posterior predictive checking | Diagnostics | Evidence integration is evaluated by simulated-data fit, not only parameter summaries. |
| Independent kinetic-rate comparison | External validation node | Held-out measurements test whether inferred parameters correspond to real-world quantities. |
| Translation-rate mismatch | Model deficiency signal | Cross-source constraints can reveal missing mechanisms and motivate graph expansion. |
| Joint posterior over ODE parameters | Continuous belief state | Parameter plausibility is represented as a distribution rather than a binary accepted/rejected claim. |

## Limitations

The workflow is computationally expensive, with the final refined model reportedly requiring about 60 hours to generate 1000 posterior samples [@Thijssen2017].
Scaling is limited by both ODE simulation cost and high-dimensional MCMC difficulty in posterior landscapes with multiple modes and ridges [@Thijssen2017].
The model refinement process was literature-guided and manually iterative, so the paper does not provide an automated causal-graph discovery procedure.
The case study is restricted to a relatively small budding yeast cell-cycle model, and generality to larger biological networks remains constrained by computation [@Thijssen2017].
The independent translation-rate validation depends on estimates from ribosome densities that the authors note should be used cautiously [@Thijssen2017].
Time-course integration across experimental setups requires alignment choices, and timing synchronization can directly affect inferred kinetic rates such as translation [@Thijssen2017].

## Model / Tool Availability

The authors report that the models and inference files are included in the Supplementary information [@Thijssen2017].
They used the BCM software package for Bayesian analysis of computational models, with SBML/CellDesigner model files, prior and likelihood specifications, and a NetCDF archive of pre-processed data included in Supplementary File S1 [@Thijssen2017].

## Follow-up

Use this paper as a template for representing measurement-role fields in Science evidence nodes: prior-only, likelihood/inference, conversion, and held-out validation.
Explore whether Science graph diagnostics should report each evidence source's marginal and joint contribution to posterior uncertainty, not only its direction of support.
Compare this Bayesian ODE integration approach with truth-discovery methods that aggregate claims without explicit mechanistic observation models.

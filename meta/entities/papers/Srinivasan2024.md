---
type: paper
title: Bayesian Evidence Estimation from Posterior Samples with Normalizing Flows
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Srinivasan2024
ontology_terms: []
source_refs:
- cite:Srinivasan2024
related:
- topic:bayesian-methods-continuous-belief
---

# Bayesian Evidence Estimation from Posterior Samples with Normalizing Flows

- **Authors:** Rahul Srinivasan, Marco Crisostomi, Roberto Trotta, Enrico Barausse, and Matteo Breschi
- **Year:** 2024
- **Journal:** Physical Review D
- **DOI/URL:** https://doi.org/10.1103/PhysRevD.110.123007
- **BibTeX key:** Srinivasan2024
- **Source:** PDF

## Key Contribution

Srinivasan et al. introduce `floZ`, a normalizing-flow method for estimating Bayesian evidence and numerical uncertainty from existing samples of an unnormalized posterior [@Srinivasan2024].
The paper matters to Science less as a meta-analysis method and more as an implementation route for scalable Bayes-factor computation when posterior samples already exist.

## Methods

The method trains a normalizing flow to map posterior samples to a tractable latent distribution.
The evidence is estimated through the ratio of the unnormalized posterior density to the learned normalized density, with additional loss terms designed to reduce variation in evidence estimates across samples.
The authors validate the approach on analytically tractable distributions, compare it with nested sampling and a k-nearest-neighbors estimator, and apply it to gravitational-wave ringdown model comparison.

## Key Findings

`floZ` estimates evidence from preexisting posterior samples and can be robust for posteriors with sharp features when representative samples are available.
The paper reports validation up to 15 dimensions for analytically tractable distributions and a high-dimensional Gaussian demonstration up to 200 dimensions.
The authors emphasize remaining high-dimensional limits: the approach still depends on obtaining representative posterior samples and training expressive flows under the curse of dimensionality.

## Relevance

Science's evidence graph needs computational routes for Bayes factors and marginal likelihoods if it represents proposition support quantitatively.
This paper suggests a practical path: posterior-producing workflows could feed a downstream evidence-estimation step, letting the graph store model-comparison evidence without rerunning nested sampling.
For research packages, an evidence-estimation cell could record posterior sample provenance, unnormalized density access, flow training diagnostics, and numerical uncertainty.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Bayesian evidence | model/proposition comparison strength | Could underlie evidence edge weights. |
| Posterior samples | analysis artifact | Samples need provenance and diagnostics in research packages. |
| Normalizing flow estimator | computational evidence evaluator | Candidate backend for scalable evidence estimation. |
| Numerical uncertainty | evidence uncertainty metadata | Edge weights should carry computational error. |

## Limitations

The application domain is physics, not research synthesis.
The method assumes representative posterior samples and access to the unnormalized posterior density, which may not hold for literature-derived evidence.
High-dimensional and complex posterior settings remain challenging.

## Model / Tool Availability

The paper names the method `floZ`.
The summary did not verify the repository or package availability beyond the PDF text [UNVERIFIED].

## Follow-up

Science should treat "computed Bayes factor" as a provenance-rich artifact, not just a scalar.
If Bayesian model comparison becomes part of the tool, research packages should preserve posterior samples, density code, estimator choice, and diagnostics.

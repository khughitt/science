---
id: paper:Gronau2021
type: paper
title: A Primer on Bayesian Model-Averaged Meta-Analysis
status: active
ontology_terms: []
source_refs:
- cite:Gronau2021
related: []
created: '2026-05-05'
updated: '2026-05-05'
---

# A Primer on Bayesian Model-Averaged Meta-Analysis

- **Authors:** Quentin F. Gronau, Daniel W. Heck, Sophie W. Berkhout, Julia M. Haaf, and Eric-Jan Wagenmakers
- **Year:** 2021
- **Journal:** Advances in Methods and Practices in Psychological Science
- **DOI/URL:** https://doi.org/10.1177/25152459211031256
- **BibTeX key:** Gronau2021
- **Source:** PDF

## Key Contribution

Gronau et al. present Bayesian model-averaged meta-analysis as a way to synthesize study results while accounting for uncertainty over whether the evidence is best represented by fixed-effect or random-effects assumptions [@Gronau2021].
The method combines four Bayesian meta-analysis hypotheses: fixed-effect null, fixed-effect alternative, random-effects null, and random-effects alternative [@Gronau2021].
This framing lets analysts ask both whether the overall effect is nonzero and whether there is between-study variability without first committing to a single model class [@Gronau2021].

## Methods

The input data are study-level observed effect sizes and standard errors, typically standardized measures such as Cohen's d, Hedges's g, or Fisher's z [@Gronau2021].
The random-effects model treats each observed effect as drawn around a latent study effect, with latent study effects drawn around an overall mean mu and between-study standard deviation tau [@Gronau2021].
The four hypotheses arise by either fixing mu to zero or assigning it a prior, and either fixing tau to zero or assigning it a prior [@Gronau2021].
The authors recommend, for standardized mean differences, a zero-centered Cauchy prior with scale 1/sqrt(2) as a default prior for mu and an empirically informed Inverse-Gamma(1, 0.15) prior for tau [@Gronau2021].
They compute posterior model probabilities and model-averaged inclusion Bayes factors for effect presence and heterogeneity [@Gronau2021].
They demonstrate the workflow by reanalyzing the 19-lab primary analysis from Verschuere et al.'s registered replication of the Ten Commandments dishonesty effect [@Gronau2021].

## Key Findings

The method represents evidence on a continuous scale through posterior probabilities and Bayes factors rather than forcing all-or-none significance decisions [@Gronau2021].
In the worked example, all three prior specifications favored the fixed-effect null most strongly, followed by the random-effects null [@Gronau2021].
For the default two-sided prior in the example, the model-averaged Bayes factor for an overall effect was approximately BF10 = 0.115, corresponding to moderate evidence for absence of an effect [@Gronau2021].
For the same prior, the model-averaged Bayes factor for heterogeneity was approximately BFrf = 0.189, corresponding to moderate evidence for absence of heterogeneity [@Gronau2021].
Sequential analysis showed how posterior model probabilities can be updated as studies accumulate, with the fixed-effect null gaining plausibility in the example [@Gronau2021].
The paper emphasizes that model-averaged posterior distributions can be computed by weighting hypothesis-specific posteriors by their posterior model probabilities [@Gronau2021].

## Relevance

This paper is directly relevant to Decision D-003 because it operationalizes scientific belief as continuous posterior probability mass over hypotheses rather than as collapsed 0/1 acceptance states [@Gronau2021].
It gives science-meta a concrete template for representing uncertainty over both propositions and model structure in evidence aggregation workflows.
Its sequential-update framing is relevant to H01 because uncertain or down-weighted claims can be revisited when new studies alter posterior model probabilities instead of being permanently discarded.
The distinction between evidence of absence and absence of evidence is especially relevant for research-agent behavior, because agents should preserve weakly supported alternatives when the posterior remains diffuse.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Posterior model probability | Continuous operational belief | Candidate models carry probability mass in (0,1), aligning with D-003. |
| Model-averaged inclusion Bayes factor | Evidence aggregation update | Inclusion odds aggregate support across all models that include a proposition-like parameter. |
| Overall effect mu | Claim-level effect belief | A meta-analytic target proposition can be represented as a continuous latent effect rather than a binary claim. |
| Between-study heterogeneity tau | Context sensitivity or moderator uncertainty | Heterogeneity signals that evidence may need graph refinement, moderator search, or claim splitting. |
| Sequential Bayesian updating | Stochastic revisiting policy input | Changing posterior model probabilities can trigger revisits to previously down-weighted claims under H01. |
| Random-effects null hypothesis | Robust skeptical alternative | Allows study effects to vary while keeping the average effect near zero, dampening premature global conclusions. |

## Limitations

The approach addresses uncertainty over fixed-effect versus random-effects models but does not by itself solve dependence among effect sizes, measurement error, range restriction, or violations of the normal latent-effect assumption [@Gronau2021].
Publication bias can distort the meta-analytic result, and the authors warn that no statistical procedure can recover high-quality inference from low-quality or biased study sets [@Gronau2021].
The recommended priors are specifically discussed for standardized mean differences, and other effect-size scales require adjusted prior choices [@Gronau2021].
Model-averaged inclusion Bayes factors involving more than two models can depend on prior model probabilities, so prior model settings should be explicit and sensitivity-checked [@Gronau2021].
The paper is a primer and worked demonstration rather than a general automated evidence-graph construction method.

## Model / Tool Availability

The analysis is available through the R package `metaBMA`, which supports Bayesian model averaging for fixed-effect and random-effects meta-analysis [@Gronau2021].
The method is also implemented in JASP, including visualizations of posterior model probabilities and sequential analysis [@Gronau2021].
The article reports open materials at https://osf.io/npw5c/ [@Gronau2021].

## Follow-up

Evaluate whether science-meta evidence nodes should store posterior mass over a model set, not only a single belief score.
Test whether heterogeneity posterior probability should trigger automatic moderator search or causal-graph refinement.
Compare model-averaged meta-analysis with robust Bayesian meta-analysis approaches that explicitly model publication bias.

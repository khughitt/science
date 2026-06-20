---
type: paper
title: 'Robust Bayesian Meta-Analysis: Addressing Publication Bias With Model-Averaging'
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Maier2022
ontology_terms: []
source_refs:
- cite:Maier2022
related: []
---

# Robust Bayesian Meta-Analysis: Addressing Publication Bias With Model-Averaging

- **Authors:** Maximilian Maier, Frantisek Bartos, and Eric-Jan Wagenmakers
- **Year:** 2022
- **Journal:** Psychological Methods
- **DOI/URL:** https://doi.org/10.1037/met0000405
- **BibTeX key:** Maier2022
- **Source:** PDF

## Key Contribution

Maier et al. introduce robust Bayesian meta-analysis, or RoBMA, as a model-averaged Bayesian framework for estimating meta-analytic effects while testing and adjusting for publication bias [@Maier2022].
The central contribution is to avoid all-or-none methodological choices by averaging across 12 models that vary by effect presence, fixed versus random effects, and absence versus presence of p-value-based selection [@Maier2022].
The method can quantify evidence for the absence as well as the presence of publication bias, which is a direct improvement over non-significant frequentist tests that cannot distinguish absence of evidence from evidence of absence [@Maier2022].

## Methods

RoBMA extends Bayesian model-averaged meta-analysis by adding selection models for publication bias to the existing model set for effect presence and heterogeneity [@Maier2022].
The default ensemble assigns prior probability across model classes so that publication bias, heterogeneity, and a nonzero effect each have prior probability 0.5 [@Maier2022].
Models assuming publication bias use two-step or three-step weight functions over two-sided p-value intervals, with significant studies constrained to be at least as likely to appear as less significant studies [@Maier2022].
The default effect-size prior is normal with mean 0 and standard deviation 1, and the default heterogeneity prior is inverse gamma with parameters based on empirical heterogeneities in psychology [@Maier2022].
The implementation fits individual models through MCMC in JAGS via the RoBMA R package and estimates marginal likelihoods with bridge sampling [@Maier2022].
The paper evaluates RoBMA on a violent-video-game meta-analysis, 28 effects from Many Labs 2 where publication bias should be absent, and simulations varying effect size, heterogeneity, number of primary studies, and publication-bias severity [@Maier2022].

## Key Findings

On the Anderson et al. violent-video-game data, RoBMA strongly favored an effect and publication bias, and its model-averaged posterior mean adjusted the correlation estimate downward to r = 0.151 with a 95% credible interval of [0.094, 0.207] [@Maier2022].
On Many Labs 2, RoBMA produced one publication-bias false positive out of 28 effects and provided evidence for absence of publication bias in 12 of 28 cases [@Maier2022].
In simulations, RoBMA usually had the lowest root mean squared error and bias across compared meta-analytic methods, ranking best on RMSE in 65% of examined conditions and best on bias in 36% of conditions [@Maier2022].
RoBMA showed few false positives and high power for publication-bias detection in the selected simulation conditions, but its power to establish absence of publication bias was lower when few primary studies were available [@Maier2022].
The paper reports that RoBMA can underestimate effects when true effects are present because null models remain in the ensemble, and can overestimate effects under publication bias because no-bias models remain in the ensemble [@Maier2022].

## Relevance

This paper is directly relevant to Science because it treats evidence aggregation as continuous updating over a structured model ensemble rather than as a single model choice [@Maier2022].
It supports Decision D-003 by showing an operational pattern where beliefs remain continuous posterior probabilities and Bayes factors, not collapsed 0/1 labels [@Maier2022].
It is relevant to H01 because RoBMA preserves down-weighted hypotheses and models in the ensemble, allowing later evidence to increase their weight rather than discarding them after an early threshold decision [@Maier2022].
For graph-oriented research workflows, RoBMA is a concrete example of carrying uncertainty over causal or evidential mechanisms, including effect existence, heterogeneity, and publication selection, as explicit competing nodes in the analysis graph.
For research-agent behavior, the paper argues against treating a non-significant bias test as permission to ignore bias, which maps to agent policies that should revisit weakly supported claims under noisy or incomplete evidence.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Posterior model probability | Continuous operational belief | Model credibility remains a probability over alternatives rather than a binary model selection. |
| Inclusion Bayes factor | Evidence aggregation metric | Evidence is represented as support for including a parameter or mechanism across model subsets. |
| Publication-bias selection model | Evidence-generation mechanism | The observed literature is modeled as a biased sampling process rather than a transparent evidence stream. |
| Fixed versus random effects | Heterogeneity representation | The framework preserves uncertainty about whether evidence units share one effect or vary across contexts. |
| Model averaging | Uncertainty-guided retention | Inferential influence is distributed by posterior weight, preserving low-weight alternatives for possible later revision. |
| Evidence for absence of bias | Positive evidence for a negative proposition | The method distinguishes support for no publication bias from merely failing to detect bias. |

## Limitations

RoBMA assumes that test statistics follow weighted normal distributions around true effects with additive heterogeneity [@Maier2022].
Its default publication-bias models assume selection based on p-values and that smaller p-values are more likely to be published [@Maier2022].
The simulations operationalize publication bias in a way that favors p-value selection models, so methods based on different bias mechanisms may be disadvantaged [@Maier2022].
The paper reports weaker performance under strong p-hacking, where RoBMA can substantially overestimate effect sizes and performs worse than the Vevea and Hedges selection model [@Maier2022].
The method can be sensitive to priors when few primary studies are available, especially when p-value intervals contain few observations [@Maier2022].
The approach addresses publication bias in meta-analysis, not broader evidence-quality problems such as construct validity, dependent effects, causal confounding in primary studies, or agent-induced search bias.

## Model / Tool Availability

The method is available as the RoBMA R package, with model fitting through JAGS and custom weighted distributions for the selection models [@Maier2022].
The authors also report a JASP implementation for users who do not want to program directly [@Maier2022].
The article states that data and materials are available on OSF at https://osf.io/y354c/ and that additional simulation materials are available at https://osf.io/buk8g/ [@Maier2022].
Package license, exact package version used in the paper, and long-term maintenance status are [UNVERIFIED].

## Follow-up

Compare RoBMA's model-averaging pattern with Science belief-graph updates where each proposition has multiple possible evidence-generation mechanisms.
Evaluate whether H01 revisiting policies should use posterior model probability, inclusion Bayes factors, or expected value of information to schedule revisits of down-weighted claims.
Investigate extensions that model p-hacking, dependent evidence, and agent search bias as additional selection mechanisms in the same model-averaging style.

---
id: "topic:bayesian-methods-continuous-belief"
type: "topic"
title: "Bayesian Methods and the Continuous-Belief Representation of Evidence"
status: "active"
ontology_terms: []
source_refs: []
related:
  - "hypothesis:h01-stochastic-revisiting"
  - "topic:analytic-flexibility-and-replication"
created: "2026-04-24"
updated: "2026-04-24"
---

# Bayesian Methods and the Continuous-Belief Representation of Evidence

## Summary

Bayesian inference supplies the canonical mathematical framework for representing beliefs as continuous probabilities bounded strictly between 0 and 1, updating them on evidence, and combining evidence from multiple sources under explicit assumptions [@vandeSchoot2021].
This topic grounds the `science-meta` project's adopted design principle — *all operational beliefs are continuous in (0, 1) and never collapse to 0 or 100%* — in a literature that has worked through the real consequences of that principle: priors, calibration, model-checking, and the computational and interpretive costs.
Adopting the principle without engaging the literature would be advocacy; this topic is what makes the principle accountable.

## Key Concepts

**Posterior, prior, and likelihood.**
For a proposition represented by parameter θ and evidence D:
`p(θ | D) ∝ p(D | θ) · p(θ)`.
The prior `p(θ)` encodes belief before the evidence; the likelihood `p(D | θ)` encodes how well each value of θ explains the evidence; the posterior is the updated belief.
Applied to proposition-level evidence aggregation, each line of evidence is a likelihood term and the posterior is the current tool-level belief in the proposition.

**Bayes factor.**
Ratio of marginal likelihoods under two hypotheses: `BF = p(D | H1) / p(D | H0)`.
A continuous measure of how strongly the evidence supports one hypothesis over another, invariant to the choice of prior on the hypotheses themselves.
Useful for comparing competing explanatory models at proposition scale.

**Hierarchical (multilevel) models.**
Models in which parameters at one level are themselves drawn from distributions with higher-level parameters.
Allow partial pooling: evidence about many propositions in a group can sharpen belief about each individual proposition without fully pooling them into one.
Directly relevant when the tool needs to represent evidence aggregated across related but non-identical claims.

**Calibration.**
The property that stated probabilities match empirical frequencies: across all events the model rates at 0.7, roughly 70% should occur.
A continuous-belief system is only as useful as it is calibrated; miscalibrated probabilities are often worse than a coarse binary decision because they confer false precision.
Brier scores, reliability diagrams, and log-loss are standard calibration diagnostics.

**Posterior predictive checks.**
Simulating new data from the fitted model and comparing it to observed data.
A core Bayesian model-checking tool emphasised by Gelman and Shalizi [@Gelman2013] as the mechanism that makes applied Bayesian practice self-correcting rather than self-confirming.

**Credible vs. confidence intervals.**
Credible intervals answer "given this evidence and prior, what range contains the parameter with X% probability?"; confidence intervals answer a long-run-frequency question about the procedure.
The two are interpreted differently; the former is what a continuous-belief tool should report.

## Current State of Knowledge

**Bayesian inference is a mature, coherent framework.**
The van de Schoot et al. primer [@vandeSchoot2021] describes Bayesian methodology across domains with a mature methodological consensus on workflow: specify model and priors, fit, check, update; iterate.
Standard probabilistic programming systems (Stan, PyMC, brms, NumPyro) implement the required machinery; hierarchical and non-conjugate models that were computationally infeasible two decades ago are now routine.

**Priors can be defensible, not just subjective.**
The folk objection that "priors are arbitrary and therefore Bayesian methods are subjective" is addressed in modern practice by weakly-informative priors, default priors calibrated on the problem class, and explicit sensitivity analysis.
Gelman and Shalizi [@Gelman2013] argue that the practice of Bayesian statistics resembles hypothetico-deductive model-checking more than subjectivist belief updating, with priors treated as working assumptions to be falsified by posterior predictive failure, not as irreducible personal commitments.

**Hierarchical modelling connects naturally to evidence aggregation across lines.**
When multiple independent lines of evidence bear on related propositions, a hierarchical structure can express the expected correlation between them, giving partial pooling of information without collapsing distinct claims.
This is structurally the operation a research-assistance tool needs when many weak signals on related claims should be combined.

**Calibration is not automatic.**
A well-fit Bayesian model with a bad prior or a mis-specified likelihood can produce confident, poorly-calibrated posteriors.
Calibration is an empirical property to be verified, not a guarantee of the framework.
For a continuous-belief tool this is the most important practical caveat in the literature.

**Relationship to the replication-crisis literature.**
Ioannidis's argument that most published findings are false [@Ioannidis2005] is expressed in explicitly Bayesian language: pre-study odds, posterior positive predictive value.
McElreath and Smaldino's population-dynamics model of findings [@McElreath2015] is compatible with, and extended by, hierarchical Bayesian reasoning about how collections of claims evolve under selection.
The continuous-belief frame is not a new proposal; it is how this literature already thinks.

## Controversies & Open Questions

**Prior specification in applied settings.**
Weakly-informative defaults work well in well-studied problem classes but poorly in novel or sparse-data ones.
For proposition-level evidence aggregation in a research-assistance tool, no convention yet exists for what "default" even means; this is an open design problem.

**Computational cost at scale.**
Exact Bayesian inference is intractable for many realistic models; approximate methods (variational inference, normalising flows, ABC) trade off accuracy and calibration for speed.
Whether a research-tool-grade continuous-belief layer should use exact or approximate inference, and where the boundary sits, is not settled.

**Interpretation and usability.**
Posterior distributions require more effort to communicate than point estimates.
Non-specialist researchers may misinterpret credible intervals as confidence intervals, or overweight posteriors that are actually highly prior-dominated.
Tooling that surfaces Bayesian outputs to researchers must take this seriously.

**Does continuous belief always beat binary decision?**
A subtle and unsettled question: in domains where the cost of action is binary (publish or not, intervene or not), thresholded decisions are unavoidable, and a calibrated binary decision can outperform an uncalibrated continuous one.
The principle *beliefs are continuous* and the principle *decisions are binary* are not incompatible; the tool should represent them separately.

## Relevance to This Project

Three direct implications for `science-meta` and a fourth for H01 specifically.

1. **The continuous-belief principle recorded in `core/decisions.md` is not an isolated stance.**
   It is the standard representation in applied Bayesian statistics.
   The project inherits both the benefits — principled updating, combining heterogeneous evidence, explicit uncertainty — and the obligations: priors must be specified defensibly, calibration must be tested rather than assumed, and the framework must be communicated honestly to researcher users.

2. **Calibration should be a first-class, audited property.**
   The project should eventually include calibration diagnostics (Brier score, reliability plots) against any held-out ground-truth data it can construct.
   Without this, the continuous-belief claim is aspirational.

3. **Hierarchical structure is the natural model for aggregating evidence across related propositions.**
   Any future feature that combines evidence across propositions within a hypothesis bundle, or across related hypotheses, has a hierarchical-model shape already worked out in the literature.
   The project should not re-invent ad-hoc aggregation rules when the Bayesian framework already addresses them.

4. **H01's simulator uses Bayesian machinery directly.**
   The Beta-Bernoulli conjugate update in `specs/h01-simulator.md` is the simplest possible instance of the framework described here; uncertainty-scaled revisiting via Thompson sampling is a direct Bayesian-bandit rule.
   Simulator results interpret more cleanly when the simulator is a clean Bayesian-bandit instance — which it is — rather than an ad-hoc scoring rule.

## Key References

- van de Schoot et al. (2021) — *Nature Reviews Methods Primers* introduction to modern applied Bayesian practice [@vandeSchoot2021]
- Gelman & Shalizi (2013) — philosophical reframing of Bayesian statistics as hypothetico-deductive model-checking [@Gelman2013]
- Ioannidis (2005) — Bayesian-style PPV reasoning applied to the published-findings corpus [@Ioannidis2005]
- McElreath & Smaldino (2015) — population-dynamics treatment of evolving belief across many claims [@McElreath2015]

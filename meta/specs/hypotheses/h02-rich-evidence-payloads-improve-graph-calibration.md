---
id: hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
type: hypothesis
title: Rich evidence payloads improve graph calibration
status: proposed
phase: active
source_refs:
- paper:Zhao2012
- paper:Li2016
- paper:Allen2017
- paper:Linkov2017
- paper:Thijssen2017
- paper:Dai2023
- paper:Semochkina2025
- paper:Han2026
related:
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- question:04-authoring-cost-audit
- question:05-source-dependence-detection
- question:07-llm-agents-as-fallible-sources
- hypothesis:h01-stochastic-revisiting
created: '2026-05-05'
updated: '2026-05-05'
---
# Hypothesis H02: Rich evidence payloads improve graph calibration

## Organizing Conjecture

A graph that stores structured evidence payloads will produce better calibrated belief updates than a graph that stores only scalar support or dispute edges.
The load-bearing claim is not that more metadata is always better.
It is that a small set of epistemically relevant fields - comparison target, estimand, model family, priors, heterogeneity, bias model, diagnostics, sensitivity deltas, source reliability, source dependence, pipeline provenance, population transport, identifiability, and validation role - prevents the graph from treating unlike evidence operations as interchangeable [@Zhao2012; @Li2016; @Allen2017; @Thijssen2017; @Dai2023; @Semochkina2025; @Han2026].

## Proposition Bundle

### Core Propositions

**P1 (calibration).**
For the same set of evidence items, belief updates that consume rich structured payloads will be better calibrated against later validation outcomes than updates that consume scalar support/dispute edges alone.

**P2 (mechanism).**
The calibration gain comes from preserving distinctions that affect evidential meaning: target proposition, comparison set, estimand, aggregation operator, prior, heterogeneity, bias model, source reliability, source dependence, missingness, data-cleaning provenance, source population, target population, and diagnostics.

**P3 (minimality).**
Most of the calibration gain can be captured by a compact core schema plus typed method extensions.
If the core schema is too large for routine authoring, practical coverage will fall and the hypothesis will fail at the tool-adoption layer even if it is statistically sound.

### Supporting Or Auxiliary Propositions

**P4 (source behavior).**
Modeling source reliability as decomposed and updateable, rather than as a static trust score, improves aggregation when sources differ in false-positive and false-negative tendencies [@Zhao2012; @Li2016].

**P5 (pipeline provenance).**
Representing extraction, preprocessing, cleaning, imputation, and semantic-typing steps as evidence-generating transformations reduces overconfident updates from repaired or transformed data [@Allen2017; @Han2026].

**P6 (transport).**
Explicit source-to-target population metadata reduces biased strengthening from external datasets that are not exchangeable with the target population [@Dai2023].

## Current Uncertainty

- Current support is literature-based and architectural, not yet benchmark-based.
- The main unresolved design issue is the minimum viable schema: too little metadata loses the calibration mechanism, while too much metadata becomes authoring friction. `question:04-authoring-cost-audit` addresses this directly.
- The hypothesis assumes later validation outcomes can be defined well enough to score calibration. The "Calibration Ground Truth" subsection below names the candidate ground-truth signals and their failure modes; it remains an open empirical question how often any of them apply per neighborhood.
- It is unclear whether the first implementation should store source reliability and pipeline provenance directly on evidence payloads, as first-class graph nodes, or both.

### Calibration Ground Truth

The hypothesis predicts better calibration "against later validation outcomes." Candidate ground-truth signals, in rough order of strength:

1. **Direct experimental contradiction or replication.** A subsequent registered replication or randomized experiment that targets the same proposition is the strongest signal. Failure mode: rare, slow, and biased toward replicable claim types.
2. **Higher-quality follow-up evidence.** A subsequent meta-analysis, RCT after observational data, or larger / better-powered study supplants earlier evidence. Failure mode: "higher quality" is itself a judgment, and follow-ups can inherit upstream bias.
3. **Adjudicated researcher labels.** Domain-expert review marks a proposition supported, disputed, or unresolved against current evidence. Failure mode: expensive; introduces annotator bias; not blind to the project's own graph state.
4. **Structural updates from outside the graph.** Retractions, corrections, paradigm shifts, or canonical-source updates. Failure mode: late-arriving and uneven across fields.
5. **Internal consistency over time.** Whether a proposition's posterior at time T survives later evidence at time T+k without major revision. Failure mode: weakest signal; can be confounded by anchoring and shared sources.

Calibration scoring will likely combine signals 1-3 where available, with signals 4-5 as supporting evidence. The audit in `[t030]` should note which signals can be applied to existing project artifacts.

## Predictions

- In replay experiments over paper-derived evidence, rich-payload aggregation will show lower Brier score or expected calibration error than scalar-edge aggregation when later evidence is held out.
- Rich-payload aggregation will avoid strengthening claims when the apparent support comes from copied sources, shared extraction pipelines, missing views, unvalidated cleaning, or source-target mismatch.
- The benefit will be largest in heterogeneous evidence neighborhoods where studies differ in measurement role, target population, priors, bias risk, or source reliability.
- In simple low-noise neighborhoods with direct independent measurements, the rich schema may add little beyond scalar support.

## Falsifiability

- **P1 disconfirmed:** in a controlled replay or simulation, rich-payload aggregation does not improve calibration over scalar support/dispute edges despite correct metadata capture.
- **P2 disconfirmed:** calibration gains come only from generic regularization or conservative updating, not from the structured fields themselves.
- **P3 disconfirmed:** the schema required for improvement is too heavy for authors or agents to populate reliably, causing sparse or low-quality metadata that worsens graph behavior.
- **P4-P6 weakened:** source reliability, pipeline provenance, or transport metadata rarely changes updates in realistic project workflows.

## Supporting Evidence

- `literature_evidence` - Truth discovery jointly estimates latent truth and source reliability, and Zhao et al. show that sensitivity and specificity can diverge enough that one scalar quality score is inadequate [@Zhao2012; @Li2016].
- `literature_evidence` - Multi-view and Bayesian mechanistic data integration require measurement role, preprocessing, missingness, observation model, priors, and validation diagnostics to interpret evidence contributions [@Allen2017; @Thijssen2017].
- `literature_evidence` - External-data borrowing can improve efficiency or import bias depending on source-population and target-population assumptions [@Dai2023].
- `literature_evidence` - Informative priors and automated cleaning constraints can materially shape posterior results, making provenance and sensitivity analysis load-bearing [@Semochkina2025; @Han2026].

## Disputing Evidence

- No direct benchmark currently disputes the hypothesis.
- The strongest practical objection is metadata burden: if users or agents cannot populate rich payloads consistently, the schema could reduce coverage or create false precision.
- MCDA-style evidence integration can sometimes be useful with coarser source-quality criteria, suggesting not every workflow needs a full probabilistic payload [@Linkov2017].

## Evidence Needed To Shift Belief

- Build a small evidence-aggregation replay benchmark: hold out later or higher-quality evidence, compare scalar-edge updates against rich-payload updates, and score calibration.
- Implement a toy truth-discovery simulator with source sensitivity, specificity, copying, and missingness; compare scalar trust, decomposed source reliability, and full payload variants.
- Audit existing paper summaries to see how often the proposed fields can be extracted without unreasonable manual burden.
- Test whether schema fields improve H01 attention sampling by identifying claims that later require revision.

## Related Work

- `question:01-evidence-payload-schema` asks for the minimum field set.
- `question:03-source-and-pipeline-provenance` asks where source and pipeline metadata should live.
- `hypothesis:h01-stochastic-revisiting` supplies the attention/revisiting motivation.
- Batch 1 supplies contrastive, model-based evidence semantics; Batch 2 adds source behavior and pipeline provenance.

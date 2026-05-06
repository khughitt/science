---
id: "synthesis:bayesian-evidence-synthesis"
title: "Synthesis: Bayesian Evidence Synthesis and Meta-Analysis"
type: "synthesis"
report_kind: "paper-batch-synthesis"
generated_at: "2026-05-05T00:00:00-04:00"
source_commit: "77e358045bf60ee9dc799bf2e138aa2b456c05f0"
source_refs:
  - "paper:Williams2018"
  - "paper:Hackenberger2020"
  - "paper:Gronau2021"
  - "paper:Maier2022"
  - "paper:Cerullo2023"
  - "paper:Klugkist2023"
  - "paper:Volker2023"
  - "paper:Aitken2024"
  - "paper:Srinivasan2024"
  - "paper:VanLissa2024"
  - "paper:VanWonderen2024"
  - "paper:Mulder2026"
  - "paper:Berenfeld2026"
related:
  - "synthesis:truth-discovery-data-integration"
  - "question:01-evidence-payload-schema"
  - "question:02-causal-synthesis-guardrails"
  - "question:06-sequential-anytime-valid-evidence"
  - "question:08-mcda-bayesian-interoperability"
  - "hypothesis:h01-stochastic-revisiting"
  - "hypothesis:h02-rich-evidence-payloads-improve-graph-calibration"
  - "hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting"
  - "hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening"
  - "hypothesis:h05-sequential-evidence-improves-attention"
  - "topic:bayesian-methods-continuous-belief"
  - "topic:structured-scientific-knowledge"
created: "2026-05-05"
updated: "2026-05-05"
---

# Synthesis: Bayesian Evidence Synthesis and Meta-Analysis

## TL;DR

Batch 1 strongly supports Science's continuous-belief stance, but it also makes the current scalar-evidence intuition look too thin.
The recurring lesson is that a useful evidence graph must represent the comparison set, model family, prior, heterogeneity, study power, bias model, target estimand, and aggregation operator alongside any support value.

## Key Contribution

This synthesis extracts a design claim from Batch 1: Science should treat evidence aggregation as a typed, provenance-rich graph operation rather than as a scalar update.
The batch supplies concrete metadata requirements for quantitative support, especially comparison targets, priors, heterogeneity, bias, diagnostics, and causal estimands.

## Methods

The synthesis compares thirteen local paper summaries from Batch 1 and groups their implications by evidence semantics, Bayesian model uncertainty, heterogeneity, hypothesis-level synthesis, computational provenance, and causal interpretability.
It prioritizes implications for Science's graph-oriented research model over domain-specific statistical detail.

## Key Findings

The papers converge on a common point: quantitative evidence is meaningful only relative to explicit models, alternatives, assumptions, and target estimands.
Bayesian model averaging, BES, product Bayes factors, diagnostic-test meta-analysis, and causal meta-analysis each offer useful aggregation patterns, but they answer different questions and should be represented as distinct synthesis types.

## Relevance

The synthesis directly informs D-003 and H01.
It suggests that Science's attention and revisiting policies should use diagnostic reason codes such as underpowered evidence, high heterogeneity, prior sensitivity, publication-bias risk, imperfect labels, and estimand mismatch.

## What Was Reviewed

This batch covered thirteen papers on Bayesian meta-analysis, Bayesian model averaging, Bayes factors, Bayesian Evidence Synthesis (BES), product Bayes factors, diagnostic-test meta-analysis, evidence-estimation computation, and causal meta-analysis [@Williams2018; @Hackenberger2020; @Gronau2021; @Maier2022; @Cerullo2023; @Klugkist2023; @Volker2023; @Aitken2024; @Srinivasan2024; @VanLissa2024; @VanWonderen2024; @Mulder2026; @Berenfeld2026].
The shared theme is not merely "Bayesian methods are useful."
It is that evidence aggregation is an explicitly modeled operation, and the operation changes meaning when the estimand, heterogeneity model, comparison target, or study design changes.

## Shared Themes

**Evidence is contrastive.**
Aitken et al. foreground the Bayes factor as support for one proposition relative to another, not as an absolute truth score [@Aitken2024].
The BES papers make the same point operationally: support for an informative hypothesis differs depending on whether the alternative is a null, a complement, or an unconstrained model [@Klugkist2023; @Volker2023; @VanWonderen2024].
Science evidence edges therefore need a comparison target or hypothesis set.

**Continuous belief should preserve model uncertainty.**
Gronau et al. and Maier et al. model evidence as posterior mass over effect, heterogeneity, and bias models rather than selecting one model and discarding the rest [@Gronau2021; @Maier2022].
This is a direct template for Science: low-probability propositions or models should remain live with small posterior mass, especially when evidence is sparse or biased.

**Heterogeneity is not a nuisance to hide.**
Williams et al. and Hackenberger emphasize that small-study meta-analyses can understate heterogeneity and overstate certainty if between-study variance collapses to zero or is treated simplistically [@Williams2018; @Hackenberger2020].
RoBMA extends this by treating publication bias and heterogeneity as model dimensions that receive posterior weights [@Maier2022].
For Science, heterogeneity should be surfaced as a graph signal that can trigger moderator search, causal graph refinement, or stochastic revisiting.

**Hypothesis-level synthesis is different from effect-size pooling.**
BES and product Bayes factor methods aggregate support for an overarching informative hypothesis when effect sizes are too heterogeneous to pool [@Klugkist2023; @Volker2023; @VanLissa2024; @VanWonderen2024].
That is valuable for Science because many propositions will be supported by heterogeneous operationalizations.
But it should not be confused with estimating a pooled effect or resolving power problems.

**Power, complexity, and boundary cases can make aggregation brittle.**
Volker and Klugkist and van Wonderen et al. show that underpowered studies can accumulate evidence in the wrong direction, especially for complex informative hypotheses [@Volker2023; @VanWonderen2024].
This supports H01's core warning: down-weighted claims may deserve revisiting when their low support came from weak early evidence, complex constraints, or unfavorable comparison choices rather than decisive contradiction.

**Bayesian computation is itself an evidence artifact.**
Srinivasan et al. show one route for estimating Bayesian evidence from posterior samples using normalizing flows [@Srinivasan2024].
Cerullo et al. show that Bayesian diagnostic-test meta-analysis must preserve priors, posterior uncertainty, sampler behavior, and imperfect reference-standard assumptions [@Cerullo2023].
These papers imply that a Science evidence edge computed by a model should store computational provenance and diagnostics, not only the resulting weight.

**Causal interpretation requires explicit estimands.**
Berenfeld et al. show that classical meta-analysis can lack a well-defined causal target, especially for nonlinear measures such as risk ratios and odds ratios [@Berenfeld2026].
For Science, an aggregate evidence node should not strengthen a causal edge unless the causal estimand, target population, contrast, and aggregation rule are explicit.

## Tensions

**Bayes factors are coherent but not self-explanatory.**
Aitken et al. defend Bayes factors as logically coherent single-number measures of evidential value [@Aitken2024].
Mulder and van Aert, Williams et al., and Maier et al. make clear that prior choice, heterogeneity models, and bias models can materially change the value [@Williams2018; @Maier2022; @Mulder2026].
The synthesis is not that Bayes factors are fragile; it is that their assumptions must be visible.

**BES solves heterogeneity but not low power.**
BES is attractive for conceptual replication because it avoids forcing incomparable effects into one metric [@VanLissa2024; @VanWonderen2024].
But BES can perform poorly when individual studies are underpowered, because it asks whether each study supports the hypothesis rather than pooling information to estimate an effect [@Volker2023; @VanWonderen2024].
Science should use BES-like aggregation as a proposition-support operator, not as a universal meta-analysis substitute.

**Model averaging preserves uncertainty but increases representation burden.**
BMA and RoBMA give the right epistemic behavior for Science's continuous-belief philosophy [@Gronau2021; @Maier2022].
They also require Science to represent model families, prior model probabilities, inclusion probabilities, and publication-bias assumptions.
That is added complexity, but it is load-bearing complexity rather than decoration.

## Implications for Science

**1. Evidence edges need richer semantics.**
A support/dispute edge should carry at least: source, proposition, comparison target, evidence type, estimand, model family, prior, aggregation operator, assumptions, diagnostics, and uncertainty.
This could be implemented as a structured evidence payload rather than expanding the edge label vocabulary.

**2. Synthesis nodes should be typed.**
Science should distinguish effect-size synthesis, hypothesis-support synthesis, diagnostic-test synthesis, causal synthesis, and model-comparison synthesis.
These operations answer different questions and should not write to the same belief field without preserving their type.

**3. Low support should have reason codes.**
H01's revisiting policy becomes more defensible if down-weighted propositions carry reasons such as `underpowered-evidence`, `high-heterogeneity`, `publication-bias-risk`, `complex-hypothesis-penalty`, `boundary-case`, `prior-sensitive`, or `estimand-mismatch`.
These reasons can feed attention weights more directly than a scalar posterior alone.

**4. Heterogeneity should generate graph work.**
High posterior probability of heterogeneity should trigger moderator search, missing-variable review, subgroup proposition creation, or causal DAG refinement.
This is more useful than merely reporting `tau` or an I-squared analog in prose.

**5. Priors and sensitivity analyses need first-class provenance.**
The batch repeatedly shows that priors are unavoidable and consequential [@Williams2018; @Maier2022; @Mulder2026].
Science should store prior choices and sensitivity-analysis deltas on evidence and synthesis artifacts, then expose large sensitivity shifts as uncertainty signals.

**6. Causal claims need target-population and contrast checks.**
Before a synthesis node updates a causal proposition, Science should require an explicit target population, causal contrast, and aggregation rule.
For non-collapsible measures, the tool should warn or block causal strengthening unless the synthesis method is causally interpretable for the claimed estimand [@Berenfeld2026].

**7. Reference labels are evidence, not ground truth by default.**
MetaBayesDTA's handling of imperfect gold standards suggests a general rule: validation labels and reference standards should be modeled as fallible sources unless the project explicitly justifies treating them as ground truth [@Cerullo2023].

## Open Questions

The first three questions below are captured in `question:01-evidence-payload-schema`; question 5 is captured in `question:02-causal-synthesis-guardrails`.
Question 4 motivated `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`.

1. Should Science introduce a first-class `synthesis` entity subtype for Bayesian model-averaged aggregation, with posterior model probabilities and inclusion Bayes factors?
2. Should evidence edges require a `comparison_target` field whenever the support value is Bayes-factor-like?
3. What is the minimum evidence-payload schema that captures priors, heterogeneity, bias, estimand, diagnostics, and sensitivity without making manual authoring too heavy?
4. Should H01's attention sampler include reason-coded uncertainty features derived from synthesis artifacts, such as prior sensitivity, heterogeneity probability, or underpowered-source flags?
5. Should causal proposition updates be blocked unless target-population and estimand metadata are present?

## Known Gaps

- **Anytime-valid inference is not yet covered.** Sequential evidence accumulation in a research-assistance graph is closer in spirit to e-values and confidence sequences than to fixed-N Bayes factors, but no Batch 1 paper takes that view. Tracked in `[t028]` as a reading lead, scoped in `[t032]`, and framed conceptually in `question:06-sequential-anytime-valid-evidence` and `hypothesis:h05-sequential-evidence-improves-attention`.
- **Single-paper claims dominate Batch 1.** Most implications above rest on one or two sources per claim. The convergence is qualitative (across themes), not replicated benchmark evidence. Treat the claims as architectural conjectures rather than validated design.
- **Authoring-cost evidence is absent.** The "small core schema plus typed extensions" recommendation is justified on epistemic grounds, not by data on how much metadata authors or LLM agents actually populate. H02 P3 (minimality) flags this; `question:04-authoring-cost-audit` and `[t030]` make it measurable.

## Prioritized Follow-ups

**P1: Design an evidence-payload schema for quantitative support.** ([t022])
Start with fields for comparison target, model family, prior, estimand, aggregation operator, heterogeneity, bias model, diagnostics, and sensitivity-analysis deltas.
This is the highest-leverage follow-up because it changes the graph substrate used by all later synthesis work.

**P2: Add synthesis-type distinctions to the project model.** ([t023])
Separate effect-size pooling, hypothesis-support aggregation, causal synthesis, diagnostic-test synthesis, and model comparison.
This prevents Science from collapsing incompatible operations into one belief update.

**P3: Add H01 revisit reason codes.** ([t025])
Encode why a claim is down-weighted or uncertain, then feed those reasons into the graph attention sampler.
The batch gives several concrete reasons that map cleanly onto H01: underpowered evidence, high heterogeneity, prior sensitivity, bias risk, and estimand mismatch.

**P4: Draft a causal-synthesis guardrail.** ([t026])
Require target population, effect measure, and aggregation rule before evidence from meta-analysis strengthens a causal edge.
This follows directly from Berenfeld et al. and the causal-modeling aspect [@Berenfeld2026].

**P5: Represent heterogeneity and bias as evidence-generation mechanisms.** ([t024])
Treat publication bias, model uncertainty, study dependence, and imperfect reference labels as explicit mechanisms attached to evidence and synthesis nodes, not as prose-only caveats.
This is what lets P1-P3 do work; without it, the new payload fields stay descriptive.

## Relationship to Existing Hypotheses

Batch 1 supports D-003's continuous-belief decision (`core/decisions.md`) and refines H01.
The strongest refinement is that stochastic revisiting should not be driven only by low posterior support.
It should also be driven by the diagnostic reason for low support: low power, model uncertainty, heterogeneity, publication bias, prior sensitivity, imperfect labels, and estimand mismatch are all reasons to revisit rather than discard.

This refinement is the seed for `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`.
The payload-quality argument seeds `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, and the Berenfeld-driven guardrail seeds `hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`.
Batch 2 (`synthesis:truth-discovery-data-integration`) extends each of these with source behavior and pipeline provenance.

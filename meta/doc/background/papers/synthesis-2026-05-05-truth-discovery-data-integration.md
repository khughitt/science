---
id: "synthesis:truth-discovery-data-integration"
type: "synthesis"
report_kind: "paper-batch-synthesis"
generated_at: "2026-05-05T00:00:00-04:00"
source_commit: "77e358045bf60ee9dc799bf2e138aa2b456c05f0"
source_refs:
  - "paper:Zhao2012"
  - "paper:Li2016"
  - "paper:Allen2017"
  - "paper:Linkov2017"
  - "paper:Thijssen2017"
  - "paper:Majumdar2022"
  - "paper:Dai2023"
  - "paper:Semochkina2025"
  - "paper:Han2026"
related:
  - "question:01-evidence-payload-schema"
  - "question:02-causal-synthesis-guardrails"
  - "hypothesis:h01-stochastic-revisiting"
  - "topic:structured-scientific-knowledge"
  - "topic:bayesian-methods-continuous-belief"
created: "2026-05-05"
updated: "2026-05-05"
---

# Synthesis: Truth Discovery and Data Integration

## TL;DR

Batch 2 extends Batch 1's evidence-payload lesson from "aggregation needs explicit models" to "aggregation must also model source behavior."
Truth discovery, multi-view data integration, external-data borrowing, Bayesian calibration, data cleaning, and graph estimation all show that the credibility of an evidence update depends on source reliability, source dependence, missingness, preprocessing, target population, prior provenance, and validation diagnostics [@Zhao2012; @Li2016; @Allen2017; @Linkov2017; @Thijssen2017; @Majumdar2022; @Dai2023; @Semochkina2025; @Han2026].

## Key Contribution

This synthesis extracts a design claim from Batch 2: Science should represent evidence aggregation as joint inference over propositions, sources, transformations, and assumptions, rather than as an update from fixed evidence to fixed belief.
The batch supplies concrete schema requirements for source reliability, positive and negative claims, source dependence, view identity, preprocessing provenance, missingness, source-to-target transport, prior provenance, identifiability, cleaning uncertainty, and inferential calibration.

## Methods

The synthesis compares nine local paper summaries on truth discovery, statistical data integration, quantitative weight of evidence, Bayesian mechanistic data integration, multi-layer graphical-model estimation, heterogeneous external-data regression, Bayesian model calibration, and Bayesian data cleaning.
It prioritizes implications for Science's graph-oriented research model and evidence payload design over domain-specific algorithmic detail.

## Key Findings

The papers converge on a shared point: evidence quality is partly an inferred property of the source and pipeline that produced the observation.
Truth discovery jointly estimates source reliability and latent truth [@Zhao2012; @Li2016].
Data integration requires view-specific measurement models, preprocessing provenance, missingness, and batch diagnostics [@Allen2017; @Thijssen2017].
External-data borrowing requires source-population and target-population assumptions [@Dai2023].
Model calibration and graph estimation require explicit priors, identifiability diagnostics, shared-structure assumptions, and testing procedures [@Majumdar2022; @Semochkina2025].
Data cleaning and automated prior generation are themselves evidence-generating steps that require provenance and validation [@Han2026].

## Relevance

Batch 2 directly informs the Evidence Payload Schema task group.
It adds fields that Batch 1 did not fully foreground: source reliability model, source-dependence links, omission semantics, view identity, cleaning provenance, missingness class, covariate coverage, source population, target population, transport or reweighting assumption, identifiability status, and validation role.
It also refines H01: low-confidence graph items should carry reason codes that say whether uncertainty comes from unreliable sources, copied sources, missing views, prior-resolved non-identifiability, source-target mismatch, or unvalidated data repair.

## What Was Reviewed

This batch covered nine papers spanning truth discovery, statistical data integration, weight-of-evidence formalization, Bayesian mechanistic integration, multi-layer graphical models, heterogeneous external-data regression, Bayesian disease-model calibration, and Bayesian data cleaning [@Zhao2012; @Li2016; @Allen2017; @Linkov2017; @Thijssen2017; @Majumdar2022; @Dai2023; @Semochkina2025; @Han2026].
The shared theme is that evidence integration is not just a belief update.
It is a structured inference problem over latent truth, source behavior, data-generating mechanisms, transformations, and target-context assumptions.

## Shared Themes

**Source reliability is learned, not declared.**
Zhao et al. infer fact truth and source quality jointly, and they split source behavior into sensitivity and specificity rather than using one trust score [@Zhao2012].
Li et al. generalize this as truth discovery: reliable sources support inferred truths, and inferred truths update source reliability [@Li2016].
Science should therefore model source reliability as graph state that can be updated, decomposed, and scoped by domain or claim type.

**Omissions and absences need semantics.**
Zhao et al. show that negative claims can be informative when a source had an opportunity to assert a true value but omitted it [@Zhao2012].
Allen's multi-view discussion similarly shows that a missing measurement view is not the same thing as a measured negative result [@Allen2017].
Science should distinguish asserted absence, source omission, not measured, not applicable, extraction failure, imputed value, and repaired value.

**Evidence independence cannot be assumed from source count.**
Li et al. emphasize copying, shared extraction rules, source correlations, and social or provenance dependencies as major truth-discovery failure modes [@Li2016].
This is a direct warning for research agents: multiple summaries, papers, datasets, or claims may not be independent if they share data, pipelines, citations, prompts, or extraction tools.
Evidence payloads should carry dependency and provenance links so aggregation does not overcount copied support.

**Data integration preserves view identity.**
Allen frames data integration as jointly analyzing heterogeneous views measured on common observations, not collapsing all evidence into one uniform table [@Allen2017].
Thijssen et al. show why this matters: relative time courses, absolute concentrations, priors, and held-out validation measurements constrain different targets and reveal different model failures [@Thijssen2017].
Science should store evidence role and measurement model, not only source and value.

**Target population matters before external evidence can help.**
Dai and Shao show that external datasets can improve target-population estimation only when population heterogeneity is modeled through exchangeability, reweighting, or constraints [@Dai2023].
Naively treating external data as more of the same can bias the update.
This strengthens the causal-synthesis guardrail: external evidence should not strengthen a target claim unless source population, target population, covariate coverage, and transport assumptions are explicit.

**Priors can be evidence, but only with provenance.**
Semochkina and Walsh show that informative priors can resolve non-identifiability in disease-model calibration [@Semochkina2025].
Han et al. show that priors and constraints can be generated automatically for Bayesian data cleaning [@Han2026].
Both are useful for Science, but both require provenance, validation status, and sensitivity deltas so a posterior update is not confused with direct data evidence.

**Graph estimates are not automatically inferential claims.**
Majumdar and Michailidis separate penalized graph estimation from debiased edge tests and FDR-controlled inference [@Majumdar2022].
Science should preserve this distinction: estimated association or dependency edges can be graph candidates, while inferentially calibrated edge claims need estimands, tests, multiplicity handling, and diagnostics.

**MCDA is a useful fallback, not a substitute for likelihoods.**
Linkov et al. argue that weight-of-evidence practice should move toward explicit quantitative integration, with Bayesian methods as the principled target and multicriteria decision analysis as a practical approximation when likelihoods are unavailable [@Linkov2017].
Science can use MCDA-style operators for early evidence ranking, but should label them as decision-analytic scoring rather than Bayesian belief updates.

## Tensions

**More automation means more provenance burden.**
Han et al. make LLM-assisted prior and constraint generation operationally attractive [@Han2026].
But the same automation adds new source-reliability questions: which prompt, semantic type, template, validation check, and repair uncertainty produced the cleaned data?

**Borrowing strength and importing bias are the same operation under different assumptions.**
Dai and Shao show that external data can improve efficiency under a valid heterogeneity model and bias results under a naive pooling model [@Dai2023].
Majumdar and Michailidis similarly rely on grouping assumptions to share graph structure across sources [@Majumdar2022].
Science should treat shared-structure assumptions as explicit payload fields, not as invisible implementation choices.

**Truth discovery can harden labels too early.**
Truth-discovery surveys often distinguish score outputs from label outputs [@Li2016].
For Science, score outputs are usually preferable because downstream Bayesian belief updates, H01 attention sampling, and causal guardrails need uncertainty rather than final labels.

## Implications for Science

**1. Evidence payloads need source behavior fields.**
Add `source_reliability_model`, `source_reliability_scope`, `sensitivity`, `specificity`, `false_positive_risk`, `false_negative_risk`, and `source_dependency_refs` or equivalent fields.
These should be learned or updated where possible, not fixed trust badges.

**2. Evidence payloads need absence and missingness fields.**
Represent whether a value is asserted present, asserted absent, omitted by an in-scope source, not measured, missing by design, missing by failure, imputed, or repaired.
This prevents the graph from treating silence, absence, and negative evidence as interchangeable.

**3. Evidence pipelines are evidence sources.**
Cleaning, extraction, preprocessing, semantic typing, batch correction, and imputation should be represented as transformations with provenance and validation status.
For cleaned datasets, the evidence edge should point through the cleaning model, not only to the final cell values.

**4. Source-to-target transport belongs in the guardrail layer.**
Before external evidence updates a target-population proposition, the graph should require source population, target population, covariate coverage, selection mechanism, and exchangeability/reweighting/transport assumptions.
This generalizes Batch 1's causal-estimand guardrail beyond meta-analysis.

**5. Aggregation operators should be typed by output semantics.**
Truth label, truth score, Bayesian posterior, MCDA score, graph estimate, debiased edge test, validation diagnostic, and uncertainty-reduction contribution are different outputs.
Science should not write them to the same belief slot without preserving type and interpretation.

**6. H01 attention should use pipeline reason codes.**
Add reason codes such as `source-unreliable`, `source-dependent`, `omission-ambiguous`, `missing-view`, `source-target-mismatch`, `prior-resolved-nonidentifiability`, `cleaning-unvalidated`, `repair-uncertain`, `shared-structure-assumption`, and `debiased-inference-missing`.
These are more actionable than posterior score alone.

**7. Graph construction needs an evidence-generation layer.**
The scientific graph should distinguish domain propositions from source/pipeline/measurement nodes that generated the evidence.
This allows later updates to revise many claims when a source, extractor, cleaning model, batch correction, or transport assumption becomes suspect.

## Open Questions

1. Should source reliability be represented as first-class nodes, payload fields, or both?
2. How should Science distinguish source dependence from ordinary topical relatedness?
3. What minimum absence/missingness vocabulary is expressive enough without becoming burdensome?
4. Should cleaned or imputed values be allowed to update propositions directly, or only through transformation nodes with validation diagnostics?
5. Should external evidence be blocked from causal or target-population updates unless transport assumptions are present?
6. How should MCDA-style scores interact with Bayesian belief states?
7. Should graph-edge estimates and graph-edge inferential claims be separate entity kinds?

## Prioritized Follow-ups

**P1: Extend t022 with source and pipeline fields.**
Add source reliability, source dependence, absence semantics, missingness class, cleaning provenance, transformation provenance, source population, target population, covariate coverage, and transport assumptions to the minimum evidence payload candidate.

**P2: Add a typed aggregation-output taxonomy.**
Extend t023 so typed synthesis nodes distinguish truth labels, truth scores, Bayesian posteriors, MCDA scores, graph estimates, debiased edge tests, and validation diagnostics.

**P3: Add H01 source/pipeline reason codes.**
Extend t025 with reason-coded uncertainty from Batch 2: source unreliability, source dependence, ambiguous omission, missing view, source-target mismatch, prior-resolved non-identifiability, and unvalidated cleaning.

**P4: Treat data cleaning and extraction as graph transformations.**
Fold Han2026 and Allen2017 into t024 so bias and heterogeneity mechanisms include cleaning, preprocessing, extraction confidence, batch effects, and imputation.

**P5: Promote H02-H04 as explicit candidate hypotheses.**
H02 should test whether rich payloads improve calibration specifically through source reliability, source dependence, and pipeline provenance.
H03 should include reason-coded revisiting from source/pipeline uncertainty.
H04 should include source-to-target transport and covariate-coverage guardrails, not only causal estimands.

## Post-Batch-2 Synthesis Decisions

**New hypotheses.**
Batch 2 makes the draft hypotheses mature enough to track explicitly:
- `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration` - rich payloads should improve graph calibration over scalar support/dispute edges.
- `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting` - H01 attention should use diagnostic reason codes, not posterior magnitude alone.
- `hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening` - causal updates should require estimand, target, aggregation, and transport metadata.

**New question.**
Batch 2 also warrants a distinct representation question:
- `question:03-how-should-science-represent-source-behavior-and-pipeline-provenance-in` asks where source reliability, source dependence, missingness, cleaning, extraction, preprocessing, and transport should live in the graph.

**Schema update.**
The Batch 1 payload schema should now be extended with source and pipeline fields:
`source_reliability_model`, `source_reliability_scope`, `source_dependency_refs`, `claim_presence_state`, `missingness_class`, `pipeline_step_refs`, `cleaning_model_ref`, `repair_uncertainty`, `source_population`, `target_population`, `covariate_coverage`, `transport_assumption`, `identifiability_status`, and `validation_role`.

**Attention update.**
H01-style attention should include Batch 2 reason codes:
`source-unreliable`, `source-dependent`, `omission-ambiguous`, `missing-view`, `source-target-mismatch`, `prior-resolved-nonidentifiability`, `cleaning-unvalidated`, `repair-uncertain`, `shared-structure-assumption`, and `debiased-inference-missing`.

## Relationship to Existing Hypotheses and Tasks

Batch 2 strengthens H01 by making the revisit target more concrete.
The graph should revisit claims not only when posterior support is low, but when the reason for uncertainty points to a repairable representation problem: ambiguous omission, copied evidence, missing view, weak source reliability, unvalidated cleaning, prior-driven identifiability, or source-target mismatch.

Batch 2 also sharpens the Evidence Payload Schema task group.
The minimum schema now needs to represent source behavior and data-generation pipeline state alongside the Batch 1 fields for comparison target, estimand, priors, heterogeneity, bias models, diagnostics, and sensitivity deltas.

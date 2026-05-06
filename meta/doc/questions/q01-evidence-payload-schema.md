---
id: question:01-evidence-payload-schema
type: question
title: What metadata should Science require for quantitative evidence and synthesis
  updates?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Williams2018
- cite:Hackenberger2020
- cite:Gronau2021
- cite:Maier2022
- cite:Cerullo2023
- cite:Klugkist2023
- cite:Volker2023
- cite:Aitken2024
- cite:Srinivasan2024
- cite:VanLissa2024
- cite:VanWonderen2024
- cite:Mulder2026
- cite:Berenfeld2026
- cite:Zhao2012
- cite:Li2016
- cite:Allen2017
- cite:Linkov2017
- cite:Thijssen2017
- cite:Majumdar2022
- cite:Dai2023
- cite:Semochkina2025
- cite:Han2026
- cite:Petersen2014
- cite:Shi2022
- cite:Dong2023
- cite:Faller2024
- cite:Zheng2024
- cite:Zuber2025
- cite:Zhang2017CancerGenomics
- cite:Zhang2021JointGraphical
- cite:Vahabi2022
- cite:Deleu2023
- cite:Mohammadi2025
- cite:Alnajjar2026
- cite:Ding2025
- cite:Jin2025
- cite:Si2025
- cite:Yu2026
related:
- hypothesis:h01-stochastic-revisiting
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
- question:03-source-and-pipeline-provenance
- question:10-causal-graph-construction-pipeline
- question:11-graph-valued-synthesis-artifacts
- question:12-agent-tool-kg-operations
- topic:bayesian-methods-continuous-belief
created: '2026-05-05'
updated: '2026-05-06'
---

# What metadata should Science require for quantitative evidence and synthesis updates?

## Summary

Batch 1 shows that a quantitative evidence update is not just a scalar support value.
It depends on the proposition being tested, the alternative or comparison set, the estimand, the synthesis operator, priors, heterogeneity, bias model, diagnostics, and sensitivity to modeling assumptions.
Batch 2 adds that evidence aggregation also depends on source behavior and the pipeline that produced the evidence.
Batch 3 adds that causal graph construction depends on staged provenance: graph object type, discovery algorithm, method assumptions, prior role, hidden-variable assumptions, diagnostics, and identification status.
Batch 4 adds that graph-valued and integration-valued artifacts depend on integration objective, context scope, view scope, shared-structure assumptions, approximation method, graph posterior uncertainty, cluster count, and feature relevance.
Batch 5 adds that agent/tool/KG operations depend on agent role, model version, prompt/workflow, tool chain, execution trace, KG view, graph version, safety policy, validation status, abstention behavior, and evaluation protocol.
This question asks what minimum metadata Science should require before a quantitative evidence, data-integration, truth-discovery, synthesis, graph-construction, graph-valued integration, or agent-generated operation artifact can update graph beliefs.

## Why It Matters

- Affects the design of evidence edges, synthesis nodes, and graph belief updates.
- Affects whether H01's attention policy can distinguish "low support because disproven" from "low support because underpowered, heterogeneous, prior-sensitive, or model-mismatched."
- Affects whether H02 and H03 can be tested, because both require payload fields that preserve source reliability, source dependence, pipeline provenance, and reason-coded uncertainty.
- Risk if unanswered: Science may collapse incompatible evidence operations into the same belief field and produce overconfident graph updates.

## Current Evidence

- Bayes factors are contrastive and require explicit alternatives or comparison sets [@Aitken2024; @Mulder2026].
- Bayesian model-averaged meta-analysis and RoBMA preserve posterior mass over effect, heterogeneity, and bias models rather than selecting one model [@Gronau2021; @Maier2022].
- BES and product Bayes factor methods show that hypothesis-support synthesis answers a different question than effect-size pooling [@Klugkist2023; @Volker2023; @VanLissa2024; @VanWonderen2024].
- Bayesian diagnostic-test meta-analysis and evidence estimation from posterior samples show that priors, sampler diagnostics, label uncertainty, and numerical uncertainty may all matter to the credibility of an evidence artifact [@Cerullo2023; @Srinivasan2024].
- Truth discovery shows that source reliability should be inferred and decomposed, with source dependence and output scoring preserved where possible [@Zhao2012; @Li2016].
- Statistical data integration and Bayesian mechanistic integration show that evidence roles, measurement scale, preprocessing provenance, missing views, observation models, validation roles, and diagnostics affect how evidence should update the graph [@Allen2017; @Thijssen2017].
- Heterogeneous external-data regression shows that source population, target population, covariate coverage, and transport or reweighting assumptions determine whether external evidence helps or biases an update [@Dai2023].
- Bayesian calibration and Bayesian data cleaning show that prior provenance, identifiability, automated constraints, and cleaning uncertainty can be load-bearing inputs to evidence updates [@Semochkina2025; @Han2026].
- Causal graph construction and discovery papers show that graph outputs need method, graph-object, hidden-variable, diagnostic, and identification metadata before they can be interpreted as causal support [@Petersen2014; @Shi2022; @Dong2023; @Faller2024; @Zheng2024; @Zuber2025].
- Graphical-model and multiview-integration papers show that graph estimates, graph posteriors, clusters, and selected-feature outputs need context scope, view scope, shared-structure assumptions, approximation provenance, and validation role [@Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026].
- Scientific-agent and KG infrastructure papers show that tool chains, graph updates, derived KG views, agent evaluations, and context-understanding failures need operation provenance and validation state [@Ding2025; @Jin2025; @Si2025; @Yu2026].
- The main conflicting pressure is authoring cost: a complete schema could become too heavy for routine paper notes and manual graph updates.

## Thoughts

- Best current interpretation: Science needs a compact structured evidence payload with required fields for comparison target, evidence type, estimand, aggregation operator, source provenance, source behavior, pipeline provenance, and epistemic role, plus optional typed fields for priors, heterogeneity, bias, diagnostics, sensitivity deltas, transport, identifiability, cleaning, validation role, graph object type, discovery method, hidden-variable assumptions, graph-construction diagnostics, graph artifact type, integration objective, context scope, view scope, approximation class, posterior summary role, agent role, tool-chain provenance, graph version, KG view, and agent evaluation status.
- The major remaining uncertainty is where to draw the line between required metadata and richer method-specific extensions.
- A likely design is progressive: require a small core for all quantitative evidence, then attach typed method payloads for Bayesian model averaging, BES, diagnostic-test meta-analysis, causal synthesis, posterior-sample evidence estimation, truth discovery, data cleaning, external-data transport, causal discovery, mediation analysis, Mendelian-randomization graph models, graph posteriors, integrative clustering, feature selection, module discovery, predictive integration, and agent/tool operations.

## Connections to Project

- Related hypotheses: `hypothesis:h01-stochastic-revisiting`, `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Required data or analyses: schema design pass over existing evidence entities, then a migration strategy for paper-summary-derived evidence.
- Priority level: high.

## Related

- Topic notes: `topic:bayesian-methods-continuous-belief`.
- Article notes: Batch 1, Batch 2, Batch 3, Batch 4, and Batch 5 paper summaries under `doc/background/papers/`.
- Methods/Datasets: none yet.

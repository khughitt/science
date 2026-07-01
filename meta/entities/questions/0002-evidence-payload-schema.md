---
type: question
title: What metadata should Science require for quantitative evidence and synthesis
  updates?
status: active
created: '2026-05-05'
updated: '2026-07-01'
id: question:0002-evidence-payload-schema
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
- cite:Freiesleben2023
- cite:Heyard2025
- cite:Banzi2026
related:
- hypothesis:0001-stochastic-revisiting
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- question:0004-source-and-pipeline-provenance
- question:0010-causal-graph-construction-pipeline
- question:0011-graph-valued-synthesis-artifacts
- question:0012-agent-tool-kg-operations
- question:0013-robustness-reproducibility-evaluation
- topic:bayesian-methods-continuous-belief
---

# What metadata should Science require for quantitative evidence and synthesis updates?

## Summary

Batch 1 shows that a quantitative evidence update is not just a scalar support value.
It depends on the proposition being tested, the alternative or comparison set, the estimand, the synthesis operator, priors, heterogeneity, bias model, diagnostics, and sensitivity to modeling assumptions.
Batch 2 adds that evidence aggregation also depends on source behavior and the pipeline that produced the evidence.
Batch 3 adds that causal graph construction depends on staged provenance: graph object type, discovery algorithm, method assumptions, prior role, hidden-variable assumptions, diagnostics, and identification status.
Batch 4 adds that graph-valued and integration-valued artifacts depend on integration objective, context scope, view scope, shared-structure assumptions, approximation method, graph posterior uncertainty, cluster count, and feature relevance.
Batch 5 adds that agent/tool/KG operations depend on agent role, model version, prompt/workflow, tool chain, execution trace, KG view, graph version, safety policy, validation status, abstention behavior, and evaluation protocol.
Batch 6 adds that robustness/reproducibility evaluations depend on evaluation target, robustness modifier, modifier domain, target tolerance, replication design, reproducibility dimension, metric family, metric question, checklist reference, lifecycle stage, and evaluation result.
This question asks what minimum metadata Science should require before a quantitative evidence, data-integration, truth-discovery, synthesis, graph-construction, graph-valued integration, agent-generated operation, or robustness/reproducibility evaluation artifact can update graph beliefs.

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
- Robustness and reproducibility papers show that evaluation claims need target/modifier/tolerance metadata, metric-question alignment, replication-design metadata, and checklist lifecycle stage [@Freiesleben2023; @Heyard2025; @Banzi2026].
- The main conflicting pressure is authoring cost: a complete schema could become too heavy for routine paper notes and manual graph updates.

## Thoughts

- Best current interpretation: Science uses a compact t022 core plus typed extensions. The durable core contract now lives at `meta/evidence/t022-core-contract.md`; the generic implementation lives in `science/src/science_tool/evidence_payload.py` with coverage in `science/tests/test_evidence_payload_contract.py`.
- The core keeps graph-level fields only: identity, provenance, proposition attachment, comparison target, support direction, validation role/status, optional uncertainty summary, reason codes, and partial-field markers. Paper-extracted claims use `claim_source_ref`; evaluation/audit/operation targets live in their owning extensions rather than in core.
- The major remaining uncertainty is not the t022 core shape, but how much each typed extension should require for Bayesian synthesis, truth discovery, graph-valued integration, agent/tool operations, robustness/reproducibility evaluation, and future evidence families.
- A likely design remains progressive: require the small core for all evidence-like artifacts, then attach typed method payloads for Bayesian model averaging, BES, diagnostic-test meta-analysis, causal synthesis, posterior-sample evidence estimation, truth discovery, data cleaning, external-data transport, causal discovery, mediation analysis, Mendelian-randomization graph models, graph posteriors, integrative clustering, feature selection, module discovery, predictive integration, agent/tool operations, and robustness/reproducibility evaluations.

## Connections to Project

- Related hypotheses: `hypothesis:0001-stochastic-revisiting`, `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Required data or analyses: extension-specific contract passes over existing evidence entities, then a migration strategy for paper-summary-derived evidence.
- Priority level: high.

## Related

- Topic notes: `topic:bayesian-methods-continuous-belief`.
- Article notes: Batch 1, Batch 2, Batch 3, Batch 4, Batch 5, and Batch 6 paper summaries under `doc/background/papers/`.
- Methods/Datasets: none yet.

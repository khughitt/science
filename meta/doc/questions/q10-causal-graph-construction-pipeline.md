---
id: question:10-causal-graph-construction-pipeline
type: question
title: How should Science represent causal graph construction as a staged evidence
  pipeline?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Petersen2014
- cite:Fedak2015
- cite:Dugourd2021
- cite:Zhang2021gCastle
- cite:Shi2022
- cite:Bhagwat2023
- cite:Dong2023
- cite:Ban2023
- cite:Faller2024
- cite:Jiralerspong2024
- cite:Liu2024HiddenWorld
- cite:Zheng2024
- cite:Wan2025
- cite:Wang2025
- cite:Yang2025
- cite:Zuber2025
related:
- question:01-evidence-payload-schema
- question:02-causal-synthesis-guardrails
- question:07-llm-agents-as-fallible-sources
- question:11-graph-valued-synthesis-artifacts
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
created: '2026-05-06'
updated: '2026-05-06'
---

# How should Science represent causal graph construction as a staged evidence pipeline?

## Summary

Batch 3 shows that causal graph construction is not a single edge-writing step.
It is a staged evidence pipeline: variable proposal, measurement, external-variable search, data integration, prior-knowledge assembly, structure learning, graph diagnostics, identification, estimation, and interpretation.
This question asks which of those stages should become explicit Science graph artifacts, which can remain payload fields, and how their outputs should be allowed to influence causal propositions.

## Why It Matters

- Affects the Evidence Payload Schema task group: causal graph outputs require fields beyond ordinary evidence synthesis, including graph object type, discovery method, method assumptions, prior role, diagnostic scores, and identification status.
- Affects H04 because false causal strengthening can happen before effect estimation, at variable selection, graph discovery, prior elicitation, or graph-object interpretation.
- Affects H03 because graph-construction failures create distinct revisit reasons: latent-variable risk, causal-sufficiency assumption, weak-prior-only evidence, prior/data disagreement, and self-incompatibility.
- Risk if unanswered: Science may treat LLM-suggested edges, data-discovered adjacencies, equivalence-class features, mediation paths, mechanistic hypotheses, and identified causal effects as the same kind of causal support.

## Current Evidence

- Petersen and van der Laan separate causal model, observed data, counterfactual quantity, identification, statistical estimand, estimation, and interpretation; Science should preserve that separation in causal payloads [@Petersen2014].
- Causal discovery toolkits such as gCastle and causal-learn expose multiple graph objects and method families, implying that graph type and method assumptions are load-bearing metadata [@Zhang2021gCastle; @Zheng2024].
- Shi and Bhagwat show that data integration for causal inference depends on selection, confounding, missing variables, variable overlap, and external-source validity [@Shi2022; @Bhagwat2023].
- Dong shows that hidden-variable assumptions change what can be learned from observed data; causal sufficiency cannot remain implicit [@Dong2023].
- Faller et al. show that self-compatibility can provide a ground-truth-free diagnostic, but this is a falsification or warning signal rather than proof [@Faller2024].
- Ban, Jiralerspong, Liu, Wan, and Wang show that LLMs can propose variables, priors, constraints, or graph structures, but their outputs should be represented as fallible prior or pipeline evidence rather than causal truth [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
- Yang and Zuber show that mediation and Mendelian-randomization graph outputs require estimand-specific fields, instruments, direction assumptions, and graph uncertainty [@Yang2025; @Zuber2025].

## Thoughts

- Best current interpretation: represent causal graph construction as a layered pipeline with distinct artifacts for candidate variables, source annotations, extracted external variables, prior knowledge, discovery runs, graph diagnostics, identified estimands, and effect estimates.
- Edge-like outputs should be typed by epistemic role: `assumed_background_edge`, `llm_prior_edge`, `llm_ancestral_constraint`, `data_discovered_adjacency`, `equivalence_class_feature`, `latent_variable_hypothesis`, `identified_causal_effect`, `mediation_path`, or `mechanistic_hypothesis`.
- The main design uncertainty is granularity. Making every graph-construction step first-class may be too heavy, but hiding those steps inside prose makes H02/H03/H04 hard to test.
- A likely compromise is a required compact causal-discovery payload plus optional first-class entities when a step feeds many downstream claims or carries independent validation status.

## Connections to Project

- Related hypotheses: `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`, `hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`.
- Related tasks: `[t022]`, `[t023]`, `[t025]`, `[t026]`, `[t034]`.
- Required data or analyses: schema design for causal-discovery payloads, graph-object taxonomy, reason-code mapping, and a validation-mode prototype that distinguishes prior, discovery, diagnostic, identification, and estimation artifacts.
- Priority level: high for causal-modeling features; medium-high for the general evidence payload schema.

## Related

- Topic notes: `topic:structured-scientific-knowledge`, `topic:bayesian-methods-continuous-belief`.
- Article notes: Batch 3 paper summaries under `doc/background/papers/`.
- Methods/Datasets: causal discovery, LLM-assisted causal graph construction, data integration for causal inference, mediation analysis, Mendelian randomization.

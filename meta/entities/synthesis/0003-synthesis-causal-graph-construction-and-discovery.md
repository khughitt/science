---
kind: synthesis
title: 'Synthesis: Causal Graph Construction and Discovery'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: synthesis:0003-synthesis-causal-graph-construction-and-discovery
report_kind: paper-batch-synthesis
generated_at: '2026-05-06T00:00:00-04:00'
source_commit: 2005d65
source_refs:
- paper:Petersen2014
- paper:Fedak2015
- paper:Dugourd2021
- paper:Zhang2021gCastle
- paper:Shi2022
- paper:Bhagwat2023
- paper:Dong2023
- paper:Ban2023
- paper:Faller2024
- paper:Jiralerspong2024
- paper:Liu2024HiddenWorld
- paper:Zheng2024
- paper:Wan2025
- science-meta:paper:Wang2025
- paper:Yang2025
- paper:Zuber2025
related:
- question:0002-evidence-payload-schema
- question:0003-causal-synthesis-guardrails
- question:0004-source-and-pipeline-provenance
- question:0008-llm-agents-as-fallible-sources
- question:0010-causal-graph-construction-pipeline
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
---

# Synthesis: Causal Graph Construction and Discovery

## TL;DR

Batch 3 makes H04 sharper: causal graph construction needs layered provenance.
A credible causal update should distinguish causal model, observed-data link, target estimand, identification assumptions, discovery algorithm, prior knowledge, graph object type, diagnostic checks, and validation role [@Petersen2014; @Shi2022; @Faller2024; @Zheng2024].
LLMs can help with variable proposal, weak prior construction, and graph elicitation, but the batch repeatedly argues against treating LLM outputs as causal truth [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].

## Key Contribution

This synthesis extracts a design claim from Batch 3: Science should treat causal graph construction as a multi-stage evidence pipeline rather than a direct edge-writing operation.
The stages include variable proposal, measurement/annotation, external-variable search, data integration, prior-knowledge assembly, structure learning, graph diagnostics, identification, estimation, and interpretation.

## Methods

The synthesis compares sixteen local paper summaries covering causal inference roadmaps, Bradford Hill-style evidence integration, causal data integration, multi-omics mechanism search, causal discovery toolkits, hidden-variable discovery, ground-truth-free evaluation, LLM-assisted causal discovery, high-dimensional mediation, and Bayesian Mendelian randomization.
It prioritizes graph representation, evidence payload design, and implications for H02-H04.

## Key Findings

The papers converge on a common warning: a causal graph edge is not one evidence type.
It can be a background-knowledge assumption, an LLM-suggested prior, a data-discovered adjacency, a Markov-equivalence-class feature, a latent-variable hypothesis, a mediation estimand, an MR effect estimate, or a qualitative mechanistic link.
Science needs to preserve those distinctions.

## Relevance

Batch 3 directly updates the Evidence Payload Schema task group.
It adds causal-discovery fields that were not explicit after Batches 1-2: `causal_model_ref`, `observed_data_link`, `counterfactual_target`, `identification_assumptions`, `graph_object_type`, `discovery_algorithm`, `method_assumption_set`, `prior_role`, `constraint_type`, `prompt_provenance`, `variable_proposal_provenance`, `self_compatibility_score`, `causal_sufficiency_assumption`, `latent_variable_risk`, `mediation_estimand`, `instrument_set`, and `graph_posterior`.

## Shared Themes

**Causal inference is a roadmap, not an estimator.**
Petersen and van der Laan separate causal model, observed data, counterfactual quantity, identification, statistical estimand, estimation, and interpretation [@Petersen2014].
Science should adopt that separation in causal evidence payloads.

**Causal evidence is plural.**
Fedak et al. show that causal assessment in molecular epidemiology integrates epidemiologic, molecular, toxicological, mechanistic, and experimental streams [@Fedak2015].
This supports causal synthesis facets beyond numeric effect estimates.

**Data integration can create causal validity or causal bias.**
Shi et al. and Bhagwat et al. both show that integrating data for causal inference requires assumptions about selection, confounding, missing variables, variable overlap, and external sources [@Shi2022; @Bhagwat2023].
External variables can be necessary for confounding control, but their extraction and cleaning are part of the causal evidence pipeline.

**Mechanistic graphs are hypothesis generators unless identified and validated.**
COSMOS uses prior knowledge and multi-omics measurements to generate coherent mechanistic hypotheses [@Dugourd2021].
That is valuable, but network coherence should be represented as mechanistic support, not as intervention-validated causal effect evidence.

**Causal discovery outputs have different graph semantics.**
Toolkits such as gCastle and causal-learn expose many methods and graph objects [@Zhang2021gCastle; @Zheng2024].
Science should record whether the output is a DAG, CPDAG, PAG, ADMG, equivalence class, candidate graph, or graph posterior.

**Hidden variables and causal sufficiency are load-bearing.**
Dong et al. show that allowing causally related hidden variables changes what can be identified from observed data [@Dong2023].
Any graph-learning result that assumes causal sufficiency should expose that assumption.

**Ground-truth-free evaluation is possible but limited.**
Faller et al. show that self-compatibility can falsify some causal discovery outputs without ground truth [@Faller2024].
This is a diagnostic signal, not proof.

**LLMs are weak-prior and representation tools.**
Ban et al., Jiralerspong et al., Liu et al., Wan et al., and Wang et al. show several useful LLM roles: direct graph elicitation, soft prior generation, weak-prior decomposition, variable proposal, and post-refinement [@Ban2023; @Jiralerspong2024; @Liu2024HiddenWorld; @Wan2025; @Wang2025].
Across the batch, the safe design is to record LLM outputs as fallible, typed, provenance-rich evidence.

**Causal mechanisms require estimand-specific payloads.**
Yang et al. show that mediation claims require direct/indirect effect definitions and composite-null inference [@Yang2025].
Zuber et al. show that joint MR graph models require instrument assumptions, direction constraints, graph uncertainty, and interventional calculus [@Zuber2025].
Science should not collapse these into generic causal support.

## Implications for Science

**1. Add a causal graph construction pipeline layer.**
Represent candidate variables, annotations, extracted external variables, prior knowledge, discovery runs, graph diagnostics, identified estimands, and estimates as distinct artifacts.

**2. Type causal graph edges by epistemic role.**
At minimum distinguish `assumed_background_edge`, `llm_prior_edge`, `llm_ancestral_constraint`, `data_discovered_adjacency`, `equivalence_class_feature`, `latent_variable_hypothesis`, `identified_causal_effect`, `mediation_path`, and `mechanistic_hypothesis`.

**3. Store causal-discovery method assumptions.**
Payloads need causal sufficiency, faithfulness, rank faithfulness, functional-model assumptions, linearity/nonlinearity, hidden-variable handling, sample size, graph object type, and diagnostic scores.

**4. Treat LLM causal outputs as source/pipeline evidence.**
LLM-generated graph structure should record model, prompt, variable descriptions, retrieval context, temperature/config, output role, constraint type, and soft/hard use.

**5. Add ground-truth-free diagnostics to H03.**
Self-compatibility, variable-subset stability, graph posterior uncertainty, and prior/data disagreement are useful reason-coded revisit signals.

**6. Extend H04 from meta-analysis to causal discovery.**
Guardrails should cover not only synthesized effect estimates but also graph-learning outputs and mechanism claims.
Missing target estimand, missing identification assumptions, causal sufficiency assumptions, or unvalidated LLM priors should become warnings or revisit reasons.

## Open Questions

1. Should Science introduce a distinct `causal-discovery-run` or `graph-estimate` entity kind?
2. How should weak prior knowledge affect graph attention without being treated as evidence for truth?
3. Should LLM-generated causal edges be stored as propositions, assumptions, or evidence artifacts?
4. What minimal graph-object taxonomy is needed: DAG, CPDAG, PAG, ADMG, equivalence class, graph posterior, clustered graph?
5. Should self-compatibility become a standard diagnostic before any learned graph updates causal propositions?
6. How should mediation and Mendelian-randomization outputs connect to ordinary causal proposition updates?

## Prioritized Follow-ups

**P1: Extend `t026` to cover causal discovery outputs.**
H04 currently centers on synthesized evidence strengthening causal propositions.
Batch 3 says learned graph outputs need the same guardrails.

**P2: Extend `t023` with causal graph synthesis node types.**
Add LLM-prior synthesis, causal-discovery-run synthesis, mechanistic-network synthesis, mediation synthesis, and MR graph synthesis.

**P3: Extend `t025` reason codes.**
Add `causal-sufficiency-assumption`, `latent-variable-risk`, `llm-prior-unvalidated`, `prior-data-disagreement`, `graph-object-ambiguous`, `self-incompatible`, `identification-missing`, and `weak-prior-only`.

**P4: Track causal graph construction pipeline design.**
Create and use `[t034]` as the Evidence Payload Schema child task dedicated to causal graph construction artifacts: variable proposal, annotation, prior, discovery run, diagnostics, identified estimand, and effect estimate.

## Relationship to Existing Hypotheses

Batch 3 strengthens H02 by expanding rich payloads from evidence synthesis into graph construction.
It strengthens H03 by adding causal-discovery-specific reason codes.
It strengthens H04 by showing that false causal strengthening can happen before estimation, at the graph-construction and variable-representation stages.

---
id: "synthesis:graphical-models-multiview-integration"
type: "synthesis"
report_kind: "paper-batch-synthesis"
generated_at: "2026-05-06T00:00:00-04:00"
source_commit: "f40a9c5"
source_refs:
  - "paper:Zhang2017CancerGenomics"
  - "paper:Liu2020"
  - "paper:Maity2020"
  - "paper:Zhang2021JointGraphical"
  - "paper:Vahabi2022"
  - "paper:Deleu2023"
  - "paper:Mohammadi2025"
  - "paper:Alnajjar2026"
related:
  - "question:01-evidence-payload-schema"
  - "question:03-source-and-pipeline-provenance"
  - "question:10-causal-graph-construction-pipeline"
  - "question:11-graph-valued-synthesis-artifacts"
  - "hypothesis:h02-rich-evidence-payloads-improve-graph-calibration"
  - "hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting"
  - "hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening"
created: "2026-05-06"
updated: "2026-05-06"
---

# Synthesis: Graphical Models and Multiview Integration

## TL;DR

Batch 4 says that Science needs graph-valued and integration-valued evidence artifacts, not just scalar evidence edges.
Graphical model, multiview integration, clustering, feature-selection, and Bayesian graph-posterior outputs all require payloads that preserve objective, graph type, context scope, view scope, shared-structure assumption, approximation method, posterior uncertainty, and validation role [@Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026].
These outputs can support hypothesis generation, prioritization, calibration, or causal reasoning, but they should not directly strengthen causal edges without H04-style guardrails.

## Key Contribution

The batch extends Batches 2-3 from source/pipeline and causal graph construction into a broader representation claim: many scientific artifacts are themselves graphs, clusters, selected-feature sets, posterior graph distributions, or multiview integration outputs.
Science needs typed synthesis nodes for these objects so that downstream proposition updates know what kind of evidence they are consuming.

## Methods

This synthesis compares eight paper summaries covering mixed graphical model integration, joint mixed sparse graph inference, pan-cancer Bayesian survival integration, joint subpopulation/data-type gene networks, unsupervised multi-omics integration taxonomy, GFlowNet Bayesian network posterior inference, scalable Bayesian GGM structure learning, and variational integrative clustering.

## Key Findings

The batch converges on one representation finding: graph-valued and integration-valued artifacts carry more semantics than ordinary evidence edges.
They encode object type, context scope, data-view scope, shared-structure assumptions, posterior graph uncertainty, feature-selection uncertainty, approximation class, and validation role.
If Science collapses those artifacts into scalar support, it will overcount dependent outputs, lose posterior uncertainty, and risk treating exploratory integration results as causal evidence.

## Relevance

Batch 4 directly updates the Evidence Payload Schema task group.
It adds noncausal graph and integration artifacts to the same design space that Batches 1-3 opened for evidence synthesis, source provenance, and causal graph construction.
The immediate implication is a new representation question (`question:11-graph-valued-synthesis-artifacts`) and task (`[t035]`) for graph-valued synthesis schema design.

## Shared Themes

**Graph-valued evidence is not one thing.**
Batch 4 includes undirected conditional-dependence graphs, Bayesian network DAG posteriors, graph posterior summaries, common/unique network decompositions, and graph-valued data-integration outputs [@Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Deleu2023; @Mohammadi2025].
Science should distinguish these before aggregating or using them as causal support.

**Context scope is load-bearing.**
Several papers infer networks or predictors across biological conditions, tumor groups, subpopulations, or data types [@Zhang2017CancerGenomics; @Maity2020; @Zhang2021JointGraphical].
An output is not just "an edge" or "a selected feature"; it is scoped to a population, subtype, view, measurement platform, and borrowing structure.

**Shared structure is both power and dependence.**
Joint models borrow strength by assuming shared edges, shared sparsity, correlated priors, or common network components [@Zhang2017CancerGenomics; @Liu2020; @Maity2020; @Zhang2021JointGraphical].
This improves estimation but creates dependence among downstream evidence items.
Science should represent shared-structure assumptions as mechanisms, not hide them inside the paper note.

**Posterior graph uncertainty should survive ingestion.**
Deleu et al. and Mohammadi et al. both target posterior distributions over graph structures or graph features [@Deleu2023; @Mohammadi2025].
Science should not collapse graph posterior mass into a single confidence score if the posterior distribution can drive better attention, sensitivity analysis, or future evidence collection.

**Integration objective changes evidence semantics.**
Vahabi and Michailidis show that multi-omics integration methods target different objectives: clustering, biomarker discovery, module discovery, network/pathway analysis, and prediction [@Vahabi2022].
Alnajjar et al. add that integrative clustering and feature selection can produce subtype and selected-feature artifacts with posterior uncertainty [@Alnajjar2026].
These outputs are often prioritization or hypothesis-generation evidence, not confirmatory causal evidence.

**Approximation is provenance.**
Variational inference, pseudo-likelihood, block decomposition, GFlowNet training, sparsity penalties, and finite-mixture assumptions all affect the evidence artifact [@Liu2020; @Deleu2023; @Mohammadi2025; @Alnajjar2026].
Science should record approximation class, sampler or optimizer, diagnostics, convergence status, and sensitivity where available.

## Implications for Science

**1. Add graph-valued synthesis payloads.**
Typed synthesis nodes should handle graph estimates, graph posterior distributions, graph feature summaries, common/unique component decompositions, and graph diagnostics.

**2. Represent integration objective explicitly.**
Payloads should record whether an artifact is for prediction, clustering, feature selection, module discovery, network analysis, pathway analysis, posterior structure learning, or causal estimation.

**3. Add view/context scope.**
Minimum fields should include population/subtype scope, data-view scope, measurement platform, matched-sample status, missingness handling, and external-knowledge use.

**4. Treat shared-structure assumptions as dependence mechanisms.**
Fields should capture shared sparsity, common components, group borrowing, correlated priors, and platform-shared graph structure.
These should feed H03 reason codes and H02 calibration logic.

**5. Preserve posterior graph uncertainty.**
Graph posterior artifacts should expose edge inclusion probabilities, posterior graph samples or summaries, graph prior, sampler, approximation, convergence diagnostics, and posterior-summary role.

**6. Keep exploratory integration outputs out of causal belief slots.**
Clusters, selected features, module memberships, and conditional-dependence edges can prioritize review or generate hypotheses.
They should strengthen causal propositions only through H04 guardrails and explicit identification/validation metadata.

## Open Questions

1. Should Science add a dedicated `graph-valued-synthesis` node family distinct from ordinary synthesis nodes?
2. What is the minimum graph-object taxonomy for noncausal graph artifacts: conditional-dependence graph, Bayesian-network DAG, graph posterior, edge inclusion summary, common component, unique component, module, and cluster-feature map?
3. How should graph posterior uncertainty be represented so it can drive H01/H03 attention without pretending to be a causal posterior?
4. When does a selected feature or cluster label become evidence for a proposition rather than a prioritization artifact?
5. How should shared-structure assumptions (group lasso across data types, common/unique component decomposition, correlated priors across groups) be represented as source dependence across multiple downstream claims? Tracked into `[t031]` as a mechanically detectable joint-model dependence pattern.

## Prioritized Follow-ups

**P1: Extend t023 typed synthesis nodes.**
Add graph-estimate synthesis, graph-posterior synthesis, integrative-clustering synthesis, feature-selection synthesis, module-discovery synthesis, and predictive-integration synthesis.

**P2: Extend t022 payload fields.**
Add `integration_objective`, `graph_artifact_type`, `context_scope`, `view_scope`, `shared_structure_assumption`, `borrowing_structure`, `approximation_class`, `posterior_summary_role`, `edge_inclusion_probability`, `cluster_count`, `feature_relevance_posterior`, and `validation_role`.

**P3: Extend t024/t025 mechanisms and reason codes.**
Add shared-structure bias, posterior-graph-uncertainty, variational-approximation-risk, pseudo-likelihood-risk, clustering-unvalidated, selected-feature-unstable, and view-scope-mismatch.

**P4: Track graph-valued synthesis schema design.**
Create and use `[t035]` as the Evidence Payload Schema child task focused on graph-valued, cluster-valued, selected-feature, module, and predictive-integration artifacts.

## Relationship to Existing Hypotheses

Batch 4 strengthens H02 by showing more artifact types where scalar support edges lose calibration-relevant structure.
It strengthens H03 by adding reason codes tied to graph posterior uncertainty, approximation risk, shared-structure dependence, and exploratory integration outputs.
It strengthens H04 by clarifying that noncausal graph estimates and integration outputs need guardrails before causal use.

## Post-Batch-4 Synthesis Decisions

**New question.**
Batch 4 warrants a distinct representation question:
- `question:11-graph-valued-synthesis-artifacts` asks how Science should represent graph-valued, cluster-valued, selected-feature, module, and predictive-integration artifacts.

**New task.**
The Evidence Payload Schema task group now includes:
- `[t035]` to design the graph-valued synthesis artifact schema.

**No new hypothesis yet.**
Batch 4 strengthens H02, H03, and H04 rather than motivating a standalone H06.
A later hypothesis may be worth drafting after the schema design is concrete:
- **candidate H06:** preserving graph-posterior and integration-artifact structure improves graph calibration and attention over point-graph or scalar-edge summaries.

Hold this until `[t035]` defines measurable artifact types and evaluation targets.

**Schema update.**
Batch 4 extends the candidate payload schema with:
- `integration_objective`;
- `graph_artifact_type`;
- `context_scope`;
- `view_scope`;
- `matched_sample_status`;
- `missingness_handling`;
- `external_knowledge_use`;
- `shared_structure_assumption`;
- `borrowing_structure`;
- `approximation_class`;
- `posterior_summary_role`;
- `edge_inclusion_probability`;
- `cluster_count`;
- `feature_relevance_posterior`;
- `validation_role`.

**Reason-code update.**
Batch 4 extends H03 with:
- `graph-posterior-uncertain`;
- `edge-inclusion-unstable`;
- `shared-structure-dependent`;
- `view-scope-mismatch`;
- `variational-approximation-risk`;
- `pseudo-likelihood-risk`;
- `clustering-unvalidated`;
- `selected-feature-unstable`;
- `exploratory-integration-only`.

## Related Papers and Topics to Consider

Highest-value additions:

- **Joint graphical lasso and fused graphical lasso.** Danaher, Wang, and Witten's joint graphical lasso work is a foundation for many shared-structure graph-estimation methods.
- **Similarity Network Fusion and iCluster lineage.** These are central multiview clustering baselines that would clarify how graph/kernel fusion and latent-variable clustering should be represented.
- **MOFA / MOFA+.** Multi-omics factor analysis is a major model-based integration family adjacent to graph-valued and cluster-valued artifacts.
- **G-Wishart / Bayesian graphical-model uncertainty.** Foundational Bayesian GGM structure-learning papers would help define graph prior, posterior, and edge-inclusion semantics.
- **Stability selection for graphical models and feature selection.** Useful for representing selected-feature instability and edge-inclusion instability as H03 attention signals.
- **Benchmark papers on multi-omics integration.** Batch 4 includes one review, but schema decisions need benchmark evidence on when integration outputs are stable and externally valid.

## Command and Skill Feedback

Batch 4 reinforces the workflow improvements already tracked in `[t029]`, and adds several specifics:

- The paper-summary template should include an explicit `Artifact Semantics` section for outputs such as graph estimates, graph posteriors, clusters, modules, selected features, and predictive models.
- Batch synthesis should prompt for typed synthesis nodes and reason codes automatically when a batch contains methods papers.
- The validator should allow synthesis files to use batch-synthesis sections without warning about paper-summary-only required sections.
- The research-papers command should emit a machine-readable batch manifest with paper keys, local PDF paths, synthesis path, question IDs, task IDs, `[UNVERIFIED]` counts, and citation keys added.
- The command should provide a "remaining PDFs by likely topic" report to support batch selection.

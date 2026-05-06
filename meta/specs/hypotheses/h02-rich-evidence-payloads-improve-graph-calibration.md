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
- paper:Petersen2014
- paper:Shi2022
- paper:Dong2023
- paper:Faller2024
- paper:Zheng2024
- paper:Zuber2025
- paper:Zhang2017CancerGenomics
- paper:Zhang2021JointGraphical
- paper:Vahabi2022
- paper:Deleu2023
- paper:Mohammadi2025
- paper:Alnajjar2026
- paper:Ding2025
- paper:Jin2025
- paper:Si2025
- paper:Yu2026
- paper:Freiesleben2023
- paper:Heyard2025
- paper:Banzi2026
related:
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- question:04-authoring-cost-audit
- question:05-source-dependence-detection
- question:07-llm-agents-as-fallible-sources
- question:10-causal-graph-construction-pipeline
- question:11-graph-valued-synthesis-artifacts
- question:12-agent-tool-kg-operations
- question:13-robustness-reproducibility-evaluation
- hypothesis:h01-stochastic-revisiting
created: '2026-05-05'
updated: '2026-05-06'
---
# Hypothesis H02: Rich evidence payloads improve graph calibration

## Organizing Conjecture

A graph that stores structured evidence payloads will produce better calibrated belief updates than a graph that stores only scalar support or dispute edges.
The load-bearing claim is not that more metadata is always better.
It is that a small set of epistemically relevant fields - comparison target, estimand, model family, priors, heterogeneity, bias model, diagnostics, sensitivity deltas, source reliability, source dependence, pipeline provenance, population transport, identifiability, validation role, graph object type, discovery method, prior role, hidden-variable assumption, diagnostic status, integration objective, context scope, view scope, approximation class, posterior summary role, agent role, tool-chain provenance, graph version, agent evaluation status, robustness target/modifier/tolerance, replication design, reproducibility metric, and lifecycle checklist state - prevents the graph from treating unlike evidence operations as interchangeable [@Zhao2012; @Li2016; @Allen2017; @Thijssen2017; @Dai2023; @Semochkina2025; @Han2026; @Petersen2014; @Shi2022; @Dong2023; @Faller2024; @Zheng2024; @Zuber2025; @Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026; @Ding2025; @Jin2025; @Si2025; @Yu2026; @Freiesleben2023; @Heyard2025; @Banzi2026].

## Proposition Bundle

### Core Propositions

**P1 (calibration).**
For the same set of evidence items, belief updates that consume rich structured payloads will be better calibrated against later validation outcomes than updates that consume scalar support/dispute edges alone.

**P2 (mechanism).**
The calibration gain comes from preserving distinctions that affect evidential meaning: target proposition, comparison set, estimand, aggregation operator, prior, heterogeneity, bias model, source reliability, source dependence, missingness, data-cleaning provenance, source population, target population, diagnostics, graph object type, discovery algorithm, method assumptions, prior role, and identification status.

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

**P7 (causal graph construction).**
Explicit graph-construction payloads reduce false confidence from treating background assumptions, LLM priors, data-discovered adjacencies, equivalence-class features, latent-variable hypotheses, mediation paths, and identified causal effects as the same kind of evidence [@Petersen2014; @Dong2023; @Faller2024; @Zheng2024; @Zuber2025].

**P8 (graph-valued integration).**
Explicit graph-valued and integration-valued payloads reduce false confidence from treating graph estimates, graph posterior summaries, common/unique components, clusters, selected features, modules, and predictive-integration outputs as interchangeable support for propositions [@Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026].

**P9 (agent/tool operations).**
Explicit agent, tool-chain, KG-view, graph-version, and evaluation provenance reduces false confidence from treating automated summaries, graph updates, tool outputs, retrieved contexts, and derived KG views as transparent evidence [@Ding2025; @Jin2025; @Si2025; @Yu2026].

**P10 (robustness/reproducibility evaluations).**
Explicit robustness target/modifier/tolerance, replication design, metric-question alignment, and checklist lifecycle state reduce false confidence from treating "robust", "replicated", and "reproducible" labels as interchangeable validation outcomes [@Freiesleben2023; @Heyard2025; @Banzi2026].

## Current Uncertainty

- Current support is literature-based and architectural, not yet benchmark-based.
- The main unresolved design issue is the minimum viable schema: too little metadata loses the calibration mechanism, while too much metadata becomes authoring friction. `question:04-authoring-cost-audit` addresses this directly.
- The hypothesis assumes later validation outcomes can be defined well enough to score calibration. The "Calibration Ground Truth" subsection below names the candidate ground-truth signals and their failure modes; it remains an open empirical question how often any of them apply per neighborhood.
- It is unclear whether the first implementation should store source reliability, pipeline provenance, causal graph construction stages, and graph-valued integration artifacts directly on evidence payloads, as first-class graph nodes, or both.

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
- Rich-payload aggregation will avoid strengthening causal claims when the apparent support is only a weak LLM prior, ambiguous graph object, hidden-variable-sensitive adjacency, self-incompatible discovery output, or unidentified estimand.
- Rich-payload aggregation will avoid overconfident updates when the apparent support is an exploratory cluster, unstable selected-feature set, posterior-uncertain graph feature, shared-structure-dependent edge, or view-scope-mismatched integration result.
- Rich-payload aggregation will avoid overconfident updates when the apparent support comes from an unvalidated agent, unrecorded tool chain, stale graph version, task-conditioned KG view, failed abstention, or unsafe tool execution.
- Rich-payload aggregation will avoid overconfident updates when validation evidence uses an underspecified robustness claim, a mismatched replication metric, an ambiguous reproducibility dimension, or an incomplete reproducibility checklist.
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
- `literature_evidence` - Causal graph construction depends on explicit causal models, observed-data links, graph object types, hidden-variable assumptions, diagnostics, and identification status, making graph-construction provenance load-bearing [@Petersen2014; @Shi2022; @Dong2023; @Faller2024; @Zheng2024; @Zuber2025].
- `literature_evidence` - Graphical-model and multiview-integration outputs depend on context scope, view scope, shared-structure assumptions, graph posterior uncertainty, clustering assumptions, feature-selection rules, and approximation class [@Zhang2017CancerGenomics; @Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026].
- `literature_evidence` - Scientific agent and KG infrastructure papers show that tool dependencies, execution traces, KG evolution, derived KG views, model bias evaluation, and scientific context-understanding benchmarks are load-bearing provenance [@Ding2025; @Jin2025; @Si2025; @Yu2026].
- `literature_evidence` - Robustness and reproducibility evaluation papers show that validation claims require target/modifier/tolerance semantics, metric-question alignment, and lifecycle checklist state [@Freiesleben2023; @Heyard2025; @Banzi2026].

## Disputing Evidence

- No direct benchmark currently disputes the hypothesis.
- The strongest practical objection is metadata burden: if users or agents cannot populate rich payloads consistently, the schema could reduce coverage or create false precision.
- MCDA-style evidence integration can sometimes be useful with coarser source-quality criteria, suggesting not every workflow needs a full probabilistic payload [@Linkov2017].

## Evidence Needed To Shift Belief

- Build a small evidence-aggregation replay benchmark: hold out later or higher-quality evidence, compare scalar-edge updates against rich-payload updates, and score calibration.
- Implement a toy truth-discovery simulator with source sensitivity, specificity, copying, and missingness; compare scalar trust, decomposed source reliability, and full payload variants.
- Implement a causal-graph construction audit that compares scalar causal-edge updates against role-typed graph outputs: prior, discovered adjacency, equivalence-class feature, diagnostic result, identified estimand, and effect estimate.
- Implement a graph-valued synthesis audit that compares scalar-edge updates against typed graph/integration artifacts: graph estimate, graph posterior summary, common component, context-unique component, cluster, selected feature set, and predictive-integration model.
- Implement a robustness/reproducibility evaluation audit that compares binary validation labels against typed evaluation artifacts: robustness test, replication metric, reproducibility checklist, and lifecycle-stage audit.
- Audit existing paper summaries to see how often the proposed fields can be extracted without unreasonable manual burden.
- Test whether schema fields improve H01 attention sampling by identifying claims that later require revision.

## Related Work

- `question:01-evidence-payload-schema` asks for the minimum field set.
- `question:03-source-and-pipeline-provenance` asks where source and pipeline metadata should live.
- `question:10-causal-graph-construction-pipeline` asks how causal graph construction stages should be represented.
- `question:11-graph-valued-synthesis-artifacts` asks how graph-valued and integration-valued synthesis artifacts should be represented.
- `question:12-agent-tool-kg-operations` asks how agent operations, tool graphs, KG transformations, and graph evolution events should be represented.
- `question:13-robustness-reproducibility-evaluation` asks how robustness, reproducibility, and replication evaluation claims should be represented.
- `hypothesis:h01-stochastic-revisiting` supplies the attention/revisiting motivation.
- Batch 1 supplies contrastive, model-based evidence semantics; Batch 2 adds source behavior and pipeline provenance; Batch 3 adds causal graph construction and discovery provenance; Batch 4 adds graph-valued and integration-valued synthesis artifacts; Batch 5 adds agent/tool/KG operational provenance; Batch 6 adds robustness/reproducibility evaluation semantics.

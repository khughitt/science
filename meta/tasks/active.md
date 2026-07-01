<!-- Task queue. Use /science:tasks to manage. -->

## [t004] Extend H01 r-curve to resolve P5
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:0001-stochastic-revisiting]
- created: 2026-04-24

`[t002]`'s sweep tested `constant_revisit` at `revisit_prob ∈ {0.05, 0.1, 0.2, 0.3}` and the r-curve was monotonically increasing through the upper bound — meaning P5 ("optimal r is a function of uncertainty, not a constant") could not be evaluated. Either the optimum lies above r=0.3 or there is no optimum within sensible bounds. Extend the axis to e.g. `{0.3, 0.4, 0.5, 0.7, 0.9}`, re-run a focused sweep (no need to repeat the existing rows — append new r values for the existing seeds), and update the interpretation with the resolved finding. Specifically: does the optimum vary with `bias_model` × `noise_level` (P5 supported) or land at a single r across all conditions (P5 disconfirmed in the simpler form)?

Lightweight enough to keep within the existing `RUNTIME_BUDGET_SECONDS = 3180s` budget if scoped only to the new r values; re-anchor the gate if the full grid is re-run. Deliverable: an updated interpretation section addressing P5 specifically, with a figure showing the full r-curve.

## [t005] Gaussian effect-size variant of H01 simulator
- priority: P3
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:0001-stochastic-revisiting]
- created: 2026-04-24

The current H01 simulator emits binary Bernoulli signals — H01's recall finding is bounded to that abstraction. An earlier engine handoff note flagged "Beta-Bernoulli artifact" as a candidate alternative explanation that the Bernoulli sweep cannot rule out. Build a Gaussian-effect-size variant: signals drawn from `Normal(mu, sigma)` where `mu = mu_pos` for truth=1 and `mu_neg` for truth=0; conjugate posterior is normal-normal with running mean and variance; recall analog uses a posterior-mean threshold; calibration analog is MSE between posterior mean and truth-conditional effect size.

Tests whether the H01 finding generalises beyond binary signals. If it does, D-003's continuous-belief commitment has stronger empirical footing. If not, H01 is bounded to the Beta-Bernoulli regime and the design principle needs re-examination. Likely a substantial new package alongside `h01_simulator/` (or a parallel module within it) with its own sweep, notebook, and interpretation. Plan before implementation.

## [t014] Epistemic freshness: content-hash upstream change detection
- priority: P3
- status: proposed
- aspects: [software-development, framework-design]
- related: [hypothesis:0001-stochastic-revisiting]
- created: 2026-05-05

Phase 1 freshness uses frontmatter `updated` / `created` dates as the upstream change marker. `docs/plans/historical/2026-05-03-epistemic-dependency-graph-design.md` explicitly deferred content-hash-based change detection to a later phase. Add a graph/materialization path that can detect upstream content changes even when authors forget to bump `updated:`, without replacing the current date-based convention prematurely.

Scope to design first: which authored fields participate in the hash, whether hashes live in the graph only or in a sidecar manifest, how to avoid noise from formatting-only edits, and how this interacts with existing managed-artifact hash utilities.

Surfaced by: EDG design § Decisions, item 5.

## [t015] Cross-project freshness propagation
- priority: P3
- status: proposed
- aspects: [software-development, federation, framework-design]
- related: [hypothesis:0001-stochastic-revisiting]
- created: 2026-05-05

Extend epistemic freshness beyond a single project: a paper, dataset, workflow-run, observation, proposition, or other epistemic upstream added in a parent/child/sibling project should be able to mark downstream hypotheses, questions, propositions, inquiries, and interpretations as `needs-review` across project boundaries.

This is distinct from current federation graph assembly/status. The missing design pieces are cross-project entity address syntax, resolver source of truth (live child sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics when a downstream project is not locally available.

Surfaced by: EDG design trajectory item 2.

## [t016] Derived qualitative standing for epistemic entities
- priority: P3
- status: deferred
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [hypothesis:0001-stochastic-revisiting]
- created: 2026-05-05

Explore replacing implicit binary verdict-state with an explicit qualitative ladder such as `dormant` / `contested` / `supported` / `well-supported`, derived from evidence edges, pre-registered interpretation outcomes, and freshness/attention signals.

Deliberately deferred until `[t011]` weighted sampling shows whether sampling-driven attention is sufficient or whether the data model needs a visible standing field. The implementation must stay qualitative and derived from observable graph state, not LLM-estimated probabilities.

Surfaced by: EDG design trajectory item 3.

## [t018] Cross-project typed blockers
- priority: P3
- status: proposed
- aspects: [software-development, federation]
- created: 2026-05-05

Extend typed task blockers from local entity refs to cross-project refs: a task in project A blocked by an entity in project B, including parent/child/sibling project shapes.

Open design questions: cross-project address syntax, resolver source (live entity-store sweep vs. federated graph snapshot), stale-graph behavior, audit semantics, and how `validate_blocker_refs` / `ReadinessResolver` grow a project-scope parameter without weakening the current strict local validation.

Surfaced by: typed-entity-blockers trajectory item 1.

## [t019] Auto-unblock sweep for ready blocked tasks
- priority: P3
- status: proposed
- aspects: [software-development, task-management]
- created: 2026-05-05

Add a command that flips `status: blocked` to `status: active` for tasks whose typed blockers all report `ready`. Current behavior only nudges in display output (`all ready — run 'tasks unblock <id>'`), which was the right manual-first implementation.

Design before implementation: dry-run by default, explicit `--apply`, clear audit output, no action on unresolved/forced blockers, and a policy for preserving notes about why the task had been blocked. This should land only after the manual readiness workflow has proven stable enough to automate.

Surfaced by: typed-entity-blockers trajectory item 2.

## [t021] Evidence Payload Schema task group
- priority: P1
- status: proposed
- aspects: [software-development, framework-design, hypothesis-testing, causal-modeling]
- related: [question:0002-evidence-payload-schema, question:0003-causal-synthesis-guardrails, hypothesis:0001-stochastic-revisiting, topic:bayesian-methods-continuous-belief]
- group: evidence-payload-schema
- created: 2026-05-05

Coordinate the post-Batch-1 work on quantitative evidence representation.
Batch 1 showed that evidence updates need more than `supports` / `disputes` plus a scalar: they need comparison target, estimand, model family, prior, heterogeneity, bias model, study power, diagnostics, causal target population, aggregation operator, and sensitivity deltas.
Batch 2 extends this with source behavior and pipeline provenance: source reliability, source dependence, omission semantics, missingness class, cleaning/extraction/preprocessing provenance, source population, target population, transport assumptions, prior provenance, identifiability, and validation role.
Batch 3 extends this with causal graph construction provenance: causal model reference, observed-data link, counterfactual target, graph object type, discovery algorithm, method assumption set, prior role, constraint type, prompt and variable-proposal provenance, self-compatibility score, causal-sufficiency assumption, latent-variable risk, mediation estimand, instrument set, and graph posterior.
Batch 4 extends this with graph-valued and integration-valued artifacts: integration objective, graph artifact type, context scope, view scope, shared-structure assumption, borrowing structure, approximation class, posterior summary role, edge inclusion probability, cluster count, feature relevance posterior, and validation role.
Batch 5 extends this with agent/tool/KG operational provenance: agent role, model version, prompt/workflow reference, tool-chain reference, tool I/O contract, safety policy, execution trace, KG view, KG filter objective, subgraph selection method, graph update event type, graph version, validation status, abstention reason, agent evaluation protocol, and Bayes-factor evidence.
Batch 6 extends this with robustness/reproducibility evaluation semantics: evaluation target, robustness target, robustness modifier, modifier domain, intervention type, target tolerance, replication design, reproducibility dimension, metric family, metric question, metric assumptions, checklist reference, lifecycle stage, evaluation result, and validation role.

This parent task tracks the group.
Concrete implementation/design tasks are `[t022]` through `[t026]` plus `[t030]` through `[t041]`.
Do not implement a schema directly from this parent; use it to keep the work visible and grouped.

**Architecture decision (2026-05-06):** the schema is layered — `[t022]` produces the **core** (small, mandatory) plus the **extension contract**; `[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]` produce **typed extensions** that conform to that contract.
Without this split, every batch silently widened the "minimum" schema (~50 fields after Batch 6) and aspect tasks competed as P1 siblings.
`[t025]` is the canonical H03 reason-code registry — aspect tasks declare codes locally and mirror them there with batch provenance.
Lit follow-up tasks (`[t028]`, `[t036]`, `[t039]`, `[t041]`) are P3 so they do not compete with the schema work.

**State (2026-07-01):** `[t022]` shipped and is now carried by the durable
contract at `meta/evidence/t022-core-contract.md`, with generic implementation
coverage in `science/src/science_tool/evidence_payload.py` and
`science/tests/test_evidence_payload_contract.py`. `[t030]` validated the
structural pruning that produced the compact core. Aspect extensions
(`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) remain the place for
family-specific fields and validators.
Carry-forwards: each aspect extension declaring an evaluation/audit/operation
type owns its own target field (no longer in core); paper-extracted claims use
`claim_source_ref`; `partial_fields` marks partially enumerated list fields; and
`uncertainty_summary` is optional so authors do not synthesize qualitative prose
as if it were canonical uncertainty.

Surfaced by: `entities/synthesis/0001-synthesis-bayesian-evidence-synthesis-and-meta-analysis.md`.

## [t024] Represent heterogeneity and bias as evidence-generation mechanisms
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t021, question:0002-evidence-payload-schema, hypothesis:0001-stochastic-revisiting]
- group: evidence-payload-schema
- created: 2026-05-05

Model heterogeneity and bias as explicit mechanisms that bear on evidence interpretation rather than as prose-only caveats.
Candidate mechanism classes include publication bias, p-hacking / selection, model uncertainty, imperfect reference labels, study dependence, source copying, shared pipeline bias, extraction uncertainty, data-cleaning bias, batch effects, missing views, source-target population mismatch, prior-resolved non-identifiability, agent search bias, causal-sufficiency violations, latent-variable misspecification, prior/data conflict, prompt-induced graph bias, variable-proposal bias, self-incompatibility, instrument invalidity, shared-structure bias, graph-posterior uncertainty, variational-approximation risk, pseudo-likelihood risk, clustering instability, selected-feature instability, and view-scope mismatch.

Deliverables:
- propose entity kinds or payload fields for these mechanisms;
- define how they attach to studies, evidence edges, synthesis nodes, propositions, and H01 attention signals;
- identify which mechanisms are general enough for core Science versus project-specific extensions.

## [t025] Add reason-coded uncertainty features to H01 attention
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t021, hypothesis:0001-stochastic-revisiting, question:0002-evidence-payload-schema]
- group: evidence-payload-schema
- created: 2026-05-05

Extend H01-style revisiting beyond posterior/support magnitude by adding reason-coded uncertainty features.
Candidate reasons from Batch 1: `underpowered-evidence`, `high-heterogeneity`, `publication-bias-risk`, `model-uncertainty`, `prior-sensitive`, `imperfect-label`, `boundary-case`, `complex-hypothesis-penalty`, and `estimand-mismatch`.
Candidate reasons from Batch 2: `source-unreliable`, `source-dependent`, `omission-ambiguous`, `missing-view`, `source-target-mismatch`, `prior-resolved-nonidentifiability`, `cleaning-unvalidated`, `repair-uncertain`, `shared-structure-assumption`, and `debiased-inference-missing`.
Candidate reasons from Batch 3: `causal-sufficiency-assumption`, `latent-variable-risk`, `llm-prior-unvalidated`, `prior-data-disagreement`, `graph-object-ambiguous`, `self-incompatible`, `identification-missing`, `weak-prior-only`, `instrument-assumption-risk`, and `mediation-estimand-ambiguous`.
Candidate reasons from Batch 4: `graph-posterior-uncertain`, `edge-inclusion-unstable`, `shared-structure-dependent`, `view-scope-mismatch`, `variational-approximation-risk`, `pseudo-likelihood-risk`, `clustering-unvalidated`, `selected-feature-unstable`, and `exploratory-integration-only`.
Candidate reasons from Batch 5: `agent-source-unvalidated`, `tool-chain-unvalidated`, `safety-check-missing`, `context-retrieval-uncertain`, `information-absence-undetected`, `kg-view-derived`, `graph-version-stale`, `agent-bias-risk`, and `attention-not-evidence`.
Candidate reasons from Batch 6: `robustness-target-ambiguous`, `modifier-domain-missing`, `tolerance-unspecified`, `replication-metric-mismatch`, `reproducibility-dimension-ambiguous`, `checklist-incomplete`, `analysis-plan-missing`, `deviation-unreported`, `code-or-data-unavailable`, and `null-results-omitted`.
Generic evidence-quality codes (added 2026-05-06 from `[t030]` narrow audit; not extension-specific): `single-source-evidence`, `simulated-data-only`, `peer-reviewed-only`, `self-validated-method`, and `legacy-unverified-payload`. These arise on paper-extracted-claim payloads regardless of aspect; mark `peer-reviewed-only` non-blocking, `legacy-unverified-payload` blocking (per v2.1 migration spec), and the others non-blocking-by-default with extension override allowed.

Design how these reasons are recorded on evidence/synthesis artifacts and how `science graph attention-sample` could incorporate them without using LLM-estimated probabilities.
This should follow `[t022]` enough to avoid inventing a parallel schema.
Aspect-extension design tasks (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) each declare their own H03 reason codes; this task is the canonical registry — when those tasks formalize a code, mirror it here with batch provenance.

## [t026] Causal synthesis guardrails
- priority: P2
- status: active
- parent: task:t021
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t021, question:0003-causal-synthesis-guardrails, question:0002-evidence-payload-schema]
- group: evidence-payload-schema
- created: 2026-05-05

Design guardrails for when meta-analytic, synthesized, integrated, discovered, or LLM-elicited evidence can strengthen causal propositions or causal edges.
Require explicit target population, source population where relevant, causal contrast, effect measure, aggregation rule, covariate coverage, transport or exchangeability assumptions, evidence role, validation role, graph object type, discovery method, method assumption set, prior role, hidden-variable assumption, diagnostic status, and identification status before a synthesis or graph-construction node can update a causal proposition.

Special attention:
- non-collapsible measures such as odds ratios;
- target-population mismatch;
- source-population and covariate-coverage mismatch;
- arm-based versus contrast-based aggregation;
- graph estimates versus debiased inferential edge claims;
- LLM priors versus causal evidence;
- discovered adjacencies versus identified causal effects;
- DAG / CPDAG / PAG / ADMG / graph posterior distinctions;
- causal-sufficiency and hidden-variable assumptions;
- self-compatibility diagnostics and variable-subset stability;
- mediation estimands and MR instrument assumptions;
- whether missing metadata should produce a warning, validation error, or H01 revisit signal.

Start from `paper:Berenfeld2026`, `paper:Dai2023`, `paper:Thijssen2017`, `paper:Majumdar2022`, `paper:Petersen2014`, `paper:Shi2022`, `paper:Dong2023`, `paper:Faller2024`, `paper:Zheng2024`, `paper:Zuber2025`, and the causal-modeling aspect.

### Notes

- 2026-05-08: Scope narrowed (2026-05-08): t034 v1.3 design absorbs per-payload schema (graph-object taxonomy, edge-role typing, causal-sufficiency, mediation, MR, self-compatibility, identification). t026 now owns the cross-payload policy layer: non-collapsibility / odds ratios, arm-based vs contrast-based aggregation, source-population transport, and the decision rule for when t034 graph + t023 synthesis + t040 robustness jointly strengthen a causal proposition (warning vs validation error vs H01 revisit signal).

## [t028] Follow-up literature on Bayesian synthesis, causal meta-analysis, and anytime-valid evidence
- priority: P3
- status: proposed
- aspects: [research, hypothesis-testing, causal-modeling]
- related: [question:0002-evidence-payload-schema, question:0003-causal-synthesis-guardrails, topic:bayesian-methods-continuous-belief]
- group: evidence-payload-schema
- created: 2026-05-05

Track highest-value reading leads surfaced by Batch 1:
- Kuiper et al. 2013 on original Bayesian Evidence Synthesis / product Bayes factor;
- Gu et al. 2018 and Hoijtink's informative-hypothesis work behind `bain` and BES;
- Bartoš et al. on RoBMA extensions and publication-bias model averaging;
- Dahabreh / Robertson / Steingrimsson on causally interpretable meta-analysis and target-population transportability;
- e-values / anytime-valid inference for iterative graph evidence monitoring.

Deliverable: either add PDFs to `meta/papers/pdfs/` and process them in a later batch, or write a short topic note explaining why each lead matters.

## [t029] Improve `science-research-papers` batch workflow
- priority: P2
- status: proposed
- aspects: [software-development, skills, research]
- related: [question:0002-evidence-payload-schema]
- group: research-papers-workflow
- created: 2026-05-05

Update the `science-research-papers` skill / command and related tooling based on Batch 1 friction.

Concrete improvements to design and implement:
- resolve software-profile research-layer summaries to `doc/background/papers/`, not `doc/papers/`;
- make `question reserve --source-refs` normalize bare BibTeX keys to `cite:<key>` or reject them early with a clear error;
- add real batch mode where workers write only paper summaries and the orchestrator owns `references.bib`, questions, and synthesis to avoid races;
- add a dedicated batch-synthesis template/location so validation does not treat synthesis files as paper summaries, and silence "paper-summary-only required sections" warnings on synthesis-shape files;
- add an "Implications" section to paper summaries for graph implications, evidence-schema implications, H01/revisiting implications, and command/skill feedback;
- add an `Artifact Semantics` section to the paper-summary template covering output object type (graph estimate, graph posterior, cluster, module, selected feature, predictive model), context/view scope, shared-structure assumptions, approximation class, and validation role (surfaced by Batch 4 methods papers where the artifact type and its causal-use restrictions are load-bearing);
- prompt the orchestrator to propose typed synthesis nodes and reason codes automatically when a batch contains methods papers (graph-estimation, graph-posterior, integrative-clustering, feature-selection, module-discovery, predictive-integration);
- emit a machine-readable batch manifest at end of run with paper keys, local PDF paths, synthesis file path, related question IDs, related task IDs, `[UNVERIFIED]` counts, and citation keys added;
- emit a "remaining PDFs by likely topic" report after each batch to support batch selection for the next run;
- add a post-batch prompt that proposes questions, hypotheses, task groups, and command improvements;
- record `[UNVERIFIED]` counts in the orchestrator report.
- register `synthesis` as a graph entity kind or keep batch synthesis artifacts out of graph-audited entity scans; `hypothesis create` currently reports unknown `synthesis` kind while scanning paper-batch synthesis files.
- add agent/workflow provenance frontmatter to generated summaries and syntheses;
- record explicit `abstention` / `insufficient-context` cases when a PDF does not support a requested claim;
- add a command/skill registry graph with capabilities, expected inputs/outputs, safety constraints, and validation commands.

Start with a design pass before editing generated commands or skills.

## [t031] Source-dependence detection design
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t024, task:t025, task:t033, task:t035, task:t037, task:t038, question:0004-source-and-pipeline-provenance, question:0006-source-dependence-detection, question:0008-llm-agents-as-fallible-sources, question:0011-graph-valued-synthesis-artifacts, question:0012-agent-tool-kg-operations, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: evidence-payload-schema
- created: 2026-05-05

Stratify evidence-source dependence patterns by mechanical detectability and prototype detectors for the high-leverage cases.

Mechanically detectable candidates: shared dataset identifiers, shared author lists, citation chains, shared extractor or prompt versions, near-duplicate text, shared upstream synthesis nodes, joint-model shared-structure dependence (when multiple condition-, subtype-, view-, or platform-specific outputs come from a single estimator with group lasso, common/unique component decomposition, correlated priors across groups, or shared sparsity), shared posterior sampler / approximation runs (when multiple graph-feature claims are read from the same posterior chain or variational fit), joint-operator dependence (when multiple evidence items are produced by the same agent, model version, prompt or system-prompt version, or tool chain), and shared-KG-view dependence (when multiple downstream claims are derived from the same task-conditioned subgraph, RAG retrieval context, correlation graph, or KG-diffusion view, even when the ostensibly underlying source graph differs).
Annotation-required candidates: methodological convergence by independent groups, conceptual dependence through shared theoretical frameworks, prior-knowledge contamination across paper summaries.

Deliverables:
- a dependence-pattern taxonomy with detectability score per pattern;
- prototype detectors for two or three high-leverage patterns;
- a design note for how detected dependence attaches to evidence edges and propagates to aggregation operators;
- alignment notes with `[t024]` (heterogeneity / bias mechanisms) and `[t025]` (reason codes).

## [t032] Scope sequential / anytime-valid evidence as a graph aggregation primitive
- priority: P2
- status: proposed
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t028, question:0007-sequential-anytime-valid-evidence, hypothesis:0005-sequential-evidence-improves-attention, hypothesis:0001-stochastic-revisiting, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: sequential-evidence
- created: 2026-05-05

Resolve t028's anytime-valid reading lead into either a topic note + simulator extension or a deferred-with-reason record.

Steps:
- ingest the e-value / test-martingale / confidence-sequence references queued in `[t028]`;
- write a topic note `entities/topics/sequential-evidence.md` linking these methods to H01 / H03 attention and H02 payload state;
- audit current and likely-future project graph state for the realized prevalence of optional stopping and unbounded revisiting;
- propose a sequential-evidence extension to the H01 simulator: propositions receive evidence over time, attention policies compare fixed-N posterior, BMA-style, and anytime-valid evidence levels;
- decide whether H05 graduates to an active simulation track or stays speculative pending stronger upstream evidence.

## [t033] Model LLM agents as fallible evidence sources and graph-governed operators
- priority: P2
- status: active
- aspects: [software-development, framework-design, research]
- related: [task:t022, task:t024, task:t031, task:t037, task:t038, question:0008-llm-agents-as-fallible-sources, question:0006-source-dependence-detection, question:0012-agent-tool-kg-operations, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: agent-source-modeling
- created: 2026-05-05

Treat LLM agents (paper summarizers, claim extractors, batch synthesizers, attention samplers, curation assistants, tool-using science agents) as first-class fallible source entities AND as graph-governed operators, and design the minimum representation.

Deliverables:
- a taxonomy of agent roles in this project, with current and planned uses (source-side: summarizer, extractor, synthesizer, sampler; operator-side: planner, tool executor, KG mutator, retriever, evaluator);
- a minimal agent-source schema: agent identifier, model version, prompt or system-prompt version, tool version, validation history, and dependence links to other agents;
- an operator-side extension covering `tool_chain_ref`, `tool_io_contract`, `execution_trace_ref`, `safety_policy_ref`, `abstention_reason`, `agent_evaluation_protocol`, and Bayes-factor-style evaluation history (per Si2025) that distinguishes "no evidence of bias" from "evidence of no bias";
- a `derived_by` field design for evidence payloads, plus a `validation_status` field;
- an alignment note with `[t031]` on shared-prompt, shared-model, shared-tool-chain, and shared-KG-view dependence;
- alignment with `[t037]` (operations schema) so the source-side agent record links to operator-side records via shared identifiers rather than duplicating fields;
- a self-application pass: mark which existing artifacts in this project (including the Batch 1, Batch 2, Batch 3, Batch 4, and Batch 5 syntheses) should be retroactively annotated with agent provenance, and at what granularity.

Granularity is a key design decision; expect to defend the chosen level (per-prompt, per-tool-version, per-model) against alternatives.

**Inputs from `[t030]` D4 (2026-05-06)** at `meta/doc/plans/historical/2026-05-06-t030-full-audit-results.md`: two verbatim-identical blind-LLM extraction passes disagreed within-1 on ~25–40% of rubric-ambiguous fields, with systematic pass-1-higher-than-pass-2 calibration drift (17/25 cases). Implications for this task: (a) per-extraction confidence and per-call agent identity are needed in agent-source records; (b) ensemble-of-N or repeated-extraction-with-disagreement-flagging should be considered for high-stakes fields; (c) the deferred full-context-manual-vs-blind-LLM signal is required to fully ground this task and should be obtained via a fresh audit before agent-source modeling commits.

### Notes

- 2026-05-08: Scope reduced (2026-05-08): t037 v1.3 design absorbs source-side agent schema (agent/agent_role registry entities, validation_status, agent-evaluation extension with Si2025 Bayes-factor semantics). Residual t033 scope to re-evaluate when t037 closes: (a) self-application / retroactive agent-provenance pass on Batch 1-5 syntheses; (b) granularity decision (per-prompt vs per-tool-version vs per-model); (c) source-dependence integration with t031 (shared prompt/model/tool-chain/KG-view); (d) repeated-extraction-with-disagreement policy per t030 D4 calibration drift finding.

## [t035] Design graph-valued synthesis artifact schema
- priority: P1
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t022, task:t023, task:t024, task:t025, task:t026, task:t034, question:0011-graph-valued-synthesis-artifacts, question:0010-causal-graph-construction-pipeline, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting, hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening]
- group: evidence-payload-schema
- created: 2026-05-06

Design how Science represents graph-valued, cluster-valued, selected-feature, module, and predictive-integration artifacts.

Candidate artifact types:
- conditional-dependence graph estimate;
- Bayesian network DAG posterior;
- graph posterior summary;
- edge inclusion probability table;
- common / context-unique graph component;
- integrative cluster assignment;
- selected-feature set;
- module or pathway membership;
- predictive integration model.

Deliverables:
- a graph/integration artifact taxonomy with strict enum candidates for `graph_artifact_type` and `integration_objective`;
- a payload schema covering `context_scope`, `view_scope`, `matched_sample_status`, `missingness_handling`, `shared_structure_assumption`, `borrowing_structure`, `approximation_class`, `posterior_summary_role`, `edge_inclusion_probability`, `cluster_count`, `feature_relevance_posterior`, and `validation_role`;
- rules for whether each artifact updates propositions, prioritizes attention, creates hypotheses, or merely records exploratory state;
- H03 reason-code mapping for graph posterior uncertainty, shared-structure dependence, view-scope mismatch, approximation risk, clustering validation, and selected-feature stability;
- H04 guardrail notes for preventing noncausal graph or clustering outputs from strengthening causal propositions without identification metadata.

Start from Batch 4 synthesis: `entities/synthesis/0004-synthesis-graphical-models-and-multiview-integration.md`.

## [t036] Follow-up literature on graph-valued and multiview synthesis artifacts
- priority: P3
- status: proposed
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t035, question:0011-graph-valued-synthesis-artifacts, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting, hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening]
- group: evidence-payload-schema
- created: 2026-05-06

Track follow-up papers needed to make `[t035]` empirically and historically grounded.

Highest-value additions:
- Danaher, Wang, and Witten on joint graphical lasso / fused graphical lasso;
- Similarity Network Fusion and iCluster lineage papers for multiview clustering and latent-variable integration;
- MOFA / MOFA+ papers for factor-analysis-style multi-omics integration;
- foundational G-Wishart / Bayesian graphical-model structure-learning papers for graph prior and posterior semantics;
- stability selection papers for graph and feature-selection uncertainty;
- benchmark papers comparing multi-omics integration methods under external validation.

Deliverable: either add PDFs and process them in a later batch, or write a topic note explaining how each family should influence `graph_artifact_type`, `integration_objective`, posterior uncertainty, validation role, and H03 reason codes.

## [t038] Design graph evolution and KG view provenance
- priority: P1
- status: proposed
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t021, task:t035, task:t037, question:0012-agent-tool-kg-operations, question:0004-source-and-pipeline-provenance, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: evidence-payload-schema
- created: 2026-05-06

Design how Science records graph evolution, graph versions, KG filtering, derived KG views, and replayable graph update events.

Candidate event types:
- entity creation;
- evidence edge creation;
- graph edge creation;
- rename;
- merge;
- split;
- deprecation;
- validation;
- contradiction;
- derived-view generation;
- embedding-view generation;
- rollback or replay.

Deliverables:
- a `graph_update_event` taxonomy with strict enum candidates;
- a versioning model for graph state, derived KG views, embedding views, and batch-generated updates;
- provenance fields for `kg_view_ref`, `source_graph_ref`, `kg_filter_objective`, `subgraph_selection_method`, `removed_edge_policy`, `graph_version`, `graph_update_event_type`, `validation_status`, and `replay_command`;
- guidance for representing RAG contexts, task-conditioned subgraphs, correlation-discovery outputs, and KG diffusion/denoising views;
- H03 reason-code mapping for `kg-view-derived`, `graph-version-stale`, `attention-not-evidence`, and `context-retrieval-uncertain`.

Start from Batch 5 synthesis: `entities/synthesis/0006-synthesis-scientific-agents-and-knowledge-graph-infrastructure.md`.

## [t039] Follow-up literature on scientific agents, tool provenance, and KG operations
- priority: P3
- status: proposed
- aspects: [research, software-development, framework-design]
- related: [task:t037, task:t038, question:0012-agent-tool-kg-operations, question:0008-llm-agents-as-fallible-sources, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: agent-source-modeling
- created: 2026-05-06

Track follow-up papers and standards needed to ground the Batch 5 agent/tool/KG operations layer.

Highest-value additions:
- Toolformer / ReAct / Reflexion / Voyager-style agent papers for tool use, replanning, memory, and self-correction patterns;
- RAG evaluation papers on retrieval provenance, faithfulness, answer grounding, and abstention;
- W3C PROV and workflow provenance systems for durable operation-record semantics;
- Galaxy, Snakemake, Nextflow, and CWL papers/docs for scientific workflow provenance and reproducibility;
- SHACL, KG validation, and constraint-checking papers for graph-evolution safety;
- agent safety and dual-use risk papers for scientific tool execution.

Deliverable: either add PDFs and process them in a later batch, or write a topic note explaining how each family should influence operation records, tool graphs, KG update events, evaluation competencies, safety status, and H03 reason codes.

## [t040] Design robustness/reproducibility evaluation schema
- priority: P1
- status: proposed
- aspects: [software-development, framework-design, hypothesis-testing, research]
- related: [task:t021, task:t022, task:t025, task:t030, question:0013-robustness-reproducibility-evaluation, question:0002-evidence-payload-schema, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting, topic:analytic-flexibility-and-replication]
- group: evidence-payload-schema
- created: 2026-05-06

Design how Science represents robustness tests, replication studies, reproducibility metrics, and checklist audits.

Candidate artifact types:
- `robustness_test`;
- `replication_study`;
- `reproducibility_metric_result`;
- `reproducibility_checklist_audit`;
- `reporting_completeness_audit`;
- `code_data_availability_check`;
- `deviation_report_check`.

Deliverables:
- an evaluation-artifact taxonomy with strict enum candidates for `evaluation_artifact_type`, `reproducibility_dimension`, `metric_family`, and `lifecycle_stage`;
- a payload schema covering `evaluation_target`, `robustness_target`, `robustness_modifier`, `modifier_domain`, `intervention_type`, `target_tolerance`, `replication_design`, `metric_question`, `metric_assumptions`, `success_threshold`, `uncertainty_treatment`, `checklist_ref`, `evaluation_result`, and `validation_role`;
- rules for whether each evaluation artifact updates belief, updates attention, records reporting quality, or blocks a causal/evidence update;
- H03 reason-code mapping for `robustness-target-ambiguous`, `modifier-domain-missing`, `tolerance-unspecified`, `replication-metric-mismatch`, `reproducibility-dimension-ambiguous`, `checklist-incomplete`, `analysis-plan-missing`, `deviation-unreported`, `code-or-data-unavailable`, and `null-results-omitted`;
- alignment notes with `[t030]` so H02 calibration benchmarks use typed validation outcomes rather than binary replication-success labels.

Start from Batch 6 synthesis: `entities/synthesis/0005-synthesis-robustness-and-reproducibility-evaluation.md`.

## [t041] Follow-up literature on replication metrics, robustness, and reproducibility standards
- priority: P3
- status: proposed
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t040, question:0013-robustness-reproducibility-evaluation, topic:analytic-flexibility-and-replication, hypothesis:0002-rich-evidence-payloads-improve-graph-calibration, hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: evidence-payload-schema
- created: 2026-05-06

Track follow-up papers needed to ground `[t040]` in the broader reproducibility and robustness literature.

Highest-value additions:
- Goodman, Fanelli, and Ioannidis on reproducibility terminology;
- National Academies 2019 report on reproducibility and replicability in science;
- Nosek et al. on preregistration, registered reports, and transparency reforms;
- Anderson and Maxwell on replication goals and metrics;
- Hedges and Schauer / Pawel and Held / Mathur and VanderWeele on replication success and heterogeneous effects;
- Munafo et al. 2017 manifesto for reproducible science;
- WILDS, distribution-shift, and robustness-benchmark papers for ML robustness evaluation.

Deliverable: either add PDFs and process them in a later batch, or write a topic note explaining how each family should influence evaluation artifacts, metric-family enums, checklist fields, H02 validation outcomes, and H03 reason codes.

## [t042] Design synthesis artifact lifecycle and output-artifact model
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [task:t023, task:t038, question:0002-evidence-payload-schema]
- group: evidence-payload-schema
- created: 2026-05-07

Define how synthesis nodes, output artifacts, propositions, validation runs, and downstream syntheses form a derivation DAG. Cover replay, invalidation, supersession, reason-code propagation, artifact reuse, and the decision rule for first-class output artifacts versus embedded output fields.

## [t043] Cross-project blockers spec
- priority: P1
- status: deferred
- aspects: [software-development, framework-design]
- related: [topic:cross-project]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t044] Workspace registry design
- priority: P2
- status: deferred
- aspects: [software-development, framework-design]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t045] Remote peers via cloneable repos
- priority: P3
- status: deferred
- aspects: [software-development, framework-design]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t046] Versioned entity references
- priority: P3
- status: deferred
- aspects: [software-development, framework-design]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t047] L2 caching & freshness
- priority: P3
- status: deferred
- aspects: [software-development]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t048] Composite graph policy controls (compose: opt-in)
- priority: P2
- status: deferred
- aspects: [software-development, framework-design]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t049] Service / capability exchange (Layer 3)
- priority: P2
- status: deferred
- aspects: [software-development, framework-design]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t050] Multi-user identity scoping
- priority: P3
- status: deferred
- aspects: [software-development]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t051] Auto-unblock / change notification
- priority: P3
- status: deferred
- aspects: [software-development]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t052] Symmetry tooling (peers check --symmetric)
- priority: P3
- status: deferred
- aspects: [software-development]
- group: project-peers
- created: 2026-05-07

Deferred trajectory item from project-peers Decision 13

## [t053] Adaptive project topology task group
- priority: P1
- status: proposed
- aspects: [software-development, hypothesis-testing]
- group: adaptive-project-topology
- created: 2026-05-17

Coordinate the meta-research work on evidence-responsive project topology: promotion of dense/high-uncertainty themes into projects, demotion or archival of stale branches, cross-project linking, and human approval gates. This is a Science/meta idea, distinct from the biological model proposed for ~/d/bio/meta.

## [t054] Define adaptive topology signal metrics
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [task:t053]
- group: adaptive-project-topology
- created: 2026-05-17

Define a v1 signal rubric for project/theme promotion and demotion, split into computable signals from existing artifacts and judgment-required prompts for human review. V1 should score only artifact-derived signals such as graph edges, task counts, commit recency, paper links, unresolved refs, and stale inputs; uncertainty, novelty, coherence, and false-positive risk should remain reviewer prompts until the pilot shows which can be operationalized.

## [t056] Design topology-change recommendation workflow
- priority: P2
- status: proposed
- aspects: [software-development]
- related: [task:t053]
- group: adaptive-project-topology
- created: 2026-05-17

Design a manual-first workflow that recommends promote, split, merge, demote, archive, create commons resource, or create synthesis task actions. Include reviewer/cadence, dry-run output, required evidence, human approval gates, audit logs, and a provenance contract for stable IDs, archived graph nodes, decisions, and task history.

## [t057] Pilot topology audit across Science, health, and cancer projects
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [task:t053]
- group: adaptive-project-topology
- created: 2026-05-17

Write a baseline-of-harm note for current topology pain points, then apply the initial topology audit to Science, health-meta, cycles, cancer-evolution, pre-cancer, and pan-disease artifacts. Use the pilot to estimate false positives, identify missing signals, and decide whether ~/d/bio/meta is a clean manually promoted project candidate.

## [t058] Prepare bio/meta scaffold brief as a topology case study
- priority: P1
- status: proposed
- aspects: [hypothesis-testing]
- related: [task:t053]
- group: bio-meta-scaffold
- created: 2026-05-17

Write a concise project brief for ~/d/bio/meta as the first manually promoted biological meta-model project. The brief must explicitly settle the health/meta vs bio/meta boundary: bio/meta as substrate model for multiscale dynamics, observability, reachability, and time/space; health/meta as applied health lens for homeostasis, disease, intervention, and family coordination.

## [t059] Reconcile theme_kind enum sources across template, schema, and active profiles
- priority: P2
- status: proposed
- aspects: [software-development]
- created: 2026-05-18

Three sources currently define the theme_kind enum and they do not agree. (1) templates/theme.md defaults to 'methodological' with no enum documentation; (2) schemas/mixin-theme-2.0.json declares enum: methodological | conceptual | empirical | domain; (3) some active profiles (e.g., the cancer/mechanisms/evolution project's resolved profile) accept methodological | biological | translational | evidence-quality | organizational instead. Pick a source of truth and propagate, or formally document that active profiles may extend/replace the upstream enum (with a discovery path: science-tool entity sections theme should show the effective enum). Deliverable: (a) reconciliation decision in core/decisions.md, (b) updated schema if the upstream enum changes, (c) updated profile schemas if they should align with the upstream, (d) documentation pointer if extension is the intended pattern. Surfaced 2026-05-18 while creating themes for cancer/mechanisms/evolution: agent picked theme_kind=conceptual (upstream-correct) which failed validation against the active profile that requires biological/translational/etc. Templates were updated inline 2026-05-18 (added enum comments to templates/theme.md and science/model/src/science_model/templates/theme.md) to mitigate the immediate discoverability problem; this task is the structural fix.

## [t060] Extend science-tool entity sections to show frontmatter constraints
- priority: P2
- status: proposed
- aspects: [software-development]
- created: 2026-05-18

Currently 'science-tool entity sections <kind>' (and its alias 'science entity sections <kind>') lists only the body sections required by a template — it does NOT show frontmatter field requirements or enum constraints. This is the CLI surface that should answer 'how do I create a valid <kind>?', so the absence of frontmatter info forces agents/users to either hand-inspect schema files or guess and validate by trial-and-error. Deliverable: extend the command output to include a Frontmatter section listing each required/optional field, its type, and (for enums) the accepted values. The accepted values must come from the effective schema (post-profile-resolution), not just the upstream mixin schema, so the output reflects what will actually validate in the current project. Originally surfaced 2026-05-18 while creating themes for cancer/mechanisms/evolution: the agent ran 'science-tool entity sections theme' looking for theme_kind enum, got only body sections, fell back to inspecting mixin-theme-2.0.json, which had a different enum than the active profile actually accepted. Sibling: t059 (reconcile theme_kind enums); together they close the discoverability gap.

## [t061] Add /science:add-theme skill / slash command
- priority: P3
- status: proposed
- aspects: [software-development]
- created: 2026-05-18

Add a /science:add-theme skill analogous to /science:add-hypothesis so that themes are discoverable from the slash-command list and agents have a guided path to creating them. The skill should wrap 'science-tool entity create theme' with interactive scaffolding: ask for theme_kind (using the effective profile's enum), theme_scope, and the initial related entities; produce a draft with the canonical body sections pre-populated with hint comments; and optionally cross-link to related federation-scope themes when appropriate. Originally surfaced 2026-05-18 while creating themes for cancer/mechanisms/evolution: the agent searched the available skills list, found /science:add-hypothesis but no /science:add-theme, and fell back to inventing an ad-hoc theme format. The fallback was eventually rejected by schema validation but it cost the user a multi-turn correction cycle. Depends on: t060 (entity sections CLI should expose theme_kind enum) so the interactive prompt can pull from the effective schema.

## [t062] Improve schema-validation error messages with discovery hints
- priority: P3
- status: proposed
- aspects: [software-development]
- created: 2026-05-18

When 'science tasks list' or other inventory commands hit a schema-validation failure, the error currently shows only the failing field and the accepted-values list (e.g., 'theme_kind: Input should be methodological, biological, translational, evidence-quality or organizational'). Extend the error to include actionable next steps: (a) suggest 'science-tool entity sections <kind>' for the full effective-schema view (once t060 lands, this will include frontmatter constraints), (b) suggest 'science-tool entity create <kind> "Title"' as the preferred path for new entities, (c) cite the source schema file path so users can inspect it directly. Originally surfaced 2026-05-18 while creating themes for cancer/mechanisms/evolution: the schema-validation error correctly listed the accepted theme_kind values but offered no path forward — the agent only discovered 'science-tool entity create theme' existed by probing the CLI separately. Pairs with t060 (frontmatter constraints in entity sections) and t061 (add-theme skill); together they close the create-a-valid-entity discoverability gap from three angles. Low engineering cost relative to t060/t061; mostly a string-formatting change at the validation error sites.

## [t068] Cross-project entity reference syntax (single addressable world)
- priority: P1
- status: proposed
- aspects: [software-development]
- related: [hypothesis:0007-working-model, hypothesis:0006-adaptive-project-topology-improves-research-fit, question:0014-adaptive-project-topology, task:t043]
- created: 2026-05-31

Design a VALIDATING cross-project entity reference syntax. Surfaced by fb-2026-05-31-012 (writing h00): a foreign 'type:id' ref resolves against the local repo so it reads as broken, and the refs-checker even resolves the bare token locally — forcing honest foreign mentions into untyped prose (the interim h00 policy), which defeats validation, graph linkage, and cross-boundary freshness.

K.H. framing (load-bearing): all projects live in ONE WORLD; a project is sub-structure, itself decomposable into hypothesis/domain neighborhoods (h00 patches). A cross-project ref is a same-world ref crossing a sub-structure boundary, not a foreign ref needing a bridge — the resolver should treat project scope as a grouping level in one addressable space.

This is the single primitive the recurring 'cross-project address syntax' open item in t015 (freshness propagation), t018 (typed blockers), and t043 (cross-project blockers spec) each separately defer; land it once. Design questions to settle: address grammar (project-qualified id e.g. pan-disease::task:t071 vs URN), resolver source of truth (live sibling-repo sweep vs federated graph snapshot), behavior when the target project is not locally available, validation severity (resolvable-vs-unresolvable vs warn-on-stale), and how refs-checker stops greedily resolving bare local tokens. Aligns h00 (multi-scale patch<=project<=collection), h06/q14 (adaptive topology), and the project-peers group (t043-t052).

## [t069] Harden L1 patch prototype before it becomes a pattern (sweep mapping + fix PROV-O)
- priority: P2
- status: proposed
- aspects: [software-development]
- related: [hypothesis:0007-working-model, task:t065, task:t066]
- created: 2026-06-01

Two pre-pattern hardening items from the t065 review (2026-06-01), to settle before the L1 patch is treated as canonical:

(1) EVIDENCE-FIELD MAPPING SENSITIVITY (review #5). The prototype's mapping choices are the main sensitivity surface and are currently asserted, not swept: ClinGen-strict -> strength=strong, OMIM/GeneReviews-broad -> moderate, curated panels -> is_reference_dataset=True, and q99 ubiquity defines publication gravity (meta/src/h00_patch_l1/model.py). Sweep these (esp. the pub-gravity ubiquity threshold and the strength tiers) and report how the headline numbers (u=0.50/0.67/1.0; the 53% double-counting discount) move. Can fold into t066.

(2) PROV-O ACTIVITY/AGENT MODELING (review #3). The current emission (meta/src/h00_patch_l1/patch.py) uses prov:wasGeneratedBy with an AGENT IRI as a placeholder. PROV-O expects generation by an Activity, with agents linked via attribution/association (prov:wasAttributedTo / prov:wasAssociatedWith). Source provenance, AI extraction/prototype provenance, and human ratification are DISTINCT activities and must not collapse into one edge annotation. Model them as separate activities before this emission is reused as a pattern.

Until both are done, t065 claims stay scoped: 'PROV-O round-trips structurally' (not 'fully carries the agent axis'); 'supports derived opinion as the default next representation' (not 'decides no v4 successor needed').

## [t070] Validate + variance-guard the t066 PMI correction at scale
- priority: P2
- status: proposed
- aspects: []
- created: 2026-06-01

t066 demonstrated the latent-construct (PMI) correction subtracts the publication-attention axis cleanly at BOTH ends of the slice (7 panel genes positive, 10 universal genes negative, for CMT + HSP) and flips raw-ranking errors. Two things it did NOT establish: (1) behavior on the ambiguous MIDDLE — the clean step is partly a property of a slice built to contrast extremes, so PPMI>0 is a correction, not a calibrated classifier; needs the full 18206x3831 matrix + held-out-panel validation (overlaps pan-disease recall@K / cluster-mate-AUC, the cross-project proving ground). (2) a sampling-variance guard — rare cells have high-variance PMI (e.g. CYP7B1 cooc=39); add shrinkage / Poisson-significance before any fine ranking or near-zero threshold. Code: meta/src/h00_patch_l1/latent.py. Interpretation: interpretation:0003-t066-latent-correction-2026-06-01.

## [t071] Refresh user-guide docs for v3 three-root layout
- priority: P2
- status: proposed
- aspects: []
- group: docs
- created: 2026-06-22

Phase 5 of the adapter-entity-layout migration (checkpoint: docs/audits/plans-cleanup/2026-06-03-entity-layout-v3-checkpoint.md) updated only docs/user-guide/project-layout.md to the v3 three-root model (entities/ owners, overlays/ borrows, doc/ prose). The rest of docs/user-guide/ is still written for the v2 world: entities.md, science-model.md, epistemic-model.md, evidence-lines.md, graph-and-derived-state.md, agent-workflows.md, cross-project-work.md, health-and-validation.md, introduction.md, index.md mostly describe specs/ + doc/<type>/ placement and never mention entities/ or overlays/. Audit all user-guide docs and bring filesystem/layout references in line with layout_version: 3: owners under entities/<kind>/ (id-local filenames), overlays under overlays/<type>/, doc/ prose-only. Cross-link to the new Three-Root Entity Layout section in project-layout.md. Scope is docs-only; no code/behaviour changes. Enumerate stale refs with: python3 -c "import re,pathlib; [print(p) for p in pathlib.Path('docs/user-guide').glob('*.md') if re.search(r'specs/|doc/(datasets|papers|topics|themes|workflows)', p.read_text())]"

## [t072] Migrator pre-mutation gate should be a superset of post-mutation validation
- priority: P2
- status: proposed
- aspects: []
- group: v3-migration
- created: 2026-06-22

science entities migrate --apply has a weaker pre-mutation gate (_postmove_audit_failures in entity_layout_migration.py, via audit_project_sources on the simulated post-move model) than its final post-mutation full graph validation. On protein-landscape, --apply passed the pre-mutation gate (0 unresolved) but then failed post-mutation with 11 unresolved report:/task: related-refs AFTER git-mv'ing 243 owners, self-reporting 'working tree modified; run git restore' and forcing a rollback. The pre-mutation gate should be a superset of the post-mutation validation so fan-out projects fail fast pre-mutation instead of apply-then-rollback. Align the two reference surfaces.

## [t073] Design first-class minimum viable synthesis artifacts
- priority: P2
- status: proposed
- aspects: []
- related: [task:t021]
- group: evidence-payload-schema
- created: 2026-06-26

Cancer-meta t026 surfaced a reusable Science pattern: when quantitative synthesis is blocked, the workflow should still produce a structured artifact rather than a terminal abstention. Design whether Science should provide template or command support for minimum viable synthesis outputs: structured comparison, heterogeneity or incompatibility statement, missing-fields list, follow-up route, and an explicitly adapted certainty block when formal GRADE/SWiM is out of scope. Relate this to evidence payload fields, uncertainty reason codes, and source-reliability dimensions without making project-specific certainty labels part of core semantics. Origin: cancer-meta question:0013-adapted-federation-certainty-blocks and feedback fb-2026-06-26-001.

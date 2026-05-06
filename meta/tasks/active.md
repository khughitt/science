<!-- Task queue. Use /science:tasks to manage. -->

## [t004] Extend H01 r-curve to resolve P5
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-04-24

`[t002]`'s sweep tested `constant_revisit` at `revisit_prob ∈ {0.05, 0.1, 0.2, 0.3}` and the r-curve was monotonically increasing through the upper bound — meaning P5 ("optimal r is a function of uncertainty, not a constant") could not be evaluated. Either the optimum lies above r=0.3 or there is no optimum within sensible bounds. Extend the axis to e.g. `{0.3, 0.4, 0.5, 0.7, 0.9}`, re-run a focused sweep (no need to repeat the existing rows — append new r values for the existing seeds), and update the interpretation with the resolved finding. Specifically: does the optimum vary with `bias_model` × `noise_level` (P5 supported) or land at a single r across all conditions (P5 disconfirmed in the simpler form)?

Lightweight enough to keep within the existing `RUNTIME_BUDGET_SECONDS = 3180s` budget if scoped only to the new r values; re-anchor the gate if the full grid is re-run. Deliverable: an updated interpretation section addressing P5 specifically, with a figure showing the full r-curve.

## [t005] Gaussian effect-size variant of H01 simulator
- priority: P3
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-04-24

The current H01 simulator emits binary Bernoulli signals — H01's recall finding is bounded to that abstraction. The handoff note (`meta/doc/plans/2026-04-24-h01-engine-handoff.md`) flagged "Beta-Bernoulli artifact" as a candidate alternative explanation that the Bernoulli sweep cannot rule out. Build a Gaussian-effect-size variant: signals drawn from `Normal(mu, sigma)` where `mu = mu_pos` for truth=1 and `mu_neg` for truth=0; conjugate posterior is normal-normal with running mean and variance; recall analog uses a posterior-mean threshold; calibration analog is MSE between posterior mean and truth-conditional effect size.

Tests whether the H01 finding generalises beyond binary signals. If it does, D-003's continuous-belief commitment has stronger empirical footing. If not, H01 is bounded to the Beta-Bernoulli regime and the design principle needs re-examination. Likely a substantial new package alongside `h01_simulator/` (or a parallel module within it) with its own sweep, notebook, and interpretation. Plan before implementation.

## [t008] Validator: warn on inline-dict synthesized_from items
- priority: P3
- status: proposed
- aspects: [software-development]
- created: 2026-04-25

Per the 2026-04-25 synthesis-shape investigation Q2, the canonical form for `synthesized_from:` items in `type: synthesis` + `report_kind: synthesis-rollup` files is **block-list** (one field per line):

```yaml
synthesized_from:
  - hypothesis: "hypothesis:<slug>"
    file: "doc/reports/synthesis/<slug>.md"
    sha: "<SHA>"
```

The inline-dict form (`synthesized_from: [{hypothesis: "...", file: "...", sha: "..."}]`) is deprecated. Currently `meta/validate.sh` § 11a only checks for the presence of the `synthesized_from:` field, not item shape.

Extend the validator (both `meta/validate.sh` and `scripts/validate.sh` per the lockstep convention) to warn (not error) when `synthesized_from:` items are inline-dict shape on a `report_kind: synthesis-rollup` file. Use the warn severity (matches surrounding validator conventions per the master rollout plan).

Add a regression test in `science/tests/test_validate_script.py` covering the inline-dict warn case + the block-list silent case + the absent-field skip case.

Surfaced by: `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` Q2 resolution.

## [t009] Entity-rename / declarative-migrations primitive (Q5 follow-up)
- priority: P2
- status: proposed
- aspects: [software-development]
- created: 2026-04-26

Land the long-term ideal articulated as Q5 in the 2026-04-25 synthesis-shape investigation: entity-id references become first-class citizens of the knowledge graph, and migrations become **declarative** rather than imperative. Concrete deliverables to scope when this lands:

- `science entity rename <old-id> <new-id>` as a primitive that rewrites every reference graph-wide (not regex-driven; uses the actual reference index).
- A declarative migration shape: "transition entity instances of kind K from shape S₀ to shape S₁" — a registry-like description that the tool can plan, dry-run, and apply, rather than ad-hoc Python scripts.
- Composes WITH the managed-artifact system (per `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md` — to be written): managed-artifact version bumps that need entity-shape changes ride into the same declarative migration channel. The managed-artifact system is one delivery surface; entity-rename / declarative migrations are the other.

**Why this is its own track:** The 2026-04-25 conventions audit's Bucket C (P1 #1, #3, #5, #8 — design-pass items) defines the abstract entity data model that this primitive needs. Bucket C must land first, or at least its load-bearing pieces (the multi-axis profile shape and the sanctioned entity-kind extension surface). Until that, entity-rename has no stable referent shape to operate over.

**Sequencing recommendation:**
1. Bucket C design session (P1 #1/#3/#5/#8 — separate cycle, with user).
2. Implement Bucket C decisions.
3. Implement managed-artifact long-term system (per the 2026-04-26 design spec).
4. Then this task: entity-rename primitive + declarative migration registry.

Phase 2 of `scripts/migrate_downstream_conventions.py` (shape-driven rules, landed `fe8d974`) is the first concrete step toward this; it should be cited as the prior art when planning the declarative migration shape.

Surfaced by: 2026-04-26 brainstorm of the managed-artifact long-term design (Q5 referenced from `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` and `docs/plans/2026-04-25-rollout-and-migration-handoff.md` decision #6).

## [t012] Pre-registration semantics recast (epistemic vs operational targets)
- priority: P2
- status: proposed
- aspects: [skills, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-03

Update `science:pre-register` and `science:interpret-results` skills (and the project-level docs `docs/claim-and-evidence-model.md`, `docs/proposition-and-evidence-model.md`) to reflect the recast articulated in `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` § Part 4: a pre-registration over an *operational* claim ("we will run pipeline P with params X before unblinding") stays binary and gating; a pre-reg over an *epistemic* claim ("if we observe Y we will treat hypothesis H as supported") becomes evidence input to H's standing rather than a verdict on H.

Zero schema change to pre-reg entities. Behavioral changes:
- `science:pre-register` prompts the user to identify whether the target is operational or epistemic, and frames the commitment language accordingly.
- `science:interpret-results` reads the pre-reg's commitment, evaluates the result against it, and emits a `bears_on` edge into the epistemic target — weighted by pre-reg commitment, not as a binary verdict.
- Skill prose explicitly drops "kill switch" framing for null results against epistemic targets.

Independent of `[t010]`/`[t011]`: can land before, during, or after the code changes since it touches only skills and prose. Do *not* land before downstream projects (myeloma, natural-systems) have a chance to surface objections — the recast changes how their existing pre-regs are interpreted.

Surfaced by: 2026-05-03 design discussion on continuous-belief flow.

## [t014] Epistemic freshness: content-hash upstream change detection
- priority: P3
- status: proposed
- aspects: [software-development, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-05

Phase 1 freshness uses frontmatter `updated` / `created` dates as the upstream change marker. `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` explicitly deferred content-hash-based change detection to a later phase. Add a graph/materialization path that can detect upstream content changes even when authors forget to bump `updated:`, without replacing the current date-based convention prematurely.

Scope to design first: which authored fields participate in the hash, whether hashes live in the graph only or in a sidecar manifest, how to avoid noise from formatting-only edits, and how this interacts with existing managed-artifact hash utilities.

Surfaced by: EDG design § Decisions, item 5.

## [t015] Cross-project freshness propagation
- priority: P3
- status: proposed
- aspects: [software-development, federation, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-05

Extend epistemic freshness beyond a single project: a paper, dataset, workflow-run, observation, proposition, or other epistemic upstream added in a parent/child/sibling project should be able to mark downstream hypotheses, questions, propositions, inquiries, and interpretations as `needs-review` across project boundaries.

This is distinct from current federation graph assembly/status. The missing design pieces are cross-project entity address syntax, resolver source of truth (live child sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics when a downstream project is not locally available.

Surfaced by: EDG design trajectory item 2.

## [t016] Derived qualitative standing for epistemic entities
- priority: P3
- status: deferred
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
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
- related: [question:01-evidence-payload-schema, question:02-causal-synthesis-guardrails, hypothesis:h01-stochastic-revisiting, topic:bayesian-methods-continuous-belief]
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
Sequencing: `[t022]` first; aspect-extension tasks then drop to P2 awaiting the contract.
`[t025]` is the canonical H03 reason-code registry — aspect tasks declare codes locally and mirror them there with batch provenance.
Lit follow-up tasks (`[t028]`, `[t036]`, `[t039]`, `[t041]`) are P3 so they do not compete with the schema work.

Surfaced by: `doc/background/papers/synthesis-2026-05-05-bayesian-evidence-synthesis.md`.

## [t022] Design minimum quantitative evidence payload schema
- priority: P1
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t021, question:01-evidence-payload-schema, hypothesis:h01-stochastic-revisiting, topic:bayesian-methods-continuous-belief]
- group: evidence-payload-schema
- created: 2026-05-05

Design the **core** evidence payload schema and the **extension contract** that aspect-specific schemas (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) must conform to.

This task is the unblocker for the rest of the Evidence Payload Schema group.
The previous version of this task accumulated ~50 fields across Batches 1-6 and was no longer "minimum".
Reframing: the core is the small, mandatory part every payload carries; aspect extensions are typed payload sections that load only when the relevant artifact type applies.

Required deliverables:

1. **Core payload schema (small).** The fields every evidence/synthesis payload must declare regardless of type. Candidates from Batches 1-2: source, proposition, comparison target / hypothesis set, evidence type, validation role, identifiability status, source reliability ref, source-dependence refs, claim presence / omission state, missingness class, pipeline provenance, source population, target population, transport assumptions, and an aggregation operator. Resist adding fields that only apply to one artifact family.

2. **Extension contract.** A typed-payload-section mechanism so each aspect task can declare its own fields without expanding the core. Specify: how an extension declares its `artifact_type`, how validation rules dispatch to the right extension, and how attention/H03 reason codes inherit across core + extension.

3. **Aspect-extension assignment rule.** A decision rule for which fields belong in core vs in an extension. Use the Batch 3-6 schema-update lists as test cases — most should land in extensions, not core.

4. **Migration notes** for existing support/dispute evidence edges to the new core layout.

5. **Worked examples** from Batches 1-6 showing one core payload + one extension load per batch.

Aspect-extension design tasks should not begin formalizing fields until the core + extension contract is drafted.
Coordinate with `[t023]` (synthesis node types), `[t024]` (heterogeneity/bias mechanisms), `[t025]` (reason-code registry), and `[t026]` (causal guardrails); these define dimensions that may live in core or in shared extensions.

## [t023] Design typed synthesis nodes
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t021, question:01-evidence-payload-schema, topic:bayesian-methods-continuous-belief]
- group: evidence-payload-schema
- created: 2026-05-05

Design first-class synthesis node types so Science does not collapse incompatible aggregation operations into one belief update.
At minimum distinguish:
- effect-size pooling;
- hypothesis-support synthesis;
- causal synthesis;
- diagnostic-test synthesis;
- model-comparison synthesis;
- Bayesian model-averaged synthesis.
- truth-discovery synthesis;
- data-cleaning / repair synthesis;
- multi-view data-integration synthesis;
- graph-estimation versus debiased edge-inference synthesis.
- LLM-prior / constraint synthesis;
- causal-discovery-run synthesis;
- mechanistic-network synthesis;
- mediation synthesis;
- Mendelian-randomization graph synthesis;
- graph-diagnostic synthesis.
- graph-estimate synthesis;
- graph-posterior synthesis;
- integrative-clustering synthesis;
- feature-selection synthesis;
- module-discovery synthesis;
- predictive-integration synthesis.

For each synthesis type, specify required inputs, output fields, provenance, graph edges, and validation checks.
Use Batch 1 as motivating cases: BES/PBF, RoBMA/BMA, diagnostic-test accuracy, posterior-sample evidence estimation, and causal meta-analysis.
Use Batch 2 as motivating cases: truth discovery, MCDA, Bayesian ODE data integration, JMMLE, heterogeneous external-data regression, disease-model calibration, and Bayesian data cleaning.
Use Batch 3 as motivating cases: causal inference roadmaps, causal data integration, hidden-variable discovery, self-compatibility diagnostics, LLM causal priors, mediation analysis, and Bayesian Mendelian-randomization graph models.
Use Batch 4 as motivating cases: mixed graphical model integration, joint sparse graph inference, Bayesian survival integration, common/unique network decomposition, graph posterior inference, scalable Bayesian GGM structure learning, integrative clustering, and feature selection.

## [t024] Represent heterogeneity and bias as evidence-generation mechanisms
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t021, question:01-evidence-payload-schema, hypothesis:h01-stochastic-revisiting]
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
- related: [task:t021, hypothesis:h01-stochastic-revisiting, question:01-evidence-payload-schema]
- group: evidence-payload-schema
- created: 2026-05-05

Extend H01-style revisiting beyond posterior/support magnitude by adding reason-coded uncertainty features.
Candidate reasons from Batch 1: `underpowered-evidence`, `high-heterogeneity`, `publication-bias-risk`, `model-uncertainty`, `prior-sensitive`, `imperfect-label`, `boundary-case`, `complex-hypothesis-penalty`, and `estimand-mismatch`.
Candidate reasons from Batch 2: `source-unreliable`, `source-dependent`, `omission-ambiguous`, `missing-view`, `source-target-mismatch`, `prior-resolved-nonidentifiability`, `cleaning-unvalidated`, `repair-uncertain`, `shared-structure-assumption`, and `debiased-inference-missing`.
Candidate reasons from Batch 3: `causal-sufficiency-assumption`, `latent-variable-risk`, `llm-prior-unvalidated`, `prior-data-disagreement`, `graph-object-ambiguous`, `self-incompatible`, `identification-missing`, `weak-prior-only`, `instrument-assumption-risk`, and `mediation-estimand-ambiguous`.
Candidate reasons from Batch 4: `graph-posterior-uncertain`, `edge-inclusion-unstable`, `shared-structure-dependent`, `view-scope-mismatch`, `variational-approximation-risk`, `pseudo-likelihood-risk`, `clustering-unvalidated`, `selected-feature-unstable`, and `exploratory-integration-only`.
Candidate reasons from Batch 5: `agent-source-unvalidated`, `tool-chain-unvalidated`, `safety-check-missing`, `context-retrieval-uncertain`, `information-absence-undetected`, `kg-view-derived`, `graph-version-stale`, `agent-bias-risk`, and `attention-not-evidence`.
Candidate reasons from Batch 6: `robustness-target-ambiguous`, `modifier-domain-missing`, `tolerance-unspecified`, `replication-metric-mismatch`, `reproducibility-dimension-ambiguous`, `checklist-incomplete`, `analysis-plan-missing`, `deviation-unreported`, `code-or-data-unavailable`, and `null-results-omitted`.

Design how these reasons are recorded on evidence/synthesis artifacts and how `science graph attention-sample` could incorporate them without using LLM-estimated probabilities.
This should follow `[t022]` enough to avoid inventing a parallel schema.
Aspect-extension design tasks (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) each declare their own H03 reason codes; this task is the canonical registry — when those tasks formalize a code, mirror it here with batch provenance.

## [t026] Causal synthesis guardrails
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t021, question:02-causal-synthesis-guardrails, question:01-evidence-payload-schema]
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

## [t028] Follow-up literature on Bayesian synthesis, causal meta-analysis, and anytime-valid evidence
- priority: P3
- status: proposed
- aspects: [research, hypothesis-testing, causal-modeling]
- related: [question:01-evidence-payload-schema, question:02-causal-synthesis-guardrails, topic:bayesian-methods-continuous-belief]
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
- related: [question:01-evidence-payload-schema]
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

## [t030] Audit authoring cost of the proposed evidence-payload schema
- priority: P1
- status: proposed
- parent: task:t021
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t022, question:04-authoring-cost-audit, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration]
- group: evidence-payload-schema
- created: 2026-05-05

Sample 10-20 existing paper summaries from this commit and attempt to extract the candidate t022 fields against a defined rubric.
Record per-field success rate, ambiguity rate, inferred-vs-stated status, and rough effort cost.
Run a second extraction pass with an LLM agent and score it against the manual pass.

Deliverables:
- a sampling plan and field-extraction rubric in `meta/doc/plans/`;
- a per-field extractability table;
- a short note feeding back into t022 with field-pruning recommendations (core / typed-extension / drop);
- a note on agent-vs-manual extraction agreement that informs `[t033]`.

Blocks: cannot start until t022 has a candidate field set.

## [t031] Source-dependence detection design
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [task:t024, task:t025, task:t033, task:t035, task:t037, task:t038, question:03-source-and-pipeline-provenance, question:05-source-dependence-detection, question:07-llm-agents-as-fallible-sources, question:11-graph-valued-synthesis-artifacts, question:12-agent-tool-kg-operations, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
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
- related: [task:t028, question:06-sequential-anytime-valid-evidence, hypothesis:h05-sequential-evidence-improves-attention, hypothesis:h01-stochastic-revisiting, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: sequential-evidence
- created: 2026-05-05

Resolve t028's anytime-valid reading lead into either a topic note + simulator extension or a deferred-with-reason record.

Steps:
- ingest the e-value / test-martingale / confidence-sequence references queued in `[t028]`;
- write a topic note `doc/background/topics/sequential-evidence.md` linking these methods to H01 / H03 attention and H02 payload state;
- audit current and likely-future project graph state for the realized prevalence of optional stopping and unbounded revisiting;
- propose a sequential-evidence extension to the H01 simulator: propositions receive evidence over time, attention policies compare fixed-N posterior, BMA-style, and anytime-valid evidence levels;
- decide whether H05 graduates to an active simulation track or stays speculative pending stronger upstream evidence.

## [t033] Model LLM agents as fallible evidence sources and graph-governed operators
- priority: P2
- status: proposed
- aspects: [software-development, framework-design, research]
- related: [task:t022, task:t024, task:t031, task:t037, task:t038, question:07-llm-agents-as-fallible-sources, question:05-source-dependence-detection, question:12-agent-tool-kg-operations, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
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

## [t034] Design causal graph construction pipeline artifacts
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t022, task:t023, task:t025, task:t026, question:10-causal-graph-construction-pipeline, question:02-causal-synthesis-guardrails, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting, hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening]
- group: evidence-payload-schema
- created: 2026-05-06

Design how Science represents causal graph construction as a staged evidence pipeline rather than as direct causal edge creation.

Candidate artifacts:
- candidate variable / measurement proposal;
- source annotation and external-variable extraction;
- background knowledge or prior-knowledge bundle;
- LLM-generated weak prior or constraint set;
- causal-discovery run;
- learned graph object or graph posterior;
- graph diagnostic result;
- identified estimand;
- mediation or MR-specific result;
- causal effect estimate.

Deliverables:
- a graph-object taxonomy covering at least DAG, CPDAG, PAG, ADMG, equivalence-class feature, candidate graph, and graph posterior;
- an epistemic-role taxonomy covering `assumed_background_edge`, `llm_prior_edge`, `llm_ancestral_constraint`, `data_discovered_adjacency`, `equivalence_class_feature`, `latent_variable_hypothesis`, `identified_causal_effect`, `mediation_path`, and `mechanistic_hypothesis`;
- a payload-versus-first-class-entity decision rule for each artifact type;
- validation rules for when each artifact may strengthen, annotate, or merely prioritize a causal proposition;
- alignment notes with `[t022]`, `[t023]`, `[t025]`, and `[t026]`.

Start from Batch 3 synthesis: `doc/background/papers/synthesis-2026-05-06-causal-graph-construction.md`.

## [t035] Design graph-valued synthesis artifact schema
- priority: P2
- status: proposed
- parent: task:t021
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t022, task:t023, task:t024, task:t025, task:t026, task:t034, question:11-graph-valued-synthesis-artifacts, question:10-causal-graph-construction-pipeline, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting, hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening]
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

Start from Batch 4 synthesis: `doc/background/papers/synthesis-2026-05-06-graphical-models-multiview-integration.md`.

## [t036] Follow-up literature on graph-valued and multiview synthesis artifacts
- priority: P3
- status: proposed
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t035, question:11-graph-valued-synthesis-artifacts, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting, hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening]
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

## [t037] Design agent/tool operations schema
- priority: P2
- status: proposed
- aspects: [software-development, framework-design, research]
- related: [task:t029, task:t033, question:07-llm-agents-as-fallible-sources, question:12-agent-tool-kg-operations, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
- group: agent-source-modeling
- created: 2026-05-06

Design a Science operations schema for agents, tools, commands, skills, and tool chains.

Candidate entities:
- `agent`;
- `agent_role`;
- `tool`;
- `skill`;
- `command`;
- `tool_chain`;
- `execution_trace`;
- `safety_policy`;
- `validation_protocol`;
- `operation_record`.

Deliverables:
- a tool/skill graph schema with capability descriptions, expected inputs/outputs, dependency edges, safety constraints, and validation commands;
- an operation-record schema covering `agent_role`, `agent_model_version`, `prompt_or_workflow_ref`, `tool_chain_ref`, `tool_io_contract`, `safety_policy_ref`, `execution_trace_ref`, `validation_status`, `abstention_reason`, and `agent_evaluation_protocol`;
- mapping of operation records to evidence payloads, paper summaries, syntheses, graph updates, and task edits;
- H03 reason-code mapping for `agent-source-unvalidated`, `tool-chain-unvalidated`, `safety-check-missing`, `context-retrieval-uncertain`, `information-absence-undetected`, and `agent-bias-risk`;
- alignment with `[t033]` so LLM agents are represented as both fallible sources and graph-governed operators.

Start from Batch 5 synthesis: `doc/background/papers/synthesis-2026-05-06-scientific-agents-knowledge-graphs.md`.

## [t038] Design graph evolution and KG view provenance
- priority: P2
- status: proposed
- aspects: [software-development, framework-design, causal-modeling, hypothesis-testing]
- related: [task:t021, task:t035, task:t037, question:12-agent-tool-kg-operations, question:03-source-and-pipeline-provenance, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
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

Start from Batch 5 synthesis: `doc/background/papers/synthesis-2026-05-06-scientific-agents-knowledge-graphs.md`.

## [t039] Follow-up literature on scientific agents, tool provenance, and KG operations
- priority: P3
- status: proposed
- aspects: [research, software-development, framework-design]
- related: [task:t037, task:t038, question:12-agent-tool-kg-operations, question:07-llm-agents-as-fallible-sources, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
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
- priority: P2
- status: proposed
- aspects: [software-development, framework-design, hypothesis-testing, research]
- related: [task:t021, task:t022, task:t025, task:t030, question:13-robustness-reproducibility-evaluation, question:01-evidence-payload-schema, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting, topic:analytic-flexibility-and-replication]
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

Start from Batch 6 synthesis: `doc/background/papers/synthesis-2026-05-06-robustness-reproducibility-evaluation.md`.

## [t041] Follow-up literature on replication metrics, robustness, and reproducibility standards
- priority: P3
- status: proposed
- aspects: [research, framework-design, hypothesis-testing]
- related: [task:t040, question:13-robustness-reproducibility-evaluation, topic:analytic-flexibility-and-replication, hypothesis:h02-rich-evidence-payloads-improve-graph-calibration, hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting]
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

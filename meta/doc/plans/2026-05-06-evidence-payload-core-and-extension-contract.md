# Evidence Payload — Core Schema and Extension Contract (t022 draft v2.3)

> **Status:** Updated for v2.3 (2026-05-06). v2.3 patches from the `[t034]` v1.1 pilot extraction (`meta/doc/plans/2026-05-06-t034-pilot-extraction.md`): added `partial_fields` optional core field with associated authoring convention for partially-enumerated multi-element list fields (P-pilot-6); added complementary `proposition_refs` authoring rule for the intertwined-vs-independent disambiguation (P-pilot-5); added `uncertainty_summary` authoring guidance to leave the field empty rather than synthesize prose for purely-qualitative content (P-pilot-9). Field count 17 → 18 (12 required, 6 optional). Structural decisions unchanged through v2.3.
>
> v2.2 (prior) patches from the full `[t030]` audit (`meta/doc/plans/historical/2026-05-06-t030-full-audit-results.md`): removed `target_artifact_ref` from core (applicability 0.167 — moved to evaluation/audit/operation extensions); extended `artifact_type` enum with `methods-paper` / `framework-paper` / `benchmark-or-dataset-paper`; extended `comparison_target` enum with `method-set`; extended `support_direction` enum with `framework-proposal`; loosened `uncertainty_summary` from required to optional with allowed qualitative form; added `proposition_refs` cardinality rule (one per finding-cluster). Field count 18 → 17 (12 required, 5 optional). Structural decisions (core/extension split, multi-extension dispatch, reason-code inheritance) remain unchanged through v2.2.
>
> v2.1 (prior) patches from the narrow `[t030]` audit (`meta/doc/plans/historical/2026-05-06-t030-narrow-authoring-cost-audit.md`): added `claim_source_ref` core field for paper-extracted claims, added explicit "What does NOT live in t022" section, added validation_status pitfall note, generic evidence-quality reason codes mirrored to `[t025]`.

**Goal:** Produce the **core** evidence payload schema and the **extension contract** that aspect-specific schemas (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) must conform to. Without a layered split, every batch silently widened the "minimum" payload (~50 fields after Batch 6) and the aspect tasks collapse into ad-hoc accretion.

**Related tasks:** `[t021]` (parent), `[t023]` (synthesis nodes), `[t024]` (heterogeneity/bias mechanisms), `[t025]` (reason-code registry), `[t026]` (causal guardrails), `[t030]` (authoring-cost audit), `[t034]`/`[t035]`/`[t037]`/`[t038]`/`[t040]` (extensions).

---

## Findings from the worked-example exercise

Six paper summaries were drafted-against to ground the schema bottom-up, one per batch: Gronau2021 (Batch 1, BMA meta-analysis), Zhao2012 (Batch 2, truth discovery), Petersen2014 (Batch 3, causal-inference roadmap), Mohammadi2025-style joint graphical model (Batch 4, graph posterior), Ding2025 (Batch 5, SciToolAgent operation), Banzi2026 (Batch 6, OSIRIS reproducibility checklist).

**Finding 1 — Papers are not payloads.** None of the source papers is itself an evidence payload about a specific scientific proposition. Some are method papers, some are roadmaps, some define checklists or tools. The schema must therefore distinguish **source artifacts** (papers, datasets, agents, tools), **evidence payloads** (claims attached to propositions), **synthesis artifacts** (aggregating multiple evidence into one node), and **evaluation artifacts** (audits/replications/robustness tests evaluating other artifacts). Only the latter three carry payloads in the t022 sense.

**Finding 2 — Method-ref and input-ref are different things.** The first draft conflated them under `source_ref`, then used method-defining papers (Gronau, Banzi) where it should have used the inputs (the dataset, the audited study). Splitting these is unavoidable; see core schema below.

**Finding 3 — Cardinality differs across families.** A Bayesian-evidence-synthesis payload (Gronau-style) attaches *one* numeric posterior to *one* proposition. A causal-discovery payload (Petersen-style) produces a *graph object* whose edges each carry their own epistemic role and identification status — many propositions per payload. A reproducibility audit (Banzi-style) attaches a checklist *to another artifact*, not to a proposition. An agent-tool-operation record (Ding-style) attaches to *no* proposition — it records that an operation happened. Core fields must accommodate all four cardinalities.

**Finding 4 — `validation_role` (permission) and `validation_status` (state) are orthogonal.** v1 conflated them. A payload can have `validation_role: strengthen-belief` (it is *allowed* to update belief) but `validation_status: pending` (its content has not yet been validated). Both belong in core; both are mandatory.

**Finding 5 — A payload may load multiple extensions.** A Bayesian causal-discovery run loads *both* the causal-graph extension (for graph object semantics) and the statistical extension (for posterior summaries over edges). v1 spoke of "imports"; v2 makes the multi-extension list explicit on the payload, with a registry that knows which extensions co-require which others.

---

## Proposed core schema

Every evidence/synthesis/evaluation/operation payload carries these fields. **Required** unless marked `[opt]`.

```yaml
core:
  # Identity
  payload_id: str                    # unique within project
  artifact_type: enum                # primary type; dispatches to the primary extension. v2.2 enum includes synthesis-derived types (bayesian-meta-analysis, truth-discovery-result, causal-discovery-run, graph-posterior-synthesis), operation/evaluation types (agent-tool-operation, reproducibility-checklist-audit), and paper-extracted-claim types (methods-paper, framework-paper, benchmark-or-dataset-paper).
  extensions: [str]                  # all loaded extension names, primary first; validates against registry
  created_at: datetime
  source_commit: str           [opt] # the commit of source content the payload was extracted from

  # Provenance
  input_artifact_refs: [ref]         # derivation inputs (datasets, primary studies, prior payloads, target artifacts of audits); may be empty
  claim_source_ref: ref        [opt] # the artifact this payload's claim was *extracted from* (e.g., a paper for paper-extracted claims). Distinct from inputs and method.
  method_ref: ref              [opt] # canonical method / instrument / tool definition (e.g., paper:Gronau2021, checklist:OSIRIS-32)
  agent_ref: ref               [opt] # the agent (human, LLM, pipeline) that authored the payload
  pipeline_provenance_ref: ref [opt] # the actual run/execution record (extraction run, synthesis run, audit run)

  # Attachment
  proposition_refs: [ref]            # propositions this is evidence about; empty for evaluation/operation artifacts. Cardinality rule: one entry per finding-cluster (don't synthesize a catch-all).
  comparison_target: enum            # null-vs-alternative / hypothesis-set / model-set / method-set / artifact-target / n-a

  # Epistemic semantics
  support_direction: enum            # supports / disputes / qualifies / methodological-input / framework-proposal / quality-record / operation-record
  validation_role: enum              # PERMISSION: strengthen-belief / prioritize-attention / gate-update / quality-record-only / record-only
  validation_status: enum            # STATE: validated / pending / failed / not-applicable / unknown
  uncertainty_summary: str     [opt] # short canonical form OR short qualitative form: "BF10=0.115" / "CPDAG, 12 edges" / "supports method under stated conditions"; detailed numeric uncertainty in extensions

  # Quality flags
  reason_codes: [enum]               # H03 codes from t025; declared on this payload (does not include inherited codes — see inheritance section); may be empty
  abstention_reason: enum      [opt] # if the payload is "we can't say" rather than "we say X"

  # Partial-extraction flag (v2.3)
  partial_fields: [str]        [opt] # field paths in this payload (core or extension) whose multi-element list value is partial (e.g., "extension/mr-graph-model.exposure_set"). Listed here, the field's enumerated values are a subset of the true set. Validators must not treat a listed field's count as authoritative.
```

**Field count: 18** (12 required, 6 optional) after v2.3 added optional `partial_fields`.

**Pitfall — `validation_status` is the payload's state, not the source's.** A common authoring error is to set `validation_status: validated` because the source paper (in `claim_source_ref`) is peer-reviewed. That conflates two things. `validation_status` describes whether *this payload* (its extraction, its content, its application) has been audited; default `pending` for newly-authored payloads. Source-quality signals belong in reason codes (e.g., `peer-reviewed-only`, `single-source-evidence`).

**Authoring rule — `proposition_refs` cardinality (two-sided).** When a paper carries multiple distinct findings, author one `proposition_refs` entry per finding-cluster — do not synthesize a catch-all proposition. *Conversely* (added v2.3 from `[t034]` pilot extraction F-pilot-7): when a paper presents multiple intertwined patterns within a single mechanism story (e.g., Dugourd2021's hypoxia + inflammatory + oncogenic patterns recovered as one ccRCC mechanism cluster), author one proposition, not several. Heuristic: if the patterns *share* the paper's central causal/mechanistic story, one proposition; if they make independent claims that could survive each other failing, separate propositions. The synthesis layer (`[t023]`) re-aggregates if the call turns out wrong.

**Authoring rule — `reason_codes` empty list.** When no reason codes apply, score / store the field as an explicit empty list `[]` (a positive declaration of "no concerns"), not as missing. Validators should treat absent `reason_codes` as a payload error.

**Authoring rule — `uncertainty_summary` for purely-qualitative content (added v2.3).** When the paper-summary or pipeline output is purely qualitative and has no canonical short-form rendering, leave `uncertainty_summary` empty rather than synthesizing prose. Synthesized prose tends to over-claim precision (e.g., turning "supports method under stated conditions" into "BF≈moderate"). The field is `[opt]` in v2.2 specifically to permit empty values; consumers expecting a summary fall back to extension-level uncertainty fields.

**Authoring rule — `partial_fields` convention (added v2.3).** When a multi-element list field (e.g., `extension/mr-graph-model.exposure_set`, `extension/mediation-analysis.mediator_set`, `extension/mechanistic-hypothesis-bundle.omics_layer_set`) is partially enumerated — the author lists what the source names but cannot enumerate the rest — list the field's full path in `core.partial_fields`. Validators must not treat that field's element count as authoritative; downstream synthesis must treat the listed values as a subset, not the totality. Default behavior: absent from `core.partial_fields` ⇒ the list is complete. This pattern propagates to all aspect extensions; field-level `<field>_complete: bool` flags are *not* added on the extension side — `core.partial_fields` is the single source of truth.

### What does NOT live in t022 (added v2.1)

Some artifact classes are out of scope for the t022 contract entirely. They should not be forced into a payload shape; they belong to sibling artifact classes:

- **Survey / scoping-review papers** that catalog methods, metrics, or definitions without making a single propositional claim (e.g., `paper:Heyard2025`, `paper:Jin2025`). These contribute to method registries / topic notes, not evidence payloads.
- **Conceptual theory papers** that contribute vocabulary or analytic frameworks without empirical claims (e.g., `paper:Freiesleben2023`). They feed *into* downstream evaluation extensions but are not themselves payloads.
- **Method-registry imports** — a paper that defines a tool, a checklist, or a method becomes a method-registry entry; the registry is its own graph layer, not a payload.
- **Taxonomy / vocabulary contributions** — typed terms entering the project's ontology are graph-evolution events, not evidence.

These should be routed through a sibling artifact class (likely owned by `[t038]` graph-evolution, or a dedicated topic-import / method-registry task). The `[t030]` narrow audit confirmed that attempting to author payloads for such papers fails cleanly — that is the correct outcome, not a sign that t022's enums are undersized.

A paper-extracted *claim* (an empirical or methodological assertion lifted from a single paper) **is** in scope, and uses `claim_source_ref` plus a `single-source-evidence` reason code. The line is: claim-bearing → t022; vocabulary-bearing → out of t022.

### What did not make it into core (and why)

These are valid fields, but they do not belong in core:

- `model_family`, `prior`, `bayes_factor`, `posterior_model_probabilities`, `heterogeneity`, `bias_model` — Bayesian-meta-analysis-specific; → `bayesian-meta-analysis` extension.
- `causal_model_ref`, `target_estimand`, `identification_assumptions`, `graph_object_type`, `discovery_algorithm`, `method_assumption_set` — causal-graph-specific; → `causal-graph` extension.
- `checklist_ref`, `lifecycle_stage`, `completeness_score`, `missing_items` — reproducibility-audit-specific; → `reproducibility-checklist-audit` extension.
- `tool_chain_ref`, `prompt_or_workflow_ref`, `safety_policy_ref`, `agent_evaluation_protocol`, `execution_trace_ref` — agent-operation-specific; → `agent-tool-operation` extension.
- `transport_assumptions`, `target_population`, `source_population` — relevant when generalization is in scope; → shared `transportability` extension.
- `source_reliability`, `source_dependence_refs`, `omission_semantics`, `missingness_class` — truth-discovery / source-modeling specific; → `truth-discovery` extension or shared `source-behavior` extension.
- `edge_inclusion_probability`, `cluster_count`, `feature_relevance_posterior`, `graph_artifact_type`, `integration_objective` — graph-valued artifact specific; → `graph-valued-artifact` extension.

---

## Extension contract

An **extension** is a typed payload section keyed by name. The extension registry tracks each extension's:

1. **Name** (string, e.g., `bayesian-meta-analysis`).
2. **Required fields**, **optional fields**, with types.
3. **Co-required extensions** — extensions that must also be loaded when this one is loaded (e.g., `bayesian-causal-discovery` co-requires `causal-graph` and `statistical-uncertainty`).
4. **Validation rules** — conditions that must hold for each `validation_role` permission to be allowed (e.g., `causal-discovery-run` cannot have `validation_role: strengthen-belief` on a causal proposition unless its `identification_status: identified`).
5. **Uncertainty-summary contract** — how the extension's full uncertainty fields are rendered into `core.uncertainty_summary`.
6. **Reason-code contributions** — codes specific to this extension's failure modes; mirrored to `[t025]` with extension provenance.
7. **Reason-code propagation policy** — how codes flow when this extension's payload is referenced by a downstream payload via `input_artifact_refs` (see inheritance section below).
8. **Owning task** — which design task (`[t034]`/`[t035]`/`[t037]`/`[t038]`/`[t040]`) owns the extension.

### Multi-extension payloads

A payload's `core.extensions` lists all extensions present, **primary first**. The payload validates iff:

- `core.artifact_type` matches the primary extension's declared type;
- the registry's transitive co-required extensions are all listed (import-closure validation);
- each listed extension's required fields are present in the corresponding YAML section;
- the strictest-applicable validation rule across all loaded extensions permits the declared `validation_role`.

This replaces v1's "imports" language. A multi-extension payload looks like:

```yaml
core:
  artifact_type: bayesian-causal-discovery
  extensions: [bayesian-causal-discovery, causal-graph, statistical-uncertainty]
  ...
extension/bayesian-causal-discovery: { ... }
extension/causal-graph: { ... }
extension/statistical-uncertainty: { ... }
```

### Field-assignment rule (core vs extension vs shared extension)

A field belongs in **core** iff: (a) every payload must declare it for the graph to function (proposition refs, validation role, support direction, validation status), or (b) it answers a graph-level question independent of artifact family (when was it created, what produced it, what's the one-line summary).

A field belongs in a **primary extension** iff: it is meaningful only for one artifact family.

A field belongs in a **shared extension** iff: it spans more than one but not all families (e.g., `transportability`, `source-behavior`, `statistical-uncertainty`).

---

## Reason-code inheritance

The first draft deferred this; it is required by `[t022]`'s mandate. Spec:

### Within a payload (mechanical union)

A payload's **declared** reason codes are `core.reason_codes`. A payload's **effective** reason codes are:

```
effective_codes(p) = p.core.reason_codes
                   ∪ ⋃ over each loaded extension e: e.reason_codes
                   ∪ inherited_codes(p)        # see below
```

Each contribution is tagged with origin (`core` / extension name / inherited from upstream payload). Origin is preserved so consumers (e.g., the H01 attention sampler) can filter or weight by where a code came from.

### Across payloads (explicit propagation)

When a payload `q` lists payload `p` in its `input_artifact_refs`, codes can propagate from `p` to `q` according to `p`'s primary extension's **propagation policy**. The policy is one of:

- `propagate-all` — all of `p`'s effective codes flow to `q`'s inherited codes.
- `propagate-blocking` — only codes flagged as `blocking` in the t025 registry (e.g., `identification-missing`, `code-or-data-unavailable`) propagate.
- `propagate-tagged-only` — only codes with explicit `propagate: true` per occurrence flow.
- `no-propagate` — codes do not propagate; the consumer is fully responsible for declaring its own.

The default for new extensions is `propagate-blocking`. Audit/evaluation extensions may override (e.g., `reproducibility-checklist-audit` defaults to `propagate-blocking` so that an unavailable-code finding on an upstream study attaches to a downstream synthesis that uses it).

Inherited codes carry origin chain (`q ← p ← p'`) so consumers can detect cycles and budget propagation depth.

### Effect on validation rules

A payload's **declared** `validation_role` must be permitted under **effective** codes, not declared codes. So if an upstream blocking code (e.g., `identification-missing`) propagates in, a downstream extension's validation rule may downgrade `strengthen-belief` to `prioritize-attention`. The validator surfaces this as a clear diagnostic, not a silent downgrade.

This is what wires t025 to the contract: extensions declare codes, the registry tracks codes' blocking semantics and propagation policy, the validator computes effective codes, validation rules consult effective codes.

---

## Worked examples (Batches 1–6)

### Example 1 — Batch 1, Bayesian model-averaged meta-analysis (Gronau-style)

```yaml
core:
  payload_id: ev-2026-replication-dishonesty-bma
  artifact_type: bayesian-meta-analysis
  extensions: [bayesian-meta-analysis, statistical-uncertainty]
  created_at: 2026-05-06T12:00:00Z
  input_artifact_refs:
    - dataset:dishonesty-19lab-effects
    - study:dishonesty-lab-01
    # ... study refs for each of 19 labs
  method_ref: paper:Gronau2021                      # the BMA primer
  agent_ref: agent:human:khughitt
  pipeline_provenance_ref: synthesis:dishonesty-19lab-bma
  proposition_refs: [prop:ten-commandments-dishonesty-effect-nonzero]
  comparison_target: null-vs-alternative
  support_direction: disputes
  validation_role: strengthen-belief
  validation_status: pending
  uncertainty_summary: "BF10=0.115 (moderate evidence for absence)"
  reason_codes: []

extension/bayesian-meta-analysis:
  model_set: [fixed-null, fixed-alt, re-null, re-alt]
  prior_spec:
    mu_prior: cauchy(0, 1/sqrt(2))
    tau_prior: inv-gamma(1, 0.15)
  posterior_model_probabilities: {fixed-null: 0.61, ...}
  inclusion_bf_effect: 0.115
  inclusion_bf_heterogeneity: 0.189
  effect_estimate: {posterior_mean: 0.02, ci95: [-0.04, 0.08]}
  heterogeneity_estimate: {tau_post_mean: 0.03, ci95: [0.00, 0.11]}

extension/statistical-uncertainty:
  posterior_form: model-averaged
  ci_method: equal-tailed
  prior_sensitivity_checked: true
```

Key points: `method_ref: paper:Gronau2021` (the method definition), `input_artifact_refs:` lists the dataset and per-lab studies (the actual evidence inputs). `validation_status: pending` because no audit has run yet.

### Example 2 — Batch 2, truth-discovery aggregation (Zhao-style)

A truth-discovery run over five extracted-from-papers claims about an effect size, with copying suspected between sources s2 and s4.

```yaml
core:
  payload_id: ev-2026-effect-truth-discovery
  artifact_type: truth-discovery-result
  extensions: [truth-discovery, source-behavior, statistical-uncertainty]
  created_at: 2026-05-06T12:30:00Z
  input_artifact_refs:
    - claim:s1-effect-x
    - claim:s2-effect-x
    - claim:s3-effect-x
    - claim:s4-effect-x
    - claim:s5-effect-x
  method_ref: paper:Zhao2012
  agent_ref: agent:truth-discovery-runner
  pipeline_provenance_ref: pipeline:td-em-v2
  proposition_refs: [prop:effect-x-magnitude]
  comparison_target: hypothesis-set
  support_direction: supports
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "TD posterior: x≈0.31 (5 sources, 2 inferred copying)"
  reason_codes: [source-dependent]

extension/truth-discovery:
  source_reliability_estimates:
    s1: {sensitivity: 0.83, specificity: 0.91}
    s2: {sensitivity: 0.62, specificity: 0.88}
    s3: {sensitivity: 0.78, specificity: 0.85}
    s4: {sensitivity: 0.61, specificity: 0.88}    # near-identical to s2: copying suspected
    s5: {sensitivity: 0.74, specificity: 0.82}
  latent_truth_posterior: {mean: 0.31, sd: 0.07}
  copying_graph_edges: [(s2, s4)]

extension/source-behavior:
  omission_semantics: closed-world-by-source
  missingness_class: mcar-by-claim
  source_dependence_method: pairwise-lift

extension/statistical-uncertainty:
  posterior_form: gaussian-approx
  ci_method: posterior-quantile
```

Key points: `support_direction: supports` but `validation_role: prioritize-attention` (not strengthen-belief) because copying between sources was inferred, materializing as `reason_codes: [source-dependent]`. The combination signals "treat as a lead, not as a confirmed update."

### Example 3 — Batch 3, causal-discovery output (Petersen-roadmap-aware)

```yaml
core:
  payload_id: ev-2026-vaccine-cpdag-pc-run
  artifact_type: causal-discovery-run
  extensions: [causal-discovery-run, causal-graph]
  created_at: 2026-05-06T13:00:00Z
  input_artifact_refs: [dataset:covid-vaccine-obs-cohort]
  method_ref: paper:Petersen2014                          # roadmap reference; algorithm is in extension
  agent_ref: agent:pc-runner
  pipeline_provenance_ref: pipeline:causal-discovery-pc-v3
  proposition_refs: [prop:vaccination-reduces-severe-illness]
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention                   # gated; cannot strengthen until identified
  validation_status: pending
  uncertainty_summary: "CPDAG, 12 edges, vaccination→severe-illness present (undirected)"
  reason_codes: [causal-sufficiency-assumption]   # identification-missing auto-injected per t034 v1.3 (causal-discovery-run extension); v1.4 hard-errors on hand-writing

extension/causal-discovery-run:
  observed_data_link: dataset:covid-vaccine-obs-cohort
  discovery_algorithm: PC
  method_assumption_set: [causal-sufficiency, faithfulness, no-selection-bias]
  diagnostic_score: {self_compatibility: 0.82}

extension/causal-graph:
  causal_model_ref: causal-model:vaccine-effectiveness-v1
  graph_object_type: CPDAG
  edges:
    - {a: vaccination, b: severe-illness, role: data_discovered_adjacency, oriented: false}
  target_estimand: ~                                      # not yet identified
  identification_status: not-attempted
```

Key points: `identification-missing` is a **blocking** code in the t025 registry. It propagates by default. Any downstream synthesis that consumes this payload via `input_artifact_refs` inherits `identification-missing` and cannot use it to strengthen a causal proposition until identification is performed.

### Example 4 — Batch 4, joint graphical model graph posterior

A Bayesian joint graphical model integrating proteomics + transcriptomics views, producing a graph posterior with edge inclusion probabilities.

```yaml
core:
  payload_id: ev-2026-joint-ggm-tcga-brca
  artifact_type: graph-posterior-synthesis
  extensions: [graph-posterior-synthesis, graph-valued-artifact, statistical-uncertainty]
  created_at: 2026-05-06T13:30:00Z
  input_artifact_refs:
    - dataset:tcga-brca-proteomics-v3
    - dataset:tcga-brca-transcriptomics-v3
  method_ref: paper:Mohammadi2025
  agent_ref: agent:bayes-ggm-runner
  pipeline_provenance_ref: pipeline:joint-ggm-mcmc-v1
  proposition_refs: []                                    # graph-valued; edges propose propositions, don't update existing ones
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "graph posterior, 412 nodes, 2 views, 187 high-prob edges (PIP>0.5)"
  reason_codes: [graph-posterior-uncertain, shared-structure-assumption]

extension/graph-posterior-synthesis:
  integration_objective: shared-and-context-unique-edges
  shared_structure_assumption: shared-precision-pattern-with-view-deviations
  borrowing_structure: hierarchical-prior-on-precision
  approximation_class: full-mcmc

extension/graph-valued-artifact:
  graph_artifact_type: posterior-over-undirected-graphs
  edge_inclusion_probabilities_path: results/tcga-brca-pip.parquet
  posterior_summary_role: candidate-edge-prioritization
  view_scope: [proteomics, transcriptomics]

extension/statistical-uncertainty:
  posterior_form: full-posterior
  ci_method: hpd
  approximation_diagnostics: {ess_min: 1283, rhat_max: 1.03}
```

Key points: `proposition_refs: []` because a graph posterior doesn't update existing propositions — it *proposes* candidate edges. `validation_role: prioritize-attention` is the only legal value here.

### Example 5 — Batch 5, agent-tool-operation record (Ding-style SciToolAgent)

A SciToolAgent run that retrieved KG context, called a docking tool, and produced a candidate hypothesis. Operation-record only — not an evidence claim.

```yaml
core:
  payload_id: op-2026-scitool-dock-run-4521
  artifact_type: agent-tool-operation
  extensions: [agent-tool-operation]
  created_at: 2026-05-06T14:00:00Z
  input_artifact_refs:
    - kg-view:protein-target-context-v8
  method_ref: paper:Ding2025
  agent_ref: agent:scitool-runner
  pipeline_provenance_ref: pipeline:scitool-orchestrator-v2
  proposition_refs: []                                    # operation-record; no proposition target
  comparison_target: n-a
  support_direction: operation-record
  validation_role: record-only
  validation_status: validated                            # operation succeeded; result quality is separate
  uncertainty_summary: "SciToolAgent run: KG-retrieve → AutoDock → candidate hypothesis"
  reason_codes: [agent-source-unvalidated]

extension/agent-tool-operation:
  target_artifact_ref: hypothesis:novel-egfr-binding-pocket   # v2.2: target lives in the operation extension
  agent_role: hypothesis-generator
  agent_model_version: scitool-v0.4
  prompt_or_workflow_ref: workflow:hypothesis-from-target-v3
  tool_chain_ref: chain:kg-retrieve-then-dock
  tool_io_contract_ref: contract:autodock-vina-v1
  safety_policy_ref: policy:no-uncontrolled-release
  execution_trace_ref: trace:scitool-run-4521
  abstention_supported: false
```

Key points: `support_direction: operation-record`, `validation_role: record-only`. The operation produces a *target_artifact* (a candidate hypothesis, now in the extension after v2.2's move), but does not itself update belief. A *separate* downstream payload would evaluate the candidate hypothesis and could carry `strengthen-belief` permission.

### Example 6 — Batch 6, OSIRIS reproducibility checklist audit (Banzi-style)

```yaml
core:
  payload_id: ev-2026-dishonesty-osiris-audit
  artifact_type: reproducibility-checklist-audit
  extensions: [reproducibility-checklist-audit]
  created_at: 2026-05-06T14:30:00Z
  input_artifact_refs: [study:dishonesty-19lab]
  method_ref: paper:Banzi2026                             # the checklist definition
  agent_ref: agent:reproducibility-auditor
  pipeline_provenance_ref: ~
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: validated
  uncertainty_summary: "OSIRIS 24/32 items present"
  reason_codes: [code-or-data-unavailable]

extension/reproducibility-checklist-audit:
  target_artifact_ref: study:dishonesty-19lab             # v2.2: audit target lives in the audit extension
  checklist_ref: checklist:OSIRIS-32
  lifecycle_stage: [planning, methods, data-analysis, dissemination]
  items_present: [hypothesis-declared, sap-preregistered, null-results-reported]   # ... abridged
  items_missing: [data-availability, persistent-id-data]
  completeness_score: 0.75
  audit_notes: "Code repo private; data deposit pending."
```

Key points: `code-or-data-unavailable` is **blocking** by default; it propagates back to Example 1's BMA payload via `input_artifact_refs` if the audited study is one of the 19 labs there. Example 1's effective codes would then include it (with origin `inherited from ev-2026-dishonesty-osiris-audit`), and the BMA payload's `validation_role: strengthen-belief` would be reviewed by the validator.

---

## Migration notes

Existing support/dispute evidence edges in the project carry roughly: `source`, `proposition`, `direction`, `weight`, `note`. Migration:

- `source` → if it's a paper or dataset, `core.input_artifact_refs += [source]`. If it's a method-defining paper, `core.method_ref = source`. (Heuristic: papers in `papers/` or referenced by `cite:` are inputs unless the edge note describes "applying method X" — then method.)
- `proposition` → `core.proposition_refs[0]`.
- `direction` ∈ {supports, disputes} → `core.support_direction`.
- `weight` (if present) → `core.uncertainty_summary` as `"weight=N"` plus `extension/legacy-weighted` carrying the raw value.
- `note` → either `core.uncertainty_summary` (if short and canonical) or `extension/legacy-weighted.note`.

Default `validation_role: strengthen-belief`, `validation_status: unknown`, `reason_codes: [legacy-unverified-payload]`. The legacy code is **blocking** so every legacy edge is downgrade-able to attention until re-typed.

The `legacy-weighted` extension exists only to host migrated edges and should be removed once they've all been re-typed.

---

## Open questions

1. **~~Should `proposition_refs: []` and `target_artifact_ref` be a tagged union?~~** **Resolved in v2.2.** `target_artifact_ref` left core (full `[t030]` audit found applicability 0.167 in payload-bearing papers). Each evaluation/audit/operation extension owns its own `target_artifact_ref`-equivalent field. `proposition_refs: []` remains a valid empty list for those extension types. No core-level constraint needed.

2. **~~What is the canonical-form rule for `uncertainty_summary`?~~** **Resolved in v2.2.** Full `[t030]` found ambiguous-rate 0.583 — most paper summaries are prose and forced numeric short-form was the source of ambiguity. v2.2 marks the field `[opt]` and explicitly allows a short qualitative form (e.g., "supports method under stated conditions"). Detailed numeric uncertainty lives in extensions.

3. **Should `agent_ref` become required?** Even human-authored payloads have a human-as-agent record. Forcing it surfaces unowned legacy payloads. Probably required after migration; default to `agent:human:<email>` for manual extraction.

4. **Should a payload list per-extension `reason_codes` separately, or one merged list?** Spec'd as per-extension above (each extension contributes; effective codes = union). Alternative: only `core.reason_codes` is authored, extensions only contribute static "always-on" codes. Decision: authored codes are core; extension-static codes added via the registry. The completed `[t030]` audit preserved this structural split while adding authoring guidance for explicit empty reason-code lists.

5. **Extension-version pinning.** Should `core.extensions` carry version specifiers (`bayesian-meta-analysis@v2`) so that schema evolution doesn't silently invalidate old payloads? Probably yes; version field deferred to a follow-up of this draft.

6. **Cycle handling in propagation.** Two payloads can plausibly cite each other (e.g., a synthesis citing an audit citing the synthesis input). Inheritance must detect cycles and stop. Currently spec'd via the origin-chain field; needs a budgeted-traversal rule.

7. **Where do Batch-5 derived KG views live?** A `kg-view` is neither evidence nor an audit nor an operation strictly — it's a derived sub-artifact. Candidate: a `kg-view` extension with `validation_role: prioritize-attention` only. Owned by `[t038]`.

---

## Next steps

- **Follow up on authoring cost.** `[t030]` completed the first authoring-cost audit and drove the v2.1/v2.2 pruning above. Remaining work is narrower: recover the originally intended full-context-human-vs-blind-LLM comparison, or run a multi-model extraction audit to separate model-family calibration from rubric ambiguity.
- **Draft each aspect extension** (`[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`) using this contract. Each task should publish: name, required + optional fields, co-required extensions, validation rules per `validation_role`, uncertainty-summary contract, reason-code contributions, and propagation policy.
- **Wire `[t025]` to the contract.** Reason codes from extensions land in t025 with batch + extension provenance; t025 also tracks each code's `blocking` flag (used by propagation policy).
- **Pilot the migration plan.** Pick 3–5 legacy support/dispute edges; run them through the migration above; identify mismatches.

Field names and enum values remain subject to implementation feedback from the aspect extensions and real payload authoring. The structural decisions (core/extension split, multi-extension dispatch, reason-code inheritance) are the load-bearing claims of this draft.

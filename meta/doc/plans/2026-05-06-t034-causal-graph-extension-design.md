# Causal Graph Construction — Extension Design (t034 draft v1)

> **Status:** v1.4 draft (2026-05-09). v1.4 patches from the third validator-prototype slice (`meta/doc/plans/2026-05-06-t034-effective-codes-validator-findings.md`): (P1.4-a) add explicit retirement rule for `instrument-assumption-risk` by a co-loaded `mr-analysis` extension whose `pleiotropy_handling != unhandled` AND whose resolved `mr_graph_payload_ref.instrument_validity_assumptions` includes `relevance`; the rule retires `iar` from `effective_codes` at the *current* payload only (local retirement) — the first retirement rule that depends on upstream state, not just local state. This converts the parenthetical at the `causal-effect-estimate.strengthen-belief` rule into a decidable rule and is what makes the T34-6 stage-(b) two-stage MR example actually validate. (P1.4-b) authoring-policy decision: the validator **hard-errors** when authors hand-write any code that is auto-injected per the v1.3 contribution table; there is no migration window. The contract-level reason: an auto-injected code is by definition a falsifiable claim about extension presence, not about payload-specific state, so an author re-writing it adds no information and increases drift risk. Existing payloads carrying hand-written `instrument-assumption-risk`, `mechanism-hypothesis-only`, `prior-network-dependent`, or `identification-missing` (the four auto-injected codes) must be swept before slice-3 prototype folds into `meta/validate.sh`. Reason-code count unchanged. Built against v2.3 of the t022 contract.
>
> **v1.3 (prior, superseded):** v1.3 patches from the second validator-prototype slice (`meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-findings.md`): (P1.3-a) `graph-posterior` payloads must store edges externally (in `graph_artifact_path`) and never enumerate posterior-summary edges in the YAML — closes the `graph-posterior` permitted-edge-roles ambiguity surfaced by slice 1; (P1.3-b) reason-code authoring rules of the form "declared when X" are read biconditionally — over-declaration is as much an error as under-declaration, because reason codes encode falsifiable claims about payload state; (P1.3-c) extension contributions described as "always when extension loaded" are *auto-injected* by the validator's contribution-merging step rather than authored by hand — authors write only the conditional codes. Reason-code count unchanged. Built against v2.3 of the t022 contract.
>
> **v1.2 (prior, superseded):** v1.2 patches from the pilot extraction (`meta/doc/plans/2026-05-06-t034-pilot-extraction.md`) on three Batch-3 papers (Faller2024, Zuber2025, Dugourd2021): (P-pilot-1) added `extracted-from-summary-only` reason code with conditional-required-field rules on `graph-diagnostic.audited_graph_payload_ref`, `mr-graph-model.instrument_set` / `summary_statistic_provenance`, `mechanistic-hypothesis-bundle.prior_knowledge_network_ref` / `coherent_subnetwork_size`; (P-pilot-2) added `pleiotropy_model: unspecified` enum value plus new non-blocking `pleiotropy-unspecified` code (distinct from blocking `pleiotropy-untested` for the explicit `none-assumed` case); (P-pilot-3) `compatibility_notion` shape: enum → list-of-enum; (P-pilot-4) `result` enum extended with `correlative`; (P-pilot-7) `reverse-causation-assumed` rule refined: declared only when direction-constraint is not biologically inherent (new `instrument_validity_assumptions` value `direction-inherent-from-iv-class`); (P-pilot-8) added "Method-paper vs applied-payload routing" doc section. Reason-code count: 7 → 9 (two new: `extracted-from-summary-only`, `pleiotropy-unspecified`).
>
> **v1.1 (prior, superseded):** v1.1 patches addressed review findings: F1 invalid `validation_role: methodological-input` (not a role per v2.2 enum) corrected; F2 `mechanistic` graph-object-type dropped in favor of `candidate-graph` + `epistemic_role: mechanistic_hypothesis`; F3 `causal-sufficiency-assumption` removed from causal-discovery-run propagation list (non-blocking, doesn't propagate under `propagate-blocking`); F4 MR lifecycle made explicit: two stages — graph-construction (`mr-graph-model` primary) and effect-estimate (`causal-effect-estimate` + new `mr-analysis` extension); F5 identified-edge promotion carrier clarified — promotion is recorded by the existence of a `causal-identification` payload referencing (graph, edge), not by edge-role rewrite; F6 graph-object/edge-role mismatches promoted from non-blocking reason code to validation error; F7 reason-code count fixed.
>
> **v1 (prior, superseded):** Designs the `[t034]` aspect extension(s) against the v2.2 evidence-payload contract at `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`. Drafted bottom-up from the seven Batch 3 paper-summary specifics most load-bearing for extension design.
>
> **Scope:** This task owns the *causal* aspect of the schema — how Science records causal graph construction as a staged pipeline rather than direct edge writing. Sister tasks `[t035]` (graph-valued / multiview), `[t037]` (agent/tool ops), `[t038]` (graph-evolution / KG views), `[t040]` (robustness/reproducibility) own neighbouring concerns and are referenced where they would compose.
>
> **Goal:** Specify the extension set, graph-object taxonomy, edge-role taxonomy, payload-vs-entity carve-up, validation rules, reason-code contributions, and worked examples sufficient for an audit-style review.

**Related tasks:** `[t021]` (parent), `[t022]` (core contract — v2.2), `[t023]` (synthesis nodes), `[t025]` (reason-code registry), `[t026]` (causal guardrails — co-owns H04 with this), `[t030]` (audit results inform field choices), `[t033]`/`[t037]` (LLM-prior agent/operator semantics).

**Source:** `doc/background/papers/synthesis-2026-05-06-causal-graph-construction.md` plus per-paper grounding from Petersen2014, Faller2024, Ban2023, Wan2025, Jiralerspong2024, Liu2024HiddenWorld, Yang2025, Zuber2025, Dong2023, Dugourd2021.

---

## Findings from the worked-example exercise

Drafted-against per-paper specifics rather than the synthesis high-level themes. Five findings drive the extension carve-up below.

**Finding 1 — A "causal edge" is at least nine different evidence types.** Per Batch 3 synthesis and confirmed by the per-paper survey: `assumed_background_edge`, `llm_prior_edge`, `llm_ancestral_constraint`, `data_discovered_adjacency`, `equivalence_class_feature`, `latent_variable_hypothesis`, `identified_causal_effect`, `mediation_path`, `mechanistic_hypothesis`. These are not interchangeable. The schema must carry edge-role typing on the graph object itself, not just on the producing payload.

**Finding 2 — Petersen's seven-step roadmap aligns roughly with payload boundaries, not field boundaries.** Causal model, observed-data link, counterfactual target, identification assumptions, statistical estimand, estimator, interpretation. Within one payload, the first two are *inputs* (refs); the next two are the *content* of an identification artifact; the next two are the content of an estimation artifact; the last is the proposition update. So the pipeline factors into at least three downstream payloads (graph object → identification → effect estimate), not one mega-record.

**Finding 3 — LLM-elicited priors are operator-side artifacts, not pure causal-graph artifacts.** Ban2023, Wan2025, Jiralerspong2024, Liu2024HiddenWorld all argue LLM outputs are fallible domain proxies whose evidential weight depends on prompt, model version, retrieval context, and role (direct inference / prior constraint / variable proposal / refinement). This duplicates fields `[t037]` will own. Resolution: this task defines `causal-prior-bundle` carrying the *causal-typed* aspects (constraint type, prior strength, soft-vs-hard, role); operator provenance (model id, prompt hash, tool chain) lives in `[t037]`'s `agent-tool-operation` extension co-loaded via `extensions:`.

**Finding 4 — Self-compatibility is a quality record, not evidence.** Faller2024 explicitly says compatibility is *necessary* but not *sufficient* for correctness. Passing checks doesn't certify; failing flags assumption violation. Validation rule must reject `validation_role: strengthen-belief` on a `graph-diagnostic` payload regardless of score; the maximum permitted role is `quality-record-only`.

**Finding 5 — Mediation is an estimation specialization; MR is two-stage.** Yang2025's NIE/NDE rides on top of an identified causal-effect estimate and is best modelled as an additive extension co-requiring `causal-effect-estimate`. Zuber2025's MrDAG, by contrast, has two distinct stages: (a) an MR-specific *graph posterior* over exposure-outcome relations using genetic instruments (graph construction; produces no effect estimate on its own); (b) an MR-specific *effect estimate* (IVW / Egger / weighted-median, etc.) for individual exposure-outcome edges identified in stage (a). The schema must distinguish these: stage (a) is its own primary type (`mr-graph-model`, parallel to `causal-discovery-run`); stage (b) is an additive extension `mr-analysis` co-loaded onto a `causal-effect-estimate` payload. Conflating them obscures the lifecycle and makes validation rules incoherent.

These five findings together motivate the carve-up below: ten extensions, of which six are stage-specific and four are method-family specializations (mediation, MR stage (a), MR stage (b), and mechanistic-hypothesis-bundle).

---

## Pipeline → extension mapping

Petersen-style stages, mapped to artifact types and extensions:

| Stage | Artifact (`core.artifact_type`) | Primary extension | Co-required extensions |
|---|---|---|---|
| Variable proposal / annotation | (first-class entities, not payloads) | — | — |
| External-variable extraction | (first-class entities — `dataset`, `variable`) | — | — |
| Prior-knowledge / LLM-prior assembly | `causal-prior-bundle` | `causal-prior-bundle` | optional `agent-tool-operation` (t037) for LLM origin |
| Causal-discovery run | `causal-discovery-run` | `causal-discovery-run` | `causal-graph` |
| Learned graph object | (no separate artifact — content of `causal-graph` extension on the run payload, or `mechanistic-hypothesis-bundle` for non-identified output) | — | — |
| Graph diagnostic | `graph-diagnostic` | `graph-diagnostic` | references the audited `causal-graph` payload via `input_artifact_refs` |
| Identification | `causal-identification` | `causal-identification` | references upstream `causal-graph` payload |
| Effect estimation | `causal-effect-estimate` | `causal-effect-estimate` | `statistical-uncertainty`; references upstream `causal-identification` |
| Mediation specialisation | `causal-effect-estimate` (with mediation extension co-loaded) | `causal-effect-estimate` | `mediation-analysis`, `statistical-uncertainty` |
| MR graph construction (stage a) | `mr-graph-model` | `mr-graph-model` | `causal-graph`, `statistical-uncertainty` |
| MR effect estimation (stage b) | `causal-effect-estimate` (with MR extension co-loaded) | `causal-effect-estimate` | `mr-analysis`, `statistical-uncertainty` |
| Mechanistic hypothesis (multi-omics, network-coherence) | `mechanistic-hypothesis-bundle` | `mechanistic-hypothesis-bundle` | `causal-graph` (object_type: candidate-graph); optional `causal-prior-bundle` |

**Why ten extensions instead of one mega-extension.** A unified `causal-payload` extension would require nullable fields for every method family (mediator set, instrument set, prior network ref, identification status, etc.), eroding the "every required field is meaningful" property and re-creating the ~50-field accretion problem `[t022]` solved. Conversely, fewer than ten collapses semantically distinct artifacts (e.g., merging `causal-prior-bundle` into `causal-discovery-run` confuses the *ingredient* with the *process*; merging `mediation-analysis` into `causal-effect-estimate` loses the assumption-set distinction; merging the two MR stages obscures the graph-vs-estimate lifecycle).

**Why two artifacts can produce a graph object.** A `causal-discovery-run` produces an *identifiable-class* graph (CPDAG/PAG/ADMG/posterior) under stated assumptions. A `mechanistic-hypothesis-bundle` produces a *coherent-mechanism* graph that is explicitly pre-identification (Dugourd2021 / COSMOS-style). Forcing them through the same primary type would conflate identification status; separating cleanly preserves the H04 guardrail.

---

## Graph-object taxonomy (`graph_object_type` strict enum)

Used by `causal-graph`, `mr-graph-model`, and `mechanistic-hypothesis-bundle` extensions. The enum is intentionally small.

| Value | Means | Source |
|---|---|---|
| `DAG` | Fully directed, fully oriented; no equivalence-class semantics | textbook |
| `CPDAG` | Markov equivalence class under causal sufficiency; mix of directed and undirected edges | Zhang2021gCastle, Petersen2014 |
| `PAG` | Markov equivalence class under hidden confounding; circle-marked endpoints | Zheng2024 |
| `ADMG` | Directed plus bidirected edges (bidirected = unobserved confounder) | Dong2023 |
| `equivalence-class-feature` | Single feature constant across an equivalence class (e.g., "X→Y oriented in the CPDAG") | derived |
| `candidate-graph` | Single graph with no equivalence-class semantics (e.g., LLM single output, mechanistic hypothesis) | Jiralerspong2024, Dugourd2021 |
| `graph-posterior` | Distribution over graphs (MCMC samples / VI posterior / edge inclusion table) | Zuber2025, t035 cross-ref |

**Authoring rule.** A payload whose graph contains both directed and undirected edges and which assumes causal sufficiency declares `CPDAG`; under hidden confounding, declares `PAG`; with explicit bidirected edges, declares `ADMG`. Mixing types within a single graph object is forbidden — split into multiple payloads if the discovery output has a hybrid character.

**Authoring rule.** A `graph-posterior` payload's `proposition_refs` must be `[]` per `[t022]` Example 4 — graph posteriors propose, not update.

**Authoring rule (added v1.3, P1.3-a).** A `graph-posterior` payload must store edges externally — in `graph_artifact_path` (an MCMC-sample table, edge-inclusion-probability table, or VI-posterior dump) — and never enumerate posterior-summary edges in the `causal-graph` extension's `edges` list. The Edge-Role Taxonomy table reflects this: `graph-posterior` permits `llm_prior_edge` (carried in via prior) but no posterior-summary role, because there is no payload-level role for "an edge whose posterior probability is X." Consumers wanting per-edge probabilities read `graph_artifact_path`. This convention closes the slice-1 ambiguity (`meta/doc/plans/2026-05-06-t034-validator-prototype-findings.md`) and matches the actual usage in Example T34-6.

---

## Edge-role taxonomy (`epistemic_role` strict enum, on each edge)

The graph object's edges each carry an `epistemic_role` field. Strict enum:

| Role | Means | Permitted on graph-object types |
|---|---|---|
| `assumed_background_edge` | Asserted from domain knowledge; not derived | DAG, CPDAG, candidate-graph |
| `llm_prior_edge` | LLM-suggested direct edge; soft prior | DAG, candidate-graph, graph-posterior (via prior) |
| `llm_ancestral_constraint` | LLM-suggested ancestral relation, not direct | candidate-graph, CPDAG (as constraint, not edge) |
| `data_discovered_adjacency` | Algorithm found this edge (oriented or unoriented) from data | CPDAG, PAG, ADMG, candidate-graph |
| `equivalence_class_feature` | Feature constant across the MEC (e.g., directed in CPDAG) | CPDAG, PAG, ADMG |
| `latent_variable_hypothesis` | Postulated unobserved variable connection | PAG, ADMG, candidate-graph |
| `identified_causal_effect` | Promotion role recorded *by reference* — see "How identification updates an edge's role" below; not authored on a discovery-stage `causal-graph` | (recorded by `causal-identification` payload, not in-place on graph) |
| `mediation_path` | Specific direct/indirect path under mediation framework | (recorded by `causal-effect-estimate` + `mediation-analysis` payload, not in-place on graph) |
| `mr_instrumental_effect` | Effect estimated via Mendelian randomization | (recorded by `causal-effect-estimate` + `mr-analysis` payload, not in-place on graph) |
| `mechanistic_hypothesis` | Network-coherence-based; pre-identification | candidate-graph |

**Authoring rule — graph objects record only discovery-stage roles.** The four roles `identified_causal_effect`, `mediation_path`, `mr_instrumental_effect`, and `mechanistic_hypothesis` (when in a mechanistic-hypothesis-bundle) are *promotion* roles: they are not authored in place on a `causal-graph` extension's edge list. Instead, an edge in an upstream graph is promoted by the existence of a downstream payload that references it. The mapping:

- `data_discovered_adjacency` (in a `causal-discovery-run` graph) → `identified_causal_effect`: a `causal-identification` payload exists with `causal_graph_payload_ref` pointing at the upstream graph and `target_estimand` corresponding to that edge.
- `data_discovered_adjacency` → `mediation_path`: a `causal-effect-estimate + mediation-analysis` payload's `input_artifact_refs` includes the upstream graph and the mediation extension names the edge's exposure/mediator/outcome.
- `mr_instrumental_effect`: produced by an `mr-graph-model` payload's edges; promoted to identified-causal-effect status via a downstream `causal-effect-estimate + mr-analysis` payload.

This means: the upstream graph's edge role does not change in place. A consumer wanting an "all currently-identified edges" view joins the upstream graph against the set of `causal-identification` / `causal-effect-estimate` payloads that reference it. This preserves provenance for H03 attention and for the H04 guardrail without requiring re-emission of large graph objects.

**Authoring rule — mixed roles within a single discovery-stage graph.** Heterogeneous graphs (e.g., a CPDAG with some `data_discovered_adjacency` edges and some `assumed_background_edge` edges where domain knowledge fixed orientation) are permitted. The payload's `support_direction` must reflect the *weakest* role's semantics — a CPDAG with one assumed and ten discovered edges still has `support_direction: methodological-input`, not `supports`, because none of its edges yet carry promoted-role semantics.

---

## Payload-vs-first-class-entity decision rule

For each artifact named in `[t034]`'s candidate list, the decision:

| Artifact | Disposition | Rationale |
|---|---|---|
| Candidate variable / measurement proposal | First-class entity (`variable`, `measurement` already exist in Science) | Reusable across many causal pipelines; deserves identity |
| Source annotation, external-variable extraction | First-class entity (`dataset`, `variable`); annotations live as fields | Same |
| Background / prior-knowledge bundle | **Payload** (`causal-prior-bundle`) | Identity is per-pipeline-use; bundle composition varies by run |
| LLM-generated weak prior or constraint set | **Payload** (`causal-prior-bundle` with operator extension co-loaded) | Same as above; operator details from t037 |
| Causal-discovery run | **Payload** (`causal-discovery-run`) | One run = one payload; provenance-rich |
| Learned graph object | **Inside** a `causal-discovery-run` / `mr-graph-model` / `mechanistic-hypothesis-bundle` payload via co-loaded `causal-graph` extension | A graph object always has a producer; the producer payload is the right home |
| Graph diagnostic result | **Payload** (`graph-diagnostic`) | Audits a separate graph; needs own provenance and validation_role |
| Identified estimand | **Payload** (`causal-identification`) | Marks the identification step; has assumption set, status; references the upstream graph |
| Mediation result | **Payload** (`causal-effect-estimate` + `mediation-analysis`) | Effect estimate with mediation-specific composition |
| MR graph posterior | **Payload** (`mr-graph-model` + `causal-graph`) | Stage (a): graph construction with instrument set |
| MR effect estimate | **Payload** (`causal-effect-estimate` + `mr-analysis`) | Stage (b): per-edge effect estimate with MR-specific assumptions |
| Causal effect estimate | **Payload** (`causal-effect-estimate`) | Final-stage artifact |

---

## Method-paper vs applied-payload routing (added v1.2)

A paper that *introduces* a method (e.g., Faller2024 self-compatibility, Petersen2014 roadmap, Ban2023 LLM-prior, Wan2025 LLM-survey, Zuber2025 MrDAG, Dugourd2021 COSMOS) produces *two distinct payload candidates* in this project:

1. **A `methods-paper` core-only paper-extracted-claim.** Lives in `[t022]` core. `artifact_type: methods-paper` (or `framework-paper` / `benchmark-or-dataset-paper` per v2.2 enum). `support_direction: framework-proposal` or `methodological-input`. `validation_role: record-only` or `quality-record-only`. Default reason codes: `single-source-evidence` plus often `simulated-data-only` or `peer-reviewed-only`. *No t034 extension is loaded* — the claim is about the method's properties, not about a specific causal graph.

2. **Zero-or-more applied-payload re-encodings of the paper's worked applications.** Each application becomes its own t034-extension payload (a `causal-discovery-run`, `mr-graph-model`, `mechanistic-hypothesis-bundle`, etc.) with `claim_source_ref: paper:X` for provenance. `extracted-from-summary-only` is declared if the project's paper-summary (rather than the PDF or a pipeline run) is the extraction source.

Authors should consciously decide *which* of these two payload candidates is being authored at any given time. A paper-summary that names the worked application but lacks reproducible detail typically supports (1) cleanly and (2) only sparsely; the v1.2 conditional-required-field rules (P-pilot-1) make the latter case authorable without lying. A pipeline run produces (2) directly, and authors should *not* declare `extracted-from-summary-only` in that case.

This routing is the underlying source of the pilot extraction's `[t034]` ✗-rates: applying a paper-summary against an applied-payload schema is a known impedance mismatch. Authoring (1) instead of (2) when the source is summary-only is often the right call.

## Reason-code authoring conventions (added v1.3)

Two cross-cutting conventions govern how this document's per-extension `Reason-code contributions` sections are read. They were tacit through v1.2 and made explicit in v1.3 after the second validator-prototype slice (`meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-findings.md`) needed unambiguous semantics.

**Biconditional reading (P1.3-b).** A contribution rule of the form *"<code> declared when X"* is read biconditionally: `<code>` must appear in `core.reason_codes` if and only if `X` holds. Over-declaration (declaring `<code>` when `¬X`) is as much a validation error as under-declaration (omitting `<code>` when `X`). The reason: reason codes encode *falsifiable claims* about a payload's epistemic state, not free-form authorial notes. Declaring `pleiotropy-untested` on a payload with `pleiotropy_model: mr-egger` (pleiotropy IS handled) is a category error, not a defensive caveat. The validator rejects both directions.

**Auto-injected always-on contributions (P1.3-c).** A contribution rule of the form *"<code> always when extension loaded"* (or *"always — the bundle's defining property"*) describes a code the validator's contribution-merging step *injects automatically* into `effective_codes`. Authors do **not** write these into `core.reason_codes` by hand. The five always-on contributions are:

| Extension | Auto-injected code(s) |
|---|---|
| `causal-discovery-run` | `identification-missing` (default — runs are not identified by virtue of being runs) |
| `mr-graph-model` | `instrument-assumption-risk` |
| `mr-analysis` | `instrument-assumption-risk` |
| `mechanistic-hypothesis-bundle` | `mechanism-hypothesis-only`, `prior-network-dependent` |

Conditional codes (those that depend on field values, not just on extension presence) remain author-written subject to the biconditional rule above. The injected codes participate in `effective_codes` and propagation exactly as if they had been authored — they are merely sourced from the extension's contribution table rather than the YAML. This (a) keeps payloads visually clean, (b) prevents the "the author forgot the obvious code" failure mode at extract-time, and (c) gives the validator one canonical place to update if a contribution rule changes.

**Authoring-policy decision (P1.4-b).** When an author writes any of the four auto-injected codes — `identification-missing`, `instrument-assumption-risk`, `mechanism-hypothesis-only`, `prior-network-dependent` — into `core.reason_codes` by hand, the validator emits a **hard error** (rule `v1.3-auto-inject` per the slice-3 prototype). There is no migration window; existing payloads carrying these codes by hand must be swept before slice-3 folds into `meta/validate.sh`. Reason: an auto-injected code is a falsifiable claim about *extension presence*, not about payload-specific state — an author re-writing it adds no information and increases drift risk if the contribution table changes.

`effective_codes` is therefore: declared codes (from `core.reason_codes`, post-authoring-check) ∪ auto-injected always-on contributions (from each loaded extension's contribution table) ∪ codes propagated from upstream payloads via `input_artifact_refs` (per each contributing extension's propagation policy), minus codes retired per the retirement table below.

## Reason-code retirement rules (added v1.4)

Retirement removes a code from `effective_codes` at the current payload (and therefore from anything that propagation would carry forward). It does not delete the code from upstream `effective_codes` — origin-chain inspection still surfaces it. Two rules govern retirement:

| Payload condition | Retires |
|---|---|
| `causal-identification` payload with `identification_status ∈ {identified, partially-identified}` | `identification-missing` (whether locally auto-injected by a co-loaded `causal-discovery-run` or propagated from upstream) |
| `causal-effect-estimate + mr-analysis` payload with `pleiotropy_handling != unhandled` AND resolved `mr_graph_payload_ref.instrument_validity_assumptions` includes `relevance` | `instrument-assumption-risk` (whether locally auto-injected by `mr-analysis` or propagated from an upstream `mr-graph-model`) |

The second rule (P1.4-a) is the first retirement rule that depends on *upstream payload state* in addition to local state. Implementation note for the validator: the retirement check needs to resolve `mr_graph_payload_ref` and read `instrument_validity_assumptions` from it before computing local `effective_codes`. The first rule can resolve from local payload fields alone.

The pleiotropy retirement rule already documented in v1.3 (mr-analysis with `pleiotropy_handling != unhandled` retires `pleiotropy-untested`) is unchanged and continues to apply alongside the iar retirement.

## Extension specs

For each: required + optional fields, co-required extensions, validation rules per `validation_role`, uncertainty-summary contract, reason-code contributions, propagation policy.

### `causal-prior-bundle`

Bundle of background knowledge / LLM-elicited / empirical priors fed into a downstream discovery run.

```yaml
extension/causal-prior-bundle:
  prior_role: enum             # background-knowledge / llm-prior / empirical-prior / structural-constraint
  prior_format: enum           # edge-list / ancestral-constraint-list / soft-score-matrix / ordering-constraint
  constraint_type: enum        # hard / soft / ancestral / direction-only
  prior_strength: float [opt]  # in [0,1] for soft constraints; null for hard
  variable_set: [ref]          # the variables the prior is over
  prior_provenance: ref [opt]  # citation for background; agent-tool-operation ref for LLM
  prior_validation_status: enum  # validated / unvalidated / partially-validated
```

**Co-required extensions:** none mandatory; optional `agent-tool-operation` (t037) when `prior_role` is `llm-prior`.

**Validation rules.** `validation_role` permitted values:
- `record-only` — always permitted (the default for a prior bundle that is just being recorded for downstream use)
- `prioritize-attention` — permitted iff `prior_validation_status ∈ {validated, partially-validated}`
- `quality-record-only` — always permitted (when the prior bundle is itself a curated reference object)
- `strengthen-belief` — **forbidden** (a prior is never evidence)
- `gate-update` — **forbidden** (priors constrain; they don't gate)

(A prior bundle's `support_direction` is typically `methodological-input` — that's the support semantic, not the role.)

**Uncertainty-summary contract.** `core.uncertainty_summary` should encode the bundle scope: e.g., `"LLM ancestral prior, 14 variables, soft, validated against 3 background sources"`.

**Reason-code contributions.** Declares: `weak-prior-only` (when `prior_role: llm-prior` is the bundle's only contributor); `llm-prior-unvalidated` (when LLM and `prior_validation_status: unvalidated`); `prior-network-dependent` (when bundle includes `background-knowledge` from a single named network — Dugourd2021's signal).

**Propagation policy.** `propagate-blocking`. Specifically: `weak-prior-only` and `llm-prior-unvalidated` propagate into any downstream `causal-discovery-run` that lists this bundle in `input_artifact_refs`.

### `causal-discovery-run`

A single discovery process executed against observed data, optionally with a prior bundle.

```yaml
extension/causal-discovery-run:
  observed_data_link: ref          # dataset
  discovery_algorithm: str         # PC, GES, FCI, NOTEARS, RLCD, etc.
  algorithm_version: str [opt]
  method_assumption_set: [enum]    # causal-sufficiency / faithfulness / rank-faithfulness / linear / additive-noise / no-selection-bias / acyclicity
  hyperparameters: dict [opt]      # alpha, score function, etc.
  sample_size: int
  causal_sufficiency_assumption: bool   # explicit
  hidden_variable_handling: enum   # none / latent-discovery / equivalence-class-only
  prior_bundle_refs: [ref] [opt]   # causal-prior-bundle payloads
  diagnostic_score: dict [opt]     # algorithm-internal scores; not validation
```

**Co-required extensions:** `causal-graph`. (A discovery run that doesn't produce a graph isn't one.)

**Validation rules.** `validation_role` permitted values:
- `record-only` — always permitted
- `prioritize-attention` — always permitted (the typical role for a discovery run output)
- `gate-update` — permitted only on a *negative* result (e.g., a discovered absence-of-edge that contradicts a prior assumption)
- `strengthen-belief` — **forbidden directly**; only permitted on a downstream `causal-effect-estimate` referencing this run after identification
- `quality-record-only` — forbidden (this is not an audit)

**Uncertainty-summary contract.** Render as `"<graph_object_type>, <n_edges> edges, <algorithm>, <key-assumption-summary>"` — e.g., `"CPDAG, 12 edges, PC, assumes causal sufficiency"`.

**Reason-code contributions.** Declares: `causal-sufficiency-assumption` (whenever `causal_sufficiency_assumption: true`); `latent-variable-risk` (whenever `hidden_variable_handling: none` AND domain has plausible unobserved confounders); `identification-missing` *[auto-injected per v1.3]* (default — no run is identified by virtue of being a run).

**Propagation policy.** `propagate-blocking`. Of the codes this extension declares, only `identification-missing` is blocking, so only `identification-missing` propagates into downstream `causal-identification` / `causal-effect-estimate`. `causal-sufficiency-assumption` and `latent-variable-risk` are non-blocking and remain on this payload only (consumers can still inspect them via the origin chain, but they do not enter `effective_codes` at the consumer).

### `causal-graph`

The graph object. Always co-loaded with a producing extension.

```yaml
extension/causal-graph:
  graph_object_type: enum          # DAG / CPDAG / PAG / ADMG / equivalence-class-feature / candidate-graph / graph-posterior
  causal_model_ref: ref [opt]      # canonical causal model (when one exists)
  nodes: [ref]                     # variable refs
  edges: [edge]                    # see edge schema
  edges_total: int
  identified_edge_count: int       # number of edges with role=identified_causal_effect
  hidden_variable_set: [str] [opt] # for PAG/ADMG/equivalence
  graph_artifact_path: str [opt]   # large graphs/posteriors stored externally
```

Where each `edge` is:

```yaml
- a: ref
  b: ref
  epistemic_role: enum             # see edge-role taxonomy
  oriented: bool                   # for CPDAG/PAG handling
  prior_source_ref: ref [opt]      # for llm_prior_edge / assumed_background_edge
  evidence_strength: float [opt]   # for graph-posterior; PIP or similar
  identification_status: enum [opt] # not-attempted / identified / not-identifiable / failed
  estimand_ref: ref [opt]          # for identified edges
```

**Co-required extensions:** none directly — but a `causal-graph` extension is itself only loaded *as part of* another payload (e.g., `causal-discovery-run`, `mr-graph-model`, `mechanistic-hypothesis-bundle`). The validator must reject a payload whose primary type is `causal-graph` standalone.

**Validation rules (structural, hard errors).**
- `graph_object_type` must be one of the strict enum values; unknown values are rejected.
- For each edge, `epistemic_role` must be in the per-`graph_object_type` permitted set per the Edge-Role Taxonomy table. Mismatches are validation **errors**, not reason codes (e.g., a CPDAG cannot carry `mechanistic_hypothesis` edges).
- The four promotion roles (`identified_causal_effect`, `mediation_path`, `mr_instrumental_effect`, and `mechanistic_hypothesis` outside `mechanistic-hypothesis-bundle`) must NOT appear as in-place edge roles in a discovery-stage `causal-graph`. They are recorded by reference per "How identification updates an edge's role" above. In-place authoring is a validation error.
- The producing extension's role-permission rules also govern; this extension's rules are additive.

**Uncertainty-summary contract.** Producing extension may pull `graph_object_type`, `edges_total`, and identified-fraction (computed by joining against referenced `causal-identification` / `causal-effect-estimate` payloads) into its summary.

**Reason-code contributions.** Declares: `graph-object-ambiguous` (used only when `graph_object_type: candidate-graph` is the deliberate "I don't know which strict type this is" signal — never to caveat a structural error, since structural errors are now hard-rejected).

**Propagation policy.** N/A (extension never primary).

### `causal-identification`

Identification of a target estimand from a causal graph + observed-data link.

```yaml
extension/causal-identification:
  causal_graph_payload_ref: ref    # the upstream graph
  target_estimand: enum            # ATE / CATE / NDE / NIE / interventional-distribution / counterfactual-quantity
  estimand_definition: str         # canonical form, e.g., "E[Y|do(X=1)] - E[Y|do(X=0)]"
  identification_method: enum      # backdoor / frontdoor / iv / mediation-formula / mr-formula / not-identified
  identification_assumptions: [enum]  # exchangeability / positivity / consistency / no-interference / no-unmeasured-confounding / instrument-validity / monotonicity
  identification_status: enum      # identified / partially-identified / not-identified / pending
  adjustment_set: [ref] [opt]      # for backdoor
  instrument_set: [ref] [opt]      # for iv / mr
```

**Co-required extensions:** none mandatory; references graph via `causal_graph_payload_ref`.

**Validation rules.** `validation_role` permitted values:
- `record-only` — always permitted
- `prioritize-attention` — permitted iff `identification_status ∈ {identified, partially-identified}`
- `gate-update` — permitted iff `identification_status: not-identified` (a payload that says "not identifiable" can gate downstream estimation)
- `strengthen-belief` — **forbidden** (identification is not estimation)
- `quality-record-only` — forbidden

**Uncertainty-summary contract.** Render as `"<target_estimand> identified via <identification_method> under <key-assumption>"`.

**Reason-code contributions.** Declares: `identification-missing` (when `identification_status: pending` or `not-identified`); `instrument-assumption-risk` (when `identification_method: iv` and instruments are not externally validated).

**Propagation policy.** `propagate-blocking`. `identification-missing` propagates into downstream `causal-effect-estimate`.

### `causal-effect-estimate`

Estimated causal effect after identification.

```yaml
extension/causal-effect-estimate:
  identification_payload_ref: ref  # upstream causal-identification
  target_estimand_ref: ref         # may equal identification_payload_ref's estimand or a refinement
  estimator: str                   # IPW, AIPW, TMLE, g-formula, MLE, BMA, MR-IVW, MR-Egger, etc.
  effect_estimate:
    point: float
    ci_method: enum
    ci: [float, float] [opt]
    posterior_summary: dict [opt]
  effect_measure: enum             # risk-difference / odds-ratio / hazard-ratio / mean-difference / standardized-mean-difference
  estimator_diagnostics: dict [opt]  # convergence, balance, etc.
```

**Co-required extensions:** `statistical-uncertainty`. Optional: `mediation-analysis`, when the estimand is NDE/NIE.

**Validation rules.** `validation_role` permitted values:
- `strengthen-belief` — permitted iff (a) `identification_payload_ref.identification_status ∈ {identified, partially-identified}`, (b) `effective_codes` (post-retirement per the v1.4 retirement table) include neither `identification-missing` nor `instrument-assumption-risk`, (c) `estimator_diagnostics` are present. Note that `instrument-assumption-risk` is retirable at this payload by a co-loaded `mr-analysis` per the second retirement rule; `identification-missing` is retired by the upstream `causal-identification.identification_status` resolving to `identified` / `partially-identified`. Both retirements are computed before this rule fires.
- All other roles — always permitted.

**Uncertainty-summary contract.** Render as `"<effect_measure> = <point> [<ci_low>, <ci_high>], <estimator>"`.

**Reason-code contributions.** Declares: `estimand-mismatch` (when `target_estimand_ref` differs structurally from the identification payload's estimand).

**Propagation policy.** `propagate-blocking`. Effective codes flow to any synthesis (t023) consuming this estimate.

### `mediation-analysis`

Composes with `causal-effect-estimate` when the estimand is mediation-based.

```yaml
extension/mediation-analysis:
  estimand_type: enum              # NDE / NIE / total-effect-decomposition / composite-null
  mediator_set: [ref]
  mediator_count: int
  exposure_ref: ref
  outcome_ref: ref
  confounder_set: [ref]
  exposure_mediator_interaction: bool
  cross_world_assumption: bool     # required for NDE/NIE under sequential ignorability
  multiplicity_correction: enum    # bonferroni / fdr-bh / fdr-by / none / not-applicable
  composite_null_method: enum [opt]  # for high-dim mediation, per Yang2025
```

**Co-required extensions:** `causal-effect-estimate`.

**Validation rules.** Strengthens `causal-effect-estimate`'s rule: `validation_role: strengthen-belief` additionally requires `cross_world_assumption: true` (declared, not assumed) AND `multiplicity_correction != none` when `mediator_count > 1`.

**Uncertainty-summary contract.** Render as `"<estimand_type> = <point>, <mediator_count> mediators, <multiplicity_correction>"`.

**Reason-code contributions.** Declares: `mediation-estimand-ambiguous` (when `estimand_type: composite-null` and method unspecified); `multiplicity-uncorrected` (when `multiplicity_correction: none` and `mediator_count > 1`); `cross-world-assumption-untested` (always when `cross_world_assumption: true`).

**Propagation policy.** `propagate-blocking`.

### `mr-graph-model`

Mendelian randomization producing a causal graph posterior over exposure-outcome relations using genetic instruments.

```yaml
extension/mr-graph-model:
  exposure_set: [ref]                       # supports core.partial_fields convention
  outcome_set: [ref]                        # supports core.partial_fields convention
  instrument_set: [ref]                     # genetic variants. Required UNLESS extracted-from-summary-only ∈ effective_codes (then [opt]); supports core.partial_fields
  instrument_validity_assumptions: [enum]   # relevance / exclusion / independence / no-pleiotropy / no-reverse-causation / direction-inherent-from-iv-class (v1.2: declares direction is intrinsic to the IV class, e.g., germline genetic instruments)
  pleiotropy_model: enum                    # none-assumed / mr-egger / mr-presso / weighted-median / mr-mix / not-modelled / unspecified (v1.2: unspecified is the paper-summary-silent fallback; triggers non-blocking pleiotropy-unspecified, not blocking pleiotropy-untested)
  direction_constraint: enum                # exposures-to-outcomes-only / bidirectional-search / data-driven
  graph_object_type: enum                   # CPDAG / DAG / graph-posterior — must match co-loaded causal-graph
  summary_statistic_provenance: ref         # GWAS dataset. Required UNLESS extracted-from-summary-only ∈ effective_codes (then [opt])
```

**Co-required extensions:** `causal-graph`, `statistical-uncertainty`.

**Validation rules.** `mr-graph-model` is graph-construction stage (a) — it produces a posterior over MR causal DAGs but **never** an effect estimate. `validation_role` permitted values:
- `prioritize-attention` — permitted (the typical role for an MR posterior)
- `record-only` — always permitted
- `strengthen-belief` — **forbidden directly** on this payload, since a graph posterior does not estimate an effect. Strengthening happens on a downstream stage-(b) `causal-effect-estimate` payload (with `mr-analysis` co-loaded) that references this graph and meets that extension's strengthening guards.
- `gate-update`, `quality-record-only` — forbidden.

**Uncertainty-summary contract.** Render as `"MR <graph_object_type>, <n_exposures> exposures × <n_outcomes> outcomes, <pleiotropy_model>"`.

**Reason-code contributions (v1.2).** Declares:
- `instrument-assumption-risk` *[auto-injected per v1.3]* (always when extension loaded — instruments are never self-validating);
- `pleiotropy-untested` (blocking; declared when `pleiotropy_model ∈ {none-assumed, not-modelled}` — i.e., the author *chose* to not model pleiotropy);
- `pleiotropy-unspecified` (NEW v1.2; non-blocking; declared when `pleiotropy_model: unspecified` — i.e., the value is unknown to the extractor, typically for paper-summary-only extractions where the source is silent on pleiotropy treatment);
- `reverse-causation-assumed` (declared when `direction_constraint: exposures-to-outcomes-only` AND `instrument_validity_assumptions` does NOT include `direction-inherent-from-iv-class` — v1.2 carve-out: germline genetic instruments biologically constrain direction, so declaring the assumption is over-flagging in that case).

**Propagation policy.** `propagate-blocking`. `pleiotropy-untested` (blocking) propagates to any downstream `causal-effect-estimate` referencing this graph, which prevents stage (b) from strengthening unless a less-permissive `pleiotropy_model` is specified at that stage. `pleiotropy-unspecified` (non-blocking) does not propagate to effective_codes at the consumer but remains visible via the origin chain.

### `mr-analysis`

Stage (b) of MR. Composes with `causal-effect-estimate` for per-edge effect estimation under MR assumptions (IVW / Egger / weighted-median / etc.). Method-family specialisation analogous to `mediation-analysis`.

```yaml
extension/mr-analysis:
  mr_graph_payload_ref: ref           # the upstream stage (a) mr-graph-model payload
  exposure_ref: ref                    # the specific exposure for this estimate
  outcome_ref: ref                     # the specific outcome
  instrument_set_used: [ref]           # may be subset of upstream's instrument_set
  estimator_method: enum               # ivw / mr-egger / mr-presso / weighted-median / mr-lasso / mr-mix
  pleiotropy_handling: enum            # mr-egger-intercept / mr-presso-distortion / weighted-median-robust / unhandled
  heterogeneity_test: enum [opt]       # cochrans-q / rucker-q / none
  heterogeneity_test_passed: bool [opt]
  conditional_independence_check: bool [opt]   # for cases where multi-exposure conditioning is meaningful
```

**Co-required extensions:** `causal-effect-estimate`, `statistical-uncertainty`.

**Validation rules.** Strengthens `causal-effect-estimate`'s rule: `validation_role: strengthen-belief` additionally requires (a) `mr_graph_payload_ref` resolves to an `mr-graph-model` payload whose `pleiotropy_model` is not `none-assumed` or `not-modelled`, OR `pleiotropy_handling != unhandled` on this payload (so pleiotropy is addressed at one stage); (b) `instrument_validity_assumptions` upstream includes `relevance`; (c) effective reason codes do not include `pleiotropy-untested` (this code, propagated from stage (a), retires only if stage (b)'s `pleiotropy_handling != unhandled`).

**Uncertainty-summary contract.** Render as `"MR <estimator_method> for <exposure> → <outcome>, <pleiotropy_handling>"`.

**Reason-code contributions.** Declares: `instrument-assumption-risk` *[auto-injected per v1.3]* (always when extension loaded); `mr-heterogeneity-untested` (when `heterogeneity_test: none` or `heterogeneity_test_passed: false`).

**Propagation policy.** `propagate-blocking`.

### `graph-diagnostic`

A diagnostic computed against a previously-recorded `causal-graph` payload.

```yaml
extension/graph-diagnostic:
  audited_graph_payload_ref: ref         # required UNLESS extracted-from-summary-only ∈ effective_codes (then [opt])
  diagnostic_kind: enum                  # self-compatibility / variable-subset-stability / graph-posterior-stability / prior-data-disagreement / refutation-test
  compatibility_notion: [enum] [opt]     # list (v1.2): graphical / interventional — required when diagnostic_kind = self-compatibility; can be both when paper presents the pair
  variable_subsets_tested: [list-of-ref-list] [opt]
  diagnostic_score: float [opt]          # canonical scalar, when one exists
  pass_threshold: float [opt]
  result: enum                           # pass / fail / inconclusive / correlative (v1.2: correlative for "useful signal but not a hard verdict")
```

**Co-required extensions:** none.

**Validation rules.** `validation_role` permitted values:
- `quality-record-only` — always permitted (the only non-trivial role)
- `prioritize-attention` — permitted iff `result: fail` (a failed diagnostic is a revisit signal)
- `record-only` — always permitted
- `strengthen-belief`, `gate-update` — **forbidden** (Faller2024: compatibility cannot certify correctness)

**Uncertainty-summary contract.** Render as `"<diagnostic_kind>: <result> (score=<diagnostic_score>)"`.

**Reason-code contributions.** Declares: `self-incompatible` (when `diagnostic_kind: self-compatibility` AND `result: fail`); `prior-data-disagreement` (when `diagnostic_kind: prior-data-disagreement` AND `result: fail`).

**Propagation policy.** `propagate-blocking`. A failed diagnostic on an upstream `causal-graph` flows to any downstream payload that references either the audited graph OR this diagnostic via `input_artifact_refs`.

### `mechanistic-hypothesis-bundle`

Multi-omics or network-coherence-derived mechanism hypotheses (Dugourd2021 / COSMOS-style). Pre-identification by construction.

```yaml
extension/mechanistic-hypothesis-bundle:
  prior_knowledge_network_ref: [ref]            # v1.2: list shape — paper-derived priors are commonly integrations of multiple curated sources; use core.partial_fields when the integration is not exhaustively listed. Required UNLESS extracted-from-summary-only ∈ effective_codes (then [opt])
  prior_network_version: str [opt]
  omics_layer_set: [enum]                       # transcriptomics / proteomics / metabolomics / phosphoproteomics / etc. supports core.partial_fields
  activity_estimation_method: str               # e.g., footprint-based regulator activity
  causal_reasoning_algorithm: str               # e.g., COSMOS-CARNIVAL
  coherent_subnetwork_size: int                 # Required UNLESS extracted-from-summary-only ∈ effective_codes (then [opt])
  mechanism_role: enum                          # hypothesis-only / supporting-prior / refining-existing
```

**Co-required extensions:** `causal-graph` (with `graph_object_type: candidate-graph` and edges typed `epistemic_role: mechanistic_hypothesis`); optional `causal-prior-bundle`.

**Validation rules.** `validation_role` permitted values:
- `prioritize-attention` — permitted (hypothesis generation is exactly what this is for)
- `record-only` — permitted
- `strengthen-belief`, `gate-update`, `quality-record-only` — **forbidden** (mechanism is hypothesis until identified)

**Uncertainty-summary contract.** Render as `"mechanistic hypothesis: <coherent_subnetwork_size> nodes across <n_omics_layers> layers"`.

**Reason-code contributions.** Declares: `mechanism-hypothesis-only` *[auto-injected per v1.3]* (always — the bundle's defining property); `prior-network-dependent` *[auto-injected per v1.3]* (always — output is conditional on prior network).

**Propagation policy.** `propagate-blocking`.

---

## Reason-code additions to `[t025]`

Codes declared by the above extensions. Mirror to the t025 registry with batch-3 provenance and the blocking flag indicated.

| Code | Owner extension | Blocking? | Note |
|---|---|---|---|
| `causal-sufficiency-assumption` | `causal-discovery-run` | non-blocking | already in t025 |
| `latent-variable-risk` | `causal-discovery-run` | non-blocking | already in t025 |
| `weak-prior-only` | `causal-prior-bundle` | non-blocking | already in t025 |
| `llm-prior-unvalidated` | `causal-prior-bundle` | **blocking** | already in t025 |
| `prior-network-dependent` | `causal-prior-bundle`, `mechanistic-hypothesis-bundle` | non-blocking | **NEW** (Dugourd2021) |
| `graph-object-ambiguous` | `causal-graph` | non-blocking | already in t025 |
| `identification-missing` | `causal-discovery-run`, `causal-identification` | **blocking** | already in t025 |
| `instrument-assumption-risk` | `causal-identification`, `mr-graph-model`, `mr-analysis` | non-blocking | already in t025 |
| `pleiotropy-untested` | `mr-graph-model` | **blocking** | **NEW** (Zuber2025) — `pleiotropy_model ∈ {none-assumed, not-modelled}` |
| `pleiotropy-unspecified` | `mr-graph-model` | non-blocking | **NEW v1.2** (pilot F-pilot-5) — `pleiotropy_model: unspecified` for paper-summary-only extractions |
| `reverse-causation-assumed` | `mr-graph-model` | non-blocking | **NEW** (Zuber2025) — only when constraint is *not* biologically inherent |
| `mr-heterogeneity-untested` | `mr-analysis` | non-blocking | **NEW** (Zuber2025 / standard MR practice) |
| `mediation-estimand-ambiguous` | `mediation-analysis` | non-blocking | already in t025 |
| `multiplicity-uncorrected` | `mediation-analysis` | **blocking** | **NEW** (Yang2025) |
| `cross-world-assumption-untested` | `mediation-analysis` | non-blocking | **NEW** (Yang2025) |
| `self-incompatible` | `graph-diagnostic` | **blocking** | already in t025 |
| `prior-data-disagreement` | `graph-diagnostic` | non-blocking | already in t025 |
| `mechanism-hypothesis-only` | `mechanistic-hypothesis-bundle` | **blocking** | **NEW** (Dugourd2021) |
| `estimand-mismatch` | `causal-effect-estimate` | **blocking** | already in t025 |
| `extracted-from-summary-only` | core (any t034 extension can declare) | non-blocking | **NEW v1.2** (pilot F-pilot-1) — payload was authored from a project paper-summary rather than a PDF re-read or pipeline run; relaxes specific extension required-field rules |

Nine new codes total (v1.1 + v1.2): `prior-network-dependent`, `pleiotropy-untested`, `pleiotropy-unspecified`, `reverse-causation-assumed`, `mr-heterogeneity-untested`, `multiplicity-uncorrected`, `cross-world-assumption-untested`, `mechanism-hypothesis-only`, `extracted-from-summary-only`. Three of these are blocking (`pleiotropy-untested`, `multiplicity-uncorrected`, `mechanism-hypothesis-only`); six non-blocking.

---

## Worked examples

Seven examples covering each primary type. References to v2.2 contract example numbers given in passing.

### Example T34-1 — Causal-discovery run (refines v2.2 Example 3)

PC algorithm applied to observational COVID-vaccine cohort data; produces a CPDAG.

```yaml
core:
  payload_id: ev-2026-vaccine-cpdag-pc-run
  artifact_type: causal-discovery-run
  extensions: [causal-discovery-run, causal-graph]
  created_at: 2026-05-06T13:00:00Z
  input_artifact_refs:
    - dataset:covid-vaccine-obs-cohort
  method_ref: paper:Petersen2014       # roadmap reference
  agent_ref: agent:pc-runner
  pipeline_provenance_ref: pipeline:causal-discovery-pc-v3
  proposition_refs: [prop:vaccination-reduces-severe-illness]
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "CPDAG, 12 edges, PC, assumes causal sufficiency"
  reason_codes: [causal-sufficiency-assumption]   # identification-missing auto-injected per v1.3

extension/causal-discovery-run:
  observed_data_link: dataset:covid-vaccine-obs-cohort
  discovery_algorithm: PC
  algorithm_version: causal-learn-1.4.0
  method_assumption_set: [causal-sufficiency, faithfulness, no-selection-bias]
  hyperparameters: {alpha: 0.05}
  sample_size: 38421
  causal_sufficiency_assumption: true
  hidden_variable_handling: none
  prior_bundle_refs: []
  diagnostic_score: {}

extension/causal-graph:
  graph_object_type: CPDAG
  causal_model_ref: causal-model:vaccine-effectiveness-v1
  nodes: [var:vaccination, var:severe-illness, var:age, ...]
  edges:
    - {a: var:vaccination, b: var:severe-illness, epistemic_role: data_discovered_adjacency, oriented: false, identification_status: not-attempted}
    # ...
  edges_total: 12
  identified_edge_count: 0
  hidden_variable_set: []
```

Refinements vs. v2.2 Example 3: `support_direction: methodological-input` (not `methodological-input` as a stand-in — that was already correct); `identified_edge_count: 0` makes the lack-of-identification machine-checkable.

### Example T34-2 — LLM ancestral-prior bundle (Ban2023-style)

```yaml
core:
  payload_id: ev-2026-vaccine-llm-ancestral-prior
  artifact_type: causal-prior-bundle
  extensions: [causal-prior-bundle, agent-tool-operation]   # t037 co-load
  created_at: 2026-05-06T12:30:00Z
  input_artifact_refs: []
  method_ref: paper:Ban2023
  agent_ref: agent:claude-opus-4-7
  pipeline_provenance_ref: pipeline:llm-ancestral-prior-v1
  proposition_refs: []
  comparison_target: n-a
  support_direction: methodological-input
  validation_role: record-only
  validation_status: pending
  uncertainty_summary: "LLM ancestral prior, 14 variables, soft constraints, unvalidated"
  reason_codes: [weak-prior-only, llm-prior-unvalidated]

extension/causal-prior-bundle:
  prior_role: llm-prior
  prior_format: ancestral-constraint-list
  constraint_type: ancestral
  prior_strength: 0.6
  variable_set: [var:vaccination, var:severe-illness, var:age, ...]
  prior_provenance: trace:llm-elicitation-2026-05-06
  prior_validation_status: unvalidated

extension/agent-tool-operation:           # operator-side, owned by t037; sketched here
  agent_role: causal-prior-elicitor
  agent_model_version: claude-opus-4-7-1m
  prompt_or_workflow_ref: workflow:ancestral-elicitation-v2
  # ... t037 fills the rest
```

Co-loading `agent-tool-operation` lets the LLM provenance live in the t037 extension rather than duplicating fields here.

### Example T34-3 — Identification step (do-calculus backdoor)

```yaml
core:
  payload_id: ev-2026-vaccine-ate-identification
  artifact_type: causal-identification
  extensions: [causal-identification]
  created_at: 2026-05-06T13:30:00Z
  input_artifact_refs: [ev-2026-vaccine-cpdag-pc-run]   # the discovery run
  method_ref: paper:Petersen2014
  agent_ref: agent:human:khughitt
  pipeline_provenance_ref: ~
  proposition_refs: [prop:vaccination-reduces-severe-illness]
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "ATE identified via backdoor under no-unmeasured-confounding"
  reason_codes: []

extension/causal-identification:
  causal_graph_payload_ref: ev-2026-vaccine-cpdag-pc-run
  target_estimand: ATE
  estimand_definition: "E[Y|do(X=1)] - E[Y|do(X=0)]"
  identification_method: backdoor
  identification_assumptions: [exchangeability, positivity, consistency, no-interference]
  identification_status: identified
  adjustment_set: [var:age, var:comorbidity-index, var:test-rate]
```

Note `causal-sufficiency-assumption` from upstream did not propagate here because t025 marks it non-blocking. `identification-missing` from upstream is *retired* by this payload — the upstream run carried it as a pending state, this payload resolves it.

### Example T34-4 — Causal-effect estimate (downstream of T34-3)

```yaml
core:
  payload_id: ev-2026-vaccine-ate-estimate
  artifact_type: causal-effect-estimate
  extensions: [causal-effect-estimate, statistical-uncertainty]
  created_at: 2026-05-06T14:00:00Z
  input_artifact_refs: [ev-2026-vaccine-ate-identification]
  method_ref: paper:vanderLaan2011-tmle
  agent_ref: agent:tmle-runner
  pipeline_provenance_ref: pipeline:tmle-v3
  proposition_refs: [prop:vaccination-reduces-severe-illness]
  comparison_target: null-vs-alternative
  support_direction: supports
  validation_role: strengthen-belief
  validation_status: pending
  uncertainty_summary: "RD = -0.18 [-0.21, -0.15], TMLE"
  reason_codes: []

extension/causal-effect-estimate:
  identification_payload_ref: ev-2026-vaccine-ate-identification
  target_estimand_ref: ev-2026-vaccine-ate-identification
  estimator: TMLE
  effect_estimate:
    point: -0.18
    ci_method: influence-curve
    ci: [-0.21, -0.15]
  effect_measure: risk-difference
  estimator_diagnostics: {balance_check: passed, near_positivity_violations: 0}

extension/statistical-uncertainty:
  posterior_form: gaussian-approx
  ci_method: influence-curve
  prior_sensitivity_checked: not-applicable
```

This payload is the first in the chain permitted to carry `validation_role: strengthen-belief`. The validator confirms upstream `identification_status: identified`, no propagated blocking codes, and presence of `estimator_diagnostics`.

### Example T34-5 — Mediation analysis (Yang2025-style high-dim)

```yaml
core:
  payload_id: ev-2026-smoking-lung-cancer-mediation
  artifact_type: causal-effect-estimate
  extensions: [causal-effect-estimate, mediation-analysis, statistical-uncertainty]
  created_at: 2026-05-06T14:30:00Z
  input_artifact_refs: [ev-2026-smoking-lung-id, dataset:nhanes-mediator-panel]
  method_ref: paper:Yang2025
  agent_ref: agent:hd-mediation-runner
  pipeline_provenance_ref: pipeline:hd-mediation-v1
  proposition_refs: [prop:smoking-mediated-by-inflammation]
  comparison_target: hypothesis-set
  support_direction: supports
  validation_role: strengthen-belief
  validation_status: pending
  uncertainty_summary: "NIE = 0.07, 124 mediators, FDR-BH corrected"
  reason_codes: [cross-world-assumption-untested]

extension/causal-effect-estimate:
  identification_payload_ref: ev-2026-smoking-lung-id
  target_estimand_ref: ev-2026-smoking-lung-id
  estimator: hd-mediation-mle
  effect_estimate: {point: 0.07, ci_method: bootstrap-percentile, ci: [0.04, 0.11]}
  effect_measure: standardized-mean-difference
  estimator_diagnostics: {convergence: ok}

extension/mediation-analysis:
  estimand_type: NIE
  mediator_set: [var:il6, var:crp, var:tnfa, ...]   # 124 entries
  mediator_count: 124
  exposure_ref: var:smoking-pack-years
  outcome_ref: var:lung-cancer-incidence
  confounder_set: [var:age, var:occupational-exposure, var:family-history]
  exposure_mediator_interaction: false
  cross_world_assumption: true
  multiplicity_correction: fdr-bh
  composite_null_method: joint-significance-yang2025

extension/statistical-uncertainty:
  posterior_form: bootstrap
  ci_method: bootstrap-percentile
```

Permitted to strengthen because `cross_world_assumption: true` and `multiplicity_correction: fdr-bh`. Carries `cross-world-assumption-untested` (always declared when CWA is asserted) so a downstream synthesis can route this through more cautious aggregation.

### Example T34-6 — MR graph model (Zuber2025 MrDAG)

```yaml
core:
  payload_id: ev-2026-mrdag-cardio-metab
  artifact_type: mr-graph-model
  extensions: [mr-graph-model, causal-graph, statistical-uncertainty]
  created_at: 2026-05-06T15:00:00Z
  input_artifact_refs:
    - dataset:gwas-cardio-sumstats-v4
    - dataset:gwas-metab-sumstats-v4
  method_ref: paper:Zuber2025
  agent_ref: agent:mrdag-runner
  pipeline_provenance_ref: pipeline:mrdag-mcmc-v2
  proposition_refs: []                       # graph-posterior; proposes, doesn't update
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "MR graph-posterior, 8 exposures × 4 outcomes, MR-Egger pleiotropy"
  reason_codes: [reverse-causation-assumed]   # instrument-assumption-risk auto-injected per v1.3

extension/mr-graph-model:
  exposure_set: [var:ldl, var:hdl, var:tg, var:bmi, ...]
  outcome_set: [var:cad, var:t2d, var:stroke, var:af]
  instrument_set: [variant:rs6511720, ...]   # 312 instruments
  instrument_validity_assumptions: [relevance, exclusion]
  pleiotropy_model: mr-egger
  direction_constraint: exposures-to-outcomes-only
  graph_object_type: graph-posterior
  summary_statistic_provenance: dataset:gwas-cardio-sumstats-v4

extension/causal-graph:
  graph_object_type: graph-posterior
  nodes: [var:ldl, var:hdl, ..., var:cad, var:t2d, ...]
  edges: []                                  # too many; see external path
  graph_artifact_path: results/mrdag-posterior.parquet
  edges_total: 32
  identified_edge_count: 0

extension/statistical-uncertainty:
  posterior_form: full-posterior
  ci_method: hpd
  approximation_diagnostics: {ess_min: 1832, rhat_max: 1.04}
```

`mr-graph-model` is stage (a) — it never strengthens belief on its own, regardless of whether a downstream stage (b) exists. `prioritize-attention` is the maximum role for this payload type. Strengthening (when warranted) happens at a downstream `causal-effect-estimate + mr-analysis` payload referencing this graph; that payload is sketched below as the stage-(b) companion. `pleiotropy-untested` is *not* declared because `pleiotropy_model: mr-egger` is a non-trivial choice; `reverse-causation-assumed` is declared because direction was constrained, not learned.

A stage-(b) companion would look like (sketch — fields abridged):

```yaml
core:
  payload_id: ev-2026-mrdag-ldl-cad-effect
  artifact_type: causal-effect-estimate
  extensions: [causal-effect-estimate, mr-analysis, statistical-uncertainty]
  input_artifact_refs: [ev-2026-mrdag-cardio-metab]   # the stage-(a) graph
  proposition_refs: [prop:ldl-causal-on-cad]
  support_direction: supports
  validation_role: strengthen-belief                  # permitted under mr-analysis guards
  uncertainty_summary: "MR-Egger: log-OR(LDL→CAD)=0.42 [0.31, 0.55]"
  ...
extension/mr-analysis:
  mr_graph_payload_ref: ev-2026-mrdag-cardio-metab
  exposure_ref: var:ldl
  outcome_ref: var:cad
  estimator_method: mr-egger
  pleiotropy_handling: mr-egger-intercept   # retires upstream pleiotropy-untested
  ...
```

Strengthening is permitted at stage (b) iff `pleiotropy_handling != unhandled` AND upstream `instrument_validity_assumptions` includes `relevance`. Two retirements fire at this payload (per v1.4 retirement table): the upstream `pleiotropy-untested` blocking code is retired by `pleiotropy_handling: mr-egger-intercept`; the `instrument-assumption-risk` code (auto-injected locally by `mr-analysis` *and* propagated from upstream `mr-graph-model`) is retired by the same `pleiotropy_handling != unhandled` condition combined with the upstream `instrument_validity_assumptions` containing `relevance`. Without P1.4-a's iar retirement rule, this example would not validate at strengthen-belief — slice-3 of the validator-prototype program surfaced this gap.

### Example T34-7 — Self-compatibility diagnostic (Faller2024)

```yaml
core:
  payload_id: ev-2026-vaccine-cpdag-self-compat
  artifact_type: graph-diagnostic
  extensions: [graph-diagnostic]
  created_at: 2026-05-06T13:15:00Z
  input_artifact_refs: [ev-2026-vaccine-cpdag-pc-run]
  method_ref: paper:Faller2024
  agent_ref: agent:self-compat-runner
  pipeline_provenance_ref: pipeline:self-compat-v1
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: validated
  uncertainty_summary: "self-compatibility: pass (incompat=0.07 < 0.15)"
  reason_codes: []

extension/graph-diagnostic:
  audited_graph_payload_ref: ev-2026-vaccine-cpdag-pc-run
  diagnostic_kind: self-compatibility
  compatibility_notion: graphical
  variable_subsets_tested: [[var:vaccination, var:severe-illness, var:age], [var:vaccination, var:severe-illness, var:comorbidity-index], ...]
  diagnostic_score: 0.07
  pass_threshold: 0.15
  result: pass
```

`validation_role: quality-record-only` is the *maximum* permitted by this extension's rules — even with `result: pass`, this cannot strengthen belief. Faller's central claim, encoded.

### Example T34-8 — Mechanistic hypothesis (Dugourd2021 / COSMOS)

```yaml
core:
  payload_id: ev-2026-cosmos-egfr-resistance
  artifact_type: mechanistic-hypothesis-bundle
  extensions: [mechanistic-hypothesis-bundle, causal-graph]
  created_at: 2026-05-06T15:30:00Z
  input_artifact_refs:
    - dataset:nsclc-egfr-multiomics
    - kg:omnipath-2025
  method_ref: paper:Dugourd2021
  agent_ref: agent:cosmos-runner
  pipeline_provenance_ref: pipeline:cosmos-v2
  proposition_refs: [prop:egfr-resistance-mechanism]
  comparison_target: hypothesis-set
  support_direction: methodological-input
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: "mechanistic hypothesis: 47 nodes across 3 omics layers"
  reason_codes: []   # mechanism-hypothesis-only and prior-network-dependent auto-injected per v1.3

extension/mechanistic-hypothesis-bundle:
  prior_knowledge_network_ref: kg:omnipath-2025
  prior_network_version: omnipath-2025-q1
  omics_layer_set: [transcriptomics, phosphoproteomics, metabolomics]
  activity_estimation_method: footprint-decoupler-v2
  causal_reasoning_algorithm: COSMOS-CARNIVAL
  coherent_subnetwork_size: 47
  mechanism_role: hypothesis-only

extension/causal-graph:
  graph_object_type: candidate-graph
  nodes: [...]                               # 47 nodes
  edges:
    - {a: protein:EGFR, b: protein:ERK, epistemic_role: mechanistic_hypothesis, oriented: true, prior_source_ref: kg:omnipath-2025}
    # ...
  edges_total: 89
  identified_edge_count: 0
```

Validator forbids `validation_role: strengthen-belief` here per the extension's rule, regardless of how coherent the subnetwork is.

---

## Alignment notes

**With `[t022]` v2.2.** This task uses every v2.2 affordance: multi-extension dispatch (5/8 examples load 2+ extensions), reason-code propagation (`identification-missing`, `pleiotropy-untested` are spec'd as blocking and propagating), `target_artifact_ref` lives inside `graph-diagnostic` (audited graph) and inside `causal-identification` (referenced graph) rather than core. No core-schema changes proposed by this task.

**With `[t023]` (synthesis nodes).** The synthesis types listed in t023 — *causal-discovery-run synthesis*, *mediation synthesis*, *Mendelian-randomization graph synthesis*, *graph-diagnostic synthesis*, *mechanistic-network synthesis* — each consume payloads from this task. Suggested mapping: each synthesis type aggregates payloads of the matching primary type, with synthesis-specific aggregation rules (e.g., MR graph synthesis = posterior-merge across studies, with shared-instrument-set risk). When t023 lands, this task's payloads are its inputs.

**With `[t025]` (reason-code registry).** Nine new codes to mirror in t025 with batch-3 provenance: `prior-network-dependent`, `pleiotropy-untested`, `pleiotropy-unspecified`, `reverse-causation-assumed`, `mr-heterogeneity-untested`, `multiplicity-uncorrected`, `cross-world-assumption-untested`, `mechanism-hypothesis-only`, `extracted-from-summary-only`. Three blocking; six non-blocking. The blocking-vs-non-blocking line: codes are blocking when their presence should prevent `strengthen-belief` on a causal proposition without further work; non-blocking when they're persistent caveats but don't gate the update. The `extracted-from-summary-only` code (added v1.2) acts as a *relaxation gate* on specific extension required-fields — see "Conditional required-field rules" subsection per affected extension.

**With `[t026]` (causal guardrails).** This task and `[t026]` are tightly paired — `[t026]` defines the abstract guardrail set (target population, source population, identification status, etc.); this task makes the guardrails machine-enforceable via validation rules. Recommendation: `[t026]`'s "missing metadata should produce a warning, validation error, or H01 revisit signal" decision is now well-typed: validation rules above produce errors (forbidden roles), reason codes produce warnings + H01 signals.

**With `[t033]`/`[t037]` (LLM-as-source / agent-tool-ops).** The `causal-prior-bundle` extension does *not* duplicate operator provenance; it co-loads the `agent-tool-operation` extension when the prior was LLM-elicited. This is the v2.2-multi-extension pattern in action. When `[t037]` lands its extension spec, this task's worked Example T34-2 will need to be updated to align field names — flagged as a coordination point, not a blocker.

**With `[t038]` (graph-evolution / KG views).** A `causal-graph` payload's `graph_artifact_path` and the lifecycle of graph-posterior summaries cross into `[t038]`'s territory (versioning, replay, derived views). Out of scope here; `[t038]` should treat causal graphs as a sub-class of graph-valued artifacts that carry causal-typed edges.

**With sibling natural-systems project's observability program (2026-05-06 next-steps doc).** The natural-systems project is running a parallel "asserted vs. verified" sweep across three layers (code metadata, label/lens artifacts, prose citations), with a unifying observation that *the project encodes its discipline as vocabulary and schema but does not yet execute it as machinery*. Their `verifiable: true` rows that lack runners (`pipeline/label-provenance/results/field-provenance.json`) are the same gap shape this design risks: a `validation_role: strengthen-belief` claim that lacks an enforcing runner. Two cross-project commitments worth making early: (1) the validation rules in this doc must be implemented as enforcing runners — a `causal-effect-estimate` payload claiming `strengthen-belief` without `estimator_diagnostics` should fail at validate-time, not pass with a comment; (2) the same `pipeline/<scope>/results/{<scope>.json,<scope>.tsv,coverage.json}` row-shape convention used for natural-systems audits is a candidate target for `[t034]`-payload audits as well, so cross-project rigor metrics aggregate cleanly. This is a coordination signal, not a v1.1 dependency — the design stands without it. See `~/d/natural-systems/doc/meta/next-steps-2026-05-06.md` and `~/d/natural-systems/doc/interpretations/2026-05-06-citation-audit-pilot.md`.

---

## Migration / mapping for existing project content

The project already has `causal-modeling` aspect tasks and several Batch-3 papers consumed as `cite:` references. No existing causal-edge entities exist that need migrating (per `[t022]` migration notes, all current support/dispute edges are non-causal). When the first causal-edge migration lands (probably under `[t026]`), the rule is:

- A bare "X causally affects Y" assertion with no provenance → `causal-prior-bundle` with `prior_role: background-knowledge`, `support_direction: methodological-input`, `validation_role: record-only`, `reason_codes: [legacy-unverified-payload]`. Not promotable to `causal-effect-estimate` until evidence is reconstructed.
- A claim citing a published RCT or observational study with effect estimate → `causal-effect-estimate` with `causal-identification` reconstructed from the source method, `reason_codes` set per source quality.
- A claim citing a meta-analysis → `causal-effect-estimate` *plus* a t023-style `causal-meta-analysis` synthesis node referencing it.

---

## Open questions

1. **Should `causal-graph` be a first-class entity rather than an extension?** Tradeoff: the graph object is content-heavy and reusable across many downstream payloads (an identification + an effect estimate + a diagnostic might all reference the same graph). An entity gives identity and reuse. Counter: the v2.2 contract has a strong "extensions don't get instantiated standalone" rule, so making `causal-graph` an entity would require breaking that. Currently spec'd as extension-only; revisit if reuse becomes load-bearing.

2. **Granularity of mediation paths.** Per-mediator-path payload (one `causal-effect-estimate` per mediator) versus per-bundle (one payload with mediator_count and a vectorized estimate)? Spec'd as per-bundle here per Yang2025's high-dim framing; per-path may be needed for low-dim mechanistic analysis. Defer until `[t023]` mediation-synthesis design forces a choice.

3. **Should `prior-network-dependent` always propagate?** It's a near-permanent property of mechanistic work — every COSMOS-style output carries it. Risk of noise: if it propagates aggressively, every downstream synthesis will accumulate it and the signal degrades. Currently spec'd non-blocking; consider gating its propagation past 1 hop.

4. **Do equivalence-class-feature edges deserve their own propositions?** A CPDAG edge that is constant across the equivalence class (e.g., directed in every member DAG) is a different epistemic object than an undirected adjacency. Should it get its own `prop:` entity, or stay as an edge field? Lean: stays as edge field; t023 synthesis can promote to a proposition if many independent CPDAGs converge on the same orientation.

5. **MR's `direction_constraint: exposures-to-outcomes-only` and `reverse-causation-assumed`.** Currently the code is declared whenever direction is constrained, regardless of whether the constraint is well-justified (genetics inherently constrains direction for germline IVs). Risk of over-flagging. Refinement: only declare when the constraint is not biologically grounded — but this requires an authoring judgment. Keep as-is for v1; revisit if extractors over-trigger.

6. **Cross-extension shared field: `causal_model_ref`.** Used by `causal-graph`, `causal-identification`, `causal-effect-estimate`. Could become a `causal-context` shared extension. Defer; not a v1 issue.

7. **Should `graph-posterior` summaries (PIPs, edge probabilities) live in `causal-graph` or in a co-loaded `graph-valued-artifact` extension owned by `[t035]`?** Currently both are spec'd to carry posterior-related fields. Likely `[t035]` should own the posterior-summary semantics, and `causal-graph` references it via co-load. Coordinate when `[t035]` drafts.

8. **`identification-missing` retirement semantics.** Spec'd: when a downstream `causal-identification` payload sets `identification_status: identified`, the upstream's `identification-missing` is *retired* — does not propagate further. This is a one-off rule in the propagation system; needs validator support. Confirm with t025 / validator implementer.

---

## Audit prompts

For an `[t030]`-style audit of this draft, the four most likely points of failure to probe:

- **Extension count.** Is ten right, or have I over-fragmented? Specifically: should `mr-graph-model` and `mr-analysis` collapse into one MR extension with a `stage: graph | estimate` enum? Probably not — they load against different primary types (`mr-graph-model` is itself a primary; `mr-analysis` co-loads onto `causal-effect-estimate`) — but the audit should test it.
- **Edge-role taxonomy completeness.** Are nine roles enough? Or have I missed e.g. an `interventional-effect-edge` (RCT-derived) and a `policy-effect-edge` (causal-inference-on-policy-data)?
- **Validation rules are enforceable from the contract.** Each rule references upstream payload state (e.g., `identification_payload_ref.identification_status`). The validator must be able to dereference these — confirm with the validator implementation.
- **Worked examples vs reality.** Examples are constructed; an audit should re-extract one of them from the actual source paper (e.g., recreate T34-1 from a real PC run on a public dataset) and surface field-fit problems empirically, like `[t030]` did for `[t022]`.

---

## Next steps

1. **Audit-style review** of this v1 draft (analogous to `[t030]` narrow audit on `[t022]`). Surface field-overload, missing roles, invalid validation rules. Outputs: v1.1 patches.
2. **Sister-extension coordination.** Cross-check `causal-prior-bundle`'s `agent-tool-operation` co-load against the `[t037]` v1 draft when it lands; cross-check `graph-posterior` field placement against `[t035]` v1.
3. **Mirror new reason codes to `[t025]`.** Nine codes: `prior-network-dependent`, `pleiotropy-untested`, `pleiotropy-unspecified`, `reverse-causation-assumed`, `mr-heterogeneity-untested`, `multiplicity-uncorrected`, `cross-world-assumption-untested`, `mechanism-hypothesis-only`, `extracted-from-summary-only`. With blocking flag and batch-3 provenance.
4. **Pilot extraction.** Pick 2–3 Batch-3 papers (Faller2024, Zuber2025, Dugourd2021 are highest-yield given their distinct artifact types) and extract real payloads under this draft. Surfaces ambiguities the worked examples don't.
5. **Defer:** `causal-meta-analysis` synthesis node (t023), `[t026]` formal guardrails (depends on this draft's enums stabilizing), entity-vs-extension status for `causal-graph` (open question 1).

The structural decisions of this draft — the ten-extension carve-up, the graph-object enum, the edge-role enum (with promotion-by-reference rather than in-place rewrite), the validation-role permission table per extension, and the structural validation rules on `causal-graph` — are the load-bearing claims. Field names and reason-code blocking flags remain candidates pending audit and pilot extraction.

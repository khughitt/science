# Typed Synthesis Nodes - Design (t023 draft v1)

> **Status:** v1 complete (2026-05-07). Review patches clarified that synthesis nodes are `[t022]` payloads with synthesis-family artifact types, split default versus maximum permissions, added routing and owner-arbitration rules, scoped effective reason codes to computed views, and moved lifecycle/output-artifact replay semantics to `[t042]`. Designs `[t023]` against the v2.3 evidence-payload core/extension contract at `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`.

**Scope:** This task defines the cross-cutting synthesis-node contract and synthesis-family taxonomy. It does not duplicate the detailed field schemas owned by sibling aspect tasks such as `[t034]` causal graph construction, `[t035]` graph-valued / multiview artifacts, `[t037]` agent/tool operations, `[t038]` graph evolution and KG views, or `[t040]` robustness/reproducibility evaluation.

**Goal:** Make synthesis operations first-class derivation artifacts so Science does not collapse effect-size pooling, model comparison, truth discovery, graph posterior estimation, causal synthesis, and decision scoring into one generic belief update.

**Related tasks:** `[t021]` (parent), `[t022]` (core contract), `[t024]` (heterogeneity/bias mechanisms), `[t025]` (reason-code registry), `[t026]` (causal guardrails), `[t031]` (source-dependence detection), `[t034]`, `[t035]`, `[t037]`, `[t038]`, `[t040]`.

**Sources:** Batch 1 through Batch 4 synthesis notes, especially Bayesian evidence synthesis, truth discovery / data integration, causal graph construction, and graph-valued / multiview integration.

---

## Design stance

Long term, a synthesis node is a first-class derivation artifact:

- Evidence payloads say "this artifact bears on these propositions."
- Synthesis nodes say "this operator combined these inputs under these assumptions and produced these outputs."
- Output artifacts carry the concrete result: scalar support, posterior summary, graph object, cluster assignment, feature set, diagnostic result, new proposition, or downstream payload.

This separation matters because the epistemic meaning of a result depends on both the operator and the output. A graph posterior, an MCDA ranking, a Bayes factor, and a diagnostic-test meta-analysis can all be "syntheses", but they should not write to the same belief slot or pass the same validation rules.

## Near-term t023 boundary

`[t023]` should define:

1. The minimal synthesis-node contract.
2. The synthesis-family taxonomy.
3. The graph edges linking inputs, operations, outputs, propositions, methods, agents, and validation records.
4. Permission rules for whether a synthesis can strengthen belief, prioritize attention, create hypotheses, or remain a quality/record-only artifact.
5. Alignment constraints that detailed aspect extensions must obey.

`[t023]` should not define every per-family field. Detailed fields remain with the owning aspect task. For example, MR instrument fields belong to `[t034]`, graph posterior fields belong to `[t035]`, operation trace fields belong to `[t037]`, KG-view lifecycle fields belong to `[t038]`, and robustness metric fields belong to `[t040]`.

## Core synthesis-node contract

Near term, a synthesis node is a `[t022]` payload whose `core.artifact_type` is a synthesis-family artifact type. There is no separate synthesis-node store in v1. The operation-specific fields below live in a required `extension/synthesis-operation` section, and family-specific fields live in the owning detail extension.

Every synthesis payload carries the `[t022]` core fields. The subset below shows the fields most load-bearing for synthesis dispatch:

```yaml
core:
  payload_id: ref
  artifact_type: enum              # one of the synthesis families below
  extensions: [synthesis-operation, ...]
  created_at: datetime
  input_artifact_refs: [ref]
  proposition_refs: [ref]
  method_ref: ref [opt]
  agent_ref: ref [opt]
  pipeline_provenance_ref: ref [opt]
  validation_role: enum
  validation_status: enum
  uncertainty_summary: str [opt]
  reason_codes: [enum]

extension/synthesis-operation:
  output_artifact_refs: [ref]
  operator_assumption_refs: [ref]
```

Field semantics:

- `input_artifact_refs` are the consumed payloads, datasets, graph views, source records, or prior synthesis outputs.
- `proposition_refs` retains `[t022]` semantics: propositions this payload is evidence about. It can be empty for exploratory graph, clustering, quality-record, operation-record, or hypothesis-generation syntheses.
- `output_artifact_refs` are the artifacts produced by the operation. They may be payloads, graph artifacts, tables, diagnostics, propositions, or derived views.
- `operator_assumption_refs` identify reusable assumptions such as independence, exchangeability, transportability, shared-structure, causal sufficiency, missingness, score-to-prior mapping, or source-reliability model assumptions.
- `reason_codes` are declared local concerns. Effective reason codes are computed from local codes plus propagated input codes under `[t025]` propagation rules; they are not source-authored in the payload.

## Synthesis-family taxonomy

| Family | Default permission | Max permission with conditions | Typical outputs | Primary owner |
|---|---|---|---|---|
| `effect-size-pooling` | `prioritize-attention` | `strengthen-belief` when estimand, population, heterogeneity, and bias diagnostics are sufficient | pooled effect payload, heterogeneity diagnostics | `[t022]` |
| `hypothesis-support-synthesis` | `prioritize-attention` | `strengthen-belief` when support metric, comparison target, and uncertainty semantics are explicit | support payload, posterior/probability summary | `[t022]` |
| `bayesian-model-comparison` | `prioritize-attention` | `strengthen-belief` for model-set propositions when priors and comparison target are explicit | posterior model probabilities, Bayes factors, inclusion probabilities | `[t022]` |
| `diagnostic-test-synthesis` | `prioritize-attention` | `strengthen-belief` when reference-standard fallibility and thresholding are modeled | sensitivity/specificity payload, latent-class diagnostic summary | `[t022]` |
| `truth-discovery` | `prioritize-attention` | `strengthen-belief` only with source-dependence and reliability checks | truth labels, source reliability scores, conflict diagnostics | `[t024]` |
| `decision-analytic-score` | `record-only` | `prioritize-attention` after an owning task defines the detailed schema | MCDA score sets, curation rankings, triage lists | reserved; no production use before owner task |
| `data-cleaning-repair` | `quality-record-only` | `prioritize-attention`; downstream evidence must cite validation before belief update | cleaned values, repair uncertainty, transformation record | `[t024]` |
| `causal-meta-analysis` | `prioritize-attention` | `strengthen-belief` only through `[t026]` causal guardrails | causal effect estimate, transport/estimand diagnostics | `[t026]` |
| `causal-discovery-synthesis` | `prioritize-attention` | `create-hypothesis`; `strengthen-belief` requires downstream identification/effect-estimate payloads | graph object, graph posterior, candidate causal propositions | `[t034]` |
| `llm-prior-constraint-synthesis` | `record-only` | `prioritize-attention`; never direct evidence | weak priors, constraints, variable proposals | `[t034]` |
| `mechanistic-network-synthesis` | `prioritize-attention` | `create-hypothesis`; causal belief update requires `[t026]` guardrails | candidate mechanism graph, module/pathway hypothesis | `[t034]` |
| `mediation-synthesis` | `prioritize-attention` | `strengthen-belief` only when identification and mediation assumptions pass | direct/indirect effect payloads | `[t034]` |
| `mendelian-randomization-graph-synthesis` | `prioritize-attention` | `strengthen-belief` only for downstream identified estimates | MR graph posterior, MR effect estimate | `[t034]` |
| `graph-diagnostic-synthesis` | `quality-record-only` | `quality-record-only`; can block or downgrade other payloads | compatibility checks, graph validation report | `[t034]` |
| `graph-estimate-synthesis` | `prioritize-attention` | `create-hypothesis`; causal belief update requires identification | conditional-dependence graph, common/unique component graph | `[t035]` |
| `graph-posterior-synthesis` | `prioritize-attention` | `create-hypothesis`; causal belief update requires downstream identification | graph samples, edge inclusion table, posterior summary | `[t035]` |
| `integrative-clustering-synthesis` | `prioritize-attention` | `create-hypothesis`; belief update requires proposition-specific validation | cluster assignments, subtype hypotheses | `[t035]` |
| `feature-selection-synthesis` | `prioritize-attention` | `prioritize-attention`; belief update requires separate validation payload | selected-feature set, relevance posterior, stability report | `[t035]` |
| `module-discovery-synthesis` | `prioritize-attention` | `create-hypothesis`; belief update requires proposition-specific validation | module/pathway membership artifact | `[t035]` |
| `predictive-integration-synthesis` | `quality-record-only` | `prioritize-attention`; belief update requires proposition-specific validation | predictive model, risk score, validation artifact | `[t035]` |

**Owner arbitration rule.** The primary owner in the table owns field names, required-field rules, and validation semantics for the family. Secondary tasks may define co-loaded extensions, but field-name collisions resolve to the primary owner unless a later design explicitly changes the table.

**Reserved-family rule.** `decision-analytic-score` is reserved because MCDA-like scoring appears in project questions but has no concrete workflow yet. Validators should reject production payloads with this `artifact_type` until an owning task defines its detailed schema.

## Family routing rules

Authors choose the narrowest family that matches the aggregation operator:

- Use `effect-size-pooling` when the operation pools numeric effect estimates for a shared estimand.
- Use `bayesian-model-comparison` when the operation compares models or hypotheses through prior-sensitive posterior model probabilities, Bayes factors, or inclusion probabilities. Gronau/RoBMA-style BMA routes here unless the actual output is only a pooled effect estimate.
- Use `hypothesis-support-synthesis` when the operation aggregates evidence directly into proposition support without a model-set comparison or effect-size pooling operator.
- Use `diagnostic-test-synthesis` when the target output is test accuracy or latent diagnostic state, even if the model is Bayesian.
- Use causal families when the output is intended to bear on causal propositions; noncausal graph, clustering, and feature-selection outputs stay in `[t035]` families until a downstream causal-identification payload exists.
- Use `truth-discovery` when the central operation estimates source reliability, source dependence, or truth labels from conflicting sources.
- Use `data-cleaning-repair` when the operation transforms observations before evidence is authored; downstream payloads cite the repair output rather than treating the repair as direct support.

## Graph edges

Synthesis nodes introduce explicit derivation edges:

| Edge | Meaning |
|---|---|
| `consumes` | synthesis node consumes an input artifact |
| `uses-method` | synthesis node uses a method, instrument, workflow, or operator definition |
| `performed-by` | synthesis node was authored or run by an agent |
| `produced` | synthesis node emitted an output artifact |
| `targets-proposition` | synthesis intended to bear on a proposition |
| `validates` | validation/evaluation artifact evaluates a synthesis or its output |
| `supersedes` | a later synthesis replaces an earlier output under an explicit lifecycle rule |
| `derived-from-synthesis` | output artifact records its producer for replay/invalidation |

`validates` may target one synthesis payload, one output artifact, or an explicit list of output artifacts from the same synthesis. A validation payload that covers multiple outputs must enumerate all covered refs; otherwise consumers assume it covers only the referenced artifact.

`targets-proposition` is derived from `core.proposition_refs`. If `proposition_refs` is empty, no `targets-proposition` edge is emitted.

These edges let downstream consumers reason over the derivation DAG without parsing prose. They also give `[t038]` and `[t042]` stable hooks for replay, KG-view provenance, lifecycle state, and invalidation.

## Validation rules

Validation is permissioned, not merely descriptive.

- A synthesis may only declare `validation_role: strengthen-belief` if the synthesis family permits it and all required guardrails pass.
- Exploratory graph, clustering, feature-selection, LLM-prior, and MCDA syntheses do not strengthen propositions by default.
- Causal syntheses must pass `[t026]` guardrails before strengthening causal propositions.
- Quality-record syntheses can validate, dispute, or downgrade other artifacts, but a passing diagnostic does not by itself strengthen a domain proposition.
- Blocking reason-code rules should be biconditional where possible: a blocking code should be declared exactly when its triggering condition is present, not as a vague caveat. Non-blocking descriptive codes follow `[t025]`'s blocking/non-blocking classification and may remain declarative when the registry defines them that way.
- Effective reason codes flow from inputs to outputs according to `[t025]`; blocking codes prevent `strengthen-belief` unless a downstream validation artifact explicitly retires or resolves them. The source-authored payload stores only `core.reason_codes`; `effective_reason_codes` is a computed derivation view, materialized only by validator/replay machinery owned by `[t038]`/`[t042]`.

## Output-artifact boundary

An output should be a first-class artifact when any of these are true:

- It can be reused by more than one downstream synthesis.
- It is large or externally stored, such as graph samples, edge tables, model outputs, or trace logs.
- It needs independent validation, review, supersession, or lifecycle state.
- It carries typed semantics not reducible to the synthesis operation itself.

Otherwise, compact scalar outputs can remain embedded in the producing payload, while still exposing an `output_artifact_ref` if later reuse becomes necessary.

## Alignment notes

**With `[t022]`.** Synthesis nodes use the same provenance, validation-role, validation-status, uncertainty-summary, and reason-code discipline as the core payload contract. The difference is that synthesis nodes emphasize operation and derivation, while payloads emphasize evidence-bearing content.

**With `[t026]`.** Causal-meta-analysis, mediation, MR, causal-discovery, graph-estimate, graph-posterior, and mechanistic-network syntheses can strengthen causal propositions only through `[t026]` guardrails. `[t023]` names the synthesis families; `[t026]` decides when their outputs may become causal belief updates.

**With `[t034]`.** Causal-discovery, LLM-prior, mechanistic-network, mediation, MR graph, and graph-diagnostic syntheses consume and produce `[t034]` causal artifacts. `[t023]` supplies the operation layer; `[t034]` supplies causal graph fields and guardrails.

**With `[t035]`.** Graph-estimate, graph-posterior, clustering, feature-selection, module-discovery, and predictive-integration syntheses produce the graph-valued and integration-valued artifacts owned by `[t035]`.

**With `[t037]`.** Agent-authored or tool-run syntheses should reference operation records for model, prompt/workflow, context retrieval, safety policy, and trace provenance rather than duplicating those fields.

**With `[t038]`.** The synthesis derivation DAG is the source of truth for replay, invalidation, derived KG views, and artifact supersession.

**With `[t040]`.** Robustness, reproducibility, and diagnostic syntheses are often quality-record-only, but they can block or downgrade downstream belief updates through effective reason codes.

## Follow-up task

The long-term architecture is tracked as `[t042]`:

**Design synthesis artifact lifecycle and output-artifact model.**

Scope: define how synthesis nodes, output artifacts, propositions, validation runs, and downstream syntheses form a derivation DAG. Cover replay, invalidation, supersession, reason-code propagation, artifact reuse, and the decision rule for first-class output artifacts versus embedded output fields.

This is intentionally outside `[t023]` v1 so the taxonomy can land without forcing a full lifecycle implementation.

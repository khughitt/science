# Typed Synthesis Nodes

Typed synthesis nodes implement `meta/doc/plans/2026-05-07-t023-typed-synthesis-nodes-design.md`.

Near term, a synthesis node is an `EvidencePayload` whose `core.artifact_type` is a synthesis-family artifact type. There is no separate synthesis store. Every synthesis payload lists its family as the primary extension and also loads `synthesis-operation`.

Required shape:

```yaml
core:
  payload_id: syn-2026-example
  artifact_type: bayesian-model-comparison
  extensions: [bayesian-model-comparison, synthesis-operation]
  created_at: 2026-05-08T10:00:00Z
  input_artifact_refs: [study:input]
  proposition_refs: [prop:model-a-over-null]
  comparison_target: model-set
  support_direction: supports
  validation_role: prioritize-attention
  validation_status: pending
  uncertainty_summary: PMP(model-a)=0.72
  reason_codes: []
extension/bayesian-model-comparison: {}
extension/synthesis-operation:
  output_artifact_refs: [payload:model-summary]
  operator_assumption_refs: [assumption:prior-model-probabilities-explicit]
```

Families:

- `effect-size-pooling`
- `hypothesis-support-synthesis`
- `bayesian-model-comparison`
- `diagnostic-test-synthesis`
- `truth-discovery`
- `decision-analytic-score`
- `data-cleaning-repair`
- `causal-meta-analysis`
- `causal-discovery-synthesis`
- `llm-prior-constraint-synthesis`
- `mechanistic-network-synthesis`
- `mediation-synthesis`
- `mendelian-randomization-graph-synthesis`
- `graph-diagnostic-synthesis`
- `graph-estimate-synthesis`
- `graph-posterior-synthesis`
- `integrative-clustering-synthesis`
- `feature-selection-synthesis`
- `module-discovery-synthesis`
- `predictive-integration-synthesis`

`decision-analytic-score` is reserved. Validators reject production payloads with that family until an owning task defines a detailed schema.

Routing rules:

- Model-set posterior probabilities, Bayes factors, and BMA outputs route to `bayesian-model-comparison`.
- Pooled numeric effect estimates route to `effect-size-pooling`.
- Direct proposition support aggregation routes to `hypothesis-support-synthesis`.
- Diagnostic accuracy outputs route to `diagnostic-test-synthesis`.
- Source reliability or truth-label estimation routes to `truth-discovery`.
- Causal outputs route to causal families and require downstream guardrails before belief strengthening.
- Noncausal graph, clustering, feature-selection, module, and predictive integration outputs route to graph-valued families.

Implementation APIs:

- `validate_synthesis_payload()` validates production synthesis payloads. It enforces reserved-family rejection, primary extension ordering, permission ceilings, generic registry validation, and `SynthesisOperation` parsing.
- `route_synthesis_family()` maps known operator and output route keys to canonical synthesis family names.
- `derivation_edges()` builds graph edges from inputs, methods, agents, propositions, and outputs.
- `effective_reason_codes()` computes reason-code views for consumers that need effective codes.

Effective reason codes are computed views. Source-authored payloads store only `core.reason_codes` plus extension-local reason codes.

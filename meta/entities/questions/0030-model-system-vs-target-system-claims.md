---
id: question:0030-model-system-vs-target-system-claims
kind: question
title: Should the evidence schema distinguish model-system claims from target-system
  claims?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Tahko2023
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0002-evidence-payload-schema
- paper:Tahko2023
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the evidence schema distinguish model-system claims from target-system claims?

## Summary

Tahko (2023) draws a sharp distinction between *model-system claims* — assertions about
what a model represents internally (e.g., "the frictionless-plane model has no friction")
— and *target-system claims* — assertions about the actual phenomenon being modelled
(e.g., "a real surface approximately behaves as frictionless in this regime"). The two
classes of claim have structurally different truthmakers: model-system claims are made
true by properties of the model itself (its internal representational structure), whereas
target-system claims are made true by actual entities and their modal properties in the
world. The question is whether the Science toolkit's evidence schema should add a
claim-type tag distinguishing these two classes, and what consequences that would have
for evidence propagation across patches.

## Why It Matters

- **Evidence propagation correctness**: if model-system claims (e.g., a theoretical
  derivation from a causal DAG structure) and target-system claims (e.g., an empirical
  GWAS hit) are tagged identically, the belief aggregation layer cannot distinguish
  evidence that bears on the model's internal consistency from evidence that bears on the
  actual world. This risks propagating "model-internally supported" claims as if they were
  empirically grounded.
- **Provenance integrity**: the existing toolkit provenance types (`editorial`, `empirical`,
  `mathematical`) partially capture this distinction but do not enforce it structurally.
  A model-system claim with empirical provenance is still a model-system claim and should
  not update a target-system proposition as though it were direct empirical evidence of the
  target.
- **Guardrail design** (`h04`, `q0003`): causal-estimand guardrails should fire differently
  depending on claim type. A claim derived from a theoretical causal model (model-system)
  may be fully valid as prior-specification evidence without yet constituting causal
  evidence about an actual population (target-system). Without the distinction, guardrails
  either over-fire (blocking valid model-derived inference) or under-fire (treating
  model-derived claims as target-system evidence).
- **Risk if unanswered**: evidence nodes from LLM-generated theoretical models and
  evidence nodes from empirical datasets silently accumulate under the same proposition,
  making calibration misleading. The toolkit's belief aggregation layer cannot distinguish
  "many independent theoretical derivations" from "many independent empirical observations."

## Current Evidence

- **Supporting ([@Tahko2023])**: The model-system / target-system distinction is philosophically
  grounded and tracks a real difference in truthmaker structure. Target-system claims require
  actual-world grounding; model-system claims require only internal representational
  consistency. The distinction is not merely epistemic but metaphysical.
- **Partial support (existing provenance types)**: The toolkit already tracks
  `provenance_type` (editorial, empirical, mathematical, derived) and `evidence_type`
  (lit, emp, sim, bench, expert). A model-system claim would typically have
  `provenance_type: mathematical` or `provenance_type: editorial`. But this does not
  *prevent* a mathematically derived model-system claim from updating a target-system
  proposition — it is only a label.
- **Against (schema complexity)**: Adding a mandatory claim-type field increases the
  authoring burden for every evidence entry. Many real evidence items sit at the boundary
  (e.g., a validated simulation result is partly model-system, partly target-system). A
  hard binary may not capture the graded structure.
- **Partial mitigation**: The `source_class` (obs, derived, ref) + `derived_kind` fields
  in the existing provenance model partially encode this. An `obs` evidence node with
  empirical data is a target-system claim; a `derived` node from a model derivation is a
  model-system claim. The question is whether this implicit encoding is sufficient or
  whether it needs to be made explicit and enforced.

## Thoughts

- **Best current interpretation**: the distinction should be encoded as an optional
  annotation on evidence nodes (`claim_scope: model-system | target-system | both`) rather
  than a mandatory field. Most empirical nodes default to `target-system`; most
  mathematical/editorial derivations default to `model-system`. Mixed cases (validated
  simulation against real data) use `both`.
- **Guardrail implication**: a `model-system` tagged evidence node should update the
  patch's internal consistency score but should require an additional `target-system`
  anchor before it can strengthen a causal proposition in the `object_layer`.
- **Major uncertainty**: whether this annotation is actionable at scale. If authors
  consistently mis-tag, the annotation is noise. A default-inferred scheme (provenance type
  → claim scope) may be more robust than requiring explicit tagging.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (the object_layer / meta_layer split
  mirrors the target-system / model-system split); `hypothesis:0004-causal-estimand-guardrails`
  (guardrails need to fire differently by claim scope).
- Required data or analyses: audit a sample of existing evidence nodes in `entities/papers/`
  and classify them as model-system or target-system to measure how often the distinction
  matters in practice, and whether `provenance_type` already captures it reliably.
- Priority level: medium — lower than finalising the causal graph construction pipeline
  (q0010) but relevant before scaling evidence ingestion.

## Related

- Topic notes: `hypothesis:0007-working-model` (object_layer vs. meta_layer);
  `question:0002-evidence-payload-schema` (the broader payload design question).
- Article notes: `paper:Tahko2023` §3 (model-system vs. target-system claims, truthmakers);
  `paper:Frigg2025` §3 (surrogative reasoning, how model knowledge transfers to target).
- Methods/Datasets: n/a at this stage.

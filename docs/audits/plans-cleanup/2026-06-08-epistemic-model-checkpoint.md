# Epistemic Model Implementation Checkpoint

Date: 2026-06-30

This checkpoint preserves the post-implementation contract that had been spread
across active June planning files. Current user-facing behavior is documented in:

- `docs/user-guide/epistemic-model.md`
- `docs/user-guide/evidence-lines.md`
- `docs/user-guide/graph-and-derived-state.md`
- `docs/user-guide/health-and-validation.md`

## Implemented Contract

- A `proposition` is the single truth-apt, belief-bearing assertion. Relational
  propositions carry subject, sign-free predicate, object, polarity, claim layer,
  and identification strength. A relational proposition's own IRI is also the
  rendered edge-node IRI.
- Proposition-edges are belief-bearing assertions. Plumbing edges such as
  containment, patch membership, grouping, and measurement wiring do not carry
  belief.
- Authored `edge_status` is retired as scientific source of truth. Renderers use
  orthogonal channels and may expose `derived_edge_status` as a lossy compatibility
  projection.
- Evidence lines own support/dispute grounding. Empirical belief-eligible lines
  require `dataset_usage`; `belief_eligible: false` stages incomplete empirical
  lines so they emit no `cito:supports` / `cito:disputes` and do not enter belief.
- `quantitative_result` is evidence substance on an evidence line and can feed
  scalar belief projections. It is not authored belief.
- `EvidenceType` is model-typed. The canonical tokens are normalized at parse;
  graph readers share the suffix normalizer but degrade unknown graph literals to
  rank 0 rather than raising.
- `patch-definition` is authored patch intent. Patch membership is derived graph
  state emitted as authoritative `sci:PatchMembership` nodes, with generated
  `sci:hasMember` / `sci:inPatch` convenience edges.
- `<patch>.workbench.yaml` is an editable normalized projection over entities.
  Compile/check keeps it a fixed point; consumers read compiled entities and
  graph state, not the workbench as a parallel epistemic store.
- `graph attention-rank` is the deterministic review queue. Open-question debt
  is computed from direct `skos:related` links and shared theme membership for
  active, partially answered, or deferred questions.
- `entity review` through the CLI requires a note artifact so reviews cannot be
  bare timestamp bumps.

## Preserved Deferrals

- MM30 legacy edge-corpus migration remains outside the framework implementation.
- Broader epistemic drift M2/M3 work remains active: operationalization coverage,
  decision-review scope, and rubric/backstop behavior are not closed by M1.
- Patch follow-ons remain deferred: `PatchSnapshot`, remote/commons scopes,
  ontology or latent glue, patch maturity levels, lead/candidate workflow, and
  inquiry subsumption beyond the current profile bridge.
- Evidence-tier weighting and cross-modality reward are not implemented by the
  typed evidence model. They need a separate belief-policy design.
- `negative_result` is accepted as a valid but unranked evidence type for
  compatibility; deeper semantic cleanup may remodel it later as stance/scope
  metadata instead of a type.

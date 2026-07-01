# t034 causal graph evidence contract

This page is the durable authoring contract for t034 causal graph evidence
payloads in the meta project. The historical design and prototype trail lives
under `doc/plans/historical/`; this page records the rules enforced by
`src/t034_validator/` and exercised by `tests/test_t034_validator.py`.

## Validation entry points

- `validate.sh` runs `python -m t034_validator evidence/` through
  `validate_local.py`.
- `python -m t034_validator evidence/` validates every top-level `.yaml` or
  `.yml` payload in `meta/evidence/`.
- `tests/test_t034_validator.py` is the durable test suite extracted from the
  three t034 prototype slices: causal-graph structure, MR graph-model role and
  field rules, and cross-payload effective-code propagation.

Each payload is keyed by `core.payload_id`. The loader fails on missing payload
ids, duplicate ids, malformed YAML, non-mapping YAML, and missing payload
directories.

## Extension and section shape

Every extension listed in `core.extensions` must have a matching
`extension/<name>` section, and every `extension/<name>` section must be listed
in `core.extensions`. This prevents a payload from silently bypassing rules by
listing an extension without content, or by carrying an unlisted section.

`core.input_artifact_refs` must resolve to payload ids loaded in the same
directory. Cycles are validation errors; `effective_codes` halts at the cycle
boundary so validation does not recurse forever.

## Pipeline and artifact dispositions

The causal graph pipeline is staged. Authors should not collapse prior
elicitation, discovery, identification, estimation, diagnostics, and mechanism
hypotheses into one payload.

| Stage | Artifact | Primary extension | Co-required extensions |
|---|---|---|---|
| Variable proposal / annotation | first-class entities | none | none |
| External-variable extraction | first-class `dataset` / `variable` entities | none | none |
| Prior-knowledge or LLM-prior assembly | payload | `causal-prior-bundle` | optional `agent-tool-operation` for LLM origin |
| Causal-discovery run | payload | `causal-discovery-run` | `causal-graph` |
| Learned graph object | embedded in producer payload | `causal-graph` | producer extension |
| Graph diagnostic | payload | `graph-diagnostic` | references audited graph |
| Identification | payload | `causal-identification` | references upstream graph |
| Effect estimation | payload | `causal-effect-estimate` | `statistical-uncertainty` |
| Mediation specialization | payload | `causal-effect-estimate` | `mediation-analysis`, `statistical-uncertainty` |
| MR graph construction, stage a | payload | `mr-graph-model` | `causal-graph`, `statistical-uncertainty` |
| MR effect estimation, stage b | payload | `causal-effect-estimate` | `mr-analysis`, `statistical-uncertainty` |
| Mechanistic hypothesis | payload | `mechanistic-hypothesis-bundle` | `causal-graph`; optional `causal-prior-bundle` |

Candidate variables, measurements, datasets, and source annotations are reusable
entities, not t034 evidence payloads. A graph object is not a standalone payload;
it is content on a producer such as `causal-discovery-run`, `mr-graph-model`, or
`mechanistic-hypothesis-bundle`.

## Extension inventory

This inventory records the authoring contract for all t034 extension families.
Some rules are enforced by the current validator; others are stable authoring
rules that future validators may enforce.

### `causal-prior-bundle`

Fields: `prior_role`, `prior_format`, `constraint_type`, `variable_set`,
`prior_validation_status`; optional `prior_strength` and
`prior_provenance`.

Permitted roles are `record-only`, `prioritize-attention` when the prior is
validated or partially validated, and `quality-record-only`. `strengthen-belief`
and `gate-update` are forbidden. Reason codes include `weak-prior-only`,
`llm-prior-unvalidated`, and `prior-network-dependent`; blocking prior codes
propagate to downstream discovery runs.

### `causal-discovery-run`

Fields: `observed_data_link`, `discovery_algorithm`,
`method_assumption_set`, `sample_size`, `causal_sufficiency_assumption`, and
`hidden_variable_handling`; optional `algorithm_version`, `hyperparameters`,
`prior_bundle_refs`, and `diagnostic_score`.

Co-load `causal-graph`. `record-only` and `prioritize-attention` are permitted;
`gate-update` is reserved for negative results; direct `strengthen-belief` is
forbidden because strengthening requires downstream identification and effect
estimation. `identification-missing` is auto-injected and blocking.

### `causal-identification`

Fields: `causal_graph_payload_ref`, `target_estimand`,
`estimand_definition`, `identification_method`,
`identification_assumptions`, and `identification_status`; optional
`adjustment_set` and `instrument_set`.

`record-only` is always permitted. `prioritize-attention` is permitted when the
status is `identified` or `partially-identified`; `gate-update` is permitted
when the status is `not-identified`; `strengthen-belief` is forbidden because
identification is not estimation. Identified or partially identified payloads
retire propagated `identification-missing`.

### `causal-effect-estimate`

Fields: `identification_payload_ref`, `target_estimand_ref`, `estimator`,
`effect_estimate`, `effect_measure`; optional `estimator_diagnostics`.

Co-load `statistical-uncertainty`. Optional specializations include
`mediation-analysis` and `mr-analysis`. `strengthen-belief` is guarded by the
consumer rule below; other roles are permitted when the payload is being used as
a record or attention signal rather than as belief-strengthening evidence.

### `mediation-analysis`

Fields: `estimand_type`, `mediator_set`, `mediator_count`, `exposure_ref`,
`outcome_ref`, `confounder_set`, `exposure_mediator_interaction`,
`cross_world_assumption`, and `multiplicity_correction`; optional
`composite_null_method`.

Co-load `causal-effect-estimate`. `strengthen-belief` additionally requires the
cross-world assumption to be explicit and multiple-mediators analyses to use a
correction other than `none`.

### `mr-analysis`

Fields: `mr_graph_payload_ref`, `exposure_ref`, `outcome_ref`,
`instrument_set_used`, `estimator_method`, and `pleiotropy_handling`; optional
`heterogeneity_test`, `heterogeneity_test_passed`, and
`conditional_independence_check`.

Co-load `causal-effect-estimate` and `statistical-uncertainty`. Stage-b MR can
strengthen only when the upstream MR graph resolves, instrument relevance is
present upstream, pleiotropy is handled locally or upstream, and effective codes
no longer include blocking MR risk codes.

### `graph-diagnostic`

Fields: `diagnostic_kind` and `result`; optional `audited_graph_payload_ref`,
`compatibility_notion`, `variable_subsets_tested`, `diagnostic_score`, and
`pass_threshold`. `audited_graph_payload_ref` may be omitted only for
summary-only extractions.

`quality-record-only` and `record-only` are permitted. `prioritize-attention` is
permitted for failed diagnostics. `strengthen-belief` and `gate-update` are
forbidden because diagnostics can falsify or prioritize review but cannot certify
causal correctness.

### `mechanistic-hypothesis-bundle`

Fields: `prior_knowledge_network_ref`, `omics_layer_set`,
`activity_estimation_method`, `causal_reasoning_algorithm`,
`coherent_subnetwork_size`, and `mechanism_role`; optional
`prior_network_version`. Summary-only extractions may omit
`prior_knowledge_network_ref` and `coherent_subnetwork_size`.

Co-load `causal-graph` with `graph_object_type: candidate-graph` and
`mechanistic_hypothesis` edges. `prioritize-attention` and `record-only` are
permitted; `strengthen-belief`, `gate-update`, and `quality-record-only` are
forbidden. `mechanism-hypothesis-only` and `prior-network-dependent` are
auto-injected.

## Causal graph structure

The `causal-graph` extension uses a strict `graph_object_type` enum:

- `DAG`
- `CPDAG`
- `PAG`
- `ADMG`
- `equivalence-class-feature`
- `candidate-graph`
- `graph-posterior`

Edge `epistemic_role` values are checked against the graph object type. Discovery
stage graph edges may use the roles permitted by `EDGE_ROLE_BY_GRAPH_TYPE` in
`src/t034_validator/__init__.py`. Promotion-only roles are never authored
in-place on a producing graph:

- `identified_causal_effect`
- `mediation_path`
- `mr_instrumental_effect`

Those roles are represented by downstream payloads that reference the upstream
graph. A `mechanistic_hypothesis` edge is only permitted in-place when the
payload's primary extension is `mechanistic-hypothesis-bundle`.

## MR graph-model rules

The `mr-graph-model` extension is a stage-a graph construction artifact, not an
effect estimate. Its permitted `core.validation_role` values are:

- `prioritize-attention`
- `record-only`

It rejects direct `strengthen-belief`, `gate-update`, and `quality-record-only`
roles. It co-requires `causal-graph` and `statistical-uncertainty` in
`core.extensions`.

The MR graph-model `graph_object_type` slice is narrower than the full causal
graph enum:

- `CPDAG`
- `DAG`
- `graph-posterior`

Always-required MR fields:

- `exposure_set`
- `outcome_set`
- `instrument_validity_assumptions`
- `pleiotropy_model`
- `direction_constraint`
- `graph_object_type`

Conditionally required fields are `instrument_set` and
`summary_statistic_provenance`. They may be absent only when
`extracted-from-summary-only` is in effective codes.

The reason-code field-state rules are biconditional:

- `pleiotropy-untested` is required exactly when `pleiotropy_model` is
  `none-assumed` or `not-modelled`.
- `pleiotropy-unspecified` is required exactly when `pleiotropy_model` is
  `unspecified`.
- `reverse-causation-assumed` is required exactly when `direction_constraint` is
  `exposures-to-outcomes-only` and
  `direction-inherent-from-iv-class` is absent from
  `instrument_validity_assumptions`.

## Effective codes

For payload `p`:

```text
effective_codes(p) =
  declared(p)
  union auto_injected(p)
  union propagated_blocking(upstream(p))
  minus retired_by(p)
```

`declared(p)` is `core.reason_codes`. `auto_injected(p)` is derived from loaded
extensions:

| Extension | Auto-injected code(s) |
|---|---|
| `causal-discovery-run` | `identification-missing` |
| `mr-graph-model` | `instrument-assumption-risk` |
| `mr-analysis` | `instrument-assumption-risk` |
| `mechanistic-hypothesis-bundle` | `mechanism-hypothesis-only`, `prior-network-dependent` |

Authors must not hand-write auto-injected codes. The validator emits
`v1.3-auto-inject` as a hard error when an auto-injected code appears in
`core.reason_codes`.

Only blocking codes propagate through `core.input_artifact_refs`. The current
blocking set is:

- `llm-prior-unvalidated`
- `identification-missing`
- `pleiotropy-untested`
- `multiplicity-uncorrected`
- `self-incompatible`
- `mechanism-hypothesis-only`
- `estimand-mismatch`

Retirement is local to the current payload:

- `causal-identification` with `identification_status` of `identified` or
  `partially-identified` retires `identification-missing`.
- `mr-analysis` with `pleiotropy_handling` other than `unhandled` retires
  `pleiotropy-untested`.
- The same handled `mr-analysis` retires `instrument-assumption-risk` when its
  resolved `mr_graph_payload_ref` points to an upstream `mr-graph-model` payload
  whose `instrument_validity_assumptions` includes `relevance`.

## Strengthen-belief consumer rule

A `causal-effect-estimate` payload with `core.validation_role:
strengthen-belief` is accepted only when all of the following hold:

- `extension/causal-effect-estimate.identification_payload_ref` resolves.
- The referenced identification payload has `identification_status` of
  `identified` or `partially-identified`.
- Post-retirement `effective_codes` does not contain `identification-missing` or
  `instrument-assumption-risk`.
- `extension/causal-effect-estimate.estimator_diagnostics` is present.

This is the t034 guardrail that prevents discovery-stage graph outputs, MR graph
posteriors, unretired instrument-risk payloads, or diagnostics-free estimates
from strengthening beliefs by assertion.

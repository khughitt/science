# t022 evidence payload core contract

This page is the durable authoring contract for the t022 evidence payload core
and extension mechanism. The historical design trail lives under
`doc/plans/historical/`; this page records the current non-plan contract used by
Science payload tooling.

## Current implementation

- `science/src/science_tool/evidence_payload.py` implements the generic
  `EvidencePayloadCore`, `EvidencePayload`, extension registry, reason-code
  propagation, and role validation helpers.
- `science/tests/test_evidence_payload_contract.py` pins the generic t022 core
  and extension-contract behavior.
- `meta/src/t034_validator/` implements additional t034 causal/MR-specific
  validation rules that sit on top of this contract.
- `meta/evidence/t034-causal-graph-contract.md` records the durable t034
  extension contract.

The generic t022 module intentionally validates only the reusable substrate:
core field shape, extension registration, co-required extension closure,
extension required fields, effective reason-code propagation, and blocking-code
permission checks. Aspect-specific field-state rules belong in extension
validators such as t034.

## Core fields

Every payload has a `core` mapping. The v2.3 core fields are:

```yaml
core:
  payload_id: str
  artifact_type: str
  extensions: [str]
  created_at: datetime
  source_commit: str | null

  input_artifact_refs: [ref]
  claim_source_ref: ref | null
  method_ref: ref | null
  agent_ref: ref | null
  pipeline_provenance_ref: ref | null

  proposition_refs: [ref]
  comparison_target: enum          # null-vs-alternative / hypothesis-set / model-set / method-set / artifact-target / n-a

  support_direction: enum          # supports / disputes / qualifies / methodological-input / framework-proposal / quality-record / operation-record
  validation_role: enum
  validation_status: enum
  uncertainty_summary: str | null

  reason_codes: [str]
  abstention_reason: str | null
  partial_fields: [str] | null
```

`payload_id`, `artifact_type`, `extensions`, `created_at`,
`input_artifact_refs`, `proposition_refs`, `comparison_target`,
`support_direction`, `validation_role`, `validation_status`, and
`reason_codes` are required. Nullable fields may be omitted by YAML authors when
they are not meaningful.

`core.extensions` must list at least one extension. The first extension is the
primary extension and must have the same `artifact_type` as `core.artifact_type`.

## Provenance fields

Use `input_artifact_refs` for derivation inputs: datasets, primary studies,
prior payloads, and upstream artifacts whose content was used to produce this
payload.

Use `claim_source_ref` for paper-extracted claims: the artifact from which the
claim was extracted. Do not put the paper into `input_artifact_refs` unless the
paper is also a derivation input to a synthesis or evaluation.

Use `method_ref` for the canonical method, checklist, instrument, or tool
definition. This is distinct from both derivation inputs and claim source.

Use `pipeline_provenance_ref` for the concrete run or execution record that
created the payload.

## Attachment fields

Use `proposition_refs` for propositions this payload bears on. It may be empty
for evaluation, operation, exploratory graph, and other record-only artifacts.

Do not use `target_artifact_ref` in core. t022 v2.2 moved targets into the
owning extension. Evaluation, audit, and operation extensions should declare
their own target field, usually `target_artifact_ref` or `target_artifact_refs`,
and validate its cardinality locally.

The generic Python model accepts a payload when it attaches through
`proposition_refs`, `input_artifact_refs`, or `claim_source_ref`. Extension
validators are responsible for stricter target requirements on payload families
that need them.

## Epistemic fields

`validation_role` is permission: what consumers may do with the payload.
Supported roles are:

- `strengthen-belief`
- `prioritize-attention`
- `create-hypothesis`
- `gate-update`
- `quality-record-only`
- `record-only`

`validation_status` is state: whether this payload has been validated. It is not
the peer-review status of `claim_source_ref`. Newly authored extracted claims
normally start as `pending`.

`uncertainty_summary` is optional. Use it only when the source or pipeline has a
canonical short rendering, such as a Bayes factor, posterior probability, edge
count, or checklist score. For purely qualitative content, leave it empty rather
than synthesizing prose that implies false precision.

`reason_codes` is an explicit list. Use `[]` when no declared concerns apply.
Extension-generated or inherited codes are added by the contribution/propagation
machinery; authors should not duplicate generated codes by hand.

## Partial fields

`partial_fields` marks multi-element list fields whose values are known to be
partial. Use full field paths, for example:

```yaml
partial_fields:
  - extension/mr-graph-model.exposure_set
```

If a field path appears in `partial_fields`, downstream consumers must treat the
listed values as a subset, not a complete enumeration. If a field path is absent,
the listed values are treated as complete unless the extension contract says
otherwise. t022 uses this single core convention instead of adding per-extension
`*_complete` flags.

## Extension contract

Each extension spec declares:

- `name`
- `artifact_type`
- required and optional fields
- co-required extensions
- role-specific validation rules
- static reason-code contributions
- reason-code propagation policy
- owning task
- uncertainty-summary contract

A payload validates against the generic extension contract when:

1. the primary extension exists and matches `core.artifact_type`;
2. every extension listed in `core.extensions` has an extension section;
3. all transitive co-required extensions are listed;
4. every listed extension has its required fields;
5. effective reason codes are known to the registry;
6. `strengthen-belief` is blocked by any effective blocking reason code; and
7. extension-specific role rules pass.

Plan-style YAML keys such as `extension/causal-graph` are accepted and folded
into `extension_sections` by the Python model.

## Effective reason codes

Effective reason codes are:

```text
declared core reason codes
+ extension-section reason codes
+ extension static reason codes
+ inherited upstream reason codes
```

Inherited codes flow through `core.input_artifact_refs` according to the
upstream primary extension's propagation policy:

- `propagate-all`
- `propagate-blocking`
- `propagate-tagged-only`
- `no-propagate`

The default extension policy is `propagate-blocking`. Blocking inherited codes
can prevent downstream `strengthen-belief`.

## Out of scope

Do not force every paper or project note into a t022 payload. Survey papers,
taxonomy/vocabulary contributions, conceptual theory papers, method-registry
imports, and reusable topic notes should become their own entity or registry
records unless they contain a specific extracted claim.

Paper-extracted claims are in scope when they make an empirical,
methodological, or evaluation assertion that bears on a proposition or
operation. Those payloads use `claim_source_ref` plus an appropriate reason code
such as `single-source-evidence`.

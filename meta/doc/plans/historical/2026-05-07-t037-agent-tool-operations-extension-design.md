# Agent / Tool Operations - Extension Design (t037 draft v1.3)

> **Status:** v1.3 draft (2026-05-07). v1.3 patches from validator prototype findings (`meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md`): (P-proto-1) tightened safety not-applicable semantics so an applicable registry-resolved safety policy makes `safety_check_status: not-applicable` invalid; (P-proto-2) preserved the retrieval-method boundary for `context-retrieval-uncertain`, so partial explicit-user-provided context does not declare that code by itself; (P-proto-3) recorded standalone prototype coverage for `ato-1` through `ato-10` with 20 passing fixtures, including two pilot-adapted operation cases. Designs the `[t037]` operation layer against the v2.3 evidence-payload contract at `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`.
>
> **Prior history:** v1.2 pilot patches from `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md`: (P-pilot-1) added a provisional registry-ref authoring convention for pilot/design extraction while keeping production validation registry-resolved; (P-pilot-2) clarified that operation `method_ref` prefers concrete project workflow refs and uses method papers only when they are the operative protocol; (P-pilot-3) clarified class-level and dataset/protocol-level `agent-evaluation` coverage when `evaluated_operation_refs: []`; (P-pilot-4) made Bayes-factor `evidence-for-risk` independently sufficient for `agent-bias-risk`; (P-pilot-5) added a project-local trace/provenance requirement for after-the-fact operation records.
>
> **Prior history:** v1.1 audit patches: (F1) canonicalized `agent-source-unvalidated` as a local operation-extension rule and removed cross-payload variants from `agent-evaluation`; (F2) made the absence-sensitive role set explicit; (F3) required a one-step `tool_chain_ref` for direct command/skill/tool invocations so `tool-chain-unvalidated` has no bare-capability escape hatch; (F4) stated that safety and chain validation rules run against a registry-resolved operation view; (F5) added authoring rules for `context_ref_set` vs `input_artifact_refs`, empty `evaluated_operation_refs`, operation `method_ref`, and normalized not-applicable validation/safety states.
>
> **Scope:** This task owns how Science represents agents, agent roles, tools, skills, commands, tool chains, execution traces, safety policies, validation protocols, and operation records. Sister tasks `[t034]` (causal graph construction), `[t035]` (graph-valued / multiview), `[t038]` (graph evolution / KG views), and `[t040]` (robustness / reproducibility) own neighboring concerns and are referenced where they compose.
>
> **Goal:** Specify the operations registry, operation-record extension, evaluation extension, validation rules, H03 reason-code contributions, propagation policy, causal-prior co-load interlock with `[t034]`, and worked examples sufficient for audit-style review.

**Related tasks:** `[t029]` (research-paper workflow), `[t033]` (LLM agents as fallible sources), `[t034]` (causal graph construction; direct co-load dependency), `[t038]` (graph evolution and KG views), `[t025]` (reason-code registry), `[t022]` (core contract - v2.3).

**Source:** `doc/background/papers/synthesis-2026-05-06-scientific-agents-knowledge-graphs.md` plus paper-summary grounding from Ding2025, Yu2026, Si2025, Zhang2025ScientificMethod, Jiang2024, Gong2024, Jin2025, and Dai2024GraphAttention.

---

## Findings from the worked-example exercise

Drafted against the Batch 5 synthesis and the existing t022 Example 5 (`agent-tool-operation`). Six findings drive the carve-up below.

**Finding 1 - Agents are both sources and operators.** Q07 models LLMs as fallible sources; Batch 5 adds that agents also transform graph state through tools, retrieval, summarization, validation, and task edits. A single `agent_ref` on core provenance is not enough. Science needs an operation record that says what role the agent played, what model/workflow was used, what context was retrieved, what tools ran, and what validation happened.

**Finding 2 - Tool capability is registry state, not payload state.** Ding2025's SciToolAgent depends on tool capabilities, prerequisites, I/O formats, compatibility, dependencies, and safety levels. Those fields should not be repeated inside every payload. They belong to first-class registry entities (`tool`, `skill`, `command`, `tool_chain`, `safety_policy`, `validation_protocol`). Payloads reference the relevant registry rows plus the execution trace.

**Finding 3 - Operation records are provenance, not evidence.** A successful command run, tool chain, paper summary, or KG retrieval does not by itself support a scientific proposition. It can create or update target artifacts, but belief update requires a downstream evidence/evaluation payload with the appropriate validation role. Therefore the primary `agent-tool-operation` extension normally has `support_direction: operation-record`, `validation_role: record-only`, and `proposition_refs: []`.

**Finding 4 - Context retrieval and KG filtering are evidence-shaping operations.** Jiang2024 and Gong2024 show that derived KG views, task-conditioned retrieval, correlation filtering, spatio-temporal alignment, and missingness policies shape what the agent can know. The operation record must reference context sources and retrieved/derived views. If those views are incomplete or unvalidated, the operation contributes H03 reason codes even when the downstream artifact is otherwise well formed.

**Finding 5 - Agent evaluation needs competency-typed semantics.** Yu2026's SciCUEval competencies map directly to Science's extraction risks: relevant information identification, information-absence detection, multi-source integration, and context-aware inference. Si2025 adds that bias/safety evaluation should distinguish no evidence of failure from evidence of absence. Agent evaluations therefore need their own extension rather than being flattened into `validation_status`.

**Finding 6 - The t034 causal-prior-bundle interlock is the load-bearing co-load case.** t034 deliberately leaves LLM prompt/model/tool-chain provenance out of `causal-prior-bundle` and expects `[t037]` to supply `agent-tool-operation`. This design must make that co-load precise: causal prior fields carry the causal role and constraint semantics; operation fields carry model, prompt/workflow, context, tool chain, execution trace, safety, and evaluation state.

---

## Artifact and entity carve-up

This task uses a two-layer split:

1. **Operation registry entities** describe durable capabilities, roles, policies, contracts, and protocols.
2. **Operation payloads** describe a particular run or evaluation event.

| Candidate | Disposition | Rationale |
|---|---|---|
| `agent` | First-class entity | Reused across many operations; needs evaluation history and dependence modeling. |
| `agent_role` | First-class enum/entity | A stable role taxonomy is required so output semantics do not depend on prose. |
| `tool` | First-class entity | Durable external or internal executable capability. |
| `skill` | First-class entity, subtype of operator capability | Skills are graph-governed workflows; they may call tools/commands but are not payloads. |
| `command` | First-class entity, subtype of operator capability | Commands expose reproducible CLI/API surfaces with validation commands. |
| `tool_chain` | First-class entity | A reusable plan/template of ordered or DAG-shaped steps. |
| `execution_trace` | First-class run artifact referenced by payloads | Potentially large; holds observed step I/O, logs, timings, exits, and hashes. |
| `safety_policy` | First-class entity | Reused across tools/chains; versioned independently. |
| `validation_protocol` | First-class entity | Reused tests/checks/evaluations; may be run many times. |
| `operation_record` | Payload (`agent-tool-operation`) | One execution event with core provenance and extension-specific state. |

**Why `tool_chain` is not the payload.** The chain is the planned workflow template. The operation record is the observed event. Re-running the same chain with a different model, prompt, context, graph version, or safety policy produces a new operation record and execution trace.

**Why `execution_trace` is not embedded.** Traces may include long logs, full tool I/O, retrieved context snippets, and artifacts. The payload records a `trace_ref` and compact trace summary. Detailed trace content lives in a trace artifact path or database row.

---

## Registry schemas

Registry schemas are graph entities rather than t022 payload extensions. They can be represented in YAML, JSON, or graph-native rows; the field names below define the contract.

**Authoring rule - provisional registry refs (P-pilot-1).** Pilot and design extraction artifacts may use provisional refs for chains, policies, protocols, execution traces, and KG views when the source summary supports the entity's role but no production registry row exists yet. Production validation must resolve those refs before enforcing registry-dependent biconditionals such as `tool-chain-unvalidated` and `safety-check-missing`; unresolved provisional refs are a draft-state authoring finding, not a silent fallback.

### `agent`

```yaml
entity/agent:
  agent_id: ref
  agent_kind: enum              # human / llm / pipeline / hybrid / service
  display_name: str
  owner_ref: ref [opt]
  model_family: str [opt]       # for LLM/service agents
  default_role_refs: [ref]
  source_behavior_profile_ref: ref [opt]
  evaluation_protocol_refs: [ref]
  lifecycle_status: enum        # active / deprecated / retired / experimental
```

**Authoring rule.** A model-version change that can affect outputs is recorded in operation payloads (`agent_model_version`), not by creating a new `agent` unless the agent identity/workflow boundary changes.

### `agent_role`

Strict enum for operation semantics:

| Role | Means |
|---|---|
| `paper-reader` | Reads source documents and extracts summary material. |
| `field-extractor` | Populates structured fields from source context. |
| `synthesis-author` | Aggregates multiple sources into synthesis artifacts. |
| `hypothesis-generator` | Proposes candidate hypotheses or entities. |
| `causal-prior-elicitor` | Produces causal priors/constraints for `[t034]`. |
| `tool-planner` | Selects tools and constructs a chain. |
| `tool-executor` | Executes an already-selected tool or chain. |
| `pipeline-runner` | Runs a multi-step analysis or workflow where the pipeline, not one tool call, is the meaningful operation. |
| `graph-editor` | Creates, edits, merges, or deprecates graph entities/edges. |
| `validator` | Runs tests, schema checks, audits, or benchmark evaluations. |
| `critic` | Reviews artifacts for flaws without directly editing them. |
| `safety-reviewer` | Applies a safety policy to a plan, tool call, or output. |
| `task-editor` | Creates or edits task/question/project-management artifacts. |

**Authoring rule.** A single operation record has one primary `agent_role`. If one run contains planning, execution, and summarization with meaningfully different agents or models, split into multiple operation records linked by `input_artifact_refs`.

**Authoring rule - absence-sensitive roles.** The roles that require information-absence detection are exactly: `paper-reader`, `field-extractor`, `synthesis-author`, `hypothesis-generator`, `causal-prior-elicitor`, `validator`, and `critic`. An operation with one of these roles and `abstention_supported: false` declares `information-absence-undetected`. Other roles do not declare that code solely because abstention is unsupported.

### `tool`, `skill`, and `command`

These share the same capability contract. `operator_kind` distinguishes them.

```yaml
entity/operator-capability:
  capability_id: ref
  operator_kind: enum              # tool / skill / command
  name: str
  capability_description: str
  owner_ref: ref [opt]
  version: str [opt]
  expected_input_contract_ref: ref
  expected_output_contract_ref: ref
  dependency_refs: [ref]           # tools, skills, commands, datasets, services
  safety_policy_refs: [ref]
  validation_command_refs: [ref]   # concrete commands or protocols
  side_effect_profile: enum        # read-only / writes-workspace / external-call / graph-mutation / destructive
  determinism_profile: enum        # deterministic / stochastic / model-dependent / environment-dependent
  lifecycle_status: enum           # active / experimental / deprecated / retired
```

**Validation rule.** Any capability whose `side_effect_profile` is `graph-mutation` or `destructive` must list at least one `safety_policy_ref` and one `validation_command_ref`.

### `io_contract`

```yaml
entity/io-contract:
  contract_id: ref
  input_schema_ref: ref [opt]
  output_schema_ref: ref [opt]
  required_context_kinds: [enum]   # paper / graph / dataset / task / code / web / none
  produced_artifact_kinds: [enum]  # summary / payload / graph-update / task-edit / trace / report
  allowed_partial_outputs: bool
  abstention_supported: bool
  failure_modes: [enum]
```

**Authoring rule.** `abstention_supported: false` is allowed, but any operation that needs information-absence detection should use a contract with abstention support or declare `information-absence-undetected`.

### `tool_chain`

```yaml
entity/tool-chain:
  chain_id: ref
  purpose: str
  chain_kind: enum                 # linear / dag / replanning-loop / human-in-loop
  step_set:
    - step_id: str
      capability_ref: ref
      agent_role: enum
      input_contract_ref: ref
      output_contract_ref: ref
      depends_on: [str]
      safety_policy_refs: [ref]
      validation_protocol_refs: [ref]
  expected_terminal_artifact_kinds: [enum]
  replanning_policy: enum [opt]    # none / on-failure / on-low-confidence / iterative
```

**Validation rule.** Every `depends_on` value must resolve to another step in the same chain. Cycles are forbidden unless `chain_kind: replanning-loop`, in which case the loop boundary and stop condition must be explicit.

**Authoring rule - direct capability calls.** Any operation that invokes a `tool`, `skill`, or `command` must reference a `tool_chain_ref`. A direct single-capability invocation is represented as a one-step `tool_chain`, not as an operation with no chain. `tool_chain_ref` may be absent only for operations that do not invoke an executable capability, such as a human critique or a dataset-only evaluation record.

### `safety_policy`

```yaml
entity/safety-policy:
  policy_id: ref
  policy_scope: [enum]             # tool-use / web-retrieval / code-execution / graph-edit / scientific-domain / dual-use
  risk_class: enum                 # low / medium / high / prohibited
  required_checks: [enum]
  prohibited_actions: [str]
  escalation_required: bool
  policy_version: str
```

**Validation rule.** An operation whose chain or capability references a safety policy must record `safety_check_status` in the operation payload.

### `validation_protocol`

```yaml
entity/validation-protocol:
  protocol_id: ref
  protocol_kind: enum              # schema-check / unit-test / integration-test / audit-rubric / benchmark / bias-test / safety-check / replay-check
  evaluation_competency: enum [opt]
  command_ref: ref [opt]
  acceptance_criteria: str
  output_contract_ref: ref [opt]
  evidence_of_absence_supported: bool
```

**Authoring rule.** Bias and absence-detection protocols should set `evidence_of_absence_supported: true` only when the protocol can distinguish "no evidence of failure" from "evidence of no failure" (Si2025-style Bayes-factor semantics).

---

## Payload extensions

### `agent-tool-operation`

A single operation by an agent, tool chain, command, skill, or hybrid workflow.

```yaml
extension/agent-tool-operation:
  target_artifact_refs: [ref]          # artifacts created/edited/evaluated by the operation
  agent_role: enum                     # from agent_role taxonomy
  agent_model_version: str [opt]       # model, service, script, or human workflow version
  prompt_or_workflow_ref: ref [opt]
  tool_chain_ref: ref [opt]
  tool_io_contract_ref: ref [opt]
  safety_policy_ref: ref [opt]
  execution_trace_ref: ref [opt]
  context_ref_set: [ref]               # paper refs, kg-view refs, search contexts, dataset refs
  context_selection_method: enum       # explicit-user-provided / graph-query / rag-retrieval / kg-filter / web-search / file-search / none
  context_completeness: enum           # complete-for-task / partial / unknown / not-applicable
  safety_check_status: enum            # passed / failed / skipped / not-applicable / unknown
  validation_protocol_refs: [ref]
  validation_status_detail: enum       # validated / partially-validated / unvalidated / failed / not-applicable
  abstention_supported: bool
  abstention_reason: enum [opt]        # insufficient-context / unsafe-action / contract-mismatch / validation-failed / out-of-scope
```

**Authoring rule - operation method refs (P-pilot-2).** For `agent-tool-operation`, `core.method_ref` should point to the concrete project workflow, command, skill, protocol, or run method that governed the operation. A method paper is a valid `method_ref` only when the operation directly applies that paper's method as the operative protocol. Summary-only pilots may leave `method_ref` absent rather than fabricating a workflow ref from a general architecture paper.

**Co-required extensions:** none. Optional co-loads:

- `agent-evaluation` when the operation itself is an agent reliability or bias evaluation.
- `[t034]` `causal-prior-bundle` when the operation produced an LLM prior/constraint bundle.
- `[t038]` graph-evolution extension when `target_artifact_refs` include graph mutations or versioned KG views.

**Validation rules.** `validation_role` permitted values:

- `record-only` - always permitted and the default.
- `quality-record-only` - permitted iff the operation evaluates another artifact and `validation_protocol_refs` is non-empty.
- `prioritize-attention` - permitted iff the operation creates candidate artifacts and `validation_status_detail != failed`.
- `gate-update` - permitted iff `agent_role` is `validator` or `safety-reviewer` and `validation_status_detail: failed` or `safety_check_status: failed`.
- `strengthen-belief` - forbidden directly. Operation records may not strengthen scientific propositions.

**Uncertainty-summary contract.** Render as `"<agent_role>, <tool_chain_ref or prompt/workflow>, validation=<validation_status_detail>, safety=<safety_check_status>"`.

**Registry-resolved validation view.** The reason-code rules below are evaluated against a materialized operation view that resolves `tool_chain_ref`, the chain's step capabilities, each capability's validation protocols, and applicable safety policies. Payload-local validators may check field shape, but biconditional reason-code validation requires this registry-resolved view.

**Reason-code contributions.** Declares:

- `agent-source-unvalidated` when `agent_model_version` is present and `validation_status_detail: unvalidated`.
- `tool-chain-unvalidated` when `tool_chain_ref` is present and no referenced validation protocol has passed.
- `safety-check-missing` when any referenced capability/chain has a safety policy but `safety_check_status` is `skipped` or `unknown`. If the registry-resolved view has an applicable safety policy, `safety_check_status: not-applicable` is invalid rather than code-free (P-proto-1).
- `context-retrieval-uncertain` when `context_selection_method in {rag-retrieval, kg-filter, web-search, file-search}` and `context_completeness != complete-for-task`. Partial or unknown context from `explicit-user-provided` does not declare this code solely because it is incomplete; use a more specific downstream finding if explicit context omission matters (P-proto-2).
- `information-absence-undetected` when `abstention_supported: false` and `agent_role` is in the absence-sensitive role set (`paper-reader`, `field-extractor`, `synthesis-author`, `hypothesis-generator`, `causal-prior-elicitor`, `validator`, `critic`).

**Propagation policy.** `propagate-blocking`. Blocking codes from operation records propagate to payloads that list the operation in `pipeline_provenance_ref` or `input_artifact_refs`. This is the t037 contribution to H03: downstream evidence cannot silently hide unvalidated agent/tool/context state.

**Propagation scale rule.** Split multi-step workflows produce multiple operation records when the steps have different roles, agents, or validation semantics. Downstream consumers inherit the union of blocking codes from the referenced parent/child operation chain. Validators should de-duplicate repeated codes and preserve origin refs so a five-step workflow does not create five visually indistinguishable copies of the same reason.

### `agent-evaluation`

Evaluation of an agent, model/workflow, prompt, tool chain, or operation family.

```yaml
extension/agent-evaluation:
  evaluated_agent_ref: ref
  evaluated_role: enum
  evaluated_model_version: str [opt]
  evaluated_tool_chain_ref: ref [opt]
  evaluation_protocol_ref: ref
  evaluation_competency: enum       # relevant-info-identification / information-absence-detection / multi-source-integration / context-aware-inference / tool-selection / tool-execution / bias-detection / safety-compliance
  evaluation_dataset_ref: ref [opt]
  sample_size: int [opt]
  metric_set: dict [opt]
  bayes_factor_evidence:
    hypothesis_ref: ref [opt]
    null_baseline: str [opt]
    bf10: float [opt]
    interpretation: enum [opt]      # evidence-for-risk / evidence-against-risk / inconclusive / not-applicable
  result: enum                       # pass / fail / partial / inconclusive
  evaluated_operation_refs: [ref]
```

**Co-required extensions:** optional `statistical-uncertainty` when numeric uncertainty is available.

**Validation rules.** `validation_role` permitted values:

- `quality-record-only` - always permitted.
- `record-only` - always permitted.
- `gate-update` - permitted iff `result: fail` and the evaluation protocol is assigned as a gate for the evaluated agent/chain.
- `prioritize-attention` - permitted iff `result in {fail, partial, inconclusive}`.
- `strengthen-belief` - forbidden directly. An agent evaluation changes source reliability or operation eligibility, not a scientific proposition.

**Uncertainty-summary contract.** Render as `"<evaluation_competency>: <result>, n=<sample_size>, BF10=<bf10 if present>"`.

**Reason-code contributions.** Declares:

- `agent-bias-risk` when `evaluation_competency: bias-detection` and `result in {fail, partial}` or `bayes_factor_evidence.interpretation: evidence-for-risk`. Bayes-factor `evidence-for-risk` is independently sufficient even when a benchmark's coarse `result` label is `inconclusive`; result labels do not override positive Bayes-factor risk evidence (P-pilot-4).
- `information-absence-undetected` when `evaluation_competency: information-absence-detection` and `result in {fail, partial}`.

`agent-evaluation` does not declare `agent-source-unvalidated`; that code is local to `agent-tool-operation`. A downstream operation that uses an inconclusive or stale evaluation remains `validation_status_detail: unvalidated` and declares `agent-source-unvalidated` on the operation record. If pilot extraction shows that inconclusive/stale evaluations need their own H03 signal, add a separate evaluation-specific code rather than overloading `agent-source-unvalidated`.

**Propagation policy.** `propagate-blocking` only when the evaluation is referenced by an operation as a gating protocol. Otherwise evaluation codes remain visible through origin-chain inspection but do not enter downstream `effective_codes`.

**Authoring rule - evaluated operation coverage.** `evaluated_operation_refs: []` means the evaluation is dataset/protocol-level coverage for an agent, role, model version, or chain, not a retrospective audit of specific runs. To gate or retire codes for already-authored operations, list those operation refs explicitly or attach the evaluation protocol to the registry entry used by those operations.

**Authoring rule - evaluation scope (P-pilot-3).** Dataset/protocol-level evaluations may use class-level agent refs, role refs, or model-family refs when the source does not evaluate a concrete Science agent version. Such records describe coverage only. They do not retire `agent-source-unvalidated`, `tool-chain-unvalidated`, `information-absence-undetected`, or `agent-bias-risk` for concrete operation records unless those operations are explicitly listed in `evaluated_operation_refs` or the evaluation is attached as a gating protocol in registry state.

---

## Operation-record mapping to Science artifacts

Operation records attach to project artifacts through `target_artifact_refs`, `pipeline_provenance_ref`, or downstream `input_artifact_refs`.

| Produced/edited artifact | Operation record use | Notes |
|---|---|---|
| Evidence payload | Payload `core.pipeline_provenance_ref` points to the operation record. Blocking t037 effective codes propagate into the payload. |
| Paper summary | Operation target is `paper-summary:<id>` or the paper note path; role usually `paper-reader` or `field-extractor`. |
| Batch synthesis | Operation target is `synthesis:<id>`; role usually `synthesis-author`; context refs include all source paper summaries. |
| Causal prior bundle (`[t034]`) | Payload co-loads `causal-prior-bundle` and `agent-tool-operation`; causal fields live in t034, operator fields here. |
| Graph update | Operation target is a graph-update event or graph version owned by `[t038]`; role usually `graph-editor` or `validator`. |
| Task edit | Operation target is `task:<id>`; role `task-editor`; validation may be `record-only` unless task edits are gated by project checks. |
| Validation/audit report | Operation target is the audited artifact; role `validator` or `critic`; may co-load `agent-evaluation` or another quality extension. |

**Authoring rule.** If an operation produces several semantically different target artifacts in one run (for example: paper summary plus graph updates plus task edits), either split the operation into multiple records or use one parent operation with child operations for each artifact class. Do not let a single record obscure which target inherited which risk.

**Authoring rule - project-local traces (P-pilot-5).** After-the-fact project-local operation records require a trace/provenance sidecar or artifact frontmatter sufficient to resolve the agent/workflow/chain boundary, model or workflow version when applicable, target artifact, context, validation state, and safety state. If those fields are absent, record the operation attempt as unauthorable in a pilot or audit artifact rather than inventing refs.

---

## H03 reason-code additions

Codes to mirror in `[t025]` with Batch 5 provenance.

| Code | Owner extension | Blocking? | Declared when |
|---|---|---|---|
| `agent-source-unvalidated` | `agent-tool-operation` | blocking | `agent_model_version` is present and `validation_status_detail: unvalidated` on the operation record. |
| `tool-chain-unvalidated` | `agent-tool-operation` | blocking | Tool chain exists but has no passed validation protocol for this use. |
| `safety-check-missing` | `agent-tool-operation` | blocking | Applicable safety policy exists but check was skipped/unknown. |
| `context-retrieval-uncertain` | `agent-tool-operation` | non-blocking | Retrieval/filter/search context is partial or completeness unknown. |
| `information-absence-undetected` | `agent-tool-operation`, `agent-evaluation` | blocking | Operation/evaluation cannot detect absent information where the role requires it. |
| `agent-bias-risk` | `agent-evaluation` | non-blocking by default | Bias evaluation indicates risk, partial failure, or Bayes-factor evidence for risk. |

**Biconditional authoring convention.** As in `[t034]` v1.3, conditional rules of the form "declared when X" are biconditional: the code must appear iff X holds. Over-declaration is a validation error because reason codes encode falsifiable claims about operation state.

**Auto-injection convention.** This v1.3 draft does not auto-inject any t037 code by extension presence alone. All six codes are conditional. A future audit may recommend auto-injecting `agent-source-unvalidated` for specific experimental agent classes, but that would require a registry-level lifecycle rule not present here.

**Registry-resolved rule convention.** `tool-chain-unvalidated` and `safety-check-missing` are evaluated after resolving the operation's `tool_chain_ref` to its steps, capability refs, validation protocols, and safety policies. The raw payload alone is insufficient for those two biconditionals. The first standalone validator prototype materializes this as a compact `ResolvedOperationView` fixture and validates `ato-1` through `ato-10` with 20 passing cases (P-proto-3).

## Pilot-driven authoring conventions

**Provisional refs are draft-only (P-pilot-1).** Pilot extraction may use provisional registry refs where source summaries support the entity's function, but production validation requires registry resolution before registry-dependent reason-code rules pass.

**Operation methods prefer project workflows (P-pilot-2).** Operation records use concrete project workflows, skills, commands, or protocols as `method_ref`; a paper ref belongs there only when the operation directly applies that paper's method.

**Evaluation scope does not imply operation retirement (P-pilot-3).** Dataset/protocol-level `agent-evaluation` records with empty `evaluated_operation_refs` do not retire codes on concrete operation records unless attached through explicit operation refs or registry gating state.

**Bayes-factor risk evidence wins over coarse labels (P-pilot-4).** `bayes_factor_evidence.interpretation: evidence-for-risk` declares `agent-bias-risk` even when the evaluation's coarse `result` is not `fail` or `partial`.

**Project-local operations need trace state (P-pilot-5).** Author after-the-fact operation records only when artifact frontmatter or trace sidecars expose enough agent, workflow, chain, context, safety, and validation state to make the record falsifiable.

**Safety not-applicable is registry-dependent (P-proto-1).** `safety_check_status: not-applicable` is valid only when the registry-resolved operation view has no applicable safety policy. If a policy applies, authors must record `passed`, `failed`, `skipped`, or `unknown`.

**Context uncertainty is retrieval-scoped (P-proto-2).** Do not declare `context-retrieval-uncertain` for partial explicit-user-provided context unless another extension or downstream audit defines a specific omission code.

---

## Interlock with `[t034]` causal-prior-bundle

The canonical co-load pattern:

**Authoring rule - context refs vs input refs.** `context_ref_set` records what the agent saw or retrieved while performing the operation. `core.input_artifact_refs` records upstream artifacts that are semantic derivation inputs to the payload itself and whose effective codes should propagate through ordinary payload input semantics. A source can appear in both only when it is both observed context and a formal derivation input. In the example below, the papers and KG view are operation context; the prior bundle has no upstream evidence payload input.

```yaml
core:
  payload_id: ev-2026-vaccine-llm-ancestral-prior
  artifact_type: causal-prior-bundle
  extensions: [causal-prior-bundle, agent-tool-operation]
  input_artifact_refs: []
  agent_ref: agent:llm-causal-prior-agent
  pipeline_provenance_ref: op-2026-vaccine-llm-prior-run
  proposition_refs: []
  comparison_target: n-a
  support_direction: methodological-input
  validation_role: record-only
  validation_status: pending
  reason_codes:
    - weak-prior-only
    - llm-prior-unvalidated
    - agent-source-unvalidated
    - tool-chain-unvalidated
    - context-retrieval-uncertain

extension/causal-prior-bundle:
  prior_role: llm-prior
  prior_format: ancestral-constraint-list
  constraint_type: ancestral
  prior_strength: 0.6
  variable_set: [var:vaccination, var:severe-illness, var:age]
  prior_provenance: op-2026-vaccine-llm-prior-run
  prior_validation_status: unvalidated

extension/agent-tool-operation:
  target_artifact_refs: [ev-2026-vaccine-llm-ancestral-prior]
  agent_role: causal-prior-elicitor
  agent_model_version: claude-opus-4-7-1m
  prompt_or_workflow_ref: workflow:ancestral-elicitation-v2
  tool_chain_ref: chain:retrieve-context-then-elicit-prior
  tool_io_contract_ref: contract:causal-prior-json-v1
  safety_policy_ref: policy:llm-causal-prior-record-only-v1
  execution_trace_ref: trace:vaccine-llm-prior-2026-05-07
  context_ref_set: [paper:Ban2023, paper:Wan2025, kg-view:vaccine-context-v3]
  context_selection_method: kg-filter
  context_completeness: partial
  safety_check_status: passed
  validation_protocol_refs: []
  validation_status_detail: unvalidated
  abstention_supported: true
```

**Division of responsibility.**

- t034 owns `prior_role`, `constraint_type`, `prior_strength`, variable scope, and whether the prior can only prioritize attention.
- t037 owns model version, prompt/workflow, context retrieval, tool chain, execution trace, safety state, and agent evaluation.
- H03 effective codes are the union of both extension contributions. In the example, t034 contributes `weak-prior-only` and `llm-prior-unvalidated`; t037 contributes `agent-source-unvalidated`, `tool-chain-unvalidated`, and `context-retrieval-uncertain` under the conditional rules.

**Validation interlock.** A downstream `causal-discovery-run` consuming this bundle inherits blocking t034 codes and blocking t037 codes. It may still run and prioritize attention, but it cannot create a belief-strengthening causal effect without downstream validation that retires those codes.

---

## Worked examples

### Example T37-1 - SciToolAgent-style operation record

```yaml
core:
  payload_id: op-2026-scitool-dock-run-4521
  artifact_type: agent-tool-operation
  extensions: [agent-tool-operation]
  created_at: 2026-05-07T10:00:00Z
  input_artifact_refs: [kg-view:protein-target-context-v8]
  method_ref: workflow:hypothesis-from-target-v3
  agent_ref: agent:scitool-runner
  pipeline_provenance_ref: pipeline:scitool-orchestrator-v2
  proposition_refs: []
  comparison_target: n-a
  support_direction: operation-record
  validation_role: record-only
  validation_status: pending
  uncertainty_summary: "hypothesis-generator, chain:kg-retrieve-then-dock, validation=unvalidated, safety=passed"
  reason_codes: [agent-source-unvalidated, tool-chain-unvalidated]

extension/agent-tool-operation:
  target_artifact_refs: [hypothesis:novel-egfr-binding-pocket]
  agent_role: hypothesis-generator
  agent_model_version: scitool-v0.4
  prompt_or_workflow_ref: workflow:hypothesis-from-target-v3
  tool_chain_ref: chain:kg-retrieve-then-dock
  tool_io_contract_ref: contract:autodock-vina-v1
  safety_policy_ref: policy:no-uncontrolled-release
  execution_trace_ref: trace:scitool-run-4521
  context_ref_set: [kg-view:protein-target-context-v8]
  context_selection_method: kg-filter
  context_completeness: complete-for-task
  safety_check_status: passed
  validation_protocol_refs: []
  validation_status_detail: unvalidated
  abstention_supported: false
```

This operation proposes a hypothesis. It does not strengthen belief in the hypothesis; a separate evidence payload must evaluate the candidate. `paper:Ding2025` grounds the design pattern for this example, but the operation's `method_ref` is the concrete workflow used by this run. Use a method-defining paper in `method_ref` only when the operation is directly applying that paper's method as the operative protocol.

### Example T37-2 - Paper-summary extraction with missingness risk

```yaml
core:
  payload_id: op-2026-yu2026-summary-extraction
  artifact_type: agent-tool-operation
  extensions: [agent-tool-operation]
  created_at: 2026-05-07T10:15:00Z
  input_artifact_refs: [paper:Yu2026]
  method_ref: workflow:science-research-papers-v1
  agent_ref: agent:llm-paper-reader
  pipeline_provenance_ref: trace:yu2026-summary-run
  proposition_refs: []
  comparison_target: n-a
  support_direction: operation-record
  validation_role: record-only
  validation_status: pending
  reason_codes:
    - agent-source-unvalidated
    - tool-chain-unvalidated
    - information-absence-undetected

extension/agent-tool-operation:
  target_artifact_refs: [paper-summary:Yu2026]
  agent_role: paper-reader
  agent_model_version: claude-sonnet-4-5
  prompt_or_workflow_ref: workflow:paper-summary-v2
  tool_chain_ref: chain:pdf-read-summarize
  tool_io_contract_ref: contract:paper-summary-frontmatter-v1
  safety_policy_ref: ~
  execution_trace_ref: trace:yu2026-summary-run
  context_ref_set: [paper:Yu2026]
  context_selection_method: explicit-user-provided
  context_completeness: unknown
  safety_check_status: not-applicable
  validation_protocol_refs: []
  validation_status_detail: unvalidated
  abstention_supported: false
```

The reason code is not a claim that the summary is wrong. It says the operation was not capable of detecting all absent information required by a high-stakes extraction workflow.

When `safety_policy_ref: ~`, `safety_check_status` must be `not-applicable` unless the registry-resolved chain adds an applicable safety policy. When `validation_protocol_refs: []`, `validation_status_detail` must be `unvalidated`. These are normalized state fields; validators check the implication so authors do not use `unknown` as a silent fallback.

### Example T37-3 - Agent evaluation for context understanding

```yaml
core:
  payload_id: eval-2026-paper-reader-absence-detection
  artifact_type: agent-evaluation
  extensions: [agent-evaluation]
  created_at: 2026-05-07T10:30:00Z
  input_artifact_refs: [dataset:science-paper-summary-eval-v1]
  method_ref: paper:Yu2026
  agent_ref: agent:evaluation-runner
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: validated
  uncertainty_summary: "information-absence-detection: partial, n=40"
  reason_codes: [information-absence-undetected]

extension/agent-evaluation:
  evaluated_agent_ref: agent:llm-paper-reader
  evaluated_role: paper-reader
  evaluated_model_version: claude-sonnet-4-5
  evaluated_tool_chain_ref: chain:pdf-read-summarize
  evaluation_protocol_ref: protocol:paper-summary-absence-detection-v1
  evaluation_competency: information-absence-detection
  evaluation_dataset_ref: dataset:science-paper-summary-eval-v1
  sample_size: 40
  metric_set: {missingness_recall: 0.72, false_abstention_rate: 0.11}
  bayes_factor_evidence: {interpretation: not-applicable}
  result: partial
  evaluated_operation_refs: []
```

This evaluation can gate future paper-reader operations if the protocol is assigned as a required gate for that role/model.

### Example T37-4 - Bias evaluation with Bayes-factor semantics

```yaml
core:
  payload_id: eval-2026-causal-prior-agent-bias
  artifact_type: agent-evaluation
  extensions: [agent-evaluation]
  created_at: 2026-05-07T10:45:00Z
  input_artifact_refs: [dataset:causal-prior-bias-prompts-v1]
  method_ref: paper:Si2025
  agent_ref: agent:evaluation-runner
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: validated
  uncertainty_summary: "bias-detection: inconclusive, n=120, BF10=1.4"
  reason_codes: []

extension/agent-evaluation:
  evaluated_agent_ref: agent:llm-causal-prior-agent
  evaluated_role: causal-prior-elicitor
  evaluated_model_version: claude-opus-4-7-1m
  evaluated_tool_chain_ref: chain:retrieve-context-then-elicit-prior
  evaluation_protocol_ref: protocol:causal-prior-bias-bf-v1
  evaluation_competency: bias-detection
  evaluation_dataset_ref: dataset:causal-prior-bias-prompts-v1
  sample_size: 120
  metric_set: {stereotyped_choice_rate: 0.54}
  bayes_factor_evidence:
    hypothesis_ref: hypothesis:agent-causal-prior-bias
    null_baseline: "pi = 0.5"
    bf10: 1.4
    interpretation: inconclusive
  result: inconclusive
  evaluated_operation_refs: []
```

No `agent-bias-risk` is declared because the Bayes-factor interpretation is inconclusive. This distinguishes "risk shown" from "not enough evidence either way."

---

## Validation machinery candidates

The v1.3 design is intentionally written so the first validator slices can mirror t034.

The standalone prototype at `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py` validates `ato-1` through `ato-10` and reports `20/20 tests passed`, including pilot-adapted Ding and paper-reader fixtures (P-proto-3).

**Slice 1 - `agent-tool-operation` structural rules.**

- `agent_role` is in the strict role enum.
- `validation_role: strengthen-belief` is rejected for operation records.
- `safety_check_status` is required whenever `safety_policy_ref` is present.
- `safety_check_status: not-applicable` is rejected whenever the registry-resolved operation view has an applicable safety policy.
- `target_artifact_refs` is non-empty unless `abstention_reason` is present.
- project-local operation records are rejected or deferred when no trace/provenance sidecar can resolve required operation state.

**Slice 2 - reason-code biconditional rules.**

- `agent-source-unvalidated` iff `agent_model_version` is present and `validation_status_detail: unvalidated`.
- `tool-chain-unvalidated` iff the registry-resolved `tool_chain_ref` has no passed validation protocol for this use.
- `safety-check-missing` iff the registry-resolved operation view has an applicable safety policy and safety check is skipped/unknown.
- `context-retrieval-uncertain` iff retrieval/filter/search context is not complete-for-task.
- explicit-user-provided partial context does not declare `context-retrieval-uncertain` by itself.
- `information-absence-undetected` iff abstention is unsupported for the explicit absence-sensitive role set.

**Slice 3 - propagation into a downstream payload.**

Smallest test: an `agent-tool-operation` with blocking `agent-source-unvalidated` is referenced by a paper-extracted evidence payload via `pipeline_provenance_ref`. The downstream payload's `effective_codes` includes the operation code and rejects `validation_role: strengthen-belief`.

---

## Alignment notes

**With `[t022]` v2.3.** This task uses the t022 core exactly as intended: operation-specific fields stay out of core; `support_direction: operation-record` and `validation_role: record-only` are the default for operations; `target_artifact_refs` lives in the extension, not core.

This design depends on these t022 v2.3 enum values already being present: `support_direction: operation-record`, `support_direction: methodological-input`, `support_direction: quality-record`, `validation_role: record-only`, and `validation_role: quality-record-only`. If any are absent in a future t022 revision, the coordination fix belongs in t022, not in this extension.

**With `[t033]` / Q07.** Agents remain fallible sources. This task adds the operator side: role, model version, workflow, context, tool chain, safety, trace, and evaluation. Source-reliability updates should be driven by `agent-evaluation` payloads rather than ad hoc confidence.

**With `[t034]`.** `causal-prior-bundle` co-loads `agent-tool-operation` for LLM prior elicitation. t034 owns causal semantics; t037 owns operator provenance. Blocking reason codes from both extensions propagate to downstream causal payloads.

**With `[t038]`.** Derived KG views, graph update events, graph versions, rollback/replay, and stale-version codes belong to t038. This task records operation references to those objects but does not define their internal schema.

**With `[t025]`.** Six new H03 reason codes need registry entries with blocking flags as listed above. This task adopts t034's biconditional reason-code convention.

---

## Open questions

1. **Should `execution_trace` be a graph entity or opaque artifact path?** Lean: entity with optional external artifact path. Validators need refs and hashes; humans need logs only on demand.
2. **Should `agent-source-unvalidated` be auto-injected for experimental agents?** Lean: no for v1.1. Make it conditional from operation state; revisit after pilot extraction.
3. **How much registry validation should happen before payload validation?** Tool-chain dependency closure, policy applicability, and validation-protocol resolution are registry checks. Operation payload validation should assume registry lookups are available.
4. **How should human operations be represented?** Same operation schema, with `agent_kind: human` and `agent_model_version` optional. Human review does not automatically mean validated.
5. **What retires t037 blocking codes?** Candidate rules: passing `agent-evaluation` retires `agent-source-unvalidated`; passing chain replay retires `tool-chain-unvalidated`; passed policy check retires `safety-check-missing`; an absence-detection protocol with passing result retires `information-absence-undetected`.

---

## Audit prompts

For the next audit-style review of this v1.3 draft, the highest-risk points:

- **Entity vs payload boundary.** Are `tool_chain` and `execution_trace` correctly kept out of the payload body, or does authoring become too ref-heavy?
- **Role taxonomy completeness.** Do the thirteen roles cover actual Science workflows without forcing vague roles?
- **Reason-code decidability.** Can all six conditional codes be enforced from the operation payload plus the registry-resolved operation view?
- **Propagation scope.** Should blocking t037 codes propagate through `pipeline_provenance_ref` as well as `input_artifact_refs`, or only through explicit input refs?
- **t034 co-load fit.** Does the `causal-prior-bundle + agent-tool-operation` example give t034 all operator provenance it needs without duplicating causal fields?

---

## Next steps

1. **Pilot extraction** on 2-3 Batch 5 papers/operations: Ding2025 (tool-chain operation), Yu2026 (agent evaluation), and one actual Science paper-summary or synthesis run (project-local operation record).
2. **Patch to v1.2** from pilot findings. Expect pressure on required fields, abstention support, and context completeness.
3. **Prototype validator slice** for `agent-tool-operation` structural plus reason-code biconditional rules against the registry-resolved operation view.
4. **Patch to v1.3** after prototype findings, especially propagation via `pipeline_provenance_ref` and retirement of operation-level blocking codes.

The load-bearing claims in this v1.3 draft are: registry entities for durable capabilities and policies; operation records as payloads but not evidence; direct prohibition on operation-level `strengthen-belief`; six H03 operation reason codes; and the `[t034]` causal-prior co-load pattern.

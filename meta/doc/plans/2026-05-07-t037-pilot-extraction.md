# t037 Pilot Extraction (3 operation/evaluation cases, v1.1)

> **Status:** Pilot extraction (2026-05-07). Empirical pressure-test of `[t037]` v1.1 (`meta/doc/plans/2026-05-07-t037-agent-tool-operations-extension-design.md`).
>
> **Goal:** find gaps between the v1.1 agent/tool operation schema and what authors can actually populate from current project content. Surfaces ref-heaviness, registry-state ambiguity, reason-code decidability gaps, and worked-example drift.

**Sources:**
- `meta/doc/background/papers/Ding2025.md`
- `meta/doc/background/papers/Yu2026.md`
- `meta/doc/background/papers/Si2025.md`
- one project-local operation chosen from existing Science paper-summary or synthesis workflow traces, if enough context exists in the repo

**Method:** author the payload(s) that the source content actually supports. Use only the project's existing summaries and files. Score extraction fields with the same scale used in t034:

| Score | Meaning |
|---|---|
| 2 | Stated explicitly or mechanically determined by the schema. |
| 1 | Clearly inferable from the source. |
| 0 | Ambiguous; multiple plausible values. |
| x | Not present in source and not authoring-stage; would require external lookup or a real run trace. |
| A | Authoring/mechanical field. |

## Extraction 1 - Ding2025 -> agent-tool-operation

Ding2025 describes SciToolAgent as an LLM-powered scientific agent that uses SciToolKG for tool selection, tool orchestration, and safety checking. The summary supports an operation-record sketch for a SciToolAgent-style tool-chain run, but it does not describe one concrete project run or registry row. The extraction therefore treats the chain, trace, policy, and KG-view refs as author-created refs.

```yaml
core:
  payload_id: op-2026-ding-scitoolagent-tool-plan
  artifact_type: agent-tool-operation
  extensions: [agent-tool-operation]
  created_at: 2026-05-07T00:00:00-04:00
  input_artifact_refs: [kg-view:scitoolkg-task-context]
  method_ref: ~
  agent_ref: agent:scitoolagent
  pipeline_provenance_ref: trace:ding-scitoolagent-tool-plan
  proposition_refs: []
  comparison_target: n-a
  support_direction: operation-record
  validation_role: record-only
  validation_status: pending
  uncertainty_summary: "hypothesis-generator, chain:scitoolkg-retrieve-plan-execute-summarize, validation=unvalidated, safety=unknown"
  reason_codes:
    - agent-source-unvalidated
    - tool-chain-unvalidated
    - safety-check-missing
    - information-absence-undetected

extension/agent-tool-operation:
  target_artifact_refs: [hypothesis:scitoolagent-generated-candidate]
  agent_role: hypothesis-generator
  agent_model_version: scitoolagent-summary-only
  prompt_or_workflow_ref: workflow:scitoolagent-planning-execution-summary
  tool_chain_ref: chain:scitoolkg-retrieve-plan-execute-summarize
  tool_io_contract_ref: contract:scientific-tool-chain-summary
  safety_policy_ref: policy:scitoolagent-safeguard-database
  execution_trace_ref: trace:ding-scitoolagent-tool-plan
  context_ref_set: [kg-view:scitoolkg-task-context]
  context_selection_method: kg-filter
  context_completeness: complete-for-task
  safety_check_status: unknown
  validation_protocol_refs: []
  validation_status_detail: unvalidated
  abstention_supported: false
```

| Field | Score | Note |
|---|---:|---|
| core.artifact_type | 2 | `agent-tool-operation` follows from the design. |
| core.input_artifact_refs | 1 | KG context is described, exact view ref is author-created. |
| core.method_ref | 0 | The paper defines the architecture, but the concrete workflow is not in the summary. |
| core.support_direction | 2 | `operation-record` by extension rule. |
| core.validation_role | 2 | `record-only` by extension rule. |
| core.reason_codes | 1 | Depends on inferred validation/safety state. |
| extension/agent-tool-operation.agent_role | 1 | Planner/executor/summarizer roles are named, exact primary role depends on chosen operation. |
| extension/agent-tool-operation.tool_chain_ref | A | Author-created registry ref. |
| extension/agent-tool-operation.context_ref_set | 1 | SciToolKG context explicit; exact kg-view ref absent. |
| extension/agent-tool-operation.safety_check_status | 1 | Safety module explicit; exact check result not given. |
| extension/agent-tool-operation.validation_status_detail | 1 | Benchmark exists, this exact operation unvalidated. |

**Friction.** The v1.1 field set is usable, but two authoring conventions need tightening. First, `method_ref` should be allowed to point to a workflow or be absent when a paper describes the general architecture but not the exact operation protocol. Second, `safety-check-missing` is decidable only through the registry-resolved view; when the payload names a policy and the status is `unknown`, the code should be required even if the paper says a safety module exists.

## Extraction 2 - Yu2026 -> agent-evaluation

Yu2026 describes SciCUEval as a benchmark for scientific context understanding. The summary explicitly names the competencies, including information-absence detection, but not the model results or metric values. The most faithful payload is a dataset/protocol-level quality record, not an audit of specific Science operations.

```yaml
core:
  payload_id: eval-2026-scicueval-absence-detection
  artifact_type: agent-evaluation
  extensions: [agent-evaluation]
  created_at: 2026-05-07T00:00:00-04:00
  input_artifact_refs: [dataset:scicueval]
  method_ref: paper:Yu2026
  agent_ref: agent:evaluation-author
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: pending
  uncertainty_summary: "information-absence-detection: inconclusive, n=unknown"
  reason_codes: []

extension/agent-evaluation:
  evaluated_agent_ref: agent:scientific-llm-class
  evaluated_role: paper-reader
  evaluated_model_version: ~
  evaluated_tool_chain_ref: ~
  evaluation_protocol_ref: protocol:scicueval-information-absence-detection
  evaluation_competency: information-absence-detection
  evaluation_dataset_ref: dataset:scicueval
  sample_size: ~
  metric_set: {}
  bayes_factor_evidence: {interpretation: not-applicable}
  result: inconclusive
  evaluated_operation_refs: []
```

| Field | Score | Note |
|---|---:|---|
| core.artifact_type | 2 | `agent-evaluation` follows from the benchmark use. |
| core.input_artifact_refs | 1 | The dataset is explicit, exact local registry ref is author-created. |
| core.method_ref | 2 | Yu2026 is the protocol source. |
| core.support_direction | 2 | `quality-record` by extension rule. |
| core.validation_role | 2 | `quality-record-only` by extension rule. |
| core.reason_codes | 2 | No `information-absence-undetected` when result is inconclusive rather than fail/partial. |
| extension/agent-evaluation.evaluation_competency | 2 | Information-absence detection is explicit. |
| extension/agent-evaluation.result | x | The summary says evaluations exist but gives no result for a specific model/role. |
| extension/agent-evaluation.metric_set | x | Fine-grained analysis is named, values are absent. |
| extension/agent-evaluation.evaluated_operation_refs | 2 | Empty list means dataset/protocol-level coverage by v1.1 rule. |

**Friction.** `evaluated_agent_ref` and `evaluated_role` are required even when the summary only supports a benchmark-level artifact. v1.2 should add an authoring convention for evaluation scope: dataset/protocol-level evaluations may use class-level agent refs and role refs, but that choice must not retire codes for concrete operations unless those operations are explicitly listed or gated through registry state.

## Extraction 3 - Si2025 -> agent-evaluation

Si2025 gives the clearest evaluation payload. It explicitly frames implicit-bias detection as Bayesian hypothesis testing, with Bayes factors distinguishing evidence for bias, evidence against bias, and inconclusive cases.

```yaml
core:
  payload_id: eval-2026-si2025-llm-bias-bayes-factor
  artifact_type: agent-evaluation
  extensions: [agent-evaluation]
  created_at: 2026-05-07T00:00:00-04:00
  input_artifact_refs: [dataset:bbq, dataset:crows-pairs, dataset:winogender]
  method_ref: paper:Si2025
  agent_ref: agent:evaluation-author
  proposition_refs: []
  comparison_target: artifact-target
  support_direction: quality-record
  validation_role: quality-record-only
  validation_status: pending
  uncertainty_summary: "bias-detection: partial, n=unknown, BF10=present-in-paper"
  reason_codes: [agent-bias-risk]

extension/agent-evaluation:
  evaluated_agent_ref: agent:llm-class
  evaluated_role: causal-prior-elicitor
  evaluated_model_version: ~
  evaluated_tool_chain_ref: ~
  evaluation_protocol_ref: protocol:bayesian-implicit-bias-test
  evaluation_competency: bias-detection
  evaluation_dataset_ref: dataset:implicit-bias-benchmarks
  sample_size: ~
  metric_set: {binary_choice_preference_model: bernoulli}
  bayes_factor_evidence:
    hypothesis_ref: hypothesis:llm-implicit-bias-risk
    null_baseline: "pi = 0.5 unless context-specific baseline is supplied"
    bf10: ~
    interpretation: evidence-for-risk
  result: partial
  evaluated_operation_refs: []
```

| Field | Score | Note |
|---|---:|---|
| core.artifact_type | 2 | Bias testing is an `agent-evaluation`. |
| core.input_artifact_refs | 1 | Datasets are named; exact project registry refs are author-created. |
| core.method_ref | 2 | Si2025 is the protocol source. |
| core.support_direction | 2 | `quality-record` by extension rule. |
| core.validation_role | 2 | `quality-record-only`; direct `strengthen-belief` remains forbidden. |
| core.reason_codes | 2 | `agent-bias-risk` follows from partial/fail or evidence-for-risk. |
| extension/agent-evaluation.evaluation_competency | 2 | Bias detection is explicit. |
| extension/agent-evaluation.bayes_factor_evidence | 2 | Bayes-factor semantics are explicit, but numeric BF is not in the summary. |
| extension/agent-evaluation.result | 1 | Broadly consistent bias behavior supports partial/risk, but per-model results are absent. |
| extension/agent-evaluation.metric_set | 1 | Bernoulli binary-choice model is explicit; benchmark metrics are absent. |

**Friction.** The design handles the key Bayes-factor distinction, but the result/Bayes-factor biconditional needs one more explicit priority rule. If `bayes_factor_evidence.interpretation: evidence-for-risk`, `agent-bias-risk` must be declared regardless of whether the coarse `result` is `partial` or `inconclusive`.

## Extraction 4 - project-local operation record, if authorable

### Project-local operation attempt

The search found synthesis files with frontmatter such as `generated_at` and `source_commit`, including `meta/doc/background/papers/synthesis-2026-05-06-scientific-agents-knowledge-graphs.md`. That is enough to identify a produced artifact and source commit, but not enough to author a faithful `agent-tool-operation` record. Missing fields include the concrete `agent_ref`, `agent_model_version`, `prompt_or_workflow_ref`, `tool_chain_ref`, `execution_trace_ref`, validation protocol state, and abstention capability.

The closest operation sketch is therefore intentionally incomplete:

```yaml
core:
  payload_id: op-2026-batch5-synthesis-generation
  artifact_type: agent-tool-operation
  extensions: [agent-tool-operation]
  input_artifact_refs:
    - paper:Ding2025
    - paper:Yu2026
    - paper:Si2025
  method_ref: workflow:science-research-papers
  agent_ref: ~
  pipeline_provenance_ref: ~
  proposition_refs: []
  comparison_target: n-a
  support_direction: operation-record
  validation_role: record-only
  validation_status: pending
  reason_codes: [agent-source-unvalidated, tool-chain-unvalidated, information-absence-undetected]

extension/agent-tool-operation:
  target_artifact_refs: [synthesis:scientific-agents-knowledge-graphs]
  agent_role: synthesis-author
  agent_model_version: ~
  prompt_or_workflow_ref: workflow:science-research-papers
  tool_chain_ref: ~
  execution_trace_ref: ~
  context_ref_set:
    - paper:Ding2025
    - paper:Yu2026
    - paper:Si2025
  context_selection_method: explicit-user-provided
  context_completeness: unknown
  safety_check_status: not-applicable
  validation_protocol_refs: []
  validation_status_detail: unvalidated
  abstention_supported: false
```

**Finding.** Existing synthesis frontmatter records artifact time and source commit but does not record run-level agent/tool provenance. For v1.2, the design should state that project-local operations are authorable only when the source artifact has a trace/provenance sidecar or frontmatter fields that can resolve the agent/workflow/chain boundary.

## Cross-case findings

1. **Registry refs are the dominant authoring burden.** Ding2025 is semantically about a tool-chain operation, but almost every durable object is an author-created registry ref. The schema should acknowledge "summary-derived provisional refs" as acceptable during design extraction and require later registry resolution before production validation.
2. **Evaluation scope needs an explicit convention.** Yu2026 and Si2025 are dataset/protocol-level evaluations. `evaluated_operation_refs: []` is clear, but authors still need a sanctioned way to use class-level `evaluated_agent_ref` values without pretending a specific Science agent/version was tested.
3. **Safety status must stay registry-resolved.** Ding2025 names a safety module but not the check result. The author can set `unknown`; whether `safety-check-missing` fires depends on the resolved applicable policy.
4. **Bayes-factor semantics need priority over coarse result labels.** Si2025 motivates `agent-bias-risk` whenever the BF interpretation is evidence-for-risk, even if result labels differ by benchmark convention.
5. **Project-local operation records need trace capture.** Current synthesis frontmatter does not expose enough agent/tool-operation state to author a real operation record after the fact.

### Cross-case check - context refs vs input refs

The distinction held, but only when the author deliberately separated semantic derivation inputs from observed context:

- Ding2025: the KG view is both what the operation saw and the semantic basis of the operation sketch, so it appears in both `core.input_artifact_refs` and `context_ref_set`.
- Yu2026 and Si2025: benchmark datasets are formal inputs to the evaluation payload; there is no separate operation context because these are evaluation records, not tool-operation records.
- Project-local synthesis: paper summaries are both synthesis inputs and context seen by the authoring workflow. They should appear in both places only for an operation payload that represents the synthesis-generation run.

Ambiguity remains for paper-derived method descriptions. A method paper such as Ding2025 can be `method_ref` for an evaluation/protocol payload, but a concrete Science operation should prefer a project workflow ref.

## Proposed v1.2 patches

1. **P-pilot-1 - Add provisional registry-ref authoring convention.** In the registry or operation authoring section, state that pilot/design extraction may use provisional refs for chains, policies, protocols, traces, and KG views, but production validation must resolve them before enforcing registry-dependent biconditionals.
2. **P-pilot-2 - Clarify operation `method_ref` priority.** In `agent-tool-operation`, state that concrete project workflow refs are preferred; method papers are valid only when the operation directly applies that paper's method as the operative protocol; otherwise `method_ref` may remain absent in a summary-only pilot.
3. **P-pilot-3 - Add evaluation-scope convention.** In `agent-evaluation`, state that `evaluated_operation_refs: []` plus class-level agent or role refs records dataset/protocol-level coverage and does not retire or gate concrete operation codes unless wired through registry gating state.
4. **P-pilot-4 - Strengthen Bayes-factor priority for `agent-bias-risk`.** In `agent-evaluation` and H03 text, make `bayes_factor_evidence.interpretation: evidence-for-risk` sufficient for `agent-bias-risk` even when the coarse `result` label is not fail/partial.
5. **P-pilot-5 - Add project-local trace authoring requirement.** In operation mapping or validation candidates, state that after-the-fact project-local operation records require a trace/provenance sidecar or frontmatter sufficient to resolve agent/workflow/chain state; otherwise authors must record the attempt as unauthorable rather than fabricate missing refs.

## Residual audit prompts

- Should `agent_model_version` remain optional for class-level evaluations, or should class-level evaluations use a separate `evaluated_agent_class_ref` field?
- Should production validators reject unresolved provisional refs immediately, or should there be an explicit `registry_resolution_status` field for draft payloads?
- What exact frontmatter or sidecar format should future Science synthesis/paper-summary operations emit so t037 records can be authored mechanically?

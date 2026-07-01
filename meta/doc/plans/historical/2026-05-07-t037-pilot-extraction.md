# t037 Pilot Extraction (3 operation/evaluation cases, v1.1)

> **Status:** Pilot extraction (2026-05-07). Empirical pressure-test of `[t037]` v1.1 (`meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`).
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

**Scoring discipline.** Match t034's strict rubric: a registry ref counts as "in source" only when the source content itself names the specific ref (or names a concrete artifact the ref unambiguously denotes). When the source describes the *concept* but the specific ref label is invented by the author, score `x` rather than `1`/`A`. Picking among multiple plausible values that the source mentions in parallel is `0`, not `1`. This is the discipline that drove t034's 25–41% per-case ✗-rates and is what makes the pilot's signal honest about authoring impedance.

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
| core.input_artifact_refs | x | KG context is described conceptually; the specific `kg-view:scitoolkg-task-context` ref is invented because no such registry view exists in the project. Production authoring would require a real materialized KG view. |
| core.method_ref | x | The paper describes SciToolAgent's architecture, but the concrete project workflow ref `~` is absent because no Science workflow runs SciToolAgent. |
| core.support_direction | 2 | `operation-record` by extension rule. |
| core.validation_role | 2 | `record-only` by extension rule. |
| core.reason_codes | 1 | The four codes follow inferably from the unvalidated/unknown-safety/non-abstaining state, given the schema's biconditional rules. |
| extension/agent-tool-operation.agent_role | 0 | The paper names planner, executor, and summarizer roles in parallel; choosing `hypothesis-generator` as the *primary* role is one of multiple plausible readings. |
| extension/agent-tool-operation.tool_chain_ref | x | The paper describes the orchestration shape but does not specify a concrete chain. The ref `chain:scitoolkg-retrieve-plan-execute-summarize` is invented; no registry chain exists. |
| extension/agent-tool-operation.context_ref_set | x | Same situation as `core.input_artifact_refs` — the kg-view ref is invented. |
| extension/agent-tool-operation.safety_check_status | x | The paper says a safety module exists but does not state the per-run check result. `unknown` is a defensive default, not a value the source gives. |
| extension/agent-tool-operation.validation_status_detail | 1 | Inferable: a paper-summary-only operation cannot have passed Science-side validation, so `unvalidated` is uncontroversial. |

Per-case score histogram: 2×3, 1×2, 0×1, x×5, A×0. ✗-rate: 5/11 ≈ **45%**.

**Friction.** The 45% ✗-rate is concentrated in registry refs (chain, kg-view, safety state). The schema fields exist; the source doesn't supply the values. Two authoring conventions need tightening. First, `method_ref` should be allowed to point to a workflow or be absent when a paper describes the general architecture but not the exact operation protocol. Second, `safety-check-missing` is decidable only through the registry-resolved view; when the payload names a policy and the status is `unknown`, the code should be required even if the paper says a safety module exists. The high ✗-rate is exactly the signal that motivates P-pilot-1: production validation must resolve provisional refs against a real registry, but pilot/design extraction cannot meet that bar.

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
| core.input_artifact_refs | x | SciCUEval is explicit conceptually; the local registry ref `dataset:scicueval` is invented because no Science-side dataset entry exists. |
| core.method_ref | 2 | `paper:Yu2026` resolves to a real summary in the repo, so this ref is source-grounded. |
| core.support_direction | 2 | `quality-record` by extension rule. |
| core.validation_role | 2 | `quality-record-only` by extension rule. |
| core.reason_codes | 2 | No `information-absence-undetected` when result is inconclusive rather than fail/partial — schema-determined. |
| extension/agent-evaluation.evaluation_competency | 2 | Information-absence detection is explicit. |
| extension/agent-evaluation.result | x | The summary says evaluations exist but gives no result for a specific model/role. |
| extension/agent-evaluation.metric_set | x | Fine-grained analysis is named, values are absent. |
| extension/agent-evaluation.evaluated_operation_refs | 2 | Empty list means dataset/protocol-level coverage by v1.1 rule. |

Per-case score histogram: 2×7, 1×0, 0×0, x×3, A×0. ✗-rate: 3/10 = **30%**.

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
| core.input_artifact_refs | x | The benchmarks (BBQ, CrowS-Pairs, WinoGender) are named conceptually; the project-side `dataset:bbq` etc. refs are invented because no Science-side dataset entries exist. |
| core.method_ref | 2 | `paper:Si2025` resolves to a real summary in the repo. |
| core.support_direction | 2 | `quality-record` by extension rule. |
| core.validation_role | 2 | `quality-record-only`; direct `strengthen-belief` remains forbidden. |
| core.reason_codes | 2 | `agent-bias-risk` follows from `evidence-for-risk` interpretation by the v1.2 P-pilot-4 priority rule. |
| extension/agent-evaluation.evaluation_competency | 2 | Bias detection is explicit. |
| extension/agent-evaluation.bayes_factor_evidence | 1 | The interpretation field (`evidence-for-risk`) is inferable from the paper's framing; the numeric `bf10` is `~` because the summary gives no value. Net: structurally inferable, partially populated. |
| extension/agent-evaluation.result | 1 | Broadly consistent bias behavior supports partial/risk, but per-model results are absent — inferable, not stated. |
| extension/agent-evaluation.metric_set | 1 | Bernoulli binary-choice model is explicit; benchmark metrics are absent — inferable structure, missing values. |

Per-case score histogram: 2×6, 1×3, 0×0, x×1, A×0. ✗-rate: 1/10 = **10%**.

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
  target_artifact_refs: [synthesis:0006-synthesis-scientific-agents-and-knowledge-graph-infrastructure]
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

**✗-rate roll-up across the three completed extractions:** 9/31 ≈ **29%** (Ding 45%, Yu 30%, Si 10%). The project-local attempt was deliberately abandoned at ~46% authorability, which is the same impedance signal expressed differently. The roll-up sits inside t034's 25–41% per-case band and the per-case spread reveals the structural cause: `agent-tool-operation` payloads against architecture papers (Ding) carry more registry-ref invention than `agent-evaluation` payloads against benchmark papers (Yu, Si), because the latter are semantically dense — the protocol *is* the paper. Si's 10% is the floor; Ding's 45% is the ceiling. Future operation-record pilots against architecture-but-not-implementation papers should expect ≥40% ✗-rates.

1. **Registry refs are the dominant authoring burden.** Ding2025 is semantically about a tool-chain operation, but almost every durable object is an author-created registry ref. Of Ding's 5 ✗ scores, all 5 are registry refs (input_artifact_refs, method_ref, tool_chain_ref, context_ref_set, safety_check_status). The schema should acknowledge "summary-derived provisional refs" as acceptable during design extraction and require later registry resolution before production validation.
2. **Evaluation scope needs an explicit convention.** Yu2026 and Si2025 are dataset/protocol-level evaluations. `evaluated_operation_refs: []` is clear, but authors still need a sanctioned way to use class-level `evaluated_agent_ref` values without pretending a specific Science agent/version was tested.
3. **Safety status must stay registry-resolved.** Ding2025 names a safety module but not the check result. The author can set `unknown`; whether `safety-check-missing` fires depends on the resolved applicable policy.
4. **Bayes-factor semantics need priority over coarse result labels.** Si2025 motivates `agent-bias-risk` whenever the BF interpretation is evidence-for-risk, even if result labels differ by benchmark convention.
5. **Project-local operation records need trace capture.** Current synthesis frontmatter does not expose enough agent/tool-operation state to author a real operation record after the fact.
6. **Methods-paper vs applied-payload routing applies to t037 too.** The same routing principle t034 added in v1.2 (P-pilot-8) is the right framing for what Ding-style papers look like in t037: a *methods-paper* core-only claim about SciToolAgent-the-method (no extension loaded, low ✗-rate) is cleanly authorable; an *applied-payload* `agent-tool-operation` re-encoding requires either a real Science run or accepting the ~45% ✗-rate. The pilot evidence supports adopting the same routing convention in t037 v1.3.

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

## Re-scored 2026-05-07: additional patch candidates

The strict-rubric re-score (2026-05-07) raised the per-case ✗-rates from a soft 0–20% to a stricter 10–45%, putting t037 in the same impedance band as t034. The re-score surfaced one new patch candidate not caught by the original soft scoring:

6. **P-pilot-6 - Methods-paper vs applied-payload routing for t037 (mirrors t034 P-pilot-8).** Add a section to the design doc stating that a paper introducing an *agent/tool method* (Ding2025 SciToolAgent, Yu2026 SciCUEval, Si2025 Bayesian-bias-test) produces two distinct payload candidates: (1) a `methods-paper` core-only paper-extracted-claim with no t037 extension loaded; (2) zero-or-more applied-payload re-encodings (`agent-tool-operation` for tool-chain runs, `agent-evaluation` for benchmark runs) that declare an `extracted-from-summary-only`-equivalent code if the source is a paper-summary rather than a real run. Authors should consciously choose which they're authoring; the strict-rubric ✗-rate is the operational signal for when (1) is the right call.

P-pilot-6 was not present in the v1.2 design bump (the soft scoring obscured it). Track it as a v1.4 candidate alongside whatever v1.3 finalized.

## Residual audit prompts

- Should `agent_model_version` remain optional for class-level evaluations, or should class-level evaluations use a separate `evaluated_agent_class_ref` field?
- Should production validators reject unresolved provisional refs immediately, or should there be an explicit `registry_resolution_status` field for draft payloads?
- What exact frontmatter or sidecar format should future Science synthesis/paper-summary operations emit so t037 records can be authored mechanically?

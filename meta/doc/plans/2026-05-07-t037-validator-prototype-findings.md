# t037 v1.2 `agent-tool-operation` Validator Prototype - Findings

> **Status:** Findings (2026-05-07). Companion to the validator script at `meta/doc/plans/2026-05-07-t037-agent-tool-operation-validator-prototype.py`.
>
> **Goal:** prove that the load-bearing t037 operation-record rules are decidable from payload state plus a registry-resolved operation view.

## What the prototype implements

- `ato-1`: If `extension/agent-tool-operation` is absent, the validator returns no issues.
- `ato-2`: `agent_role` is required and must be one of the strict t037 role taxonomy values.
- `ato-3`: `validation_role: strengthen-belief` is forbidden on `agent-tool-operation`.
- `ato-4`: If the registry-resolved view says the operation invokes an executable capability, `tool_chain_ref` is required.
- `ato-5`: Safety policy consistency is biconditional against the registry-resolved view: no applicable policy requires `not-applicable` and no safety code; applicable skipped/unknown checks require `safety-check-missing`.
- `ato-6`: `agent-source-unvalidated` is declared iff `agent_model_version` is present and `validation_status_detail: unvalidated`.
- `ato-7`: `tool-chain-unvalidated` is declared iff `tool_chain_ref` is present and the resolved chain has no passed validation.
- `ato-8`: `context-retrieval-uncertain` is declared iff the selection method is retrieval/filter/search and context is not `complete-for-task`.
- `ato-9`: `information-absence-undetected` is declared iff abstention is unsupported for an absence-sensitive role.
- `ato-10`: `target_artifact_refs` must be non-empty unless `abstention_reason` is present.

## Test outcome

The prototype was run with:

```bash
python meta/doc/plans/2026-05-07-t037-agent-tool-operation-validator-prototype.py
```

Outcome: `20/20 tests passed`.

| Test | Probe | Outcome |
|---|---|---|
| 01-minimal-valid | positive case | passes |
| 02-strengthen-forbidden | rejects direct strengthen-belief | passes |
| 03-unknown-agent-role | rejects role outside taxonomy | passes |
| 04-direct-capability-without-chain | requires one-step-or-more chain for direct capability use | passes |
| 05-no-safety-policy-not-applicable-clean | allows no policy plus `not-applicable` safety status | passes |
| 06-safety-code-overdeclared | rejects safety code when no policy applies | passes |
| 07-safety-policy-skipped-missing-code | requires safety code for applicable skipped check | passes |
| 08-agent-unvalidated-missing-code | requires agent unvalidated code | passes |
| 09-agent-unvalidated-overdeclared | rejects agent unvalidated over-declaration | passes |
| 10-tool-chain-unvalidated-missing-code | requires tool-chain unvalidated code | passes |
| 11-tool-chain-unvalidated-overdeclared | rejects tool-chain unvalidated over-declaration | passes |
| 12-context-retrieval-uncertain-missing-code | requires context retrieval uncertainty code | passes |
| 13-context-retrieval-uncertain-overdeclared | rejects context retrieval uncertainty over-declaration | passes |
| 14-explicit-context-partial-no-code-clean | allows explicit-user-provided partial context without retrieval code | passes |
| 15-information-absence-missing-code | requires information absence code for sensitive role without abstention | passes |
| 16-information-absence-overdeclared-non-sensitive-role | rejects information absence over-declaration for non-sensitive role | passes |
| 17-no-target-without-abstention | requires target refs unless abstaining | passes |
| 18-no-extension-no-issues | no extension means no t037 operation issues | passes |
| 19-v12-pilot-adapted-ding | Ding pilot-adapted operation passes with expected codes | passes |
| 20-v12-pilot-adapted-paper-reader | paper-reader pilot-adapted operation passes with expected codes | passes |

## What this discharges

The prototype discharges the core decidability concern from the v1.1 and v1.2 audit loops: the operation-record rules can be evaluated from the payload plus a compact `ResolvedOperationView`. No rule requires reading prose or inferring source intent at validation time once registry state is materialized.

It also discharges the direct-capability audit prompt. A direct command, tool, or skill call can be represented as a one-step `tool_chain_ref`, and the validator can reject bare capability invocation when the resolved view says a capability was invoked.

## What the prototype showed about v1.2's rules

The rules are decidable, but three wording points should be tightened before v1.3:

- Safety consistency should explicitly reject `safety_check_status: not-applicable` when the registry-resolved view says a safety policy applies.
- `context-retrieval-uncertain` should stay scoped to retrieval/filter/search methods. Partial context from `explicit-user-provided` does not by itself declare the code.
- The design should record that the first validator slice covers `ato-1` through `ato-10` and has a passing 20-case prototype, while leaving propagation and `agent-evaluation` validation for follow-up slices.

## What the prototype does NOT validate

- `agent-evaluation` extension rules are not validated by this prototype; they are deferred to a follow-up validator slice.
- Cross-payload propagation through `pipeline_provenance_ref` and `input_artifact_refs` is not validated by this prototype.
- Registry construction is not validated; the prototype consumes a simplified `ResolvedOperationView` fixture.

## v1.3 patch candidates

1. **P-proto-1 - Tighten safety not-applicable semantics.** Affected section: `agent-tool-operation` reason-code contributions and validation machinery candidates. Exact design change: state that when the registry-resolved view has an applicable safety policy, `safety_check_status: not-applicable` is invalid; only `passed`, `failed`, `skipped`, or `unknown` are meaningful. Prototype behavior: `ato-5` implements this in the same consistency rule that handles missing and overdeclared `safety-check-missing`.
2. **P-proto-2 - Preserve the retrieval-method boundary for context uncertainty.** Affected section: `agent-tool-operation` reason-code contributions and authoring conventions. Exact design change: state that `context-retrieval-uncertain` is not declared solely because context is partial or unknown; it requires `context_selection_method` in `rag-retrieval`, `kg-filter`, `web-search`, or `file-search`. Prototype behavior: test `14-explicit-context-partial-no-code-clean` passes without the code.
3. **P-proto-3 - Record prototype coverage as v1.3 decidability evidence.** Affected section: status block and validation machinery candidates. Exact design change: record that the standalone prototype validates `ato-1` through `ato-10` with 20 passing fixtures, including the two pilot-adapted operation cases. Prototype behavior: runner reports `20/20 tests passed`.

## Next steps

- Add a second standalone validator slice for `agent-evaluation` biconditional rules, especially `agent-bias-risk` and `information-absence-undetected`.
- Add a propagation prototype for operation codes flowing through `pipeline_provenance_ref` and `input_artifact_refs`.
- Keep the current prototype outside `meta/validate.sh` until registry construction and operation-view materialization are designed.

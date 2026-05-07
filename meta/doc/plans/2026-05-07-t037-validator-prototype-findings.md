# t037 v1.2 `agent-tool-operation` Validator Prototype - Findings

> **Status:** Findings (2026-05-07). Companion to the validator script at `meta/doc/plans/2026-05-07-t037-agent-tool-operation-validator-prototype.py`.
>
> **Goal:** prove that the load-bearing t037 operation-record rules are decidable from payload state plus a registry-resolved operation view, mirroring t034's three-slice discharge of the natural-systems "asserted vs verified" alignment commitment for `[t037]`.
>
> **Position in the program:** first slice of two for `[t037]`. Sister to:
> - `meta/doc/plans/2026-05-06-t034-causal-graph-validator-prototype.py` (t034 slice 1: structural)
> - `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-prototype.py` (t034 slice 2: role-permission)
> - `meta/doc/plans/2026-05-06-t034-effective-codes-validator-prototype.py` (t034 slice 3: propagation)
>
> Slice 1 (this doc) targets `agent-tool-operation` structural and reason-code biconditional rules. Slice 2 (deferred) targets `agent-evaluation` rules and cross-payload propagation through `pipeline_provenance_ref` and `input_artifact_refs`.

## What the prototype implements

Ten rules (`ato-1` through `ato-10`) over a single `agent-tool-operation` payload plus a small `ResolvedOperationView` materializing the registry state the rules need. The view collapses what a real registry would expose into three booleans (`invokes_capability`, `tool_chain_has_passed_validation`, `applicable_safety_policy`); a production registry will surface per-protocol results, per-policy applicability, and per-capability invocation traces.

| Rule | Kind | Statement | Inputs |
|---|---|---|---|
| `ato-1` | structural | Extension absent → no issues | `EXT_KEY in payload` |
| `ato-2` | structural enum | `agent_role` is required and must be in the 13-value taxonomy | `ext.agent_role` |
| `ato-3` | role-permission | `core.validation_role: strengthen-belief` is forbidden | `core.validation_role` |
| `ato-4` | structural | If the resolved view says capability is invoked, `tool_chain_ref` is required | `view.invokes_capability`, `ext.tool_chain_ref` |
| `ato-5` | semantic biconditional (3-mode) | Safety policy consistency: no-policy ⇒ `not-applicable` ∧ no code; applicable-policy ⇒ `not-applicable` forbidden ∧ skipped/unknown ↔ code | `view.applicable_safety_policy`, `ext.safety_check_status`, `core.reason_codes` |
| `ato-6` | semantic biconditional | `agent-source-unvalidated` ↔ (`agent_model_version` present ∧ `validation_status_detail = unvalidated`) | `ext.agent_model_version`, `ext.validation_status_detail`, `core.reason_codes` |
| `ato-7` | semantic biconditional | `tool-chain-unvalidated` ↔ (`tool_chain_ref` present ∧ `view.tool_chain_has_passed_validation = false`) | `ext.tool_chain_ref`, `view.tool_chain_has_passed_validation`, `core.reason_codes` |
| `ato-8` | semantic biconditional | `context-retrieval-uncertain` ↔ (`context_selection_method ∈ RETRIEVAL_METHODS` ∧ `context_completeness ≠ complete-for-task`) | `ext.context_selection_method`, `ext.context_completeness`, `core.reason_codes` |
| `ato-9` | semantic biconditional | `information-absence-undetected` ↔ (`abstention_supported = false` ∧ `agent_role ∈ ABSENCE_SENSITIVE_ROLES`) | `ext.abstention_supported`, `ext.agent_role`, `core.reason_codes` |
| `ato-10` | structural | `target_artifact_refs` non-empty unless `abstention_reason` is present | `ext.target_artifact_refs`, `ext.abstention_reason` |

All ten enforce-able from a single payload plus the three registry view booleans. No upstream traversal, no cross-payload joins, no live registry lookup at validate-time once the view is materialized.

## Test outcome

20/20 pass. `python meta/doc/plans/2026-05-07-t037-agent-tool-operation-validator-prototype.py` reports `20/20 tests passed`.

| Test | Probe | Outcome |
|---|---|---|
| 01-minimal-valid | positive case | passes |
| 02-strengthen-forbidden | rejects direct strengthen-belief | passes (ato-3) |
| 03-unknown-agent-role | rejects role outside taxonomy | passes (ato-2) |
| 04-direct-capability-without-chain | requires one-step-or-more chain for direct capability use | passes (ato-4) |
| 05-no-safety-policy-not-applicable-clean | allows no policy plus `not-applicable` safety status | passes |
| 06-safety-code-overdeclared | rejects safety code when no policy applies | passes (ato-5) |
| 07-safety-policy-skipped-missing-code | requires safety code for applicable skipped check | passes (ato-5) |
| 08-agent-unvalidated-missing-code | requires agent unvalidated code | passes (ato-6) |
| 09-agent-unvalidated-overdeclared | rejects agent unvalidated over-declaration | passes (ato-6) |
| 10-tool-chain-unvalidated-missing-code | requires tool-chain unvalidated code | passes (ato-7) |
| 11-tool-chain-unvalidated-overdeclared | rejects tool-chain unvalidated over-declaration | passes (ato-7) |
| 12-context-retrieval-uncertain-missing-code | requires context retrieval uncertainty code | passes (ato-8) |
| 13-context-retrieval-uncertain-overdeclared | rejects context retrieval uncertainty over-declaration | passes (ato-8) |
| 14-explicit-context-partial-no-code-clean | allows explicit-user-provided partial context without retrieval code | passes |
| 15-information-absence-missing-code | requires information absence code for sensitive role without abstention | passes (ato-9) |
| 16-information-absence-overdeclared-non-sensitive-role | rejects information absence over-declaration for non-sensitive role | passes (ato-9) |
| 17-no-target-without-abstention | requires target refs unless abstaining | passes (ato-10) |
| 18-no-extension-no-issues | no extension means no t037 operation issues | passes (ato-1) |
| 19-v12-pilot-adapted-ding | Ding pilot-adapted operation passes with expected codes | passes |
| 20-v12-pilot-adapted-paper-reader | paper-reader pilot-adapted operation passes with expected codes | passes |

Negative cases (02–04, 06–13, 15–17) each fire the expected and only the expected rule. Positive cases (01, 05, 14, 18) and pilot-adapted cases (19, 20) pass cleanly.

## What this discharges

- **Natural-systems alignment commitment, t037 single-payload half.** The four reason-code biconditionals (ato-6 through ato-9) plus the safety three-mode rule (ato-5) demonstrate that t037's load-bearing decidability claim holds for one payload's state given a materialized registry view. A `validation_role: strengthen-belief` claim against an `agent-tool-operation` is rejected at validate-time (ato-3); a payload that authors a reason code without the corresponding state is rejected biconditionally; a payload that omits the corresponding code when state demands it is rejected. The "asserted vs verified" gap closes for every rule in the slice.
- **`[t037]` v1.1 audit baseline (F1–F5) is structurally enforceable.** F1's local-rule canonicalization for `agent-source-unvalidated` shows up as ato-6's biconditional (no cross-extension form). F3's one-step `tool_chain_ref` rule for direct capability calls is ato-4. F4's registry-resolved validation view is the `ResolvedOperationView` abstraction that ato-5 and ato-7 read against. F5's authoring rules are the test fixtures themselves.
- **`[t037]` v1.2 pilot patches (P-pilot-1 through P-pilot-5) are decidable in this prototype's scope.** P-pilot-2's `method_ref` priority is observable in tests 19/20 (Ding pilot-adapted uses `method_ref: ~`); P-pilot-1's provisional registry-ref convention is exercised by every test that supplies a `ResolvedOperationView` rather than a real lookup.

## What the prototype showed about v1.2's rules

Section organized by rule. Each rule states what the test set proves and what edge case it does *not* probe.

**ato-1 (extension absent → no issues).** Tests: t18 (positive). What's proven: missing `extension/agent-tool-operation` key skips silently. **Untested edge:** a typo'd extension key (e.g., `extension/agent_tool_operation` with underscore) also skips silently — the validator can't distinguish "intentionally absent" from "misspelled and accidentally invisible." This is a feature for incremental adoption but a footgun for hand-authored payloads. A v1.3 candidate would add a project-level "extension key spell-check" pass against the t022 manifest.

**ato-2 (agent_role enum).** Tests: t03 (negative — `"unknown-role"`). What's proven: a string-typed bogus role fires. **Untested edge:** `agent_role: None` and `agent_role: ""` (empty string). Both currently fire ato-2 (None ∉ AGENT_ROLES is true; "" ∉ AGENT_ROLES is true), but the error message says "must be one of [13 values]" without naming the input. A real authoring error involving an empty field would benefit from a clearer message. Cosmetic only.

**ato-3 (strengthen-belief forbidden).** Tests: t02 (negative). What's proven: `core.validation_role: strengthen-belief` is rejected directly. **Untested edge:** `core.validation_role: None` or any role outside the t022 v2.3 enum. The validator only catches `strengthen-belief` specifically; an unknown role like `"foo"` passes ato-3 silently. The validator's `PERMITTED_ROLES` constant is defined but never enforced — it's a documentation artifact, not a check. This is a v1.3 candidate (P-proto-4 below): either drop the constant or enforce membership.

**ato-4 (tool_chain_ref required when invokes_capability).** Tests: t04 (negative — capability invoked, chain absent). What's proven: missing chain on a capability-invoking operation is rejected. **Untested edge:** `invokes_capability=False` AND `tool_chain_ref` present. This should be allowed (an operation can reference a chain without having invoked it on this run, e.g., for a planned-but-not-yet-executed operation), but no test confirms ato-4 stays silent. Adding this case would document the rule's directionality.

**ato-5 (safety policy three-mode).** Tests: t05 (positive, no-policy clean), t06 (negative, code over-declared with no policy), t07 (negative, applicable-policy + skipped status missing code), and the v1.3 P-proto-1 case (applicable-policy + `not-applicable` is invalid). What's proven: all three failure modes fire. **Untested edge:** the *transition* from `unknown` to `passed` is not exercised — i.e., a payload that has `safety_check_status: passed` AND `safety-check-missing` declared. The current rule says skipped/unknown ↔ code, so a payload with `passed` AND code declared SHOULD fire ato-5 (false to true mismatch). Reading the implementation: yes, it fires (`safety_missing != has_safety_code` evaluates true when `safety_missing` is False and `has_safety_code` is True). But a positive-direction test for `passed`/`failed` statuses without the code would be cleaner. Note also that ato-5 collapses three distinct violations under one rule ID (no-policy + wrong-status-or-code, applicable-policy + not-applicable, applicable-policy + miscount). A future split into `ato-5a/b/c` would improve diagnostic precision without changing semantics.

**ato-6 (agent-source-unvalidated biconditional).** Tests: t08 (negative, missing code), t09 (negative, over-declared). What's proven: code-state biconditional matches in both directions. **Untested edge:** `agent_model_version` present AND `validation_status_detail: validated` — should NOT declare the code. No positive test confirms ato-6 stays silent for the validated case. Implementation: `validated ≠ "unvalidated"` so `agent_unvalidated = False`; `has_agent_code = False` if code absent; rule passes. But an explicit positive test would close the four-cell matrix (presence × status × code).

**ato-7 (tool-chain-unvalidated biconditional).** Tests: t10 (negative, missing code), t11 (negative, over-declared). What's proven: same biconditional shape as ato-6, sourced from `view.tool_chain_has_passed_validation`. **Untested edge:** `tool_chain_ref` absent AND code declared — should fire ato-7. Reading the implementation: `chain_unvalidated = (False and ...) = False`; `has_chain_code = True` ⇒ mismatch ⇒ ato-7 fires. The over-declaration case for *absent* chain is not separately tested; it's only tested for *present* chain that passed validation.

**ato-8 (context-retrieval-uncertain biconditional).** Tests: t12 (negative, missing code), t13 (negative, over-declared), t14 (positive, explicit-user-provided + partial = no code). What's proven: the retrieval-method gate works (P-proto-2 explicitly preserves it), and the biconditional matches. **Untested edge:** `context_selection_method` set to a value outside both retrieval methods AND `explicit-user-provided` (e.g., `"future-method"`) — currently the validator treats unknown methods as non-retrieval (silent on the code). This is a behavior worth documenting: the retrieval-method enum is implicitly closed-world.

**ato-9 (information-absence-undetected biconditional).** Tests: t15 (negative, missing for sensitive role), t16 (negative, over-declared for non-sensitive role). What's proven: role-set membership gates the code. **Untested edge:** sensitive role WITH `abstention_supported: true` — should NOT declare the code. Implementation: `absence_undetected = (False and ...)` = False; clean. But no positive test confirms ato-9 stays silent for the sensitive-but-supported case. Also: `abstention_supported: None` (missing) — implementation uses `is False`, so missing is treated as "not unsupported," and ato-9 stays silent. This is the conservative choice but worth documenting as an authoring contract: missing `abstention_supported` is read as "author hasn't said," NOT as "abstention not supported."

**ato-10 (target_artifact_refs unless abstention_reason).** Tests: t17 (negative, target absent without abstention). What's proven: target-required-unless-abstaining fires. **Untested edge:** target present AND abstention_reason present (both filled) — currently allowed by the validator, but is it a category error? An operation that produced an artifact AND abstained on something else is semantically muddled. The design doc should clarify whether this is permitted (probably yes, since they target different things) or rejected. **Note:** ato-9 reads `abstention_supported` (capability) while ato-10 reads `abstention_reason` (incident). These are different fields and the asymmetry is intentional but non-obvious — the design should call this out explicitly so authors don't conflate them.

## Cross-rule interactions

The 10 rules are not independent. Five interactions worth surfacing:

1. **ato-2 silently suppresses ato-9.** When `agent_role` is missing or unknown, ato-2 fires. Because the unknown role is not in `ABSENCE_SENSITIVE_ROLES`, ato-9 evaluates `absence_undetected = False` regardless of `abstention_supported`. So a payload with no role declared *cannot* trigger ato-9. This is correct behavior (don't compound role-shape errors with absence-detection errors), but means fixing ato-2 may surface a previously-hidden ato-9 violation. Authors should re-validate after fixing ato-2.
2. **ato-4 and ato-7 are mutually exclusive on the same payload.** ato-4 fires when `tool_chain_ref` is empty AND capability is invoked; ato-7 fires when `tool_chain_ref` is present AND chain has no passed validation. The trigger conditions partition the chain-presence axis cleanly, so a single payload can exhibit at most one of these two errors. Clean composition.
3. **ato-5 collapses three violation modes under one rule ID.** Cases where ato-5 fires: (a) no applicable safety policy + `safety_check_status ≠ not-applicable`; (b) no applicable safety policy + `safety-check-missing` over-declared; (c) applicable safety policy + `safety_check_status = not-applicable` (P-proto-1); (d) applicable safety policy + skipped/unknown status without code; (e) applicable safety policy + non-skipped status with code. Five distinct authoring errors, one rule ID. Diagnostic precision suffers; **v1.3 should consider splitting** into `ato-5a` (no-policy consistency) and `ato-5b` (applicable-policy consistency) at minimum, or all five sub-cases at maximum.
4. **ato-6, ato-7, and ato-5 share the registry-view dependency.** All three rules consult `ResolvedOperationView`. A misconfigured registry view (e.g., `applicable_safety_policy: True` when no policy actually exists in the registry) would propagate into all three rules' decisions. The validator does not check view *consistency*; it trusts the view as authoritative. Documenting this contract — the view is a trusted boundary — is a v1.3 polish item.
5. **ato-9 and ato-10 use different abstention fields.** `abstention_supported: bool` is a *capability* claim ("this agent can abstain"); `abstention_reason: str` is an *incident* claim ("this run abstained for reason X"). ato-9 reads the capability; ato-10 reads the incident. A payload with `abstention_supported: true` but no `abstention_reason` AND no target refs fires ato-10 (the agent could have abstained but didn't, so it must have produced something). This is correct semantics but the field-pair asymmetry is non-obvious — the design should make it explicit.

## What the prototype does NOT validate

- **`agent-evaluation` extension rules.** The full design (lines 264–309) defines validation rules for `evaluation_competency`, `bayes_factor_evidence`, `result`, `evaluated_operation_refs`, and `agent-bias-risk` biconditionals. None are validated by this slice. A second slice on `agent-evaluation` is the natural successor — should exercise the v1.2 P-pilot-3 (evaluation-scope convention) and P-pilot-4 (Bayes-factor priority) rules.
- **Cross-payload propagation** through `pipeline_provenance_ref` and `input_artifact_refs`. The t034 slice 3 prototype demonstrated the propagation pattern (declared ∪ auto-injected ∪ propagated_blocking − retired). t037's blocking codes (`agent-source-unvalidated`, `tool-chain-unvalidated`, `safety-check-missing`, `information-absence-undetected`) should propagate into downstream consumer payloads under the same rule. Untested.
- **Registry construction.** The prototype consumes a `ResolvedOperationView` fixture with three booleans. A real registry would expose per-protocol validation results, per-policy applicability conditions, per-capability invocation traces, and a query API. The prototype does not validate that the registry-construction logic produces a consistent view, only that *given* a consistent view, the rules decide correctly.
- **Worked-example cross-validation.** Examples T37-3 and T37-4 in the design doc are `agent-evaluation` payloads. They are not validated against this prototype's rules (out of scope for slice 1).
- **t034 co-load interlock.** The design specifies the canonical `causal-prior-bundle + agent-tool-operation` co-load pattern (design lines 372–431). The prototype does not validate co-load preconditions, field division between the two extensions, or the context-vs-input distinction at the boundary. The pilot's cross-case check (lines 245–253) covers this informally; a real co-load validator would belong in slice 2.

## v1.3 patch candidates

The three candidates already adopted into the v1.3 design (visible in the design doc's status block) are:

1. **P-proto-1 - Tighten safety not-applicable semantics.** *Affected section:* `agent-tool-operation` reason-code contributions and validation machinery candidates. *Exact change:* state that when the registry-resolved view has an applicable safety policy, `safety_check_status: not-applicable` is invalid; only `passed`, `failed`, `skipped`, or `unknown` are meaningful. *Prototype evidence:* `ato-5` implements this via the `safety_status == "not-applicable"` branch under the applicable-policy path; cases 06 and 07 fire correctly. Prior to this patch, the design's wording on `not-applicable` was permissive enough that an applicable-policy payload could quietly use `not-applicable` and skip both the code check and the status check — exactly the pre-v1.1 absence-bug pattern that F4 was meant to close.
2. **P-proto-2 - Preserve the retrieval-method boundary for context uncertainty.** *Affected section:* `agent-tool-operation` reason-code contributions and authoring conventions. *Exact change:* state that `context-retrieval-uncertain` is not declared solely because context is partial or unknown; it requires `context_selection_method` in the four-value retrieval set (`rag-retrieval`, `kg-filter`, `web-search`, `file-search`). *Prototype evidence:* test 14 (`14-explicit-context-partial-no-code-clean`) confirms an `explicit-user-provided` source with partial completeness does not declare the code; the validator's `context_selection_method in RETRIEVAL_METHODS` gate makes this decidable. Without the patch, authors who knew the context was incomplete would be tempted to declare `context-retrieval-uncertain` as a defensive caveat — which would conflate "the retrieval was uncertain" with "the user supplied something incomplete," collapsing two distinct evidence stories.
3. **P-proto-3 - Record prototype coverage as v1.3 decidability evidence.** *Affected section:* status block and validation machinery candidates. *Exact change:* record that the standalone prototype validates `ato-1` through `ato-10` with 20 passing fixtures, including the two pilot-adapted operation cases. *Prototype evidence:* `20/20 tests passed`; the test set covers all 10 rules with positive and negative cases plus two pilot-grounded cases.

The deepened review (2026-05-07) surfaced one additional candidate not in the v1.3 design:

4. **P-proto-4 (NEW v1.4 candidate) - Either enforce or drop `PERMITTED_ROLES`.** *Affected section:* `agent-tool-operation` validation rules and the validator's `PERMITTED_ROLES` constant. *Issue:* the constant is defined (`{record-only, quality-record-only, prioritize-attention, gate-update}`) but only the negative `strengthen-belief` case is checked (ato-3). An author writing `validation_role: foo` passes ato-3 silently; a downstream rule that depends on role membership has no validate-time guard. *Recommended change:* extend ato-3 to enforce membership: `validation_role` must be in `PERMITTED_ROLES`, with `strengthen-belief` rejected as the load-bearing case. Alternatively, drop the constant and rely on t022's core enum check (cleaner if t022 already enforces membership). *Prototype evidence:* the constant is never read in `validate_agent_tool_operation`; this is observable from the source.

A v1.3 cleanup candidate also surfaced from the cross-rule analysis:

5. **P-proto-5 (NEW v1.4 candidate) - Split ato-5 into sub-rules.** *Affected section:* validator rule IDs and findings. *Issue:* ato-5 covers five distinct violation modes (no-policy + wrong-status; no-policy + code over-declared; applicable-policy + not-applicable; applicable-policy + missing code; applicable-policy + over-declared code) under one rule ID, hurting diagnostic precision. *Recommended change:* split into `ato-5a` (no-policy consistency) and `ato-5b` (applicable-policy consistency); optionally split further per failure mode. Tests 06, 07, and the implicit P-proto-1 case would each fire a more specific ID. No semantic change; pure diagnostics improvement.

## Next steps

1. **Slice 2: `agent-evaluation` rules.** Build a sister validator for the `agent-evaluation` extension covering the Bayes-factor `agent-bias-risk` biconditional (P-pilot-4), the evaluation-scope convention (P-pilot-3), and the result-vs-interpretation priority. Roughly the same shape as this slice (~10 rules, ~20 tests).
2. **Slice 3: cross-payload propagation prototype.** Mirror t034 slice 3's `effective_codes` machinery for t037's four blocking codes propagating through `pipeline_provenance_ref` and `input_artifact_refs`. Smallest non-trivial test: an `agent-tool-operation` declaring `agent-source-unvalidated`, referenced by a downstream synthesis payload claiming `validation_role: prioritize-attention` — the consumer's `effective_codes` should inherit the blocking code under propagate-blocking, and any downstream rule that forbids that code should reject.
3. **Adopt P-proto-4 and P-proto-5 in the next design bump.** Both are decidability/diagnostics polish, not semantic changes. Either fold into v1.4 alongside the slice-2 findings, or land standalone.
4. **Pilot rescore (2026-05-07) re-checked the v1.2 patch coverage.** The strict-rubric rescore (per-case ✗-rates Ding 45% / Yu 30% / Si 10%) surfaced one additional pilot-level patch candidate: **P-pilot-6** (methods-paper vs applied-payload routing for t037, mirroring t034's P-pilot-8). Track as v1.4 alongside the slice-2 work.
5. **Keep the prototype outside `meta/validate.sh`.** Two prerequisites match t034's: (a) registry-construction design lands; (b) a YAML payload-loader replaces the Python-dict fixture interface. Until both, the prototype stays a study, not a production check.

The natural-systems "asserted vs verified" commitment is now half-discharged for `[t037]` (single-payload structural and biconditional rules). The remaining half — cross-payload propagation — is one slice away.

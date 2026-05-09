# t034 v1.3 effective-codes / propagation Validator Prototype — Findings

> **Status:** Findings (2026-05-06). Companion to the validator script at `meta/doc/plans/2026-05-06-t034-effective-codes-validator-prototype.py`. Reports what the third (and final-for-now) prototype slice exercises and surfaces.
>
> **Goal:** discharge the *remaining half* of the natural-systems alignment commitment for `[t034]` — prove that cross-payload reason-code propagation, retirement, and consumer-side strengthening rules are decidable from the payload graph and the v1.3-tightened contract.
>
> **Position in the program:** slice 3 of 3. Sister to:
> - `meta/doc/plans/2026-05-06-t034-causal-graph-validator-prototype.py` (slice 1: structural rules on `causal-graph`)
> - `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-prototype.py` (slice 2: role-permission rules on `mr-graph-model`)
> - design contract: `meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md` (v1.3, 85b984c)

## What the prototype implements

**The v1.3 effective-codes computation.** Per design v1.3 P1.3-c, `effective_codes(p)` is now formally:

```
effective_codes(p) = declared(p) ∪ auto_injected(p) ∪ propagated_blocking(upstream(p))
                   \ retired_by(p)
```

Where:
- `declared(p)` = `core.reason_codes` (post-v1.3, must NOT contain auto-injected codes)
- `auto_injected(p)` = ⋃ over loaded extensions of `AUTO_INJECTION[ext]`
- `propagated_blocking(upstream(p))` = ⋃ over `core.input_artifact_refs` of `{c ∈ effective_codes(upstream) : c ∈ BLOCKING_CODES}`
- `retired_by(p)` = codes the payload resolves on its own content (e.g., `causal-identification` with `identification_status ∈ {identified, partially-identified}` retires `identification-missing`)

Cycle detection halts recursion at the cycle boundary; a separate `detect_cycle` helper reports them as their own error.

**Auto-injection table** (mirroring the v1.3 design table):

| Extension | Auto-injected codes |
|---|---|
| `causal-discovery-run` | `identification-missing` |
| `mr-graph-model` | `instrument-assumption-risk` |
| `mr-analysis` | `instrument-assumption-risk` |
| `mechanistic-hypothesis-bundle` | `mechanism-hypothesis-only`, `prior-network-dependent` |

**Blocking-code set** (mirroring the v1.3 reason-code rollup table at design.md:492):

```
{llm-prior-unvalidated, identification-missing, pleiotropy-untested,
 multiplicity-uncorrected, self-incompatible, mechanism-hypothesis-only,
 estimand-mismatch}
```

**Retirement table:**

| Payload condition | Retires |
|---|---|
| `causal-identification` with `identification_status ∈ {identified, partially-identified}` | `identification-missing` |
| `mr-analysis` with `pleiotropy_handling != unhandled` | `pleiotropy-untested` |

**Three rules under enforcement:**

| Rule | Statement |
|---|---|
| `v1.3-auto-inject` | `core.reason_codes` must NOT contain auto-injected codes for any loaded extension. |
| `cee-strengthen-a` | `causal-effect-estimate.strengthen-belief` requires `identification_payload_ref` to resolve and its upstream `identification_status ∈ {identified, partially-identified}`. |
| `cee-strengthen-b` | Same context: `effective_codes` must contain neither `identification-missing` nor `instrument-assumption-risk`. |
| `cee-strengthen-c` | Same context: `estimator_diagnostics` must be present. |

These three (a, b, c) are the load-bearing consumer-side rule from design line 331.

## Test outcome

14/14 pass.

| Test | Probes | Outcome |
|---|---|---|
| `test_effective_simple_auto_inject` | mr-graph-model auto-injects iar | passes — eff = {iar} |
| `test_effective_propagation_blocking_only` | causal-sufficiency-assumption (non-blocking) does NOT propagate; identification-missing (blocking) does | passes |
| `test_effective_retirement_id_resolved` | causal-identification with `identified` retires propagated identification-missing | passes |
| `test_effective_retirement_pleiotropy` | mr-analysis with mr-egger-intercept retires propagated pleiotropy-untested | passes |
| `test_effective_cycle_halts` | cyclic input_artifact_refs halts; detect_cycle finds the cycle | passes |
| `test_v13_authoring_clean` | declared codes free of auto-injects → no v1.3 violation | passes |
| `test_v13_authoring_violation` | author wrote iar by hand → v1.3-auto-inject fires | passes |
| `test_strengthen_clean` | identified upstream + clean codes + diagnostics → strengthen permitted | passes |
| `test_strengthen_blocked_by_propagated_identification_missing` | upstream pending → propagation → both cee-strengthen-a and cee-strengthen-b fire | passes |
| `test_strengthen_blocked_by_local_iar_via_mr_analysis` | mr-analysis co-load auto-injects iar locally → cee-strengthen-b fires | passes |
| `test_strengthen_missing_diagnostics` | estimator_diagnostics absent → cee-strengthen-c fires | passes |
| `test_strengthen_unresolved_id_ref` | identification_payload_ref doesn't resolve → cee-strengthen-a fires | passes |
| `test_strengthen_role_not_triggered` | validation_role: record-only → rule guard not triggered → no issues | passes |
| `test_strengthen_mr_two_stage_iar_finding` | end-to-end MR with mr-egger-intercept retires pleiotropy-untested but cee-strengthen-b STILL fires on auto-injected iar — surfaces a design ambiguity (see below) | passes (asserts the misfire) |

## What this discharges

- **Natural-systems alignment commitment, propagation half.** Cross-payload reason-code propagation, blocking-only filtering, and consumer-side rule enforcement are now decidable from the payload graph. A `causal-effect-estimate` claiming `strengthen-belief` whose upstream `causal-identification` is still `pending` is rejected at validate-time, the propagation chain producing the rejection traceable through `effective_codes`. Combined with slice 1 (structural) and slice 2 (role-permission), the t034 contract's *machinery* claim is now structurally verified for one consumer rule end-to-end. The remaining work is (a) per-extension consumer rules beyond `causal-effect-estimate.strengthen-belief`, and (b) integration into `meta/validate.sh`.
- **`[t034]` v1.3 P1.3-c (auto-injection) is decidable AND enforceable.** The `v1.3-auto-inject` rule fires when authors hand-write codes that the contribution-merger should add. The slice-2 prototype's mr-6 ("instrument-assumption-risk MUST be in core.reason_codes") is now formally retired and replaced by auto-injection at the validator level — slice 2 needs a follow-up patch to remove mr-6 and adopt the auto-injection table.
- **Retirement semantics (causal-identification → identification-missing; mr-analysis → pleiotropy-untested) are decidable.** Both retirement rules pass in isolation. The pleiotropy retirement chain works correctly end-to-end: `pleiotropy-untested` declared at stage (a), propagated to stage (b), retired by `pleiotropy_handling: mr-egger-intercept`, and absent from the consumer's `effective_codes`.
- **Cycle handling is graceful.** A cycle in `input_artifact_refs` halts recursion at the boundary and is surfaced separately by `detect_cycle`. The validator does not diverge.

## What the prototype showed about v1.3's rules

**Auto-injection has a non-trivial interaction with the consumer-side iar rule.** Test 14 (`test_strengthen_mr_two_stage_iar_finding`) is the slice-3 surprise. Setup:

- Stage (a) `mr-graph-model` declares `pleiotropy-untested` (because pleiotropy_model is silent or none-assumed). Auto-injects iar.
- Stage (b) `causal-effect-estimate + mr-analysis` co-load. mr-analysis auto-injects iar **locally on the consumer**. Pleiotropy is handled (`pleiotropy_handling: mr-egger-intercept`), retiring the propagated `pleiotropy-untested`.
- The consumer's `effective_codes` therefore contains `iar` (from local mr-analysis auto-inject) but NOT `pleiotropy-untested` (retired).
- The generic CEE strengthen rule fires on iar, rejecting strengthen-belief.

This is *technically* what the design says — line 331's parenthetical "(unless [iar] has been retired by an upstream MR diagnostic)" is the intended escape hatch but is currently underspecified:

1. The retirement is supposed to happen "by an upstream MR diagnostic," but in practice the diagnostic that retires iar is the **co-loaded mr-analysis on the same payload**, not an upstream artifact.
2. There is no formal retirement rule for iar in the v1.3 retirement table — only pleiotropy-untested has one.
3. Without that rule, iar can never be retired, so any payload co-loading mr-analysis can never strengthen-belief, even with valid pleiotropy handling. That contradicts the design's two-stage MR worked example (T34-7).

**Recommendation for v1.4:** Add the iar retirement rule explicitly:

> `mr-analysis` with `pleiotropy_handling != unhandled` AND upstream `instrument_validity_assumptions` includes `relevance` retires `instrument-assumption-risk` from `effective_codes` at the *current* payload.

This converts line 331's parenthetical from prose into a decidable rule and makes the T34-7 worked example actually validate. It also exercises a new pattern: retirement that depends on *upstream* state, not just local state — which slice 3's `_retired_by` would need to extend.

**Blocking vs non-blocking has clear validation semantics now.** The propagation pass filters `effective_codes(upstream)` to blocking codes only. This means non-blocking codes are *invisible* at the consumer's `effective_codes` even though they were declared upstream. Consumers can still inspect them via the origin chain (the design says so explicitly at line 211), but the prototype doesn't expose that — and probably shouldn't, since hiding non-blocking codes from `effective_codes` is the whole point of the blocking flag. **Sanity check passed.**

**The v1.3 P1.3-c "authors don't write auto-injected codes" rule is enforceable but creates a soft migration cost.** Existing payloads (and the worked examples in v1.2 and earlier) have `instrument-assumption-risk` and other auto-injected codes hand-written. v1.3 patched the worked examples to drop them, but any real payloads in the project carry the same issue. **Recommendation for v1.4:** the validator should *warn* (not error) for an interim period when an author writes an auto-injected code. Alternatively, silently strip + warn. The current prototype hard-errors, which would block existing payload re-validation. Pick a migration policy.

## What this prototype does NOT validate (and why)

These are scope declarations. The natural-systems commitment is now *fully* discharged for one consumer rule (`causal-effect-estimate.strengthen-belief`); generalizing to every other consumer rule is mechanical work, not a research question.

- **All other per-extension consumer rules.** Each extension has its own permitted-`validation_role` table and additional guards: `causal-prior-bundle.prioritize-attention` requires validated priors; `graph-diagnostic.prioritize-attention` requires `result: fail`; `mediation-analysis.strengthen-belief` requires `cross_world_assumption: true` and `multiplicity_correction != none` when `mediator_count > 1`; `mr-analysis.strengthen-belief` adds the iar / pleiotropy constraints. Implementing the rest is a matter of writing rule tables — no new machinery needed.
- **Multi-extension dispatch on the consumer side.** When `mr-analysis` is co-loaded with `causal-effect-estimate`, the mr-analysis rule *strengthens* (in the design's word) the generic CEE rule — meaning both must pass, and mr-analysis can additionally retire codes the generic rule rejects (the iar finding above). The dispatch policy is "intersection of permitted roles ∩ extra constraints from each loaded extension." Slice 3 enforces just the generic CEE rule; the dispatch layer is one level up.
- **Origin-chain visibility for non-blocking codes.** Per design line 211, consumers should be able to *inspect* upstream non-blocking codes even though they don't enter `effective_codes`. The prototype doesn't expose an origin-chain API. A real validator would.
- **Reference resolution beyond input_artifact_refs.** `claim_source_ref`, `causal_graph_payload_ref`, `mr_graph_payload_ref`, `audited_graph_payload_ref` etc. are all refs that need to resolve. The prototype only resolves `identification_payload_ref` (because the CEE strengthen rule reads it). A real validator would resolve all refs as part of a registry pass.
- **The "strengthen-belief on a synthesis (t023) consumer" propagation step.** Design line 338 says effective codes flow to t023 syntheses. That's downstream of t034 entirely.

## Cumulative state of the t034 validator program

After three slices:

| Slice | Target | Rules | Tests | Lines |
|---|---|---|---|---|
| 1 | `causal-graph` structural | 4 (cg-1, cg-2, cg-3, cg-3-mech) | 10 | ~210 |
| 2 | `mr-graph-model` role-permission + conditional-required | 9 (mr-1 .. mr-9) | 25 | ~360 |
| 3 | effective-codes / propagation / consumer-rule | 4 (v1.3-auto-inject + cee-strengthen-a/b/c) | 14 | ~470 |
| **Total** | | **17** | **49** | **~1040** |

Runs in <250ms total. Production validators for the remaining rules should stay in this size class.

**Discharged commitments (cumulative):**
- structural decidability (slice 1) ✓
- role-permission decidability *given effective_codes* (slice 2) ✓
- v1.2 conditional/carve-out machinery (slice 2) ✓
- effective_codes computation: declared ∪ auto_injected ∪ propagated_blocking - retired (slice 3) ✓
- one end-to-end consumer rule (`causal-effect-estimate.strengthen-belief`) (slice 3) ✓
- cycle handling (slice 3) ✓

**Outstanding (mechanical):**
- per-extension consumer rules for the other ~6 strengthening / blocking checks
- multi-extension consumer dispatch (intersection + iar-retirement-by-mr-analysis)
- origin-chain inspection API
- reference resolution as a registry pass

**Outstanding (semantic / v1.4 candidates surfaced by slice 3):** *— both adopted in v1.4 (2026-05-09)*
1. **iar retirement by mr-analysis.** ~~Add to retirement table~~ **Adopted as P1.4-a.** Retirement table now lists: `causal-effect-estimate + mr-analysis` payload with `pleiotropy_handling != unhandled` AND resolved upstream `instrument_validity_assumptions` containing `relevance` retires `instrument-assumption-risk` from `effective_codes` at the current payload. First retirement rule depending on upstream state. T34-6 stage (b) commentary updated to confirm validation. (Slice-3 finding mis-labeled this as T34-7 — actual example is T34-6 stage (b).)
2. **Auto-injected-code authoring policy.** ~~Hard-error vs warn vs silently-strip~~ **Adopted as P1.4-b: hard-error.** Validator hard-errors when authors hand-write any of the four auto-injected codes (`identification-missing`, `instrument-assumption-risk`, `mechanism-hypothesis-only`, `prior-network-dependent`). No migration window. Existing payloads carrying these by hand must be swept before slice-3 prototype folds into `meta/validate.sh`.

Plus the two carried v1.3 candidates that are now adopted into the contract:
- (slice 1 → v1.3) `graph-posterior` external edge storage rule. Adopted in v1.3 P1.3-a.
- (slice 2 → v1.3) Biconditional reading of reason-code authoring rules. Adopted in v1.3 P1.3-b.
- (slice 2 → v1.3) Auto-injection of always-on contributions. Adopted in v1.3 P1.3-c.

## Next steps

1. **Land the slice-2 prototype patch.** Drop mr-6 (the "must contain instrument-assumption-risk" rule) from the slice-2 validator; remove the code from the t01/t08/t13/t15/t21/t24 fixtures' `core.reason_codes`; add v1.3-auto-inject as a co-validator. This brings slice 2 in line with the v1.3 contract and closes the "prototype lags contract" gap noted in the v1.3 commit message (85b984c).
2. **Adopt v1.4 candidate #1 (iar retirement).** One-paragraph design patch. Should land before the next slice or before any payloads use the two-stage MR pattern.
3. **Decide auto-injected-code authoring policy.** Either hard-error (current prototype behavior) or warn-with-strip (migration-friendly). Affects when the prototypes can be folded into `meta/validate.sh` without breaking existing payloads.
4. **Fold the prototypes into `meta/validate.sh`.** Two prerequisites: (a) the auto-injected-code authoring policy decided; (b) a YAML payload-loader (currently the prototypes take Python dicts). After that, every t034 payload runs structural / role-permission / propagation rule-sets at extract-time.
5. **Then pivot.** The t034 validator-program work is feature-complete after step 4. Sister-extension work (`[t037]` agent-ops, `[t023]` synthesis) is the next natural target.

**The natural-systems "asserted vs verified" commitment is now fully discharged for `[t034]` machinery.** All three layers (structural rules, role-permission rules, cross-payload propagation) are decidable from payload state and enforced by runnable validators. The remaining work to make this *production-active* (steps 1–4 above) is mechanical, not research.

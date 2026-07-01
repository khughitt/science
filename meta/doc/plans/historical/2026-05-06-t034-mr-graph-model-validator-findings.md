# t034 v1.2 `mr-graph-model` Validator Prototype — Findings

> **Status:** Findings (2026-05-06). Companion to the validator script at `meta/doc/plans/historical/2026-05-06-t034-mr-graph-model-validator-prototype.py`. Reports what the second prototype slice exercises and what it surfaced about the role-permission machinery.
>
> **Goal:** discharge the load-bearing half of the natural-systems alignment commitment for `[t034]` — prove that role-permission rules (`validation_role` × extension state × `effective_codes`) and the v1.2 conditional-required-field machinery are decidable from a single payload's content.
>
> **Position in the program:** second of three planned validator slices. First slice (`causal-graph` structural rules) at `meta/doc/plans/historical/2026-05-06-t034-causal-graph-validator-prototype.py` and findings at `meta/doc/plans/historical/2026-05-06-t034-validator-prototype-findings.md`. Third slice (cross-payload reason-code propagation) is unbuilt.

## What the prototype implements

Nine rules from `[t034]` v1.2's `mr-graph-model` spec:

| Rule  | Kind | Statement |
|-------|------|-----------|
| mr-1  | structural | `graph_object_type` ∈ {CPDAG, DAG, graph-posterior} (mr-graph-model's narrower slice) |
| mr-2  | role-permission | `validation_role` ∈ {prioritize-attention, record-only}; forbids strengthen-belief / gate-update / quality-record-only |
| mr-3  | structural | co-required extensions {causal-graph, statistical-uncertainty} present |
| mr-4  | required-field | always-required: exposure_set, outcome_set, instrument_validity_assumptions, pleiotropy_model, direction_constraint, graph_object_type |
| mr-5  | conditional-required | instrument_set, summary_statistic_provenance — required UNLESS extracted-from-summary-only ∈ effective_codes |
| mr-6  | semantic | instrument-assumption-risk MUST be declared whenever extension is loaded |
| mr-7  | semantic biconditional | pleiotropy-untested ↔ pleiotropy_model ∈ {none-assumed, not-modelled} |
| mr-8  | semantic biconditional | pleiotropy-unspecified ↔ pleiotropy_model = unspecified |
| mr-9  | semantic biconditional | reverse-causation-assumed ↔ (direction_constraint = exposures-to-outcomes-only AND direction-inherent-from-iv-class ∉ instrument_validity_assumptions) |

**Effective-codes scope.** For stage-(a) primary payloads, the prototype treats `effective_codes := core.reason_codes`. That's correct *for stage-(a) without upstream `input_artifact_refs`* but wrong in general. The third prototype slice handles the cross-payload propagation case.

## Test outcome

25/25 tests pass. Coverage by rule:

| Rule | Positive | Negative | Adapted-pilot |
|---|---|---|---|
| mr-1 | tc01 | tc22 | tc24 (graph-posterior) |
| mr-2 | tc01, tc05 | tc02, tc03, tc04, tc25 | tc25 (Zuber strengthen attempt) |
| mr-3 | tc01 | tc06 | tc24 |
| mr-4 | tc01 | tc11 | tc24 |
| mr-5 | tc08, tc09 | tc07, tc10 | tc24 |
| mr-6 | tc01 | tc21 | tc24 |
| mr-7 | tc13, tc14 | tc12 | — |
| mr-8 | tc15, tc17 | tc16 | tc24 (correct unspecified) |
| mr-9 | tc19, tc20 | tc18 | tc24 (carve-out engaged) |

Special tests:
- **tc02** is the load-bearing natural-systems case: `validation_role: strengthen-belief` on a stage-(a) MR posterior. The validator rejects at extract-time.
- **tc08, tc09** confirm the v1.2 P-pilot-1 relaxation gate: omitting `instrument_set` or `summary_statistic_provenance` is permitted iff `extracted-from-summary-only ∈ effective_codes`.
- **tc11** confirms the gate is *narrow*: it relaxes only the listed conditional fields, not always-required ones.
- **tc24** is an end-to-end adapted Zuber pilot exercising the full v1.2 surface: paper-summary-only relaxation gate, pleiotropy-unspecified carve-out, direction-inherent-from-iv-class carve-out — all engaged simultaneously, payload passes.

## What this discharges

- **Natural-systems alignment commitment, role-permission half.** mr-2 enforces the design's strongest claim: a stage-(a) MR posterior cannot strengthen belief, regardless of how confident the author is or how many priors got loaded. An extractor that writes `strengthen-belief` on an `mr-graph-model` payload is rejected at validate-time, not flagged in prose. The "asserted vs verified" gap is closed *for this rule*.
- **`[t034]` v1.2 conditional-required-field machinery (P-pilot-1) is decidable.** mr-5 fires correctly across the four-cell matrix (field-present × code-present). The relaxation gate works as designed: it makes the paper-summary case *authorable* without making the strict case *forgiving*.
- **`[t034]` v1.2 pleiotropy carve-out (P-pilot-2) is decidable.** mr-7 / mr-8 distinguish blocking `pleiotropy-untested` (author chose not to model pleiotropy) from non-blocking `pleiotropy-unspecified` (extractor doesn't know what was modelled) at validate-time, biconditionally — the validator rejects both under-declaration *and* over-declaration.
- **`[t034]` v1.2 direction-inherent carve-out (P-pilot-7) is decidable.** mr-9 correctly suppresses the `reverse-causation-assumed` requirement when the IV class biologically constrains direction.

## What the prototype showed about v1.2's rules

**Most rules are decidable from a single payload — but the boundary is `effective_codes`.** Every rule encoded here lives on a single payload's content, including its own `core.reason_codes`. The first prototype already established this for *structural* rules; the second extends it to *role-permission* rules. The wall the prototype runs into is `effective_codes` itself: when stage-(a) primaries reference upstream payloads (e.g., a `causal-prior-bundle` providing `prior-network-dependent`), the role-permission rules need cross-payload state. That's the third prototype slice's job, not this one's. The honest framing: this slice validates rules that are decidable *given* effective_codes, leaving the propagation closure to the next slice.

**The biconditional reading of reason-code authoring rules is the right one.** The design doc says "declared when X" for `pleiotropy-untested` / `pleiotropy-unspecified` / `reverse-causation-assumed`. The prototype interprets this as a biconditional ("declared if and only if X"). This is a strict reading — a permissive reading would only enforce "must declare when X" and tolerate "may declare when not-X." The strict reading is correct because reason codes encode falsifiable claims about the payload's epistemic state; declaring `pleiotropy-untested` when pleiotropy is in fact handled (e.g., `mr-egger`) is a category error, not a free-form note. **Recommendation for v1.3:** add a single sentence to the design doc making this explicit ("reason codes that encode payload state are biconditional; over-declaration is as much an error as under-declaration").

**`instrument-assumption-risk` ambiguity — authoring vs auto-declaration.** The design says `mr-graph-model` "declares" `instrument-assumption-risk` always when the extension is loaded. The prototype treats this as a *required authoring rule* (must appear in `core.reason_codes`). But "declares" could also mean "the extension implicitly contributes this code at validate-time, the author doesn't need to write it." This matters for ergonomics: if every `mr-graph-model` payload must include `instrument-assumption-risk` literally, that's noise; if the validator auto-injects it, payloads stay clean. **Recommendation for v1.3:** decide and document. The natural choice is *auto-injection by the extension's contribution table*; the author writes only the *conditional* codes (pleiotropy-*, reverse-causation-assumed, extracted-from-summary-only). This would also clean up `causal-discovery-run` (which has the parallel `causal-sufficiency-assumption` always-declared rule) and other extensions.

**The `quality-record-only` permission is asymmetric across extensions and that's correct.** mr-2 forbids `quality-record-only` on `mr-graph-model` because it's a graph-construction posterior, not a quality artifact; `graph-diagnostic` *requires* `quality-record-only` as the maximum permitted role because diagnostics ARE quality artifacts. This asymmetry held up under tests — different extensions get different role tables, and the rule lookup is per-extension. No consolidation needed.

## What this prototype does NOT validate (and why)

These are scope declarations for future slices, not implementation gaps:

- **Cross-payload reason-code propagation.** A stage-(a) `mr-graph-model` payload that references a `causal-prior-bundle` via `input_artifact_refs` should inherit codes (e.g., `prior-network-dependent`) into its `effective_codes`. Mr-2 / mr-7 / mr-9 read `effective_codes`, but the prototype currently equates that to `core.reason_codes`. The third slice should compute the proper closure with cycle detection.
- **Stage-(b) downstream propagation.** Per the design, `pleiotropy-untested` (blocking) propagates from stage (a) to any consumer `causal-effect-estimate` referencing this graph; the consumer's strengthen-belief rule then rejects. This is a *consumer-side* rule on `causal-effect-estimate + mr-analysis`, not on `mr-graph-model` itself. A fourth slice (or an extension of slice 3) would handle it.
- **Multi-extension dispatch / co-required closure.** The prototype checks `causal-graph` and `statistical-uncertainty` are listed in `core.extensions`, but doesn't validate that each one's *own* rules pass. A real validator would dispatch each extension's rule-set in turn.
- **Reference resolution.** `summary_statistic_provenance` is a `ref` — the prototype only checks presence, not that the target exists. Reference resolution is core-validator territory.

## Cumulative state of the t034 validator program

After two slices:

- **Implemented and decidable from single-payload state:** four structural rules on `causal-graph`; nine rules on `mr-graph-model` (one structural enum, one role-permission, one co-required, two required-field, one always-on semantic, three biconditional semantics).
- **Discharged commitments:** structural-rule decidability (slice 1); role-permission decidability *given effective_codes* (slice 2); v1.2 conditional-required-field decidability (slice 2); v1.2 biconditional carve-outs decidable (slice 2).
- **Outstanding (slice 3+):** cross-payload reason-code propagation; downstream blocking-code retirement (e.g., `mr-analysis` retiring `pleiotropy-untested`); core-level multi-extension dispatch.
- **v1.3 candidates surfaced so far:**
  1. (slice 1) `graph-posterior` permitted edge-roles — add `posterior_summary_edge` or document external storage.
  2. (slice 2) Biconditional reading of reason-code authoring rules — add explicit sentence to design.
  3. (slice 2) `instrument-assumption-risk` (and parallels) — auto-inject vs author-must-declare; pick one.

The two prototypes together are ~430 lines of Python and run in <200ms across 35 tests. Production validators for the remaining rules should stay in this size class.

## Next steps

1. **Slice 3: cross-payload reason-code propagation.** Smallest non-trivial test: `causal-discovery-run` with `identification-missing` (blocking), referenced by a `causal-effect-estimate` declaring `validation_role: strengthen-belief`. The validator should compute `effective_codes` at the consumer including the inherited blocking code and reject the strengthen claim. This unblocks: real `effective_codes` for slices 1 and 2; consumer-side `pleiotropy-untested` retirement at `mr-analysis`.
2. **Adopt v1.3 candidate (2)** — append the biconditional-reading sentence to the design doc. This is a one-line patch that makes the strict reading authoritative.
3. **Resolve v1.3 candidate (3)** before authoring more payloads — auto-injection is the cleaner answer; if adopted, the prototype's mr-6 rule moves from "validate the payload contains it" to "the validator's contribution-merging step adds it." This also tightens slice 3's effective_codes definition (declared codes ∪ extension-contributions ∪ propagated codes).
4. **Once slice 3 lands, fold all three prototypes into `meta/validate.sh`.** Production behavior: every t034 payload runs the structural / role-permission / propagation rule-sets at extract-time, no hand-waving.

The natural-systems "asserted vs verified" commitment is now half-discharged for `[t034]`. The remaining half — propagation closure — is one prototype away.

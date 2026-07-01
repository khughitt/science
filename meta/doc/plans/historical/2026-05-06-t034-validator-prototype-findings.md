# t034 v1.2 Validator Prototype — Findings

> **Status:** Findings (2026-05-06). Companion to the validator script at `meta/doc/plans/historical/2026-05-06-t034-causal-graph-validator-prototype.py`. Reports what the prototype validator pressure-tested and what it surfaced about rule decidability.
>
> **Goal:** discharge the natural-systems alignment commitment (recorded in `[t034]` v1.1 — "validation rules must be implemented as enforcing runners, not just docs") for one extension's structural rules. Prove the rules are decidable from payload state. Surface gaps where they aren't.

## What the prototype implements

The `validate_causal_graph(payload)` function enforces four rules from `[t034]` v1.2:

- **rule-cg-1** — `graph_object_type` is required and must be one of the strict enum values `{DAG, CPDAG, PAG, ADMG, equivalence-class-feature, candidate-graph, graph-posterior}`.
- **rule-cg-2** — for each edge, `epistemic_role` must be in the per-`graph_object_type` permitted set per the Edge-Role Taxonomy table.
- **rule-cg-3** — promotion-only roles (`identified_causal_effect`, `mediation_path`, `mr_instrumental_effect`) are never authored in-place; they are recorded by a downstream payload via reference.
- **rule-cg-3-mech** — `epistemic_role: mechanistic_hypothesis` is allowed in-place only when the payload's primary extension is `mechanistic-hypothesis-bundle`.

All four are *structural* rules — decidable from a single payload's content (with the primary-extension lookup) without consulting upstream payloads, the t025 registry, or runtime state.

## Test outcome

10/10 tests pass. The test set covers:

| Test | Probe | Outcome |
|---|---|---|
| 01-valid-cpdag | positive case (CPDAG with discovered + assumed edges) | no issues |
| 02-cpdag-with-mechanistic-edge | wrong graph_object_type for role | rule-cg-3-mech fires |
| 03-mhb-with-mechanistic-edge | mechanistic_hypothesis in mechanistic-hypothesis-bundle | no issues |
| 04-discovery-run-with-mechanistic-edge | mechanistic_hypothesis with wrong primary | rule-cg-3-mech fires |
| 05-cpdag-with-identified-edge | promotion-only role authored in-place | rule-cg-3 fires |
| 06-unknown-got | leaked v1.0 'mechanistic' graph_object_type | rule-cg-1 fires |
| 07-missing-got | required field missing | rule-cg-1 fires |
| 08-graph-posterior-empty-edges | adapted Zuber pilot — no edges, valid type | no issues |
| 09-no-causal-graph-extension | adapted Faller pilot — extension absent | no issues (correctly not applied) |
| 10-dugourd-adapted | adapted Dugourd pilot — mechanistic edges in MHB | no issues |

Negative cases (02, 04, 05, 06, 07) all fire the expected and only the expected rule. Positive cases (01, 03, 08, 09, 10) all pass cleanly. The recently-added adapted-pilot cases (08, 10) confirm that the structural rules accommodate the messy real-world cases the pilot extraction surfaced.

## What the prototype does NOT validate (and why)

These are not implementation gaps; they are scope declarations that should be honored by future validator slices.

- **Role-permission rules (`validation_role` × `validation_status` × `effective_codes`).** Not in this prototype — these rules cross extensions (each extension declares its own `validation_role` permission table) and depend on `effective_codes` computation, which requires reason-code propagation across `input_artifact_refs`. A second prototype scoped to one primary extension (`mr-graph-model` would be a good next target — most rules, recently extended in v1.2) is the right next step.
- **Reason-code propagation.** Not in this prototype — requires a multi-payload graph traversal with cycle detection. Per-payload structural rules don't need it.
- **Conditional required-fields gated by `extracted-from-summary-only` (P-pilot-1).** Not in this prototype — the rules under scope here (cg-1 through cg-3-mech) are unconditional. The conditional rules live on the *primary* extensions (`mr-graph-model.instrument_set`, `mechanistic-hypothesis-bundle.coherent_subnetwork_size`, etc.), which a primary-extension validator would handle.
- **Multi-extension dispatch and co-required closure.** Not in this prototype — the `causal-graph` extension is rarely the primary, so it doesn't drive co-required-extension validation. A core-level validator would.
- **Cross-payload reference resolution.** The "promotion-by-reference" rule (cg-3) is enforced *negatively* here ("you can't author this role in-place") but not *positively* ("a `causal-identification` payload referencing the right (graph, edge) is sufficient to declare the edge identified"). The positive direction is a join across payloads — out of scope for a structural validator.

## What the prototype showed about v1.2's rules

**The structural rules are decidable.** All four enforce-able from a single payload, no joins, no registry lookups (the rules' enums and the edge-role compatibility table are baked into the validator code, but they correspond directly to the design doc's tables).

**One small ambiguity surfaced — `graph-posterior` permitted edge-roles.** The design doc's Edge-Role Taxonomy table for `graph-posterior` says `llm_prior_edge` is permitted "via prior" — meaning data-discovered edges in a posterior are summarized into edge_inclusion_probability rather than enumerated. The prototype encodes this as `{llm_prior_edge}` only. But Test 8 (adapted Zuber) uses `graph-posterior` with `edges: []` — passes only because there are no edges to validate. If a graph-posterior payload *did* enumerate posterior-summary edges, there's no clean role for them in the current taxonomy. **Recommendation for v1.3:** either explicitly add a `posterior_summary_edge` epistemic role to the enum and to the per-graph-type permission table, or document that `graph-posterior` payloads must store edges externally (in `graph_artifact_path`) and never enumerate them in the YAML. The latter matches Example T34-6's actual usage.

**The `mechanistic_hypothesis` rule depends on knowing the primary extension.** Only one rule does — but it required threading the primary extension through the validator. This is fine; the validator function takes the full payload, not just the extension content. Future validators that depend on cross-extension state (most of the role-permission rules) will use the same pattern.

**The promotion-only rule (cg-3) is the cleanest test of v1.1's F5 fix.** If the F5 fix had not landed and `identified_causal_effect` were still authorable in-place, Test 5 would silently pass and create a duplicate identification record. The structural rule prevents this at extract-time.

## What this discharges

- **Natural-systems alignment commitment, partial.** One extension's structural rules are now enforceable at validate-time. The remaining commitment — role-permission rules across all extensions — needs further prototype slices.
- **`[t034]` v1.1 audit prompt #3** ("Validation rules are enforceable from the contract") — yes, for the structural-rule subset. Confirms the rules in the design doc are not just prose.

## Next steps

1. **Second prototype slice: `mr-graph-model` role-permission rules.** This exercises validation_role × pleiotropy_model × extracted-from-summary-only conditional dependencies. Surfaces decidability for the v1.2 conditional-required-field machinery.
2. **Third prototype slice: cross-payload reason-code propagation.** Smallest non-trivial test: a `causal-discovery-run` declaring `identification-missing` (blocking), referenced by a `causal-effect-estimate` declaring `validation_role: strengthen-belief`. The validator should compute `effective_codes` at the consumer including the inherited `identification-missing` and reject the strengthen claim.
3. **If both pass, fold the validators into `meta/validate.sh`** — turn the prototypes into production checks. The natural-systems "asserted vs. verified" commitment then propagates to every payload authored against this contract.
4. **Add a YAML-input mode.** Currently the prototype takes Python dicts. A real validator should take YAML files (the actual payload format) — trivial extension via PyYAML.

The prototype is ~210 lines of Python and runs in <100ms on 10 tests. Production validators for the remaining rules should stay in this size class — if any single-extension validator grows beyond ~500 lines, the rule design has overcomplicated itself.

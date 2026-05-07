# Chain-Audit Verdict Entity — Design Sketch

**Status.** Design sketch (2026-05-07). Extends `2026-05-03-epistemic-dependency-graph-design.md` Phase 1 (`bears_on` + freshness, `[t010]` done) to cover chain-shaped audit verdicts. Source of the gap: natural-systems stress test recorded in `interpretation:2026-05-07-t473-decomposition-stress-test`.

**Revision note.** Findings 1–5 from internal code review applied: `title` field corrected, `bears_on.target_kinds` extension made explicit, validator enforcement surfaces corrected, reference-resolution audit coverage made explicit for new fields, and ordered-chain serialization committed (`sci:linkSequence` RDF list + flat `sci:hasLink` triples). Verdict-block integration with the existing `verdict/parser.py` surface added.

## Motivation

Phase 1 of the epistemic dependency graph (`bears_on` + freshness) assumes that the relationships an audit verdict depends on are encoded as graph edges. The natural-systems stress test surfaced a class of audit verdicts whose dependencies are *structural chains* (e.g., "particle-advection → Fokker-Planck → heat-equation") and which today are encoded only as test sentinels and hardcoded counts in source code. The dependency exists in the codebase but never enters the graph. When a load-bearing intermediate (FP) was removed, the freshness machinery had no way to flag the verdict as needs-review; the only signal was a brittle test failure indistinguishable from snapshot drift.

This design promotes structural chains and their audit verdicts to first-class graph entities so the existing `bears_on` machinery propagates freshness automatically. The change is additive — no schema changes to existing entities — but it does require two targeted extensions to existing relation/validator surfaces (documented in the file-touch list).

The need is cross-domain: physics, geochemistry, and cancer-mechanism work all carry chain-shaped findings ("model A is realized by mechanism B which approximates phenomenon C"). The framework-level fix lives here so each downstream project doesn't reinvent it.

## Architecture

Two new EPISTEMIC entity kinds and two new relation kinds. Plus targeted extensions to existing surfaces for `bears_on.target_kinds`, model validation, materialization endpoint validation, and reference auditing.

```
   structural-chain ──audits──◂── chain-audit
        │                              │
        │ has_link (ordered)           │ verdict (composite token)
        ▼                              │ bayes_factor_evidence
   ┌────┴────┬─────┬─────┬───────┐     │ (hypothesis_ref, null_baseline,
   ▼         ▼     ▼     ▼       ▼     │  bf10, interpretation)
mechanism  model  prop  obs  finding   │
   │         │     │     │       │     │
   └─────────┴──bears_on──┴───────┘     │
                  ▼                     │
            structural-chain ── bears_on ─▶ chain-audit
```

### New entity kinds

- **`structural-chain`** (EPISTEMIC). Holds an ordered list of ≥2 entity refs that constitute a structural decomposition claim. Reusable: multiple chain-audits can audit the same chain over time.
- **`chain-audit`** (EPISTEMIC). Verdict-bearing entity carrying both (a) a `verdict:` block compatible with the existing `verdict/parser.py` surface and (b) `bayes_factor_evidence:` for the BF-style framing. Single-target by convention (one audit, one chain); multi-chain audits use multiple chain-audit entities.

Both kinds inherit `EpistemicReviewState`, so `entity review`, freshness propagation, and Phase-2 weighted sampling work without extra wiring.

### New relation kinds

- **`has_link`** (predicate `sci:hasLink`). Source: `structural-chain`. Targets: `mechanism`, `model`, `proposition`, `observation`, `finding`. Order is carried by an accompanying `sci:linkSequence` RDF list (see "Ordered serialization" below).
- **`audits`** (predicate `sci:audits`). Source: `chain-audit`. Target: `structural-chain`. Symmetric in shape with `tests` (task/experiment/workflow-run → hypothesis/question).

### Auto-derivation rules (added to `freshness.py`)

| Direct rule | Derived `bears_on` |
|---|---|
| `structural-chain has_link X` | `X bears_on structural-chain` (inverse) |
| `chain-audit audits structural-chain` | `structural-chain bears_on chain-audit` (mirrors `tests`) |

The existing transitive closure (`close_bears_on`) then derives `X bears_on chain-audit` for every link X. No changes to `derive_freshness` — it already walks every `bears_on` triple.

### Pipeline insertion

Add the two new derivation stages to the existing `freshness.py` pipeline **before** `close_bears_on`, **after** `derive_bears_on_from_typed_edges`. Closure picks up the new triples automatically.

### Ordered serialization

Materialization emits two parallel forms for each chain:

1. Flat `chain sci:hasLink link_i` triples — set-shaped, easy to query ("does X appear in this chain?").
2. An RDF list `chain sci:linkSequence ( link_1 link_2 link_3 )` — order-preserving via `rdf:first`/`rdf:rest`/`rdf:nil`.

Both are emitted by `materialize.py` from the frontmatter `chain:` field. The `sci:hasLink` triples drive `bears_on` derivation; the `sci:linkSequence` triples carry order so a reorder of the same link set produces a different materialized graph (different `rdf:rest` chain). Freshness propagation remains date-based over `bears_on`, so authors must advance the structural-chain entity's `updated:` date when a link edit or reorder should make downstream audits `needs-review`.

## Frontmatter schemas

### `structural-chain`

```yaml
---
id: chain:particle-advection-fp-heat-equation
kind: structural-chain
title: "Particle advection → FP → heat equation"     # required (Entity.title)
project: natural-systems
created: 2026-05-07
updated: 2026-05-07
chain:                   # ordered; ≥2 distinct refs required
  - mechanism:particle-advection
  - mechanism:fokker-planck
  - model:heat-equation
description: |
  Structural decomposition claim: particle advection is realized by
  the Fokker-Planck operator, which under <conditions> reduces to
  the heat equation.
review_state:
  last_reviewed: ~
---
```

### `chain-audit`

```yaml
---
id: chain-audit:fp-coupling-2026-05
kind: chain-audit
title: "FP-coupling load-bearing audit (2026-05)"     # required (Entity.title)
project: natural-systems
audits: chain:particle-advection-fp-heat-equation     # → sci:audits triple
created: 2026-05-07
updated: 2026-05-07
proposition_refs: [proposition:fp-heat-equivalence]
verdict:                                              # parsed by verdict/parser.py
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:fp-coupling-load-bearing
      polarity: "[-]"
      strength: load-bearing
      evidence_summary: |
        Removing FP eliminates the coupling that carries advection
        statistics into a diffusion limit.
bayes_factor_evidence:
  hypothesis_ref: hypothesis:fp-coupling-load-bearing
  null_baseline: "uniform random link substitution"
  bf10: ~                                             # optional; ~ when only categorical
  interpretation: evidence-against                    # evidence-for | evidence-against | mixed | inconclusive
rationale: |
  Removing FP from the chain eliminates the coupling that
  carries advection statistics into a diffusion limit.
review_state:
  last_reviewed: ~
---
```

### Verdict-block integration

`chain-audit` participates in the existing `verdict/parser.py` rollup surface. The `verdict:` block is **required** alongside `bayes_factor_evidence:`, with a fixed mapping the validator enforces (no drift between the two blocks).

Mapping `bayes_factor_evidence.interpretation` → `verdict.composite` (Token):

| Interpretation | Composite token |
|---|---|
| `evidence-for` | `[+]` POSITIVE |
| `evidence-against` | `[-]` NEGATIVE |
| `mixed` | `[~]` MIXED |
| `inconclusive` | `[?]` INCONCLUSIVE |

The t037 enum value `evidence-for-risk` is **dropped** from chain-audit's interpretation set: it carries risk-framing semantics that don't map cleanly to a predicted-direction-agnostic token. If a future chain audit needs risk framing, it should be authored through t037-style payloads, not chain-audit.

The verdict block's `claims[*].id` may follow the existing project claim registry convention; single-claim chain-audits typically reuse `bayes_factor_evidence.hypothesis_ref` as the claim id when no separate registry entry exists. Current model validation enforces token-mapping consistency between `verdict.composite` and `bayes_factor_evidence.interpretation`.

## Freshness propagation cases

| Change | Mechanism | Result |
|---|---|---|
| Chain link entity content updates (e.g. `mechanism:fp` edited) | existing `updated` comparison via `link bears_on chain` | chain → needs-review; chain-audit → needs-review |
| Chain shape edited — link added/removed | structural-chain entity's `updated` date advances + new/missing `sci:hasLink` triple | chain-audit → needs-review |
| Chain shape edited — links reordered, same set | structural-chain entity's `updated` date advances + changed `sci:linkSequence` RDF list | chain-audit → needs-review via date-based `bears_on` comparison |
| New chain-audit created against existing chain | chain-audit's own freshness baseline | clean state until link/chain changes |
| Atomic-decomposition (A→C becomes A→B→C in *another* chain) | not handled here | refinement C, separate task |

**Broken refs.** If a chain link's target entity is deleted, the chain has a dangling ref. The existing `audit_project_sources()` in `migrate.py` does **not** automatically pick up new frontmatter fields — it iterates over an explicit named-field list (`related`, `commits_to`, `source_refs`, `evidence_refs`, `same_as`, plus authored relation endpoints). This design adds explicit audit branches for `chain[]`, `audits`, and `proposition_refs[]` (file-touch list below), so dangling refs in those fields surface in the standard audit output. Normal `graph build` fails before freshness/materialization when `audit_project_sources` reports unresolved references.

## Validation and enforcement surfaces

Enforcement is split across the implemented surfaces: Pydantic models validate entity frontmatter shape, the core relation profile and `materialize.py` endpoint validation enforce relation contracts, `bears_on.target_kinds` admits the new epistemic targets, and `audit_project_sources` reference auditing checks the new authored refs.

**Chain shape:**
1. `structural-chain.chain` is required, ordered, with ≥2 distinct refs.
2. Each `chain[i]` resolves to a registered entity.
3. Each chain link's resolved entity has `kind ∈ {mechanism, model, proposition, observation, finding}`.
4. No duplicate authored refs in `chain` (raw string equality in the Pydantic model); materialization resolves refs before emitting triples.

**Chain-audit shape:**
5. `chain-audit.audits` is required and resolves to a `structural-chain`.
6. `bayes_factor_evidence` is required when `kind == chain-audit`. Sub-fields:
   - `hypothesis_ref` required as a string field; current reference auditing does not resolve or kind-check it.
   - `interpretation ∈ {evidence-for, evidence-against, mixed, inconclusive}`.
   - `bf10` optional; when present, must be a positive number.
   - `null_baseline` required (free string ≥ 1 char).
7. `proposition_refs[]`: current reference auditing checks that each ref resolves; it does not kind-check resolved refs as `proposition`.

**Verdict-block consistency:**
8. `chain-audit.verdict.composite` is required by model validation.
9. `verdict.composite` matches `bayes_factor_evidence.interpretation` per the mapping table. Mismatch is a hard error, not a warning — drift between the two blocks defeats integration.

**Relation contracts:**
10. `has_link` source must be `structural-chain`; targets in the kind allowlist (mirror of #3).
11. `audits` source must be `chain-audit`; target must be `structural-chain`.

**`bears_on` target_kinds extension (required, not "no change"):**
12. `bears_on.target_kinds` in `core.py` must include `structural-chain` and `chain-audit`. Authored-relation validation (`materialize.py` `relation_allows_kinds`) reads the profile's `target_kinds`, not the registry's `EntityClass`. Without this entry, hand-authored `bears_on` edges to the new kinds would be rejected even though both kinds are EPISTEMIC at the registry layer.

## Migration

**Zero-touch for downstream entities.** No existing entity, edge, or validator rule on existing kinds is modified. Downstream projects (myeloma, natural-systems) continue to validate without edits. First `graph build` after this lands emits no new triples until a project authors a `structural-chain` or `chain-audit` entity.

**Authoring path for natural-systems' particle-advection→FP→heat-equation case:**

1. Author/confirm `mechanism:particle-advection`, `mechanism:fokker-planck`, `model:heat-equation` entities exist (one-time registration cost).
2. Author `chain:particle-advection-fp-heat-equation` with the three refs.
3. Author `chain-audit:fp-coupling-2026-05` with `audits: chain:...`, the verdict block (`composite: "[-]"`, `single-claim` rule), `bayes_factor_evidence.interpretation: evidence-against`, and rationale citing the 3c finding.
4. The pre-existing test `expect(byChain.get('particle-advection→FP→heat-equation')?.auditVerdict).toBe('invalid')` becomes redundant *for dependency-tracking purposes* — the graph carries the dependency. The test can stay as a sanity check but is no longer the only signal.

## File touch list (Phase 1)

| File | Change |
|---|---|
| `science/model/src/science_model/entities.py` | Add `StructuralChainEntity`, `ChainAuditEntity`, `BayesFactorEvidence` models. Both entities inherit the existing `Entity.title` requirement (no new title-aliasing). |
| `science/model/src/science_model/profiles/core.py` | (a) Register `structural-chain`, `chain-audit` kinds. (b) Add `has_link`, `audits` `RelationKind`s. (c) **Append `structural-chain` and `chain-audit` to `bears_on.target_kinds`.** |
| `science/src/science_tool/graph/entity_registry.py` | `register_core_kind` calls for both kinds with `entity_class=EPISTEMIC` |
| `science/src/science_tool/graph/freshness.py` | Add `derive_bears_on_from_chain_links` + `derive_bears_on_from_audits`; wire into pipeline before `close_bears_on` |
| `science/src/science_tool/graph/materialize.py` | Emit `sci:hasLink` (flat) **and** `sci:linkSequence` (RDF list) triples from frontmatter `chain:`; emit `sci:audits` triple from `audits:` field |
| `science/src/science_tool/graph/migrate.py` | Extend `_audit_entity` with explicit audit branches for `chain[]`, `audits`, `proposition_refs[]` (mirrors existing `related`/`commits_to`/`source_refs` branches) |
| `science/src/science_tool/verdict/...` | If chain-audit verdict blocks need any kind-specific handling beyond what `parser.py` already provides for interpretation files, extend; otherwise no change. |
| `science/model/tests/test_chain_entities.py` | New: frontmatter shape tests |
| `science/tests/test_chain_bears_on.py` | New: `bears_on` derivation + closure tests |
| `science/tests/test_chain_kinds_registered.py` | New: core kind registration tests |
| `science/model/tests/test_chain_relations.py` | New: relation-kind registration tests |
| `science/tests/test_chain_materialize.py` | New: `sci:hasLink`, `sci:audits`, and `sci:linkSequence` materialization tests |
| `science/tests/test_chain_audit_references.py` | New: reference-audit coverage for `chain[]`, `audits`, and `proposition_refs[]` |
| `science/tests/test_chain_freshness_integration.py` | New: end-to-end freshness propagation coverage |
| `docs/claim-and-evidence-model.md` | Brief section on chain-audit semantics and the verdict↔BF dual-block convention |

## Testing strategy

Three layers, mirroring the Phase 1 epistemic-dependency design.

### 1. `science-model` unit tests

- `test_chain_entities.py`: `StructuralChainEntity` validates ≥2 chain links, list-of-refs shape, `EpistemicReviewState` accepted, and **`title` required and rejected when missing**.
- `test_chain_entities.py`: `ChainAuditEntity` validates `audits` ref present, `bayes_factor_evidence` sub-shape (required string `hypothesis_ref`, interpretation enum incl. `mixed` and excl. `evidence-for-risk`, bf10 positivity when set, null_baseline non-empty), required `verdict.composite`, and composite-to-BF interpretation consistency.
- `test_chain_entities.py`: `BayesFactorEvidence` model serialization round-trip; rejects unknown interpretation values.
- `test_chain_relations.py`: `has_link` and `audits` `RelationKind`s are registered with correct source_kinds / target_kinds.
- `test_bears_on_relation.py`: `bears_on.target_kinds` includes `structural-chain` and `chain-audit` after registration.

### 2. Registry + graph + derivation tests

- `kind_class("structural-chain") == EPISTEMIC`; same for `chain-audit`.
- `derive_bears_on_from_chain_links`: chain with 3 links emits 3 `link bears_on chain` edges.
- `derive_bears_on_from_audits`: chain-audit emits `chain bears_on chain-audit`.
- `bears_on.target_kinds` extension: hand-authored `mechanism bears_on structural-chain` and `structural-chain bears_on chain-audit` are accepted by `relation_allows_kinds`.
- Materialization emits both `sci:hasLink` (flat, count = N) and `sci:linkSequence` (RDF list head + N-1 rest cells + nil).
- **Reorder serialization regression:** swap positions of links 1 and 3 with same set; assert materialized `sci:linkSequence` triples differ.
- Transitive closure: edit `mechanism:fp.updated`, rebuild, assert `chain-audit` has `freshness.state == needs-review` and `triggered_by` includes `mechanism:fp` (via the closed chain).

### 3. CLI + audit integration tests

- Model and relation tests cover the implemented structural-chain and chain-audit validation rules, including the verdict-BF mismatch case where `composite: "[+]"` with `interpretation: evidence-against` is rejected.
- `_audit_entity` covers chain/audits/proposition_refs: dangling ref in any of the three new fields produces an audit row; `proposition_refs` auditing checks resolution only.
- End-to-end graph smoke: temp project with one chain + one chain-audit + one mechanism link -> materialize graph -> `graph validate --format json` passes for the well-formed case.
- Dangling-chain smoke: a malformed chain link is reported through the public `audit_project_sources` audit surface before graph build/freshness/materialization.

**Quality gates.** ruff + pyright + pytest. Downstream projects unmodified — no regressions in their builds.

## Out of scope (deferred)

- **Per-link verdict assessments.** Chain-audit currently carries an overall BF + verdict only. If real chains need per-link `link_assessments: [{ref, verdict, note}]`, extend later.
- **Atomic-decomposition migration prompt** (refinement C). When an upstream A→C edge is replaced by A→B→C, prompt authors to consider whether existing chains containing A→C need updating. Separate task.
- **Test→entity binding helper** (refinement B). A `expectAuditVerdict(chain, verdict, { boundTo: [...] })` helper that registers test assertions as bound entities. Closes the "test failure indistinguishable from snapshot drift" gap directly. Separate task.
- **Cross-project chain reuse.** A chain authored in one project audited from another project requires cross-project entity resolution. Federation work; tracked under the federation workstream.
- **Risk-framed chain audits.** `evidence-for-risk` is intentionally not in chain-audit's interpretation enum. If load-bearing for real chain-audit cases, revisit later with a clean predicted-direction-aware mapping.

## Decisions (resolved 2026-05-07)

1. **Two new kinds, not one bundled kind.** `structural-chain` is separate from `chain-audit` so chains can be reused across multiple verdicts and over time. Bundling would have made every audit re-author the chain.
2. **Strict registration discipline for chain links.** Every link must be a registered project entity ref. Forces dependencies into the graph by construction; refuses the "label-only chain" path that recreates the original silent-dependency problem.
3. **Link kinds restricted to `mechanism`, `model`, `proposition`, `observation`, `finding`.** These are the structural building blocks. Reference kinds (concept, topic) are excluded — they rarely change and don't materially propagate freshness. Operational kinds (workflow-run, dataset) are excluded — they belong upstream of structural claims, not inside them.
4. **BF-style verdict, not categorical-only.** Mirrors t037's `bayes_factor_evidence` pattern and aligns with D-003 (continuous beliefs). `bf10` may be `~` when only the categorical interpretation is available; `interpretation` carries the load.
5. **Dedicated `chain-audit` kind, not a field on `validation-report` or `interpretation`.** The kind itself signals "this is a chain-shaped finding" without prose inspection. Slightly larger registry surface in exchange for clearer semantics.
6. **`has_link` as a new relation, not `has_participant` reuse.** "Participant" suggests semantic membership; "link" carries the structural / ordered / load-bearing connotation. Worth one extra relation kind.
7. **`audits` mirrors `tests`.** Same single-target shape, same inverse derivation pattern. Keeps `bears_on` derivation rules visually parallel.
8. **Verdict-block integration is required, not optional.** Chain-audits participate in the existing `verdict/rollup.py` surface. Both `verdict:` and `bayes_factor_evidence:` blocks are required; validator enforces consistency. `evidence-for-risk` dropped from the interpretation enum because its risk-framing has no clean predicted-direction-agnostic token mapping.
9. **Order encoded via `sci:linkSequence` RDF list, not implementation-deferred.** Reordering same links must produce a different materialized graph so order changes are visible. Freshness propagation still relies on the structural-chain entity's `updated:` date advancing because freshness is date-based over `bears_on`. Flat `sci:hasLink` triples retained alongside for set-shaped queries.

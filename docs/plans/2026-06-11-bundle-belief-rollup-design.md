# Bundle belief roll-up — design

**Status:** Draft / design — approved approach, pending spec review.
**Created:** 2026-06-11
**Origin:** Surfaced while planning the MM30 causal-DAG corpus migration into the
epistemic-edges framework. Re-typing MM30's hypothesis-level synthesis claims to
their canonical kinds (`hypothesis`, `mechanism`) is only meaningful if a bundle
carries a *belief* derived from its member propositions. That roll-up is named in
the canonical model as a derived field but is **not implemented**. Per the
foundation-first decision (2026-06-11), it is built upstream in `~/d/science`
*before* the MM30 migration consumes it.

## 0. Purpose & scope

Add a **semantically explicit bundle-belief roll-up**: given a `hypothesis` or
`mechanism` and its member propositions, derive the bundle's belief from the
members' beliefs under an explicit composition rule. This is the missing
"aggregate `belief_state`" the proposition model already promises for hypotheses
(`docs/proposition-and-evidence-model.md:38`, `:88`, `:271`).

In scope:

- One bundle-belief engine with an authored `composition_rule`.
- A v1 composition rule — **weakest-link** continuous roll-up — for both
  hypotheses and mechanisms.
- Uniform member enumeration across the two existing linking relations.
- A `BundleBeliefResult` that surfaces *why* (bottleneck / contested / unresolved
  members), and the continuous scalar band.
- Relabeling the existing hypothesis evidence-union path as **coverage signal**,
  not the bundle's truth-belief.

Out of scope (see §10): implementing the `evidence_union` / `faceted_support`
rules; the MM30 migration itself; any change to per-proposition belief.

## 1. The gap (corrected)

Science already has *some* hypothesis-level aggregation, but it is the wrong
object for truth-belief:

- `_evidence_targets_for_uri()`
  (`science/src/science_tool/graph/store/evidence_signals.py:192`) expands a
  hypothesis to *itself + its linked propositions* and flattens their evidence
  into one **evidence-coverage** summary. Belief snapshots include both
  `Proposition` and `Hypothesis` (`graph/belief_snapshot.py:26`).
- This is an **evidence-union coverage signal**: "how much evidence touches any
  facet of this hypothesis." It is *not* a bundle roll-up — it cannot express
  "the bundle is only as strong as its weakest member," and a refuted member
  cannot floor it.
- **Mechanisms are excluded entirely** from that path, even though
  `MechanismEntity` carries an explicit, validated `propositions` list
  (`science/model/src/science_model/entities.py` — `MechanismEntity.propositions`,
  ~:505, validated in `_validate_mechanism_shape`).

> **Gap statement.** Science has an evidence-union *coverage* summary for
> hypotheses, but no semantically explicit bundle-belief roll-up over member
> proposition beliefs, and no mechanism roll-up path at all.

## 2. Binding constraints (not reopened)

1. **Independence reuse (h00 RFC §4).** *"Any opinion-fusion must route through
   the same independence logic (no parallel, weaker independence model)… the
   existing reduction already refuses to count it twice."* Roll-up must not
   introduce a second independence model.
2. **Partial update, not a verdict** (`proposition-and-evidence-model.md:271`).
   A member's weakness weakens the bundle; a member's single result never flips
   the bundle to a yes/no truth.
3. **Continuous belief (D-003).** Combine in the continuous / log-odds layer;
   never collapse to 0/1.

## 3. What already exists (the substrate to build on)

- **Member links.** Mechanisms link members forward via `sci:hasProposition`
  (materialized from any entity's `propositions` field,
  `graph/materialize.py:357–367`). Hypotheses link members in reverse via
  `cito:discusses` (`evidence_signals.py:_linked_claims_for_hypothesis`).
- **Per-proposition belief.** `aggregate_belief(reduce_units(collect_evidence_units(...)))
  -> BeliefResult` (ordinal magnitude + `contested` + `capped_by_refutation`),
  with the optional continuous `belief_scalar(result) -> BeliefScalar` (net
  log-odds band). This is the per-member computation, reused unchanged.
- **Within-member independence.** `reduce_units()` collapses evidence within
  `(independence_group, stance)` and excludes circular evidence — reused
  unchanged for each member.

## 4. The model: one engine, explicit composition rule

A single entry point dispatches by entity kind:

```
belief_for_entity(uri) -> BeliefResult | BundleBeliefResult
```

- For a `proposition` (or any non-bundle epistemic target): returns the existing
  `BeliefResult` via the current path. No behavior change.
- For a `hypothesis` or `mechanism` with members: returns a `BundleBeliefResult`
  computed from member beliefs under the bundle's `composition_rule`.

`composition_rule` is an **authored** field, defaulted per kind. It makes the
bundle's logical shape explicit rather than hiding it behind kind-dispatch — so a
non-conjunctive synthesis hypothesis and a causal mechanism can be modeled
distinctly *without* two parallel systems.

**It must be a real model field, not frontmatter the engine re-parses.** Today
`Entity`/`ProjectEntity` carries no such field and `_add_reasoning_metadata()`
materializes none — so a hypothesis-authored reserved rule would be *silently
dropped* before the §4 hard-error path ever ran, defeating fail-early. The
contract is therefore: a single `composition_rule` enum field on the **common
entity base both `hypothesis` and `mechanism` inherit** (the plan pins the exact
class — `mechanism` parses to `MechanismEntity(ProjectEntity)`; bare `hypothesis`
currently parses to plain `Entity`, so the field must live where *both* see it),
validated at the model layer (reserved values rejected there too), and
materialized as `sci:compositionRule`. The engine reads the compiled field, never
raw frontmatter.

```
composition_rule ∈ {
  all_steps,        # mechanism default — every step must hold (weakest-link)
  conjunctive,      # hypothesis default — sub-claims jointly assert the conjecture (weakest-link)
  evidence_union,   # RESERVED (not implemented v1) — facets pooled as one coverage target
  faceted_support,  # RESERVED (not implemented v1) — "N independent facets back a broader phenomenon"
}
```

`all_steps` and `conjunctive` are distinct *names* (preserving authored intent)
that share the **weakest-link** implementation in v1; they may diverge later.
Authoring a reserved rule is a **hard error** in v1 (fail early; no silent
fallback to weakest-link), with a message pointing at this doc.

### `BundleBeliefResult`

```
MemberBelief:
  member_uri:    str
  belief:        BeliefResult
  scalar:        BeliefScalar | None
  rank_key:      tuple                  # the deterministic ordering key (§5.2)
  reason:        str | None             # why this member ranked where it did (e.g. "speculative: no evidence")

BundleBeliefResult:
  composition_rule:     str
  magnitude:            BeliefMagnitude   # rolled-up ordinal = the bottleneck member's magnitude
  capped_by_refutation: bool             # OR of members' capped_by_refutation — a SEPARATE axis from magnitude
  contested:            bool
  scalar:               BeliefScalar | None   # the bottleneck member's band, if enabled
  member_results:       list[MemberBelief]
  bottleneck_members:   list[member_uri]  # members sharing the minimum ordinal magnitude
  contested_members:    list[member_uri]
  unresolved_members:   list[member_uri]  # no evidence / speculative
```

The shape is deliberately explanatory: a consumer can say *"bundle belief is
fragile because proposition X is fragile, and capped_by_refutation because step Y
is decisively refuted"* — both the bottleneck and the refutation are named, never
hidden in a scalar. `member_results` carries each member's `scalar` and `rank_key`
so a snapshot row can fully reconstruct *why* a given member was chosen as the
bottleneck even when several share an ordinal magnitude.

## 5. v1 composition: weakest-link

For `all_steps` / `conjunctive`:

1. Enumerate members (§6); compute each member's `BeliefResult` (+ scalar) via
   the existing per-proposition pipeline.
2. **Deterministic rank.** `rank_key(member) = (ordinal_index(magnitude),
   net_band_lower_or_0.0, member_uri)` — ordinal magnitude first; then the scalar
   `net_band` lower bound (`0.0` when the scalar layer is disabled); then
   `member_uri` as a total-order final tiebreak. This is reproducible **with or
   without** the scalar layer. Sort ascending.
3. The bundle's `magnitude` and `scalar` = the member with the minimum `rank_key`
   (the bottleneck representative). `bottleneck_members` lists every member sharing
   that minimum **ordinal magnitude** (the tied set), for explanation.
4. **Refutation is a separate axis, not a new ordinal.** The belief model has no
   state below `speculative` and no `refuted`/`eliminated` magnitude — the only
   refutation signal is `BeliefResult.capped_by_refutation` (which caps a member to
   `fragile`). So the bundle's `capped_by_refutation = OR` of the members' flag,
   propagated alongside the magnitude-min, **never** folded into the ordinal.
   "A refuted step refutes the chain" is thus a real propagated flag (plus a
   bottleneck/`reason` note), not something hoped to fall out of `min`.
5. A member with **no evidence** is `speculative`, the lowest ordinal, so it
   becomes the magnitude bottleneck and is listed in `unresolved_members` — an
   unestablished step is an unestablished mechanism. **Deliberate consequence,
   stated explicitly:** an *unestablished* member (`speculative`) ranks **below** a
   *refuted* one (`fragile`, capped), so when both are present the unestablished
   member drives `magnitude` while the refuted member is surfaced via
   `capped_by_refutation`. Treating "not yet shown" as weaker than "shown false"
   is the conservative skeptical default; both facts are visible because they live
   on different axes.
6. `contested = OR` of members' `contested`; `contested_members` lists them (see
   §9 — this aggressiveness is a knob).

### Why weakest-link is independence-safe by construction

The cross-member double-counting hazard — a source shared by two members
inflating the bundle — only bites rules that **sum/aggregate counts** across
members. `min` does not sum: a source shared by members A and B cannot raise the
minimum. So weakest-link needs **no new cross-member independence machinery**; the
existing within-member `reduce_units()` is sufficient and is reused untouched.
(The reserved `evidence_union` / `faceted_support` rules *do* aggregate and so
*will* require routing the union through `reduce_units()` per constraint §2.1 —
deferred with the rules themselves.)

## 6. Member enumeration (unify the two relations)

A single helper resolves a bundle's members as the union of:

- forward `sci:hasProposition` targets (mechanisms; any entity with a
  `propositions` field), and
- reverse `cito:discusses` propositions (current hypothesis linkage),

restricted to targets typed `Proposition`. **Non-transitive in v1** (direct
members only; a hypothesis-of-hypotheses is not expanded — YAGNI). Accepting both
relations avoids a schema migration of existing hypothesis links; converging on a
single canonical forward relation is noted as future cleanup, not done here.

Zero resolved members is handled by **intent, not silently**:

- An **undecomposed hypothesis with no authored `composition_rule`** and no
  members → falls back to the plain `BeliefResult` path (its own direct evidence,
  if any). This is the only forgiving case.
- A bundle that **declares itself one** — any authored `composition_rule`, or a
  `mechanism` (whose `MechanismEntity` validator already requires ≥1 authored
  proposition, so zero *resolved* members means its links are **dangling**) →
  **hard-fails** with an explicit unresolved-bundle error. A broken link must never
  silently collapse into direct-evidence belief.

## 7. Relabel the existing evidence-union path

The current `_evidence_targets_for_uri` hypothesis flattening is kept but
**renamed/reframed as a coverage signal**, surfaced separately from the bundle's
truth-belief. It answers "how much evidence touches this hypothesis," which is
useful for triage, but it is not the bundle's belief unless the bundle explicitly
authors `composition_rule: evidence_union`. This prevents the coverage number
from being misread as the bundle's warranted belief.

**Direct-on-bundle evidence is coverage-only in v1.** A hypothesis may carry
`cito:supports`/`disputes` edges on its *own* IRI (today's coverage path counts
them). The §5 weakest-link roll-up enumerates *members only*, so that direct
evidence is **intentionally not folded into the rolled-up belief** — it remains
visible in the coverage signal, never silently lost. Whether whole-conjecture
direct evidence should form a separate support axis in the roll-up is an open
question (§11), deferred rather than guessed.

## 8. Where it attaches

- `belief_snapshot.py` gains bundle rows for `hypothesis` and `mechanism` (today
  it emits hypothesis rows via the coverage path and no mechanism rows). Bundle
  rows carry `composition_rule`, rolled-up `magnitude`/band,
  `capped_by_refutation`, and the bottleneck/contested/unresolved member lists.
- Materialization may write the rolled-up `belief_state` onto the bundle IRI as a
  derived triple (mirroring per-proposition belief), so downstream `status` /
  `next-steps` surfaces can read it. Derived-only; never authored.

## 9. Defaults (reversible; recorded so they are not silent)

- `composition_rule` absent → `all_steps` for `mechanism`, `conjunctive` for
  `hypothesis`.
- **Contested propagation (knob):** bundle contested iff *any* member contested.
  Deliberately aggressive — one contested member in twenty flags the whole bundle.
  Defensible as a skeptical default, but called out as the first thing to tune if
  it proves noisy; isolated as a single predicate so it can change without
  touching the algebra.
- Members: direct links only (non-transitive).
- Refutation propagates as the separate `capped_by_refutation` flag; an
  evidence-less member caps `magnitude` at `speculative` (§5.4–5.5). No new ordinal
  state is invented.

## 10. Out of scope

- Implementing `evidence_union` / `faceted_support` (declared, reserved, hard-error
  if authored in v1). They need the cross-member independence pass.
- Converging hypothesis/mechanism onto one canonical member relation.
- Hypothesis-of-hypotheses (transitive) roll-up.
- The MM30 corpus migration that consumes this (its own design → plan cycle).
- Any change to per-proposition belief, the independence taxonomy, or D-003.

## 11. Open questions / risks

- **Scalar tiebreak choice.** The `rank_key` (§5.2) is deterministic, but ranking
  same-ordinal members by `net_band` lower bound is a judgment: for two members
  with the same magnitude but very different band *widths*, "weakest = lowest
  lower-bound" may not match intuition. Revisit if it bites; the `rank_key` is the
  single place to change it.
- **Direct-on-bundle evidence (§7).** v1 leaves whole-conjecture direct evidence
  as coverage-only. Whether it should enter the roll-up as a distinct support axis
  (not a weakest-link member) is unresolved — it needs a semantics that doesn't let
  weak whole-bundle evidence floor a strong chain, nor vice-versa.
- **`composition_rule` field placement.** The field must sit on the common base
  both `hypothesis` and `mechanism` parse to (§4). `mechanism` →
  `MechanismEntity(ProjectEntity)`; bare `hypothesis` → plain `Entity`. The plan
  pins whether that is `Entity` or `ProjectEntity` (and whether a `HypothesisEntity`
  is worth introducing); the field is **not** frontmatter-only on either.
- **Coverage-vs-belief confusion.** Two hypothesis numbers now exist (coverage
  signal + rolled-up belief). §7 relabeling mitigates, but surfaces must present
  them distinctly or risk re-conflating them.
- **Calibration unaudited (D-003 carry-forward).** Roll-up inherits the
  un-audited calibration of per-member belief; it does not worsen it, but a
  bottleneck-driven bundle belief is only as calibrated as its weakest member.

## Next step

On approval: produce a phased implementation plan (writing-plans), executed
subagent-driven in this worktree. Natural phasing: (1) member enumeration +
`composition_rule` field + engine skeleton with the proposition pass-through;
(2) weakest-link `BundleBeliefResult`; (3) snapshot/materialization wiring +
coverage-signal relabel; (4) reserved-rule hard-error + docs. Each phase leaves
the tree green.

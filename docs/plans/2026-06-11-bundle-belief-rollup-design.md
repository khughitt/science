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
  (`science/model/src/science_model/entities.py:501`).

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

`composition_rule` is an **authored** field on the bundle entity (optional;
defaulted per kind). It makes the bundle's logical shape explicit rather than
hiding it behind kind-dispatch — so a non-conjunctive synthesis hypothesis and a
causal mechanism can be modeled distinctly *without* two parallel systems.

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
BundleBeliefResult:
  composition_rule:   str
  magnitude:          BeliefMagnitude        # rolled-up ordinal (the bottleneck's)
  contested:          bool
  scalar:             BeliefScalar | None     # rolled-up continuous band (the bottleneck's), if enabled
  member_results:     list[(member_uri, BeliefResult)]
  bottleneck_members: list[member_uri]        # the min member(s) driving the result
  contested_members:  list[member_uri]
  unresolved_members: list[member_uri]        # no evidence / speculative
```

The shape is deliberately explanatory: a consumer can say *"bundle belief is
fragile because proposition X is fragile"* — the bottleneck is named, never
hidden in a scalar.

## 5. v1 composition: weakest-link

For `all_steps` / `conjunctive`:

1. Enumerate members (§6); compute each member's `BeliefResult` (+ scalar) via
   the existing per-proposition pipeline.
2. Rank members by belief, ascending: ordinal `magnitude` first, then (if scalar
   enabled) `net_band` lower bound as tiebreak.
3. The bundle's `magnitude` and `scalar` = the **minimum** member's. That member
   (and any tied at the minimum) is the `bottleneck_members`.
4. A member capped by refutation, or in an `eliminated`/refuted state, floors the
   bundle to that state (a refuted step refutes the chain).
5. A member with **no evidence** (speculative) caps the bundle at speculative and
   is listed in `unresolved_members` — an unestablished step is an unestablished
   mechanism. This is the conservative skeptical default.
6. `contested = any member contested`; `contested_members` lists them.

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

A bundle that resolves to **zero** members is not a bundle: `belief_for_entity`
falls back to the plain `BeliefResult` path (its own direct evidence, if any).

## 7. Relabel the existing evidence-union path

The current `_evidence_targets_for_uri` hypothesis flattening is kept but
**renamed/reframed as a coverage signal**, surfaced separately from the bundle's
truth-belief. It answers "how much evidence touches this hypothesis," which is
useful for triage, but it is not the bundle's belief unless the bundle explicitly
authors `composition_rule: evidence_union`. This prevents the coverage number
from being misread as the bundle's warranted belief.

## 8. Where it attaches

- `belief_snapshot.py` gains bundle rows for `hypothesis` and `mechanism` (today
  it emits hypothesis rows via the coverage path and no mechanism rows). Bundle
  rows carry `composition_rule`, rolled-up `magnitude`/band, and the
  bottleneck/contested/unresolved member lists.
- Materialization may write the rolled-up `belief_state` onto the bundle IRI as a
  derived triple (mirroring per-proposition belief), so downstream `status` /
  `next-steps` surfaces can read it. Derived-only; never authored.

## 9. Defaults (reversible; recorded so they are not silent)

- `composition_rule` absent → `all_steps` for `mechanism`, `conjunctive` for
  `hypothesis`.
- Contested propagation: bundle contested iff any member contested.
- Members: direct links only (non-transitive).
- Refuted/eliminated or evidence-less member: floors / caps the bundle per §5.

## 10. Out of scope

- Implementing `evidence_union` / `faceted_support` (declared, reserved, hard-error
  if authored in v1). They need the cross-member independence pass.
- Converging hypothesis/mechanism onto one canonical member relation.
- Hypothesis-of-hypotheses (transitive) roll-up.
- The MM30 corpus migration that consumes this (its own design → plan cycle).
- Any change to per-proposition belief, the independence taxonomy, or D-003.

## 11. Open questions / risks

- **Scalar tiebreak.** Ranking by ordinal-then-`net_band`-lower is a choice; if
  two members share an ordinal magnitude but differ in band width, "weakest" by
  lower bound may not match intuition for very wide bands. Revisit if it bites.
- **Mechanism `composition_rule` storage.** `MechanismEntity` gains an optional
  `composition_rule`; hypotheses (generic `Entity`, no dedicated class) read it
  from frontmatter. Asymmetric until/unless a `HypothesisEntity` is introduced.
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

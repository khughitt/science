# Authored-confidence-as-input — design (patchwork kernel Spec 5, Slice B)

> Patchwork kernel **Spec 5 — Proposition, Evidence, and Belief Semantics**, Slice B.
> Builds directly on Slice A's `BeliefPolicy` socket
> (`docs/plans/2026-06-16-belief-policy-keystone-{design,plan}.md`). Scope locked to
> **authored assertions** (the `expert_judgment` evidence type) with trust/agent weighting
> deferred to Spec 6.

## Goal

Give an **authored assertion** — a human or agent directly asserting belief in a proposition
— a real, disciplined path into `aggregate_belief`, weighted under the `BeliefPolicy` extended
in this slice. The governing principle: an authored assertion can **corroborate** empirical
evidence but can never **manufacture** empirical-grade belief.

**"Authored assertion" is a pure type contract:** a unit is an authored assertion **iff** its
normalized `evidence_type` equals `policy.authored_assertion_type` (`expert_judgment`).
Whether the line also declares `dataset_usage` is **not** part of belief recognition — the
engine never inspects the line's sources for this purpose. By authoring convention an
`expert_judgment` line is dataset-less (empirical lines carry `evidence_type:
empirical_data_evidence` instead), but the belief engine keys solely on the type, and an
`expert_judgment` line that also declares `dataset_usage` is a mis-authoring caught by
validation, not a special case in aggregation.

`confidence` is already an authored field on `EvidenceLineEntity` (inherited from `Entity`)
and is materialized to `SCI_NS.confidence` (`materialize.py:447`), but the belief engine
(`aggregate_belief` / `EvidenceUnit`) never reads it — it surfaces only in display/summary
code. `expert_judgment` already exists as the lowest-ranked `evidence_type`
(`belief_weights.py` `EVIDENCE_TYPE_RANK`). This slice wires the authored confidence into
belief as a **gate**, under an explicit **ceiling**, with **symmetric refutation discipline**.

## Architecture

The belief path is ordinal: `aggregate_belief` counts kept support/dispute units and buckets
the result into `SPECULATIVE / FRAGILE / SUPPORTED / WELL_SUPPORTED`, with `WELL_SUPPORTED`
gated on a clean qualifying **direct test** and a decisive independent strong direct-test
dispute capping belief to `FRAGILE`. This slice adds three things, all keyed off new
`BeliefPolicy` knobs so the policy object stays the single source of belief-aggregation
truth:

1. a **confidence gate** that admits (or rejects) an authored-assertion unit,
2. an **authored-only ceiling** that bounds how far authored support can move belief, and
3. **refutation symmetry** so an authored assertion is never a qualifying direct test on
   either side.

This is **not behavior-neutral** by design (unlike Slice A) — it deliberately activates a
new input. The contract is narrower: **empirical-only belief is unchanged**, and because
`expert_judgment` appears in no existing aggregation test or data fixture, the full existing
belief suite stays green.

## Core rule

A unit is an **authored assertion** when
`normalize_evidence_type(u.evidence_type) == policy.authored_assertion_type`
(default `"expert_judgment"`).

It **counts as a support/dispute unit** only when

```
u.confidence is not None
and 0 <= u.confidence <= 1
and u.confidence >= policy.authored_min_confidence      # default 0.5
```

Range-validation happens **before** the threshold so a malformed `confidence: 1.2` cannot
slip past the gate. A unit that fails the gate does **not** count; it is recorded in a new
`excluded_authored_confidence` bucket on `BeliefResult` (fail-explicit, surfaced in
views/checks). Both sub-threshold (valid but `< min`) and out-of-range (`<0` or `>1`) land in
that bucket; the validation layer (§ Validation) distinguishes the out-of-range / missing
case as an authoring error.

**Confidence is a gate, not a magnitude dial.** A passing assertion contributes exactly one
support/dispute unit; its numeric confidence does not scale the unit's weight.

### The ceiling (epistemic core)

After the normal magnitude is computed, if **every counted support unit is an authored
assertion** ("authored-only support"), the magnitude is capped at
`policy.authored_only_ceiling` (default `"fragile"`), setting a new `authored_capped: bool`
flag on `BeliefResult`. Mixing in even one non-authored (empirical) support unit runs the
normal path untouched, with the assertion as an ordinary corroborating unit.

- 1 assertion → `n_support == 1` → `FRAGILE` (ceiling is a no-op).
- ≥2 assertions → would compute `SUPPORTED` → **capped to `FRAGILE`** (the ceiling bites).

The ceiling is applied to the **counted support set** (after the gate), and only when that
set is non-empty and entirely authored.

### Refutation symmetry

`is_qualifying_direct_test` is extended to exclude authored assertions
(`and not is_authored_assertion(u, policy=policy)`). Consequences:

- **Support side:** an authored assertion can never satisfy `WELL_SUPPORTED`'s clean
  direct-test gate (it also can't, because the authored-only ceiling caps it first — but the
  exclusion makes the discipline explicit and robust to mixed sets).
- **Dispute side:** an authored *dispute* can never be a `decisive_refutation` (which
  requires `is_qualifying_direct_test`), so authored opinion cannot cap belief from the
  dispute side either.

Authored opinion is bounded symmetrically: it cannot manufacture top-tier belief, and it
cannot decisively eliminate it.

## Components & files

### Modify: `graph/belief_weights.py`

Add `MAGNITUDE_NAMES = ("speculative", "fragile", "supported", "well_supported")`
(`belief_weights.py` imports nothing internal, so this is the cycle-free home for the
canonical magnitude-string tuple). A reconciliation test asserts
`set(MAGNITUDE_NAMES) == {m.value for m in BeliefMagnitude}` so the tuple and the enum cannot
drift.

### Modify: `graph/belief_policy.py`

`BeliefPolicy` gains three knobs (all on `DEFAULT_BELIEF_POLICY`):

- `authored_assertion_type: str = "expert_judgment"` — the **normalized** evidence_type that
  marks authored assertions.
- `authored_min_confidence: float = 0.5` — the count-gate threshold.
- `authored_only_ceiling: str = "fragile"` — the maximum magnitude (as a string, **not**
  `BeliefMagnitude`, so `belief_policy.py` keeps importing only `belief_weights` — no cycle)
  when support is authored-only.

`__post_init__` fails early (raises `ValueError`) if `authored_min_confidence` is outside
`[0, 1]` or `authored_only_ceiling` is not in `MAGNITUDE_NAMES`. This keeps the new knobs
disciplined without importing `BeliefMagnitude`.

### Modify: `graph/belief.py`

- `EvidenceUnit` gains `confidence: float | None = None` **as the last field** (after
  `quant_prob_sign`) so the many positional `EvidenceUnit(...)` test constructors remain
  behavior-neutral.
- `_read_unit` reads it: `confidence=_float_lit(provenance, line, SCI_NS.confidence)`.
- New helper `is_authored_assertion(u, *, policy=DEFAULT_BELIEF_POLICY) -> bool` returning
  `normalize_evidence_type(u.evidence_type) == policy.authored_assertion_type`.
- New helper `_authored_assertion_counts(u, *, policy) -> bool` encoding the range-validated
  gate (`confidence is not None and 0 <= c <= 1 and c >= policy.authored_min_confidence`).
- `is_qualifying_direct_test` excludes authored assertions (see Refutation symmetry).
- `aggregate_belief` partitions authored assertions by the gate **on the raw `units` list,
  before `reduce_units`** (see § Pipeline ordering). Gate failures go to
  `excluded_authored_confidence` and never enter reduction; the surviving units (all
  empirical, plus gate-passing authored assertions) flow into `reduce_units` unchanged. After
  the existing magnitude + refutation-cap logic, the authored-only ceiling is applied and
  `authored_capped` set.
- `BeliefResult` gains `authored_capped: bool = False` and
  `excluded_authored_confidence: list[EvidenceUnit] = field(default_factory=list)`.

### Pipeline ordering (critical)

`aggregate_belief` today runs `reduce_units()` (independence collapse → winners) and derives
`contested_groups` **before** bucketing. The confidence gate MUST run **before**
`reduce_units`, not merely before bucketing:

```
units
  → partition: gate-failing authored assertions → excluded_authored_confidence
               everything else                  → admitted
  → reduce_units(admitted, policy=policy)        # collapse winners, contested_groups
  → bucket magnitude → refutation cap → authored-only ceiling
```

If a gate-failing authored *dispute* reached `reduce_units`, it could win a collapse, add to
`contested_groups`, perturb `clean_support`, or flip `contested` — so a rejected unit would
still influence the result. Gating first guarantees a rejected authored unit has **zero**
downstream effect.

### Modify: `graph/bundle_belief.py`

`BundleBeliefResult` gains `authored_capped: bool`, computed as
`any(m.belief.authored_capped for m in members)`, mirroring `capped_by_refutation`. (The
Slice-A `MixedBeliefPolicyError` comparability guard is unaffected.)

### Modify: persistence — `graph/belief_snapshot.py`

Persist `authored_capped` in **both** snapshot row branches (single-claim `BeliefResult` and
`BundleBeliefResult`), mirroring `capped_by_refutation`. (`capped_by_refutation` is today
persisted only on the bundle branch; `authored_capped` goes on both — the single-claim branch
needs it because authored-only single claims are exactly where the ceiling fires.)

**Legacy normalization (pre-Slice-B rows have no `authored_capped`):** extend the Slice-A
`_with_policy_defaults(row)` read-time normalizer (which `read_snapshots` already routes every
parsed row through) to also default `authored_capped` to `False` when the key is absent. Pre-
Slice-B belief rows were necessarily computed with no authored-only ceiling, so `False` is the
**semantically correct** value, not a silent fallback — identical in spirit to Slice-A's
policy-identity normalization. `authored_capped` is **not** added to the dedup `_key` (it is a
derived flag, like `capped_by_refutation`, not part of belief identity).

### Modify: validation — `validate/checks/evidence_lines.py`

- `check_evidence_unscored_line`: add an authored-assertion branch. An authored assertion is
  **admitted by confidence**, so it is exempt from the role/strength scoring requirements
  that the check enforces for ordinary lines. Instead, the check warns when an authored
  assertion's `confidence` is **missing or outside `[0, 1]`** (the un-gateable case).
- `check_belief_nonreproducible`: add `authored_capped` to the compared fields, alongside the
  Slice-A `policy_id` / `policy_version` (now that `authored_capped` is persisted on both
  branches a change in it is a real, comparable reproducibility signal). Compare with a
  **default of `False`** on both sides (`prior.get("authored_capped", False) !=
  now.get("authored_capped", False)`) so a pre-Slice-B prior row missing the field — already
  normalized to `False` by `read_snapshots` — never produces a spurious `belief.nonreproducible`
  error against a current `authored_capped == False` row.

## Worked examples

| Support units (after gate) | Today | This slice |
|---|---|---|
| 1× empirical direct_test (clean, strong) | FRAGILE (`n_support == 1`) | FRAGILE (unchanged) |
| ≥2× empirical clean, one a qualifying direct_test | WELL_SUPPORTED | WELL_SUPPORTED (unchanged) |
| 1× authored `confidence 0.9` | n/a (inert) | FRAGILE |
| 2× authored `confidence 0.9` | n/a (inert) | **FRAGILE (capped from SUPPORTED)** |
| 1× authored `0.9` + 2× empirical clean direct_test | n/a | WELL_SUPPORTED (authored corroborates) |
| 1× authored `confidence 0.3` | n/a | SPECULATIVE (gated out → `excluded_authored_confidence`) |
| 1× authored `confidence 1.2` | n/a | SPECULATIVE (range-rejected → bucket + validate WARN) |
| 1× authored dispute `0.9`, role=direct_test | n/a | contested, **not** decisive (no refutation cap) |

`WELL_SUPPORTED` requires `n_support >= well_supported_min_clean_support` (default 2) with a
clean qualifying direct test; a single support unit reaches at most `FRAGILE`.

## Boundary (explicit, deferred)

- **Trust / agent weighting → Spec 6.** Author identity stays in provenance
  (`prov:wasAttributedTo`); every qualifying assertion is treated **uniformly** here (a human
  ORCID and an AI agent assertion get the same gate + ceiling). Spec 6's trust policy plugs
  into the same `BeliefPolicy` socket later.
- **Confidence on empirical lines stays inert.** This slice activates authored confidence
  only for **standalone assertions** (`expert_judgment`, no dataset). Wiring confidence into
  empirical-line weight is a separate future decision.
- **Phase-2 log-odds scalar untouched** (consistent with Slice A's boundary). `confidence`
  does not enter the scalar in this slice.

## Testing (TDD)

1. **Gate (admit/reject):** authored `0.9` counts (FRAGILE); authored `0.3` rejected
   (SPECULATIVE, lands in `excluded_authored_confidence`); authored `1.2` and `-0.1`
   range-rejected (bucket); authored `None` rejected.
2. **Ceiling:** 2× authored `0.9` → FRAGILE (not SUPPORTED), `authored_capped is True`; 1×
   authored → FRAGILE, `authored_capped is False` (no-op).
3. **Mixing:** authored `0.9` + ≥2 empirical clean direct-test support → WELL_SUPPORTED,
   `authored_capped is False` (empirical path untouched, assertion corroborates).
4. **Refutation symmetry:** authored dispute `0.9` with role=direct_test → contested but
   `capped_by_refutation is False` (not decisive); empirical decisive refutation still caps.
4b. **Pipeline ordering (gate before reduction):** a **gate-failing** authored dispute
    (`confidence 0.3`) sharing an independence group with an empirical support unit leaves
    `contested`, `contested_groups`, the collapse winners, and `clean_support` **identical** to
    the same scenario with the authored dispute absent — proving the rejected unit never
    reached `reduce_units`.
5. **Policy discipline:** `BeliefPolicy(authored_min_confidence=1.5)` and
   `authored_only_ceiling="bogus"` raise `ValueError`; `MAGNITUDE_NAMES` reconciles with
   `BeliefMagnitude`.
6. **Positional stability:** existing positional `EvidenceUnit(...)` constructors still build
   (confidence defaults None) and the full existing belief suite stays green.
7. **Persistence:** single-claim and bundle snapshot rows both carry `authored_capped`;
   `BundleBeliefResult.authored_capped` is the OR over members.
8. **Validation:** an authored assertion with no role/strength but valid confidence is **not**
   flagged unscored; one with missing/out-of-range confidence **is** warned;
   `check_belief_nonreproducible` flags a row whose `authored_capped` changed.
9. **Legacy normalization:** a pre-Slice-B snapshot row (no `authored_capped` key) reads back
   with `authored_capped == False` via `read_snapshots`, and produces **no**
   `belief.nonreproducible` error when re-checked against a current `authored_capped == False`
   result.

## Success criteria

- An authored assertion (the `expert_judgment` type) participates in belief: admitted by a
  range-validated confidence gate **before independence reduction**, contributing exactly one
  unit (no magnitude scaling).
- Authored-only support is capped at `authored_only_ceiling`; mixing with empirical evidence
  is unaffected.
- An authored assertion is never a qualifying direct test on either side (no top-tier
  manufacture, no decisive refutation).
- The three new knobs live on `BeliefPolicy`, are range/membership validated at construction,
  and are recorded via the existing policy-identity persistence.
- `authored_capped` is persisted on both snapshot branches, rolled up onto bundles, and
  compared by the reproducibility check.
- Empirical-only belief is unchanged; the full existing belief suite stays green.

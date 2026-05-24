# Evidence Aggregation Phase 2: Derived Scalar, Sensitivity, Snapshots

**Date**: 2026-05-24
**Status**: Design approved (rev c); ready for implementation plan
**Revision**: rev c (2026-05-24) — four review tweaks on rev b:
(1) `evidence.unscored-line` only flags **massable** (non-diagnostic) units —
`model_criticism`/`negative_control` are recognized-but-non-massed, never flagged.
(2) snapshots carry `scalar_enabled` in the record + idempotency/golden key, so a same-day
opt-in toggle appends a new row instead of colliding.
(3) revision summary fixed: diagnostic-only contest is **caveated**, not suppressed.
(4) diagnostic-caveat logic keys off the integer `massed_dispute_score == 0`, not float band
equality (`BeliefScalar` now carries `massed_support_score`/`massed_dispute_score`).

rev b (2026-05-24) — six review findings folded in:
(1) `stable` was degenerate — a single multiplicative δ cannot flip the sign of a fixed
signed score sum, so the old sign-sweep tested nothing; replaced with an **adversarial
independent sweep** of the support/dispute sides (band extremes are closed-form at the
envelope corners, so the grid is gone).
(2) diagnostic contestation is now explicit in `BeliefScalar` and the bands are renamed
`massed_*`.
(3) a **display contract** keeps the scalar from contradicting the ordinal headline
(net suppressed under single-unit / refutation ceilings and when not robust; **caveated**
under diagnostic-only contest).
(4) snapshot determinism is per-**record**, with idempotent append.
(5) the JSON example matches the h012 math.
(6) unscored evidence lines fail loud via a new QA warning.
**Parent design**: `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md`
(§4 derived scalars, §5 edge status, Reproducibility, roadmap Phase 2).
**Builds on**: Phase 0 (evidence-line entity) + Phase 1 (independence-aware aggregation →
ordinal `belief_state`), both complete on `origin/main`.

## Goal

Add the **derived numeric scalar**, **sensitivity checks**, and **append-only belief
snapshots** on top of the Phase 1 ordinal aggregator — without inventing magic numbers and
without claiming calibrated probability. Plus fold in the deferred `query_uncertainty`
belief-unification.

## Grounding principle (why the math looks the way it does)

Two layers, graded differently for honesty:

- **Ordinal layer (Phase 1, unchanged, framework-wide).** The orderings
  (`empirical_data > simulation/benchmark > literature > expert_judgment`;
  `direct_test > proxy_support > background_constraint`; `strong > moderate > weak`), the
  magnitude ladder, and the scoped-refutation cap are **domain-reasoning claims, not tuned
  constants.** They need no numbers and are not reopened here. **The ordinal `belief_state`
  is the headline epistemic confidence;** the scalar only ever *annotates* it (see the
  display contract), never overrides it.
- **Cardinal scalar (Phase 2, new, opt-in display).** A `[−1,1]` net inherently needs
  numbers. We cannot derive "true" values: we have ~zero resolved claims (low-N calibration
  is explicitly weak) and calibrated priors are an explicit non-goal. So we do **not pick a
  point** — we minimize the cardinal commitment to one per-step log-odds increment `δ`,
  **sweep the two stances independently across an envelope**, and report a band, suppressing
  the net direction when even the worst-case weighting does not preserve it. That suppression
  is the honest signal.

The operator is **additive log-odds**, because independent evidence combines by adding
log-likelihood-ratios — the actual math, not an invented curve. It is continuous (no
gate/ceiling cutoffs), saturates naturally (diminishing returns), and reduces the scalar to
the single increment `δ`. This is an **uncalibrated evidence index validated by robustness,
never a probability**.

### Why the sweep must be adversarial (finding 1)

With one global `δ`: `net(δ) = tanh(½·δ·(S − D))` where `S = Σ support scores`,
`D = Σ dispute scores`. Since `δ > 0` and `tanh` is monotone, `sign(net) = sign(S − D)` for
**every** `δ` — the sign is already parameter-free, so sweeping a single `δ` only rescales
magnitude and can never flip the sign. A single-`δ` "sign stability" test is therefore
vacuous.

The meaningful question is robustness to **how we weight the two sides relative to each
other**. So sweep `δ_s` (support) and `δ_d` (dispute) **independently** over the same
envelope `[δ_lo, δ_hi]`. The net direction is robust only if support's ordinal lead survives
the most adversarial weighting (support at `δ_lo`, dispute at `δ_hi`). Because `net` is
increasing in `δ_s` and decreasing in `δ_d`, the band extremes are the two corners — no grid
sampling, closed-form.

## Components

### 1. Numeric weights / ordinal steps (`graph/belief_weights.py`, extended)

Reuse the Phase 1 rank tables, read as **steps above the floor** (single source of truth; no
parallel cardinal table):

```
type_steps     = EVIDENCE_TYPE_RANK[normalize_evidence_type(t)] − 1   # 0..3
role_steps     = EVIDENCE_ROLE_RANK[role] − 1                          # 0..2
strength_steps = STRENGTH_RANK[strength] − 1                          # 0..2
```

New constants:

```python
PROXY_STEP_PENALTY = 2          # gated proxy counts two ordinal steps lower (logic, not a cliff)
DELTA_ENVELOPE = (0.3, 1.0)     # log-odds per ordinal step; OR ≈ 1.35 .. 2.72; SWEPT, not chosen
CONFIG_VERSION = "belief-logodds-v1"   # part of the golden #8 input set; bump on any change above
```

`PROXY_STEP_PENALTY` is an ordinal count, not a tuned weight. The envelope endpoints are the
only cardinal commitment, and they are swept (adversarially), not chosen as a point.

**Unscored lines fail loud (finding 6).** A value missing from a rank table yields step 0
(graceful zero contribution for *computation*), **but** a **massable** (non-diagnostic)
support/dispute line whose `evidence_type`, `evidence_role`, or `strength` is absent or
unrecognized — i.e. it cannot be scored — is flagged by a new QA check `evidence.unscored-line`
(WARN / hygiene; §5). Diagnostic roles (`model_criticism` / `negative_control`) are
deliberately absent from `EVIDENCE_ROLE_RANK` — they are *recognized but non-massed*, so they
are **never** flagged by this check. Computation degrades gracefully; authored metadata gaps
are surfaced, not silently swallowed.

### 2. Scalar engine (`graph/belief_scalar.py`, new)

Consumes the **already-reduced** units `aggregate_belief` produced — never re-derives
independence (DRY):

```python
def unit_score(u: EvidenceUnit) -> int:
    s = type_steps(u) + role_steps(u) + strength_steps(u)        # 0..7
    if is_proxy_gated(u):
        s = max(0, s - PROXY_STEP_PENALTY)
    return s
```

Diagnostics (`model_criticism`/`negative_control`) are already excluded from
`BeliefResult.support_units`/`dispute_units`, so they never enter the **massed** sums —
consistent with the magnitude. Their contestation is carried separately (below), so it stays
visible.

Let `S = Σ unit_score(u)` over `support_units`, `D = Σ unit_score(u)` over `dispute_units`,
`(δ_lo, δ_hi) = DELTA_ENVELOPE`:

```
# per-side mass = SCALE sensitivity of one stance (monotone in its own δ)
massed_support_band = ( tanh(½·δ_lo·S), tanh(½·δ_hi·S) )      # both ∈ [0,1)
massed_dispute_band = ( tanh(½·δ_lo·D), tanh(½·δ_hi·D) )

# net = ADVERSARIAL independent cross-sweep (worst-case relative weighting at the corners)
net_band = ( tanh(½·(δ_lo·S − δ_hi·D)),    # support weighted down, dispute up  → min
             tanh(½·(δ_hi·S − δ_lo·D)) )    # support weighted up,  dispute down → max
```

`net` uses the **combined** log-odds (supports raise, disputes lower). The **massed pair is
the point, net is the convenience**: high-support+high-dispute (genuinely contested) →
`massed_support≈1, massed_dispute≈1`; low+low (genuinely unknown) → `≈0,≈0`. The pair
distinguishes them; net alone collapses them — the design's "never a bare net".

Result type (frozen):

```python
@dataclass(frozen=True)
class BeliefScalar:
    massed_support_score: int                  # S = Σ unit_score(support_units); integer, exact
    massed_dispute_score: int                  # D = Σ unit_score(dispute_units)
    massed_support_band: tuple[float, float]   # (min, max) over the envelope; scale sensitivity
    massed_dispute_band: tuple[float, float]
    net_band: tuple[float, float]              # adversarial cross-sweep corners
    net_robust: bool                           # net_band does not straddle/touch 0
    contested: bool                            # carried from BeliefResult.contested
    diagnostic_dispute_count: int              # disputes excluded from mass (model_criticism/...)
```

**`net_robust` (replaces the degenerate `stable`):** `True` iff both `net_band` endpoints are
strictly the same sign (the worst-case relative weighting preserves the direction). A band
that straddles or touches 0 ⇒ `net_robust = False`. `contested`/`diagnostic_dispute_count`
make diagnostic contestation explicit in the scalar itself (finding 2), so a
diagnostically-contested claim (`massed_dispute_score == 0` but `contested = True`) is no
longer indistinguishable from an uncontested one.

All band values are rounded to 6 decimals (finding 4: byte-stable records).

### 3. Display contract (`belief_scalar_enabled` + how callers surface it)

Opt-in reader (scalar **display** only; the scalar is always computed):

```python
def belief_scalar_enabled(project_root: Path) -> bool:
    # True iff core/decisions.md has a decision id "belief-scalar" with Status: active
    return "belief-scalar" in parse_active_decision_ids(project_root / "core" / "decisions.md")
```

Reuses `curate.agents_md.parse_active_decision_ids`. Everything else (`belief_state`,
`contested`, snapshots, #7, #8) is framework-wide.

**The scalar annotates the ordinal headline; it never contradicts it (findings 2 & 3).**
When `belief_scalar_enabled` is True, a caller renders:

1. Always the ordinal headline (magnitude + `contested`) — unchanged from Phase 1.
2. The **massed pair** `massed_support_band` / `massed_dispute_band` as "evidence mass".
3. The **net** number only when it cannot be misread as overall confidence:
   - **Suppress net** (show pair only) when the **ordinal ceiling binds** —
     `magnitude == fragile` (single-unit ceiling) or `capped_by_refutation` — annotated
     `single-unit ceiling applies` / `refutation cap applies`. (h012: `fragile`, net hidden.)
   - **Suppress net** when `net_robust` is False (adversarial weighting flips the sign).
   - **Caveat** `contested (diagnostic)` when `contested and massed_dispute_score == 0`
     (contestation is real but unmassed — finding 2).
   - Otherwise show `net_band`.

- `attention.py::format_attention_candidate`: `belief_weight` is a dict carrying
  `massed_support`, `massed_dispute`, `net` (the last `null` when suppressed by the rules
  above), plus `contested` and `diagnostic_dispute_count`; `None` entirely when
  `belief_scalar_enabled` is False. `influence_weight` stays `None` (structural reach — out
  of Phase 2 scope). Where attention must sort by a single number, use the **conservative**
  net endpoint (the one nearer 0) when net is shown, else fall back to ordinal magnitude.

### 4. Snapshots (`graph/belief_snapshot.py` + `science belief snapshot`)

Append-only `knowledge/belief-snapshots.jsonl`, one record per claim per as-of date. The
record stores the **raw computed values** (display suppression in §3 is presentation-only and
is not applied to the stored record):

```json
{"as_of":"2026-05-24","claim":"prop:h012","belief_state":"fragile","contested":true,
 "diagnostic_dispute_count":1,"scalar_enabled":true,
 "massed_support_score":7,"massed_dispute_score":0,
 "massed_support_band":[0.781807,0.998178],"massed_dispute_band":[0.0,0.0],
 "net_band":[0.781807,0.998178],"net_robust":true,
 "input_hashes":["sha256:..","sha256:.."],"config_version":"belief-logodds-v1"}
```

(h012: `S=7` (strong·empirical·direct_test), `D=0` (Simeonov is `model_criticism` ⇒
diagnostic), so `net_band = massed_support_band = [tanh(1.05), tanh(3.5)] = [0.7818, 0.9982]`,
`net_robust=true`. The headline is still `fragile (contested)` and the **display** hides net
under the single-unit ceiling — finding 5 alignment.)

- `belief_state` + `contested` + `diagnostic_dispute_count` + `scalar_enabled` always present
  (framework-wide). The scores, bands, and `net_robust` are present iff `scalar_enabled` is
  True (i.e. `belief-scalar` active), else `null`.
- `input_hashes` = sorted, de-duplicated content-hashes of the **contributing evidence-line
  entities** (the units `collect_evidence_units` returns). `config_version` is its own field.
  Together they are the golden #8 input set.

**Determinism semantics (finding 4):** byte-identity is a property of the **per-claim
record**, not the whole file — a claim's serialized row is byte-identical given identical
inputs+config (sorted/deduped hashes, 6-decimal float rounding, fixed JSON key order, one
record per claim sorted by claim URI). The append is **idempotent per
`(as_of, claim, input_hashes, config_version, scalar_enabled)`**: a no-op re-run on the same
day with unchanged inputs and unchanged opt-in adds **no** rows (skip when an identical-key
record already exists for that `as_of`). Toggling `belief-scalar` in `core/decisions.md`
changes `scalar_enabled`, so a same-day toggle correctly appends a new row rather than
colliding with the prior one (finding 2). Real changes append new rows ⇒ the trajectory stays
auditable and append-only. `science belief snapshot` recomputes every claim and appends only
the non-duplicate rows.

### 5. QA checks (`validate/checks/evidence_lines.py`, joining #1–#6)

- **`evidence.unscored-line` (finding 6, WARN / hygiene).** A **massable** (non-diagnostic)
  support/dispute evidence-line whose `evidence_type` / `evidence_role` / `strength` is absent
  or unrecognized (so `unit_score` cannot place it) — keeps zero-contribution compute but
  surfaces the authored-metadata gap. Diagnostic lines (`model_criticism` / `negative_control`,
  intentionally outside `EVIDENCE_ROLE_RANK`) are recognized-but-non-massed and never flagged.
- **`belief.fragile-single-line` (#7, leave-one-out, WARN / hygiene).** For each kept
  independent unit, recompute `aggregate_belief` on the unit list minus that one line; if the
  resulting `belief_state` magnitude **or** `contested` flips, flag the claim. Operates on the
  **ordinal** state (matches the design wording; unaffected by the scalar). Direct encoding of
  "one dataset shouldn't swing the conclusion".
- **`belief.nonreproducible` (#8, golden, ERROR).** For each claim with a stored snapshot
  whose `input_hashes` + `config_version` + `scalar_enabled` equal the current ones (the
  **latest** matching row), recompute belief and compare to that row's
  `belief_state`/`contested` (and scores/bands if present).
  Equal inputs with differing output ⇒ nondeterminism/bug ⇒ ERROR. Differing inputs ⇒
  legitimate change ⇒ not flagged (staleness, not irreproducibility).

### 6. `query_uncertainty` unification (`graph/store/summary.py`)

Replace the count-based contested signal (`if support_count > 0 and dispute_count > 0`,
summary.py:865–867) with `aggregate_belief(collect_evidence_units(...)).contested`, mirroring
`_claim_summary_data`. Count columns (`support_count`/`dispute_count`/`source_count`) stay as
count-based context; only the **contested** signal becomes belief-derived, so
`query_uncertainty` and `_claim_summary_data` can no longer disagree.

## Module layout

| Path | Change |
|------|--------|
| `graph/belief_weights.py` | add step maps + `PROXY_STEP_PENALTY`, `DELTA_ENVELOPE`, `CONFIG_VERSION` |
| `graph/belief_scalar.py` | **new** — `unit_score`, `belief_scalar(result)→BeliefScalar`, `belief_scalar_enabled(root)` |
| `graph/belief_snapshot.py` | **new** — record type, `make_snapshots(graph_path)`, `append_snapshots`, `read_snapshots` |
| `cli.py` | **new** `science belief snapshot` subcommand |
| `graph/attention.py` | fill `belief_weight` (opt-in + display contract) in `format_attention_candidate` |
| `graph/store/summary.py` | unify `query_uncertainty` contested onto `aggregate_belief` |
| `validate/checks/evidence_lines.py` | add `evidence.unscored-line`, #7 `belief.fragile-single-line`, #8 `belief.nonreproducible` |

`belief.py` is untouched (the scalar reads its `BeliefResult` output). The ordinal/scalar
split mirrors the existing `belief.py`/`belief_weights.py` split.

## Testing (TDD)

- **Scalar math** (`belief_scalar`): `tanh` saturation; per-side band endpoints at envelope
  corners; `net_band` from the adversarial corners; **`net_robust` False when the band
  straddles 0** (e.g. `S=6,D=5` → `net_band ≈ [−0.92, 0.978]`, not robust) and True for a
  clear lead (`S=10,D=1`); diagnostics excluded from sums but counted in
  `diagnostic_dispute_count`; proxy penalty lowers a unit's score by 2 (floored at 0);
  high/high vs low/low distinguished by the massed pair; determinism + 6-decimal rounding.
- **Display contract**: net suppressed when `magnitude==fragile` or `capped_by_refutation`;
  net suppressed when `net_robust` False; `contested (diagnostic)` caveat when
  `contested and massed_dispute_score==0`; `attention.belief_weight` is `None` when opt-in
  off, dict with `net=null` when suppressed, full dict otherwise.
- **Snapshots**: append preserves prior rows; idempotent no-op re-run adds no rows; a changed
  input appends exactly one new row; **a same-day `belief-scalar` toggle appends a new row**
  (distinct `scalar_enabled` key); `read_snapshots` round-trips; per-record byte-identity on
  unchanged inputs; scores/bands `null` when opt-in off; `input_hashes` sorted/deduped.
- **#7**: a 2-unit claim where dropping one unit flips magnitude is flagged; a robust
  multi-unit claim is not.
- **#8**: matching hashes + changed output ⇒ ERROR; changed hashes ⇒ silent; compares the
  latest matching row.
- **`evidence.unscored-line`**: a massable line with an unrecognized `evidence_type` warns; a
  fully specified line does not; a diagnostic (`model_criticism`) line does **not** warn even
  though its role is outside the rank table.
- **`query_uncertainty`**: contested signal now equals `_claim_summary_data`'s for the same
  claim (parity test), including a claim contested only via a diagnostic/contested-group.

## Worked example (h012, cancer-evolution pilot)

One support line (Yang2022: strong · empirical_data · direct_test ⇒ `s=7`) and one dispute
line (Simeonov2021: strong · empirical_data · `model_criticism` · generalization). Simeonov
is **diagnostic** ⇒ excluded from `dispute_units` ⇒ `D=0`, but counted as
`diagnostic_dispute_count=1` and sets `contested=True`. Over the envelope:
`massed_support_band = net_band = [tanh(½·0.3·7), tanh(½·1.0·7)] = [0.7818, 0.9982]`,
`net_robust=True`. Magnitude stays `fragile` (single support unit). Headline:
`fragile (contested)`. **Display:** the single-unit ceiling binds, so the net number is
**hidden**; the surfaced scalar is the massed pair `support≈[0.78,1.0] / dispute=0` with a
`contested (diagnostic)` caveat — coherent: one strong line for, one interpretive criticism
flagged but not massed, and the high support mass is visibly *not* overall confidence.

## Non-goals (unchanged from parent design)

- `influence_weight` (structural reach via `bears_on`/`cross_impact`) — distinct from belief,
  not Phase 2.
- Graph-resident `sci:edgeStatus` / `sci:Posterior` migration — Phase 3.
- Calibration backtest (#10) and pgmpy CPDs — Phase 4.
- Authoring shortcuts (nested evidence block / YAML) — separate track.
- No calibrated probabilities or invented priors; the scalar stays opt-in, a pair not a bare
  net, suppressed when not robust or when the ordinal ceiling binds.

## Exit criteria

1. `belief_scalar(result)` returns deterministic 6-decimal bands; `net_robust` reflects the
   adversarial corner signs; diagnostics excluded from mass but counted in
   `diagnostic_dispute_count`; proxy penalty applied.
2. The display contract holds: net is suppressed under the single-unit/refutation ceilings and
   under `net_robust=False`, and caveated under diagnostic-only contest.
3. `science belief snapshot` appends per-claim records to `knowledge/belief-snapshots.jsonl`;
   a no-op re-run adds no rows; a same-day `belief-scalar` toggle appends a new row (distinct
   `scalar_enabled` key); records are byte-identical on unchanged inputs.
4. `attention.belief_weight` surfaces the scalar only when `belief-scalar` is active, honoring
   the display contract; `None` otherwise.
5. `evidence.unscored-line`, `belief.fragile-single-line`, and `belief.nonreproducible` ship
   and pass on the pilot.
6. `query_uncertainty` contested matches `_claim_summary_data` for every claim (parity test).
7. Full `science` + `science-model` suites green.

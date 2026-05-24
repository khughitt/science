# Evidence Aggregation Phase 2: Derived Scalar, Sensitivity, Snapshots

**Date**: 2026-05-24
**Status**: Design approved; ready for implementation plan
**Parent design**: `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md`
(§4 derived scalars, §5 edge status, Reproducibility, roadmap Phase 2)
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
  constants.** They need no numbers and are not reopened here.
- **Cardinal scalar (Phase 2, new, opt-in display).** A `[−1,1]` net inherently needs
  numbers. We cannot derive "true" values: we have ~zero resolved claims (low-N calibration
  is explicitly weak) and calibrated priors are an explicit non-goal. So we do **not pick a
  point** — we **minimize the cardinal commitment to one swept parameter and report a
  robustness band**, suppressing the scalar when the conclusion is not robust. That
  suppression is the honest signal.

The combination operator is **additive log-odds**, because independent evidence combines by
adding log-likelihood-ratios — the actual math of evidence combination, not an invented
curve. This is continuous (no gate/ceiling cutoffs), saturates naturally (diminishing
returns), and reduces the whole scalar to a single per-step increment `δ` that we sweep
rather than choose. This is an **uncalibrated evidence index validated by robustness, never
a probability**.

## Components

### 1. Numeric weights / ordinal steps (`graph/belief_weights.py`, extended)

Reuse the Phase 1 rank tables, read as **steps above the floor** (single source of truth;
no parallel cardinal table):

```
type_steps     = EVIDENCE_TYPE_RANK[normalize_evidence_type(t)] − 1   # 0..3
role_steps     = EVIDENCE_ROLE_RANK[role] − 1                          # 0..2
strength_steps = STRENGTH_RANK[strength] − 1                          # 0..2
```

New constants:

```python
PROXY_STEP_PENALTY = 2          # gated proxy counts two ordinal steps lower (logic, not a cliff)
DELTA_ENVELOPE = (0.3, 1.0)     # log-odds per ordinal step; OR ≈ 1.35 .. 2.72; SWEPT, not chosen
DELTA_GRID_N = 7                # deterministic grid points across the envelope (inclusive)
CONFIG_VERSION = "belief-logodds-v1"   # part of the golden #8 input set; bump on any change above
```

`PROXY_STEP_PENALTY` is an ordinal count, not a tuned weight. `DELTA_ENVELOPE`/`DELTA_GRID_N`
define the deterministic sweep — no RNG. Unknown ordinal values already rank 0 (degrade
gracefully); a unit with all-unknown fields has `s(u)=0` and contributes nothing.

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
`BeliefResult.support_units`/`dispute_units`, so they never enter the sums — consistent with
the magnitude treatment.

For each δ on the grid:

```
support_lo(δ) = δ · Σ unit_score(u)  over support_units
dispute_lo(δ) = δ · Σ unit_score(u)  over dispute_units
support_index(δ) = tanh(½ · support_lo(δ))      # ∈ [0,1)
dispute_index(δ) = tanh(½ · dispute_lo(δ))       # ∈ [0,1)
net(δ)           = tanh(½ · (support_lo(δ) − dispute_lo(δ)))   # ∈ (−1,1)
```

`net` uses the **combined** log-odds (supports raise, disputes lower), not the difference of
the two indices. The **pair is preserved and is the point**: high-support+high-dispute
(genuinely contested) → `support_index≈1, dispute_index≈1, net≈0`; low+low (genuinely
unknown) → `≈0,≈0,≈0`. `net` alone collapses them; the pair distinguishes them — this is the
design's "never a bare net".

Result type (frozen):

```python
@dataclass(frozen=True)
class BeliefScalar:
    support_band: tuple[float, float]   # (min, max) over the δ grid
    dispute_band: tuple[float, float]
    net_band: tuple[float, float]
    stable: bool                        # sign(net) constant across the grid
```

**Suppression rule (no magic threshold):** `stable = all(net(δ) has the same sign)` across
the grid (a zero-crossing or any δ giving net == 0 with others nonzero ⇒ unstable). When
`stable` is False, callers surface **ordinal-only** and withhold the scalar. The band width
is always shown when surfaced, so dispersion is visible.

### 3. Opt-in (`belief_scalar_enabled`, scalar display only)

```python
def belief_scalar_enabled(project_root: Path) -> bool:
    # True iff core/decisions.md has a decision id "belief-scalar" with Status: active
    return "belief-scalar" in parse_active_decision_ids(project_root / "core" / "decisions.md")
```

Reuses `curate.agents_md.parse_active_decision_ids` (existing precedent). Gates **only
surfacing** the scalar; the scalar is always computed (cheap). Everything else
(`belief_state`, `contested`, snapshots, #7, #8) is framework-wide.

- `attention.py::format_attention_candidate`: `belief_weight =
  {"support": support_band, "dispute": dispute_band, "net": net_band}` when enabled **and**
  `stable`; else `None`. `influence_weight` stays `None` (structural reach — out of Phase 2
  scope). Where attention must sort by a single number, use the conservative endpoint
  (`net_band[0]`); unstable/disabled candidates sort by ordinal magnitude only.

### 4. Snapshots (`graph/belief_snapshot.py` + `science belief snapshot`)

Append-only `knowledge/belief-snapshots.jsonl`, one record per claim per as-of date:

```json
{"as_of":"2026-05-24","claim":"prop:h012","belief_state":"fragile","contested":true,
 "support_band":[0.71,0.93],"dispute_band":[0.0,0.0],"net_band":[0.71,0.93],"stable":true,
 "input_hashes":["sha256:..","sha256:.."],"config_version":"belief-logodds-v1"}
```

- `belief_state` + `contested` always present (framework-wide). The three bands + `stable`
  are present iff `belief-scalar` is enabled, else `null`.
- `input_hashes` = sorted, de-duplicated content-hashes of the **contributing evidence-line
  entities** for that claim (the units `collect_evidence_units` returns). `config_version`
  is its own field. Together they are the golden #8 input set.
- `science belief snapshot` recomputes every claim and **appends** one block; it never
  rewrites prior rows. Append-only ⇒ the belief trajectory is auditable.
- Deterministic by construction (grid sweep, sorted hashes, stable JSON key order, one
  record per claim sorted by claim URI) ⇒ identical inputs reproduce byte-identical rows.

### 5. QA checks (`validate/checks/evidence_lines.py`, joining #1–#6)

- **`belief.fragile-single-line` (#7, leave-one-out, WARN / hygiene).** For each kept
  independent unit, recompute `aggregate_belief` on the unit list minus that one line; if the
  resulting `belief_state` magnitude **or** `contested` flips, flag the claim. Operates on the
  **ordinal** state (matches the design wording; unaffected by the scalar). Direct encoding of
  "one dataset shouldn't swing the conclusion".
- **`belief.nonreproducible` (#8, golden, ERROR).** For each claim that has a stored snapshot
  whose `input_hashes` + `config_version` equal the current ones, recompute belief and compare
  to the snapshot's recorded `belief_state`/`contested` (and bands if present). Equal inputs
  with differing output ⇒ nondeterminism/bug ⇒ ERROR. Differing inputs ⇒ legitimate change ⇒
  not flagged (this is staleness, not irreproducibility).

### 6. `query_uncertainty` unification (`graph/store/summary.py`)

Replace the count-based contested signal (`if support_count > 0 and dispute_count > 0`,
summary.py:865–867) with `aggregate_belief(collect_evidence_units(...)).contested`, mirroring
`_claim_summary_data`. Count columns (`support_count`/`dispute_count`/`source_count`) stay as
count-based context; only the **contested** signal becomes belief-derived, so
`query_uncertainty` and `_claim_summary_data` can no longer disagree.

## Module layout

| Path | Change |
|------|--------|
| `graph/belief_weights.py` | add step maps + `PROXY_STEP_PENALTY`, `DELTA_ENVELOPE`, `DELTA_GRID_N`, `CONFIG_VERSION` |
| `graph/belief_scalar.py` | **new** — `unit_score`, `belief_scalar(result)→BeliefScalar`, `belief_scalar_enabled(root)` |
| `graph/belief_snapshot.py` | **new** — record type, `make_snapshots(graph_path)`, `append_snapshots`, `read_snapshots` |
| `cli.py` | **new** `science belief snapshot` subcommand |
| `graph/attention.py` | fill `belief_weight` (opt-in + stable) in `format_attention_candidate` |
| `graph/store/summary.py` | unify `query_uncertainty` contested onto `aggregate_belief` |
| `validate/checks/evidence_lines.py` | add #7 `belief.fragile-single-line`, #8 `belief.nonreproducible` |

`belief.py` is untouched (the scalar reads its `BeliefResult` output). The ordinal/scalar
split mirrors the existing `belief.py`/`belief_weights.py` split.

## Testing (TDD)

- **Scalar math** (`belief_scalar`): `tanh` saturation; a single max-quality unit's net band;
  diagnostics excluded from sums; proxy penalty lowers a unit's score by 2 (not to a fixed
  floor unless it crosses 0); high/high vs low/low distinguished by the pair; `stable` flips
  to False on a sign-crossing across the grid; determinism (same input → same band).
- **Opt-in**: `belief_scalar_enabled` true only with an `active` `belief-scalar` decision;
  `attention.belief_weight` is the band dict when enabled+stable, `None` when disabled, `None`
  when unstable.
- **Snapshots**: append preserves prior rows; `read_snapshots` round-trips; byte-identical
  re-run on unchanged inputs; scalar fields `null` when opt-in off; `input_hashes` sorted/deduped.
- **#7**: a 2-unit claim where dropping one unit flips magnitude is flagged; a robust
  multi-unit claim is not.
- **#8**: matching hashes + changed output ⇒ ERROR; changed hashes ⇒ silent.
- **`query_uncertainty`**: contested signal now equals `_claim_summary_data`'s for the same
  claim (parity test); a claim contested only via a diagnostic/contested-group (not raw
  counts) is now flagged contested, matching belief.

## Worked example (h012, cancer-evolution pilot)

One support line (Yang2022: strong · empirical_data · direct_test ⇒ `s=7`) and one dispute
line (Simeonov2021: strong · empirical_data · `model_criticism` · generalization). Simeonov
is **diagnostic** ⇒ excluded from `dispute_units` ⇒ `dispute_lo=0`. Over δ∈[0.3,1.0]:
`support_lo ∈ [2.1, 7.0]`, `net_band ≈ [tanh(1.05), tanh(3.5)] = [0.78, 0.998]`, `stable=True`
(all positive). Magnitude stays `fragile` (single support unit), `contested=True` (diagnostic
dispute). Headline: `fragile (contested)`, scalar `net ∈ [0.78, 1.0]` — coherent: one strong
line for, one interpretive criticism flagged but not massed.

## Non-goals (unchanged from parent design)

- `influence_weight` (structural reach via `bears_on`/`cross_impact`) — distinct from belief,
  not Phase 2.
- Graph-resident `sci:edgeStatus` / `sci:Posterior` migration — Phase 3.
- Calibration backtest (#10) and pgmpy CPDs — Phase 4.
- Authoring shortcuts (nested evidence block / YAML) — separate track.
- No calibrated probabilities or invented priors; the scalar stays opt-in, a pair not a bare
  net, and is suppressed when not robust.

## Exit criteria

1. `belief_scalar(result)` returns deterministic bands; `stable` reflects sign-constancy
   across the δ grid; diagnostics excluded; proxy penalty applied.
2. `science belief snapshot` appends per-claim records to
   `knowledge/belief-snapshots.jsonl`; re-run on unchanged inputs is byte-identical.
3. `attention.belief_weight` surfaces the band only when `belief-scalar` is active **and**
   stable; `None` otherwise.
4. `belief.fragile-single-line` and `belief.nonreproducible` ship and pass on the pilot.
5. `query_uncertainty` contested matches `_claim_summary_data` for every claim (parity test).
6. Full `science` + `science-model` suites green.

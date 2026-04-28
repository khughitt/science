# Edge-Status Distribution Dashboard

**Status:** proposed
**Created:** 2026-04-17
**Source:** feedback fb-2026-04-13-008 (mm30)
**Amended:** 2026-04-19 — adds `eliminated` as a fifth enum value per
`docs/specs/2026-04-19-dag-rendering-and-audit-pipeline-design.md`. Graph-layer
storage for `eliminated` (the `sci:eliminatedBy` predicate) and for the sibling
`identification` axis introduced by the 2026-04-19 spec is **deferred to Phase 2
`sync-dag`**. Until then, `--edge-status-distribution` and `--edge-status-trend`
may show 0 for `eliminated` on projects that haven't yet run `sync-dag`; the YAML
layer is authoritative during that window (see `science-tool dag render` /
`science-tool dag staleness` for YAML-backed equivalents).

## Problem

mm30 manually curates 85 causal-DAG edges with a status enum
`{supported, tentative, structural, unknown}`. The current distribution
(28/28/21/8) is diagnostic at a glance: it shows where the project's
epistemic weight concentrates and where it is speculating. Tracking that
distribution over time would show whether evidence is moving uphill
(`tentative → supported`) or whether new speculation is accumulating faster
than old speculation is resolved.

`science-tool graph dashboard-summary` does not surface this today, even
though much of the source data is already in the graph (the rest is blocked
on the user's "partially migrated" claim-evidence state).

The status enum itself looks broadly reusable — if science-tool adopts it
as a convention, other projects get the dashboard for free.

## Status enum

Adopt the five-value enum verbatim (four original + `eliminated` added 2026-04-19):

| Status | Meaning |
|---|---|
| `supported` | At least one accepted finding backs the edge with non-trivial evidence weight. |
| `tentative` | Backed only by weak / single-source / preliminary evidence. |
| `structural` | Asserted on theoretical or domain grounds; no empirical backing claimed. |
| `unknown` | Edge present in the model but its evidential status has not been classified. |
| `eliminated` | Hypothesised mechanism retracted or ruled out by subsequent evidence. Retained for provenance (not deleted); rendered visually distinct (e.g. dotted grey + `[✗]` marker). The optional `eliminated_by` field lists the closing task / interpretation / discussion IDs. Added 2026-04-19 via `2026-04-19-dag-rendering-and-audit-pipeline-design.md`; graph-layer predicate `sci:eliminatedBy` deferred to Phase 2 `sync-dag`. |

Default for newly-added edges is `unknown` — the explicit declaration of
"we have not classified this yet" is the point.

## Storage

Express on each edge as `sci:edgeStatus` triple in `graph/knowledge`:

```
<inquiry/X/edge/E> sci:edgeStatus "supported" .
```

When migrating projects with informal status fields, prefer to leave them
in place and add the canonical predicate alongside; remove informal fields
only after a confirmation pass.

## Surface

Extend `science-tool graph dashboard-summary` with three new sections, each
opt-in via flags so existing callers are unaffected:

### `--edge-status-distribution`

Counts and percentages by status, across all edges in the graph:

```
Edge Status Distribution
  supported   : 28 (33%)
  tentative   : 27 (32%)
  structural  : 21 (25%)
  unknown     :  7 ( 8%)
  eliminated  :  2 ( 2%)
  TOTAL       : 85
```

(Post-2026-04-19 mm30 distribution: two bridge edges moved from `tentative` to
`eliminated` under the t204 terminal verdict, one edge_status was reclassified
during curation; the remainder are stable.)

### `--edge-status-trend`

Compares against the prior `dashboard-summary` snapshot (saved under
`doc/meta/dashboard-snapshots/YYYY-MM-DD.json`):

```
Edge Status Trend (since 2026-03-15)
  tentative -> supported    : +5
  unknown -> tentative      : +3
  unknown -> structural     : +1
  new (since snapshot)      : +6 unknown, +2 tentative
  removed (since snapshot)  : -1 supported
```

Snapshots are written automatically when `dashboard-summary` runs with
`--snapshot`. No magic auto-snapshotting on every invocation.

### `--per-hypothesis-status`

Per-hypothesis breakdown of edge counts by status, with a "research debt"
column = `(unknown + tentative) / total`:

```
Per-Hypothesis Edge Status
  Hypothesis            supp   tent   struct  unk   debt
  H01 immune-fraction      6      2      1     0   25%
  H02 driver-pathway       3     12      5     5   68%   *high
  H03 cohort-bias          ...
```

`*high` flag at debt > 50%.

## Cross-cutting concerns

- `refs validate` should accept the four enum values and reject anything else.
- `inquiry uncertainty` (existing) should incorporate edge-status into its
  uncertainty surface — tentative edges and unknown edges are *types* of
  uncertainty even before posteriors enter the picture.
- The `core/decisions.md` convention from fb-2026-04-06-003 is the right
  place to record any project-specific deviation from the canonical four
  statuses (e.g., a project that wants `disputed` as a fifth value).

## Implementation plan

Ship in two PRs:

1. **PR 1: schema + read + flat distribution.**
   - Define `sci:edgeStatus` predicate + enum validation.
   - `dashboard-summary --edge-status-distribution`.
   - Tests for empty graph, all-unknown graph, mixed graph.

2. **PR 2: trend + per-hypothesis + snapshots.**
   - Snapshot writer + reader under `doc/meta/dashboard-snapshots/`.
   - `--edge-status-trend` and `--per-hypothesis-status` flags.

Gate on the same migration concern fb-2026-04-13-008 calls out: claim-backed
evidence needs to be reliably surfaced before the trend section means
anything. PR 1 is safe to ship now (the distribution is meaningful even
in a partially migrated project); PR 2 should wait until the source data
is consistently graph-resident.

## Out of scope

- Per-edge prose justification ("why is this edge tentative") — that
  belongs in the inquiry-edge annotations themselves, not the dashboard.
- Auto-classification of edges by some heuristic — the point of the enum
  is that a human (or curating agent) makes the call deliberately.

## Non-goals

- Replacing the existing `neighborhood-summary` / `claim-summary` flows.
  Those answer "what does this neighborhood look like"; this dashboard
  answers "what does the project's epistemic weight distribution look like."
- Cross-project rollups. A single-project dashboard is the right scope; a
  multi-project rollup is fb-future material.

# S2 — Adaptive Rotation (Curation Program) — Design

**Status:** design

**Goal:** Give a project's reviewable corpus a deterministic *coverage floor* —
a stateless `science entity rotation` command that, on each invocation, ranks
every locally reviewable entity by how long it has gone unreviewed and prints
the `n(N)` stalest as this sweep's work-list. It performs no reviews and writes
nothing; the human (or `/science:curate`) reviews each row with the existing
`science entity review` and commits when they choose. Rotation guarantees that,
completed sweep by sweep, nothing in the corpus goes unexamined indefinitely.

## 1. Where this sits in the curation program

- **S1 (shipped)** certified *which* kinds are reviewable: `curation_scope_for_kind`
  returns `epistemic | correspondence | none`, and `entity review` refuses a
  `none`-scoped kind. S2 consumes that boundary as its corpus filter.
- **S4 (shipped)** is the *alarm* for the correspondence corpus: the
  `plan.correspondence-drift` WARN fires when a plan under-claims its on-disk
  progress. The epistemic corpus has its own alarm — freshness state
  (`needs-review` / `stale`) from `derive_freshness`.
- **S2 is the floor under both alarms.** Alarms react to a *known* problem now;
  rotation systematically re-examines *everything* over time so that unknown
  problems surface and no entity is silently trusted forever. Freshness and drift
  never decide *who* is selected — they only annotate selected rows (§6).
- **S5 (future)** owns git-activity-derived signals (flux/activity scores) and a
  durable state tier. **This design supersedes the S1 roadmap's
  `Curation-Sweep:` commit-trailer note** (see
  `docs/plans/2026-07-17-curation-scope-certification-design.md`): rotation keys
  purely on the versioned `last_reviewed` date and `review_entity` writes *only*
  the `review_state` block, so a sweep cannot cascade phantom drift or scramble
  its own ordering key. There is nothing for a provenance trailer to protect in
  S2. The trailer belongs in S5, where a git-activity flux score genuinely needs
  to exclude sweep commits, and it should be defined and honored there.

## 2. Boundary & architecture

One deterministic, **stateless** selection command — proposed
`science entity rotation` (a sibling of `science entity needs-review`).

- **Reads** `review_state.last_reviewed`, `created`, `status`, and `kind`
  straight from entity frontmatter. No graph materialization is required and no
  git history is read, so the command works uniformly across epistemic and
  correspondence kinds and cannot be thrown off by a stale or missing
  `graph.trig`.
- **Writes nothing, reviews nothing, commits nothing.** The output is guidance.
- **Stateless.** No sweep counter, no sweep-id, no durable cache. "This sweep" is
  simply "the `n(N)` stalest entities right now." Re-running mid-sweep after some
  reviews correctly drops the just-reviewed rows (their `last_reviewed` advanced),
  and the command is idempotent for a fixed corpus and clock.

## 3. Corpus definition

The eligible corpus `N` is the set of **locally reviewable, source-authored
Markdown entities** — exactly the domain `entity review` can resolve. Precisely,
an entity is eligible iff **all** of:

1. It is yielded by the canonical scanner `iter_entity_markdown(entities_root)`
   (`entity_scan.py`, the sole sanctioned scan). This excludes the `_archive/`
   subtree and every other `_`-prefixed segment by construction, and scans only
   the project's local `entities/` root — so **commons overlays and any
   adapter-derived rows that have no local source markdown are never admitted.**
2. Its kind has `curation_scope_for_kind(kind) != CurationScope.NONE`
   (epistemic ∪ correspondence).
3. Its `status` is **not** in `CLOSED_LIFECYCLE_STATUSES`
   (`{complete, superseded, retired, archived, abandoned, deprecated}` —
   `entities.py`). This is the single shared terminal-status authority already
   used by attention and dataset-capability consumers; S2 does **not** mint a new
   `{archived, retired, superseded}` set. Dead records neither consume budget nor
   dilute the coverage figure. (Note this excludes `complete` plans — correct: a
   plan whose lifecycle is closed is not part of the live rotation, and a
   *stale-under-claim* `draft` plan that should be `complete` is exactly what the
   S4 drift alarm catches, not something rotation needs to re-surface.)

`N` is recomputed from disk on every invocation; it drifts slowly as entities are
added, closed, or archived.

## 4. Selection algorithm

### 4.1 Ordering — a total order, never-reviewed first

Sort the eligible corpus by the key

```
(last_reviewed  or  DATE_MIN,
 created        or  DATE_MIN,
 canonical_id)
```

ascending. Consequences:

- An entity with no `last_reviewed` (never reviewed) sorts **first** — the
  stalest possible.
- Ties on `last_reviewed` (it is date-granular) break by `created` ascending
  (oldest content first); a missing `created` is treated as `DATE_MIN`
  (oldest/first) so the order stays **total**.
- The final `canonical_id` tie-break makes the order fully deterministic.

### 4.2 Budget — piecewise adaptive size

```
n(0) = 0
n(N) = N                                        for 1 ≤ N ≤ N_full
n(N) = min(N, max(1, ceil(b · ln(N) − a)))      for N > N_full
```

- **Small projects read fully** (`n = N`) up to `N_full`. A lower clamp alone
  cannot guarantee full-read for every small `N`, so the full-read branch is
  explicit rather than emergent from `min`/`max`.
- **Large projects taper** sublinearly (the `ln` branch), so coverage accumulates
  across sweeps instead of demanding a full re-read each time.
- `a`, `b`, `N_full` are **baked constants**, documented in code, with **boundary
  tests** at `N ∈ {0, 1, N_full, N_full+1}` and the calibration anchor. There is
  **no per-project override** — the coverage bound below is a property of the
  tool, not something a project can tune away.

**Calibration (to be pinned from the S2 rotation simulation).** The constants
must satisfy: full-read for small projects up to `N_full`; `n(389) = 57` with
`⌈N/n⌉ = 7` sweeps (the simulated least-recently-reviewed result that beat random
sampling's ~42 sweeps / p95 57 / max 90 and its never-read tail). A provisional
fit meeting these targets is `b = 11.53`, `a = 12.57`, `N_full = 25`
(`n(100) ≈ 41`, `n(389) = 57`); the implementation plan pins the exact simulated
values.

### 4.3 Coverage invariant (with its condition)

> For a fixed eligible corpus, **when every selected entity's `last_reviewed`
> strictly advances**, completing each budget gives full coverage within
> `⌈N/n⌉` rounds.

The condition is load-bearing because `last_reviewed` is date-granular: two
reviews on the same calendar day do not move the key, so a same-day round that
re-selects an already-today row makes no progress on that row. Reviewing (via
`science entity review`) sets `last_reviewed = today`, which advances the key
across day boundaries and moves the entity behind everything not-yet-reviewed;
under the condition, the corpus behaves as a rotating buffer and every entity is
reviewed within `⌈N/n⌉` rounds.

**Partial reviews have no universal bound.** If a human reviews only some of the
presented budget, coverage slows; a *repeatedly skipped* row can starve — but
only by deliberate human choice, never because the algorithm passed it over.
Rotation always advances the stalest tail it is allowed to.

The alternatives that would make the bound unconditional — datetime-granular
review stamps, or a durable per-entity rotation cursor — add schema or state
complexity for a guarantee that the stateless design already delivers under a
plainly-stated condition. **S2 stays stateless; the condition is documented.**

## 5. Non-goals / explicitly deferred

- **No git provenance, no `Curation-Sweep:` trailer** — deferred to S5 (§1).
- **No durable state / cache / cursor** — the command is stateless (§4.3).
- **No per-project budget knob** — the coverage bound is a tool invariant (§4.2).
- **`--with-drift` is out of v1** (§6.2).
- **Rotation never gates and never changes selection based on an alarm.**

## 6. Output contract

### 6.1 Table and JSON

Default output is a table of the `n(N)` selected rows — `ref`, `last_reviewed`
(or `never`), and age-in-days — preceded by a header line stating `n of N` and
the coverage figure `⌈N/n⌉`. `--format json` mirrors `needs-review`'s shape.

`--all` prints the **whole ranked queue** (view only; it does not change the
budget). To make it unambiguous that the full queue is displayed while only its
prefix is the sweep's budget, **every JSON row carries `rank` (1-based) and
`selected` (bool = `rank ≤ n`)**, and the payload carries metadata:

```
pool_size       N (eligible corpus size)
budget          n(N)
displayed       rows printed (n by default, N under --all)
coverage_rounds ⌈N/n⌉
```

### 6.2 Annotations — best-effort, never blocking

Annotations enrich selected rows but never block selection or change the
ordering.

- **Freshness enrichment** (epistemic rows): when a materialized `graph.trig` is
  present, attach the entity's freshness state. The output shape is **stable
  regardless of availability** — every row always carries a nullable `freshness`
  field plus a `freshness_status` of `current | absent | stale | invalid`:
  - `current` — value read from a graph newer than the entity's source;
  - `absent` — no graph present;
  - `stale` — graph older than the entity's source (value shown is not trusted as
    current and is marked so, never presented as current);
  - `invalid` — graph present but unreadable/malformed.
  Enrichment being unavailable is reported explicitly; it never blocks or delays
  the selection.
- **Drift enrichment is deferred (`--with-drift` NOT in v1).** S4's validation
  surface honors evidence-scoped acceptance (an accepted false positive is
  suppressed). A raw, targeted single-entity drift probe would bypass that and
  could resurrect an accepted false positive. Doing it correctly requires an
  **accepted-aware single-entity drift instrument**, which is separate work. In
  v1, drift stays where it belongs: `science validate` / `science health`.

## 7. Components (isolation)

- `science_tool/curation/rotation.py` (proposed) — pure selection core:
  `eligible_corpus(project_root) -> list[EligibleEntity]` (scan → scope filter →
  terminal-status filter → frontmatter fields) and
  `rotation_budget(n: int) -> int` (the piecewise formula), plus
  `select_rotation(project_root, *, today) -> RotationResult` composing them into
  ranked rows + metadata. No I/O beyond reading entity markdown; no graph, no git.
- Freshness enrichment reader (best-effort, isolated) — reads `graph.trig` if
  present and returns `(freshness, freshness_status)` per ref; failures degrade to
  `absent`/`invalid`, never raise into selection.
- CLI command `entity rotation` in `entities_cli.py` — argument parsing, table
  rendering, JSON assembly. Thin; all logic lives in the core.

## 8. Testing strategy

- **Budget boundaries:** `n(0)=0`, `n(1)=1`, `n(N_full)=N_full`,
  `n(N_full+1) < N_full+1`, and the `n(389)=57` / `⌈N/n⌉=7` anchor.
- **Total order:** never-reviewed sorts first; date ties break by `created`;
  missing `created` treated as oldest; final `id` tie-break — including a fixture
  where all three keys are needed to disambiguate.
- **Corpus filter:** archived (`_archive/`) excluded; `none`-scoped kind excluded;
  each `CLOSED_LIFECYCLE_STATUSES` member excluded; commons-overlay / adapter-only
  rows absent (scanner domain).
- **Coverage invariant (simulated):** with strictly-advancing stamps, a fixed
  corpus of `N` reaches full coverage within `⌈N/n⌉` rounds; a same-day repeat
  makes no progress on already-today rows (documents the condition).
- **Enrichment shape:** `freshness_status` is one of the four values in each of
  the present/absent/stale/invalid graph conditions; selection succeeds in all
  four.
- **Output contract:** JSON rows carry `rank`/`selected`; metadata carries
  `pool_size`/`budget`/`displayed`/`coverage_rounds`; `--all` displays `N` rows
  with only the prefix `selected`.

## 9. Open item for the spec-review gate

Pin the exact `a`, `b`, `N_full` from the S2 rotation simulation (§4.2). The
provisional fit satisfies the stated targets but should be replaced with the
simulated constants before the implementation plan locks the boundary tests.

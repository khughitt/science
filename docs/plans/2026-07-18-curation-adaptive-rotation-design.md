# S2 — Adaptive Rotation (Curation Program) — Design

**Status:** design

**Goal:** Give a project's reviewable corpus a deterministic *coverage floor* —
a stateless `science entity rotation` command that, on each invocation, ranks
every locally reviewable entity by how long it has gone unreviewed and prints
the `n(N)` stalest as this sweep's work-list. It performs no reviews and writes
nothing; the human (or `/science:curate`) reviews each row with the existing
`science entity review` and commits when they choose. Under the coverage
condition in §4.3, completing each sweep's budget re-examines the whole corpus
within a bounded number of sweeps, so nothing goes unexamined indefinitely.

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

1. It is returned by the public policy-root loader
   `load_markdown_entities(project_root)` (`entities.py`). This routes each
   **registered** entity policy home through the canonical scanner
   `iter_entity_markdown` (`entity_scan.py`), which excludes the `_archive/`
   subtree and every other `_`-prefixed segment by construction. Enumerating
   through the registered homes — rather than raw-scanning an arbitrary
   `entities/` root — is what makes rotation's corpus **identical to the mutation
   surface `entity review`/`find_entity` resolves**: an unregistered directory
   cannot appear in rotation yet be unreviewable, and **commons overlays and
   adapter-derived rows with no local source markdown are never admitted.** Each
   loaded record carries `{id, kind, path, frontmatter}`, from which `status`,
   `created`, and `review_state.last_reviewed` are read.
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

**Pinned constants: `b = 11.53`, `a = 12.57`, `N_full = 25`.** The earlier
rotation simulation did not produce adaptive-curve constants — it established
only the single working point `n = 57` at `N = 389` and the least-recently-
reviewed-versus-random coverage comparison (rotation's hard 7 sweeps versus
random's ~42 / p95 57 / max 90 and its never-read tail). These three constants
are therefore a **deliberate policy fit** chosen to honor that working point and
the full-read-for-small-projects goal, not values read off a simulation. The fit
is verified: `n(25) = 25`, `n(26) = 25`, `n(100) = 41`, `n(389) = 57`
(`⌈389/57⌉ = 7`), monotone non-decreasing across the tested range. The
implementation plan locks them with the boundary tests above.

### 4.3 Coverage invariant (with its condition)

> For a fixed eligible corpus, **when each round stamps every selected row with a
> `last_reviewed` strictly greater than the maximum `last_reviewed` present in the
> corpus before that round** — equivalently, when after stamping every selected
> row sorts strictly after every unselected row — completing each budget gives
> full coverage within `⌈N/n⌉` rounds.

The weaker "each selected row's own date strictly advances" is **not** sufficient,
because `last_reviewed` is date-granular. Counterexample (`n = 1`): A was reviewed
yesterday, B today; A sorts first (yesterday < today). Reviewing A *today*
strictly advances A's own date, yet A and B are now tied at today and A still wins
the `created` tie-break — so the next round re-selects A and B is never reached,
violating the `⌈2/1⌉ = 2` bound. Requiring the new stamp to exceed the corpus's
pre-round maximum (here, B's today) rules this out: A must be stamped strictly
later than today, landing it behind B, so B is selected next round. Under this
condition the corpus behaves as a rotating buffer and every entity is reviewed
within `⌈N/n⌉` rounds.

In practice `science entity review` stamps `today`, so the condition holds exactly
when each sweep runs on a calendar day strictly later than every `last_reviewed`
already in the corpus — the normal cadence of at most one sweep per day over a
corpus whose stalest rows carry older dates. It is broken by running two
progress-expecting sweeps on the same day, or by a corpus that already contains
today's date on unselected rows; the honest statement is the maximum-based one
above.

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

Output is emitted through the shared `emit_query_rows` helper (`output.py`), so
the JSON payload is exactly `{"format":"json","meta":{...},"rows":[...]}`. The
table renders the `n(N)` selected rows; `--all` renders the **whole ranked
queue** (view only; it does not change the budget).

**Row keys** (every row, both modes):

```
id            canonical entity id
last_reviewed ISO date, or null when never reviewed
age_days      today − last_reviewed, or null when never reviewed
rank          1-based position in the total order
selected      bool = rank ≤ n(N)
freshness     nullable freshness state (see §6.2); null for correspondence
              rows and whenever graph enrichment is unavailable
```

`rank` and `selected` on every row make it unambiguous that `--all` displays the
full queue while only its prefix is the sweep's budget.

**Meta keys:**

```
pool_size       N (eligible corpus size)
budget          n(N)
displayed       rows printed (n by default, N under --all)
coverage_rounds ⌈N/n⌉, defined as 0 when N = n = 0 (⌈N/n⌉ is otherwise undefined)
graph_source    single graph-enrichment status: current | absent | stale | invalid
```

### 6.2 Annotations — best-effort, never blocking

Annotations enrich selected rows but never block selection or change the
ordering.

- **Freshness enrichment** (epistemic rows): when a materialized `graph.trig` is
  present and current, attach each epistemic entity's freshness state to its
  nullable per-row `freshness` field. Trust in that graph is a **single
  payload-level judgement**, `meta.graph_source`, derived once per invocation —
  not repeated per row:
  - `absent` — no graph file present;
  - `invalid` — graph file present but unreadable/malformed;
  - `stale` — graph present but older than the newest source markdown, per the
    existing `graph_is_stale(project_root, graph_path)` authority (`entities.py`);
  - `current` — graph present and not stale.
  Per-row `freshness` is populated **only** when `graph_source == current`;
  otherwise every row's `freshness` is `null` (correspondence rows are always
  `null` — they have no freshness state). A stale graph's values are never
  presented as current — the status says `stale` and the rows read `null`.
  Enrichment being unavailable never blocks or delays selection.
- **Drift enrichment is deferred (`--with-drift` NOT in v1).** S4's validation
  surface honors evidence-scoped acceptance (an accepted false positive is
  suppressed). A raw, targeted single-entity drift probe would bypass that and
  could resurrect an accepted false positive. Doing it correctly requires an
  **accepted-aware single-entity drift instrument**, which is separate work. In
  v1, drift stays where it belongs: `science validate` / `science health`.

## 7. Components (isolation)

- `science_tool/curate/rotation.py` — pure selection core in the **existing**
  `curate` package (no new `curation/` boundary): `eligible_corpus(project_root)
  -> list[EligibleEntity]` (via `load_markdown_entities` → scope filter →
  terminal-status filter → read `status`/`created`/`last_reviewed`) and
  `rotation_budget(pool_size: int) -> int` (the piecewise formula), plus
  `select_rotation(project_root, *, today) -> RotationResult` composing them into
  the total order, ranked rows, and meta. No I/O beyond `load_markdown_entities`;
  no graph, no git.
- Freshness enrichment reader (best-effort, isolated) — computes the single
  `graph_source` judgement (`absent`/`invalid`/`stale`/`current`, reusing
  `graph_is_stale`) and, only when `current`, returns per-ref freshness states;
  any failure degrades to `invalid`, never raises into selection.
- CLI command `entity rotation` in `entities_cli.py` — argument parsing plus a
  single `emit_query_rows` call. Thin; all logic lives in the core.

## 8. Testing strategy

- **Budget boundaries:** `n(0)=0`, `n(1)=1`, `n(25)=25`, `n(26)=25` (`< 26`),
  `n(100)=41`, and the `n(389)=57` / `⌈389/57⌉=7` anchor; monotone
  non-decreasing across the tested range.
- **Total order:** never-reviewed sorts first; date ties break by `created`;
  missing `created` treated as oldest; final `id` tie-break — including a fixture
  where all three keys are needed to disambiguate.
- **Corpus filter:** archived (`_archive/`) excluded; `none`-scoped kind excluded;
  each `CLOSED_LIFECYCLE_STATUSES` member excluded; a Markdown file under an
  **unregistered** directory does not appear (enumeration via
  `load_markdown_entities`, not a raw scan); commons-overlay / adapter-only rows
  absent.
- **Coverage invariant:** the `n=1` counterexample — A reviewed yesterday, B
  today — must show that stamping A `today` re-selects A and starves B, while
  stamping A strictly after the pre-round maximum covers B by round 2. A fixed
  corpus under the max-based condition reaches full coverage within `⌈N/n⌉`
  rounds.
- **Enrichment:** `meta.graph_source` takes the correct single value in each of
  the absent / invalid / stale / current graph conditions; per-row `freshness` is
  populated only under `current` and `null` otherwise (and always `null` for
  correspondence rows); selection succeeds in all four.
- **Output contract:** payload is `{"format":"json","meta":{...},"rows":[...]}`;
  rows carry `id`/`last_reviewed`/`age_days`/`rank`/`selected`/`freshness` with
  the specified null semantics; `meta.coverage_rounds` is `0` when `N=n=0`;
  `--all` displays `N` rows with only the prefix `selected`.

# Attention-ranking recency correctness — design (fb-2026-07-10-023)

**Status:** Decision-ready (pending review acceptance). Branch `attention-recency-correctness`.

This closes item 3 of the InstrumentResult-convergence follow-on list
(`docs/plans/2026-07-11-instrument-result-convergence-design.md` §"Follow-on
work"). It is a **scoring-model correction**, not a return-shape change — the
convergence design explicitly carved it out as out of scope for that reason.

## 1. The defect

The attention weight (`graph/attention.py:161-167`) carries **two overlapping
recency channels**:

1. `freshness_multiplier` (`:158,164`) — `needs-review`→3×, `stale`→2×,
   `fresh`→1×. **Bounded.** Derived from `sci:freshnessState`, which the
   freshness pass computes from a principled baseline (`freshness.py:340`:
   `last_reviewed or created`), a project-configured `review_horizon_days`, and
   upstream-change awareness.
2. `days_since_last_review` raw term (`:163`, `* (1.0 + days / 30.0)`) —
   **unbounded**, linear, reads **only** `sci:lastReviewed`, and substitutes a
   flat magic `NEVER_REVIEWED_DAYS = 365` for never-reviewed entities (`:663`),
   ignoring `created` entirely.

Channel 2 is a strictly worse duplicate of channel 1. Because nearly every
entity in a typical corpus is unreviewed, channel 2 evaluates to the same
`1 + 365/30 = 13.17×` on almost every candidate — a **uniform** multiplier that
**cancels out of the ranking** (a uniform scale preserves order). So recency is
**inert**: it moves nothing. Worse, the naïve repair is perverse: the moment
review events are stamped, an *unstamped* entity still scores 13.17× while one
reviewed yesterday scores 1.03×, so **stamping reviews would make unstamped
entities dominate** — precisely because flat-365 is a wildly wrong stand-in for
"never reviewed" when the freshness pass already models that case via `created`.

The reporter (fb-2026-07-10-023) observed the surface symptom:
`days_since_last_review: 365` on every row of `attention-sample`.

### Already fixed, not re-touched: fb-2026-07-11-005

The paired ticket — a retired/closed hypothesis ranked *first* by urgency on its
accumulated open questions and incoming `bears_on` — is **already resolved** by
the `_is_closed` terminal-drop at `attention.py:148` (shipped `97b4e857`, "status
is the lifecycle, verdict is the conclusion"). Closed entities are dropped from
candidacy before scoring. This design records that so the follow-on pairing can
be closed as a unit; it makes no change there.

## 2. The fix: delete the redundant channel

Remove the `* (1.0 + days_since_last_review / 30.0)` factor from the weight
product. Recency continues to influence ranking **only** through the
already-bounded `freshness_multiplier`. One recency channel, bounded, no magic
constant.

Concretely in `graph/attention.py`:

- Delete the factor from the `weight` expression (`:161-167`).
- Delete the `NEVER_REVIEWED_DAYS` constant (`:29`) — it existed solely as a
  scoring stand-in.
- Replace the float-with-sentinel helper `_days_since_last_review(knowledge,
  entity_uri, today) -> float` with:

  ```python
  def _last_reviewed_date(knowledge, entity_id: str, entity_uri: URIRef) -> date | None:
      """The entity's sci:lastReviewed date, or None if it was never reviewed.

      Absence (no triple) is None. A PRESENT but invalid value is a corrupt
      graph, not an absence, and raises — silently reading it as None would
      misrepresent bad data as 'never reviewed'.
      """
  ```

  **Absent triple → `None`. Present-but-invalid → `ValueError`.** These must
  not collapse to the same value (fail early; corrupt data is not absence).

  **Strict lexical contract.** The freshness pass writes `sci:lastReviewed` as
  `Literal(d.isoformat(), datatype=XSD.date)` (`freshness.py:392`), so the only
  valid lexical form is `xsd:date` — `YYYY-MM-DD`. Parse the **whole** literal
  with `date.fromisoformat(text)`; do **not** slice (`text[:10]`) — the current
  `_parse_date_literal` (`:670-679`) slices and so accepts `2026-05-01garbage`,
  masking corruption. Drop that helper's `datetime`/`Z` fallback here: this field
  is a date, not a timestamp. The raised `ValueError` **names the entity id and
  the offending value**, e.g.
  `f"{entity_id}: sci:lastReviewed value {raw!r} is not a valid ISO date (YYYY-MM-DD)"`
  — that message is what the CLI surfaces (§4, "Corrupt-date CLI handling").

Reasons are unaffected: `_derive_phase1_reasons` (`:405-457`) derives only from
kind + support/dispute counts, and open-question debt drives its own reason —
neither reads recency or `freshness_multiplier`.

## 3. Data-shape change

`AttentionCandidate` gains a first-class field `last_reviewed: date | None`. The
`days_since_last_review` key is **removed from the `components` mapping**.

`components` is `Mapping[str, float]` — the scoring-input/breakdown map (it
already holds raw inputs like `incoming_bears_on`, `support_count`, and
`dispute_count`, not only multiplied factors). A `date | None` is neither a
float nor a scoring input, so it belongs as its own field, not in `components`.
Removing the recency value from `components` keeps that map an honest ledger of
what feeds the weight.

## 4. Rendering contract

`format_attention_candidate` (`:365-386`) drops `days_since_last_review` and
emits `"last_reviewed": "<ISO date>" | null`. `null` (never reviewed) directly
replaces the misleading flat `365` the ticket complained about.

**JSON vs table representation.** The JSON row carries the machine value —
an ISO date string or `null`. Table and skeleton *cells* show `never` for the
null case (an ISO date otherwise). The two CLI tables achieve this with a
table-only stringification in the `table_rows` comprehension, mirroring the
existing `reasons`-join transform at `cli.py:656-662`; the Wander skeleton
stringifies in its own render loop. JSON is never stringified — `null` stays
`null`.

Every surface that renders review recency is updated to the honest value:

| Surface | Before | After |
|---------|--------|-------|
| `graph attention-sample` table (`cli.py:671`) | column `("days_since_last_review", "Days")` | column `("last_reviewed", "Last reviewed")` |
| `graph attention-rank` table | *(no recency column)* | **add** column `("last_reviewed", "Last reviewed")` |
| JSON for both commands | `days_since_last_review` in row | `last_reviewed` in row (via `format_attention_candidate`) |
| Wander skeleton table (`wander/skeleton.py:36-40`) | `"Last reviewed (days)"` from `components[...]` | `"Last reviewed"` from `bundle.last_reviewed` (ISO date / `never`) |
| Wander JSON (`wander/skeleton.py:116` `_bundle_to_dict`) | recency reachable only via `components["days_since_last_review"]` | explicit `"last_reviewed"` key (ISO date / `null`) |

`attention-rank` is the deterministic review queue — the surface where
"when was this last looked at" is most useful — so it gains the column rather
than only replacing the sample column.

This is a **breaking change** to the row/JSON schema of `attention-sample`,
`attention-rank`, the Wander skeleton table, **and Wander JSON**. Acceptable per
project doctrine (internal tooling, no compatibility layer); called out so the
plan updates every column config, JSON assertion, and skeleton fixture.

### Wander propagation

`wander/context.py` `ContextBundle` gains `last_reviewed: date | None`, set from
`candidate.last_reviewed` in `assemble_bundle` (`context.py:51-57`).

Both Wander render paths carry it, because `_bundle_to_dict` hand-selects fields
(it does not spread the candidate) and would otherwise drop recency entirely once
the key leaves `components`:

- **Skeleton table** (`skeleton.py:36-40`): render `bundle.last_reviewed` — ISO
  date when set, `never` when `None`.
- **JSON** (`skeleton.py:116` `_bundle_to_dict`): add
  `"last_reviewed": bundle.last_reviewed.isoformat() if bundle.last_reviewed else None`.

### Corrupt-date CLI handling

`_last_reviewed_date` raises `ValueError` (from inside
`compute_attention_candidates`) on a present-but-invalid `sci:lastReviewed`. The
two `graph attention-*` commands must surface it as a clean
`click.ClickException`, not a traceback. Today the handling is **inconsistent**:
`graph attention-sample` already wraps `query_attention_sample` in
`try/except ValueError → ClickException` (`cli.py:641-652`), but
`graph attention-rank` calls `unwrap_instrument(query_attention_ranked(...))`
directly (`:705`) with no wrap. Add the same `try/except ValueError` around
`attention-rank`'s `query_attention_ranked` call so corrupt data yields the
entity-naming message from §2, on both commands. (Wander already wraps its
`compute_attention_candidates` call in `try/except ValueError → ClickException`,
so its path is covered.) Tested on both attention commands in §7.

## 5. Dead-API removal: `today`

Once the recency term is gone, `current_date = today or date.today()`
(`attention.py:110`) has no remaining reader — `_days_since_last_review` was its
only consumer, and `_is_closed` takes no date. The `today` parameter therefore
becomes dead and must be removed everywhere it exists **only** to feed attention
scoring; leaving it would create a misleading control (`--today` help text: "Date
for age weighting.").

Remove `today` from:

- `compute_attention_candidates` (`attention.py:90`)
- `query_attention_sample` (`:289`) and `query_attention_ranked` (`:320`)
  (both only pass it through)
- `wander/sampling.py` `sample_for_walk` (`:24`) (only forwards it; would
  otherwise break against the new signature)
- `graph attention-sample` / `attention-rank` CLI: remove the `--today` option
  and the `sample_date` / `rank_date` plumbing (`cli.py:615,630,640,646` and
  `:686,695,704,709`)

**Keep** Wander's `--today` (`wander/cli.py:48`). It legitimately controls
`walk_date`, which still dates the walk (`walk_id`) and drives stub-smell
evaluation (`compute_stub_signals(b, today=walk_date)`, `cli.py:96`). Only its
`today=walk_date` argument to `compute_attention_candidates` (`cli.py:84`) is
dropped, and the option help is updated to drop "sampling" (now: "Override the
date used for the walk and stub-smell").

## 6. Side-effect I checked: sampling scale

The deleted factor was ~13.17× and near-uniform on today's corpus. Ranking order
is **exactly** preserved only among candidates over which the deleted age factor
was uniform — i.e. the all-unreviewed common case, where a uniform multiplier
does not reorder. Where reviewed and unreviewed candidates mix, order **does**
change, and that change is the **intended** correction (the old term made an
unstamped entity outrank a freshly-reviewed one). It also shrinks absolute
weights ~13×, which raises the relative prominence of the
additive `epsilon` floor (`DEFAULT_EPSILON = 0.05`): with a multiplicative base
of 1, epsilon's maximum contribution to a candidate's weight becomes ~4.8%
(`0.05 / 1.05`), versus ~0.4% when the 13× inflation was present.

Leaving `epsilon` untouched is appropriate for this narrowly scoped fix — the new
prominence is *toward* epsilon's documented intent (a small exploration floor on
an O(1)-scale weight), not away from it. Note that the **sampling distribution**
shifts, not merely absolute weights: because epsilon is additive, low-weight
candidates get a slightly larger relative sampling chance than before. This is a
behavioural change worth recording; it is not a regression. Recalibrating epsilon
is explicitly out of scope (§9).

## 7. Testing

All tests build a small in-memory `Dataset` with `sci:freshnessState` triples
(and `sci:lastReviewed` where needed) under `graph/knowledge`.

- **The recency channel is gone (the assertion fb-2026-07-10-023 lacked).**
  Three candidates identical in every scoring input **and holding
  `freshness_state` constant** — differing only in `last_reviewed` (recent /
  old / `null`) — produce the **same weight**. This isolates the removed
  raw-date channel from the freshness channel.
- **Recency still ranks via freshness.** A `needs-review` entity outranks an
  otherwise-identical `fresh` one (`freshness_multiplier` still discriminates).
- **Perverse-repair guard.** A never-reviewed (`fresh`, `last_reviewed = None`)
  entity does **not** outrank a recently-reviewed, otherwise-identical `fresh`
  entity on recency alone.
- **Honest output.** A never-reviewed row emits `last_reviewed: null` (never
  `365`); a stamped entity emits its ISO date; `components` contains no
  `days_since_last_review` key.
- **Both CLI tables + Wander.** `attention-sample` and `attention-rank` tables
  each render a "Last reviewed" column; the Wander skeleton renders the ISO
  date / `never`.
- **`_last_reviewed_date` contract.** Returns the parsed date when
  `sci:lastReviewed` is present and valid; `None` when the triple is **absent**;
  raises `ValueError` when the triple is **present but invalid**. Pin all three
  cases, and specifically use `2026-05-01garbage` (not merely `not-a-date`) for
  the invalid case, to prove the fix rejects trailing garbage the old `[:10]`
  slice accepted. The raised message contains the entity id and the raw value.
- **Corrupt-date CLI surfacing.** With a corrupt `sci:lastReviewed` in the graph,
  **both** `graph attention-sample` and `graph attention-rank` exit non-zero with
  a `ClickException` naming the entity and the invalid value — not a traceback.
- **`today` is gone.** `compute_attention_candidates` and the two `query_*`
  functions no longer accept `today` (a call passing it raises `TypeError`); the
  `graph attention-*` commands no longer expose `--today`.

## 8. Files

- `science/src/science_tool/graph/attention.py` — weight formula;
  `AttentionCandidate.last_reviewed`; `format_attention_candidate`; helper
  rename/contract; `NEVER_REVIEWED_DAYS` deletion; `today` removal.
- `science/src/science_tool/graph/cli.py` — both attention table column configs;
  remove `--today` options and `sample_date`/`rank_date` plumbing; wrap
  `attention-rank`'s `query_attention_ranked` call in `try/except ValueError →
  ClickException`.
- `science/src/science_tool/wander/context.py` — `ContextBundle.last_reviewed`
  + `assemble_bundle`.
- `science/src/science_tool/wander/skeleton.py` — skeleton table column **and**
  the `last_reviewed` key in `_bundle_to_dict` (JSON).
- `science/src/science_tool/wander/sampling.py` — drop `today` from
  `sample_for_walk`.
- `science/src/science_tool/wander/cli.py` — drop `today=` arg to attention;
  update `--today` help.
- Tests:
  - `science/tests/**/test_attention*.py` — update weight/column/JSON
    assertions; add the recency-gone, freshness-still-ranks, perverse-repair,
    honest-output, `_last_reviewed_date`, corrupt-date CLI, and `today`-removed
    tests (§7).
  - `science/tests/test_wander_sampling.py` — drop `today` from
    `sample_for_walk` call sites.
  - `science/tests/test_wander_context.py` — assert `ContextBundle.last_reviewed`
    is populated from the candidate.
  - `science/tests/test_wander_skeleton.py` — table "Last reviewed" column and
    JSON `last_reviewed` assertions; update its direct `ContextBundle(...)`
    constructions for the new field.
  - `science/tests/test_wander_stub_smell.py` — update its direct
    `ContextBundle(...)` constructions for the new field.
  - `science/tests/test_wander_cli.py` — `--today` still accepted (walk/stub),
    no longer influences attention.
- Docs: add authoritative status banners to
  `docs/plans/2026-07-11-instrument-result-convergence-design.md` and
  `-plan.md` marking the attention-ranking pair (fb-2026-07-10-023 +
  fb-2026-07-11-005) **resolved** when this ships.

## 9. Out of scope

- The freshness model itself (`derive_freshness`, the `freshness_multiplier`
  buckets, `review_horizon_days`). Recency modeling stays where it already lives.
- Recalibrating `epsilon` or the sampler (§6). This fix removes a channel; it
  does not re-tune the ones that remain.
- Finer within-`freshnessState` recency ordering. If the 3-bucket multiplier
  proves too coarse for the review queue, that is a change to the freshness
  model (a bounded continuous staleness signal), not a second recency term
  bolted onto attention — a separate, additive follow-up.

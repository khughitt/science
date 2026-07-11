# Instrument Result Convergence — the Silent-Instrument Ruling

## Status

Decision-ready. Cross-cutting ruling extracted from the 2026-07-11 downstream
feedback triage (50 open entries). Names its canonical type, its migration, and
its guard, in the shape of
[`2026-07-10-half-applied-pattern-convergence-design.md`](2026-07-10-half-applied-pattern-convergence-design.md).

Blocks two other planned specs (big-picture run integrity; curate + transient
placement), both of which would otherwise invent a local status-surface
convention of their own.

## Context

Five open feedback entries, from three different projects, are the same failure:

> **an instrument returns a clean-looking empty result when it never actually ran.**

The reported instances:

| Entry | Surface | What renders |
|---|---|---|
| `fb-2026-07-11-004` | `compute_topic_gaps` | "No knowledge gaps detected this run." — when *every* question's topic ref failed to resolve |
| `fb-2026-07-11-014` | `count_research_orphans` | a count with no list counterpart, so callers re-derive `orphan_ids` and silently disagree with it (40 vs 31 observed) |
| `fb-2026-07-11-016` | `graph diff` | "graph-prose sync: all inputs up to date" — because the walk never entered `entities/` |
| `fb-2026-07-11-017` | `supersedes:` | a top-level key materializes **zero** triples, with no warning; MM30 has 0 `sci:supersedes` triples project-wide |
| `fb-2026-07-10-023` | `attention-sample` | `days_since_last_review: 365` on every row — a constant, so the freshness term is dead weight |

The same *shape* recurs in three more entries that belong to other specs and are
not re-litigated here: `curate inventory` returning a payload that silently omits
keys its own spec promises (`fb-2026-07-10-017`), `missing_source_refs`
over-reporting (`fb-2026-07-10-019`), and the `orphaned-executable` false positive
that has trained reviewers to ignore an entire warning class
(`fb-2026-07-08-002`). They are evidence the ruling generalizes; they are not in
this spec's scope.

This directly violates the repo's own standing rule — *fail early, avoid silent
fallbacks* — and it is load-bearing, not cosmetic. `/science:update-graph` Step 1
says "If no files are stale, report Graph is up to date and stop." An
entities-only commit hits that stop condition **wrongly**. MM30's `t3288` already
recorded "graph diff --mode hybrid reports no stale files" as *evidence the graph
was current*.

### This is a half-applied pattern, not a missing one

The instrument surface is already half-converged. A structural query over
`science/src/science_tool` (58 helpers named `compute_*`/`count_*`/`query_*`/`list_*`/`collect_*`/`summarize_*`)
splits cleanly:

```
ALREADY TYPED
  compute_stats            -> StatsReport
  collect_inventory        -> CurationInventory
  compute_topic_coverage   -> TopicCoverage
  compute_source_snapshots -> SourceSnapshotResult
  query_cross_impact       -> CrossImpactPayload

AD-HOC PRECURSOR  (a reason channel, invented locally, twice)
  list_benchmarks -> tuple[list[BenchmarkRow], str | None]
  list_datasets   -> tuple[list[dict], str | None]

STILL BARE  (every reported bug lives here)
  compute_topic_gaps       -> list[TopicGap]
  count_research_orphans   -> int
  query_attention_sample   -> list[dict[str, Any]]
  graph/health.py           10 x collect_* -> list[...]
  graph/store/summary.py     8 x query_*   -> list[dict[str, str]]
  graph/store/queries.py     3 x query_*   -> list[dict[str, str]]
  graph/store/inquiry.py     2 x list_*    -> list[dict[str, str]]
```

Two independent helpers grew a `str | None` reason channel on their own. That is
the pattern trying to converge without a canonical form to converge *on*. Fixing
only the five reported sites would leave ~25 bare instruments able to reproduce
the identical bug, and would give the guard no principled boundary to key on.

## Non-goals

- Wrapping genuinely-total pure functions (`compute_vrs_id -> str`,
  `compute_source_hash -> str`). They cannot be unwired; a status surface there is
  ceremony without safety and dilutes what the guard means.
- Changing what any instrument *computes*. This is a return-shape and
  precondition-declaration change, not a re-derivation of any metric.
- The renderer-side prose of every affected command. Renderers must handle
  `unwired` distinctly (below), but their wording is left to the consuming specs.

## Decision

### 1. Canonicalize — `InstrumentResult`

Lives in **`science_tool`** (`science/src/science_tool/instruments.py`), beside
`output.py` — the analogous canonical module from convergence Phase 3.

It does **not** go in `science-model`. An earlier draft of this design placed it
there on the stated grounds that "`science_tool` and `science-qa` both read
instruments." That is false: `science/qa/pyproject.toml` depends on
`click`/`pandas`/`pyarrow`/`pyyaml` only, and `science_model` is imported nowhere
in `qa/src/`. Placing the type in the shared package would have introduced a
package dependency to serve a consumer that does not exist. `science_tool` is the
sole consumer; the type lives with it. If `science-qa` ever grows an instrument,
move it then and pay for the dependency edge deliberately.

The type **enforces** its invariant; it does not merely document it:

```python
class InstrumentResult(BaseModel, Generic[RowT]):
    status: Literal["ok", "empty", "unwired"]
    rows: list[RowT] = Field(default_factory=list)
    reason: str | None = None   # human: "14 of 14 questions reference unknown topics"
    code: str | None = None     # machine: "no_resolvable_topics"

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "InstrumentResult[RowT]":
        if self.status == "ok" and not self.rows:
            raise ValueError("status='ok' requires non-empty rows; use 'empty'")
        if self.status == "empty" and self.rows:
            raise ValueError("status='empty' forbids rows")
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self
```

The entire ruling reduces to one invariant:

> **`empty` and `unwired` are different, and the result cannot be constructed
> without choosing between them.**

- `ok` — the instrument ran and found rows. Requires non-empty `rows`.
- `empty` — the instrument ran and genuinely found nothing. *This is a real
  finding* ("no knowledge gaps this run") and must stay sayable. Requires empty
  `rows`.
- `unwired` — the instrument could not run. **`rows` is meaningless**; a caller
  that reports it as a finding is reporting a lie. Requires empty `rows` **and** a
  `code`.

A bare `[]` becomes unrepresentable, and so does every mixed state that would let
a caller keep producing clean-looking false results while technically using the
canonical type. The validator is the ruling; the docstring is not.

**Why a universal 3-value status** rather than per-instrument status enums
(`no_gaps`, `no_resolvable_topics` as first-class values): a universal status is
what the guard and the renderers can check *generically*. Per-instrument enums
would need ~30 renderers each hand-taught the vocabulary of one instrument, which
is how the current divergence happened. The instrument-specific semantics survive
intact — they live in `code` (machine-stable) and `reason` (human).

**Renderer contract.** A renderer MUST distinguish `unwired` from `empty`. It may
render `empty` as its documented one-liner; it MUST NOT render `unwired` as one.

```
ok       -> the gap table
empty    -> "No knowledge gaps detected this run."
unwired  -> "INSTRUMENT DID NOT RUN: 14 of 14 questions reference unknown topics."
```

And, independently of status: **a result carrying a `reason` must surface it.** A
successful run can still have silently dropped part of its input (see *Partial
resolution* below); an unqualified `ok` would be a quieter version of the same lie.

### 2. Migrate — by structural query, not by list

Per the convergence design's own lesson (its line 189: *"Do not migrate from this
list. Regenerate the set with that structural query at implementation time"*), the
implementer regenerates the set and migrates whatever it returns. The inventory
above is evidence that the problem is real and roughly how big it is — **it is not
the work order.**

Query: public helpers in the instrument namespace — `big_picture/`,
`graph/health.py`, `graph/store/{summary,queries,inquiry}.py`,
`graph/attention.py`, `curate/`, **`benchmark_catalog.py`, `datasets_catalog.py`**
— whose return annotation is either

- a bare `list` / `dict` / `int`, **or**
- a tuple whose first element is a `list` (the ad-hoc precursor form,
  `tuple[list[T], str | None]`).

Both forms must be in the query and in the guard. The two catalog modules are in
the namespace *because* they carry the precursor form; omitting them would let the
allowlist empty out while the very helpers this design promises to converge went
unmigrated.

**The real work is per-instrument and is not mechanical.** Each instrument must
declare its **precondition** — the condition whose absence means it never ran.

Some instruments have no unwired state; they get `status ∈ {ok, empty}` and that
is correct, not an exemption.

#### The precondition must not over-claim `unwired`

A precondition stated carelessly moves the false classification rather than
removing it. `compute_topic_gaps` is the worked example, and its three input
states are materially different:

| Input state | Status | Why |
|---|---|---|
| Included questions declare topic refs; **none** resolve | `unwired`, `code="no_resolvable_topics"` | The reported defect. Demand exists but was silently discarded, so a zero-gap result is a lie. |
| Included questions declare **no** topic refs at all | `empty` | No demand was expressed. Zero gaps is a **true** finding, not a failure. |
| **No** question survives the aspect filter | `empty` | Nothing was asked of the instrument. Also true — *unless the filter itself failed*, which is a distinct precondition the filter owns, not this one. |

So the precondition is **not** "≥1 question resolves to a topic." It is:

> **If at least one included question *declares* a topic ref and *none* resolve,
> return `unwired`. Otherwise execute normally.**

The distinction is declared-vs-resolved, not resolved-vs-nothing.

#### Partial resolution needs a caveat channel, not a status

The three states above omit the common case: some refs resolve and some do not.
The instrument genuinely ran, so the status is `ok` (or `empty`) — but part of the
demand was dropped, and reporting the result unqualified is a quieter version of
the same lie.

`reason` and `code` are therefore **not** exclusive to `unwired`. An `ok` or
`empty` result may carry them as a caveat:

```python
InstrumentResult(
    status="ok",
    rows=gaps,
    code="partial_topic_resolution",
    reason="7 of 10 question topic refs did not resolve; their demand is excluded",
)
```

The renderer contract extends accordingly: **a result carrying a `reason` must
surface it, whatever its status.** This is what `list_benchmarks`'
`tuple[list, str | None]` channel was reaching for, and it is why that precursor
converges onto this type rather than being deleted.

The type already permits this — only `unwired` *requires* a `code` — so no change
to the validator is needed.

#### Scalar counters are prohibited, not wrapped

`InstrumentResult` is row-shaped and has no natural representation for a scalar.
Rather than widen the contract to carry scalars, **the scalar counter is deleted**:

- `count_research_orphans() -> int` is **removed**. `list_research_orphans() ->
  InstrumentResult[Orphan]` replaces it, and callers that need the count take
  `len(result.rows)`.

This is the strongest available reading of `fb-2026-07-11-014`, which asked for the
count and the list to be unable to drift. The surest way for two functions not to
disagree is for there to be one function. It also keeps the guard's rule clean —
a bare `int` return in the namespace is simply prohibited, with no scalar
carve-out to reason about.

`big-picture`'s `orphan_question_count` frontmatter field is unaffected: it is
still a number, now sourced from `len(rows)` of the same call that produced
`orphan_ids`, which is precisely the drift the entry reported.

#### Out of scope: the attention scoring model (`fb-2026-07-10-023`)

`query_attention_sample` migrates its **return shape** here and nothing else. Its
`days_since_last_review: 365` defect is *not* fixed in this spec, because fixing it
means changing what the instrument **computes**, which this design's non-goals
forbid.

It is worth recording what the review of this design surfaced, because the entry
understates the bug. The term is multiplicative (`graph/attention.py:110`):

```python
weight = (1.0 + incoming_bears_on) * (1.0 + (days_since_last_review / 30.0)) * ...
```

At the constant `365` this is a uniform **13.17×** factor on every candidate — so
it currently cancels out of the *ranking* altogether (a uniform scale preserves
order). The freshness signal is not merely non-discriminating; it is **inert**.
Worse, the naive repair is actively harmful: the moment review events are stamped,
an *unstamped* entity still scores 13.17× while one reviewed yesterday scores
1.03×, so **stamping reviews would make unstamped entities dominate the ranking.**

Availability is also **per-candidate**, not per-result, so a single result-level
`status` cannot express it — the abstraction in this spec is structurally the
wrong instrument for the job.

This needs an explicit scoring-model decision (per-row component availability;
behaviour for mixed stamped/unstamped candidates), and it belongs with
`fb-2026-07-11-005` — the retired hypothesis that dominates the attention ranking
by open-question debt. Both are **attention-ranking correctness**. They get their
own design; see [Follow-on work](#follow-on-work).

### 3. Guard — `tests/test_instrument_boundary.py`

In the shape of the five existing AST guards (`test_output_boundary.py`,
`test_frontmatter_boundary.py`, `test_durable_write_boundary.py`,
`test_project_root_boundary.py`, `test_store_package_structure.py`): an
**additive ratchet**, with its detection rule and its known gaps stated in the
module docstring rather than hidden.

Rule: a public helper in the instrument namespace may not carry a bare
`list` / `dict` / `int` return annotation, **nor the `tuple[list[T], str | None]`
precursor form**. It must return `InstrumentResult[...]`.

The guard's namespace and the migration's structural query are the **same
expression**, defined once and imported by both. If they are written twice they
will drift, which is the failure this whole design exists to stop.

The ratchet seeds its allowlist with the not-yet-migrated helpers and **empties it
as they migrate**. Per the convergence design (its line 271): an allowlist entry
the guard would still flag means the migration is incomplete — *not* a carve-out
to add.

Known gap, stated rather than hidden: the guard checks the return **annotation**,
so an un-annotated helper, or one annotated `Any`, evades it. This is a ratchet
against the bare-collection return that recurred across the tree, not a sandbox —
the same class of limit the output and durable-write guards document candidly.

### 4. The two siblings that are not read-side

Same disease, different mechanism. They do not fit `InstrumentResult` and get
their own phases rather than being bent into it.

**`fb-2026-07-11-016` — the walk-side instrument (`graph diff`).** `build_input_manifest`
(`graph/io.py:305-312`) hard-codes an include list that omits `pp.entities_dir`;
the `except`-branch fallback at `:317` omits it too. Appending it is a one-line fix
and it closes the reported bug — but it does **not** close the *class*, and a test
asserting only "entity files now report stale" passes on the one-liner while
leaving the class wide open. The next directory added to the layout reintroduces
the identical silence.

The principled fix is that the manifest must record **which directories it walked**,
so "walked `entities/`, found nothing" is distinguishable from "never walked
`entities/`" — `empty` vs `unwired`, applied to a walk.

**This requires an envelope, not an extra key.** The manifest is today
`dict[str, dict[str, int | str]]` — relative path → `{sha256, mtime_ns}` — JSON-dumped
into a single `schema:text` literal on `REVISION_URI` (`graph/io.py:133-143`). Both
`read_revision_manifest` (`:271-295`) and `_revision_timestamp_from_manifest`
(`:258-262`) iterate `manifest.values()` expecting a file record. A top-level
`walked` key would be handed to them **as if it were a file**. So:

```jsonc
{
  "schema": 2,
  "walked": ["doc", "entities", "specs", "tasks", "knowledge/sources", ...],
  "files":  { "<relpath>": {"sha256": "...", "mtime_ns": 123} }
}
```

`read_revision_manifest` returns the envelope; the file map moves under `files`, and
`_revision_timestamp_from_manifest` reads `files.values()`.

**A v1 baseline is an unwired instrument, and is treated as one.** A manifest
persisted before this change records no walk set, so `graph diff` *cannot know* what
its baseline covered — it is structurally unable to tell "clean" from "never looked."
It must therefore report `unwired` (`code="baseline_predates_walk_set"`) and demand
a rebuild, **not** report "all inputs up to date."

This is deliberately **not** a compatibility layer (which the repo forbids by
default): it is this design's own ruling applied to itself. The cost is nil, because
a rebuild is already mandatory — the blast radius below requires one regardless.

Blast radius to plan for, not discover: the first rebuild after this lands stamps
~2,600 new manifest entries in MM30, and until then every entity file reports
`new_file` once.

Note the irony worth recording: `compute_source_snapshots`
(`graph/source_snapshots.py:96-141`) *already* persists `sci:sourcePath` +
`schema:sha256` for every markdown entity (2,628 such triples in MM30's graph).
The baseline hashes needed to detect entity staleness are **already in the graph**;
`graph diff` simply does not consult them.

**`fb-2026-07-11-017` — the authoring-side instrument (`supersedes:`).** A
top-level `supersedes:` / `amends:` frontmatter key materializes zero triples,
silently — the graph source of truth is a `relations:` entry with predicate
`sci:supersedes` (`consolidation.py:8-9`). MM30 has two interpretations that
authored the top-level form and produced nothing. Fix: a `validate` lint — **a
frontmatter field that materializes nothing is an error, not a no-op.**

This one has a downstream consequence that links it to the big-picture spec:
`big-picture` computes `provenance_coverage` from these chains (≥60% high, ≥30%
partial). The silent drop directly produces a wrong `thin` rating, which is what
subjects every MM30 hypothesis to the 150-word Arc cap in `fb-2026-07-11-015`.
**Fixing this shrinks that item.**

## Sequencing

Type → guard (failing, allowlist full) → migrate until the allowlist is empty.
The guard defines "done"; a checklist would not.

1. `InstrumentResult` in `science_tool/instruments.py` + its validator unit tests
   (each invalid construction must raise).
2. `test_instrument_boundary.py`, allowlist seeded with the current bare set.
3. Migrate the namespace, instrument by instrument, each with its precondition
   declared. Allowlist shrinks monotonically.
4. Sibling phases: the `graph diff` walk (`fb-016`) and the materialization lint
   (`fb-017`). Independent of 1–3; may land in parallel.

## Blast radius

Changing ~30 return types breaks every caller: CLI renderers, `big_picture`, and
their tests. This is a **large mechanical diff with a small semantic core**. It is
worth saying plainly so the diff size is not mistaken for risk — the risk is
concentrated entirely in step 3's per-instrument precondition judgments, and
nowhere else.

## Validation

```bash
cd science && uv run --frozen pytest
cd science && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest
```

Acceptance:

- `test_instrument_boundary.py` passes with an **empty** allowlist.
- `InstrumentResult` **rejects** each invalid construction: `ok` with no rows,
  `empty` with rows, `unwired` with rows, and `unwired` without a `code`. These are
  unit tests on the validator, not conventions in a docstring.
- `compute_topic_gaps` is tested on **all four** input states, so the fix cannot
  merely invert the misclassification:
  - questions declare topic refs, none resolve ⇒ `unwired` / `no_resolvable_topics`;
  - questions declare no topic refs ⇒ `empty` (a true zero-gap finding);
  - no question survives the aspect filter ⇒ `empty`;
  - some refs resolve, some do not ⇒ `ok` **carrying** `code="partial_topic_resolution"`,
    and the rollup surfaces the caveat.
- The rollup renders the `unwired` case as an instrument failure, **not** as
  "No knowledge gaps detected this run."
- `count_research_orphans` **no longer exists**; `grep -r count_research_orphans`
  returns nothing outside this design doc and the changelog.
- `graph diff` distinguishes **walked-but-empty from never-walked**: a project with
  an empty `entities/` reports clean, and a manifest whose `walked` set omits
  `entities/` reports `unwired`, not "up to date." *A test asserting only that
  entity files go stale is insufficient — the one-line include fix passes it without
  implementing the walk-set contract.*
- A v1 (envelope-less) baseline manifest makes `graph diff` report
  `baseline_predates_walk_set` and demand a rebuild.
- A top-level `supersedes:` key fails `science validate`.

## Follow-on work

Carved out of this design deliberately, with the reason recorded so it is not
silently dropped:

- **Attention-ranking correctness.** `fb-2026-07-10-023` (the inert, and on repair
  actively perverse, `days_since_last_review` term) and `fb-2026-07-11-005` (a
  retired hypothesis ranked *first* by urgency on 10 open questions and 27 incoming
  `bears_on`) are one subject. Both require a scoring-model decision — per-row
  component availability, behaviour for mixed stamped/unstamped candidates, and
  what retirement does to question re-homing and attention weight. Neither is a
  return-shape change and neither belongs here.

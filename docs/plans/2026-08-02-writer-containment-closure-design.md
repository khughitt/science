# Writer Containment Closure — Design

**Status:** design of record. Two sequenced landing slices, one design.

**Goal:** no writer may turn a base-shape-valid entity record into an invalid one, and a
promotion batch that would do so writes nothing at all.

---

## 1. The gap

`certify_persisted` — the **persisted-shape** certification — is called in exactly two
places, both inside `science/src/science_tool/dag/entity_frontmatter.py`: `render_create` and
`render_update`. No other path that rewrites entity frontmatter certifies persisted shape.

That is a narrower claim than "uncertified". `_validate_prospective_write` (`entities.py:1793`,
used at `:920`, `:1085`, `:1326`) certifies a **different property** on other entity writers —
prospective reference resolution and audit rows — and says nothing about whether the result
satisfies base shape. The two are complementary, and neither substitutes for the other.

Two renderers in `science/src/science_tool/entities.py` carry that traffic:

| Renderer | Reached by |
|---|---|
| `render_entity_source_refs` (`:477`) | `append_entity_source_ref` (`:524`), and directly by reconciliation (`:647`) |
| `render_entity_frontmatter_updates` (`:504`) | resynthesis (`:495`), reconciliation (`:668`) |

**Five workflows**, named by their entry points, not five literal call sites:

| # | Entry point | Renderer traffic | Write style |
|---|---|---|---|
| 1 | `apply_candidates` (`promote.py:400`) | both its MINT-accrual route (`:304`) and its LINK route (`:430`) | immediate |
| 2 | `promote_prose_unit` (`prose_promote.py:148`) | LINK, two refs (`:238-239`) | immediate |
| 3 | `apply_prose_promotion_plan` (`prose_promotion_batch.py:77`) | LINK, two refs (`:135-136`) | immediate |
| 4 | `apply_resynthesis_draft` (`proposition_resynthesis_apply.py:665`) | lineage updates (`:495`) | staged |
| 5 | `apply_canonicalization_plan` (`proposition_reconciliation_apply.py:788`) | **both** renderers — source refs (`:647`) and duplicate supersession (`:668`) | staged |

Workflows 4 and 5 are distinct staged workflows in separate modules, not one item: resynthesis
lineage and reconciliation supersession are planned and applied independently.

Neither renderer is kind-scoped. Promotion targets `proposition`, `question` and
`hypothesis` (`build_targets()`, `promote.py:392`); the two prose paths resolve their
destination through `find_entity`, which reaches any kind.

### 1.1 A guard already predicted this work, and is one writer short

`tests/test_hypothesis_consumers.py:263-276`
(`test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis`) pins the call-site set of
`render_entity_frontmatter_updates` and says in its own comment that the writer "runs NO
schema or resolution check", that this "is not a hole TODAY because both its callers
operate on PROPOSITIONS", and that it "becomes a hole the day a third caller points it at
a hypothesis, or the day the proposition slice runs — and this is the test that will say
so."

The reasoning is sound and the roster is real. It ranges over one writer and not its
sibling: **`append_entity_source_ref` already reaches `hypothesis`** through promotion
LINK, and `hypothesis` is an armed kind. No record is currently broken by it — the write is
an append that preserves base shape — but the boundary the guard asserts does not hold for
the writer it does not name. A guard that lists its scope has a hole by construction; this
design closes the hole by making the *renderers* certify, so containment no longer depends
on a roster staying complete.

The guard's roster and its comment both need updating in slice 1: the premise "runs NO
schema check" stops being true.

---

## 2. The invariant: a writer may not degrade a record

Inside each renderer, validate the pre-image and the post-image with
`EntityValidator.validate_persisted_base_shape`. **Refuse iff the pre-image satisfies base
shape and the post-image would not.**

Exactly one transition is forbidden:

| Pre-image | Post-image | Result |
|---|---|---|
| valid | valid | write |
| valid | **invalid** | **refuse** |
| invalid | invalid | write |
| invalid | valid | write |

Consequences, stated so a later reader does not mistake them for oversights:

- **A record that already fails base shape stays writable.** 183 records across 13 kinds
  fail it today (measured 2026-08-02 over 8209 records in 40 project roots; 41 of them are
  `question`, a live promotion LINK target). Refusing writes to those would couple this
  work to migrating them. This branch performs **no intentional backfill**: it never sets out
  to repair a record, though a write whose own content happens to satisfy base shape is
  allowed through (the `invalid → valid` row above).
- **This is deliberately weaker than `render_update`, not the same rule.** `render_update`
  calls `certify_persisted` unconditionally, so it **rejects an already-invalid record** —
  that is piece 1's "rejection, not backfill" ruling, and it is what makes a workbench update
  refuse the 769 legacy records rather than migrate them. These renderers cannot adopt it:
  they are kind-agnostic and serve live promotion traffic onto records this branch does not
  repair. The shared principle is only that neither writer backfills.
- **The guard is kind-agnostic** — it applies to every built-in or project-local kind routed
  through these renderers, rather than the two kinds piece 1 contained, and it does not need
  to know which kinds are armed. (For scale: `EntityType` has 52 members and
  `_BUILTIN_MARKDOWN_POLICIES` 37, plus whatever kinds a project declares locally. The guard
  ranges over whatever actually arrives, so no roster of kinds appears in it.)
- **Base shape only.** The typed half of `certify_persisted` needs a `WorkbenchEntity` the
  typed writers already hold and these paths do not. Fabricating one from arbitrary
  frontmatter would put the migration's own guesswork inside a certification.

### 2.1 The post-image is validated after rendering and reparsing

Validate the mapping obtained by parsing the **rendered text**, never the in-memory mapping
that was dumped. `certify_persisted` documents the reason at
`dag/entity_frontmatter.py:210-215`: the round trip is what catches a date the YAML dumper
emitted as a bare scalar, which reloads as `datetime.date` where the schema requires a
string. Validating the in-memory mapping would certify something that was never persisted.

That defect class is real but was the minority of piece 3's corpus: of the 792 records it
repaired, **769 had an empty `title`** and **23 differed in no parsed value at all** — those
23 were date-quoting alone, which is exactly what this round trip catches and an in-memory
check would miss.

### 2.2 How a refusal surfaces

The renderer **raises** `EntityDegradationError` (new, in `entities.py`, subclassing
`EntityCommandError` so existing `except EntityCommandError` handlers in the prose paths keep
their current shape). The message names the record and the validator's own text, so an
operator sees what base shape objected to rather than a paraphrase.

Naming the record requires a path the text-in signature no longer carries, so both renderers
take a **diagnostic-only** keyword:

```python
def render_entity_source_refs(
    current_text: str,
    refs_to_append: Sequence[str],
    *,
    entity_path: Path,
    as_of: date | None = None,
) -> tuple[str, bool]: ...
```

`entity_path` is used **only** to build the error message. The renderer performs no
filesystem I/O — it neither reads nor writes that path — so text-in/text-out and composition
(§4.3) are unaffected. Requiring it rather than defaulting it to `None` keeps every refusal
identifiable; a planner that has text has a path, since it read the text from one.

Raising rather than returning a refusal keeps the guard unskippable — a caller cannot ignore a
return value it never inspects — and matches `certify_persisted`, which raises
`PersistedShapeError`.

**Aggregation is the planner's job, not the renderer's.** A planner catches
`EntityDegradationError` per planned edit, records it, and continues planning so that one
refusal does not hide the next. It raises once, after planning, naming every refused record.
This is the same division piece 3 used: the repair planner collected refusals and the caller
raised once with all of them.

---

## 3. Slice 1 — the guard

### 3.1 Renderers become text-in / text-out

Both renderers currently take a `file_path` and read their own pre-image. Composition (§4.3)
is impossible under that signature, because every edit would re-read the unmodified file.
They become:

```python
def render_entity_source_refs(
    current_text: str, refs_to_append: Sequence[str], *, as_of: date | None = None
) -> tuple[str, bool]: ...

def render_entity_frontmatter_updates(
    current_text: str, updates: Mapping[str, object], *, as_of: date | None = None
) -> tuple[str, bool]: ...
```

The caller reads. `render_entity_frontmatter_updates`'s unchanged branch returns
`current_text` directly instead of re-reading the file, which also removes a redundant read.

Affected: 4 production call sites and ~12 test call sites across `test_entity_writer.py`,
`test_proposition_resynthesis_apply.py` and `test_hypothesis_consumers.py`.

### 3.2 The shared edit vocabulary

`proposition_resynthesis_apply.py:13-21` already imports six private names from
`proposition_reconciliation_apply.py` across a module boundary. That import list defines the
hoist set by evidence rather than by taste.

**Hoist** to a new `science/src/science_tool/annotation/planned_edits.py`:
`PlannedFileEdit`, `_edit`, `_current_text`, `_sha256_text`, `_path_string`,
`_changed_and_noop_paths`.

**Leave in reconciliation:** `ReconciliationApplyError` and `_live_annotation_index` (its own
domain), `CanonicalizationPreflight` (its fields — `expected_source_refs_by_canonical`,
`action_diagnostics_by_id` — are reconciliation's), and
`_changed_and_noop_paths_from_path_changes` (nothing else imports it; it serves
reconciliation's per-action map).

No transaction framework is invented. The hoist moves generic helpers and nothing else.

**`_current_text` must read with `open(newline="")`, not `Path.read_text()`.** `read_text`
applies universal-newline translation, so a CRLF body would be normalized to LF *before
planning* — a change to bytes the edit never intended, and one the round-trip guard would
then certify as correct. The preserving reader at `entities.py:1920-1923` is the precedent.

### 3.3 What slice 1 closes on its own

The two staged workflows (resynthesis, reconciliation) already plan-then-write, so the guard
contains them the moment it lands. `append_entity_source_ref` survives slice 1 unchanged as
the adapter its current callers need — it reads the file, calls the renderer, writes — and is
**deleted in slice 2** once its production callers are gone.

---

## 4. Slice 2 — preflight the three immediate-write workflows

`apply_candidates` and the two prose loops build a complete plan, aggregate every refusal,
then write. This is the pattern reconciliation already implements and that
`resolve_entity_slug`'s docstring (`entities.py`) already states as doctrine: "a caller
creating many entities in a loop calls this for each planned create up front, and a
predictable naming failure aborts the batch instead of stranding it half-written."
Promotion half-adopted it — it pre-screens slugs, then writes as it goes.

### 4.1 Which failures aggregate, and which may abort

Degradation is not the only deterministic preflight failure. Collision detection, slug
naming, template rendering and target resolution all fail deterministically too, and an
operator who fixes one refusal only to hit the next has not been told the truth about the
batch. The boundary:

- **Candidate-local deterministic errors are collected**, and the batch reports them
  together. This covers `EntityDegradationError`, slug-naming failures from
  `resolve_entity_slug`, LINK target-resolution failures, and the never-overwrite guard at
  `promote.py:296-300`. Planning continues past each one so the report is complete.
- **Batch-global errors may abort planning immediately** — a missing or malformed packaged
  template (`Renderer().sections(kind)`, `promote.py:351-352`), an unreadable sidecar, an
  unresolvable project root. They are not attributable to a candidate, every later candidate
  would raise the same thing, and continuing would produce noise rather than information.
  They still abort **before any write**, so the all-or-nothing property holds either way.
- Only the collected candidate-local set is aggregated. A batch-global abort reports one
  error, and says which stage it came from.

### 4.2 What all-or-nothing means, precisely

Atomicity **against deterministic preflight failures only.** The write stage can still fail
partway on I/O or concurrent drift. Reconciliation already models the honest answer at
`proposition_reconciliation_apply.py:806-816`, and slice 2 adopts its error shape verbatim:

```
[stage=write, files_written=N, written_paths=(...)] failed to write <path>: <error>
```

**The wrapping must cover every way the write stage can fail, not just `OSError` from
`atomic_write_text`.** A promotion apply's write stage also calls `claim_number_in_dir`,
which raises `EntityCommandError` on exactly the drift it exists to detect ("number NNNN was
committed since the preview; re-run the preview"), and then writes the sidecar via
`anno_io.write_sidecar`. If those escape unwrapped, the operator gets a bare error after N
files have already landed and the partial-state diagnostic — the whole point of the shape —
is missing precisely when it matters most. Wrap the write stage on `(OSError,
EntityCommandError)`, and let the sidecar/index write share the same wrapper.

No claim of transactional rollback appears anywhere in this design.

### 4.3 Planned edits compose per path

Each planner maintains `planned_text_by_path: dict[Path, str]`, initialized from disk **once**
per path, then feeds each post-image into the next edit for that path. One `PlannedFileEdit`
is constructed per path **after** composition, so `before_sha256` is the on-disk pre-image and
`after_sha256` is the composed result.

Two reachable cases make this load-bearing, not theoretical:

- A single LINK appends two refs through two sequential renderer calls.
- Two annotations can LINK to the same existing record; prose rows sharing one decomposition
  index are the same case.

Independent edits computed from the same disk pre-image would each contain only their own
change, and the last write would erase the others.

### 4.4 Numeric mints plan without consuming a number

`_mint_numeric` (`promote.py:341`) calls `reserve_entity` → `reserve_number_in_dir`, which
claims the **next** number and commits an empty placeholder `.md` to back it. Under preflight
that is actively wrong: planning would consume numbers and strand placeholders for a batch
that then refuses. `propose_number`'s docstring says so directly — "calling it from a dry run
leaves an empty entity behind and makes the subsequent apply mint a DIFFERENT number."

Slice 2 adopts the pair `entity_import.py` and `migrate_specs.py` already use:

- **Plan:** call `propose_number(project_root, kind)` **once per kind**, then allocate
  `base`, `base+1`, … in memory. `propose_number` is read-only, so repeated calls before any
  write return the same number — calling it per mint would hand every candidate the same id.
- **Apply:** each assigned number goes through `claim_number_in_dir`, which re-reads the
  archive under a sentinel and **refuses** a number claimed since the preview rather than
  silently taking the next free one. `entity_import.py:10` states the rule as doctrine: "The
  preview is READ-ONLY. Id proposal goes through `propose_number`."

---

## 5. Testing

**The guard, per renderer** — the four transitions of §2 are the test matrix: valid→valid
writes, valid→invalid refuses, invalid→invalid writes, invalid→valid writes. The two
`invalid→` rows are what prove the guard forbids one transition rather than enforcing
validity.

**The round trip** — a fixture whose in-memory post-image mapping is acceptable but whose
*rendered* text reloads differently (an unquoted date emitted as a bare scalar). It passes if
the guard validates the reparsed text and fails if the guard validates the mapping. Without
it, §2.1 is unenforced.

**CRLF** — a record with a CRLF body survives planning byte-for-byte. Fails if `_current_text`
uses `read_text()`.

**Aggregation** — a batch containing **two** unsupported records plus one valid edit: both
refusals are named and **nothing is written**. One refusal does not prove aggregation; it is
equally consistent with abort-on-first. A second case mixes *kinds* of candidate-local failure
— one degradation plus one slug-naming failure — so the report is proven to span the whole
candidate-local set of §4.1 rather than degradation alone.

**Batch-global abort** — a malformed packaged template aborts planning, reports one error
naming its stage, and writes nothing. This is the §4.1 boundary's other half; without it,
"may abort immediately" is untested and an implementer could aggregate everything.

**Write-stage wrapping** — a `claim_number_in_dir` drift failure raised *after* an earlier
file has been written carries `files_written` and `written_paths`. An `OSError`-only wrapper
passes the plain `atomic_write_text` test and fails this one, which is the point.

**Composition** — two edits to one path: the composed post-image carries both, and the first
is not lost.

**Numeric mints** — a refused batch consumes no number and leaves no placeholder; a number
claimed between plan and apply refuses rather than renumbering.

**Write stage** — the error carries `files_written` and `written_paths`.

Every guard is certified by mutation: break what it guards and watch a named test fail.

---

## 6. Scope-out

Recorded so a later reader does not mistake these for oversights.

- **No repair of the 183 pre-existing invalid records.** That is the "extend the migration to
  13 more kinds" slice, and it is independent.
- **No typed-shape certification** on these paths — base shape only (§2).
- **No transactional rollback** (§4.1).
- **No arming** of `proposition` or `evidence-line`; neither mixin exists yet.
- **`render_update`'s stale-owned-key hole** stays open. Clearing an owned key leaves the
  stale value (`dag/entity_frontmatter.py:298-300`), and the one-line fix also deletes the
  `legacy_*` triple, so it needs its own pass.
- **`entities.py:317-318`'s stale docstring** — it still names the armed set as "hypothesis,
  concept, method and search"; it has been six kinds since the `finding` slice. Out of scope
  here, worth a one-line fix wherever it is next touched.

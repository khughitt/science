# Annotation writer containment — design

**Status:** design, ready for the implementation plan (revision 2 — §2.3 measurement corrected)
**Branch:** `annotation-writer-containment`, forked from `main` at `0c7a6ba6`
**Program:** schema-first closure, piece 3 (first slice)

## 1. What this is

[`annotation/promote.py:283`](../../science/src/science_tool/annotation/promote.py) and
[`annotation/synthesize.py:430`](../../science/src/science_tool/annotation/synthesize.py)
mint and update propositions through `entities.write_entity_file`, the uncontained
full-model dump that
[`dag/entity_frontmatter.py`](../../science/src/science_tool/dag/entity_frontmatter.py)
was built to replace. That module's own docstring names them as its deferred work:

> It does NOT govern every path that mints a proposition: `annotation/promote.py` and
> `annotation/synthesize.py` still write propositions through `entities.write_entity_file`
> [...] migrating those is out of scope here.

This design closes that. It routes both writers through the contained renderers and
adds a guard that keeps them there. **It repairs no existing records.**

## 2. What piece 3 was filed as, and what measurement found

Piece 3 was filed as a single job: "backfill the 769 malformed proposition /
evidence-line records", with the two annotation writers noted alongside. Measuring
first — the rule this program adopted after F7 — separated it into three jobs with
different physics, and corrected the filing three times.

### 2.1 The population is 697, not 769

Measured 2026-07-31 by walking every `entities/**/*.md` frontmatter across the live
projects and counting absent-or-blank `title`:

| project | evidence-line | proposition |
|---|---|---|
| `~/d/r/mm30` | 374 / 396 | 307 / 334 |
| `~/d/protein-landscape` | 10 / 10 | 6 / 6 |
| `~/d/natural-systems` | 0 / 9 | 0 / 5 |
| **total** | **384** | **313** |

697 in total, against the filing's 769 (432 evidence-line + 337 proposition).
`natural-systems` is entirely clean, which is evidence the newer paths already write
well-formed records.

### 2.2 It is two populations, not one

They do not share a repair:

- **propositions** carry `subject` / `predicate` / `object`, so a title is *derivable*
  (`concept:a affects concept:b` — already the convention in the piece-1 fixtures).
- **evidence-lines** carry `stance` / `target` / `source`. The well-formed ones have
  authored sentences ("MM30 progression meta-analysis makes MGUS->SMM the weakest
  transition (21 genes vs 665 at H->MGUS)"), which no triple derives.

### 2.3 The legacy triple is not the inert cleanup the filing implied

Piece 1's plan recorded `legacy_relation_label` / `legacy_patch` / `legacy_edge_id` as
keys whose "deleting them is piece 3's corpus migration". Measured:

- In mm30, empty-title ⟺ legacy-triple **exactly** for propositions: 307 and 307, with
  zero records on either side alone. The triple is a perfect marker of the old generation.
- Its validator, `dag/validate.py:_check_legacy_dag_metadata`, is **live, and currently
  failing on every one of the 307 records**. An earlier revision of this design claimed the
  opposite ("mm30 contains zero `.dot` files, so `per_dag_edges` is empty and the check
  `continue`s on every record"). Re-measured 2026-07-31, that is wrong in every clause: mm30
  holds **105 `.dot` files** under `doc/figures/dags` (16 after `_discover_dot_files` excludes
  `-auto` / `-numbered`), and **all 15 distinct `legacy_patch` values match a `.dot` stem**, so
  every record passes the `continue` at `validate.py:275` and reaches the subject/object
  cross-check. Running `validate_project` on mm30:

  ```
  findings by rule: {'proposition_edge_missing': 362, 'acyclicity': 1,
                     'legacy_dag_edge_unresolved': 307}
  ```

  307 findings, severity `error`. Deleting `legacy_patch` would retire a check that runs — and
  fails — on the whole population. The check is not silent; it is unread.
- `graph/materialize.py:2082-2087` still emits `sci:legacyPatch` and `sci:legacyEdgeId`
  into the graph. That output *is* live.
- `legacy_relation_label` holds **243 distinct values across 307 records** — the only
  human-authored semantics on those skeletons, ranging from terse (`dosage`, `epigenetic`)
  to substantive ("gain(1q) carries a dosage-linked mitochondrial-redox expression block").
  It is also **still consumed**: `dag/proposition_edges.py:69` maps it to `original_label`,
  which `dag/render.py:242` uses to build rendered edge labels. Deleting it would both
  destroy information and change rendered DAG output.
- `legacy_patch`, by contrast, carries little *information*: 15 distinct values, near-redundant
  with `discusses` (9 of 15 map to exactly one `discusses` set; the remaining 6 map to two).
  But it is the field with the **most** machinery attached — it keys both the graph emitter and
  the live `.dot` cross-check. Low information content is not low coupling, and the migration
  should not mistake the first for the second.

**All three fields are load-bearing, and none of the consumers is inert.** Two materialize
into the provenance graph, the third renders as an edge label, and the `.dot` cross-check runs
on every legacy record. Each field needs its own verdict.

The correction matters beyond bookkeeping: the retired-reading said the triple could be
deleted cheaply because nothing consumed it. The measured reading is that deleting
`legacy_patch` would silence 307 live errors rather than resolve them, which is the opposite
kind of migration. **Start the migration design from this measurement, not from the retired
one.**

**Ruling: out of scope here.** The triple's fate belongs to the migration design, which
should start from these measurements rather than from "just delete them".

### 2.4 The writers' defect is destruction, not emission

The filing said the two writers "set a non-empty `title`, so they add nothing to the 769."
Accurate, and — as with F7 — one step short of the defect. What they do is *destroy*.

Reproduced 2026-07-31: write a proposition enriched by `synthesize`, then re-mint the same
claim through `promote`'s path (its never-overwrite guard permits this, because the claims
match):

```
predicate         'affects'            -> None
polarity          'positive'           -> None
claim_layer       'causal_effect'      -> None
reasoning_source  'synthesize:model-x' -> None
body              'curated body'       -> '# stub'
```

`write_entity_file` renders the whole model with `exclude_none`, so every field the minting
`PropositionEntity` leaves unset is *absent from the new file* — silently deleting the
synthesis result and the curated body.

This is a live data-loss path. Containment alone does **not** close it: rendering the same
write as a contained update would still replace `source_refs`, `subject` and `object`, because
the minting writer owns them. Closing it requires the §4.3 ruling — an existing identical
claim is provenance accrual, not a rewrite.

**This, not the empty titles, is why the slice is worth doing on its own.**

## 3. Scope

**In:** route both annotation writers through the contained renderers; generalize ownership
from per-kind to per-writer; guard the uncontained writer against re-acquiring callers.

**Out:** repairing any of the 697 records; the legacy triple; title derivation policy;
`render_update`'s stale-owned-key hole (F4); retiring `materialize.py`'s legacy emitters.

## 4. Design

### 4.1 Ownership becomes per-writer

`entity_frontmatter` currently resolves ownership from the entity's kind:

```python
def owned_keys(kind: str) -> frozenset[str]: ...
```

That is the wrong axis. Ownership is a property of *the writer*, not of the kind — and the
three writers of `proposition` own genuinely different sets:

| writer | operation | owns beyond the shared core |
|---|---|---|
| `dag.workbench` | upsert | `legacy_*`, `discusses`, `predicate`, `polarity` |
| `annotation.promote` | **create only** (§4.3) | **`source_refs`**, at create |
| `annotation.synthesize` | update only | **`reasoning_source`** |

`source_refs` and `reasoning_source` appear in neither existing allowlist.

Introduce an explicit value object:

```python
@dataclass(frozen=True)
class Ownership:
    """Which frontmatter keys ONE writer owns.

    Per-writer, not per-kind: three writers mint propositions and each owns a different
    set. Widening a shared per-kind allowlist to their union would give the workbench
    ownership of `source_refs` -- so every `compile_workbench` recompile would overwrite
    an author's curated value on a path this design does not otherwise touch.
    """
    owned: frozenset[str]
    create_only: frozenset[str] = frozenset()
```

with four declarations. The two workbench sets are carried over **verbatim**, which makes its
*ownership semantics* — which keys a workbench write may overwrite — unchanged by
construction. That is narrower than "the workbench is unchanged", and the difference matters:
the moved path, body, date and atomic-write logic of §4.2 is shared code that this design
relocates, and `workbench_apply`'s no-op detection depends on `render_update`'s output rather
than on ownership alone. Those are covered by test, not by construction (§5.2).

```python
WORKBENCH_PROPOSITION   = Ownership(PROPOSITION_OWNED_KEYS,   CREATE_ONLY_KEYS)
WORKBENCH_EVIDENCE_LINE = Ownership(EVIDENCE_LINE_OWNED_KEYS, CREATE_ONLY_KEYS)
PROMOTE_PROPOSITION     = Ownership(
    frozenset(("id", "kind", "subject", "object", "source_refs")), CREATE_ONLY_KEYS
)   # reaches `render_create` ONLY -- promote never updates a record (§4.3)
SYNTHESIZE_PROPOSITION  = Ownership(
    frozenset(("subject", "object", "predicate", "polarity", "claim_layer",
               "reasoning_source"))
)
```

`SYNTHESIZE_PROPOSITION` is exactly `synthesize.SYNTH_FIELDS` plus `reasoning_source`, and
must be **derived from that tuple in code**, not retyped — a hand-copied duplicate of a
five-element tuple silently diverges the first time a field is added.

The two new sets omit `created` / `updated`, which the carried-over workbench sets contain.
That asymmetry is deliberate and harmless: both renderers stamp the two keys unconditionally
after the allowlist filter (`entity_frontmatter.py:129-130` and `:188-189`), so membership
changes nothing. The workbench sets keep them only because §4.1 carries those frozensets over
verbatim. Do not "fix" the new sets by adding them — and do not read their absence as a bug.

`render_create` and `render_update` take `ownership: Ownership` explicitly and stop calling
`owned_keys`. A `workbench_ownership(kind)` helper retains today's fail-early raise on an
unsupported kind for the workbench's two-kind dispatch.

### 4.2 Three operation-named entry points, replacing a copy

`workbench._write_entity_file` already performs the full dance:

```
dest = project_root / resolve_path_policy(kind, project_root=project_root).root / f"{local_part}.md"
if dest.exists():
    fm, body, _ = read_existing_target(dest, entity)   # ADMIT FIRST
    text = render_update(entity, existing_frontmatter=fm, body=body,
                         created=str(fm["created"]), updated=today)
else:
    text = render_create(entity, body=create_body, created=today, updated=today)
dest.parent.mkdir(parents=True, exist_ok=True)
_atomic_replace_text(dest, text)
```

Move it into `entity_frontmatter` as **three** entry points over shared internals, one per
operation actually performed:

```python
def upsert_entity_file(entity, *, project_root, ownership, create_body, as_of=None) -> Path
def create_entity_file(entity, *, project_root, ownership, create_body, as_of=None) -> Path
def update_entity_file(entity, *, project_root, ownership, as_of=None) -> Path
```

`upsert_entity_file` is today's behaviour, used only by the workbench, which legitimately
recompiles over existing rows. `create_entity_file` refuses an **existing** destination;
`update_entity_file` refuses a **missing** one and takes no `create_body`, because an
update-only writer has none to supply.

The three entry points are not decoration — each writer performs exactly one operation, and
naming it is what keeps the other branches from existing. Handing `synthesize` an upsert
would force a `create_body` argument that can never be used, and a value invented to satisfy
a signature is the silent fallback that would one day mint a proposition from a stub body.
Handing `promote` an upsert is worse, and is the defect §4.3 fixes.

This **removes a copy rather than adding an abstraction**: leaving the dance in
`workbench._write_entity_file` would put the admit-then-render ordering — the subtle part,
where reading the file directly instead of via `read_existing_target` lets `render_update`
repair a record into validity before `certify_persisted` ever sees it — in three places.

### 4.3 The two call sites

**`promote._mint_proposition` becomes create-only, and an existing identical claim accrues
provenance instead of being rewritten.**

A same-slug MINT onto an existing record is reachable only through a curator override — auto
mints are pre-screened, since a claim matching an existing title classifies as `LINK` and a
colliding slug classifies as `COLLISION`. The never-overwrite guard already rejects the case
where the claims *differ*. So the only destination that survives the guard is a record
asserting **the same claim**, and for that case promotion has an established, correct
behaviour: the `LINK` path at `promote.py:384-391` accrues provenance with
`append_entity_source_ref`, whose contract is explicit that it exists

> so a hand-authored proposition's prose is never clobbered.

Rendering that record as an update would replace `source_refs` with only the current paper's
refs — discarding accumulated provenance — and overwrite `subject` / `object` with the
promotion's values, discarding refinements `synthesize` owns and may have made. **An
identical claim arriving from a second source is provenance accrual, not a rewrite**, and the
two paths that reach it must not disagree about that.

So:

- destination absent → `create_entity_file(..., ownership=PROMOTE_PROPOSITION,
  create_body=_proposition_body(c.claim))`.
- destination present and the guard passes → `append_entity_source_ref` for each ref, exactly
  as `LINK` does. Nothing else on the record is touched.

`PROMOTE_PROPOSITION` therefore never reaches `render_update`, which is why §4.1 marks it
create-only.

**The report must follow the behaviour, and that changes `MintFn`.** `apply_candidates:380-383`
currently does `report.minted += 1` and `written_paths.append(...)` unconditionally on the MINT
branch, because `MintFn` returns a bare `str`:

```python
MintFn = Callable[["PromotionCandidate", list[str], Path, "date | None"], str]   # promote.py:247
```

A mint that accrued would then report as a mint, and name a path nothing wrote. The ruling:

- **an accrual counts as `linked`**, not minted — one behaviour, one counter, matching §4.3's
  "an identical claim arriving from a second source is provenance accrual, not a rewrite";
- **no `accrued` counter** — a third bucket would re-introduce the distinction the ruling
  collapses;
- **`written_paths` gains an entry only when a file is created.**

So `MintFn` returns the entity id *and* whether it created, and `apply_candidates` branches on
that instead of assuming. **All three mint implementations carry the contract** —
`_mint_proposition` returns created-or-accrued, and both `_mint_numeric` closures
(`question`, `hypothesis`) always report created, since `reserve_entity` + the template render
have no accrual path. Threading it through only the proposition mint would leave the other two
returning a value the caller must special-case, which is how the unconditional `+= 1` got there
in the first place.

**`synthesize._write_proposition`** calls
`update_entity_file(..., ownership=SYNTHESIZE_PROPOSITION)`. Its destination always exists —
it updates in-scope propositions — so it takes the update-only entry point, and
`read_existing_target` raising `MalformedTargetError` on a wrong-identity or undated record is
the fail-early admission check the path has never had.

The `PropositionEntity(**merged_fm)` reconstruction **stays** — `render_update` renders owned
keys from a typed entity, so one must be built. What `read_existing_target` replaces is the
`_parse_markdown_file` body read and the absent identity check, not the construction. Two
readers of the same file disagreeing about what its frontmatter is, is the defect
`read_existing_target` exists to prevent.

That the reconstruction survives is what makes test 6 land where it does. `PropositionEntity.title`
is `str = ""` (`model/src/science_model/propositions.py:48`), so an empty-title pre-containment
record **constructs without complaint** and is refused later, by `certify_persisted`, with
`PersistedShapeError`. Test 6 must assert that error and not a pydantic `ValidationError`; if
the model ever makes `title` required, the failure moves earlier and that test's premise moves
with it.

### 4.4 Delete the writer; guard the symbol, not its callers

After this slice `entities.write_entity_file` has **zero** production callers (measured: the
only two are the ones being contained; its docstring at `entities.py:486` claiming it is "also
used by `dag.workbench`" is already stale). **It is deleted, not retained.**

An earlier revision kept it as a general any-kind writer, reasoning that the contained
renderers cover only `proposition` and `evidence-line` so deleting it would leave no general
facility. Measurement refutes the premise: the other two promotable kinds never used it.
`_mint_numeric` (`promote.py:307-345`) renders `question` and `hypothesis` through
`Renderer().render()` + `_atomic_replace_text`, on a template-faithful path that predates this
design and is untouched by it. No production path wants a general full-model dump — that dump
*is* the defect, and `exclude_none=True` at `entities.py:466` is what §2.4 reproduced.

Keeping a callerless function alive plus a guard asserting nobody calls it is also two
mechanisms where one will do, and it is the "legacy layer nobody asked for" the repo
conventions rule out.

So the guard becomes a **symbol-absence assertion**: `write_entity_file` is not defined in
`science_tool.entities` and does not appear anywhere under `science/src/science_tool/`. That is
strictly stronger than the caller guard it replaces — a caller cannot re-acquire a symbol that
does not exist — and it cannot be satisfied by a re-definition under another name reached
through the same dump.

The scope is **derived from a tree walk, never an enumerated module list**. A guard that lists
its own scope has a hole by construction, and this program has already been bitten by one.

Deleting it moves the three *test* callers (§5.9), which are the only remaining references.

## 5. Testing

1. **Ownership declarations** — `SYNTHESIZE_PROPOSITION.owned` equals
   `set(SYNTH_FIELDS) | {"reasoning_source"}`, asserted against the imported tuple, so adding
   a synth field fails loudly rather than silently escaping containment.
2. **The workbench is unchanged** — its two ownership constants equal today's frozensets, and
   its existing conformance and apply suites pass untouched. Ownership equality is by
   construction; everything else on that path is not, so the implementation plan must carry
   **all five renderer call sites** through the signature change explicitly:
   `workbench._write_entity_file:372` (`render_update`) and `:380` (`render_create`);
   `workbench_apply:178` (`render_create`), `:196` (the **unchanged-timestamp no-op probe**,
   whose result depends on `render_update`'s output) and `:206` (the final `render_update`).
   The no-op probe is the one most likely to change behaviour silently and needs a test
   asserting a no-op edit still writes nothing.
3. **The §2.4 regression test** — enrich a proposition, then force a same-slug MINT of the
   identical claim, and assert that `predicate`, `polarity`, `claim_layer`,
   `reasoning_source`, the curated body, **the pre-existing `source_refs` (accrued, not
   replaced), and the `subject` / `object` refinements** all survive. It fails on `main`.
   The `source_refs` / `subject` / `object` assertions are the ones a naive contained-update
   implementation would still fail — they are the point of §4.3, not incidental coverage.
4. **No skeleton keys** — a minted proposition's frontmatter contains no `datapackage`,
   `local_path`, `accessions`, `siblings`, `parent_dataset`, or `license`.
5. **Guard falsifiability** — mutation-test by re-introducing a `write_entity_file` definition
   in `entities.py` and confirming the symbol-absence test goes red, then again with a call
   site added. A guard that has never failed is an assertion, not a check.
6. **`certify_persisted` on the annotation path** — a synthesize update targeting a
   pre-containment empty-title record raises `PersistedShapeError` naming the record and
   `title`, rather than rewriting it.
7. **The operation contracts hold** — `update_entity_file` refuses a missing destination and
   accepts no `create_body`; `create_entity_file` refuses an existing one. Asserted rather
   than assumed, since these refusals are what keep the unreachable branches unreachable.
8. **Promotion accrual matches LINK** — a same-slug MINT of an identical claim and a `LINK`
   to the same record leave the file in the same state **and the same `ApplyReport`**:
   `linked` incremented, `minted` not, and no `written_paths` entry (§4.3). One behaviour, two
   routes to it — asserting only the file state would let the report diverge unnoticed, which
   is the hole the unconditional `report.minted += 1` opened.
9. **The fixtures move off the deleted writer** — `tests/test_proposition_synthesize.py`'s
   `_write_prop` helper (`:283-286`) currently builds its records *with* `write_entity_file`,
   as do `test_entity_writer.py` and `test_workbench_apply.py`. §4.4 deletes it, so they must
   be rewritten onto the contained path. This is not mechanical: the full-model dump seeds
   skeleton keys that `render_update` preserves (they are not owned) and `certify_persisted`
   does not reject (base 2.0 deliberately omits `unevaluatedProperties`, per its docstring).
   Left alone, the synthesize suite would certify containment against inputs only the
   uncontained writer could produce — and test 4's "no skeleton keys" would pass over records
   whose skeleton keys came from the fixture, not the writer under test.

Validation per `AGENTS.md`: `cd science && uv run --frozen pytest`, `cd science/model &&
uv run --frozen pytest`, `uv run ruff check` in both packages, `uv run pyright` from
`science/`. `-m real_projects` has three known pre-existing failures on `main`; reproduce
any failure at the merge-base before attributing it to this branch.

## 6. Accepted costs

- **A curator `override` forcing a write onto a pre-containment record now fails**, per the
  workbench-writer-containment design's §5.4 ruling (reject an update to a pre-containment
  record; never silently backfill it). Measured blast radius: **zero records absent
  an explicit override** — all 307 legacy propositions already have all five `SYNTH_FIELDS`
  set, so `plan_writes` produces no writes and `synthesize` skips them today.
- **Nothing in the 697-record corpus is repaired.** They remain unwritable by the contained
  paths, which is what makes the migration necessary rather than optional.

## 7. Follow-ups this design surfaced

- **The corpus migration** (the rest of piece 3): 697 records, two populations with different
  repair physics (§2.2), and the legacy triple's fate (§2.3). Needs its own design.
- **The legacy triple has three separate consumers and needs three verdicts**, not one:
  `sci:legacyPatch` / `sci:legacyEdgeId` still materialize into the provenance graph
  (`materialize.py:2082-2087`), `legacy_relation_label` still renders as an edge label
  (`proposition_edges.py:69` → `render.py:242`), and `legacy_patch` additionally keys the
  `.dot` cross-check, which runs on all 307 records (§2.3). Every one of them is live.
  Retiring any changes an output, and belongs with the migration.
- **mm30's DAG validation is red and nobody is reading it.** `validate_project` returns 670
  findings — 362 `proposition_edge_missing`, 307 `legacy_dag_edge_unresolved`, 1 `acyclicity`
  — all severity `error`, so `report.ok` is `False` today. That is a project-health finding
  this design surfaced in passing and does not own; it needs triage on its own terms, and the
  307 must be resolved rather than deleted out from under the check.
- **`compile_workbench`'s docstring** still says entities are "(re)written via the canonical
  entity-layer writer", which stopped being true when piece 1 landed. One-line fix.

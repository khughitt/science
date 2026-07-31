# Annotation writer containment — design

**Status:** design, awaiting implementation plan
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
- Its validator, `dag/validate.py:_check_legacy_dag_metadata`, is **already inert**: mm30
  contains **zero `.dot` files**, so `per_dag_edges` is empty and the check `continue`s on
  every record. Deleting the field would retire nothing that currently runs — but it also
  means the check's silence today is not evidence of health.
- `graph/materialize.py:2082-2087` still emits `sci:legacyPatch` and `sci:legacyEdgeId`
  into the graph. That output *is* live.
- `legacy_relation_label` holds **243 distinct values across 307 records** — the only
  human-authored semantics on those skeletons, ranging from terse (`dosage`, `epigenetic`)
  to substantive ("gain(1q) carries a dosage-linked mitochondrial-redox expression block").
  Deleting it destroys information. `legacy_patch`, by contrast, has 15 distinct values and
  is near-redundant with `discusses` (9 of 15 map to exactly one `discusses` set; the
  remaining 6 map to two).

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
synthesis result and the curated body. This is a live data-loss path, and containing the
writers closes it as a direct consequence: `render_update` preserves unowned keys and the
existing body.

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
| `annotation.promote` | create (upsert on identical claim) | **`source_refs`** |
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

with four declarations. The two workbench sets are carried over **verbatim**, so the
workbench's behaviour is unchanged by construction:

```python
WORKBENCH_PROPOSITION   = Ownership(PROPOSITION_OWNED_KEYS,   CREATE_ONLY_KEYS)
WORKBENCH_EVIDENCE_LINE = Ownership(EVIDENCE_LINE_OWNED_KEYS, CREATE_ONLY_KEYS)
PROMOTE_PROPOSITION     = Ownership(
    frozenset(("id", "kind", "subject", "object", "source_refs")), CREATE_ONLY_KEYS
)
SYNTHESIZE_PROPOSITION  = Ownership(
    frozenset(("subject", "object", "predicate", "polarity", "claim_layer",
               "reasoning_source"))
)
```

`SYNTHESIZE_PROPOSITION` is exactly `synthesize.SYNTH_FIELDS` plus `reasoning_source`, and
must be **derived from that tuple in code**, not retyped — a hand-copied duplicate of a
five-element tuple silently diverges the first time a field is added.

`render_create` and `render_update` take `ownership: Ownership` explicitly and stop calling
`owned_keys`. A `workbench_ownership(kind)` helper retains today's fail-early raise on an
unsupported kind for the workbench's two-kind dispatch.

### 4.2 One upsert helper, replacing a copy

`workbench._write_entity_file` already performs the full dance:

```
dest = project_root / resolve_path_policy(kind).root / f"{local_part}.md"
if dest.exists():
    fm, body, _ = read_existing_target(dest, entity)   # ADMIT FIRST
    text = render_update(entity, existing_frontmatter=fm, body=body,
                         created=str(fm["created"]), updated=today)
else:
    text = render_create(entity, body=create_body, created=today, updated=today)
dest.parent.mkdir(parents=True, exist_ok=True)
_atomic_replace_text(dest, text)
```

Move it into `entity_frontmatter` as **two** entry points over shared internals:

```python
def upsert_entity_file(entity, *, project_root, ownership, create_body, as_of=None) -> Path
def update_entity_file(entity, *, project_root, ownership, as_of=None) -> Path
```

`upsert_entity_file` is today's behaviour, for writers that legitimately create — the
workbench and `promote`. `update_entity_file` refuses a missing destination with
`MalformedTargetError` and takes **no `create_body`**, because an update-only writer has no
create body to supply.

The two entry points are not decoration. `synthesize` only ever updates existing
propositions, so giving it `upsert_entity_file` would force a `create_body` argument that
can never be used — and a value invented to satisfy a signature is exactly the silent
fallback that would one day mint a proposition from a stub body. Making the operation
explicit in the function name lets the unreachable branch not exist rather than be guarded.

This **removes a copy rather than adding an abstraction**: leaving the dance in
`workbench._write_entity_file` would put the admit-then-render ordering — the subtle part,
where reading the file directly instead of via `read_existing_target` lets `render_update`
repair a record into validity before `certify_persisted` ever sees it — in three places.

### 4.3 The two call sites

**`promote._mint_proposition`** keeps its never-overwrite guard unchanged and calls
`upsert_entity_file(..., ownership=PROMOTE_PROPOSITION, create_body=_proposition_body(c.claim))`.
Because `title` is create-only and unowned keys survive an update, a re-mint of an identical
claim now preserves the author's title, body, and everything `synthesize` contributed —
closing §2.4.

**`synthesize._write_proposition`** calls
`update_entity_file(..., ownership=SYNTHESIZE_PROPOSITION)`. Its destination always exists —
it updates in-scope propositions — so it takes the update-only entry point, and
`read_existing_target` raising `MalformedTargetError` on a missing or wrong-identity record
is the fail-early replacement for today's silent `PropositionEntity(**merged_fm)`
reconstruction.

The `_parse_markdown_file` body read in `_write_proposition` is dropped: `read_existing_target`
returns the body, and having two readers of the same file disagree about what its frontmatter
is, is the defect `read_existing_target` exists to prevent.

### 4.4 The guard

After this slice `entities.write_entity_file` has **zero** production callers (measured: the
only two are the ones being contained; its docstring's claim that it is "also used by
`dag.workbench`" is already stale). It is retained as a general any-kind writer — the
contained renderers support only `proposition` and `evidence-line`, so deleting it would
leave no general facility — but nothing must silently re-acquire it.

Add an AST test that walks **every** `.py` file under `science/src/science_tool/` and asserts
no reference to `write_entity_file` outside its own definition in `entities.py`, catching both
`from ... import write_entity_file` and `entities.write_entity_file(...)` attribute access.

The scope is **derived from a tree walk, never an enumerated module list**. A guard that lists
its own scope has a hole by construction, and this program has already been bitten by one.

## 5. Testing

1. **Ownership declarations** — `SYNTHESIZE_PROPOSITION.owned` equals
   `set(SYNTH_FIELDS) | {"reasoning_source"}`, asserted against the imported tuple, so adding
   a synth field fails loudly rather than silently escaping containment.
2. **The workbench is unchanged** — its two ownership constants are identical to today's
   frozensets, and its existing conformance and apply suites pass untouched. This is the
   slice's central safety claim and must be asserted, not assumed.
3. **The §2.4 regression test** — the reproduction above, as a test: enrich, re-mint, assert
   `predicate` / `polarity` / `claim_layer` / `reasoning_source` and the body all survive.
   It fails on `main`.
4. **No skeleton keys** — a minted proposition's frontmatter contains no `datapackage`,
   `local_path`, `accessions`, `siblings`, `parent_dataset`, or `license`.
5. **Guard falsifiability** — mutation-test by reverting one call site to
   `write_entity_file` and confirming the AST test goes red. A guard that has never failed
   is an assertion, not a check.
6. **`certify_persisted` on the annotation path** — a synthesize update targeting a
   pre-containment empty-title record raises `PersistedShapeError` naming the record and
   `title`, rather than rewriting it.
7. **`update_entity_file` refuses a missing destination** with `MalformedTargetError`, and
   accepts no `create_body` — the update-only contract, asserted rather than assumed.

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
- **`materialize.py`'s legacy emitters** (`sci:legacyPatch`, `sci:legacyEdgeId`) outlive the
  validator that justified them. Retiring them is a graph-output change and belongs with the
  migration.
- **`_check_legacy_dag_metadata` is inert wherever the `.dot` corpus is gone.** A check that
  cannot fire is worth either restoring or retiring, and its silence should not be read as
  health.
- **`compile_workbench`'s docstring** still says entities are "(re)written via the canonical
  entity-layer writer", which stopped being true when piece 1 landed. One-line fix.

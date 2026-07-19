# refs body-entity-ref prefix resolution — design

**Status:** approved (rev 2)
**Date:** 2026-07-19
**Scope:** `science` — `refs.py`, `numeric_provenance.py`, tests, docs

**rev 2 changes** (design review): helper params typed as read-only
`AbstractSet[str]` (not `Set`/`Iterable`) so a `frozenset` caller type-checks
and duplicate inputs cannot over-count owners; `refs` import arrangement for
`ResolutionIndex.resolve()` made explicit (function-local, mirroring
`build_resolution_index`) to avoid `NameError`; entity-CLI "parity" claim
corrected (the CLI is exact-only for colon-qualified refs — t108
numeric-provenance is the true identical prior art); ambiguous short prefixes
now get a distinct diagnostic and the not-found message is made
truth-source-neutral.

## Problem

`science refs check --include-body` validates typed entity-ref citations that
appear in body prose (`_scan_body_typed_refs`, `refs.py`). The check is an
**exact** set-membership test:

```python
if ref in entity_index:   # entity_index = canonical `<kind>:<id>` strings
    continue
# else: flag as body-entity-ref "typed entity ref not found ..."
```

Canonical entity ids carry a descriptive suffix — e.g. the plan whose
`id:` is `plan:0019-t071-q14-panel-replication`. A document that cites it by
the natural short form `plan:0019` therefore fails the exact test and is
reported as a **broken ref**, even though it unambiguously identifies a real
entity.

This surfaced concretely when `plan` was added to `_LOCAL_ENTITY_KINDS`
(t108): pan-disease's short `plan:0019` / `plan:0023` / `plan:0024` citations
began flagging under `--include-body`. The same latent asymmetry already
affected every other kind (`interpretation:0011`, `pre-registration:0012`, …);
adding `plan` merely made it visible. `refs check --include-body` is the only
surface affected — `science validate` calls `check_refs()` **without**
`include_body`, so nothing here reaches validation.

## Prior art

**t108 numeric-anchor** (`numeric_provenance.py`) is the exact same
resolution rule this change adopts: it resolves a cited entity-ref as *exact
canonical id **or** unique digit-lead prefix* via an
`entity_prefix_owners: dict[str,int]` owner-count map. Non-numeric leads
never enter the map; ambiguous multi-owner prefixes have `owners > 1`, so
neither resolves — fail-closed, a citation can never silently anchor to a
guessed entity. This change extracts that rule into `refs` and reuses it, so
the two checks share one implementation.

**Entity CLI resolver — related but NOT identical** (do not overstate the
parity). `resolve_entity_ref()` (`entities.py`) treats any **colon-qualified**
reference as exact-only — `plan:0019` does *not* prefix-resolve there. Its
shorthand resolution applies only to **unqualified** forms (`0019`) and
registered shortforms (`p19`, `t1`, …). It is still useful precedent in one
respect: for an ambiguous unqualified match it raises a distinct
`"Ambiguous entity reference {ref}: …"` error rather than a bare "not found" —
the model this design follows for its own ambiguity diagnostic (below).

## Approach

**DRY shared helper in `refs`, digit-lead-only semantics** — identical to the
t108 resolution rule, with the shared logic extracted into `refs` as the
single source of truth (both decisions confirmed with the maintainer).

### 1. Two new pure helpers in `refs.py`

Both take a read-only `AbstractSet[str]` (`from collections.abc import Set as
AbstractSet`) so a `frozenset` — the concrete type of
`ResolutionIndex.entity_ids` — type-checks, and so the builder cannot count a
duplicate input value as two owners.

```python
def build_entity_prefix_owners(entity_ids: AbstractSet[str]) -> dict[str, int]:
    """Count owners of each `<kind>:<digit-lead>` short prefix.

    For a canonical id `<kind>:<ident>`, the lead is the segment before the
    first `-`. A lead that is all-digits and is not the whole ident (so a
    bare-numeric id does not count itself) registers one owner under
    `<kind>:<lead>`. A short ref resolves only when its owner count is exactly
    one, so this map is the fail-closed ambiguity guard.
    """
    owners: dict[str, int] = {}
    for eid in entity_ids:
        kind, _, ident = eid.partition(":")
        lead = ident.split("-", 1)[0]
        if lead.isdigit() and lead != ident:
            key = f"{kind}:{lead}"
            owners[key] = owners.get(key, 0) + 1
    return owners


def resolve_local_entity_ref(
    ref: str, entity_ids: AbstractSet[str], prefix_owners: dict[str, int]
) -> bool:
    """True if `ref` is an exact canonical id or a unique digit-lead prefix."""
    return ref in entity_ids or prefix_owners.get(ref) == 1
```

These two functions are the **only** home for the "unique digit-lead prefix"
contract after this change.

### 2. Wire into the body scan (`refs.py`)

- `check_refs`: when `include_body`, build
  `prefix_owners = build_entity_prefix_owners(entity_index)` alongside the
  existing `entity_index`, and thread it into `_scan_body_typed_refs`.
- `_scan_body_typed_refs`: accept `prefix_owners`; for each matched `ref`:
  - if `resolve_local_entity_ref(ref, entity_index, prefix_owners)` → resolved,
    no issue.
  - else if `prefix_owners.get(ref, 0) > 1` → **ambiguous**, emit a distinct
    diagnostic: `f"{ref} — ambiguous short entity ref: matches {n} entities by
    prefix; cite the full id"` (where `n = prefix_owners[ref]`). The ref *does*
    exist — reporting it as "not found" would be wrong.
  - else → **not found**, emit the existing (neutralized) message.

The current not-found message hardcodes "not found in project frontmatter
`id:` index", but the index truth-source is configurable
(`EntityIndexSource.FRONTMATTER` vs `KNOWLEDGE_GRAPH`, `refs.py:_resolve_entity_index`).
Change the wording to be source-neutral —
`f"{ref} — typed entity ref not found in project entity id index"` — so it is
accurate under either source. Any test asserting the old wording is updated in
the same task.

No change to the regex, the cross-project `mm30:task:…` skip, or the
frontmatter/code-fence exclusions — only the resolution/diagnostic logic
changes.

### 3. Refactor `numeric_provenance.py` to reuse the shared helper

- `build_resolution_index`: replace the inline owner-count loop with
  `refs.build_entity_prefix_owners(entity_ids)` (this function already imports
  `refs` locally at its top — no new import needed).
- `ResolutionIndex.resolve` (the `_TYPED_REF_RE` branch): replace the inline
  `ref in self.entity_ids or self.entity_prefix_owners.get(ref) == 1` with
  `refs.resolve_local_entity_ref(ref, self.entity_ids, self.entity_prefix_owners)`.
  **`resolve()` has no `refs` in scope** — the module's only `refs` import is
  function-local inside `build_resolution_index`. Add a matching function-local
  `from science_tool import refs` at the top of `resolve()` (consistent with
  the existing pattern, and cycle-proof: `refs` imports nothing from
  `numeric_provenance`). After the module is first loaded the import is a cheap
  `sys.modules` lookup, negligible even though `resolve()` is called per-claim.

Behavior is identical; the existing t108 tests in `test_numeric_provenance.py`
are the regression guard for the refactor. `ResolutionIndex` keeps its
`entity_prefix_owners` field and its frozen shape unchanged.

## Semantics (identical to t108)

| Citation | Index contains | Resolves? |
|----------|----------------|-----------|
| `plan:0019` | `plan:0019-t071-…` (sole owner) | yes — unique digit-lead prefix |
| `plan:0019` | `plan:0019-a`, `plan:0019-b` | no — ambiguous (owners = 2) |
| `plan:0019-t071-q14-panel-replication` | same, exact | yes — exact id |
| `dataset:gtex` | `dataset:gtex-v8` | no — non-numeric lead, exact-only |
| `interpretation:9999` | (absent) | no — fabricated |

Fail-closed throughout: ambiguous, non-numeric, and absent refs all remain
flagged.

## Non-goals

- No general (non-digit-lead) prefix resolution — semantic slugs are not
  sequential and carry higher accidental-collision risk; excluded to stay
  consistent with t108.
- No change to `science validate` (it does not run `--include-body`).
- No change to frontmatter-ref validation — only body-prose typed refs.

## Testing

- `tests/test_refs.py`:
  - short digit-lead body ref resolves (previously flagged) — a real
    `plan:NNNN` short-form shape, asserting no issue;
  - ambiguous multi-owner short ref → still flagged, **with the ambiguity
    diagnostic** (`"ambiguous short entity ref"`, and the owner count in the
    message), not the not-found message;
  - non-numeric short prefix → still flagged (exact-only);
  - exact canonical id → resolves;
  - not-found ref → flagged with the neutralized, source-agnostic wording
    (assert the new string; no residual "frontmatter" test).
- `tests/test_numeric_provenance.py`: existing t108 tests stay green — no new
  behavior, refactor regression only.
- Grep the test suite for the old `"frontmatter \`id:\` index"` assertion and
  update every occurrence to the neutralized wording in the same task.

## Acceptance

1. `uv run --frozen pytest` green from `science/`.
2. Overlay-verify on pan-disease with `--with-editable`: `refs check
   --include-body` no longer reports the short `plan:NNNN` entries, with no
   new breakage introduced; `science validate` output unchanged.

## Docs

Update the documentation of `refs check --include-body` body-ref validation
to state that body refs resolve by exact canonical id **or** unique digit-lead
prefix, and that an ambiguous short prefix is reported with its own diagnostic.
Do **not** claim parity with the entity CLI resolver — the CLI is exact-only
for colon-qualified refs, so the behaviors differ for the `<kind>:<digits>`
form.

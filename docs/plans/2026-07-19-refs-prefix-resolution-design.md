# refs body-entity-ref prefix resolution — design

**Status:** approved (rev 1)
**Date:** 2026-07-19
**Scope:** `science` — `refs.py`, `numeric_provenance.py`, tests, docs

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

Two existing mechanisms already resolve short forms by uniqueness, so this
change aligns `refs` body-scanning with established project behavior rather
than introducing a new idea:

1. **t108 numeric-anchor** (`numeric_provenance.py`) resolves a cited
   entity-ref as *exact canonical id **or** unique digit-lead prefix* via an
   `entity_prefix_owners: dict[str,int]` owner-count map. Non-numeric leads
   never enter the map; ambiguous multi-owner prefixes have `owners > 1`, so
   neither resolves — fail-closed, a citation can never silently anchor to a
   guessed entity.
2. **The entity CLI resolver** (`show` / `edit` / `note` / `neighbors`,
   documented in `docs/user-guide/entities.md`) already accepts "unambiguous
   local shorthands … when they identify exactly one loaded source record."

## Approach

**DRY shared helper in `refs`, digit-lead-only semantics** — identical to the
t108 resolution rule, with the shared logic extracted into `refs` as the
single source of truth (both decisions confirmed with the maintainer).

### 1. Two new pure helpers in `refs.py`

```python
def build_entity_prefix_owners(entity_ids: Iterable[str]) -> dict[str, int]:
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
    ref: str, entity_ids: Set[str], prefix_owners: dict[str, int]
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
- `_scan_body_typed_refs`: accept `prefix_owners` and replace
  `if ref in entity_index:` with
  `if resolve_local_entity_ref(ref, entity_index, prefix_owners):`.

No change to the regex, the cross-project `mm30:task:…` skip, or the
frontmatter/code-fence exclusions — only the resolution predicate changes.

### 3. Refactor `numeric_provenance.py` to reuse the shared helper

- `build_resolution_index`: replace the inline owner-count loop with
  `refs.build_entity_prefix_owners(entity_ids)`.
- `ResolutionIndex.resolve` (the `_TYPED_REF_RE` branch): replace the inline
  `ref in self.entity_ids or self.entity_prefix_owners.get(ref) == 1` with
  `refs.resolve_local_entity_ref(ref, self.entity_ids, self.entity_prefix_owners)`.

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

- `tests/test_refs.py`: short digit-lead body ref resolves (previously
  flagged); ambiguous multi-owner still flagged; non-numeric short prefix
  still flagged (exact-only); exact canonical id resolves; a real
  `plan:NNNN` short-form shape.
- `tests/test_numeric_provenance.py`: existing t108 tests stay green — no new
  behavior, refactor regression only.

## Acceptance

1. `uv run --frozen pytest` green from `science/`.
2. Overlay-verify on pan-disease with `--with-editable`: `refs check
   --include-body` no longer reports the short `plan:NNNN` entries, with no
   new breakage introduced; `science validate` output unchanged.

## Docs

Update the documentation of `refs check --include-body` body-ref validation
to state that body refs resolve by exact canonical id **or** unique digit-lead
prefix, matching the CLI shorthand rule already documented in
`docs/user-guide/entities.md`.

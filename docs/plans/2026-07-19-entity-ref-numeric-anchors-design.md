# Entity-ref citations as numeric-anchor anchors — design

**Status:** approved (2026-07-19)
**Scope:** `numeric-anchor` prose lint (Part A engine). Single subsystem.
**Origin:** pan-disease t108. Surfaced while dogfooding numeric-provenance on
pan-disease: ~48 of the project's residual numeric-anchor findings are numbers
that *are* grounded — their paragraph cites a resolvable typed entity-ref
(`interpretation:0011-…`, `question:0016`) — but the detector cannot see that
citation as provenance.

## Problem

`numeric-anchor` classifies a prose numeric claim as grounded when its
paragraph carries a resolvable body reference (an existence-checked
paragraph-local candidate). The extraction regex `_BODY_REF_RE`
(`numeric_provenance.py`) recognizes only:

- `task:tNNN`
- `[@bibkey]`
- `cite:bibkey`
- `dataset:slug`
- `[[wiki]]` (topical — deliberately *not* a candidate)

The dominant citation convention in real projects is the **typed entity-ref**:
`` `interpretation:0011-h01-a2-bc2-tissue-confound` ``, `` `question:0016` ``,
`` `hypothesis:0001-molecular-truth-axis` ``, `` `plan:0023` ``, etc. These are
invisible to extraction, so a number whose only nearby provenance is such a
citation is flagged `Unanchored`.

The resolver already knows how to resolve these refs — `ResolutionIndex.resolve`
routes any `_TYPED_REF_RE` match (`^[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$`)
to membership in `entity_ids`. The gap is purely **extraction** plus
**short-prefix resolution** (citations appear as both full ids and bare
`interpretation:0013` prefixes).

### Measured impact (pan-disease, 2026-07-19)

- Residual numeric-anchor after the t107 config migration: **196**.
- Numbers with a resolvable-style entity-ref within ±3 lines: **~48**.
- Citation forms across the affected files: **545 full-id** (with slug),
  **58 short numeric-only prefixes** (`interpretation:0013`). Both forms must
  resolve.

## Non-goals

- No change to `additional_anchor_patterns` / `anchor_patterns`. That path is
  weak regex-only suppression (masking); this design deliberately routes
  through existence-checked resolution instead.
- No change to the shared refs-integrity check, the graph, or Part B
  (`numeric-verification`).
- No new dependency, no config surface, no schema change.

## Design

Three contained changes, all in `src/science_tool/numeric_provenance.py`.

### 1. Extraction — additive generic alternative in `_BODY_REF_RE`

Append **one** alternative after the existing five (additive: every current
extraction stays byte-identical because earlier alternatives win at a given
start position, and the new alternative only fires on `type:id` shapes none of
the existing ones match):

```
(?<![A-Za-z])[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*
```

The kind-token charset `[a-z][a-z0-9_-]*` matches the resolver's
`_TYPED_REF_RE` exactly, so extraction is never narrower than resolution.

Guards and why they hold:

- `(?<![A-Za-z])` — preserves the anti-substring guard
  (`recite:Foo2024` is its own token, not a `cite:` substring).
- Leading `[a-z]` (lowercase) — `MESH:D009101`, `Note: foo`, `Fig. 3:` never
  match; only lowercase-initial type tokens.
- Required `[A-Za-z0-9]` immediately after the colon — `https://…` (slash),
  `note: foo` (space), `12:30` (the whole token starts with a digit) never
  match.
- Kind token allows internal hyphens (`pre-registration`, `evidence-line`).

Anything the regex over-captures (e.g. a literal `note:foo` in prose) is
**existence-checked** and resolves to nothing, so it becomes an *unresolved*
candidate: it neither anchors a number nor emits any finding.

### 2. Short-prefix resolution — `ResolutionIndex`

Add a precomputed `entity_prefixes: frozenset[str]` to `ResolutionIndex`,
built in `build_resolution_index`: for each canonical `entity_id` of the shape
`<kind>:<digits>-<slug>`, add `<kind>:<digits>` (e.g.
`interpretation:0010-h01-a2-bc2-residualization-deskcheck` →
`interpretation:0010`). Entities without a numeric prefix (`dataset:gtex`)
contribute nothing here and resolve by exact id as today.

In `resolve()`'s typed-ref branch:

```python
if _TYPED_REF_RE.match(ref):
    return ref in self.entity_ids or ref in self.entity_prefixes
```

O(1). Deterministic: entity numbers are unique per kind, so a bare
`interpretation:0013` maps to exactly one entity. Full-id refs keep resolving
via exact `entity_ids` membership.

### 3. `local_candidates_for_paragraph` — no logic change

It already iterates `_BODY_REF_RE.finditer`, skips `[[wiki]]`, and stamps each
ref `resolved`/`unresolved` via `index.resolve`. It transparently consumes the
broadened regex and the prefix-aware resolver.

## Safety invariant ("don't mask")

Extraction never anchors on its own. A number is `Anchored(local)` only when a
paragraph-local candidate **resolves** against the real entity index. A
fabricated `interpretation:9999` extracts but does not resolve → the number
stays `Unanchored` (flagged). This is genuine, existence-checked provenance
recognition — the opposite of regex suppression.

## Testing

New unit tests in `tests/test_numeric_provenance.py`:

- Full-id typed ref (`interpretation:0007-h01-…`) extracts and, when the entity
  exists, resolves → paragraph-local candidate `resolved`.
- Short-prefix typed ref (`interpretation:0013`) resolves via `entity_prefixes`.
- Fabricated ref (`interpretation:9999`) extracts but is `unresolved`; a number
  whose only provenance is that ref stays `Unanchored`.
- Over-capture (`note:foo`) yields at most an `unresolved` candidate and never
  anchors.
- End-to-end: a numeric claim in a paragraph citing a resolvable
  `interpretation:NNNN` classifies as `Anchored`.
- Regression: the existing extraction/resolution/word-boundary/wiki-link/
  `config/`-path tests stay green unchanged.

Plus `ruff check`, `pyright`, and the full `pytest` suite from `science/`.

## Acceptance (pan-disease)

Run pan-disease's `science prose lint --check numeric-anchor` with the worktree
science overlaid (`uv run --with-editable <worktree>/science`). Expect:

- The ~48 entity-ref-grounded findings clear.
- Mixed spec docs that embed empirically-grounded values cited by entity-ref
  (e.g. `pre-registration:0012`) anchor those values.
- No regressions elsewhere (other checks and counts unchanged).

## Docs

Update `docs/conventions/prose-lints.md` numeric-anchor section: resolvable
typed entity-ref citations (both full-id and short numeric-prefix forms) count
as paragraph-local anchors, existence-checked against the entity index.

## Files

- `src/science_tool/numeric_provenance.py` — `_BODY_REF_RE`, `ResolutionIndex`
  (add `entity_prefixes`), `build_resolution_index`, `resolve`.
- `tests/test_numeric_provenance.py` — new tests + confirm regressions green.
- `docs/conventions/prose-lints.md` — one paragraph.

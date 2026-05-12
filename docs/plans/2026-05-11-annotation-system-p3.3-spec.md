# P3.3 — Author CRUD: list / ack / dismiss / fix / stats (Spec)

> **Phase 3 of the annotation system.** Builds on P3.0 (data model + sidecar
> I/O), P3.1 (drift detection), P3.2 (mechanical-source write path).
> Adds the author-facing read/triage surface: query annotations, transition
> their status, and aggregate counts. Folds in four mechanical follow-ups
> from the P3.2 final review where they touch shared code.

**Status:** draft 2026-05-11.
**Predecessors:** [P3.0](2026-05-11-annotation-system-p3.0.md),
[P3.1](2026-05-11-annotation-system-p3.1.md),
[P3.2](2026-05-11-annotation-system-p3.2.md).
**Spec source of truth:** [annotation-system-spec](2026-05-10-annotation-system-spec.md)
§"CLI surface", §"Status lifecycle", §"Migration from phase 2".

---

## Goals

1. Ship `science annotate list [PATH]` — table/JSON over project annotations
   with status / source-glob / `--since` filtering. Default view is open
   annotations only.
2. Ship `science annotate ack <ID>`, `dismiss <ID> --reason "..."`,
   `fix <ID>` — author-facing status mutations. Each transitions exactly
   one annotation, rewrites its sidecar atomically, preserves the prior
   state via `prov:wasRevisionOf`.
3. Ship `science annotate stats` — three-section aggregation
   (by_status, by_source, by_type) over the project.
4. Land four mechanical follow-ups from the P3.2 final review where they
   touch code P3.3 modifies (sentence-split helper extraction; `assert`→
   `ValueError` in `audit.merge_planned`; `mint_id` O(N²)→O(N);
   marker-token selector duplication).

## Non-goals

- **`science annotate render`.** Terminal/HTML rendering with color and
  hover tooltips is P3.4. P3.3's `list` is a tabular query surface; it
  does not produce inline-prose-with-marks output.
- **`--type <annotation-type>` filter on `list`.** Spec mentions it but
  it overlaps heavily with `--source` (one source typically maps to one
  type) and adds another orthogonal filter axis. Defer until a real use
  case demands it; `--source` covers the common triage paths.
- **Top-N entity aggregation in `stats`.** "Which files have the most
  open annotations?" is a useful view but requires sort/truncate UI
  work. Defer to P3.4 alongside `render`.
- **Batch CRUD.** Each mutation command takes exactly one `<ID>`. No
  `ack a-7f3a a-7f3b ...`, no `--from-file`. Status mutation is a
  per-decision act, not a sweep; if a sweep is needed later, add it
  then with explicit semantics.
- **Re-resolving the selector during `fix`.** `fix` trusts the author.
  Drift gets caught by the next `verify` run.
- **A persistent index.** ID lookup walks sidecars on every invocation.
  No `.science-annotate-index.json` cache, no incremental update path.
  Walk cost is O(sidecars × annotations) on every CRUD invocation;
  acceptable until project sizes make it visibly slow.
- **`prose lint` deprecation.** Long-term `prose lint` may collapse to
  a thin wrapper over `annotate list --source 'lint:*'`; that's not
  P3.3 work.
- **Touching `verify` or `audit` CLIs.** Their command surfaces are
  stable. Only `audit.py` internals change to fold follow-ups (2) and
  (3); behavior unchanged. `lifecycle.py` *is* touched — see Decision
  12 — but the change is tightening one guard, not reshaping the
  module.

## Decisions ratified during brainstorming

1. **`stats` ships in P3.3** alongside CRUD. Same project-walk plumbing
   as `list`; piggybacks at near-zero cost.
2. **ID resolution: walk-on-every-call, no cache.** Two qualifier
   forms accepted:
   - **Bare frag** (`a-7f3a`) — works when the frag is unique across
     the project. Ambiguous → error with rel-path candidates.
   - **Qualified** (`<entity-key>:<frag>`) where `entity-key` is
     either a *bare stem* (`foo`) or a *rel-path-without-suffix*
     (`notes/foo`). Bare stem is unique-when-it-is-unique; on
     collision the user gets an error listing rel-path candidates.
     Rel-path form is always unambiguous. Both are accepted by the
     CLI; the resolver picks the right strategy by checking for `/`
     in the entity-key.
3. **`dismiss --reason` is required.** Refuse with `ClickException`
   when absent or whitespace-only. Forensic value: re-audit may
   reproduce the finding later; the reason is the author's recorded
   judgement.
4. **`fix` does not re-resolve the selector.** Author trust;
   `verify` catches drift on its own schedule. Symmetric with `ack`/
   `dismiss`, neither of which inspect prose.
5. **`list` defaults to `--status open`.** Triage view. Other statuses
   accessed explicitly; `--status all` is a literal sentinel for
   no-filter.
6. **`list` filter axes shipped:** `--status` (multi), `--source`
   (multi, supports trailing `*` glob), `--since <git-ref>`. `--type`
   deferred (see Non-goals).
7. **`stats` aggregates three axes**, all independent: status, source
   (exact source name strings, including version suffixes), annotation
   type. Same row contributes to all three.
8. **No defensive `(target, source)` dedupe at read time.** P3.2's
   write-side dedupe key prevents duplicates at write; if a hand-edited
   sidecar contains a duplicate, `verify` is the right tool to surface
   it. `list`/`stats` count every row.
9. **One core CRUD function for three verbs.** `crud.apply_status_change`
   is parameterised on `new_status` and `reason`; `ack_cmd`, `dismiss_cmd`,
   `fix_cmd` are thin shells over it.
10. **Per-sidecar dirty-tree guard, not project-wide.** Editing prose
    while ack-ing an annotation is fine; only an uncommitted edit to
    the *target sidecar* refuses without `--force-dirty`. Mirrors
    verify's `--apply` guard pattern but narrowed to one file.
11. **`--actor` resolution order:** `--actor` flag → `git config
    user.email` → fail with explicit error. No `unknown` / `cli` /
    hostname fallback (no silent fallbacks per CLAUDE.md).
12. **Tighten `lifecycle.mutate_status`: author transitions require
    `OPEN` source.** Per source-spec §"Status lifecycle"
    (lines 266, 292), `ack`/`fixed`/`dismissed` are author-set from
    `open` only; `superseded` is tooling-set. Current
    `lifecycle._TERMINAL_STATES` correctly refuses transitions out of
    `ack`/`fixed`/`dismissed`, but it permits `superseded → ack/fixed/
    dismissed`, which contradicts the source spec (superseded means
    "the prose moved on"; resurrecting it via author CRUD is
    confusing and wrong). P3.3 tightens the guard: any
    non-`SUPERSEDED` `new_status` requires source status `OPEN`. The
    auto `* → SUPERSEDED` transition is unchanged (still permitted
    from any status). One-line change to `lifecycle.py`; existing
    tests covering `OPEN → *` and terminal refusal stay green; new
    test covers `SUPERSEDED → ack` refusal.
13. **`list [PATH]` accepts directory, markdown file, or sidecar.**
    Directory → walk that subtree. Markdown file → derive sidecar via
    `io.sidecar_for_markdown(path)` (handles multi-dotted names like
    `paper.v1.md`) and read it directly. `.anno.trig` file → read it
    directly. Bare `list` (no positional) → walk from `--root` (cwd
    default). `--root` and positional `PATH` are mutually exclusive
    (Click enforces with custom callback; both → `ClickException`).
14. **Read-time `(target, source)` dedupe is a no-op for P3.3.** The
    source spec's dedupe rule (§"Migration from phase 2" line 555)
    targets the unified inline-token + sidecar-row view that
    `render` (P3.4) produces. `list` reads only sidecar rows, where
    P3.2's 4-tuple write-side key (`source_name, target.exact,
    lifted_from, match_text`) already prevents intra-sidecar
    `(target, source)` duplicates at write time. So `list` and
    `stats` count every row without further dedupe. The spec's rule
    is preserved, not superseded — it just lives at the unified-view
    layer (P3.4), not the per-sidecar read layer (P3.3).
15. **Folded follow-ups: (1), (2), (3), (7).** Deferred: (4)
    `_strip_tokens_from_prose` re-walk, (5) `LintSource.scan` Sidecar
    O(N²), (6) `audit_file` parallelization. None are touched by P3.3
    code paths and none have measured performance impact.

## Architecture

### Module layout

```
science/src/science_tool/annotation/
├── audit.py                    # MOD: assert→ValueError; mint_id O(N²)→O(N)
├── cli.py                      # MOD: +5 commands (list/ack/dismiss/fix/stats)
├── crud.py                     # NEW: apply_status_change orchestrator
├── io.py                       # MOD: serialize_sidecar + atomic_write_text move here
├── lifecycle.py                # MOD: tighten guard (Decision 12)
├── model.py                    # unchanged
├── query.py                    # NEW: walk + resolve_id + filter + stats
├── selector.py                 # unchanged (resolution algorithm only)
├── sources/
│   ├── lint.py                 # MOD: switch to text_segmentation helpers
│   └── marker_token.py         # MOD: switch to text_segmentation helpers
├── text_segmentation.py        # NEW: extracted sentence-split + selector-build
└── verify.py                   # unchanged
```

`query.py` ≈ 200 lines, `crud.py` ≈ 120 lines, `text_segmentation.py` ≈
120 lines. `cli.py` net add ≈ 250 lines (lands ~950 lines total — at
the upper edge but still single-file; revisit decomposition in P3.4 if
it grows further).

### Read concerns: `query.py`

**Public surface (4 functions):**

```python
def iter_sidecars(root: Path) -> Iterator[tuple[Path, Sidecar]]:
    """Walk root, yield (sidecar_path, parsed Sidecar) for every *.anno.trig.

    Wraps any read_sidecar exception (ValueError, FileNotFoundError,
    rdflib parse errors) in SidecarParseError(sidecar_path, cause).
    The first SidecarParseError propagates; iteration stops. CLI layer
    converts to ClickException naming the offending file.
    """

def resolve_id(root: Path, id_arg: str) -> ResolvedAnnotation:
    """Resolve `a-7f3a` (bare frag) or `entity:a-7f3a` (qualified)
    to (sidecar_path, Annotation, entity).

    Raises:
      AnnotationNotFound       — no match
      AmbiguousAnnotationId    — bare frag matches >1 sidecar;
                                 .candidates lists qualified forms
    """

def filter_annotations(
    sidecars: Iterable[tuple[Path, Sidecar]],
    *,
    statuses: frozenset[Status] | None = None,        # None == no status filter
    sources: tuple[str, ...] = (),                    # empty == no source filter
    since_changed: frozenset[Path] | None = None,     # None == no since filter
) -> Iterator[tuple[Path, Annotation]]:
    """AND across all predicates. Source patterns support trailing `*`."""

def compute_stats(
    sidecars: Iterable[tuple[Path, Sidecar]],
) -> StatsReport:
    """Three independent aggregations; one row contributes to all three."""
```

**Supporting types (frozen dataclasses in `query.py`):**

```python
@dataclass(frozen=True)
class ResolvedAnnotation:
    sidecar_path: Path
    sidecar: Sidecar           # full parse, so callers don't re-read
    annotation: Annotation
    entity_stem: str           # bare markdown stem ("foo")
    entity_relpath: str        # rel-to-root, no suffix ("notes/foo")

@dataclass(frozen=True)
class StatsReport:
    by_status: dict[Status, int]
    by_source: dict[str, int]
    by_type: dict[str, int]
    total_annotations: int
    total_sidecars: int

class AnnotationLookupError(Exception): ...
class AnnotationNotFound(AnnotationLookupError): ...
class AmbiguousAnnotationId(AnnotationLookupError):
    candidates: tuple[str, ...]   # rel-path-qualified IDs

class SidecarParseError(Exception):
    sidecar_path: Path
    cause: Exception
```

**ID resolution algorithm:**

The qualified form is `<entity-key>:<frag>` where `entity-key` is
either:
- a **bare stem** like `foo` (works only when stem is unique across the
  project), or
- a **rel-path-without-suffix** like `notes/foo` (always unambiguous;
  resolves to `<root>/notes/foo.anno.trig`).

Algorithm:

1. If `id_arg` contains `:`, split on first `:` into (`entity_key`, `frag`).
   - If `entity_key` contains `/`: look up
     `<root>/<entity_key>.anno.trig` (exact path). No file →
     `AnnotationNotFound("no sidecar at <path>")`.
   - Else (bare stem): collect every `<root>/**/<entity_key>.anno.trig`.
     Zero → `AnnotationNotFound`. >1 → `AmbiguousAnnotationId(
     candidates=(rel-path-qualified IDs, ...))` so the user knows the
     full forms to retry with. 1 → use it.

   Then search the chosen sidecar's annotations for `id == frag`. No
   match → `AnnotationNotFound`.
2. Else (`a-7f3a` bare frag): walk all sidecars. Collect matches.
   Zero → `AnnotationNotFound`. >1 → `AmbiguousAnnotationId(
   candidates=(rel-path-qualified IDs, ...))`. 1 → return.

Candidates in `AmbiguousAnnotationId` always use rel-path form to
guarantee the user has an unambiguous handle to retry with.

**`--since <git-ref>` plumbing.** Helper
`git_changed_markdown(root: Path, ref: str) -> frozenset[Path]` runs
`git diff --name-only <ref>... -- '*.md'` from `root`, returns absolute
paths. Empty result → empty filter (no entities pass). Non-zero git
exit / not-a-repo → `ClickException` from the CLI layer (no silent
fallback). `filter_annotations` excludes a `(sidecar_path, annotation)`
when `io.markdown_for_sidecar(sidecar_path)` is not in the changed
set.

**Source pattern matching.** `fnmatch.fnmatchcase(source_name, pattern)`
per pattern; OR across patterns. Empty patterns tuple → no filter.
Supports `lint:*` (prefix glob) and exact literals.

### Write concerns: `crud.py`

**Public surface:**

```python
def apply_status_change(
    root: Path,
    id_arg: str,
    new_status: Status,
    *,
    actor: str,
    now: datetime,
    reason: str | None = None,
    force_dirty: bool = False,
) -> CrudResult:
    """Resolve → guard dirty tree → mutate via lifecycle → atomic rewrite."""

@dataclass(frozen=True)
class CrudResult:
    sidecar_path: Path
    qualified_id: str           # "<entity>:<frag>"
    prior_status: Status
    new_status: Status

class CrudRefusedDirty(Exception):
    sidecar_path: Path
```

**Steps inside `apply_status_change`:**

1. `resolved = query.resolve_id(root, id_arg)` — returns
   `ResolvedAnnotation(sidecar_path, sidecar, annotation,
   entity_stem, entity_relpath)`.
2. If `not force_dirty and _sidecar_is_dirty(root, resolved.sidecar_path)`:
   `raise CrudRefusedDirty(sidecar_path=...)`.
3. `mutated = lifecycle.mutate_status(resolved.annotation, new_status,
   actor=actor, now=now, reason=reason)` — propagates lifecycle
   `ValueError` for non-`OPEN`-source / terminal-state /
   transition-to-open refusals.
4. Build new `Sidecar` by replacing the matching annotation in
   `resolved.sidecar.annotations` (tuple comprehension; preserves order).
5. `io.atomic_write_text(resolved.sidecar_path, io.serialize_sidecar(new_sidecar))`.
6. Return `CrudResult(sidecar_path=resolved.sidecar_path,
   qualified_id=f"{resolved.entity_relpath}:{resolved.annotation.id}",
   prior_status=resolved.annotation.status, new_status=new_status)`.

The `qualified_id` always uses rel-path form (not bare stem) so the
output round-trips into a follow-up CRUD command without ambiguity.

**Helper migration into `io.py`.** P3.2's `_atomic_write_text` and
`_serialize_sidecar` live in `cli.py:664-693`. Move them to `io.py` as
public `atomic_write_text(path: Path, text: str) -> None` and
`serialize_sidecar(sidecar: Sidecar) -> str`. Update `cli.py` import;
no behavior change for `lift-tokens`.

**Path-derivation helpers in `io.py` (new).** Both directions need
explicit, fail-loud helpers — `Path.with_suffix` alone misbehaves on
multi-dotted names (`Path("paper.v1.anno.trig").with_suffix(".md")`
returns `paper.v1.anno.md`, not `paper.v1.md`). The two helpers:

```python
def sidecar_for_markdown(md_path: Path) -> Path:
    """foo.md → foo.anno.trig; paper.v1.md → paper.v1.anno.trig.

    Matches P3.2's `md_path.with_suffix(".anno.trig")` convention.
    Raises ValueError if md_path does not end with `.md`.
    """

def markdown_for_sidecar(sidecar_path: Path) -> Path:
    """foo.anno.trig → foo.md; paper.v1.anno.trig → paper.v1.md.

    Strips the literal `.anno.trig` suffix and appends `.md`. Raises
    ValueError if sidecar_path does not end with `.anno.trig`.
    """
```

All call sites that currently chain `with_suffix("").with_suffix(...)`
or use ad-hoc string slicing for these conversions switch to the
helpers: `query.iter_sidecars` (no — already walks `*.anno.trig`
glob), `query.filter_annotations` `--since` predicate (uses
`markdown_for_sidecar`), `cli.list_cmd` PATH-is-markdown branch (uses
`sidecar_for_markdown`).

**`_resolve_actor(actor_opt: str | None, root: Path) -> str`** lives in
`crud.py`. Returns `actor_opt` if given; else `git config user.email`
from `root`; else raises `ClickException("--actor required (no git
user.email available)")`. Helper-only; not in the public surface.

### CLI surface

**`science annotate list [PATH]`** — query/filter projection.

`PATH` (positional, optional) selects the read scope:
- *Directory*: walk that subtree for `*.anno.trig`.
- *Markdown file* (`foo.md`): read only `foo.anno.trig` (no walk).
  Missing sidecar → empty result, not error.
- *Sidecar file* (`foo.anno.trig`): read it directly.
- *Omitted*: walk from `--root` (cwd default).

`PATH` and `--root` are mutually exclusive. Specifying both →
`ClickException("--root and PATH are mutually exclusive")`.

| Option | Type | Default | Notes |
|---|---|---|---|
| `--root PATH` | Path | cwd | Mutually exclusive with positional `PATH` |
| `--status STATUS` | str (multi) | `open` | `all` is sentinel for no filter |
| `--source PATTERN` | str (multi) | (none) | Trailing `*` glob OK |
| `--since GIT_REF` | str | (none) | `git diff --name-only <ref>...` |
| `--format` | `table\|json` | `table` | |

Table columns: `entity:id  status  source  type  exact-preview`.
`entity:id` uses the rel-path-qualified form so it round-trips into
CRUD commands without ambiguity. `exact-preview` is
`selector.exact[:60]` with trailing `…` if truncated. Sorted by
`(entity, id)` for stable diffs. Trailing summary
`N annotation(s) across M sidecar(s)`.

JSON: `{"summary": {...}, "annotations": [{...}]}`.

Exit policy: 0 on success; 1 on filter / parse / git errors (see
matrix below). No 2 — list and stats can never produce ambiguous-id.

**`science annotate ack <ID>`**

| Option | Required | Notes |
|---|---|---|
| `--root PATH` | no | Default cwd |
| `--actor IDENTITY` | conditional | Falls back to `git config user.email` |
| `--force-dirty` | no | Bypasses per-sidecar guard |

Output: `ack: <entity:id> open → ack`. Exit 0 success; 1 on lookup /
dirty / lifecycle errors; 2 on ambiguous-id (so wrappers can
distinguish "fix your input" from "doesn't exist").

**`science annotate dismiss <ID> --reason "<text>"`**

Same options as `ack` plus required `--reason`. Empty / whitespace-only
rejected with `ClickException("--reason cannot be empty")`. Output:
`dismiss: <entity:id> open → dismissed (reason: ...)`.

**`science annotate fix <ID>`**

Same options as `ack`. No selector re-resolution. Output:
`fix: <entity:id> open → fixed`.

(Per `lifecycle._TERMINAL_STATES`, `ack` is terminal — author cannot
re-transition `ack → fixed`. The intended workflow is: author chooses
between `ack` ("noted, not acting") and `fix` ("prose now corrected")
when first encountering the open annotation. If a need for
`ack → fixed` arises, it's a `lifecycle.py` change, not a P3.3 CLI
change.)

**`science annotate stats`**

| Option | Default |
|---|---|
| `--root PATH` | cwd |
| `--format` | `table` |

Table: header `annotate stats: N annotations across M sidecars`, then
three sections (`By status`, `By source`, `By type`), each
descending-numerically-sorted. JSON: `{"summary", "by_status",
"by_source", "by_type"}`.

Exit policy: 0 on success; 1 on parse errors. Same surface as `list`.

### Error handling matrix

| Condition | Exception | Exit | Message shape |
|---|---|---|---|
| ID not found | `AnnotationNotFound` | 1 | `no annotation matching '<id_arg>'` |
| Bare ID ambiguous | `AmbiguousAnnotationId` | 2 | `ambiguous: '<id_arg>' matches:\n  ent1:a-7f3a\n  ent2:a-7f3a\nuse 'entity:id' form` |
| Sidecar dirty | `CrudRefusedDirty` | 1 | `refusing: <sidecar> has uncommitted changes; commit/stash or use --force-dirty` |
| Transition to `open` | `ValueError` | 1 | (lifecycle msg) `cannot transition to 'open'; status flows forward only` |
| Already terminal | `ValueError` | 1 | (lifecycle msg) `annotation 'a-7f3a' is already in terminal status 'fixed'` |
| Source not `OPEN` (e.g. superseded → ack) | `ValueError` | 1 | (lifecycle msg) `cannot ack/dismiss/fix annotation 'a-7f3a' in status 'superseded'; only 'open' annotations accept author transitions` |
| `--root` and positional `PATH` both given | `ClickException` | 1 | `--root and PATH are mutually exclusive` |
| `dismiss` empty reason | `ClickException` | 1 | `--reason cannot be empty` |
| `--since` not in repo | `ClickException` | 1 | `--since requires a git repository at <root>` |
| `--since` ref invalid | `ClickException` | 1 | propagated git stderr |
| Sidecar parse error | `SidecarParseError` (wraps `ValueError`/`FileNotFoundError`/rdflib) | 1 | first failure aborts; CLI message includes `sidecar_path` and `cause` |
| `--actor` unresolvable | `ClickException` | 1 | `--actor required (no git user.email available)` |

No silent fallbacks; each failure tells the operator exactly what to
fix. Matches the project's "fail early" core dev rule.

## Folded follow-ups

### Follow-up 1 + 7 — sentence-split + selector-build extraction

New `annotation/text_segmentation.py`:

```python
def split_sentences_with_offsets(text: str) -> list[tuple[int, int]]:
    """(start, end) char ranges of each sentence."""

def sentence_range_at(text: str, line: int, col: int) -> tuple[int, int] | None:
    """Sentence-range covering the (line, col) cursor position.

    Falls back to nearest preceding sentence when (line, col) lies in
    inter-sentence whitespace. `col` is REQUIRED — there is no default.
    Lint findings carry both line and col, so this is the right API
    for that caller. Callers without a column should use
    `sentence_range_containing_literal` instead.
    """

def sentence_range_containing_literal(
    text: str, line: int, literal: str,
) -> tuple[int, int] | None:
    """Sentence containing `literal` on the given line.

    Searches `line` for `literal`, then maps its character offset to a
    sentence range. Returns None if the literal is not on that line.
    Designed for line-only callers (e.g. MarkerHit, which carries
    `line` and `token` but no `col`). Picking the right sentence even
    when multiple sentences share a line is load-bearing — token
    appearing in the second sentence on a line must NOT anchor to the
    first sentence's range.
    """

def build_quote_selector(
    text: str, sent_start: int, sent_end: int, *, context: int = 60,
) -> TextQuoteSelector:
    """Build TextQuoteSelector with prefix/suffix windows of `context` chars."""
```

(Module name `text_segmentation`, not `selector`, to keep `selector.py`
focused on resolution.)

Callers updated:
- `sources/marker_token.py` — replaces `_sentence_range_at` and
  `_build_selector`. Calls `sentence_range_containing_literal(text,
  hit.line, f"[{hit.token}]")` since `MarkerHit` lacks `col`. Both
  `scan` and `scan_text` use the same helpers (closes Follow-up 7).
- `sources/lint.py` — replaces `_selector_for_issue`. Calls
  `sentence_range_at(text, issue.line, issue.col)` since lint findings
  carry both.
- `cli.py:_replan_for_remove` — uses
  `sentence_range_containing_literal` on `original_text` to find the
  source sentence, then maps to `cleaned_text` by sentence ordinal
  (existing logic preserved; helpers from this module take over the
  segmentation).

**Why two helpers, not one with optional col?** A single
`sentence_range_at(text, line, col=1)` defaults to col=1, which silently
mis-anchors marker tokens that appear after the first sentence on a
line. Better to make `col` required and surface the column-less case as
a distinct call site (`sentence_range_containing_literal`).

Net effect: ~80 lines of near-duplicated code removed across the three
callers; one canonical implementation in `text_segmentation.py`. No
changes to `markers.py` or `MarkerHit` (column-add stays out of P3.3
scope).

### Follow-up 2 — `merge_planned` invariant: assert → ValueError

In `audit.py`, every `assert` that protects an invariant (not a debug
hint) becomes `if not <cond>: raise ValueError(<msg>)`. The
single-source invariant in `merge_planned` is the load-bearing case.
Existing tests using `pytest.raises(AssertionError)` switch to
`pytest.raises(ValueError)`.

### Follow-up 3 — `mint_id` O(N²) → O(N)

Build `taken_ids: set[str] = {a.id for a in sidecar.annotations}` once
at the top of `mint_id`. Probe `f"{base}-{n}"` against the set instead
of iterating annotations. Keeps the same suffix-allocation semantics
(deterministic, smallest unused N).

## Testing

### Unit tests (`tests/annotation/`)

- `test_text_segmentation.py` — sentence boundaries, multi-line, edge
  cases (empty, no-period, fragment); `sentence_range_at(text, line,
  col)` resolution and inter-sentence fallback;
  `sentence_range_containing_literal(text, line, literal)` correctly
  picks the SECOND sentence on a multi-sentence line when the literal
  appears there (regression for marker-token mis-anchoring); literal
  not on line returns None; `build_quote_selector` prefix/suffix
  windowing at file boundaries (full-window in middle, truncated
  prefix near start-of-file, truncated suffix near EOF).
- `test_io_path_helpers.py` — `sidecar_for_markdown` and
  `markdown_for_sidecar` round-trip on simple (`foo.md`),
  multi-dotted (`paper.v1.md`), and rejected inputs (`README` →
  ValueError; `foo.txt` → ValueError); round-trip identity holds for
  all valid inputs.
- `test_query_resolve_id.py` — bare-frag unique / bare-frag ambiguous
  / bare-frag not-found / qualified bare-stem unique / qualified
  bare-stem ambiguous (two `notes/foo.anno.trig` and
  `appendix/foo.anno.trig`, error candidates use rel-path form) /
  qualified rel-path hit / qualified rel-path missing-sidecar /
  qualified missing-frag.
- `test_query_iter_sidecars_parse_error.py` — corrupt `*.anno.trig`
  triggers `SidecarParseError` with correct `sidecar_path` and
  `cause`; CLI smoke test asserts `ClickException` message names the
  file and cause class.
- `test_query_filter.py` — status filter (default, multi, `all`); source
  glob (`lint:*`, exact, multi-pattern OR); `--since` with mock git
  helper; AND across all predicates.
- `test_query_stats.py` — three-axis aggregation; one row contributes to
  all three; descending-sorted output invariant; empty corpus.
- `test_crud_apply.py` — happy path each verb (open→ack, open→fixed,
  open→dismissed); terminal-state refusal (ack→fixed, fixed→dismissed,
  dismissed→ack all rejected); **non-OPEN-source refusal**
  (superseded→ack, superseded→fixed, superseded→dismissed all
  rejected); dirty-tree refusal; `--force-dirty` bypass; reason
  persists in `dc:description`; `prov:wasRevisionOf` records prior
  status; round-trip write→re-parse→compare.
- `test_lifecycle_open_source_guard.py` — direct unit test of the
  tightened `lifecycle.mutate_status` guard: `OPEN → {ACK, FIXED,
  DISMISSED}` allowed; `SUPERSEDED → {ACK, FIXED, DISMISSED}`
  refused; `* → SUPERSEDED` allowed from any status.
- `test_audit_invariants.py` (new or extend existing) — `merge_planned`
  raises `ValueError` (not `AssertionError`) on cross-source contamination;
  exercises code path under `python -O` (assert-stripped) by import
  rather than runtime flag.
- `test_audit_mint_id.py` (extend) — assert `mint_id` is O(N) not O(N²)
  via timing harness on N=1000 annotations (loose bound, ~10× margin).

### CLI tests (`tests/cli/test_annotate_p33.py`)

Click `CliRunner` based:
- One smoke test per command (happy path, table + json).
- `list` PATH modes: directory (subtree walk), markdown file
  (single-sidecar derive), `.anno.trig` (direct), omitted (root walk),
  missing markdown (empty result, exit 0), `--root` + PATH conflict
  (exit 1).
- `list` filter combinations (status, source glob, since with mock
  git, `--since` outside repo → exit 1).
- `ack` / `dismiss` / `fix` happy path, plus each error class above.
- `dismiss` empty-reason rejection.
- `stats` three-section table output, JSON schema.
- Ambiguous-bare-frag integration: fixture with two sidecars in
  separate dirs sharing `a-aaaa`; `ack a-aaaa` exits 2 with both
  candidates in rel-path form.
- Ambiguous-bare-stem integration: fixture with `notes/foo.anno.trig`
  + `appendix/foo.anno.trig`; `ack foo:a-7f3a` exits 2 with both
  rel-path candidates; `ack notes/foo:a-7f3a` succeeds.

### Fixture corpus (`tests/_fixtures/annotation/p33/`)

- `multi-entity/` — two `*.md` + two `*.anno.trig` in separate
  subdirectories with intentionally colliding bare frag IDs (`a-aaaa`
  in both) for ambiguous-bare-frag path.
- `bare-stem-collision/` — `notes/foo.md` + `notes/foo.anno.trig`
  alongside `appendix/foo.md` + `appendix/foo.anno.trig` for
  ambiguous-bare-stem path; rel-path qualified form must succeed.
- `mixed-statuses/` — single sidecar containing one annotation in each
  of the five statuses, drives `list --status all` and `stats`.
- `dirty-tree/` — single sidecar; tests set up via subprocess
  `git init && git add && git commit` then mutate without committing
  to exercise the dirty-tree guard.

### Integration test

Extend `tests/annotation/test_audit_idempotent.py` style: run `audit`
to populate a sidecar, then exercise `list` (default + filtered),
`ack`, `dismiss --reason`, `fix`, `stats` via real CLI invocation. Final
state asserted via `read_sidecar` + structural compare.

## Plan task ordering

Rough dependency order (writing-plans will refine into bite-sized tasks):

1. Extract `text_segmentation.py`; update `marker_token.py`, `lint.py`,
   `cli.py:_replan_for_remove` to use it. Tests for the new module.
   (Follow-ups 1 + 7.)
2. `audit.py` invariant + `mint_id` fixes. Update affected tests.
   (Follow-ups 2 + 3.)
3. Tighten `lifecycle.mutate_status` (Decision 12) + add
   `test_lifecycle_open_source_guard.py`.
4. Move `serialize_sidecar` + `atomic_write_text` from `cli.py` into
   `io.py`. Update `cli.py` imports.
5. Build `query.py` (walk, resolve_id, filter, stats,
   `SidecarParseError` wrapping) + unit tests.
6. Build `crud.py` + unit tests.
7. Wire `list` CLI + tests.
8. Wire `ack` / `dismiss` / `fix` CLI + tests.
9. Wire `stats` CLI + tests.
10. Integration test pass.

## Out of scope reminders (for the P3.4+ author)

- `render` (terminal + HTML) — P3.4.
- Top-N entity stats axis — P3.4.
- `--type` filter on `list` — defer until use case demands.
- Persistent ID index — defer until walk cost is measured to hurt.
- LLM auditor — P3.5.

## Cross-references

- [P3.0](2026-05-11-annotation-system-p3.0.md) — sidecar I/O and data model.
- [P3.1](2026-05-11-annotation-system-p3.1.md) — verify (precedent for
  `--apply --actor --force-dirty` pattern).
- [P3.2](2026-05-11-annotation-system-p3.2.md) — audit / lift-tokens
  (precedent for atomic-write-then-rewrite, dirty-tree guard).
- [annotation-system-spec](2026-05-10-annotation-system-spec.md) §"CLI
  surface", §"Status lifecycle", §"Migration from phase 2".

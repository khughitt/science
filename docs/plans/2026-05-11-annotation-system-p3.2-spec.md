# P3.2 — Lift Mechanical Lints + Tokens (Spec)

> **Phase 3 of the annotation system.** Builds on P3.0 (data model + sidecar
> I/O) and P3.1 (drift detection). Establishes the write-side machinery for
> mechanical annotation sources: the inline-token migration (`lift-tokens`)
> and a generic `audit` umbrella that runs detector functions and writes
> annotation rows. Closes the inline/sidecar double-count loop in
> `validate.sh` Section 8.

**Status:** approved 2026-05-11.
**Predecessors:** [P3.0](2026-05-11-annotation-system-p3.0.md),
[P3.1](2026-05-11-annotation-system-p3.1.md).
**Spec source of truth:** [annotation-system-spec](2026-05-10-annotation-system-spec.md)
§"Migration from phase 2", §"CLI surface", §"Annotation type vocabulary".

---

## Goals

1. Ship `science annotate lift-tokens` as a one-shot migration for the
   four phase-2 inline tokens (`[UNVERIFIED]`, `[MISSING_CITATION]`,
   `[SPECULATION]`, `[INACCESSIBLE]`).
2. Ship `science annotate audit` as the umbrella write-side command for
   mechanical sources. In P3.2 this dispatches three `prose lint`
   detectors (`bare-author-year`, `short-form-ids`, `numeric-anchor`);
   the fourth, `frontmatter-inline-gap`, is deferred — see Decision 9.
   The architecture is forward-compatible with P3.5's LLM source.
3. Close the dedupe loop: `science markers scan --ignore-lifted` skips
   inline tokens whose enclosing sentence already has a sidecar row;
   `validate.sh` Section 8 sets the flag by default (managed-artifact
   bump).

## Non-goals

- **Touching `science prose lint`.** Its current ephemeral
  table/JSON output is unchanged in P3.2. The same detector functions
  are reused by `audit`, but the existing CLI keeps its read-only
  semantics. Long-term (post-P3.4) `prose lint` becomes a thin wrapper
  over `annotate list --source 'lint:*'`; that deprecation is *not*
  P3.2 work.
- **`audit --since <git-ref>`.** Listed in the spec's CLI surface but
  deferred — it requires per-paragraph git-diff plumbing and the value
  is small until LLM sources land in P3.5.
- **Body promotion (richer linking).** The spec's example 2 lifts a
  `bare-author-year` hit to a `cites` row whose body is a
  `<bib:brunton-2022>` IRI. P3.2 ships textual bodies only; the bib
  resolver pass is a follow-up.
- **`science annotate ack / dismiss / fix`.** Status mutation CRUD is
  P3.3. P3.2 only writes `Status.OPEN` rows; the idempotent merge
  preserves existing mutations across re-runs but never authors them.
- **AuditLedger usage.** P3.2 deduplicates via row-existence check
  on the 4-tuple `(source_name, target.exact, lifted_from,
  match_text)`. The ledger remains in
  the data model (added in P3.0) but is not written by P3.2 — it
  becomes P3.5's mechanism for LLM-source cost control.
- **Render / list surfaces.** P3.3 / P3.4. P3.2 produces sidecar rows
  but provides no human-friendly query/render path beyond the
  `audit --format json` raw dump.

## Decisions ratified during brainstorming

1. **Scope:** all three of {lift-tokens, lint→rows write path, dedupe
   wiring} ship together.
2. **Lint refactor depth:** the `prose lint` CLI is untouched. A new
   `science annotate audit` is the write path; both reuse the same
   detector functions in `science_tool/prose_lint.py`.
3. **`lift-tokens` default:** `--mirror` (non-destructive). `--remove`
   strips inline tokens but refuses if `git status` is dirty for the
   affected files; `--force-dirty` overrides.
4. **Section 8 dedupe:** ship the `--ignore-lifted` flag *and* flip
   `validate.sh` Section 8 to use it by default in one
   managed-artifact bump.
5. **Source-version policy:** per-detector date stamp (e.g.,
   `lint:bare-author-year-v2026-05-11`). Bumping a detector's version
   forces re-audit for that detector only.
6. **Idempotence key:** the 4-tuple
   `(source_name, target.exact, lifted_from, match_text)`. Skip
   writing if a non-superseded row already matches. Status-mutated
   rows (ack/dismiss/fix) are preserved verbatim across re-runs.
   Superseded rows are *ignored* for dedupe — a re-run can produce a
   fresh `open` row at the same 4-tuple. ID disambiguation appends
   `-N` only when the existing row at `base_id` is the same finding's
   superseded predecessor; cross-tuple base_id collisions are fatal
   (raise `IdCollisionError`).
7. **`content_hash` always computed.** The P3.0 model invariant
   (lints + marker sources require `content_hash`) is preserved.
   `merge_planned` calls `annotation.hash.content_hash(target.exact,
   source_name)` for every newly-minted row; the value is stored
   even though P3.2 does not yet use the ledger.
8. **Code organization:** per-source modules under
   `annotation/sources/`. P3.5's LLM source slots in as
   `sources/llm_gap_d.py` without restructuring.
9. **`frontmatter-inline-gap` deferred from `audit`.** The detector
   emits file-level findings (`line=1, col=1`) that don't fit the
   sentence-target selector model. `science prose lint` keeps the
   detector intact; the annotation lift requires a frontmatter-aware
   selector strategy out of P3.2 scope.
10. **Model extension: `Annotation.match_text`.** Persisted via new
    TriG predicate `sci:matchText`. Required for round-trip
    preservation of the dedupe key. Optional field on the dataclass
    (legacy sidecars round-trip with `match_text = None`); reading a
    legacy row's `match_text` as `None` does not collide with planned
    rows that carry a real `match_text`. P3.0's round-trip guarantee
    extends to the new field.

---

## CLI surface (additions)

```
science annotate lift-tokens --root <dir>                   # Mirror inline tokens to sidecar rows
science annotate lift-tokens --root <dir> --remove          # Also strip inline tokens (requires clean tree)
science annotate lift-tokens --root <dir> --remove --force-dirty
science annotate lift-tokens --root <dir> --actor <id>      # Default: science-annotate-cli
science annotate lift-tokens --root <dir> --format {table,json}

science annotate audit --root <dir>                         # Run all mechanical sources
science annotate audit --root <dir> --source bare-author-year  # Run one source
science annotate audit --root <dir> --no-llm                # Accepted no-op in P3.2
science annotate audit --root <dir> --dry-run               # Show plan; do not write
science annotate audit --root <dir> --actor <id>            # Default: science-annotate-cli
science annotate audit --root <dir> --format {table,json}

science markers scan --ignore-lifted                        # New flag; existing command
```

`--source` is repeatable. Valid values are any key in `SOURCES`:
`bare-author-year`, `short-form-ids`, `numeric-anchor`, and
`marker-token` (advanced; normally invoked via `lift-tokens`).
`frontmatter-inline-gap` is **not** in `SOURCES` — see "Module
layout" for the deferral rationale. Future LLM source names slot in
(`llm-audit:gap-d-v1`, etc.); P3.2 rejects unknown source names with
a clear error message.

**Default source set** (when no `--source` given): `LINT_SOURCES` —
the three lint detectors above, excluding `marker-token`.

`--no-llm` is accepted but no-op in P3.2 — the architecture rejects
LLM sources in this phase; the flag exists for forward compatibility
with shell scripts that use it once P3.5 lands.

**Exit codes** (mirror P3.1's separation of "data fact" from "process
fact"):
- `0` — command succeeded; some rows may have been written.
- `1` — parse error on a sidecar, write error, unknown source name,
  or dirty-tree guard failure (lift-tokens).

`audit --dry-run` reports the planned writes and exits 0; it does not
treat "would write N rows" as a failure.

---

## Module layout

```
science/src/science_tool/annotation/
  sources/
    __init__.py             # exports SOURCES registry: {name → SourceAdapter}
    base.py                 # SourceAdapter protocol; PlannedAnnotation dataclass
    marker_token.py         # MarkerTokenSource (covers all 4 inline tokens)
    lint.py                 # LintSource per detector (3 instances; shared base class)
  audit.py                  # orchestrator: per-file walk, dispatch, idempotent merge
  cli.py                    # extended: adds `audit` and `lift-tokens` subcommands
```

### `sources/base.py`

```python
from typing import Iterable, Optional, Protocol
from dataclasses import dataclass
from pathlib import Path

from science_tool.annotation.model import (
    Body, Motivation, SpecificResource,
)


@dataclass(frozen=True)
class PlannedAnnotation:
    """A would-be annotation, before idempotence + ID minting.

    `match_text` is the per-finding identity token (the specific
    substring or token literal the source flagged). It distinguishes
    multiple findings within the same target sentence so dedupe and
    ID minting do not collapse them.
    """
    target: SpecificResource          # selector already constructed
    annotation_type: str
    motivation: Motivation
    body: Body
    match_text: str                   # per-finding identity (see merge rule)
    source_name: str                  # full source-version, e.g. "lint:bare-author-year-v2026-05-11"
    lifted_from: Optional[str] = None # set by marker_token source only


class SourceAdapter(Protocol):
    name: str        # e.g., "lint:bare-author-year-v2026-05-11"
    short_name: str  # e.g., "bare-author-year" (CLI --source value)

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]: ...
```

`content_hash` is **always computed** at write time (not stored on
`PlannedAnnotation`): `merge_planned` calls
`science_tool.annotation.hash.content_hash(target.exact, source_name)`
for every newly-minted row. The model invariant from P3.0 — `lint:`
and `marker-scanner:` sources require `content_hash` — is preserved
by P3.2 rather than relaxed.

### Persisting `match_text` on the model

The 4-tuple dedupe rule requires `match_text` to survive a
write/read round-trip. P3.2 extends the persisted model:

1. **`Annotation.match_text: Optional[str] = None`** — additive
   field on the frozen dataclass in
   `science_tool/annotation/model.py`. Optional for backward
   compatibility with existing P3.0/P3.1 sidecars (rows without the
   field default to `None`).
2. **TriG predicate `sci:matchText`** — new predicate on the `sci:`
   namespace, written by `io.write_sidecar` when
   `match_text is not None` and parsed by `io.read_sidecar` into the
   field. Sits next to `sci:liftedFrom` in emission order; same
   handling: a single string literal, no language tag.
3. **Round-trip preservation guarantee** (P3.0 §Round-trip
   guarantee) extends to the new field: skolemize → graph → parse →
   de-skolemize is byte-identical.

`merge_planned` reads `existing.match_text` directly when computing
the dedupe key — no derivation, no parsing of body text.

For pre-P3.2 sidecars (no `sci:matchText` written), `match_text`
reads back as `None`. The dedupe rule treats a `None` slot as
matching only another `None` — so a row planned with `match_text =
"Brunton 2022"` will not collide with a legacy row whose
`match_text` is missing. This is acceptable: legacy lifted rows
predate the dedupe rule and should not block re-audit. After the
first re-audit, the legacy row stays as-is and the new row coexists
under its own minted ID (computed from the new 4-tuple including
`match_text`); the two IDs differ. Operators clean up legacy rows
via P3.3's `dismiss` once it ships.

### `sources/marker_token.py`

`MarkerTokenSource` reads a `.md` file via the existing
`science_tool.markers.scan_text` (one source instance scans for all four
tokens; the resulting `MarkerHit` is mapped to a `PlannedAnnotation`
per the type table in §"Annotation-type mapping"). `lifted_from` is set
to the literal token form (`"[UNVERIFIED]"`, etc.).

`short_name = "marker-token"`. `name = "marker-scanner:phase-2"`.

### `sources/lint.py`

One module-level `LintSource` class; three instances are constructed
(one per in-scope detector — `frontmatter-inline-gap` is excluded;
see "Module layout") and registered in `sources/__init__.py:SOURCES`.
Each instance carries:

```python
LintSource(
    short_name="bare-author-year",
    name="lint:bare-author-year-v2026-05-11",
    detector=detect_bare_author_year,  # from prose_lint.py
    annotation_type="bare-author-year",
)
```

The detector returns `LintIssue(file, line, col, ...)`; `LintSource.scan`
reads the file, locates the sentence containing `(line, col)`, and
constructs a `TextQuoteSelector` (see §"Selector construction"). Body
is a `TextualBody` wrapping `LintIssue.message`.

### `sources/__init__.py`

```python
SOURCES: dict[str, SourceAdapter] = {
    "marker-token":            MarkerTokenSource(),
    "bare-author-year":        LintSource(short_name="bare-author-year", ...),
    "short-form-ids":          LintSource(short_name="short-form-ids", ...),
    "numeric-anchor":          LintSource(short_name="numeric-anchor", ...),
}

LINT_SOURCES = (
    "bare-author-year", "short-form-ids", "numeric-anchor",
)  # subset audited by default `audit --root <dir>` with no --source
```

`marker-token` is excluded from default `audit` because it is meant to
be lifted by the dedicated `lift-tokens` command, not the generic
audit walk. `audit --source marker-token` is permitted (advanced
usage); `lift-tokens` always uses it.

`frontmatter-inline-gap` is **deferred** from P3.2's audit surface.
The detector emits `(line=1, col=1)` for file-level findings, which
does not fit the sentence-target selector model. A frontmatter-aware
selector strategy (likely `oa:FragmentSelector` against a YAML
JSONPointer-style anchor, or selecting the literal `related: <ref>`
prose span) is a separate design problem and lands in a follow-up.
`science prose lint --check frontmatter-inline-gap` continues to work
unchanged.

### `audit.py`

```python
def merge_planned(
    sidecar: Sidecar,
    planned: Sequence[PlannedAnnotation],
    *,
    actor: str,
    now: datetime,
) -> tuple[Sidecar, list[Annotation]]:
    """Merge planned rows into sidecar; return (new_sidecar, written_rows).

    All `planned` rows MUST share the same `source_name` (caller
    groups by source — see `audit_file` orchestration). The function
    asserts this invariant.

    Per-finding identity (the dedupe key) is the 4-tuple:

        (source_name, target.exact, lifted_from, match_text)

    Idempotence rule: skip a planned row if the sidecar contains any
    annotation with status != SUPERSEDED whose 4-tuple matches.
    Superseded rows are ignored for dedupe — a re-run can produce a
    fresh OPEN row at the same selector + match_text.

    For each planned row that is NOT skipped:

      id          = mint_id(sidecar, planned)     # see ID minting below
      status      = Status.OPEN
      creator     = actor
      created     = now
      content_hash = annotation.hash.content_hash(target.exact, source_name)
    """
```

ID minting is deterministic on the 4-tuple. Disambiguation only
applies when the existing row at the same base ID is the **same
finding's predecessor** (matching 4-tuple, status `SUPERSEDED`); a
hash collision between **unrelated** 4-tuples is a fatal error.

```python
def mint_base_id(p: PlannedAnnotation) -> str:
    h = hashlib.sha256()
    h.update(p.source_name.encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.target.selector.exact.encode("utf-8"))
    h.update(b"\x1e")
    h.update((p.lifted_from or "").encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.match_text.encode("utf-8"))
    return f"a-{h.hexdigest()[:6]}"


def _annotation_tuple(a: Annotation) -> tuple[str, str, Optional[str], Optional[str]]:
    return (a.source, a.target.selector.exact, a.lifted_from, a.match_text)


def _planned_tuple(p: PlannedAnnotation) -> tuple[str, str, Optional[str], str]:
    return (p.source_name, p.target.selector.exact, p.lifted_from, p.match_text)


def mint_id(sidecar: Sidecar, p: PlannedAnnotation) -> str:
    """Mint the on-disk ID for a planned row.

    - If no existing row occupies base_id: return base_id.
    - If the existing row at base_id has the same 4-tuple AND its
      status is SUPERSEDED: return base_id-N where N is the smallest
      integer ≥ 2 such that base_id-N is unused. Subsequent
      superseded rows at the same finding extend the chain
      (base_id, base_id-2, base_id-3, ...).
    - If the existing row at base_id has the same 4-tuple AND its
      status is NOT SUPERSEDED: this branch is unreachable —
      `merge_planned`'s dedupe rule already skipped this planned row.
      An assert guards the invariant.
    - Otherwise (unrelated 4-tuple at same base_id): raise an
      explanatory error. The hash slice is too short for the sidecar
      size; bump from 6 to 8 hex chars and retry the audit.
    """
    base_id = mint_base_id(p)
    existing_at_base = next(
        (a for a in sidecar.annotations if a.id == base_id), None,
    )
    if existing_at_base is None:
        return base_id

    if _annotation_tuple(existing_at_base) == _planned_tuple(p):
        assert existing_at_base.status is Status.SUPERSEDED, (
            "merge_planned should have skipped a non-superseded match"
        )
        n = 2
        existing_ids = {a.id for a in sidecar.annotations}
        while f"{base_id}-{n}" in existing_ids:
            n += 1
        return f"{base_id}-{n}"

    raise IdCollisionError(
        f"base_id {base_id!r} occupied by unrelated 4-tuple "
        f"(existing source={existing_at_base.source!r}, "
        f"planned source={p.source_name!r}); bump hash slice length"
    )
```

`mint_id` also rejects collisions among *planned* rows themselves
(two distinct planned 4-tuples that hash to the same base ID before
either is written): `merge_planned` accumulates a per-call set of
freshly-minted IDs and raises `IdCollisionError` if a second planned
row tries to mint the same `base_id` without being a same-tuple
match.

The 6-hex-char base collides at ~1 in 16M for distinct 4-tuples;
unrelated cross-tuple collisions within a single sidecar abort the
write with an explanatory error. No collision is expected in
practice with sidecar sizes ≤ a few hundred rows.

Per-file orchestration (sources merged sequentially so each
`merge_planned` call sees the cumulative state):

```python
def audit_file(
    md_path: Path, sidecar_path: Path, sources: Sequence[SourceAdapter], *,
    actor: str, now: datetime,
) -> AuditFileReport:
    """Read sidecar (or empty if absent), run each source, merge per source,
    write back if anything new.

    Sidecar shared_targets and ledgers are preserved unchanged. The new
    annotations list is the union of (existing, newly-written-across-all-sources),
    sorted by ID at write time (write_sidecar already sorts).

    Sources are merged sequentially: each merge_planned call consumes
    the planned rows for ONE source and sees the sidecar state from
    all earlier merges in the same audit_file invocation. This keeps
    merge_planned's single-source invariant intact. Cross-source
    base_id collisions are unrelated 4-tuples — `mint_id` raises
    `IdCollisionError` and the audit aborts; that signals the hash
    slice length is too short for the workspace and needs to be
    bumped (operator-visible action).
    """
```

Empty-sidecar behavior: when the sidecar file does not exist, a fresh
`Sidecar(annotations=(), ledgers=(), shared_targets=())` is constructed
in memory; the file is written only if at least one row is produced.

**Sidecar path resolution:** for `<name>.md` the sidecar is
`<name>.anno.trig`, computed as `md_path.with_suffix(".anno.trig")`.
For `paper.v1.md` → `paper.v1.anno.trig`. (Do **not** use
`with_suffix("").with_suffix(".anno.trig")` — that strips an extra
suffix on multi-dotted names.)

---

## Source-version policy

Per-detector date-stamp constants in each source module:

```python
# annotation/sources/lint.py
DETECTOR_VERSIONS: dict[str, str] = {
    "bare-author-year": "v2026-05-11",
    "short-form-ids":   "v2026-05-11",
    "numeric-anchor":   "v2026-05-11",
}

def lint_source_name(short: str) -> str:
    return f"lint:{short}-{DETECTOR_VERSIONS[short]}"
```

```python
# annotation/sources/marker_token.py
TOKEN_SCANNER_VERSION = "phase-2"
TOKEN_SOURCE_NAME = "marker-scanner:phase-2"
```

Bumping a detector's `DETECTOR_VERSIONS` entry forces re-audit *for
that detector only* — clean sentences land as fresh rows under the new
source-version, while old rows (under the previous source-version
string) remain untouched. The two coexist in the sidecar; the
`prov:wasRevisionOf` chain is *not* invoked because these are
independent detector outputs, not status mutations of the same
finding. Operators who want to suppress the old rows do so via P3.3's
`dismiss` once it ships.

---

## Annotation-type mapping

| Source short name | `sci:annotationType` | `oa:motivatedBy` | Body |
|---|---|---|---|
| `marker-token` for `[UNVERIFIED]` | `unverified` | `oa:classifying` | `TextualBody`: "verifiable claim, not yet checked (lifted from `[UNVERIFIED]`)" |
| `marker-token` for `[MISSING_CITATION]` | `missing-citation` | `oa:classifying` | `TextualBody`: "claim needs source pointer (lifted from `[MISSING_CITATION]`)" |
| `marker-token` for `[SPECULATION]` | `speculation` | `oa:classifying` | `TextualBody`: "author conjecture / brainstorming (lifted from `[SPECULATION]`)" |
| `marker-token` for `[INACCESSIBLE]` | `inaccessible` | `oa:classifying` | `TextualBody`: "paywalled / image-only / private source (lifted from `[INACCESSIBLE]`)" |
| `bare-author-year` | `bare-author-year` | `oa:classifying` | `TextualBody`: `LintIssue.message` |
| `short-form-ids` | `short-form-ids` | `oa:classifying` | `TextualBody`: `LintIssue.message` |
| `numeric-anchor` | `numeric-anchor` | `oa:classifying` | `TextualBody`: `LintIssue.message` |

All written rows: `Status.OPEN`, `creator = actor`, `created = now`,
`content_hash = annotation.hash.content_hash(target.exact, source_name)`
(satisfying the P3.0 model invariant for `lint:` and `marker-scanner:`
sources). The hash is stored on every row even though P3.2 does not
yet read the audit ledger — P3.5's ledger work will use it directly,
no backfill required.

---

## Selector construction and `match_text`

### From a `LintIssue(line, col, message)`

The sentence containing position `(line, col)` is the **target**;
the specific token at `(line, col)` is the **match_text**.

Sentence boundaries: naive `re.split(r'(?<=[.!?])\s+', text)` over the
full file body — same heuristic flagged in spec open-question 1
(acceptable false-positive rate at this stage; revisit in a later
phase if drift becomes a problem).

```python
def build_lint_selector(
    file_text: str, line: int, col: int,
) -> tuple[TextQuoteSelector, str]:
    """Return (selector, match_text).

    selector.exact     = the sentence containing (line, col)
    selector.prefix    = up to 60 chars of preceding context, capped at file boundary
    selector.suffix    = up to 60 chars of following context, capped at file boundary
    match_text         = the specific substring at (line, col) — for
                         bare-author-year that's "Brunton 2022"; for
                         short-form-ids that's "h04"; for numeric-anchor
                         that's the matched numeric literal.
    """
```

Per-detector `match_text` extraction:

| Detector | `match_text` |
|---|---|
| `bare-author-year` | `f"{Author} {Year}"` (the captured `<name> <year>` pair) |
| `short-form-ids`   | the matched short ID literal (e.g., `"h04"`, `"Q1"`) |
| `numeric-anchor`   | the matched numeric literal (e.g., `"42%"`, `"3.14"`) |

**Implementation contract (normative):** P3.2 extends `LintIssue`
in `science_tool/prose_lint.py` with a required `match: str` field.
All four detectors (including the deferred `frontmatter-inline-gap`,
to keep the dataclass uniform) populate it:

| Detector | `match` value |
|---|---|
| `bare-author-year` | the matched `<Author> <Year>` literal (e.g., `"Brunton 2022"`) |
| `short-form-ids` | the matched short ID literal (e.g., `"h04"`, `"Q1"`) |
| `numeric-anchor` | the matched numeric literal (e.g., `"42%"`, `"3.14"`) |
| `frontmatter-inline-gap` | the missing `related:` ref string (e.g., `"hypothesis:h04-..."`) — populated for uniformity even though this detector is deferred from `audit` |

`LintIssue.match` is required (no default) so the type checker
catches any detector that forgets to populate it.

**Render impact on `science prose lint`:**

- **Table output** (`--format table`): unchanged. The renderer
  prints `line:col [check] (severity) message` and never references
  the new field.
- **JSON output** (`--format json`): the new field appears as an
  additional `"match"` key on every hit object, because the existing
  serializer uses `dataclasses.asdict(h)` (see
  `science_tool/prose_lint_cli.py`). This is treated as a deliberate
  additive change to the JSON schema — consumers that key into known
  fields are unaffected, consumers that do full-shape equality
  checks must accept the extra key. The spec explicitly endorses
  this rather than special-casing the serializer to omit it; the
  field carries useful diagnostic information for any external tool
  reading the output.

`LintSource.scan` reads `match` directly off the `LintIssue` — no
message parsing.

### From a `MarkerHit(line, token)`

The sentence containing the bracketed token is the target.
`match_text` is set to the bracketed token form (`"[UNVERIFIED]"`,
`"[MISSING_CITATION]"`, etc.) — same value as `lifted_from`.

For `--mirror` mode the token stays in the `exact` field (so the
sidecar selector resolves to the original prose). For `--remove`
mode, the sidecar is constructed using the *post-removal* sentence so
subsequent `science annotate verify` runs find an exact anchor in the
cleaned prose.

`lifted_from` is set to the literal token form (`"[UNVERIFIED]"`),
which is what `markers scan --ignore-lifted` matches against.

### Multiple findings in the same sentence

Two distinct findings (e.g., `Brunton 2022` and `Spivak 1999` both
flagged in one sentence) produce two `PlannedAnnotation` rows with
the same `target.exact` but different `match_text` → two distinct
4-tuples → two distinct base IDs → two rows.

Two identical findings (the same `Brunton 2022` matched twice in one
sentence by an over-eager regex) produce two `PlannedAnnotation` rows
with identical 4-tuples → the second is skipped by the dedupe. This
is the desired behavior: same finding = one row.

---

## `lift-tokens` semantics

```
science annotate lift-tokens --root <dir>
```

1. Walk `_collect_markdown_files(root)` (reuse the helper from
   `markers.py`).
2. **Mirror-mode flow:**
   1. For each `.md`, run `MarkerTokenSource.scan(md_path)` → planned
      rows whose selectors anchor to the **original** prose.
   2. Read the existing sidecar (or empty) at
      `md_path.with_suffix(".anno.trig")`.
   3. `merge_planned` for any non-duplicate rows; write the sidecar
      back if at least one new row was minted.
   4. Prose is unchanged.
3. **Remove-mode flow:**
   1. Pre-flight clean-tree guard. Compute the set of `.md` files
      that contain at least one non-documentation `MarkerHit`. For
      each, check `git status --porcelain`. If any is dirty, refuse
      with a clear error unless `--force-dirty`. (Consistent with
      P3.1's `verify --apply` guard.)
   2. For each `.md` in the set:
      1. Read the original text and the existing sidecar (or empty).
      2. Run `markers.scan_text(file, original_text, ...)` to collect
         the **original** non-documentation `MarkerHit` list — the
         tokens are still present, so the regex matches.
      3. Compute the post-removal text by stripping each
         non-documentation bracketed token plus any
         immediately-adjacent whitespace (preserve backticked /
         fenced occurrences). Reuse `markers_cli._rewrite_*` helpers
         where applicable.
      4. For each original `MarkerHit`, build a `PlannedAnnotation`
         whose selector anchors to the **post-removal** sentence:
         locate the sentence in the cleaned text that corresponds to
         the hit's original line (i.e., the sentence that previously
         contained the bracketed token, now with the token + adjacent
         whitespace removed). `match_text` and `lifted_from` retain
         the bracketed token literal (`"[UNVERIFIED]"`); only the
         selector's `exact`/`prefix`/`suffix` fields use cleaned text.
      5. `merge_planned` in memory for the planned rows.
      6. Write the **sidecar first**, then the **prose**. Both
         writes use temp-file + `os.replace` for crash-safety on the
         single-file level (POSIX `os.replace` is atomic).

   Key invariant: hits are gathered from the **original** prose, but
   selectors anchor to the **cleaned** prose. Scanning the cleaned
   text directly would yield zero hits.

   **Write-order rationale and crash-safety contract:**

   This is two writes to two files, so it is not transactional
   across both. The order is chosen so partial-failure states are
   *forward-recoverable* by re-running `lift-tokens --remove`:

   - **Sidecar fails (prose unchanged):** no harm. Re-run repeats
     from step 1 with the original tokens still in place.
   - **Sidecar succeeds, prose write fails:** the sidecar carries
     rows whose selectors anchor to cleaned text, but the on-disk
     prose still has tokens. `science annotate verify` will report
     these rows as `degraded` or `superseded`. Re-running
     `lift-tokens --remove` is safe: `merge_planned`'s dedupe
     skips the existing rows (matching 4-tuple, status `OPEN`); the
     prose-rewrite step strips the tokens; selectors then resolve
     cleanly.
   - **Both succeed:** the steady state.

   The reverse order (prose first, then sidecar) is *not*
   recoverable: a sidecar-write failure leaves cleaned prose with
   no annotation rows, and a re-run finds zero `MarkerHit`s in the
   cleaned text — the rows are permanently lost. The chosen order
   trades a transient verify-warning state for guaranteed
   recoverability.

   Sentence-correspondence helper:

   ```python
   def cleaned_sentence_for_hit(
       cleaned_text: str, original_text: str, hit_line: int,
   ) -> tuple[int, int]:
       """Return (start, end) char range in cleaned_text of the sentence
       that corresponds to the sentence containing hit_line in original_text.

       Implementation: split original_text into sentences (same naive
       segmentation as build_lint_selector). Find the sentence whose
       line range covers hit_line. The cleaned-text counterpart is the
       sentence at the same ordinal position in
       split_sentences(cleaned_text) — the strip preserves sentence
       boundaries because it removes only `[TOKEN]` literals, not
       sentence-terminating punctuation."""
   ```
4. Report (table or JSON):
   - Per file: count of rows written, count of inline tokens removed
     (only `--remove`), count of skipped duplicates.
   - Summary totals at the bottom.

JSON output shape:

```json
{
  "summary": {
    "files_scanned": 42,
    "rows_written": 17,
    "tokens_removed": 17,
    "duplicates_skipped": 3,
    "files_with_writes": 9
  },
  "files": [
    {"path": "doc/example.md", "rows_written": 2, "tokens_removed": 2, "duplicates_skipped": 0},
    ...
  ]
}
```

Exit 1 on parse errors, write failures, or dirty-tree guard refusal.
Otherwise 0, regardless of how many rows were written.

---

## `audit` semantics

```
science annotate audit --root <dir> [--source <name> ...] [--dry-run]
```

1. Resolve sources: if `--source` not given, use `LINT_SOURCES`. If
   given, validate each name against `SOURCES` (reject unknowns).
   `--no-llm` is silently ignored in P3.2.
2. Walk `_collect_markdown_files(root)` (reuse the prose-lint helper).
3. For each `.md`, for each source in resolved set:
   - Call `source.scan(md_path)` → `Iterable[PlannedAnnotation]`.
   - Accumulate per-file plan.
4. `--dry-run`: emit the per-file plan (table or JSON), exit 0.
   Otherwise, for each `.md` with any planned rows, call
   `audit_file` to merge + write the sidecar.
5. Report similar shape to `lift-tokens`:

```json
{
  "summary": {
    "files_scanned": 42,
    "rows_written": 28,
    "duplicates_skipped": 14,
    "files_with_writes": 11,
    "sources_run": ["lint:bare-author-year-v2026-05-11", ...]
  },
  "files": [
    {"path": "doc/example.md", "rows_written": {"bare-author-year": 2, "short-form-ids": 1}, "duplicates_skipped": 0},
    ...
  ]
}
```

Per-file `rows_written` is a dict keyed by short source name (not full
source-version) for table-rendering brevity; the full source-version
appears once in `summary.sources_run`.

Exit 1 on parse errors, write failures, or unknown source names.

---

## Section 8 dedupe: `markers scan --ignore-lifted`

### Flag semantics

`science markers scan --ignore-lifted` post-filters `scan_markers`
output. For each `MarkerHit`:

1. Locate the candidate sidecar: `hit.file.with_suffix(".anno.trig")`
   for `<name>.md` → `<name>.anno.trig` (and
   `paper.v1.md` → `paper.v1.anno.trig`). Same rule as the audit
   path resolution in "Module layout".
2. If the sidecar does not exist: keep the hit (no skip).
3. If the sidecar exists, load it (cached per-file across the
   scan). Skip the hit if any annotation matches all of:
   - `source == "marker-scanner:phase-2"`
   - `lifted_from == f"[{hit.token}]"`
   - the annotation's target selector resolves (per the P3.1 selector
     algorithm) to a `(start, end)` character range whose containing
     line range — computed against `source_text.splitlines(keepends=True)`
     — includes `hit.line`. Resolution status `SUPERSEDED` is treated as
     "no skip" (the row no longer locates the prose, so the inline
     token should still be reported).

Sidecar parse errors → log a warning to stderr, do not skip (fail
open: under-skip is safer than over-skip when the dedupe state is
broken).

### `validate.sh` Section 8 update

```bash
# ─── 8. Unresolved annotation markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

if command -v science >/dev/null 2>&1 && [ -d "$DOC_DIR" ]; then
    SCIENCE_MARKERS_FLAGS=(--ignore-lifted)   # NEW
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_MARKERS_FLAGS+=("--strict")
    fi
    markers_json=$(science markers scan --root . --format json "${SCIENCE_MARKERS_FLAGS[@]}" 2>/dev/null) || true
    if [ -z "$markers_json" ]; then
        markers_json='{"counts":{},"hits":[]}'
    fi
    # ... existing parsing logic unchanged ...
fi
```

The fallback-on-empty + `|| true` capture pattern matches P3.1's
Section 19 (avoids the concatenation bug from the P3.1 review pass).

### Managed-artifact bump

`science/src/science_tool/project_artifacts/registry.yaml`:

- `version: '2026.05.11.2'` (was `2026.05.11.1`)
- `current_hash`: recomputed `body_hash` of the new `validate.sh`
- Old `body_hash` `171dada6...` prepended to `previous_hashes`
- New migration entry from `2026.05.11.1` → `2026.05.11.2`
- New changelog entry: "Section 8 markers scan now passes
  `--ignore-lifted` to dedupe inline tokens against lifted sidecar
  rows."

---

## Testing strategy

Mirrors P3.1's pattern: pure-function unit tests on the source
adapters + acceptance tests on CLI behavior + idempotence tests on the
merge.

### New test files

| File | What it covers | Approx tests |
|---|---|---|
| `tests/test_annotation_model_match_text.py` | New `Annotation.match_text` field default; `sci:matchText` round-trip via `write_sidecar`/`read_sidecar`; legacy sidecar (no predicate) reads back as `None`; field appears next to `sci:liftedFrom` in emission. | 4 |
| `tests/test_annotation_sources_lint.py` | Each `LintSource` (3 of them) produces correct `PlannedAnnotation` from a fixture .md (selector, type, body, `source_name` with version, `match_text` extraction from new `LintIssue.match` field); two distinct findings in one sentence → two rows; identical findings collapse to one. | 9 |
| `tests/test_prose_lint_match_field.py` | All 4 detectors set `LintIssue.match` correctly per the type table; the field is required (constructing a `LintIssue` without it errors); existing `prose lint` rendering unaffected. | 5 |
| `tests/test_annotation_sources_marker_token.py` | Each token type → correct `PlannedAnnotation`; `lifted_from` and `match_text` set to bracketed literal; documentation/fenced tokens skipped; legacy aliases handled; mirror vs remove selector text differs. | 7 |
| `tests/test_annotation_audit_merge.py` | Empty sidecar → N rows; clean re-run → 0 new rows; ack/dismiss/fix rows preserved; superseded same-tuple row → re-run mints `<base>-2`; non-superseded same-tuple row → dedupe (no mint, no error); fabricated cross-tuple `base_id` collision → `IdCollisionError` raised; planned-vs-planned collision in one merge call also raises; mint_base_id determinism on the 4-tuple; single-source invariant in `merge_planned` enforced; `content_hash` computed correctly on every written row. | 11 |
| `tests/test_annotate_audit_cli.py` | `--source` filtering, repeat, unknown rejection; default set is `LINT_SOURCES`; `marker-token` accepted as advanced; `frontmatter-inline-gap` rejected (deferred); `--dry-run` no writes; `--format json` shape; `--actor` recorded as `creator`; exit codes; `--no-llm` no-op. | 10 |
| `tests/test_annotate_lift_tokens_cli.py` | `--mirror` writes sidecar, prose unchanged, selector anchors to original; `--remove` writes sidecar before prose, each via temp+os.replace (per-file atomic, not cross-file transactional), selector anchors to cleaned prose; clean-tree guard refuses on dirty; `--force-dirty` overrides; idempotent re-run from steady state; recoverable re-run from "sidecar written, prose write failed" simulated state; multi-dotted name (`paper.v1.md`) sidecar path correct. | 9 |
| `tests/test_markers_scan_ignore_lifted.py` | Flag skips lifted hits; absent sidecar → no skip; non-matching `lifted_from` → no skip; sidecar parse error → log + no skip; selector-resolution cross-check (line containment); SUPERSEDED row → no skip. | 7 |
| `tests/test_validate_sh_section_8.py` | Managed-artifact integrity (version, current_hash, migrations, previous_hashes); smoke-test invocation against `mktemp -d` fixture; `--ignore-lifted` actually appears in the command line via `set -x` capture. | 4 |

Estimated **~66 new tests** in green-field files. Two existing test
suites need touch-ups (additive, no behavior change):

- `tests/test_prose_lint.py` — every existing `LintIssue(...)`
  construction needs the new required `match=` argument. Mechanical
  edit covered by the corresponding task in the implementation plan.
- Tests under `tests/test_annotation_io*.py` (P3.0) — add coverage
  for the new `sci:matchText` predicate. Existing behavioral
  assertions (round-trip equality on rows that lack `match_text`,
  parser tolerance of unknown predicates, etc.) should remain green
  because the field is optional and defaults to `None`. Any
  golden-output / full-file fixture assertions need their expected
  text updated **only** when the fixture exercises a row whose
  `match_text` is non-`None` — those new fixtures land alongside
  the new tests and are authored with `sci:matchText` in their
  expected output from the start.

### New fixtures under `science/tests/_fixtures/annotation/audit/`

- `bare-author-year.md` — sentences with and without `[@key]`
  adjacency; one sentence with two distinct mentions to exercise
  per-finding identity.
- `short-form-ids.md` — bare and canonical-prefixed forms.
- `numeric-anchor.md` — claims with and without anchor patterns in
  paragraph.
- `mixed-tokens.md` — all four phase-2 tokens, some inside backticks.
- `clean-after-remove.md` — pre-existing fixture for the `--remove`
  selector path; ships next to a `.expected.md` showing the
  post-removal text.
- `paper.v1.md` — multi-dotted name to exercise the
  `with_suffix(".anno.trig")` path rule.

---

## Out of scope reminders (for the P3.3+ author)

These were intentionally deferred during P3.2 brainstorming. Listing
them here so they don't get re-discovered as gaps.

1. **`prose lint` deprecation.** After P3.4 ships render+list, point
   `science prose lint` at `science annotate list --source 'lint:*'`
   and add a deprecation banner. Mass-rewrite of existing scripts
   that consume `prose lint --format json` happens in that follow-up.
2. **Body promotion.** `bare-author-year` → `cites` row with a bib-IRI
   body; `short-form-ids` → `entity-mention` row with the resolved
   entity IRI. Requires a bib/entity resolver pass; out of scope for
   the mechanical-lint write path.
3. **`--since <git-ref>` for audit.** Per-paragraph git-diff to skip
   unchanged sentences. Likely lands alongside or after P3.5 when LLM
   call cost makes it worth the plumbing.
4. **Ledger usage for lints.** P3.2 deduplicates by row-existence;
   if re-audit cost becomes meaningful (very large repos), the
   ledger's `(content_hash, source_version)` cache can be wired in
   without changing the sidecar schema.
5. **Sentence segmentation upgrade.** Replace naive `re.split(r'(?<=[.!?])\s+')`
   with pysbd / spaCy if false-positive rate becomes a problem.
6. **Body promotion for marker tokens.** None planned — the
   `unverified` / `missing-citation` / `speculation` / `inaccessible`
   types stay textual; their value is the type tag, not the body.
7. **`frontmatter-inline-gap` lift.** Needs a frontmatter-aware
   selector (likely `oa:FragmentSelector` against a YAML JSONPointer
   anchor, or a prose selector that locates the literal `related:`
   block in frontmatter). Lands in a follow-up. `science prose lint
   --check frontmatter-inline-gap` continues to surface the finding
   in the meantime.

---

## Acceptance criteria (end-to-end smokes)

After P3.2 lands, the following must work on `main`:

1. **`science annotate lift-tokens --root <fixture>` (mirror mode)**
   over a fixture with three `[UNVERIFIED]` and two `[MISSING_CITATION]`
   tokens writes a sidecar with 5 rows; re-running writes 0 new rows;
   running `science annotate verify --root <fixture>` reports 5 ok
   annotations.
2. **`science annotate lift-tokens --root <fixture> --remove`** on a
   clean copy of the same fixture writes 5 rows AND strips 5 inline
   tokens; `science annotate verify` still reports 5 ok (selectors
   constructed against post-removal prose).
3. **`science annotate audit --root <fixture>`** over a fixture
   triggering each of the three in-scope lint detectors writes the
   expected per-detector row counts; re-running with no changes
   writes 0 new rows; manually editing one row's status to
   `dismissed` (via direct sidecar edit in P3.2; via CLI in P3.3+)
   and re-running preserves the dismissal verbatim. A sentence with
   two distinct findings yields two separate rows with distinct IDs.
   A row mutated to `superseded` by `verify --apply` (from P3.1)
   does not block a fresh `open` row at the same selector on
   re-audit; the new row lands at `<base_id>-2`.
4. **`science markers scan --ignore-lifted`** over the fixture from (1)
   reports zero hits for the lifted token types, while plain
   `science markers scan` still reports them.
5. **`validate.sh`** in `--verbose` mode shows `--ignore-lifted` in
   the markers-scan invocation; the `science init` flow reproduces
   the bumped version (`2026.05.11.2`) and matching `body_hash`.
6. **`uv run pytest`** passes with the ~66 new tests added; total
   suite count rises by that amount; no existing test regresses.

---

## Cross-references

- `plan:2026-05-10-annotation-system-spec` — parent spec; §"Migration
  from phase 2" defines the lift semantics; §"CLI surface" defines
  `audit` and `lift-tokens`.
- `plan:2026-05-11-annotation-system-p3.0` — data model + io.py;
  `Sidecar`, `Annotation`, `write_sidecar`, `Status` consumed here.
- `plan:2026-05-11-annotation-system-p3.1` — `science annotate verify`;
  P3.2 must not break verify's drift-detection contract on rows it
  writes (acceptance criterion 1).
- `docs/conventions/annotation-tokens.md` — token vocabulary used by
  `marker-token` source.
- `docs/conventions/prose-lints.md` — lint catalog used by `lint`
  source. P3.2 does not modify this doc; long-term deprecation note
  lands in a follow-up.

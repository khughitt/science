# Entity-ref citations as numeric-anchor anchors — design

**Status:** rev 3 (2026-07-19) — pending review
**Scope:** `numeric-anchor` prose lint (Part A engine). Single subsystem.
**Origin:** pan-disease t108. Surfaced while dogfooding numeric-provenance on
pan-disease: some residual numeric-anchor findings are numbers whose paragraph
cites a resolvable **provenance-bearing** typed entity-ref (an
`interpretation:…`, `pre-registration:…`, `plan:…`) yet flag because the
detector cannot see typed entity-refs as provenance.

## Problem

`numeric-anchor` classifies a prose numeric claim as grounded when its
paragraph carries a resolvable body reference. The extraction regex
`_BODY_REF_RE` (`numeric_provenance.py`) recognizes only `task:tNNN`,
`[@bibkey]`, `cite:bibkey`, `dataset:slug`, and `[[wiki]]` (topical — not a
candidate). Typed entity-refs — the dominant in-prose citation convention —
are invisible, so a number whose only nearby provenance is
`` `interpretation:0011-h01-a2-bc2-tissue-confound` `` flags as `Unanchored`.

The resolver already resolves typed refs (`ResolutionIndex.resolve` routes any
`_TYPED_REF_RE` match to `entity_ids` membership). The gap is **extraction**
plus **short-prefix resolution** (citations appear as both full ids and bare
`interpretation:0013` prefixes).

### Existence is not provenance (the load-bearing distinction)

Recognizing *any* resolvable entity-ref as an anchor would mask real findings.
Measured citation kinds within ±3 lines of a pan-disease numeric-anchor hit:

| kind | hits nearby | provenance-bearing? |
|---|---|---|
| hypothesis | 21 | no — topical/framing |
| question | 21 | no — topical/framing |
| interpretation | 9 | yes |
| plan | 3 | yes (registered/planned params) |
| probe | 1 | yes, but project-local (unindexed) |
| discussion | 1 | no — topical |
| pre-registration | 1 | yes |

A `hypothesis:` or `question:` citation next to a number is topical adjacency,
not the number's source. Anchoring on those would silently clear ~34 findings
that must stay flagged. `EntityClass` cannot serve as the filter either:
`interpretation` is `EPISTEMIC` alongside `hypothesis`, so that axis (belief
propagation) does not separate provenance from framing. The distinction must be
an **explicit, curated allowlist of provenance-bearing kinds.**

### Measured impact (pan-disease, 2026-07-19)

- Residual numeric-anchor after the t107 config migration: **196**.
- Numbers whose paragraph cites a **provenance-bearing** entity-ref:
  interpretation (9) + plan (3) + pre-registration (1) ≈ **13** legitimately
  anchor. The ~34 hypothesis/question-adjacent numbers **stay flagged** — the
  correct, non-masking outcome.
- Citation forms across affected files: 545 full-id (with slug), 58 short
  numeric-only prefixes. Both must resolve.

## Non-goals

- No change to `additional_anchor_patterns` / `anchor_patterns` (weak regex-only
  suppression); this routes through existence-checked resolution instead.
- No anchoring on topical/framing kinds (hypothesis, question, topic, theme,
  concept, discussion, assumption, story, inquiry, falsification, mechanism,
  method, model, proposition, meta).
- No support for project-local kinds not in the shared index (`probe`,
  `review`); the shared entity index only carries built-in kinds. Documented as
  a follow-up.
- No change to Part B (`numeric-verification`), the graph, or the shared
  refs-integrity semantics beyond the one-kind index correction below.

## Design

Changes span `numeric_provenance.py` (extraction, resolution), `refs.py` (one
missing kind), and the detector-version registry.

### 1. Provenance-bearing anchor allowlist

A new module constant in `numeric_provenance.py`:

```python
_ANCHOR_ENTITY_KINDS = frozenset({
    # result / evidence artifacts produced by project work
    "interpretation", "report", "synthesis", "observation", "finding",
    "evidence-line", "validation-report", "experiment", "workflow-run",
    "data-package",
    # external sources
    "dataset", "paper", "book", "source",
    # registered / planned parameters
    "pre-registration", "plan",
})
```

`task:` (via `task_numbers`) and `cite:`/`[@]` (via `bib_keys`) remain anchors
through their existing alternatives — they are provenance too. Topical entity
kinds are simply absent from every alternative, so they are never extracted,
never become candidates, and cannot anchor. The extraction allowlist **is** the
provenance gate.

### 2. Extraction — one added, boundary-guarded alternative in `_BODY_REF_RE`

Append a single alternative built from the allowlist (kinds sorted
longest-first so hyphenated names win over prefixes):

```
(?<![A-Za-z0-9_.:/@-])(interpretation|validation-report|pre-registration|…):([0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?)(?![A-Za-z0-9_:/@-])
```

Existing alternatives are untouched (additive), so current extraction is
byte-identical. Boundary guards:

- Left `(?<![A-Za-z0-9_.:/@-])` — rejects an id embedded in a larger token:
  `x_interpretation:0013`, `x-interpretation:0013`, `foo.plan:1`,
  `path/interpretation:0013`, `a:interpretation:0013`.
- Explicit kind alternation — only allowlisted kinds match; `hypothesis:` etc.
  never match.
- id charset `[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?` — an alnum start, an
  **alnum terminal**, and internal `. _ -`. This matches the `_VERBATIM_RE` id
  policy (entities.py:193) so legal dotted ids extract
  (`paper:Volker2023.source`, allowlisted `paper`), while the required alnum
  terminal keeps a trailing sentence period outside the match
  (`interpretation:0013.` captures `interpretation:0013`).
- Right `(?![A-Za-z0-9_:/@-])` — rejects `interpretation:0013@host`,
  `interpretation:0013/x`, `interpretation:0013:extra`.

An allowlisted kind that resolves to nothing (typo, fabrication) stays an
*unresolved* candidate — it never anchors and never emits a finding.

### 3. Short-prefix resolution with ambiguity handling

Add `entity_prefix_owners: dict[str, int]` to `ResolutionIndex`, built in
`build_resolution_index` like the big-picture validator's `_index_by_prefix`
(validator.py:125) **but restricted to digit-only leads**: for each canonical
id `<kind>:<lead>-<rest>`, count owners of `<kind>:<lead>` **only when
`lead.isdigit()`**. The short-form convention is `<kind>:<NNNN>`
(`_NUMERIC_LOCAL_PART_RE`, entities.py); non-numbered ids (`dataset:cptac-…`,
`paper:Volker2023.source`) have no short prefix form. In `resolve()`'s
typed-ref branch:

```python
if _TYPED_REF_RE.match(ref):
    if ref in self.entity_ids:          # exact full-id
        return True
    return self.entity_prefix_owners.get(ref, 0) == 1   # unique numeric prefix only
```

Restricting to digit leads closes a masking hole: `dataset:cptac` must **not**
resolve to a unique `dataset:cptac-gbm-2021-proteogenomics` when no
`dataset:cptac` entity exists — a non-numeric lead is never a valid short form,
so it is never indexed and the claim stays flagged. A numeric prefix with
**two or more** owners also does not resolve (fail-closed), mirroring the
validator's contract ("an AMBIGUOUS prefix is a LOUDER failure"). Full-id refs
keep resolving by exact membership.

### 4. Index correction — add `plan` to `_LOCAL_ENTITY_KINDS`

`_LOCAL_ENTITY_KINDS` (refs.py:85) is a hardcoded snapshot that omits `plan`, a
core kind (`science_model/profiles/core.py`), so `plan:*` ids are never indexed
and `plan:0023` cannot resolve. Add `"plan"`. All other allowlisted kinds are
already present. This also lets the shared body-prose ref scanner
(`_TYPED_ENTITY_REF_RE`) validate `plan:` refs — a correct broadening. Full
reconciliation of `_LOCAL_ENTITY_KINDS` with the authoritative registry
(`markdown_entity_kinds`) is a separate follow-up, not attempted here.

### 5. Detector-version bump

`numeric-anchor` output changes materially, and annotation persistence /
audit ledgers key findings by `DETECTOR_VERSIONS["numeric-anchor"]`
(annotation/sources/lint.py:34). Bump `v2026-07-18b → v2026-07-19` and update
its contract test, so re-keyed findings are not mistaken for previously-audited
output under the old behavior.

### 6. `local_candidates_for_paragraph` — no logic change

It consumes the broadened `_BODY_REF_RE` and existence-checks each ref via the
prefix-aware `resolve()`, exactly as it does today. Still skips `[[wiki]]`.

## Safety invariant ("don't mask")

Three independent gates, all required for a number to anchor on an entity-ref:
(1) the citation's kind is in the provenance allowlist (extraction); (2) the
ref resolves against the real entity index — exact id or **unique** prefix
(existence + non-ambiguity); (3) the ref token is not a substring of a larger
token (boundary guards). A fabricated ref, a topical kind, or an ambiguous
prefix all leave the number `Unanchored`.

## Testing (`tests/test_numeric_provenance.py`, unless noted)

Positives:
- Full-id provenance ref (`interpretation:0007-h01-…`) → resolved candidate.
- Short unique numeric-prefix ref (`interpretation:0013`) → resolved via prefix
  owners.
- Dotted verbatim id (`paper:Volker2023.source`) → extracts and, when the
  entity exists, resolves.
- End-to-end: a number in a paragraph citing a resolvable `interpretation:NNNN`
  classifies as `Anchored`.
- `plan:NNNN` resolves after the index correction.

Negatives (the anti-masking core):
- Topical kind: a number whose only citation is a **real** `hypothesis:NNNN`
  (or `question:NNNN`) stays `Unanchored`.
- Numeric-prefix ambiguity: a numeric prefix owned by two entities does not
  resolve; the claim stays `Unanchored`.
- Non-numeric prefix: a **unique** non-numeric prefix (`dataset:cptac` with only
  `dataset:cptac-gbm-2021-proteogenomics` present) does **not** resolve.
- Embedded token, left: `x_interpretation:0013`, `x-interpretation:0013`,
  `path/interpretation:0013` do not yield a resolvable `interpretation:0013`.
- Embedded token, right: `interpretation:0013@host`, `interpretation:0013/p`.
- Fabricated: `interpretation:9999` extracts but is `unresolved`.

Regression / contract:
- Existing extraction/resolution/word-boundary/wiki-link/`config/`-path tests
  stay green unchanged.
- Detector-version contract test updated to `v2026-07-19`
  (`test_annotation_lint_source_numeric.py`).
- `test_refs.py` contract test: with `plan` now indexed, a known `plan:NNNN-…`
  reference resolves and a nonexistent `plan:9999` does not — pinning the
  intended refs-integrity broadening.
- `ruff check`, `pyright`, full `pytest` from `science/`.

## Acceptance (pan-disease)

Overlay the worktree science (`uv run --with-editable <worktree>/science`) and
run `science prose lint --check numeric-anchor`. Expect:

- ~13 provenance-cited numbers clear (interpretation/plan/pre-registration),
  including pre-reg 0012's values cited via `interpretation:0010/0011`.
- hypothesis/question/discussion-adjacent numbers **remain flagged**.
- **No unexpected deltas.** The `plan` index addition intentionally broadens
  refs-integrity, so record the expected refs delta (any newly-validated or
  newly-flagged `plan:` references) rather than asserting counts are unchanged;
  every other check's counts must be unchanged.

## Docs

`docs/conventions/prose-lints.md` numeric-anchor section: resolvable
**provenance-bearing** typed entity-ref citations (list the kinds; both full-id
and unique short-prefix forms) count as paragraph anchors; topical kinds
(hypothesis, question, topic, …) explicitly do not, and an ambiguous prefix
does not resolve.

## Files

- `src/science_tool/numeric_provenance.py` — `_ANCHOR_ENTITY_KINDS`,
  `_BODY_REF_RE`, `ResolutionIndex` (+ `entity_prefix_owners`),
  `build_resolution_index`, `resolve`.
- `src/science_tool/refs.py` — add `"plan"` to `_LOCAL_ENTITY_KINDS`.
- `src/science_tool/annotation/sources/lint.py` — bump
  `DETECTOR_VERSIONS["numeric-anchor"]`.
- `tests/test_numeric_provenance.py` — positives (incl. dotted id), negatives
  (topical, numeric-prefix ambiguity, non-numeric prefix, embedded tokens,
  fabricated), boundaries; confirm existing green.
- `tests/test_annotation_lint_source_numeric.py` — update the expected
  `v2026-07-18b → v2026-07-19` (lines 12–13).
- `tests/test_refs.py` — contract test for known + nonexistent `plan:` refs.
- `docs/conventions/prose-lints.md` — one paragraph.

## Out of scope / follow-ups

- Project-local provenance kinds (`probe`, `review`) are not in the shared
  entity index and will not anchor; needs index reconciliation with the
  project-local kind registry.
- Full reconciliation of `_LOCAL_ENTITY_KINDS` with `markdown_entity_kinds`.

---
id: "plan:2026-05-10-annotation-system-spec"
type: "plan"
title: "Sub-document annotation system — phase-3 spec (full sidecar + W3C-aligned data model)"
status: "draft"
created: "2026-05-10"
updated: "2026-05-11"
supersedes_section_of: "plan:2026-05-09-annotation-system-stub#phase-3"
---

## Status

Draft RFC. Supersedes the "Phase 3 — full sub-document annotation system
(deferred RFC)" section of `plan:2026-05-09-annotation-system-stub`.
That stub remains the source of truth for phase 2 (inline-token vocabulary
split + shared scanner). This document is the long-form design for the
phase-3 system that phase 2 was forward-compatible with.

## Motivation

The natural-systems t466 citation-audit pilot identified six recurring
prose-quality gaps. Four are mechanically detectable and shipped as
`science prose lint` (bare-author-year, short-form-ids,
frontmatter-inline-gap, numeric-anchor). The remaining two require LLM
judgment — most notably **gap D (field-state / consensus claims
unsupported)**: strong claims about the field with no source and no
explicit missing-citation marker.

Adding a one-off LLM detector for gap D would address the immediate need
but reproduce a problem the project has already paid for elsewhere: a
proliferation of single-purpose annotation surfaces (inline tokens,
`science markers`, `science prose lint`, frontmatter `related:`, body-text
typed refs in `science refs check`) each with its own data model, storage
shape, and severity contract. None of them compose; none of them scale to
"highlight this arbitrary span and attach a comment."

The right move is to define a single annotation primitive that subsumes
all of these as special cases, then build the gap-D detector (and future
detectors) as one source within that primitive.

## Vision (one paragraph)

> Prose stays clean. Every annotation — LLM-audit verdict, human comment,
> mechanical lint hit, named-entity link, citation suggestion, inline
> token — is one row in a sidecar TriG file using the W3C Web Annotation
> Data Model. Span addressing uses `oa:TextQuoteSelector` (quoted text
> plus prefix/suffix context), so coordinates survive most prose edits
> and fail cleanly when the quoted text vanishes. Annotations have
> typed bodies, sources, statuses, and content-hash cache keys. Multiple
> annotations per span fall out naturally (each is an independent row
> sharing a target). Re-audit only fires on changed sentences. The
> existing graph backbone (`knowledge/graph.trig`) ingests annotations
> as first-class entities with the existing freshness machinery. CLI
> renders the unified view; the `~/d/dashboard` consumer reads the same
> TriG.

## Non-goals

- Dashboard UI design (downstream consumer; designed separately).
- Annotations on non-markdown sources (PDFs, code files, notebooks).
  Code-file metadata blocks (NS t465) remain a separate convention.
- Multi-author conflict resolution beyond what git already provides.
- Annotation-of-annotation threading (replies). Deferred until demand.
- Cross-entity annotations (sentence-in-A links sentence-in-B). The data
  model permits it via `oa:hasTarget` IRIs, but no CLI / render support
  in v1.
- Replacing `knowledge/graph.trig`'s entity-level metadata. Annotations
  attach *to spans of prose within entities*; entity-level metadata
  stays where it is.

## Data model

### Surface form

A single annotation type, `oa:Annotation`, with these fields:

| Predicate | Required | Range | Purpose |
|---|---|---|---|
| `oa:hasTarget` | yes | `oa:SpecificResource` (named or blank node) bearing `oa:hasSource` IRI + `oa:hasSelector` | What is being annotated |
| `oa:hasBody` | yes (≥1) | named or blank node (text body or typed-ref IRI); multiple bodies permitted | The annotation content |
| `oa:motivatedBy` | yes | one of `oa:commenting`, `oa:tagging`, `oa:classifying`, `oa:linking`, `oa:questioning`, `oa:identifying`, `oa:highlighting` | Standard W3C motivation vocabulary |
| `sci:annotationType` | yes | string literal from the project vocabulary | Project-specific narrower kind |
| `sci:source` | yes | string literal `<kind>:<version>` | What produced this row |
| `sci:status` | yes | `open` \| `ack` \| `fixed` \| `superseded` \| `dismissed` | Mutable disposition (see Status lifecycle) |
| `sci:contentHash` | conditional | string `"sha256:..."` | Required for `audit:` and `lint:` sources; optional/absent for `human:` and free-form `comment` rows |
| `dc:creator` | yes | string | Producing agent (model ID, git author, lint name) |
| `dc:created` | yes | xsd:dateTime | When this row was written |
| `dc:modified` | conditional | xsd:dateTime | Required when `sci:status` has been mutated since creation |

`sci:source` value format: `<kind>:<version>` — e.g.,
`llm-audit:gap-d-v1`, `human:keith.hughitt@gmail.com`,
`lint:bare-author-year`. The version part is what changes when prompts
or detector logic change, invalidating the content-hash cache. `human:`
and free-form `comment` sources have no meaningful version (they're
authored, not generated); convention is `human:<email>` with no version
suffix.

**Namespaces.** The `sci:` namespace is `http://example.org/science/vocab/`
(matching `science_tool/graph/io.py:SCI_NS`). All sidecar files MUST use
this binding so triples join cleanly with the canonical graph; using
any other URI for `sci:` is a build error.

### Span addressing

Use `oa:TextQuoteSelector` exclusively in v1. Character offsets are not
permitted as a primary selector (too brittle).

```turtle
oa:hasSelector [
  a oa:TextQuoteSelector ;
  oa:exact "category theory is the right framework" ;
  oa:prefix "...has been argued repeatedly that " ;
  oa:suffix " for reasoning across model classes..."
] ;
```

**Prefix/suffix length policy.** Default to 60 characters of context on
each side, computed as the substring of the source markdown after
frontmatter stripping. Trim to a word boundary. Rationale: long enough
to disambiguate when the same `exact` string appears multiple times in
a document; short enough that minor edits to surrounding prose don't
invalidate the selector.

**Resolution algorithm** (read-time). Each step must produce a *unique*
match to succeed; ambiguity falls through to the next step or to
failure, never to a guess.

1. **Anchored exact**: find `prefix + exact + suffix` as a literal
   substring. If exactly one occurrence → match. If multiple → fall
   through (the prefix/suffix didn't disambiguate; this should not
   happen with the 60-char default but is possible for short repeated
   passages).
2. **Bare exact**: find `exact` as a literal substring. If exactly one
   occurrence → match with `selector-degraded` flag. If multiple →
   try `prefix + exact` and `exact + suffix` independently; pick the
   side that yields a unique match. If both fail to disambiguate →
   fall through.
3. **Fuzzy**: compute Levenshtein-distance scores between `exact` and
   every same-length window in the source text. Accept the best score
   only if (a) it is ≤ 5% of `len(exact)` and (b) the second-best score
   is at least 2× the best score (clear-margin requirement). Match
   with `selector-fuzzy` flag.
4. **No qualifying match** → mark the annotation `sci:status
   "superseded"` and emit a `science annotate verify` warning.

This degrades gracefully and never silently corrupts: ambiguous matches
fall through rather than guessing; a never-matched selector becomes
visible as a verify warning, not a phantom annotation floating on the
wrong text.

**Multi-line spans.** `oa:exact` can contain newlines. Highlighter-style
arbitrary regions span multiple sentences/paragraphs by quoting the full
contiguous text.

### Body types

```turtle
# Text body (free comment, suggestion, justification)
oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "..." ]

# Typed entity reference (linking to a project entity)
oa:hasBody <#task-t466>            # IRI form for in-graph entities
oa:hasBody <doi:10.1038/...>       # External DOI
oa:hasBody <bib:brunton-2022>      # Bibtex key (resolved against papers/references.bib)
```

A single annotation can have multiple bodies (e.g., a textual
explanation *plus* a suggested citation IRI).

### Skolemization for graph ingest

Sidecar files MAY use blank nodes for compactness (target/selector/body
written inline as `[ ... ]`). The canonical graph writer
(`science_tool/graph/io.py:save_canonical_graph_dataset`) rejects all
blank nodes via `_assert_no_blank_nodes`, so the ingest step (P3.6)
MUST skolemize every blank node before merge.

Skolemization rule (deterministic, stable across runs):

| Blank node role | Skolemized IRI |
|---|---|
| `oa:hasTarget` of annotation `<id>` | `<id>/target` |
| `oa:hasSelector` inside that target | `<id>/target/selector` |
| `oa:hasBody` of annotation `<id>` (1st body) | `<id>/body` |
| `oa:hasBody` of annotation `<id>` (Nth body, N≥2) | `<id>/body/<N>` |
| Shared target (referenced by multiple annotations) | sidecar must declare it as a named node from the start (no blank-node form permitted) |

The sidecar's parser/writer (P3.0) provides both forms — round-tripping
between blank-node ergonomics for human readability and named-node
strictness for graph emission. Authors and tooling never write
skolemized IRIs directly; they fall out of ingest.

**Round-trip guarantee.** Skolemize → emit-to-graph → re-parse-from-graph
→ de-skolemize must yield a sidecar byte-identical to the original
(modulo whitespace), so editing through either surface stays consistent.

### Annotation type vocabulary (`sci:annotationType`)

V1 vocabulary, organized by motivation:

**Curatorial (motivatedBy `oa:classifying`)** — produced by the
phase-2 marker scanner, lifted to annotations:

- `unverified` — verifiable in principle but not yet checked
- `missing-citation` — claim needs a source pointer
- `speculation` — author conjecture / brainstorming layer
- `inaccessible` — paywalled / image-only / private source

**Audit (motivatedBy `oa:classifying`)** — produced by LLM auditors:

- `consensus-claim-unsupported` (gap D)
- `load-bearing-undercited` (general undercitation flag)

**Mechanical lints (motivatedBy `oa:classifying`)** — produced by
detector functions, lifted from `science prose lint`:

- `bare-author-year`
- `short-form-ids`
- `frontmatter-inline-gap`
- `numeric-anchor`

**Linking (motivatedBy `oa:linking` / `oa:identifying`)**:

- `entity-mention` — NER-style; body is the resolved entity IRI
- `cites` — body is a bib key or DOI; suggested citation
- `replicates`, `contradicts` — cross-entity claim relations (data model
  ready; CLI / render deferred to v2)

**Free-form (motivatedBy `oa:commenting`)**:

- `comment` — human note attached to a span
- `highlight` — region marker with optional comment body

The vocabulary is open: `sci:annotationType` is a string, not a closed
enum. Adding a new type requires registering it in
`docs/conventions/annotations.md` so tooling, render, and dashboard can
recognize it; absence-of-registration produces a render warning, not an
error.

### Multi-annotation per span

Falls out of the data model: each annotation is an independent
`oa:Annotation` row. When two annotations target the same span, the
sidecar declares the target once as a named node (e.g.,
`anno:t-7f3a a oa:SpecificResource ; oa:hasSource ... ; oa:hasSelector
[ ... ] .`) and both annotations reference it via `oa:hasTarget
anno:t-7f3a`. Render-time grouping collects them by target IRI identity.
Inline blank-node targets are permitted only when not shared.

This means: an LLM audit can flag a sentence as
`consensus-claim-unsupported`, and a human can later attach a
`comment` annotation to the same span explaining the disposition.
Both rows coexist in the sidecar.

Note: the audit row's *own status* is mutated in place by
`science annotate ack/dismiss/fix` (see Status lifecycle below).
A separate human comment is an additional annotation, not a status
disposition; it carries its own `sci:status` (typically `open` for an
unanswered question or `ack` for a justification).

### Status lifecycle

`sci:status` is a **mutable field** on each annotation. Three CLI
commands mutate it:

- `science annotate ack <id>` → `open` → `ack`
- `science annotate dismiss <id> --reason "..."` → `open` → `dismissed`
- `science annotate fix <id>` → `open` → `fixed`

Re-audit (P3.5) and verify (P3.1) automate one additional transition:

- `* → superseded` when the annotation's `oa:TextQuoteSelector` no
  longer resolves (selector-broken under the resolution algorithm)

```
   open ────► ack         (author: "valid; accept as-is")
        ────► fixed       (author: "edited prose to address")
        ────► dismissed   (author: "wrong; reject")
        ────► superseded  (auto: selector no longer matches)
```

State semantics:

- `open` — initial state at creation. Counted in open-issue surfaces.
- `ack` — annotation is correct but author accepts current prose.
  Excluded from open counts; persists for audit trail.
- `fixed` — author edited prose to resolve. Excluded from open counts.
  Re-audit may produce a *new* `open` row at the new content hash if
  the issue persists.
- `dismissed` — author rejects. Excluded from open counts. The
  `--reason` text is stored in `dc:description` on the annotation.
- `superseded` — selector lost. Excluded from open counts. Set by
  tooling, not by author.

Status mutations record `dc:modified` on the annotation. Author
identity (the actor performing the mutation) is appended to a
`prov:wasRevisionOf` chain — the annotation row is mutated in place,
but the prior state is preserved through the prov chain so audit
history is never lost without git's help.

**Why mutate in place rather than append disposition events.**
Append-only would require deriving "current state" by walking
disposition chains at every read, complicating list/render/stats and
the graph-query surface. The mutation-in-place model keeps `sci:status`
directly queryable while preserving history through git + the
`prov:wasRevisionOf` chain. The trade-off is acceptable because
status is a small enum, not a rich payload; the disposition's
*reason* (which is the part worth preserving as data) lives in
`dc:description` or in a separate `comment` annotation.

Re-audit appends *new annotation rows* (for new findings); it never
mutates existing rows except for the `* → superseded` automatic
transition.

## File layout

Twin files: each annotated `.md` has a sibling `.anno.trig` in the same
directory.

```
doc/interpretations/2026-05-06-citation-audit-pilot.md
doc/interpretations/2026-05-06-citation-audit-pilot.anno.trig
```

Rationale (over a parallel `annotations/` tree):

- Files git-mv together; locality preserved
- `find` and grep return both when a directory is queried
- Twin-file convention is already used in the project (e.g., `<entity>.json` next to `<entity>.md` in some places)

The sidecar is created lazily — no annotations means no sidecar file.

### Concrete sidecar example

`doc/interpretations/2026-05-06-citation-audit-pilot.anno.trig`:

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  # Shared target: declared once as a named node so multiple
  # annotations can reference the same span via oa:hasTarget anno:t-7f3a.
  anno:t-7f3a a oa:SpecificResource ;
    oa:hasSource <2026-05-06-citation-audit-pilot.md> ;
    oa:hasSelector [
      a oa:TextQuoteSelector ;
      oa:exact   "category theory is the right framework" ;
      oa:prefix  "background ('category theory is the right framework', " ;
      oa:suffix  "', 'ontologies remain siloed', 'shared parameters not"
    ] .

  # LLM-audit annotation, acknowledged in place by the author.
  anno:a-7f3a a oa:Annotation ;
    oa:hasTarget       anno:t-7f3a ;
    oa:hasBody         [
      a oa:TextualBody ;
      dc:format        "text/plain" ;
      rdf:value        "Strong field-state claim with no anchor or explicit hedge. Suggested anchors: discussion:2026-03-31-validation-epistemology, topic:model-classification."
    ] ;
    oa:motivatedBy     oa:classifying ;
    sci:annotationType "consensus-claim-unsupported" ;
    sci:source         "llm-audit:gap-d-v1" ;
    sci:status         "ack" ;            # mutated from "open" by `science annotate ack`
    sci:contentHash    "sha256:1f9d...ab" ;
    dc:creator         "claude-opus-4-7" ;
    dc:created         "2026-05-10T14:23:00Z"^^xsd:dateTime ;
    dc:modified        "2026-05-10T15:01:00Z"^^xsd:dateTime ;
    dc:description     "Standard textbook framing; no source needed." ;  # ack reason
    prov:wasRevisionOf [                  # prior-state record (status was "open")
      sci:status       "open" ;
      dc:created       "2026-05-10T14:23:00Z"^^xsd:dateTime ;
      dc:creator       "claude-opus-4-7"
    ] .

  # Independent human comment on the same span.
  anno:a-7f3b a oa:Annotation ;
    oa:hasTarget       anno:t-7f3a ;      # same target, no selector duplication
    oa:hasBody         [
      a oa:TextualBody ;
      dc:format        "text/plain" ;
      rdf:value        "Worth a footnote pointing at Spivak's category-theory-for-scientists when we revisit ch3."
    ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:keith.hughitt@gmail.com" ;
    sci:status         "open" ;
    dc:creator         "keith.hughitt@gmail.com" ;
    dc:created         "2026-05-10T15:02:00Z"^^xsd:dateTime .
    # Note: sci:contentHash omitted — comment sources are not cache-keyed.
}
```

Two annotations, one shared target, one mutated status. The
`prov:wasRevisionOf` block preserves the pre-ack state without
requiring an append-only event log. The comment annotation
demonstrates the `human:` source convention (no version, no
content hash).

## Workflows

### Authoring loop

1. Author writes prose normally in `foo.md`.
2. Author runs `science annotate audit foo.md` (or it runs in CI on PR).
3. Auditor (mechanical lints + LLM detector) writes new annotation rows
   to `foo.anno.trig`. Each row records the content hash of the
   sentence it audited, plus the source's prompt/version string.
4. Author runs `science annotate list foo.md` to see open issues.
5. Author edits prose, acks (`science annotate ack <id>`), dismisses
   (`science annotate dismiss <id> --reason "..."`), or marks fixed
   (`science annotate fix <id>`).
6. Re-running audit only re-calls the LLM for sentences whose hash has
   changed since the last audit row of the same `sci:source`.

### Re-audit cache

Naive caching against existing annotation rows fails for clean
sentences: if a detector returns no finding, no annotation is written,
and the next run re-calls the LLM on the same clean prose. Solve with a
**per-source audit ledger** stored alongside annotations in the same
sidecar.

The ledger is *not* an `oa:Annotation` — it's a separate node type
(`sci:AuditLedger`) so it doesn't pollute annotation counts. One ledger
per (entity, source-version):

```turtle
anno:ledger-gap-d-v1 a sci:AuditLedger ;
  sci:source         "llm-audit:gap-d-v1" ;
  sci:auditedHashes  ( "sha256:1f9d..." "sha256:abc1..." "sha256:def2..." ) ;
  dc:modified        "2026-05-10T14:23:00Z"^^xsd:dateTime .
```

`sci:auditedHashes` is an RDF list of every content hash that has been
audited at this source-version, regardless of whether the detector
returned a finding. The list is append-only within a source-version;
when the source-version bumps, a new ledger is created and the old one
is retained for history.

Cache key: `sha256(exact_text || sci:source_version)`.

For each candidate sentence at audit time:

```
ledger = sidecar.find_or_create_ledger(source_version=current_source)
hash = sha256(sentence_text || source_version)
if hash in ledger.audited_hashes:
    skip                                # already audited (clean or flagged)
else:
    new_row = run_detector(sentence_text)
    if new_row is not None:
        sidecar.append_annotation(new_row)
    ledger.append_hash(hash)             # always record audit attempt
```

**Source-version bump policy.** Bump when prompt changes meaningfully
alter the verdict distribution. Trivial edits (typo fixes in prompt)
need not bump. On bump: a new ledger node is created; the old ledger
remains in the sidecar but its hashes no longer hit the cache. Existing
annotations from the old source-version are not invalidated — they
persist as history; the next audit will produce *new* annotations from
the new source-version on the same sentences.

**Why ledger over separate cache file.** Single source of truth: cache
is committed alongside data, fully reproducible across machines.
Filtering it out of annotation queries is one type-check
(`?node a oa:Annotation` excludes `sci:AuditLedger`), trivial. The cost
— slight sidecar bloat — is bounded (one hash per audited sentence per
source) and reversible (compaction utility could fold old ledgers).

### Verify loop (CI drift detection)

`science annotate verify [<path>]` walks every annotation row in the
project, attempts to resolve each `oa:TextQuoteSelector`, and reports:

- `selector-broken` — `exact` text not found at all → row gets `sci:status "superseded"` written back
- `selector-degraded` — `exact` found but prefix/suffix don't match → warning only, no write-back
- `selector-fuzzy` — fuzzy match used → warning only

CI failure threshold is `selector-broken` count > 0. The other two are
informational. Verify never calls the LLM; it only resolves selectors.

## CLI surface

```
science annotate audit <path>           # Run auditors (mechanical + LLM); cached
science annotate audit <path> --source bare-author-year   # Run one source only
science annotate audit <path> --no-llm  # Skip LLM sources
science annotate audit <path> --since <git-ref>           # Only audit changed paragraphs

science annotate lift-tokens <path>     # Lift inline phase-2 tokens to sidecar rows
science annotate list <path>            # Table: open annotations for entity
science annotate list --status open --type consensus-claim-unsupported

science annotate ack <id>               # Status → ack
science annotate dismiss <id> --reason  # Status → dismissed
science annotate fix <id>               # Status → fixed (assumes prose was edited)

science annotate render <path>          # Terminal: prose with color-coded marks
science annotate render --html <path>   # HTML reading copy with hover tooltips
science annotate render --inspect <id>  # Show one annotation in full

science annotate verify [<path>]        # Drift detection (no LLM calls)
science annotate stats                  # Project-wide counts by type/status/source
```

`<id>` is the local fragment identifier within the sidecar
(e.g., `a-7f3a`); CLI accepts `<entity>:<frag>` shorthand
(`citation-audit-pilot:a-7f3a`) for cross-entity unambiguity.

## Migration from phase 2

The phase-2 stub (`plan:2026-05-09-annotation-system-stub`) ships four
inline tokens (`[UNVERIFIED]`, `[MISSING_CITATION]`, `[SPECULATION]`,
`[INACCESSIBLE]`) with the shared `science_tool/markers.py` scanner.

Phase-3 lift:

1. **Inline syntax remains** for cheap shallow cases. Authors can keep
   typing `[UNVERIFIED]` in prose; nothing breaks.
2. **`science annotate lift-tokens <path>`** has two modes:
   - `--mirror` (default): create sidecar rows, leave inline tokens in
     place. The lifted row records `sci:liftedFrom "[UNVERIFIED]"` to
     identify the source token; selector quotes the surrounding
     sentence.
   - `--remove`: create sidecar rows, strip inline tokens from prose
     (destructive; requires clean git working tree).

   Each lifted row carries:
   - `oa:hasSelector` quoting the surrounding sentence
   - `sci:annotationType` set to one of `unverified`, `missing-citation`,
     `speculation`, `inaccessible`
   - `sci:source` set to `marker-scanner:phase-2`
   - `sci:status` set to `open`
   - `sci:liftedFrom` set to the original token literal
3. **Dedupe semantics** (the load-bearing rule). Tooling MUST avoid
   double-counting the same logical issue across the inline scanner and
   the sidecar:
   - **`science markers scan`** (the phase-2 scanner) gains a
     `--ignore-lifted` flag. When set, it skips inline tokens whose
     enclosing sentence has a sidecar annotation with matching
     `sci:liftedFrom`. The `--mirror` mode produces such matches; the
     `--remove` mode makes the question moot.
   - **`validate.sh` Section 8** (marker counts) sets `--ignore-lifted`
     by default once Section 8 is updated for phase-3 awareness (a
     managed-artifact bump). Pre-bump projects continue counting
     inline tokens directly with no double-count risk because the
     sidecar is empty.
   - **`science annotate list/render/stats`** dedupe by `(target,
     sci:source)` — two rows with the same target and same source are
     treated as one. The lifted row IS the canonical annotation form;
     the inline token is its surface syntax.
4. **The unified view** (`science annotate list`, render, dashboard)
   shows lifted-token annotations alongside LLM-audit and human
   annotations. One mental model, two surface syntaxes (inline shallow,
   sidecar rich).
5. **Phase-2 marker scanner becomes one source** among many. Its severity
   table feeds the lifted annotations' default rendering severity.

`validate.sh` Section 8 (marker counts) continues to work via the
existing scanner; the sidecar is *additive*. The dedupe rule above
ensures inline tokens and lifted-token rows never both contribute to a
single count.

## Downstream consumers

### Graph integration

A build step ingests every `*.anno.trig` file into a named graph in
`knowledge/graph.trig` (e.g., `<#annotations>` graph). Annotations
become first-class graph entities with `bears_on` edges to their
target entities. The existing freshness propagation machinery (per
NS t479/t481) then triggers `needs-review` on dependent entities when
their annotations change.

**Skolemization at ingest.** `save_canonical_graph_dataset()` rejects
all blank nodes. Sidecars MAY use blank nodes for compactness; the
ingest step therefore applies the skolemization rule defined in the
data model section (target → `<id>/target`, selector →
`<id>/target/selector`, body → `<id>/body`, etc.) before merge. Sidecar
files that already use named nodes throughout (e.g., the shared-target
pattern in the concrete example) pass through unchanged.

`bears_on` edges from each annotation IRI to its target entity are
materialized at ingest by resolving `oa:hasTarget` → `oa:hasSource` and
emitting `<annotation-IRI> sci:bearsOn <entity-IRI>`. This is what
wires annotations into the freshness graph.

This unlocks queries like "show me all `consensus-claim-unsupported`
annotations across the project," "show me every entity with > 5 open
annotations," "show me annotations whose source is older than the last
prose edit on their target."

### `~/d/dashboard`

The dashboard reads the same TriG (via the unified graph) and renders:

- Per-entity annotation density heatmap
- Status-filterable annotation lists
- Source-filterable views (LLM-only, human-only, lints-only)
- Prose with inline marks + hover-tooltip annotations

Dashboard design is out of scope for this spec; it consumes the data
model defined here.

### `validate.sh` integration

Optional Section 19: invoke `science annotate verify` and report
`selector-broken` count. Defaults to advisory (warn-only); promotes to
strict failure under `--strict`. Lands as a separate
managed-artifact bump after the CLI is stable.

## Worked examples

### Example 1: gap D (consensus claim)

LLM audit detects the sentence "category theory is the right framework"
in `2026-05-06-citation-audit-pilot.md`. Writes one annotation:

- `sci:annotationType "consensus-claim-unsupported"`
- `sci:source "llm-audit:gap-d-v1"`
- `oa:motivatedBy oa:classifying`
- Body: textual suggestion of anchors (`discussion:...`, `topic:...`)

Author runs `science annotate ack <id>` with no comment, or
`science annotate dismiss <id> --reason "framing only, not a claim"`.
Re-audit doesn't re-flag because the sentence hash hasn't changed and
the source version is unchanged.

### Example 2: literature citation suggestion

Existing `bare-author-year` lint detects "Brunton 2022" in prose. Lifted
to annotation:

- `sci:annotationType "cites"`
- `sci:source "lint:bare-author-year"`
- `oa:motivatedBy oa:linking`
- Body: `<bib:brunton-2022>` (suggested key, resolved against
  `papers/references.bib`; if missing, body is `oa:TextualBody` with the
  bare-author-year text and a "no matching bib entry" note)

Author runs `science annotate fix <id>` after editing prose to add
`[@brunton-2022]`. Annotation status → fixed; persists as history.

### Example 3: named-entity mention

A separate NER detector finds "h04" in body prose. Resolves to
`hypothesis:h04-dynamical-invariant-validation`. Writes:

- `sci:annotationType "entity-mention"`
- `sci:source "lint:short-form-ids"` (lifted from existing detector)
- `oa:motivatedBy oa:identifying`
- Body: `<hypothesis:h04-dynamical-invariant-validation>` IRI

Render shows it as a hyperlink in HTML mode; terminal render shows it
as a bold inline mark. Dashboard can navigate from the source entity to
every entity it mentions and vice versa.

### Example 4: human highlight + comment

User selects a multi-paragraph region in dashboard, attaches a comment
"this whole section needs to move to the methods discussion." Writes:

- `sci:annotationType "highlight"`
- `sci:source "human:keith.hughitt@gmail.com"`
- `oa:motivatedBy oa:commenting`
- `oa:hasSelector` with multi-line `oa:exact`
- Body: textual comment

This is the use case that justifies the arbitrary-region capability —
nothing else in the data model needed special-casing for it.

## Sequencing

Suggested implementation phases (each a separate plan; this spec only
defines the data model + CLI surface):

**P3.0 — Data model + sidecar I/O.** TriG schema, parser/writer,
`oa:TextQuoteSelector` resolution algorithm, content-hash cache, status
lifecycle. No CLI yet. Tests define the data-model contract. Foundation
for everything else.

**P3.1 — `science annotate verify`.** Drift detection across the
project. No LLM, no auditors. Validates the data model on real data
before adding sources.

**P3.2 — Lift mechanical lints + tokens.** Refactor `science prose
lint` and `science_tool/markers.py` to write annotation rows in
addition to (or instead of) their current output. `science annotate
lift-tokens` for one-shot legacy migration.

**P3.3 — `science annotate list / ack / dismiss / fix`.** Author-facing
CRUD on existing annotations. No new sources yet.

**P3.4 — `science annotate render`.** Terminal + HTML rendering.

**P3.5 — LLM auditor (gap D first).** First LLM source. Establishes
prompt-versioning policy, cache-key format, cost guardrails.

**P3.6 — Graph integration.** Ingest sidecars into `knowledge/graph.trig`
under a named graph; wire freshness propagation.

**P3.7 — Dashboard consumer.** Out of scope for science_tool; lives in
`~/d/dashboard`. Reads the unified graph.

P3.0–P3.4 are independently shippable and provide value before any LLM
source lands. The LLM detector (the original gap-D motivator) is P3.5,
deliberately late: by then the data model, cache, status lifecycle, and
render are battle-tested on cheap mechanical sources.

## Open questions

1. **Sentence segmentation strategy.** Naive split on `.\s+` over-splits
   on abbreviations and decimals; pysbd / spaCy add dependencies.
   Probably acceptable to start naive + content-hash recovery from
   fuzzy match; revisit if false-positive rate is high.
2. **Prompt versioning policy.** Semver-on-prompt-edits is heavyweight;
   date-stamped (`gap-d-v2026-05-10`) is simpler. Pick during P3.5.
3. **TextQuoteSelector context length.** Default 60 chars / each side
   suggested above. May need tuning per detector (long-prose entities
   may need more context to disambiguate repeated phrases).
4. **Frontmatter as annotation target.** Can `oa:hasSource` point at a
   frontmatter field within an entity (e.g., `<entity.md#frontmatter:title>`)?
   Probably yes via `oa:FragmentSelector`, but defer until a use case
   demands it.
5. **Cross-entity annotations.** `replicates` / `contradicts` types are
   listed in the vocabulary but lack CLI / render support in v1. Defer
   until the dashboard exists to motivate the UX.
6. **Annotation-of-annotation.** Threading replies. Data model can
   handle it (annotation targets another annotation IRI); CLI and render
   deliberately do not in v1. Defer.
7. **Bulk-import path for the t466 pilot raw audits.** The 15 raw
   audits at `/tmp/citation-audit-pilot/` (likely now gone) would have
   been the ideal labeled training/eval set. May need to re-run the
   pilot once the LLM source is built, with results captured into
   sidecars directly (closes the loop: spec built on the pilot now
   feeds back to validate the same).

## Prior art

- **W3C Web Annotation Data Model** (https://www.w3.org/TR/annotation-model/)
  — directly adopted as the foundation. The `oa:` namespace, selector
  vocabulary, motivation taxonomy, and body model are all standards we
  reuse rather than reinvent.
- **hypothes.is** — production deployment of the W3C model on web
  content. Demonstrates the fuzzy-match selector recovery pattern at scale.
- **CriticMarkup** (`{++inserted++}`, `{>>comment<<}`) — author-friendly
  inline syntax. Considered and rejected for the structured layer
  (incompatible with TriG storage), but the inline shallow case in
  phase 2 occupies a similar niche.
- **Pandoc spans** (`[text]{.class key=val}`) — typed inline spans.
  Considered as an alternative to sidecar storage; rejected because
  storing payloads in markdown attribute syntax becomes unreadable
  past 2-3 fields and conflicts with the prose-clean goal.
- **JATS `<annotation>`** — XML/NLM scientific-publishing standard.
  Mature data model but XML-heavy; W3C OA is the more modern equivalent.
- **brat / doccano** — annotation tools for NLP corpora. Use BIO-style
  span tagging with a typed entity vocabulary. The annotation type
  vocabulary in this spec borrows the "open vocabulary, registered
  in convention doc" pattern from these tools.
- **Argdown** — argument-mapping syntax. Out of scope for v1, but the
  `replicates` / `contradicts` types in the vocabulary leave room for
  future Argdown-style argumentation overlays.
- **Semantic line breaks** (https://sembr.org/) — orthogonal authoring
  convention that would make `oa:TextQuoteSelector` resolution more
  robust to reflow. Adoption would be a separate convention proposal.

## Cross-references

- `plan:2026-05-09-annotation-system-stub` — phase 2 (inline tokens),
  superseded only at the phase-3 section.
- `interpretation:2026-05-06-citation-audit-pilot` — the t466 pilot
  that motivates gap-D detection.
- `task:t468` — NS-side Snakemake-driven citation-audit pipeline; this
  spec's P3.5 is the science-tool side of the same workflow.
- `docs/conventions/refs-check.md` — `science refs check` is a
  data-source for entity-mention / cites annotations (resolves the
  body IRIs).
- `docs/conventions/prose-lints.md` — phase-3 P3.2 refactors these
  lints to write annotations.

## Revision history

- **2026-05-11** — review pass addressing 8 findings:
  1. Status handling clarified — `sci:status` mutates in place via
     `ack/dismiss/fix`; `prov:wasRevisionOf` preserves prior state;
     re-audit appends new rows but never mutates existing ones (except
     the auto `* → superseded` transition).
  2. Re-audit cache rewritten — added `sci:AuditLedger` per
     (entity, source-version) recording every audited content hash so
     clean sentences are not re-called.
  3. Skolemization rule added — explicit mapping for blank-node→IRI
     translation at graph ingest, satisfying
     `_assert_no_blank_nodes` in `science_tool/graph/io.py`.
  4. Concrete TriG example fixed — added missing `@prefix rdf:`,
     declared the shared target as a named node (`anno:t-7f3a`), and
     restructured the second annotation as an independent comment
     (status mutation is now shown in-place on the audit row).
  5. `sci:` namespace bound to `http://example.org/science/vocab/`
     (matching repo `SCI_NS`); the prior `https://science.local/ns#`
     was non-joinable with the canonical graph.
  6. `sci:contentHash` made source-class-conditional — required for
     `audit:` and `lint:` sources, optional/absent for `human:` and
     free-form `comment` rows.
  7. Fuzzy selector resolution tightened — requires unique match with
     a 2× score margin; ambiguous matches fall through rather than
     guessing.
  8. Lifted-token dedupe semantics specified — `lift-tokens` has
     `--mirror` (default) and `--remove` modes; `science markers scan`
     gains `--ignore-lifted`; `validate.sh` Section 8 sets it by
     default after a managed-artifact bump; render/list/stats dedupe
     by `(target, sci:source)`.
- **2026-05-10** — initial draft.

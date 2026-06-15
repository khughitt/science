# PubTator3 entity-mention seeder (sub-article annotation — Phase 2a)

- **Status:** Design approved 2026-06-15 → ready for implementation plan.
- **Parent spec:** `~/d/science/docs/plans/2026-06-14-sub-article-annotation-spec.md`
  (Component 2, "PubTator3 seeder"). This doc narrows that component to an
  implementable **Phase 2a** (entity mentions only) and records the decisions made
  while planning it.
- **Builds on:** Phase 1 (`.source.md` anchor surface), shipped in
  `science/src/science_tool/annotation/source_text.py`.

## Goal

A deterministic CLI that reads an existing `<citekey>.source.md`, re-fetches the
paper's PubTator3 BioC record, converts each **entity mention** to an
`oa:TextQuoteSelector` annotation anchored into `.source.md`, and writes/merges the
`<citekey>.source.anno.trig` sidecar by **reusing** the existing W3C annotation
machinery. No annotation-model change.

## Scope

**In scope (Phase 2a):** PubTator3 entity mentions (gene / disease / chemical /
variant / species / cellline) → single-`IriBody` span annotations.

**Deferred (later phases):**
- **Relations** (Phase 2b) — evidence-sentence span targeting, the
  smallest-span-containing-both fallback, the JSON `TextualBody`, and the
  PubTator→Biolink predicate map.
- **Document-level short-circuit** (`sci:sourceTextHash` on `AuditLedger`) — the one
  part of the parent spec that touches the annotation *model* + io. Per-annotation
  `content_hash` dedup (below) already makes re-runs idempotent; the short-circuit
  only saves one deterministic API call, low value for local low-volume use.
- **Statements / metaphors / analogies** (Phase 3, agent extraction) and
  **promotion** (Phase 4).

## Decisions (resolved while planning Phase 2a)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Phase 2 split | **Entities first (2a)**; relations are a small follow-on (2b) |
| 2 | Doc-level `sci:sourceTextHash` short-circuit | **Defer** — keep Phase 2a a pure annotation producer, no model change |
| 3 | `.source.md` coupling | **Require it; fail loud** if missing ("run `science paper persist-source` first") — composable, single-responsibility |
| 4 | CLI home | **`science annotate pubtator <pmid\|doi>`** — a new subcommand on the existing top-level `annotate` group, so future book-applicable annotators sit beside it |
| 5 | Concept-IRI scheme | Full **`identifiers.org`** HTTP IRIs in `IriBody` (TriG emits `IriBody.iri` as a literal `<iri>`, so it must be a full IRI, not a CURIE) |
| 6 | Unmappable mentions | **Skip and count** (non-persisted passage, or PubTator left the mention unnormalized) — only clean concept anchors are seeded; nothing silent |
| 7 | `match_text` | A **span discriminator** `{annotation_type}\|{concept_iri}\|{file_char_base}:{length}\|{exact}`, not the bare mention text — the merge 4-tuple has no position, so bare text would collapse repeated/overlapping mentions |
| 8 | Passage bridge | Pair persisted↔BioC passages by **ordered occurrence** (left-to-right scan), not unordered text search; **fail loud** on ambiguous duplicate text |

## Architecture

### CLI & flow

`science annotate pubtator <pmid|doi>` (new `@annotate_group.command("pubtator")` in
`science/src/science_tool/annotation/cli.py`, which already imports
`read_sidecar` / `merge_planned` / `write_sidecar`):

1. `resolve_paper_entity(project_root, doi=…, pmid=…)` → citekey + directory
   (reused from Phase 1, `source_text.py`). No-match / multi-match fail loud there.
2. Load `<citekey>.source.md`. **Missing ⇒ fail loud** with an actionable message
   ("run `science paper persist-source <id>` first"). Parse the frontmatter
   `passages` offset map (`section` / `file_char_base` / `length`) and the file body.
3. Re-fetch the **raw** BioC JSON for the **entity's** PMID, reusing the Phase 1
   endpoint constants + `_get_json` (note: `source_text._fetch_bioc` discards the raw
   record and returns only parsed passages — the seeder needs the raw record to read
   the entity **annotations** too, so it fetches the record itself and parses both
   passages *and* annotations from it). No PMID / no BioC record / non-PubMed ⇒
   **graceful no-op** ("no PubTator3 annotations available for this paper") —
   PubMed-only by design.
4. Convert each entity mention to a `PlannedAnnotation` (see *Offset → selector*).
5. `read_sidecar(<citekey>.source.anno.trig)` (or empty `Sidecar()`) →
   `merge_planned(...)` → `write_sidecar(...)`. Report rows written / skipped, with
   skip reasons.

### Offset → selector (the heart)

The frontmatter offset map gives `(section, file_char_base, length)` per **persisted**
passage, in render order. The live BioC record gives passages with `bioc_offset` +
raw `text`. Bridge them by **text equality** — exactly the invariant Phase 1's
`verify_offset_map` guarantees at write time:

1. **Pair persisted passages to live BioC offset bases — by ordered occurrence, not
   unordered text search.** The persisted passages preserve BioC relative order (Phase
   1 renders abstract-floor then body, each in BioC order), so pair with a single
   left-to-right scan: iterate offset-map entries `e` in render order, advancing a
   pointer through the BioC passage list to the **next** passage `p` whose `p.text`
   equals `file_text[e.file_char_base : e.file_char_base + e.length]`; record
   `p.bioc_offset → e.file_char_base` and leave the pointer past `p`. This pairs
   duplicate-text passages to **successive** BioC occurrences by order (no ambiguity)
   and naturally skips BioC passages that were not persisted (e.g. license-gated body).
   An unordered `p.text == slice` search is **wrong**: two persisted passages with
   identical text could pair the later entry to the earlier BioC offset and mis-map
   every body annotation. A persisted passage with no remaining ordered match in the
   re-fetched BioC ⇒ **fail loud** (API/text drift; the persisted `text_sha256` is the
   guard that the body — hence the passages — is unchanged). If duplicate persisted
   text still makes a pairing genuinely ambiguous (the ordered scan cannot resolve it
   deterministically), **fail loud** rather than guess.
2. **Map each entity annotation.** For a BioC entity annotation `a` with
   `(bioc_offset, length, mention_text, concept_id, type)`:
   - Find the BioC passage `p` whose range `[p.bioc_offset, p.bioc_offset+len(p.text))`
     contains `[a.bioc_offset, a.bioc_offset+length)`.
   - **If `p` is in the persisted-pair set:** `file_idx = base + (a.bioc_offset −
     p.bioc_offset)`; `exact = file_text[file_idx : file_idx + length]`; **assert
     `exact == mention_text`** — any mismatch is a hard per-paper error (never a
     silently mis-placed anchor). Build `prefix` / `suffix` windows **clamped to the
     persisted passage bounds** `[e.file_char_base, e.file_char_base + e.length)` so a
     window never crosses a heading or passage boundary.
   - **If `p` is not persisted** (a body annotation on an abstract-only paper whose
     full text was license-gated out in Phase 1): **skip, counted.**

This anchors by construction. A test additionally re-resolves every seeded selector
through the standard `annotation/verify.py` against the rendered `.source.md`
(round-trip through frontmatter + headings), per the parent spec's testing section.

### Entity type → annotation_type / Biolink class / concept IRI

| PubTator type | `annotation_type` | Biolink class (docs map only) | Concept IRI |
|---|---|---|---|
| gene | `entity-gene` | `biolink:Gene` | `https://identifiers.org/ncbigene/{id}` |
| disease | `entity-disease` | `biolink:Disease` | `https://identifiers.org/mesh/{id}` |
| chemical | `entity-chemical` | `biolink:ChemicalEntity` | `https://identifiers.org/mesh/{id}` |
| species | `entity-species` | `biolink:OrganismTaxon` | `https://identifiers.org/taxonomy/{id}` |
| variant | `entity-variant` | `biolink:SequenceVariant` | `https://identifiers.org/dbsnp/{id}` (rsID) |
| cellline | `entity-cellline` | `biolink:CellLine` | `https://identifiers.org/cellosaurus/{id}` |

- **Single body:** `IriBody(<full concept IRI>)`. **Motivation:** `oa:identifying`.
- The Biolink class is **derived from `annotation_type`** via the documented map; it
  is **not** stored in the annotation (no second body). The map lives in
  `docs/conventions/annotation-tokens.md`.
- **Unnormalized mention** (concept id absent, or not matching the type's expected id
  shape — e.g. a tmVar variant string with no rsID) ⇒ **skip, counted.** We seed only
  clean concept anchors; no `TextualBody` fallback, no silent loss.
- A small `PUBTATOR_TYPE_SPEC` table (type → `annotation_type`, Biolink class, IRI
  builder, id validator) is the single source of this mapping in code. The seeder
  ignores PubTator types outside this table (counted as skipped/unsupported).

### Concept-id parsing notes

PubTator BioC stores the normalized id in a mention's `infons` (e.g.
`identifier` / `NCBI Gene` / `MESH`). The id may be bare (`1017`) or prefixed
(`MESH:D003920`, `Gene:1017`, `@DISEASE_…`), and a single mention may list several
(`;`-joined). The IRI builder per type strips the known prefix, takes the first id,
validates its shape, and constructs the `identifiers.org` IRI; anything that fails
validation ⇒ skip-and-count (above). Exact `infons` key handling is pinned by the
real fixture used in tests.

### Source identity, dedup, hashing

- `source_name = "pubtator3:<release>:seeder-v1"`. `<release>` is read from the live
  BioC `_release` infon (`SourcePassages.release`), fallback
  `source_text.PUBTATOR3_API_VERSION`.
- Add `"pubtator3:"` to `HASH_REQUIRED_SOURCE_PREFIXES`
  (`annotation/model.py` — a one-line tuple addition; **not** the deferred
  `sci:sourceTextHash` change). `merge_planned` already assigns
  `content_hash(exact, source_name)`, so a re-run at the same release re-derives
  identical hashes and the existing 4-tuple skip (`(source, exact, lifted_from,
  match_text)`) makes it idempotent. Bumping `seeder-vN` invalidates the cache.
- **`match_text`** = a stable **span discriminator**, NOT the bare mention text. The
  merge dedup key is `(source, selector.exact, lifted_from, match_text)`
  (`audit.py::_annotation_tuple`) — it carries no prefix/suffix or position, so two
  distinct mentions of the same surface form (e.g. two `BRCA1` occurrences in one
  paper, or the same span tagged with two concepts) would collapse to one row if
  `match_text` were just the mention text. Use
  `match_text = f"{annotation_type}|{concept_iri}|{file_char_base}:{length}|{exact}"`,
  which is unique per (type, concept, span position) and **stable across re-runs** of
  an unchanged `.source.md` (so idempotency holds). **`lifted_from`** = `None`.
- **Note on `content_hash`.** It stays `content_hash(selector.exact, source_name)`
  (spec-pinned, unchanged), so two same-surface mentions share a `content_hash`. That
  is fine here: `content_hash` is the re-audit cache key, not the merge key — insertion
  is governed by the 4-tuple above, which the span discriminator keeps distinct.

## File structure

- **Create** `science/src/science_tool/annotation/pubtator_seed.py` — BioC *entity
  annotation* parsing, the `PUBTATOR_TYPE_SPEC` table + IRI builders, the
  offset→selector mapper, the `PlannedAnnotation` builder, and the orchestrator
  (`seed_pubtator(*, project_root, identifier, cfg, http=None) -> SeedReport`). Mirrors
  Phase 1's injectable-`httpx.Client` idiom.
- **Modify** `science/src/science_tool/annotation/cli.py` — add the `pubtator`
  subcommand (resolve project root, build `FetchConfig`, call `seed_pubtator`,
  print the report; `SourceTextError` → `click.ClickException`).
- **Modify** `science/src/science_tool/annotation/model.py` — append `"pubtator3:"`
  to `HASH_REQUIRED_SOURCE_PREFIXES`.
- **Modify** `docs/conventions/annotation-tokens.md` — register the six
  `entity-<type>` annotation types, the `entity-<type>` → Biolink-class map, and the
  `pubtator3:<release>:seeder-vN` source prefix.
- **Create** `science/tests/test_pubtator_seed.py` — offset round-trip (incl.
  non-ASCII / multi-codepoint), skip-non-persisted-passage, skip-unnormalized,
  fail-loud on slice≠mention, idempotency on re-run, graceful no-op, IRI-builder
  unit cases.
- **Create** `science/tests/test_cli_annotate_pubtator.py` — `CliRunner` +
  `MockTransport` end-to-end (a small real BioC fixture), missing-`.source.md`
  fail-loud, no-op exit.

## Reuse vs. new

- **Reuse:** `resolve_paper_entity`, `parse_bioc_passages`, the PubTator3 endpoint
  constants, `RateLimiter` / `FetchConfig` / `_get_json` (all Phase 1 / `paper_fetch`);
  `PlannedAnnotation` / `SpecificResource` / `TextQuoteSelector` / `IriBody` /
  `Motivation` (`annotation/sources/base.py`, `annotation/model.py`); `merge_planned`
  / `read_sidecar` / `write_sidecar` (`annotation/audit.py`, `annotation/io.py`);
  `annotation/verify.py` (in tests). Consider reusing `build_quote_selector`
  (`annotation/text_segmentation.py`) for the prefix/suffix window, wrapped so the
  window is clamped to passage bounds rather than the whole file.
- **New:** BioC *entity-annotation* parsing (Phase 1 parsed only passages, not
  annotations), the offset-bridge mapper, the `PUBTATOR_TYPE_SPEC` table + IRI
  builders, the orchestrator + CLI subcommand.

## Testing

- **Offset → `TextQuoteSelector`:** every seeded selector re-resolves via the
  standard verifier against the rendered `.source.md`; non-ASCII / multi-codepoint
  mention text exercised (character-offset alignment, no byte drift); `slice ==
  mention_text` fails early on any offset mismatch.
- **PubTator3 BioC annotation parsing:** small real fixture (title+abstract record
  with a handful of typed mentions, at least one unnormalized and one body-section
  mention).
- **Duplicate surface mention (regression for the merge collapse):** two distinct
  mentions of the same surface form (e.g. `BRCA1`) at **different** offsets both
  survive `merge_planned` as separate rows (the span discriminator in `match_text`
  keeps the 4-tuples distinct), and re-running seeds zero new rows.
- **Duplicate passage text (regression for the bridge ambiguity):** a fixture with two
  persisted passages carrying identical text maps body annotations to the **correct**
  occurrence via the ordered scan (and a genuinely ambiguous case fails loud).
- **Skip accounting:** non-persisted-passage mention and unnormalized mention are
  both skipped, counted, and reported (not silently dropped).
- **Idempotency:** re-run at the same release writes zero new rows (4-tuple skip);
  a `seeder-vN` bump re-seeds.
- **Graceful no-op:** no PMID / empty BioC → exits cleanly with a message, writes
  nothing.
- **Fail-loud:** missing `.source.md`; persisted passage absent from re-fetched
  BioC; `slice != mention_text`.
- **CLI:** `CliRunner` + `MockTransport`, end-to-end sidecar round-trip, and the
  fail-loud / no-op exits.

## Out of scope (this phase)

Relations (2b); `sci:sourceTextHash` doc-level short-circuit; statements /
metaphors / analogies (3); promotion (4); ingesting concept IRIs into the main graph
(would require registering external namespaces in `graph/store/constants.py`
`CURIE_PREFIXES` — not needed while the bodies live only in the sidecar).

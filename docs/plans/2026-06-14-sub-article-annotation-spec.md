# Sub-article annotation for `science` papers

- **Status:** Design approved 2026-06-14; spec-review findings resolved 2026-06-14
  (round 1: offset basis, identifier→entity resolver, relation targets, source/dedupe
  vocab, annotationType registration; round 2: JSON body encoding, content_hash
  semantics, character-offset/NFC; round 3: license whitelist + fail-early,
  single-body entity mentions) → ready for implementation plan
- **Scope:** Extend `science`'s existing W3C annotation system to capture rich,
  semantic, sub-article (word / phrase / sentence) annotations of research
  articles, seeded by PubTator3 and extended by an agent.
- **Related:** `~/d/science/docs/plans/2026-05-10-annotation-system-spec.md`
  (annotation data model — the substrate this builds on)

## Motivation

We want rich, semantic annotations of research articles at sub-article
granularity. Rather than stand up a new project, we extend the machinery
`science` already has:

- A **W3C Web Annotation system** (`~/d/science/science/src/science_tool/annotation/`)
  with `oa:TextQuoteSelector` spans (exact + prefix/suffix, fuzzy re-anchoring),
  TriG sidecar storage ingested into the knowledge graph, typed bodies
  (`TextualBody` / `IriBody`), motivation + `sci:annotationType` vocabularies,
  source provenance (`kind:version`), a status lifecycle, and content-hash
  re-audit caching.
- An **epistemic layer** modelling propositions, questions, hypotheses (with
  subject/object/predicate, claim layers, evidence) — the natural promotion
  target for extracted statements.
- **Biolink** already wired in via the ontology registry
  (`~/d/science/science/model/src/science_model/ontologies/biology/catalog.yaml`).

Near-term use is **local and low-volume** — annotating papers in `~/d/science`,
agent-driven. The at-scale `lit-annot` pipeline is explicitly a separate future
project, not this work.

### Motivating use cases

1. Capture **external** propositions / questions / hypotheses (not just the
   user's), feeding the epistemic machinery — e.g. generating rival hypotheses
   to test alongside user proposals, surfacing questions we hadn't considered.
2. Build a dataset of **metaphors / analogies / mental models** used to describe
   biological and physical systems.

## Design decisions (resolved during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Where the work lives | **Extend `science`** (not a new sibling CLI or at-scale pipeline) |
| 2 | What annotations anchor into | **Source article text** — abstract always, full text when OA-licensed |
| 3 | First-iteration categories | **PubTator3 entities + relations**, **epistemic statements**, **metaphors/analogies** |
| 4 | Statement → epistemic relationship | **Annotate first, promote later** (raw evidence vs. curated knowledge stay separate) |
| a | Anchor surface | A persisted `.source.md` text artifact per paper |
| b | PubTator3 access | The **live BioC API** (not the bulk FTP pipeline) for the local case |
| c | Promotion ordering | Promotion is the **last** phase, not threaded earlier |

## Architecture

### Data artifacts (co-located with the resolved paper entity)

The new artifacts live **next to the paper's existing summary file**, wherever
that resolves to (see *Identifier → paper-entity resolution* below) — NOT a
hardcoded `doc/papers/`. The paper kind's path policy is `entities/papers/`
(citekey filenames), but projects may store summaries elsewhere (this meta
checkout uses `meta/doc/background/papers/`), so the resolver, not a literal
path, decides placement.

| File | Role | Status |
|------|------|--------|
| `<citekey>.md` | Human summary (frontmatter + prose) | exists today |
| `<citekey>.source.md` | **New.** Persisted article text — `## Abstract` always; `## Full Text` sections only when an OA-licensed copy is retrievable. Frontmatter: `retrieved_from`, `license`, `text_sha256`, `pmid` / `doi`, and the per-passage offset map (offset basis, above). | new |
| `<citekey>.source.anno.trig` | **New.** Sub-article annotations anchored into `.source.md` via `oa:TextQuoteSelector`. Reuses the existing annotation system. | new |

### Identifier → paper-entity resolution

The seeder is invoked with a `pmid|doi`, but artifacts are keyed by **citekey**
and `paper-fetch` writes only DOI-slugged *cache* artifacts (`<slug>.json/.pdf/
.xml`, `paper_fetch.py::_write_and_return`), not citekey-named project entities.
A resolver is required before any artifact is written:

- **Resolve.** Map the `pmid|doi` to a paper entity by scanning paper-entity
  frontmatter for a matching `doi`/`pmid` (the paper kind, via its path policy and
  any project-local override). Return the entity's citekey and directory.
- **No match.** Fail loud with an actionable message ("no paper entity has
  doi/pmid X; run `paper-fetch` / create the entity first"). The seeder does **not**
  silently mint a paper entity — promotion of a paper into the graph is a separate,
  deliberate step.
- **Multi match.** Two entities claiming the same `doi`/`pmid` is a data error;
  fail loud and name both files rather than guessing.

Annotations target the **article text**, not our summary — so spans quote the
authors' own words and the human summary stays clean and readable. Persisting
normalized text (vs. the raw PDF) is what makes quote selectors stable and
re-anchorable across re-runs.

### Offset basis & anchoring policy

The annotation system anchors by `oa:TextQuoteSelector` (`exact` + `prefix` /
`suffix` text), **not** by stored character offsets, and the verifier resolves a
selector by string-matching against the *entire* `.source.md` file —
frontmatter and `##` headings included (`annotation/verify.py::_load_source`).
PubTator3 offsets are therefore **not** directly usable; they must be converted
to quotes through an explicit map. Policy:

- **Offset basis (character, not byte).** PubTator3 BioC offsets are **character**
  offsets into the BioC document text (the concatenation of its passage texts). The
  selector code operates on Python `str` (character indices), so the map is kept in
  **character offsets end-to-end** — there is no byte-index layer. The API response
  is UTF-8 decoded to `str`, **Unicode-normalized to NFC once**, and that single
  normalized form is what we both persist and index; PubTator's offsets are aligned
  to it (re-normalize the API text identically before mapping). A deterministic map
  then exists from a BioC `(passage, local_char_offset, length)` to a character
  range in the `.source.md` **body**.
- **Anchor region.** Quotes, prefixes, and suffixes are sliced **only from the
  persisted passage body**, never from YAML frontmatter or `##` heading lines, and
  `prefix`/`suffix` windows MUST NOT cross a heading or passage boundary. This
  keeps a selector from re-anchoring into a heading and guarantees the `exact`
  text the verifier searches for is present in the body.
- **Provenance for the map.** `.source.md` frontmatter records, per persisted
  passage, its source character-offset base (and section), so the seeder
  reconstructs the offset→character map on re-runs without re-querying. The seeder
  computes `exact`/`prefix`/`suffix` by slicing the persisted body (a `str`) at the
  mapped character range; it never trusts a raw offset against the rendered file.
- **Testing.** The offset→`TextQuoteSelector` conversion test asserts that every
  seeded selector re-resolves against the rendered `.source.md` via the standard
  verifier (i.e. the round-trip through frontmatter+headings holds), not merely
  that the quote substring exists.

### Components

1. **Article-text persistence.** Extend `paper-fetch`
   (`~/d/science/science/src/science_tool/paper_fetch.py`) to normalize and
   persist `.source.md`. When PubTator seeding is intended, the persisted abstract
   is the **BioC passage text** (so PubTator offsets align, per *Offset basis*);
   Europe PMC is the fallback when no BioC record exists. Full text is persisted
   only when the license is whitelisted (see *License gating*). Record
   `text_sha256` + provenance in frontmatter. Abstract is the guaranteed floor;
   full text is best-effort.

2. **PubTator3 seeder** (deterministic CLI, e.g. `science paper annotate-pubtator
   <pmid|doi>`). Query the PubTator3 BioC API
   (https://www.ncbi.nlm.nih.gov/research/pubtator3/api). PubMed-only by design
   (graceful no-op for non-PubMed articles). `source = "pubtator3:<release>"`.
   Two annotation shapes, both span-anchored (the model's `SpecificResource`
   **requires** a `TextQuoteSelector`, so every target is a span):
   - **Entity mentions.** Target = the mention span, converted via the offset map
     above. `annotation_type` = the Biolink class (e.g. `biolink:Gene`); the single
     body is `IriBody(<normalized concept IRI>)` (see *Body encoding* — the
     `merge_planned` pipeline emits exactly one body per row).
   - **Relations.** A PubTator relation links two entity mentions and has no quote
     span of its own. Target = the **evidence sentence/passage span** PubTator
     supplies for the relation; when none is supplied, target the smallest passage
     span containing both mentions. Body carries the subject concept ID, object
     concept ID, and predicate (Biolink or `sci:`). Targeting the two
     entity-mention annotation IRIs directly (a span-less link) would require
     extending the annotation model and is deferred (see *Out of scope*).

3. **Agent extraction skill** (`paper-annotate`). Reads `.source.md` + existing
   PubTator annotations; extracts **propositions / questions / hypotheses** and
   **metaphors / analogies** as span annotations with JSON bodies (see *Body
   encoding*). `source = "llm-annot:<model>"`; idempotent via per-annotation
   `content_hash` + the document-level `text_sha256` short-circuit (see *Dedup*).
   May extend or compose with the existing `paper-researcher` agent.

4. **Promotion path** (decision #4 — deliberate, last). Review statement
   annotations and link/dedupe them into epistemic entities.

### License gating (full-text persistence)

`paper-fetch` records `is_oa` + OA URLs today, not a license identifier
(`paper_fetch.py`). Abstracts are not gated (NCBI / Europe PMC terms permit local
storage of abstracts for research use); **full-text** persistence is gated on an
explicit whitelist, fail-early:

- **Accepted (full text persisted, `license` recorded verbatim):** `CC0`, `CC-BY`,
  `CC-BY-SA`, `CC-BY-ND` and their versioned forms (e.g. `CC-BY-4.0`). This is the
  initial set; extend it in `docs/conventions/annotation-tokens.md`.
- **Unknown / absent / non-whitelisted (incl. `CC-BY-NC*` for now):** persist the
  **abstract only**, omit full text, and record `license` (the raw value or
  `unknown`) plus `fulltext_omitted_reason: license-not-whitelisted`. We never store
  full text we cannot license-verify.
- **Resolution.** License is read from OA-source metadata (Europe PMC `license` /
  Unpaywall `oa_locations[].license`); with multiple values the most-permissive
  whitelisted one wins, else `unknown`.

## Vocabulary (reuse over reinvent)

- **Entities.** PubTator types (gene / disease / chemical / variant / species /
  cellline) → Biolink classes via the existing registry. Motivation
  `oa:identifying`; normalized concept IDs (Entrez / MeSH / dbSNP / NCBITaxon) as
  an `IriBody`.
- **Relations.** PubTator3 relation types (`cause`, `treat`, `interact`,
  `associate`, `positive_correlate`, `negative_correlate`, …) → Biolink
  predicates where they map; a `sci:` predicate otherwise. Motivation `oa:linking`.
- **Statements.** New `sci:annotationType` values `proposition` / `question` /
  `hypothesis`, deliberately mirroring the existing epistemic models so promotion
  is a clean lift. Motivation `oa:classifying`. Body carries the authors' stance /
  polarity.
- **Metaphors / analogies.** New `sci:annotationType` `metaphor` / `analogy`
  with a minimal structured body: `source_domain`, `target_domain`, `mapping`
  (+ optional cue phrase). No external standard exists, so we define this one.

### Vocabulary registration

`annotation_type` is a free `str` on the model today (`annotation/model.py`), with
no enum or registry. The new values (`proposition` / `question` / `hypothesis` /
`metaphor` / `analogy`) and the two new `source` prefixes are registered as
controlled vocabulary in **`docs/conventions/annotation-tokens.md`** (the actual
conventions file — the older annotation spec's reference to
`docs/conventions/annotations.md` is stale; that file does not exist and should be
corrected to point here). If a runtime validation set for annotation types is
introduced, the new values are added there too; until then the conventions file is
the authority.

### Body encoding

The model serializes exactly two body shapes (`annotation/model.py`,
`annotation/io.py::_emit_body`): `IriBody` → `oa:hasBody <iri>`, and
`TextualBody(value, format)` → a blank node with `dc:format` + `rdf:value`. There
are **no structured RDF predicates** for bodies, and `bodies` is a tuple (an
annotation may carry several). The "structured bodies" this spec needs are encoded
within that existing machinery — **no model change**:

- **Entity mentions.** A single `IriBody(<concept IRI>)` for the normalized concept
  ID; the Biolink class goes in `annotation_type` (not a second body), keeping the
  row within the one-body `PlannedAnnotation` / `merge_planned` path.
- **Relations / statements / metaphors–analogies.** A single
  `TextualBody(value=<json>, format="application/json")` carrying a per-type JSON
  object (the `format` field already drives `dc:format`, so this round-trips today):
  - *relation:* `{"subject": <id>, "predicate": <curie>, "object": <id>, "predicate_source": "biolink"|"sci"}`
  - *statement:* `{"kind": "proposition"|"question"|"hypothesis", "stance": ..., "subject"?: ..., "predicate"?: ..., "object"?: ...}`
  - *metaphor/analogy:* `{"source_domain": ..., "target_domain": ..., "mapping": ..., "cue"?: ...}`
- The per-type JSON schemas live alongside the token vocabulary in
  `docs/conventions/annotation-tokens.md` and are validated at emit time.
- **Alternative (deferred).** Promoting these JSON fields to first-class structured
  RDF predicates (queryable in the graph without JSON parsing) would extend the
  annotation model; deferred to a later iteration (see *Out of scope*) — the
  promotion phase (#4) is what surfaces statement content into the epistemic graph
  as real entities, so graph-queryability of the raw body is not needed first.

## Dedup & promotion (decision #4)

- **Within an article.** Re-runs dedupe on the existing key
  `(source, exact, lifted_from, match_text)` (`annotation/audit.py::_annotation_tuple`)
  plus `content_hash` re-audit caching. The two new source prefixes must be
  specified against that machinery:
  - **`pubtator3:<release>`** — `<release>` is the PubTator3 data release string
    read from the BioC response metadata (fallback to a pinned API-version
    constant when absent). `match_text` = the exact mention text for entity
    annotations; for relations, the concatenation `"<subj_id>|<predicate>|<obj_id>"`
    (so two relations over the same evidence span but different predicates do not
    collide).
  - **`llm-annot:<model>`** — `<model>` is the exact model id (e.g.
    `claude-opus-4-8`). `match_text` = the extracted statement/figure's normalized
    text.
  - **Hash-required / re-audit cache.** Both prefixes JOIN
    `HASH_REQUIRED_SOURCE_PREFIXES` (`annotation/model.py`), meaning their
    annotations carry a `content_hash` and participate in the `sci:AuditLedger`.
    `content_hash` keeps its **existing per-annotation semantics** —
    `content_hash(selector.exact, source_version)` (`annotation/hash.py`), assigned
    in `merge_planned` as `content_hash(p.target.selector.exact, p.source_name)`
    (`annotation/audit.py`); **this spec does not change that function.** Here
    `source_version` is the source identity (`pubtator3:<release>` /
    `llm-annot:<model>`), so a re-run at the same release/model re-derives identical
    hashes and the ledger skips already-audited annotations — per-annotation
    idempotency, no document hash involved.
  - **Document-level short-circuit (separate, new).** The `.source.md`
    `text_sha256` is **provenance plus an explicit new pre-pass gate**: before
    re-querying/re-extracting, compare the current `text_sha256` to the value
    recorded at last run and skip the whole document when unchanged. This is a new
    document-level check the seeder/agent owns — it is NOT the audit-ledger key and
    does NOT feed `content_hash`.
- **To epistemic entities.** Promotion matches a candidate statement against
  existing propositions / questions / hypotheses (lexical + embedding similarity,
  then agent judgment) → either **attach as new evidence** to an existing entity
  or **mint** a new one. The annotation gains an `IriBody` pointing at the
  canonical entity; the entity gains a provenance edge ("evidence: paper X, span
  Y"). Extraction stays evidence; promotion is curated — this keeps the epistemic
  graph clean while enabling rival-hypothesis generation and external-question
  capture.

## Phasing

Each phase is independently shippable.

1. **`.source.md` persistence** — the anchor surface + provenance/hash.
2. **PubTator3 seeder** — deterministic entity/relation annotations from the API.
3. **Agent extraction skill** — statements + metaphors/analogies.
4. **Promotion** — link/dedupe statements into epistemic entities.

## Out of scope (fast-follows / future)

- **Extended entities:** phenotype / method / model / formula / dataset-accession,
  including the dataset **source-vs-consumer** role distinction.
- **Domain relation expansion** beyond PubTator's set.
- **Span-less relation targets** (a relation annotation whose `oa:hasTarget` is the
  two entity-mention annotation IRIs rather than an evidence span) — requires
  extending the annotation model's `SpecificResource`, which currently mandates a
  `TextQuoteSelector`.
- **First-class structured RDF bodies** — relation/statement/metaphor content is
  encoded as JSON in a `TextualBody` for this iteration (see *Body encoding*);
  promoting those fields to native RDF predicates would extend the annotation model.
- **Article-level rollups** (key phrases derived from sub-article annotations).
- The **at-scale `lit-annot` pipeline** project (millions of articles).

## Testing

- Offset → `TextQuoteSelector` conversion: every seeded selector **re-resolves via
  the standard verifier** against the rendered `.source.md` (round-trip through
  frontmatter + headings), including NFC-normalized text with non-ASCII characters
  (character-offset alignment, no byte drift).
- PubTator3 BioC response parsing (small real fixture).
- JSON body round-trip: `TextualBody(format="application/json")` serialize → parse →
  equal, and per-type schema validation rejects malformed bodies.
- Idempotency at both layers: per-annotation `content_hash` skip on re-run at the
  same `source_version`, and the document-level `text_sha256` short-circuit skipping
  an unchanged `.source.md` before any API/agent call.
- Identifier → paper-entity resolution: no-match and multi-match both fail loud.
- License gating: a whitelisted license persists full text; unknown / absent /
  `CC-BY-NC*` persists abstract only and records `fulltext_omitted_reason`.
- Sidecar TriG round-trip (serialize → parse → equal).
- Promotion matching (candidate vs. existing epistemic entities).

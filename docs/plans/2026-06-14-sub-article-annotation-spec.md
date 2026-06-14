# Sub-article annotation for `science` papers

- **Status:** Design approved 2026-06-14 (pending spec review → implementation plan)
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

### Data artifacts (per paper entity, under `~/d/science/doc/papers/`)

| File | Role | Status |
|------|------|--------|
| `<citekey>.md` | Human summary (frontmatter + prose) | exists today |
| `<citekey>.source.md` | **New.** Persisted article text — `## Abstract` always; `## Full Text` sections only when an OA-licensed copy is retrievable. Frontmatter: `retrieved_from`, `license`, `text_sha256`, `pmid` / `doi`. | new |
| `<citekey>.source.anno.trig` | **New.** Sub-article annotations anchored into `.source.md` via `oa:TextQuoteSelector`. Reuses the existing annotation system. | new |

Annotations target the **article text**, not our summary — so spans quote the
authors' own words, PubTator3 offsets convert cleanly, and the human summary
stays clean and readable. Persisting normalized text (vs. the raw PDF) is what
makes quote selectors stable and re-anchorable across re-runs.

### Components

1. **Article-text persistence.** Extend `paper-fetch`
   (`~/d/science/science/src/science_tool/paper_fetch.py`) to normalize and
   persist `.source.md`: abstract from Europe PMC / PubTator; OA full text only
   when the license permits. Record `text_sha256` + provenance in frontmatter.
   Abstract is the guaranteed floor; full text is best-effort.

2. **PubTator3 seeder** (deterministic CLI, e.g. `science paper annotate-pubtator
   <pmid|doi>`). Query the PubTator3 BioC API
   (https://www.ncbi.nlm.nih.gov/research/pubtator3/api), emit entity-mention +
   relation annotations, converting API character offsets →
   `oa:TextQuoteSelector` against the persisted `.source.md`. PubMed-only by
   design (graceful no-op for non-PubMed articles). `source = "pubtator3:<release>"`.

3. **Agent extraction skill** (`paper-annotate`). Reads `.source.md` + existing
   PubTator annotations; extracts **propositions / questions / hypotheses** and
   **metaphors / analogies** as span annotations with structured bodies.
   `source = "llm-annot:<model>"`, content-hashed → idempotent (skips unchanged
   text). May extend or compose with the existing `paper-researcher` agent.

4. **Promotion path** (decision #4 — deliberate, last). Review statement
   annotations and link/dedupe them into epistemic entities.

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

## Dedup & promotion (decision #4)

- **Within an article.** Existing `content_hash` + `match_text` keys dedupe re-runs.
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
- **Article-level rollups** (key phrases derived from sub-article annotations).
- The **at-scale `lit-annot` pipeline** project (millions of articles).

## Testing

- Offset → `TextQuoteSelector` conversion (PubTator offsets vs. persisted text).
- PubTator3 BioC response parsing (small real fixture).
- Idempotent re-annotation (content-hash skip).
- Sidecar TriG round-trip (serialize → parse → equal).
- Promotion matching (candidate vs. existing epistemic entities).

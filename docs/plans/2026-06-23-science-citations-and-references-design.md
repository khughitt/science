# Science Citations and References - Design

**Date:** 2026-06-23
**Status:** Draft for review

## 1. Problem

Science projects already have a citation convention:

- Inline prose uses Pandoc-style citations such as `[@Williams2018]`.
- Frontmatter uses `source_refs: ["cite:Williams2018"]`.
- Project notes use graph-visible IDs such as `paper:Williams2018`.
- `papers/references.bib` is the canonical bibliography authority.

Labnote currently renders packaged Markdown literally, so citations such as `[@Shi2025]` leak into
the UI as plain text. This is especially visible on finding detail pages, but the problem is not
MM30-specific. Any Science project rendered through Labnote should get the same citation behavior:
inline numeric references and one generated References section for the current view.

The existing Science implementation already separates the two important concepts:

- `cite:<key>` identifies a bibliography entry.
- `paper:<key>` or `book:<key>` identifies a project-visible note or lightweight graph reference.

The long-term design should preserve that distinction. Labnote should not learn MM30 paper-note
formats, and MM30 should not own custom bibliography export code.

## 2. Goals / Non-Goals

**Goals**

- Define a generic, versioned Science reference-record contract that can serve all Science
  projects.
- Keep `papers/references.bib` as an accepted authoring source while exporting normalized records.
- Export references through app packages so Labnote can render citations without reading BibTeX.
- Render Science/Pandoc citation syntax generically in Labnote Markdown surfaces.
- Generate one page-level References section from the citations actually used in that view.
- Fail visibly for unresolved citations in rendered views and fail closed during normal package
  export.
- Use MM30 Lead 3 only as the first end-to-end fixture, not as a special case.

**Non-Goals**

- No Labnote-side BibTeX parser.
- No MM30-specific citation renderer or exporter.
- No attempt to implement every Pandoc citation feature in the first pass.
- No forced migration from `paper:<key>` to `cite:<key>` or vice versa.
- No requirement that every `paper:<key>` note exists for every bibliography entry.
- No browser-side citation-style engine in the first implementation.

## 3. Existing Science Contract

Science currently treats `papers/references.bib` as the bibliography authority. The relevant code is
in `~/d/science/science/src/science_tool/bibliography.py`.

The current `BibEntry` parser is intentionally lightweight. It:

- reads `papers/references.bib`
- admits only balanced BibTeX entries
- extracts `key`, `entry_type`, `title`, `year`, `doi`, and `url`
- clamps invalid years so synthesized paper/book entities still validate

The graph layer already has `BibAdapter`, which synthesizes lightweight external-reference entities
from the bibliography. This gives graph connectivity for `paper:<key>` and `book:<key>` without
making bibliography entries project-owned Markdown files.

This design extends that idea from graph connectivity to app display. Science remains the authority
for citation identity, validation, and normalization. Labnote receives a ready-to-render reference
bundle.

## 4. Canonical Reference Record

Science should define a versioned `ReferenceRecord` model. It should be CSL-JSON-like, but small
enough to be stable and practical for current projects.

Example:

```json
{
  "contract": "science.references",
  "schema_version": "1",
  "id": "cite:Williams2018",
  "citekey": "Williams2018",
  "kind": "article",
  "title": "Bayesian Meta-Analysis with Weakly Informative Prior Distributions",
  "authors": [
    { "family": "Williams", "given": "Donald R." },
    { "family": "Rast", "given": "Philippe" },
    { "family": "Buerkner", "given": "Paul-Christian" }
  ],
  "issued": { "year": 2018 },
  "container_title": "PsyArXiv",
  "publisher": null,
  "volume": null,
  "issue": null,
  "pages": null,
  "doi": null,
  "pmid": null,
  "url": "https://osf.io/9n4zp/",
  "display": "Williams DR, Rast P, Buerkner P-C. Bayesian Meta-Analysis with Weakly Informative Prior Distributions. PsyArXiv. 2018.",
  "source": {
    "path": "papers/references.bib",
    "entry_type": "article",
    "raw_author": "Williams, Donald R. and Rast, Philippe and Buerkner, Paul-Christian"
  }
}
```

Field semantics:

- `contract`: stable contract name for this bundle family.
- `schema_version`: exact model version. Use the same bare string convention as existing Science
  export contracts such as `GRAPH_EXPORT_SCHEMA_VERSION = "1"`. Consumers must check this before
  using the bundle.
- `id`: stable bibliography ref, always `cite:<citekey>` in v1.
- `citekey`: bare key used by Pandoc citations.
- `kind`: normalized type. Initial values: `article`, `book`, `chapter`, `preprint`, `misc`.
- `title`: normalized title string, or the citekey when absent.
- `authors`: ordered author list. Empty only when unavailable.
- `issued`: publication date subset. At minimum, support `{ "year": 2024 }`.
- `container_title`: journal, proceedings, preprint server, or collection title.
- `publisher`, `volume`, `issue`, `pages`, `doi`, `pmid`, `url`: optional structured metadata.
- `display`: Science-generated fallback bibliography string.
- `source`: source metadata for debugging and validation. For BibTeX sources, include
  `raw_author` when present so name-formatting behavior can be inspected and upgraded later.

The `display` field is load-bearing. Labnote may style structured fields later, but it must always
have a trustworthy string to render when fields are incomplete or a reference kind is unfamiliar.

## 5. Science Parser and Formatter

Science should extend `BibEntry` rather than adding a second bibliography parser. The same
brace-aware balanced-entry scanner should parse additional fields:

- `author`
- `journal`
- `booktitle`
- `publisher`
- `volume`
- `number`
- `pages`
- `pmid`
- `url`
- `doi`

The parser should remain fail-closed for malformed entries:

- Unbalanced entries are excluded from the normalized bundle.
- Duplicate citekeys are errors.
- Invalid years become absent years, not invalid records.
- Missing optional fields remain absent, not empty strings.

Science should also own a conservative numeric-style formatter. The initial formatter does not need
to be a full CSL engine. It only needs stable output for common Science records:

```text
Author A, Author B. Title. Container. Year;volume(issue):pages. doi:...
```

If the record is sparse, the formatter should still emit useful text:

```text
Williams2018. Bayesian Meta-Analysis with Weakly Informative Prior Distributions. 2018.
```

This keeps Labnote out of citation-style rules and makes package output inspectable in tests.

Author formatting is part of the Science contract, not a Labnote concern. V1 should implement a
small deterministic BibTeX-name subset instead of pretending to be a complete BibTeX or CSL engine:

- Split authors on top-level ` and ` tokens, respecting braces.
- Support `Last, First`, `Last, Jr, First`, and `First Last` names.
- Preserve braced or corporate authors as literal display names with no generated initials.
- Generate initials from given names, including hyphenated given names such as `Paul-Christian` ->
  `P-C`.
- Render up to 6 authors. When a record has more than 6 authors, render the first 3 followed by
  `et al.`
- Preserve the raw author string on the normalized record for debugging and future formatter
  upgrades.

Formatter tests should be densest around names because this is the easiest place for an apparently
small citation feature to become unstable.

## 6. Citation Syntax Grammar (v1)

Both Science and Labnote must implement the same citation grammar. Science uses it to scan exported
Markdown for validation; Labnote uses it to render inline citations. A citation that passes export
must render the same key set in Labnote.

V1 supports the current Science/Pandoc subset:

- `[@Smith2020]`
- `[@Smith2020; @Jones2021]`
- `[@Smith2020, p. 42]`
- `Smith et al. [@Smith2020] found that...`

Grammar:

```text
citation_block := "[" citation_item (";" citation_item)* "]"
citation_item  := "@" citekey locator?
locator        := "," <text until ";" or "]">
citekey        := <non-empty text after "@" until whitespace, "," , ";" , or "]">
```

Rules:

- Parse only bracketed citation blocks where the first non-space character after `[` is `@`.
- Split compound citations on top-level semicolons.
- Trim whitespace around citation items.
- Preserve locator text, without the leading comma, for Labnote accessible labels.
- Ignore citation-like text inside code spans and fenced code blocks.
- Treat malformed citation items as unresolved parse errors with visible Labnote output and
  fail-closed Science export.

V1 intentionally does not render the broader Pandoc forms `[see @Smith2020]`, `[cf. @Smith2020]`,
`[-@Smith2020]`, or bare in-text `@Smith2020`. They are unsupported syntax, not ordinary prose.
Science export validation must scan for `@CitekeyLike` tokens outside recognized v1 citation spans
and fail closed with an unsupported-citation-syntax error. Science authoring lint should report the
same pattern early; this can extend the existing prose-lint nearby-BibTeX-token check. Labnote may
also render visible unresolved markers for unsupported forms when handed partial or corrupt package
data, but normal packages must not ship silent literal `@...` citation text.

Science's current `_CITATION_RE = re.compile(r"\[@([^\]]+)\]")` can still be used as the outer
block detector, but Science must split the captured inner text with the same compound-citation and
locator rules as Labnote. Tests should assert parser parity by running a shared corpus of Markdown
examples through both implementations and comparing the extracted citekey set.

The parity corpus should be a single language-neutral JSON fixture owned by Science, for example
`science/tests/fixtures/citation_grammar_v1.json`. Each case should include input Markdown,
expected citations, locators, and unsupported-citation diagnostics. Labnote tests should consume the
same fixture via the normal cross-repo sync path rather than maintaining a hand-copied JS-only copy.

## 7. Package Export Contract

Science should provide a generic reference-bundle builder for Science-backed apps:

```text
references/index.json
```

Shape:

```json
{
  "contract": "science.references",
  "schema_version": "1",
  "style": "numeric",
  "references": {
    "Williams2018": {
      "contract": "science.references",
      "schema_version": "1",
      "id": "cite:Williams2018",
      "citekey": "Williams2018",
      "kind": "article",
      "title": "...",
      "authors": [],
      "issued": { "year": 2018 },
      "display": "..."
    }
  },
  "unresolved": {}
}
```

The map key is the bare citekey because inline citations use bare keys. The embedded record keeps
`id: "cite:<key>"` so the bibliography namespace remains explicit.

`unresolved` is normally empty because production exports fail closed. If a project explicitly
permits partial export, it must include unresolved entries in this shape:

```json
{
  "unresolved": {
    "Missing2026": [
      {
        "citekey": "Missing2026",
        "reason": "unknown-citekey",
        "path": "findings/leads/example.json",
        "field": "sections[2].body",
        "snippet": "... [@Missing2026] ..."
      }
    ]
  }
}
```

Labnote should still render a visible unresolved marker for any cited key missing from
`references`, even when the optional `unresolved` context is absent. The bundle field exists to
transport export-time diagnostics, not to make lookup misses invisible.

This contract targets the MM30-style app export `manifest.json`, not Science's research-package
`datapackage.json` export. Science has two export systems today:

- Research-package exports use a Frictionless-style `datapackage.json` resource list with only
  package-resource fields such as `name` and `path`.
- MM30 app export uses `manifest.json` entries with `kind`, `sensitivity`, `media_type`, `bytes`,
  and `sha256`.

Science should therefore expose a pure builder that returns the `references/index.json` payload and
an app-export descriptor. MM30's `app_export` should call that builder, write the JSON file, compute
the concrete manifest metadata at write time, and register the result in its existing manifest.

The references bundle should be included in MM30-style `manifest.json` as a public JSON bundle:

```json
{
  "name": "references",
  "path": "references/index.json",
  "kind": "bundle",
  "sensitivity": "public",
  "bytes": 1234,
  "sha256": "abc123...",
  "media_type": "application/json"
}
```

`bytes` and `sha256` are required by the existing app-export manifest contract for bundle,
descriptor, and asset resources. They must be computed from the written `references/index.json`
content rather than hardcoded.

Package exporters should scan all exported Markdown-bearing payloads for citation keys and compare
them against the normalized bibliography:

- Known citekeys are exported normally.
- Unknown citekeys should fail export by default.
- If a project explicitly permits partial export, unknown citekeys must appear in an
  `unresolved` block with enough context for Labnote to render visible errors.

Default Science behavior should be fail-closed. A rendered public app with unresolved citations is a
publication-quality defect.

The initial MM30 scanner scope is:

- finding detail Markdown fields: `narrative`, `sections[*]`, `synthesis`, and
  `propositions[*].text`
- entity prose block text exported for Labnote entity pages
- any future app-export field explicitly marked as Markdown by the exporter

This is complementary to existing Science health validation for frontmatter `cite:<key>` references.
Both checks use `papers/references.bib` as the authority: graph health validates project metadata,
and app export validates rendered prose citations.

## 8. Labnote Citation Session

Labnote should add a small citation module, independent of findings:

```js
createCitationSession(referenceIndex) -> CitationSession
renderCitationReferences(session) -> HTMLElement | null
```

The session owns per-view numbering:

- First citation use assigns number 1.
- Repeated citekeys reuse their first number.
- Multiple citations in one bracket render in the order written.
- The References section lists cited records in assigned-number order.

The session should never mutate the reference bundle. It records only view-local citation usage.

## 9. Markdown Citation Rendering

Labnote should support the Citation Syntax Grammar (v1) defined above. The parser should ignore
code spans and fenced code because Markdown rendering already treats those as literal content.

Inline rendering should produce semantic, linkable superscripts:

```html
<sup class="citation">
  <a href="#ref-536d69746832303230" data-citekey="Smith2020">1</a>
</sup>
```

For citation locators such as `p. 42`, Labnote should preserve the locator in a title or accessible
label:

```html
<a href="#ref-536d69746832303230" title="Smith2020, p. 42">1</a>
```

The first implementation may avoid complex compressed ranges. `1,2,3` is acceptable. Range
compression such as `1-3` is optional future polish.

## 10. References Section

Any Labnote view that creates a citation session should append one References section after its
Markdown content:

```html
<section class="references" aria-labelledby="references-heading">
  <h2 id="references-heading">References</h2>
  <ol>
    <li id="ref-536d69746832303230" data-citekey="Smith2020">
      <span class="reference-display">...</span>
      <a href="https://doi.org/...">doi:...</a>
    </li>
  </ol>
</section>
```

Rules:

- Render nothing when no citations were used.
- Use the Science-generated `display` string as the primary text.
- Add DOI/URL links only when fields are present.
- IDs must be deterministic and safe for repeated page renders. Use `ref-` plus the lowercase
  hexadecimal UTF-8 bytes of the bare citekey for `id` and fragment targets; keep the original
  citekey in `data-citekey` for round-tripping and debugging.
- The section should be generic; findings, entity pages, and future views use the same component.

## 11. Unresolved Citations

Unresolved citations must be visible. Labnote should render an inline marker:

```html
<span class="citation-unresolved" data-citekey="Missing2026">[Missing citation: Missing2026]</span>
```

The References section should include an unresolved group or item only if unresolved citations are
present after export. In normal production packages, unresolved citations should not happen because
Science export fails first.

Test fixtures should cover both paths:

- Science export rejects unknown citation keys.
- Labnote renders unresolved markers when deliberately passed an incomplete reference index.

## 12. Integration Surfaces

### Science

Science owns:

- `ReferenceRecord` model
- BibTeX normalization
- display-string formatting
- reference bundle export
- citation validation during export
- the shared Citation Syntax Grammar (v1) test corpus

### MM30

MM30 owns:

- ensuring its `papers/references.bib` contains keys used in exported prose
- wiring the generic Science reference export into `app_export`
- re-exporting and syncing package data

MM30 should not implement a custom reference schema.

### Labnote

Labnote owns:

- loading `references/index.json`
- citation-session numbering
- inline citation rendering
- References section rendering
- visible unresolved-citation UI
- its implementation of the Citation Syntax Grammar (v1), verified against the shared corpus

Labnote should not parse BibTeX, read `entities/papers/*.md`, or know MM30-specific citation
metadata.

## 13. Migration Plan

The implementation should be split into independently reviewable parts:

1. **Science model extension.** Extend `BibEntry` and add `ReferenceRecord` tests.
2. **Science export bundle.** Return the `references/index.json` payload and an app-export
   descriptor; concrete `bytes` and `sha256` metadata are computed by the app exporter that writes
   the file.
3. **MM30 export adoption.** Add the generic references bundle to MM30 `app_export`; re-export and
   sync into Labnote.
4. **Labnote loader.** Load the package reference index as runtime data.
5. **Labnote Markdown rendering.** Add citation replacement and page-level sessions.
6. **Labnote view integration.** Wire sessions into finding detail and entity prose surfaces.
7. **End-to-end fixture.** Use MM30 Lead 3 as the first public package fixture: inline
   `[@Shi2025]`, `[@Elbahoty2024]`, `[@Lindstrom2022]`, and related references render as numeric
   superscripts and a generated References section.

## 14. Testing Strategy

Science tests:

- Parse authors, journal/container, volume, issue, pages, DOI, PMID, URL from BibTeX.
- Parse `Last, First`, `Last, Jr, First`, `First Last`, braced corporate authors, hyphenated given
  names, and `et al.` truncation cases.
- Reject duplicate citekeys.
- Exclude unbalanced entries.
- Format sparse and rich records.
- Export all normalized bibliography references with a stable contract.
- Fail export when exported Markdown contains an unknown citation key.
- Compute app-export manifest `bytes` and `sha256` for `references/index.json`.
- Scan the enumerated app-export Markdown surfaces for inline citations.
- Validate citation-parser parity against Labnote on the shared grammar corpus.
- Fail export for unsupported citation-looking syntax such as `[see @Smith2020]`,
  `[-@Smith2020]`, and bare `@Smith2020`.

Labnote tests:

- `renderMarkdown` converts single and multiple citations when given a session.
- Repeated citekeys reuse numbers.
- Citation locators are preserved in accessible labels.
- Missing citekeys render visible unresolved markers.
- `renderCitationReferences` outputs records in first-use order.
- Findings and entity prose share one session per page, not one session per Markdown block.
- Existing Markdown image hydration still works when citations are present.
- Validate citation-parser parity against Science on the shared grammar corpus.

End-to-end tests:

- Lead 3 page has no literal `[@... ]` citation text.
- Lead 3 page has a References section.
- Inline superscripts link to reference list items.
- Known MM30 citation keys render with non-empty display strings.

## 15. Alternatives Considered

### Labnote parses BibTeX directly

Rejected. It would duplicate Science logic, increase browser bundle complexity, and make every
Labnote deployment depend on bibliography syntax details.

### MM30 exports paper-note frontmatter as references

Rejected as the primary path. Paper notes are project interpretation artifacts. The bibliography
authority is `cite:<key>` in `papers/references.bib`. Paper notes may enrich references later, but
they should not define the generic contract.

### Labnote formats structured fields without a display fallback

Rejected. Sparse and unusual BibTeX entries are common. A Science-generated `display` string gives
Labnote a stable rendering path and keeps citation-style policy upstream.

### Full CSL engine in the first pass

Rejected for the first implementation. The target UI needs numeric references with useful display
strings, not full manuscript-grade bibliography styling. The record shape should remain compatible
with a future CSL-backed formatter.

### Paper/book entity formatter as the only formatter

Rejected as the primary path. `PaperEntity` and `BookEntity` already carry overlapping fields such
as authors, year, venue, DOI, PMID, and URL, and formatter code should be shareable where practical.
However, citation display is governed by normalized bibliography records from
`papers/references.bib`; project paper notes are optional interpretation artifacts.

## 16. Locked Design Decisions

1. `references/index.json` includes all normalized bibliography records, not only records cited by
   exported package prose.

   This keeps the resolver simple, supports citations introduced by view overlays, and mirrors the
   package-asset registry approach. If size becomes a problem later, a cited-only bundle can be a
   new versioned contract.

2. App export owns `references/index.json`.

   Graph materialization can keep its lightweight paper/book nodes. The graph and app exports are
   related but serve different consumers.

3. Unresolved citations are not allowed in normal production package exports.

   Labnote still needs a visible unresolved state for corrupt or partial fixtures, but normal export
   fails closed.

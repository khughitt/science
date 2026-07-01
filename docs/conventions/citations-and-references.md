# Citations And Reference Bundles

Science separates bibliography identity, literature notes, and app-rendered
citations. `papers/references.bib` is the bibliography authority for
`cite:<bibkey>` references. Optional `paper:<bibkey>` or `book:<bibkey>` notes
are project-owned reading or interpretation records; they do not replace the
bibliography authority.

## Reference Records

App-facing reference bundles use the `science.references` contract:

```json
{
  "contract": "science.references",
  "schema_version": "1",
  "style": "numeric",
  "references": {
    "Smith2020": {
      "contract": "science.references",
      "schema_version": "1",
      "id": "cite:Smith2020",
      "citekey": "Smith2020",
      "kind": "article",
      "title": "Example paper",
      "authors": [{"family": "Smith", "given": "Jane"}],
      "issued": {"year": 2020},
      "container_title": "Example Journal",
      "publisher": null,
      "volume": null,
      "issue": null,
      "pages": null,
      "doi": "10.1000/example",
      "pmid": null,
      "url": null,
      "display": "Smith J. Example paper. Example Journal. 2020. doi:10.1000/example.",
      "source": {
        "path": "papers/references.bib",
        "entry_type": "article",
        "raw_author": "Smith, Jane"
      }
    }
  },
  "unresolved": {}
}
```

The top-level `references` map is keyed by bare citekey. Each record keeps the
explicit `id: "cite:<bibkey>"` so consumers do not confuse bibliography refs
with project-owned `paper:` or `book:` notes.

The v1 normalized record is intentionally small and stable:

- `contract` and `schema_version` identify the consumer contract.
- `kind` is normalized from the BibTeX entry type: `article`, `book`,
  `chapter`, `preprint`, or `misc`.
- `authors` preserves ordered family/given components when the lightweight
  BibTeX parser can derive them.
- `issued` currently records the year when available.
- `display` is load-bearing. App consumers may use structured fields for links
  or styling, but the Science-generated display string is the primary fallback.
- `source` records the backing `papers/references.bib` entry type and raw
  author string for debugging formatter behavior.

`build_reference_bundle(project_root)` exports all normalized bibliography
entries, not only entries cited by the current app package. Duplicate citekeys
fail closed before a bundle is produced.

## Citation Grammar

Markdown prose uses a narrow Pandoc-style subset:

```text
[@Smith2020]
[@Smith2020; @Jones2021]
[@Smith2020, p. 42]
```

The v1 grammar is:

```text
citation_block := "[" citation_item (";" citation_item)* "]"
citation_item  := "@" citekey locator?
locator        := "," <text until ";" or "]">
citekey        := <non-empty text after "@" until whitespace, "," , ";" , or "]">
```

Only bracketed citation blocks whose first non-space character after `[` is
`@` are supported. The parser ignores citation-like text inside inline code and
fenced code blocks. Unsupported forms such as `[see @Smith2020]`,
`[-@Smith2020]`, malformed `[@Smith2020 extra]`, and bare `@Smith2020` are
syntax errors for export rather than literal text to ship.

The shared grammar fixture is `science/tests/fixtures/citation_grammar_v1.json`.
Science pins its SHA-256 in `science/tests/test_references.py`; Labnote keeps a
matching fixture and hash so parser drift is visible.

## Export Validation

Science export validation scans public Markdown-bearing payloads before writing
normal app packages:

- known citekeys export normally;
- unknown citekeys raise `UnresolvedCitationError`;
- unsupported citation syntax raises `UnsupportedCitationSyntaxError`, even
  when a partial export mode is allowed;
- source references such as `source_refs: ["cite:Smith2020"]` must resolve
  against `papers/references.bib`.

Partial export callers may deliberately place unknown citekeys under the
top-level `unresolved` map. Normal public exports keep `unresolved` empty
because unresolved citations are publication defects.

## Labnote App Packages

`science labnote export` writes `references/index.json` beside the other public
package bundles and registers it in `manifest.json` as a public JSON bundle:

```json
{
  "name": "references",
  "path": "references/index.json",
  "kind": "bundle",
  "sensitivity": "public",
  "media_type": "application/json"
}
```

The manifest `bytes` and `sha256` values are computed from the written JSON
file. The app renderer consumes the ready-to-render reference index; it should
not parse BibTeX, read project paper-note files, or implement project-specific
citation metadata rules.

Labnote assigns citation numbers per rendered view, reuses the first number for
repeat citekeys, and renders a page-level References section from the citations
actually used in that view. Reference item DOM ids use `ref-` plus the lowercase
hex encoding of the UTF-8 citekey bytes, while `data-citekey` preserves the
original key.

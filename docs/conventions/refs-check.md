# `science refs check`

Validates references across the project: hypothesis IDs, citations, markdown
links, DOIs, PMIDs, typed entity refs in frontmatter, and (with
`--include-body`) typed entity refs in body prose.

## Default behavior

Scans `paths.doc_dir` (default `doc/`), `paths.entities_dir` (default
`entities/`), and root `README.md`. The body-prose typed-ref scan
(opt-in via `--include-body`) validates against the frontmatter `id:`
sweep — a walk over every markdown file's `id:` field, collecting
`<kind>:<slug>` strings whose kind is in the canonical local-entity-kinds
set.

## Project config

`science.yaml` may include an optional `refs:` block:

```yaml
refs:
  # Truth source for body-prose entity-ref validation (--include-body).
  #   frontmatter      — walk markdown frontmatter for `id:` (default)
  #   knowledge_graph  — parse `knowledge/graph.trig` (built by `science graph build`)
  entity_index_source: knowledge_graph

  # Extra dirs to scan beyond paths.doc_dir + paths.entities_dir.
  # The special value "." means root-level .md files only (non-recursive).
  scan_roots:
    - tasks
    - papers
    - core
    - "."
```

Defaults: no `refs:` block → frontmatter source, no extra scan roots.

### `entity_index_source`

`frontmatter` is the safe default — it works for any project regardless of
whether the knowledge graph has been built and stays current with editor
saves. `knowledge_graph` is more accurate for projects that maintain a
`knowledge/graph.trig` index as the canonical entity registry, since that
index can include entities that aren't backed by a single markdown file.

When `knowledge_graph` is configured but `knowledge/graph.trig` is missing
or empty, `science refs check` writes a one-line warning to stderr and
falls back to the frontmatter sweep — the check still runs.

### `scan_roots`

Each entry is a directory under the project root. The default scan
(`doc/`, `entities/`) covers the common Science-managed authoring locations,
but projects often keep additional prose in `tasks/`, `papers/`, root-level
`README.md`/`CLAUDE.md`/`AGENTS.md`, or project-specific dirs like `core/`.

The special value `"."` means "include root-level `.md` files (non-recursive)"
and is the recommended way to pull in the canonical guide files
(`README.md`, `CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`, etc.) without
recursing into worktree or build artifacts that may live at the root.

Files surfaced through `_SCAN_FILES` (currently just `README.md`) are
already included by default — duplicates are de-duplicated automatically.

## Tooling

- `science refs check` — default scan; reports broken refs with file:line.
- `science refs check --include-body` — also scans body prose for typed
  `<kind>:<slug>` refs against the configured truth source.

## Literature References

Use `paper:<bibkey>` for external literature notes and `cite:<bibkey>` for
bibliography/source references. Use `manuscript:<slug>` for the project's own
publication drafts.

Bibkey extraction is deliberately simple and shared by literature consumers:
the bibkey is the full substring after the first `:`. Comparisons are
case-sensitive and byte-for-byte. There is no lowercasing, whitespace trimming,
or suffix folding. `paper:Smith2024` and `cite:Smith2024` share the bibkey
`Smith2024`; `paper:smith2024` does not.

Use `paper:<bibkey>` for external literature references. `article:<bibkey>` is
not a literature-reference prefix; `article` remains reserved for article
entities only.

Inline Markdown citations for app export use the narrow v1 citation grammar
documented in [Citations And Reference Bundles](citations-and-references.md).
That export-time check is complementary to `science refs check`: `refs check`
answers whether project references resolve, while the app exporter answers
whether public Markdown can be rendered as numeric citations from
`references/index.json`.

## Related

- [`science prose lint`](prose-lints.md) — separate lint group for citation
  gaps and authoring patterns. Where `refs check` answers "does this ref
  resolve?", `prose lint` answers "is this prose well-anchored?".
- `audit-citations.ts` (natural-systems, t469) — project-local script that
  this feature is designed to replace. With
  `entity_index_source: knowledge_graph` and
  `scan_roots: [tasks, papers, core, "."]`, `science refs check --include-body`
  reproduces that script's behavior.

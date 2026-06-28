# Graph And Derived State

Science builds graph state from authored project sources.

```bash
science graph build
science graph dashboard-summary
science belief snapshot
```

## Graph Build

`science graph build` materializes project sources into graph files under
`knowledge/`. The graph is a derived view over source-authored entities,
bibliography records, structured sources, and project configuration.

Do not edit `knowledge/graph.trig` as the durable fix. Correct the source and
rebuild.

Inquiry graphs are also derived views. The graph-backed inquiry source is a
`patch-definition` file with `patch_type: inquiry` under `entities/patches/`;
`science graph build` compiles it into a dedicated `sci:Inquiry` named graph and
patch-membership layer. Use `science inquiry show` and `science inquiry
validate` to read the compiled view.

For local cleanup in a project that declares peers, use:

```bash
science graph build --local-only
```

This refreshes `knowledge/graph.trig` and leaves `knowledge/composite.trig` untouched.
Use the default `science graph build` when you intentionally want to refresh the
peer-composed graph.

## Dashboard Summaries

Dashboard summaries are compact readings of the current graph: unresolved
references, evidence status, graph hygiene, and project orientation. They help
agents and humans decide where to work next.

## Public Snapshot Distillation

`science distill` creates small Turtle snapshots from public knowledge graph
sources that are too broad to author by hand. These snapshots are generated
artifacts, not project source files.

Use distillation when a project needs a compact reference layer for browsing,
orientation, or graph queries:

```bash
science distill openalex --level subfields
science distill openalex --level topics
science distill pykeen DBpedia50
science distill pykeen PrimeKG --budget 170
```

OpenAlex distillation writes a SKOS-style science hierarchy. PyKEEN
distillation writes a compact RDF view of a named PyKEEN dataset; `--budget`
keeps the highest-rank entities and edges between them for large datasets. If
no `--output` is supplied, snapshots are written under `data/snapshots/`.

Each distillation updates `data/snapshots/manifest.ttl` with the source URL,
version string, generation time, node/triple count, and SHA-256 of the Turtle
file. Treat the manifest as the reproducibility record for generated snapshots.

## Snapshot Import

`science graph import` merges a Turtle snapshot into the project's
`graph/knowledge` layer and records import provenance in `graph/provenance`:

```bash
science graph import data/snapshots/openalex-science-map.ttl
science graph import data/snapshots/primekg-core.ttl
```

Import is additive derived state. If the imported context is wrong or stale,
regenerate the snapshot or rebuild the graph rather than editing
`knowledge/graph.trig` directly.

## Belief Snapshots

`science belief snapshot` appends reproducible belief-state rollups to
`knowledge/belief-snapshots.jsonl`. Use snapshots at review milestones when you
want to preserve the state of support, dispute, fragility, and contestation.

## Prose-Derived Reports

When a project uses prose epistemics, decomposition, grounding, and prose health
artifacts are also derived state. They summarize how much authored prose has
been decomposed, promoted, and grounded. They do not replace the source
Markdown, propositions, or evidence lines.

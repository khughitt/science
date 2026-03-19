# Files To Remove

This list tracks code and documentation that should be removed once the layered KG model is fully landed and verified.

## Science Repo

1. Any command guidance that treats `knowledge/graph.trig` as a primary authoring target rather than generated output.
2. Any residual short-ID migration shims left in command docs after canonical ID migration is complete.

## `science-model`

1. Temporary alias helpers that only exist to bridge legacy `H01`/`Q05`-style references.
2. Any duplicated entity or relation registries left outside the new profile modules.

## `science-tool`

1. Direct TriG mutation paths that bypass structured upstream sources.
2. Legacy graph mutation commands or code paths that cannot preserve canonical IDs and layer semantics.
3. Ad hoc relation/type registries duplicated from `science-model`.

## `science-web`

1. Hardcoded graph type maps once type/profile metadata comes from `science-model`.
2. Any UI assumptions that tasks are not graph entities.

## Project Repos

1. Legacy short-form references in task files and document frontmatter after canonical migration is complete.
2. Project-local manual graph fragments that duplicate structured `project_specific` sources.
3. Stale provenance references to superseded source files such as legacy consolidated question documents.

## Removal Gate

Only remove the items above after:

1. canonical IDs resolve across docs, tasks, RDF, and API payloads,
2. graph rebuilds are deterministic, and
3. verification passes in `science-model`, `science-tool`, `science-web`, and at least one migrated project.

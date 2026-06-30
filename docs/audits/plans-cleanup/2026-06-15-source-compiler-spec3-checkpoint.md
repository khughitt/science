# Source Compiler Spec 3 Checkpoint

This checkpoint preserves the durable rationale from the June 15 Spec 3 source
compiler plan cluster. The implementation is now represented by code, tests, and
user-guide documentation, so the original plan files no longer need to sit in
`docs/plans/` as active work.

## Completed Slices

Spec 3 landed as three keystone slices:

- Adapter policy: adapter-specific load behavior is declared on
  `StorageAdapter` hooks instead of being hard-coded as adapter-name branches in
  the load loop.
- Source snapshot freshness: local Markdown-backed entity files produce
  `SourceSnapshot` provenance and current/latest `SourceChange` state for
  freshness derivation.
- Compiler phase split: audit and materialization share a source-load/audit path,
  then materialization continues through emit, derive, and write phases.

## Adapter Policy

The shared adapter policy surface is:

- `participation_mode`
- `skip_core_on_missing_identity`
- `should_defer(already_owned=...)`
- `source_document(ref, raw)`
- `on_owner_declared(...)`
- `deferred_dataset_datapackage(...)`

Loader-owned mutations remain in the loader. Adapters return typed policy
payloads and declarations, while `sources.py` owns identity-table updates,
source-record capture, deferral bookkeeping, and owner declarations. This keeps
adapter-specific behavior near each adapter without letting adapters mutate
shared loader state.

`classify_owner_scope(adapter.name, ...)` intentionally remains centralized
because non-adapter loaders need the same owner-scope policy. The adapter policy
split was about adapter-specific source behavior, not about making every source
compiler decision adapter-local.

`source_records.py` is the leaf home for cross-phase source records:
`MarkdownSourceDocument`, `AggregateRowMeta`, `SourceSnapshot`, and
`SourceChange`.

## Source Snapshots

`SourceSnapshot` is compiler/provenance state, not a truth-apt authored entity.
It records the project-relative source path and the raw file SHA-256 for loaded
local Markdown-backed entities. Snapshot nodes bear on the backed entity using
the normal depth-1 `BearsOnEdge` path, and freshness consumes the emitted
`source_changes` map. Source-change freshness stays distinct from date-driven
freshness triggers.

The first observation establishes a baseline and does not mint a
`SourceChange`. A later changed hash mints one current/latest `SourceChange`
with the observed date. An unchanged rebuild carries the prior snapshot and
latest-change event forward without date churn. The graph does not persist a
full source-change event log.

Snapshot observation runs even when freshness-state derivation is disabled so
baseline continuity is preserved if freshness checks are re-enabled later.

The current snapshot scope is intentionally narrow: loaded local Markdown-backed
entities only. Aggregate rows, datapackages, remote APIs, DOI records, Zenodo
records, and dataset manifests remain deferred fill-outs.

## Compiler Phases

The compiler phase contract is:

```text
Load -> Audit -> Emit -> Derive -> Write
```

`science graph audit` stops after Load and Audit. It reports audit findings
without running the materialize-only preflight, deriving graph layers, or writing
`knowledge/graph.trig`.

`science graph build` runs the full sequence. It hard-gates on audit failures
before emit, derive, or write. The materialize-only preflight remains outside
`stop_after`, so strict builds can block on legacy project-root data-package
owners while audit-only runs can still report references without requiring a
materialization-ready project.

`build_dataset_from_sources(ProjectSources)` is the pure in-memory build path:
it is load/audit-free and filesystem-write-free.

## Deferred Follow-Ups

The plan cluster named several future fill-outs that remain outside this
checkpoint:

- unify `io.py` and revision-manifest handling where that reduces duplication;
- add richer source-revision coordinates beyond raw SHA-256;
- snapshot remote, aggregate, datapackage, DOI, Zenodo, and dataset-manifest
  source surfaces;
- consider mechanically extracting more phase code from `materialize.py` if that
  makes the compiler easier to maintain.

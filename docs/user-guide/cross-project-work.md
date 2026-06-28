# Cross-Project Work

Science projects can recognize peers, compose graphs, and synchronize shared
knowledge. Peers are declared project namespaces in `science.yaml`.

Cross-project work has three separate surfaces:

- `peers:` in a project `science.yaml` declares local names for other projects.
  Peers are the addressing and graph-composition surface.
- The global registry under the Science config directory records registered
  projects, registry indexes, and sync state. Sync is an inspection/indexing
  surface, not an authoring surface.
- Commons stores reusable canonical owners. Project overlays can borrow commons
  entities without making the local project the canonical owner.

## Peers and Federation

Peer ids are project-local namespace aliases. Use them when a project needs to
refer to another project's sources or compose its graph with known neighbors.
Cross-project refs use the explicit form `<project-id>:<kind>:<slug>` when the
target is outside the current project.

Useful peer inspection commands:

```bash
science peers list
science peers check
science peers show <peer-id>
```

Graph composition follows the peer declarations. `knowledge/graph.trig` is the
local generated graph for one project. `knowledge/composite.trig` is generated
for the host project from the host `graph.trig` plus each declared peer's local
`graph.trig`. Composite assembly never reads a peer's `composite.trig`, so
bidirectional or nested peer declarations do not recurse through an already
composed graph.

## Registry Sync

`science sync` works from the global Science config directory. The directory is
resolved from `SCIENCE_CONFIG_DIR`, then `$XDG_CONFIG_HOME/science`, then
`~/.config/science`.

The durable file contract is:

- `config.yaml` stores registered projects, sync settings such as
  `stale_after_days`, and commons settings.
- `registry/entities.yaml` stores the cross-project entity index.
- `registry/relations.yaml` stores the cross-project relation index.
- `sync_state.yaml` stores the last sync time plus per-project entity counts and
  entity hashes.

Projects are registered by path as Science commands encounter them. Registration
is idempotent for the resolved path, normalizes stored paths, and can prune
missing projects during rebuild.

Sync commands:

```bash
science sync status
science sync run
science sync projects
science sync rebuild
```

`science sync run` scans registered project sources and writes the registry
entity/relation indexes and sync state. `--dry-run` reports the same alignment
without writing. `science sync rebuild` prunes missing projects, clears the
registry indexes, and rebuilds them from registered projects.

The registry is a rebuildable index, not a source of truth. Durable project
meaning remains in authored project sources or in commons-owned canonical
records. Registry entity ids are namespaced as `<project-name>::<canonical-id>`
to avoid false matches between unrelated project-local ids. Sync also reports
drift warnings for project-scope id collisions, incompatible shared metadata,
and primary external-id collisions.

Registry sync does not propagate Markdown files, author new source records, or
perform real-time exchange between projects. Older `sync_source` frontmatter can
still be parsed as provenance vocabulary, but the current steady-state sync
contract is registry indexing and drift inspection.

## Commons and Overlays

Use commons when an entity should have a reusable canonical owner outside an
individual project. The commons root resolves from `SCIENCE_COMMONS_ROOT`, then
`commons.root` in the global config, then `~/d/science-commons/`. Bulk data
roots similarly resolve from `SCIENCE_COMMONS_DATA_ROOT`, then
`commons.data_root`, then `/data/science-commons/`.

Projects borrow commons records through local overlays. Overlay files keep
project-specific context local while pointing `overlay_of` at the commons
canonical owner.

Cross-project work follows the same model as within-project work: authored
source records remain the durable basis, and derived graph views are rebuilt.
Federation connects patches, projects, and project collections without erasing
local context.

For the deeper model, see [`docs/federation.md`](../federation.md).

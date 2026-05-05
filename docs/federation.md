# Federation v1.0

Federation lets one Science `meta` project act as an umbrella over related child projects without moving ownership of
claims, data, tasks, or graph files out of those children. The model is file-based and read-only: child commands write
only child files, and meta commands write only meta files.

The initial role taxonomy is:

| Role | Meaning |
|---|---|
| `meta` | Umbrella integration, foundational questions, and cross-project synthesis |
| `cancer-type` | One cancer or natural cancer grouping studied in depth |
| `data-source` | Pipeline or evidence stream feeding other projects |
| `mechanism` | Biological process recurring across projects |
| `condition` | Disease state adjacent to the umbrella topic |

`role` is intentionally extensible. Unknown role strings are accepted so future umbrellas can add roles such as
`model-system`, `host-context`, or `methodology` without changing the schema first. The source design is currently
`~/d/r/cbioportal/doc/plans/2026-04-30-cancer-meta-project-design.md`; once the cancer umbrella is materialized, keep the
living design under `~/d/cancer/meta/doc/plans/`.

## `science.yaml` Additions

All projects may declare:

```yaml
id: cbioportal
role: data-source
parent: ~/d/cancer/meta
```

`id` is the stable project identifier used in cross-project references. If omitted, `science-tool` defaults it to the
project directory name. `role` defaults to `standalone`. `parent` is optional and points from a child back to its meta
project.

Only `role: meta` projects may declare `children:`:

```yaml
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella: cancer and pre-cancer."
children:
  - id: cbioportal
    path: ~/d/cancer/data-sources/cbioportal
    role: data-source
  - id: multiple-myeloma
    path: ~/d/cancer/cancer-types/multiple-myeloma
    role: cancer-type
  - id: evolution
    path: ~/d/cancer/mechanisms/evolution
    role: mechanism
  - id: pre-cancer
    path: ~/d/cancer/conditions/pre-cancer
    role: condition
```

The meta `children:` manifest is authoritative for federation membership. A child's `parent:` is a validated
back-reference, not the source of truth.

## Canonical Paths

Paths stored in `science.yaml` should be tilde-prefixed home-relative paths, such as:

```yaml
parent: ~/d/cancer/meta
children:
  - id: cbioportal
    path: ~/d/cancer/data-sources/cbioportal
    role: data-source
```

At use sites, `science-tool` resolves paths with `Path.expanduser().resolve()` before comparison. This makes symlink forms
such as `~/d/cancer/...`, `/home/keith/d/cancer/...`, and `/mnt/ssd/Dropbox/cancer/...` comparable without storing
machine-specific physical paths in manifests.

## Addressing

Canonical cross-project entity references use namespace-first form:

```text
<project-id>:<kind>:<slug>
```

Examples:

- `cbioportal:question:q014`
- `multiple-myeloma:hypothesis:h003`
- `evolution:task:t012`
- `cbioportal:topic:clonal-hematopoiesis-contamination`

The first segment is a federation project ID from the meta project's `children:` manifest or the current project's own
`id`. The remaining segments are the target project's normal local entity reference.

Local refs stay local by default:

- `task:t123`
- `hypothesis:h01`
- `question:q006`

Bare task shorthand such as `t123` always means a local task. It never names another project.

Artifact addresses remain two-part or path-style addresses when the target is a file-like artifact rather than a
canonical entity. For example, `cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address, while the
canonical topic entity ref is `cbioportal:topic:clonal-hematopoiesis-contamination`.

Two-part entity shorthand such as `cbioportal:q014`, `multiple-myeloma:h003`, or `evolution:t012` is legacy and non-canonical.
Migrate those references to explicit entity form, such as `cbioportal:question:q014`,
`multiple-myeloma:hypothesis:h003`, or `evolution:task:t012`.

Graph URI form is:

```text
<cancer://project-id/artifact-id>
```

## Federated Graphs

For `role: meta`, `science-tool graph build` runs two phases:

1. Standard local graph materialization for the meta project.
2. Federation assembly that re-reads meta's local `knowledge/graph.trig`, reads each child's `knowledge/graph.trig`, and
   writes the federated result back to meta's `knowledge/graph.trig`.

The federated output contains one named graph per project:

- `cancer://meta` for umbrella-local triples and federation provenance.
- `cancer://<child-id>` for each included child.

Child graph inputs are parsed as TriG datasets, preserving all child named-graph layers before collapsing them into the
child's single federated named graph. The meta graph also records provenance with `prov:wasDerivedFrom` pointing at the
child graph file and `prov:generatedAtTime` recording assembly time.

Federation is read-only. It does not write into child projects, push meta triples down, or create a live SPARQL endpoint.

## CLI

Validate a meta project's child manifest against child back-references:

```bash
science-tool federation validate
```

Render a simple umbrella rollup:

```bash
science-tool federation status
```

`/science:status` dispatches to `science-tool federation status` when the current project declares `role: meta`. Non-meta
projects keep the existing per-project status flow.

## Deferred

The following are intentionally out of scope for v1.0:

- Federated `big-picture` and `next-steps` rollups.
- Automated cross-project address resolution and link checking.
- Bidirectional sync or meta-to-child task proposal writes.
- Promotion tooling for turning a topic into a child project.
- A SPARQL endpoint over the federated graph.
- Cross-federation graph lints for coreference and role conflicts.
- Any graph federation writes into child projects.

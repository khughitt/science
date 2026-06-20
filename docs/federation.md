# Peers And Addressing

This document is the current reference for cross-project addressing in Science.
The filename is retained for existing links; the current model is a decentralized
peer graph, not an umbrella/child tree. For the full design rationale, see
`docs/superpowers/specs/2026-05-05-project-peers-design.md`.

## Entity References

Canonical entity references use:

```text
[<project-id>:]<kind>:<slug>
```

The explicit namespaced form is:

```text
<project-id>:<kind>:<slug>
```

Local references omit the project namespace and resolve in the current project:

- `task:t123`
- `hypothesis:h01`
- `question:q006`

Namespaced cross-project references include the target project's ID first:

- `cbioportal:question:q014`
- `multiple-myeloma:hypothesis:h003`
- `evolution:task:t012`
- `cbioportal:topic:clonal-hematopoiesis-contamination`

Bare task shorthand such as `t123` always means a local task. It never names
another project.

Artifact addresses remain two-part or path-style addresses when the target is a
file-like artifact rather than a canonical entity. For example,
`cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address,
while the canonical topic entity ref is
`cbioportal:topic:clonal-hematopoiesis-contamination`.

Two-part entity shorthand such as `cbioportal:q014`,
`multiple-myeloma:h003`, or `evolution:t012` is legacy and non-canonical.
Migrate those references to explicit entity form, such as
`cbioportal:question:q014`, `multiple-myeloma:hypothesis:h003`, or
`evolution:task:t012`.

Graph URI form for artifact addresses remains:

```text
<cancer://project-id/artifact-id>
```

## Project IDs And Character Rules

Every project has a stable `id:` in `science.yaml`. Cross-project refs use that
ID as the namespace segment.

Project IDs follow the character rules in Decision 1 of
`docs/superpowers/specs/2026-05-05-project-peers-design.md`: the project segment
matches `[a-z][a-z0-9-]{1,63}`. The slug/artifact segment also reserves `@`, so
`@<version>` can be added later without conflicting with existing refs.

## Declaring Peers

Each project declares the other project IDs it recognizes in `science.yaml`:

```yaml
id: evolution
role: mechanism
peers:
  - id: mm30
    path: ~/d/cancer/mm30
  - id: lit-explore
    path: ../../r/lit-explore
```

`peers:` is the namespace table for cross-project refs authored in this project.
If `mm30` is declared as a peer, `mm30:task:t015` is a recognized
cross-project entity ref. If it is not declared, the ref is reported as an
unknown namespace. Use a local ref instead when the target entity belongs to the
current project.

Peer paths are local filesystem paths to project roots. They may be absolute,
`~`-anchored, or relative to the declaring project root. The authored path is
preserved in `science.yaml`; commands resolve it at runtime.

## Graph Outputs

Science separates local graph materialization from peer composition:

| File | Contents | Writer |
|---|---|---|
| `knowledge/graph.trig` | Local project graph only | `science graph build` local materialization |
| `knowledge/composite.trig` | Host local graph plus peers' local graphs | composite assembly when peers exist |

Composite assembly reads the host project's `knowledge/graph.trig` and each
peer's `knowledge/graph.trig`. It never reads a peer's
`knowledge/composite.trig`; this prevents recursive composition and keeps build
order irrelevant.

If a peer has `knowledge/composite.trig` but no `knowledge/graph.trig`, composite
assembly treats the peer's local graph as missing instead of reading the
composite file.

## CLI

The current peer commands are:

```bash
science peers list
science peers check
science peers show <peer-id>
```

- `science peers list` shows declared peers, resolved paths, and status.
- `science peers check` validates peer entries and reports structured issues.
- `science peers show <peer-id>` displays one resolved peer's declared ID,
  project ID, name, role, and path.

## Historical Context

Older Science projects used umbrella-child config fields with
`science federation ...` commands for status and validation. Those fields and
commands described a tree-shaped relationship and are no longer supported.
Use `peers:` directly; the legacy parent/children fields are not migrated
automatically.

# Source Entity CLI Design

**Date:** 2026-04-28
**Status:** Draft for review

## Problem

Science projects already use many first-class entities: questions, hypotheses,
discussions, interpretations, reports, specs, concepts, datasets, workflows,
domain objects, and project-specific domain objects. These entities are usually
authored as markdown/frontmatter or structured source records and then
materialized into `knowledge/graph.trig`.

There is already a `science-tool graph add ...` command family, but those
commands mutate the materialized graph directly. They are useful for graph-level
experiments and legacy workflows, but they are not the right surface for routine
project-source authoring because the durable source of truth is the project
source file, not `graph.trig`.

Tasks recently moved toward CLI-routed lifecycle operations so edits are
consistent and journalable. The same principle should apply to source-authored
entities.

## Goals

- Add a generic `science-tool entity` CLI for source-authored project entities.
- Keep `knowledge/graph.trig` as a materialized artifact, not the write target
  for `entity create`.
- Support a broader initial set of high-use authored entities:
  `question`, `hypothesis`, `discussion`, and `interpretation`.
- Provide common operations:
  - `entity create`
  - `entity show`
  - `entity edit`
  - `entity note`
  - `entity list`
  - `entity neighbors`
- Add thin typed wrappers where they improve ergonomics:
  - `science-tool question create ...`
  - `science-tool hypothesis create ...`
  - `science-tool discussion create ...`
  - `science-tool interpretation create ...`
- Explicitly distinguish three entity classes:
  1. Science project/meta entities.
  2. Science domain entities.
  3. Project-specific domain entities.
- Validate writes by reloading project sources through the existing
  registry/adapters path.

## Non-Goals

- Do not replace existing `graph add ...` commands in this increment.
- Do not write new source entities directly into `knowledge/graph.trig`.
- Do not build a database or index cache.
- Do not implement full ontology/authority lookup in the first increment.
- Do not mutate complex project-specific YAML aggregate files in the MVP.
- Do not fold `tasks` into the generic entity CLI until the entity source API
  is stable.

## Existing System

Current relevant pieces:

- `science-tool graph add ...` has graph-level commands for concepts,
  hypotheses, questions, propositions, findings, interpretations, discussions,
  stories, mechanisms, papers, and inquiry objects.
- Those commands write RDF triples through `science_tool.graph.store`.
- Source materialization reads project source files through storage adapters:
  - markdown/frontmatter from `doc/`, `specs/`, and `research/packages`
  - task files
  - datapackage records
  - aggregate YAML records
- `EntityRegistry.with_core_types()` registers core kinds, including generic
  project kinds such as `question`, `hypothesis`, `interpretation`,
  `discussion`, `plan`, `report`, `spec`, and typed classes such as `task`,
  `dataset`, `workflow-run`, `research-package`, and `mechanism`.
- Projects can register profile, catalog, and extension kinds through local
  profiles and ontology catalogs.

## Entity Classes

### 1. Science Project/Meta Entities

Examples:

- `question`
- `hypothesis`
- `discussion`
- `interpretation`
- `plan`
- `report`
- `spec`
- `task`

These are authored project artifacts. They usually live as markdown files with
YAML frontmatter.

Initial MVP support:

- `question` -> `doc/questions/<slug>.md`
- `hypothesis` -> `specs/hypotheses/<slug>.md`
- `discussion` -> `doc/discussions/YYYY-MM-DD-<slug>.md`
- `interpretation` -> `doc/interpretations/YYYY-MM-DD-<slug>.md`

Tasks remain on the existing task backend for now. A later increment can expose
task operations through the same conceptual API once the source entity API is
stable.

### 2. Science Domain Entities

Examples:

- ontology-backed biology, chemistry, physics, units, math, earth, astronomy,
  and information entities
- stable shared concepts with external authorities

Creation should be conservative. If the entity can be represented by an
existing ontology/catalog term, the CLI should prefer linking/registering the
existing authority rather than inventing a local `concept:*`.

The first increment should validate that the target kind is registered and
should point users toward the entity creation cookbook when a local concept is
not the right representation. Full authority search/import is deferred.

### 3. Project-Specific Domain Entities

Examples from projects such as `natural-systems`:

- local model classes
- morphism types
- primitive families
- formula or composition structures
- other project-defined domain kinds

These should be allowed only when the project registers the kind through its
local profile/manifest or extension mechanism.

The MVP should support markdown-authored project-specific kinds when the kind
has a simple path rule. Mutation of existing aggregate YAML source files is
deferred because those files often have kind-specific structure and relations
that require specialized writers.

## CLI Shape

Generic commands:

```bash
science-tool entity create <kind> <title> [--id <kind:slug>] [--status <status>] [--related <ref>] [--source-ref <ref>]
science-tool entity show <ref>
science-tool entity edit <ref> [--title ...] [--status ...] [--related ...]
science-tool entity note <ref> <note> [--date YYYY-MM-DD]
science-tool entity list [--kind <kind>] [--status <status>] [--format table|json]
science-tool entity neighbors <ref> [--hops 1] [--format table|json]
```

Typed wrappers:

```bash
science-tool question create "<question text>" [--id question:q102-slug] [--related hypothesis:h01]
science-tool hypothesis create "<title>" [--id hypothesis:h08-slug]
science-tool discussion create "<title>" [--focus question:q102-slug]
science-tool interpretation create "<title>" [--input results/path]
```

Typed wrappers call the same generic core. They should not duplicate writers or
validation rules.

## Source Writing

Add a focused source entity module at `science_tool/entities_cli.py` for the
MVP. If later increments add complex YAML aggregate writers or ontology import,
that can be split into a package then.

Core responsibilities:

- resolve the project root
- load project config/profile/kind registry
- resolve entity kind policy
- select output path
- generate a canonical id when omitted
- render markdown frontmatter and body from a kind template
- update frontmatter fields for `edit`
- append dated notes for `note`
- reload project sources after write to catch invalid shape or identity
  collisions

The implementation should prefer structured YAML parsing/rendering for
frontmatter over ad hoc string manipulation.

## Path Policy

Initial built-in path rules:

| Kind | Path |
|---|---|
| `question` | `doc/questions/<slug>.md` |
| `hypothesis` | `specs/hypotheses/<slug>.md` |
| `discussion` | `doc/discussions/YYYY-MM-DD-<slug>.md` |
| `interpretation` | `doc/interpretations/YYYY-MM-DD-<slug>.md` |

For other markdown-authored registered kinds, the MVP requires an explicit
`--path` until a stable path rule exists.

If a target file already exists, `create` fails early and does not overwrite.

## Notes

Use the same note section grammar as the task note workflow where possible:

```markdown
### Notes

- 2026-04-28: Clarification text.
```

Notes are append-only by insertion order, not sorted by date. `--date` allows
backfills and future-dated planning notes.

`entity note` edits the source file, updates `updated: YYYY-MM-DD` when present,
and then reloads project sources to verify the edited entity remains valid.

## Editing

`entity edit` should support conservative frontmatter edits first:

- `--title`
- `--status`
- `--related`, repeatable
- `--source-ref`, repeatable
- `--updated YYYY-MM-DD`

Replacing body content or opening an editor is deferred. The first version
should avoid ambiguity between journal notes and wholesale document rewriting.

## Neighbors

`entity neighbors <ref>` is read-only.

It should use existing graph/source query machinery to show immediate
relationships around an entity. It can build or load the materialized graph,
but it should not mutate source files.

For MVP, one-hop neighbors are enough. Multi-hop traversal can reuse the
existing `graph neighborhood` behavior later.

## Validation

After create/edit/note:

1. Reload project sources with `load_project_sources(project_root)`.
2. Confirm the target canonical id exists.
3. Let existing validation catch:
   - unknown kinds
   - malformed frontmatter
   - identity collisions
   - kind/type mismatch
   - invalid registered schema

Validation errors fail loudly. The writer should not silently fall back to an
unknown or local concept kind.

## Error Handling

- Unknown kind: fail with registered-kind guidance.
- Existing destination path: fail, do not overwrite.
- Duplicate canonical id: fail.
- Missing entity for show/edit/note/neighbors: fail and list searched source
  roots.
- Unsupported writer for registered kind: fail with guidance to use `--path`
  or a future specialized command.
- Invalid note text: reject empty or whitespace-only notes.
- Invalid date: reject non-ISO dates.

## Migration And Compatibility

Existing `graph add ...` commands stay in place. The new `entity` commands are
for source authoring, not graph patching.

No existing project files are migrated in the first increment.

For projects such as `natural-systems`, existing markdown entities should be
discoverable by `entity list`, `entity show`, and `entity note` without changing
their current layout.

## Testing

Use TDD.

Core unit tests:

- kind registry resolves the initial supported kinds
- path policy maps each supported kind to the expected file path
- `create` writes markdown/frontmatter for questions, hypotheses, discussions,
  and interpretations
- `create` rejects existing destination files
- `create` reloads project sources and confirms the new canonical id
- `show` finds source-authored entities by canonical id
- `edit` updates frontmatter without changing body text
- `note` appends to the notes section and updates `updated`
- `note` rejects blank notes
- unknown kind fails loudly

CLI tests:

- `entity create question ...`
- `question create ...` wrapper delegates to the same writer
- `entity show question:...`
- `entity edit question:... --status ...`
- `entity note question:... "..."`
- `entity list --kind question`
- `entity neighbors question:...`

Integration smoke:

- create a question
- create a hypothesis related to it
- materialize graph
- verify both source entities appear in graph/source queries

## Design Decisions

- Typed wrappers auto-generate IDs when the kind has a clear existing
  convention. For example, `question create` scans existing questions and emits
  the next `question:qNN-<slug>` id when `--id` is omitted.
- Generic `entity create` requires `--id` unless the kind has a built-in path
  policy and ID-generation rule.
- `discussion create` and `interpretation create` use date-prefixed filenames
  even when the entity id itself is not date-prefixed, because the existing
  project layout uses date-prefixed files heavily.
- `neighbors` reads the materialized graph when present and warns if graph
  materialization appears stale. It does not auto-build the graph in the first
  increment.

# Source Entity CLI Design

**Date:** 2026-04-28
**Status:** Load-bearing design for implementation planning after review

## Decisions Needed Before Implementation

The following decisions are pinned in this spec because they affect the first
TDD plan:

- MVP path policy is hardcoded in `science_tool/entities.py`; profile-declared
  path templates are a future registry/profile extension.
- ID generation infers each project's existing sibling convention instead of
  hardcoding `qNN`.
- Filename slug equals the entity id local part for files created by the CLI.
- Created frontmatter has a canonical minimum schema and edits preserve unknown
  frontmatter fields.
- Validation uses a prospective temp-file write and rolls back on failures.
- Source-authored commands are preferred; overlapping `graph add` commands stay
  but emit soft-deprecation guidance for source-authored kinds.
- Reference resolution is exact by canonical id, with narrowly-defined
  unambiguous local-part shorthand.
- `related:` writes are unidirectional in source.

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
- Do not implement removal, physical deletion, rename, or re-id operations in
  the MVP.
- Do not implement profile-declared path templates in the MVP.

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

MVP class-3 support is intentionally limited: a registered project-specific
kind can be created as a markdown source only when the user supplies an
explicit `--path`. Profile-declared path templates are future work because the
current registry does not carry storage policy, and current projects do not
yet provide a stable manifest contract for that. Mutation of existing aggregate
YAML source files is deferred because those files often have kind-specific
structure and relations that require specialized writers.

## CLI Shape

Generic commands:

```bash
science-tool entity create <kind> <title> [--id <kind:slug>] [--path <path>] [--status <status>] [--related <ref>] [--source-ref <ref>]
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

Example round trip:

```bash
science-tool question create "What explains model family overlap?"
science-tool entity edit question:q102-model-family-overlap --status active --related hypothesis:h01
science-tool entity note question:q102-model-family-overlap "This also touches the morphism taxonomy."
science-tool entity show question:q102-model-family-overlap
```

Resulting file, assuming the next observed project question id is `q102`:

```markdown
---
id: "question:q102-model-family-overlap"
type: "question"
title: "What explains model family overlap?"
status: "active"
related:
  - "hypothesis:h01"
source_refs: []
created: "2026-04-28"
updated: "2026-04-28"
---

# What explains model family overlap?

## Summary

### Notes

- 2026-04-28: This also touches the morphism taxonomy.
```

## Source Writing

Add a focused source entity module at `science_tool/entities.py` for the MVP.
This mirrors the existing `science_tool/tasks.py` pattern: core writer helpers
live with the domain logic, while Click command registration stays in
`science_tool/cli.py`. If later increments add complex YAML aggregate writers
or ontology import, those helpers can be split into a package then.

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

### Path Policy Home

MVP path policy lives in a hardcoded table in `science_tool/entities.py`:

```python
_BUILTIN_MARKDOWN_POLICIES = {
    "question": EntityPathPolicy(root="doc/questions", filename="local-part"),
    "hypothesis": EntityPathPolicy(root="specs/hypotheses", filename="local-part"),
    "discussion": EntityPathPolicy(root="doc/discussions", filename="date-local-part"),
    "interpretation": EntityPathPolicy(root="doc/interpretations", filename="date-local-part"),
}
```

This is intentionally narrow. It does not pretend that
`EntityRegistry.with_core_types()` knows storage policy today.

Future path policy should move to registered kind metadata, either by:

- extending `EntityRegistry` to store kind records instead of only
  `kind -> type[Entity]`, or
- allowing profile manifests to declare `kind -> path_template` for
  project-specific markdown-authored kinds.

The MVP table should be shaped so those later records can replace it without
changing the CLI contract.

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

Explicit `--path` values must be project-relative markdown paths under a source
root that the markdown adapter already loads. Absolute paths and traversal
outside the project root are rejected.

If a target file already exists, `create` fails early and does not overwrite.

For CLI-created files, filename slug and entity id local part are coupled:

- `question:q102-model-family-overlap` writes
  `doc/questions/q102-model-family-overlap.md`.
- `hypothesis:h08-some-frame` writes
  `specs/hypotheses/h08-some-frame.md`.
- `discussion:2026-04-28-some-topic` writes
  `doc/discussions/2026-04-28-some-topic.md`.
- `interpretation:2026-04-28-some-result` writes
  `doc/interpretations/2026-04-28-some-result.md`.

If a user wants a renamed slug, the CLI should create the new id/path together.
Rename/re-id is a separate future operation because it must update inbound
references.

## ID Policy

`--id` validation rules:

- id must be `<kind>:<local-part>`
- prefix must exactly match the requested kind
- local part must match `[A-Za-z0-9][A-Za-z0-9_.-]*`
- local part must not contain `/`
- canonical id must not already exist in loaded project sources
- destination path must not already exist

Typed wrappers auto-generate ids only after inspecting existing sibling files
for that kind. They infer the numeric pattern from observed ids:

- natural-systems style: `question:q01-model-granularity` -> next
  `question:q102-<slug>`
- meta style: `question:01-bioinformatics-generalizability` -> next
  `question:02-<slug>`

If existing siblings mix incompatible numeric prefixes for the same kind and
directory, auto-generation fails and asks for explicit `--id`. Generic
`entity create` requires `--id` unless a built-in kind policy supplies a
single unambiguous generator.

Concurrent creation races are out of scope. The writer still checks existing
ids and paths immediately before write, and the prospective validation step
catches identity collisions.

## Frontmatter Schema

`entity create` emits this minimum frontmatter for MVP markdown-authored
entities:

```yaml
id: "<kind>:<local-part>"
type: "<kind>"
title: "<title>"
status: "<status>"
related: []
source_refs: []
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
```

Rules:

- `type:` is the canonical persisted field for markdown frontmatter in this
  increment. The loader already normalizes `type` to `kind`.
- `kind:` is not emitted for MVP markdown files.
- Empty list fields are emitted as empty arrays for schema consistency.
- `created` and `updated` are always emitted on new files.
- `edit` preserves unknown frontmatter fields such as `tags`, `datasets`,
  `ontology_terms`, `input`, `workflow_run`, and project-specific fields.
- `edit` updates only requested fields and sets `updated` to the edit date
  unless `--updated` is supplied.

## Body Templates

MVP body templates are code-owned constants in `science_tool/entities.py`, not
external files.

Minimum bodies:

`question`:

```markdown
# {title}

## Summary

### Notes
```

`hypothesis`:

```markdown
# Hypothesis: {title}

## Organizing Conjecture

## Current Uncertainty

### Notes
```

`discussion`:

```markdown
# Discussion: {title}

## Focus

## Synthesis

### Notes
```

`interpretation`:

```markdown
# Interpretation: {title}

## Verdict

## Findings Summary

### Notes
```

Templates can become file-backed later. The MVP should keep them in code so
the writer and tests have a small, explicit contract.

## Notes

Use the same note section grammar as the task note workflow:

```markdown
### Notes

- 2026-04-28: Clarification text.
```

Rules:

- The notes heading match is exact and case-sensitive:
  `^###\s+Notes\s*$`.
- Notes are append-only by insertion order, not sorted by date. `--date`
  allows backfills and future-dated planning notes.
- If no `### Notes` heading exists, `entity note` appends one at the end of
  the body, preceded by one blank line when the body is non-empty.
- If a notes section exists, insert the dated bullet before the next heading of
  equal-or-higher level, or at EOF if there is no later boundary.
- The section has one blank line between `### Notes` and the first bullet.
- There is no required trailing blank line after the final note bullet.
- Empty body text starts directly with `### Notes`, with no leading blank line.

`entity note` edits the source file, adds or updates `updated: YYYY-MM-DD`, and
then reloads project sources to verify the edited entity remains valid.

## Editing

`entity edit` should support conservative frontmatter edits first:

- `--title`
- `--status`
- `--related`, repeatable
- `--source-ref`, repeatable
- `--updated YYYY-MM-DD`

Replacing body content or opening an editor is deferred. The first version
should avoid ambiguity between journal notes and wholesale document rewriting.

Status values are not globally free-form, but per-kind status enums are not
fully standardized yet. MVP behavior:

- known built-in kinds get small allow-lists:
  - `question`: `active`, `open`, `partially-answered`, `answered`, `retired`
  - `hypothesis`: `candidate`, `proposed`, `active`, `retired`
  - `discussion`: `in-progress`, `active`, `closed`, `retired`
  - `interpretation`: `active`, `superseded`, `retired`
- unknown registered markdown kinds accept non-empty strings but emit a warning
  that no per-kind status validation exists.

`entity retire <ref>` is not part of the MVP. Users can set a retired status
through `entity edit --status retired` for kinds that allow it. Physical delete
is not supported because it can break inbound references.

Rename/re-id is not part of the MVP.

## Neighbors

`entity neighbors <ref>` is read-only.

It should use existing graph/source query machinery to show immediate
relationships around an entity. It can build or load the materialized graph,
but it should not mutate source files.

For MVP, one-hop neighbors are enough. Multi-hop traversal can reuse the
existing `graph neighborhood` behavior later.

Staleness warning rule:

- compare `knowledge/graph.trig` mtime to the newest discovered source file
  mtime under the source roots used by the markdown adapter plus task files
- if any source file is newer than `graph.trig`, print a warning that neighbor
  results may be stale
- do not auto-build the graph

This is deliberately mtime-based for the MVP. Hash/revision-based staleness can
reuse graph revision metadata later.

`entity list` reads live project sources, not the materialized graph. Source
scan is authoritative and ensures newly-created entities appear before graph
materialization. Performance is acceptable for the MVP; output can add paging
or graph-backed caching later if needed.

## Reference Resolution

Canonical ids such as `question:q01-model-granularity` are always accepted.

Shorthand is intentionally narrow:

- Exact local-part shorthand is accepted when it resolves to exactly one loaded
  entity, e.g. `q01-model-granularity`.
- Prefix-only shorthand such as `q01` is accepted only when exactly one entity
  local part starts with `q01-`.
- Ambiguous shorthands fail and list candidates.
- Bare kind-less title matching is not supported.
- Partial substring matching is not supported.

For `--related`, only the edited or created entity is changed. The target
entity is not mutated to add an inverse relation. Source remains
unidirectional; graph materialization may expose inverse/fanout views.

## Validation

After create/edit/note:

1. Write the prospective file contents to a temporary path in the destination
   directory.
2. Load project sources as they would look after the write, with the
   destination path's contents substituted by the prospective content and the
   temporary staging path excluded from markdown discovery.
3. Confirm the target canonical id exists.
4. Treat audit rows with failure status as blocking errors.
5. Atomically replace the destination file only after validation passes.

Implementation detail: existing `audit_project_sources()` returns rows plus a
boolean failure flag rather than raising, and it expects loaded
`ProjectSources`. The entity writer must translate blocking failure rows into
a Click error or library exception. Warnings may be printed but must not
silently pass as successful validation if `has_failures` is true.

If validation fails, the original project files are left unchanged and the temp
file is removed. Partial-bad source state is not allowed.

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
- Invalid id shape or mismatched id prefix: fail before writing.
- Mixed sibling ID conventions during auto-generation: fail and ask for
  explicit `--id`.

## Migration And Compatibility

Existing `graph add ...` commands stay in place. The new `entity` commands are
for source authoring, not graph patching.

For kinds now covered by source-authoring wrappers (`question`, `hypothesis`,
`discussion`, `interpretation`), overlapping `graph add ...` commands become
soft-deprecated: they still run, but their help text and success output should
recommend `science-tool entity create ...` for durable source-authored project
work.

Graph-only RDF records that already exist are not migrated in this increment.
A later migration can extract graph-only discussions/interpretations into
source files if a project needs it.

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
- ID generation respects both `qNN-...` and `NN-...` sibling conventions
- mixed ID conventions fail auto-generation and require `--id`
- `note` creates a `### Notes` section when missing
- `note` adds `updated` when missing
- validation failure leaves no partially-written destination file
- `edit` preserves unknown frontmatter fields
- `graph add hypothesis` plus source-authored hypothesis do not double-count
  after materialization

CLI tests:

- `entity create question ...`
- `question create ...` wrapper delegates to the same writer
- `entity show question:...`
- `entity edit question:... --status ...`
- `entity note question:... "..."`
- `entity list --kind question`
- `entity neighbors question:...`
- shorthand ref resolution rejects ambiguous prefixes
- `--related` mutates only the new/edited source file

Integration smoke:

- create a question
- create a hypothesis related to it
- materialize graph
- verify both source entities appear in graph/source queries

## Design Decisions

- Typed wrappers auto-generate IDs when the kind has a clear existing
  convention inferred from siblings. For example, `question create` in a
  natural-systems-style project emits the next `question:qNN-<slug>` id when
  `--id` is omitted.
- Generic `entity create` requires `--id` unless the kind has a built-in path
  policy and ID-generation rule.
- `discussion create` and `interpretation create` use date-prefixed filenames
  even when the entity id itself is not date-prefixed, because the existing
  project layout uses date-prefixed files heavily.
- `neighbors` reads the materialized graph when present and warns if graph
  materialization appears stale. It does not auto-build the graph in the first
  increment.

## Out Of Scope, Documented For Clarity

- `entity rename` / re-id and automatic reference rewrites.
- `entity rm` / physical deletion.
- Dedicated `entity retire`; use `entity edit --status retired` where the kind
  supports it.
- Profile-defined path templates.
- Ontology authority lookup/import.
- Aggregate YAML writers for project-specific domain kinds.
- Generic `entity` wrapper over task lifecycle commands.

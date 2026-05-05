# Task IDs And Cross-Project References Design

## Status

Approved design for `meta/tasks/active.md` task `t003`.

## Problem

Science task identifiers currently carry too much semantic weight. The meta
project contains both `t001` and `t001b`; the validator interprets `t001b` as a
duplicate `t001`, so `meta/validate.sh` fails. The ad-hoc suffix also leaves
three meanings ambiguous: revision, decomposition, and follow-up fragment.

At the same time, Science projects increasingly need to refer to tasks and
entities owned by other projects. Federation already defines stable project IDs
and a namespace-first address convention, but local task parsing and entity
references still mostly assume local `kind:slug` references.

## Goals

- Make task IDs flat, local, and mechanically validated.
- Move hierarchy and follow-up semantics into explicit fields.
- Define a single authored reference shape for cross-project task and entity
  references.
- Preserve the common local case: un-namespaced refs continue to mean "this
  project."
- Turn the current `t001b` failure into a clear migration path, not a silent
  parser artifact.

## Non-Goals

- No global task numbering.
- No automatic writes into child projects.
- No attempt to solve entity rename or declarative migrations here.
- No compatibility layer that silently accepts every historical task-ID shape.

## Decisions

### 1. Task IDs Are Flat And Local

Canonical task IDs use only:

```text
tNNN
```

Examples: `t001`, `t016`, `t335`.

Task header validation is strict:

```markdown
## [t016] H01 engine follow-ups
```

Invalid examples:

```markdown
## [t001b] H01 engine follow-ups
## [t001.1] H01 subtask
## [t001v2] H01 revision
```

The validator must reject invalid headers with an error naming the exact task ID
and file. It must not partially parse `t001b` as `t001`.

### 2. Structure Lives In Fields

Task relationships are represented as metadata, not encoded into IDs.

Use:

```markdown
- parent: task:t001
- related: [task:t001]
```

`parent:` is optional and singular. It means "this task is structurally derived
from this parent task." `related:` remains the many-valued general-purpose link
field and should include the parent when useful for existing graph and search
surfaces.

No separate `work_kind` field is required for the first implementation. If the
project later needs to distinguish fragment, subtask, and revision semantics, it
can add a typed field then. For now, the task title and body carry that nuance.

### 3. Local References Stay Local By Default

Existing local refs remain valid:

```text
task:t123
hypothesis:h01
question:q006
```

Where bare task IDs are already supported for user convenience, they remain
local shorthand:

```text
t123
```

Bare `t123` must not become a cross-project reference. It always means the
current project.

### 4. Cross-Project References Are Namespace-First

Authored cross-project refs use:

```text
<project-id>:<kind>:<slug>
```

Examples:

```text
meta:task:t003
natural-systems:task:t335
multiple-myeloma:hypothesis:h01
cbioportal:question:q006-ch-priority-gene-completeness
```

The first segment is a federation project ID from `science.yaml` or a meta
project's `children:` manifest. The remaining segments are the target project's
normal local entity reference.

This refines the existing federation convention in `docs/federation.md`, which
currently describes `<project-id>:<artifact-id>`. The broad namespace-first
rule remains; this design makes canonical entity refs explicit by requiring the
local `kind:slug` after the project namespace.

### 5. Resolution And Validation

Reference parsing should distinguish three shapes:

| Shape | Meaning |
|---|---|
| `t123` | local task shorthand |
| `task:t123` | local canonical task ref |
| `project-id:task:t123` | cross-project canonical task ref |

For any entity kind:

| Shape | Meaning |
|---|---|
| `kind:slug` | local canonical entity ref |
| `project-id:kind:slug` | cross-project canonical entity ref |

Validation behavior:

- Local refs are resolved against the current project.
- Cross-project refs resolve through the federation membership table when
  available.
- If federation metadata is unavailable, namespace-first refs are syntactically
  accepted but reported as unresolved namespace, not misclassified as local
  malformed refs.
For the initial implementation, the parser can use an explicit project-ID set
from federation config to decide whether the first segment is a namespace. It
should not infer namespaces from arbitrary strings. Two-part refs always remain
local `kind:slug`; three-part refs are namespace-first only when the first part
is a known project ID.

## Migration

The current meta task queue should migrate:

```markdown
## [t001b] H01 engine follow-ups (grid, metrics, parallelism)
```

to the next flat ID, expected:

```markdown
## [t016] H01 engine follow-ups (grid, metrics, parallelism)
- parent: task:t001
- related: [hypothesis:h01-stochastic-revisiting, task:t001]
```

All references to `[t001b]` or `t001b` in meta should be updated to `t016` or
`task:t016`, depending on context.

The migration should be explicit and small. Do not add a legacy alias layer for
`t001b`; if a stale reference remains, validation should catch it.

## Implementation Surface

- `science-tool/src/science_tool/tasks.py`
  - Make task header parsing strict.
  - Add optional `parent` parse/render support.
  - Preserve local task ID generation.
- `science_model.tasks.Task`
  - Add optional `parent: str`.
- Task storage adapter
  - Materialize `parent` as a task relationship if the graph layer has an
    existing suitable predicate; otherwise expose it in the source entity record
    for later graph use.
- Reference parsing / validation
  - Add a small parser for local vs namespace-first refs.
  - Validate namespace-first refs through federation config where available.
- `commands/tasks.md`
  - Document flat IDs, `parent:`, and namespace-first cross-project refs.
- `docs/federation.md`
  - Tighten the Addressing section to show `<project-id>:<kind>:<slug>` for
    canonical entity refs, while noting any legacy shorthand as non-canonical.
- `meta/tasks/active.md`
  - Migrate `t001b` to a flat ID and update references.

## Error Messages

Invalid task header:

```text
Invalid task id 't001b' in tasks/active.md: task ids must match tNNN. Use parent: task:t001 for fragments or subtasks.
```

Unresolved namespace:

```text
Unknown project namespace 'natural-systems' in ref 'natural-systems:task:t335'. Add it to science.yaml children: or use a local ref.
```

## Testing Strategy

- Parser accepts `## [t016] Title`.
- Parser rejects `## [t001b] Title` with the clear error above.
- Parser round-trips `parent: task:t001`.
- `next_task_id()` ignores invalid task-like headers instead of deriving
  numbers from partial matches.
- Validation catches stale references to `t001b` after migration.
- Reference parser classifies:
  - `t123` as local task shorthand.
  - `task:t123` as local entity ref.
  - `natural-systems:task:t335` as cross-project entity ref.
  - `meta:next-steps-2026-05-05` as a local `meta` entity ref, even when
    `meta` is also a project ID.
  - unknown namespace as unresolved namespace.
- Federation-aware validation resolves a child task ref when the child project
  is declared in `children:`.

## Acceptance Criteria

- `meta/validate.sh --verbose` no longer fails on duplicate `t001`.
- The meta task queue contains no semantic task-ID suffixes.
- Cross-project task refs have a documented canonical shape.
- Local task workflows remain unchanged for the common case.

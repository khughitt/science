# Task IDs And Cross-Project References Design

## Status

Approved design for `meta/tasks/active.md` task `t003`.

## Problem

Science task identifiers currently carry too much semantic weight. The meta
project contains both `t001` and `t001b`; the validator interprets `t001b` as a
duplicate `t001`, so `meta/validate.sh` fails. The ad-hoc suffix also leaves
three meanings ambiguous: revision, decomposition, and follow-up fragment.

At the same time, Science projects increasingly need to refer to tasks and
entities owned by other projects. Project peers define stable project IDs and a
namespace-first address convention, but local task parsing and entity references
still mostly assume local `kind:slug` references.

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
- No automatic writes into peer projects.
- No attempt to solve entity rename or declarative migrations here.
- No compatibility layer that silently accepts every historical task-ID shape.

## Decisions

### 1. Task IDs Are Flat And Local

Canonical task IDs use only:

```text
tNNN
```

Examples: `t001`, `t016`, `t335`, `t1000`.

`tNNN` means "at least three digits, zero-padded to three digits while the
sequence is below 1000." Four or more digits are valid once a project reaches
that many tasks.

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

`parent:` must be local. A cross-project structural parent would couple task
ownership across project boundaries; use `related:` for cross-project
associations such as `natural-systems:task:t335`.

No separate `work_kind` field is required for the first implementation. If the
project later needs to distinguish fragment, subtask, and revision semantics, it
can add a typed field then. For now, the task title and body carry that nuance.

Supersession/revision chains are not modeled by `parent:`. A future
`supersedes:` field can cover "this task replaces that task" if the project
needs that workflow.

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

The first segment is either the current project's own `id` or a peer project ID
declared in `science.yaml` under `peers:`. The remaining segments are the target
project's normal local entity reference.

This refines the existing addressing convention in `docs/federation.md`, which
historically described `<project-id>:<artifact-id>`. The broad namespace-first
rule remains; this design makes canonical entity refs explicit by requiring the
local `kind:slug` after the project namespace.

Existing two-part cross-project examples such as `cbioportal:q014`,
`multiple-myeloma:h003`, and `evolution:t012` are legacy shorthand and must be
audited/migrated during implementation. Checked-in examples in
`docs/federation.md` and `science/tests/test_addressing.py` should either
move to the three-part entity form or be explicitly labeled as legacy artifact
addresses.

Path-style addresses such as `cbioportal:topics/clonal-hematopoiesis-contamination`
are artifact addresses, not canonical entity refs. For entity references, topic
documents use the entity kind form: `cbioportal:topic:clonal-hematopoiesis-contamination`.

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

Parsing and validation are separate steps. A value can be syntactically local
(`meta:next-steps-2026-05-05`) and still fail later if `meta` is not a registered
local entity kind or the slug does not resolve.

Validation behavior:

- Local refs are resolved against the current project.
- Cross-project refs resolve through the peer project-ID set declared in
  `science.yaml` under `peers:` when available.
- Three-part namespace-first refs are syntactically accepted but reported as an
  unresolved namespace when the first segment is not the current project ID or a
  declared peer ID.
- Two-part refs remain local `kind:slug` when the first segment is a registered
  local entity kind.
- Two-part refs whose first segment is a known project ID but not a local entity
  kind are legacy cross-project shorthand. Report a deprecation/error with a
  suggested three-part replacement rather than silently treating them as local.

For the initial implementation, the parser can use an explicit project-ID set
from `science.yaml` `peers:` plus the current project ID to decide whether the
first segment is a namespace. It should not infer namespaces from arbitrary
strings.

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

- `science/src/science_tool/tasks.py`
  - Make task header parsing strict, using one anchored source of truth for
    task headers.
  - Replace `next_task_id()`'s loose `_TASK_ID_RE` scan with strict header
    parsing; do not derive numbers from partial matches such as `[t001b]`.
  - Add optional `parent` parse/render support.
  - Preserve local task ID generation.
- `science_model.tasks.Task`
  - Add optional `parent: str`.
- Task storage adapter
  - Parse/render `parent` and expose it in the raw task entity record.
  - Do not emit a graph predicate for `parent` in the first implementation.
    Graph semantics for structural containment/supersession should be designed
    separately from this parser/namespace fix.
- Reference parsing / validation
  - Add a small parser for local vs namespace-first refs.
  - Validate namespace-first refs through the peer project-ID set where available.
  - Detect legacy two-part cross-project shorthand when the first segment is a
    known project ID and suggest `<project-id>:<kind>:<slug>`.
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
Unknown project namespace 'natural-systems' in ref 'natural-systems:task:t335'. Add it to science.yaml peers: or use a local ref.
```

Legacy two-part cross-project ref:

```text
Legacy cross-project ref 'cbioportal:q014' is missing an entity kind. Use 'cbioportal:question:q014' or another explicit <project-id>:<kind>:<slug> ref.
```

## Testing Strategy

- Parser accepts `## [t016] Title`.
- Parser accepts `## [t1000] Title`.
- Parser rejects `## [t001b] Title` with the clear error above.
- Parser round-trips `parent: task:t001`.
- `next_task_id()` uses strict task-header parsing and does not derive `001`
  from `[t001b]`.
- Validation catches stale references to `t001b` after migration.
- `parent: natural-systems:task:t001` is rejected because `parent` must be local.
- Reference parser classifies:
  - `t123` as local task shorthand.
  - `task:t123` as local entity ref.
  - `natural-systems:task:t335` as cross-project entity ref.
  - `meta:next-steps-2026-05-05` as a local `meta` entity ref, even when
    `meta` is also a project ID.
  - `cbioportal:q014` as legacy two-part cross-project shorthand when
    `cbioportal` is a known project ID and not a local entity kind.
  - unknown namespace as unresolved namespace.
- Peer-aware validation resolves a cross-project task ref when the target project
  is declared in `peers:`.

## Acceptance Criteria

- `meta/validate.sh --verbose` no longer fails on duplicate `t001`.
- The meta task queue contains no semantic task-ID suffixes.
- Cross-project task refs have a documented canonical shape.
- `science tasks add` still produces `## [tNNN] Title` with no `parent:`
  line by default.

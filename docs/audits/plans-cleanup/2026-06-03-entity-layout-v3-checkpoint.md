# Entity Layout v3 Checkpoint

This checkpoint preserves the durable as-built decisions from the June entity
layout, local-kind migration, migration robustness, kind-descriptor, and
adapter-backed layout plan cluster. The original plan files were implementation
work records; current behavior is represented by code, tests, and user-guide
documentation.

Current status, 2026-07-08: the v2 entity-layout migration command described
below has since been retired by `6147e473` (`refactor: remove v2 entity layout
support`). `science entities --help` no longer lists `migrate`, and
`science/src/science_tool/entity_layout_migration.py` is absent. The migration
sections below preserve the historical migration contract and cutover rationale;
they are not instructions for a current command.

## Three-Root Layout

At `layout_version: 3`, markdown entity files have a structural home based on
what they are:

- `entities/<kind>/` holds project-owned entity declarations.
- `overlays/<type>/` holds project-local borrower overlays with `overlay_of:`.
- `doc/` holds prose only.

Dataset, workflow, workflow-run, and workflow-step owners are first-class
markdown entity kinds. They use `strategy: id-local`: the frontmatter `id` is
authoritative and the filename is the id local part. This removed the legacy
`doc/<type>/` owner roots and the dataset `data-` filename workaround.

Overlay relocation is a separate migration pass inside `science entities
migrate`: legacy `doc/{datasets,papers,topics,themes}` files with `overlay_of:`
move to `overlays/<type>/`. Overlay placement is validated; `overlay_of:` files
under `entities/` or `doc/` are findings because `entities/` mints owners and
`doc/` is prose-only.

## v2-to-v3 Migrator

`science entities migrate` is dry-run by default. It discovers legacy `doc/` and
`specs/` entity files, synthesizes frontmatter where possible, plans moves,
rewrites resolvable full-id references, simulates the post-move graph state, and
reports blockers without mutating the tree. `--apply` performs tracked moves and
writes, re-runs the post-move audit, and bumps `layout_version: 3` only after a
clean audit.

The migration blocker model is intentionally structural:

- graph-audited unresolved references block apply;
- unresolved entity-looking tokens in prose bodies are warnings;
- code spans, fenced examples, wikilinks, placeholders, and cross-project prose
  mentions should not block a mechanical layout move;
- files under known legacy roots that lack `id`, `type`, or `kind` are skipped
  with warnings rather than guessed into entities;
- files with no derivable date still block, but `generated_at` and `committed`
  can provide explicit fallback dates.

Malformed local-kind declarations are skipped with warnings so one vestigial
local kind does not abort unrelated core-kind migration. The skipped kinds are
also surfaced by entity-conformance validation.

## Project-Local Markdown Kinds

Project-local markdown kinds are declared in the active local profile under
`entity_kinds:`. A local kind's `name` is its kind, canonical id prefix, and
default directory segment. Defaults are:

- `home: entities/<kind>`
- `strategy: numeric`
- `default_status: active`
- open status vocabulary

Profiles may override `home`, `strategy`, `default_status`, and `statuses`.
Supported local markdown strategies are `numeric`, `citekey`, `slug`, and
`id-local`. Singleton is core-only. Local homes must remain relative
`entities/<segment>/...` paths, cannot traverse upward, cannot use reserved
archive segments, and cannot collide with a core entity directory. Local kinds
cannot shadow built-in kinds.

The source-entity creation path remains built-in-only. Local kinds are loaded,
migrated, and validated when authored as Markdown, but `science entities create`
does not mint new local-kind files.

## Kind Descriptor Source Of Truth

Core kind metadata is owned by `CORE_PROFILE` descriptors. `EntityKind`
descriptors carry category, entity class, markdown home, filename strategy,
default status, allowed statuses, template readiness, shortform alias, and
structured-source metadata. The tool layer derives path policies, status maps,
shortforms, and registry metadata from descriptors rather than parallel literal
tables.

The transitional `science_model/kinds.py` / `CORE_KINDS` surface was removed.
`CORE_PROFILE` is the source of truth for authored-core and reserved core facts;
`LOCAL_PROFILE` carries built-in source-only local descriptors. `EntityKind`
keeps `strategy` as raw manifest input and the tool-side path-policy loader
validates the accepted filename-strategy vocabulary.

## Deferred Or Separate Work

The later `remove-v3-migration-code` plan was a superseded cleanup plan. Do not
infer from this checkpoint that all migration-named code is dead; current live
surfaces must be checked from the CLI, imports, tests, and user guide.

Task `t071` still tracks the broader user-guide refresh for stale v2 layout
references outside the specific guide sections updated during this cleanup. Task
`t072` was retired on 2026-07-08 because the v2 entity-layout migration surface
it targeted no longer exists on `main`. These notes are therefore historical
context, not a reason to keep the completed implementation plans in `docs/plans/`.

This checkpoint also does not implement dataset lifecycle semantics such as
register-run, production/reconciliation invariants, or research-package
relocation. Those belong to later dataset lifecycle and evidence-flow work.

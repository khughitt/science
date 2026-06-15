# Source Compiler & Identity Substrate — Adapter Policy Keystone (Spec 3, Slice A)

**Status:** Design / approved for planning
**Kernel spec:** 3 (Source Compiler & Identity Substrate), keystone slice
**Architecture:** `~/d/science/docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`
**Precedent:** Spec 2 (Kind Descriptor) `2026-06-14-kind-descriptor-model-registry-design.md`; Spec 4 (Patch Contract) `2026-06-14-patch-contract-keystone-design.md`

## Purpose

Patchwork kernel Spec 3 ("Source Compiler & Identity Substrate") is too large for a
single design. The architecture assigns it source records, adapter policies, identity
rows, error policy, reference-field policy, source snapshots, freshness-origin records,
and compiled outputs. Following the keystone-first pattern that shipped Specs 2 and 4,
Spec 3 decomposes into:

- **Slice A — Adapter Policy keystone (this design).** Collapse the adapter-identity
  branching scattered through the source-load loop into *declared policy on the
  `StorageAdapter` contract*. Behavior-neutral. Establishes the substrate that the new
  primitive attaches to.
- **Slice B — `SourceSnapshot` & freshness-origin record.** The net-new kernel
  primitive: pin a source observation (content hash / revision), emit a freshness-origin
  record when it changes, propagate through `bears_on` to mark dependents stale. Consumed
  by Spec 5 (belief) and Spec 6 (review). *Out of scope here.*
- **Slice C — Compiler phase split / audit↔materialize unification.** Restructure
  `materialize.py` phases once source records are typed. *Out of scope here.*

This document specifies **Slice A only**.

## Goal

Make adapter behavior *declared data and hooks on the `StorageAdapter` contract* instead
of `isinstance(...)` / `adapter.name == ...` branching inside the
`load_project_sources` loop, so the loop body becomes one uniform sequence. The change
is **strictly behavior-neutral** and is pinned by equivalence tests.

Success: the load loop has zero `isinstance(adapter, ...)` checks and zero
`adapter.name == "..."` comparisons; adding or changing an adapter's load-time behavior
is a change to that adapter class, not an edit to the shared loop.

## Current state

`~/d/science/science/src/science_tool/graph/sources.py::load_project_sources`
runs all eight adapters (markdown, aggregate, bib, curie-ref, datapackage, workflow-run,
task, code) through one loop. Adapter-specific behavior is dispatched inside that loop by
type/name branching:

| # | Location | Branch | Behavior |
|---|---|---|---|
| 1 | `sources.py:371` | `isinstance(adapter, MarkdownAdapter)` | build a `MarkdownSourceDocument` and append to `markdown_documents` |
| 2 | `sources.py:417` | `isinstance(adapter, MarkdownAdapter) and _is_missing_identity_validation(exc)` | skip-warn a core entity missing identity fields *even under* `strict_core_schema` (fb-2026-05-30-008) |
| 3 | `sources.py:472` | `isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table` | defer (no owner row, no duplicate); also record `dataset_datapackages[id] = ref.path` (§B4) |
| 4 | `sources.py:487` | `adapter.participation_mode == EXTERNAL_REFERENCE and entity.canonical_id in identity_table` | defer (§B3/§C3) |
| 5 | `sources.py:510` | `adapter.name == "aggregate"` | capture an `AggregateRowMeta` for row-level triage (§B5) |
| 6 | `sources.py:471,564` | `classify_owner_scope(adapter.name, ...)` | map adapter name → `(owner_scope, deprecated)` |

The `StorageAdapter` base
(`~/d/science/science/src/science_tool/graph/storage_adapters/base.py`) today declares
only `name`, `participation_mode`, and the `discover`/`load_raw`/`dump` methods.

## Design

### Policy surface on `StorageAdapter`

Add to the base contract, with the common-case default inline and per-adapter overrides:

- **`skip_core_on_missing_identity: bool = False`** — when `True`, a core entity that
  fails schema validation *solely* because it is missing identity fields is skipped with
  a warning even under `strict_core_schema`, instead of raising. `MarkdownAdapter`
  overrides `True`. (Collapses branch 2.)
- **`should_defer(self, *, already_owned: bool) -> bool`** — return `True` to contribute
  no owner declaration and no duplicate entity when the id is already owned this load.
  Base default: `return self.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
  and already_owned` (collapses branch 4). `DatapackageAdapter` overrides to
  `return already_owned` (it is `OWNER` mode but still defers — collapses branch 3).
- **`source_document(self, ref, raw) -> MarkdownSourceDocument | None`** — base returns
  `None`. `MarkdownAdapter` builds and returns the document. The loop appends it to
  `markdown_documents` when non-`None`. (Collapses branch 1.)
- **`on_owner_declared(self, *, entity, ref, raw, kind) -> AggregateRowMeta | None`** —
  base returns `None`. `AggregateAdapter` builds the `AggregateRowMeta`. The loop appends
  it to `aggregate_rows` when non-`None`. (Collapses branch 5.)
- **`deferred_dataset_datapackage(self, *, entity, ref) -> tuple[str, str] | None`** —
  base returns `None`. `DatapackageAdapter` overrides to return
  `(entity.canonical_id, ref.path)`. The loop owns the mutation: when the return is
  non-`None`, the loop writes it into `dataset_datapackages` so the geneset member gate
  can still locate the datapackage's resources after the owner wins the column.
  (Captures the datapackage defer side-effect from branch 3.)

These three record-capture hooks (`source_document`, `on_owner_declared`,
`deferred_dataset_datapackage`) are deliberately small parallel typed hooks rather than
one over-generalized callback; each returns one concrete payload and the loop owns every
mutation — adapters never touch loop-owned mutable state.

#### Record types move to a leaf module (import-cycle fix)

`MarkdownSourceDocument` and `AggregateRowMeta` currently live in `sources.py`, but
`sources.py` imports the adapter modules — so an adapter that imported those types from
`sources.py` would create a cycle. Relocate both dataclasses to a new leaf module
`science/src/science_tool/graph/source_records.py` (depends only on `science_model`).
`base.py`, the adapter modules, and `sources.py` all import them from the leaf. This is
behavior-neutral (a pure move + re-import) and gives Slice B's `SourceRecord` /
`SourceSnapshot` a natural home. `sources.py` keeps a plain re-export of the two names
from the leaf because existing callers import them from `science_tool.graph.sources`;
the re-export preserves that public path while the implementation moves.

### `owner_scope` policy stays consolidated

`classify_owner_scope` (`identity_table.py:97`) is **kept as-is**. It is already the
single consolidated owner-scope SSOT and is called from three contexts — the adapter
loop (real adapter objects), the legacy/structured-source loaders (string
`ref.adapter_name`, no adapter object), and the commons-merge path (`"commons-merged"`,
no adapter object). It is a pure value lookup, not the scattered control-flow branching
this slice removes; moving it onto the adapter contract would *fragment* a currently
single-source policy because two of its callers have no adapter object. The loop
continues to call `classify_owner_scope(adapter.name, project_name=project_name)`.

### The rewritten loop

After the change, the per-record loop body is one uniform sequence with no adapter-type
or adapter-name branching:

```text
for adapter in adapters:
    for ref in adapter.discover(project_root):
        raw = adapter.load_raw(ref)
        if (doc := adapter.source_document(ref, raw)) is not None:
            markdown_documents.append(doc)
        # kind resolution + _enrich_raw (unchanged)
        # registry.resolve + model_validate, inside the shared error policy
        #   (the only adapter knob is adapter.skip_core_on_missing_identity)
        owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=...)
        if adapter.should_defer(already_owned=entity.canonical_id in identity_table):
            if (pair := adapter.deferred_dataset_datapackage(entity=entity, ref=ref)):
                cid, path = pair                          # loop owns the mutation
                dataset_datapackages[cid] = path
            continue
        identity_declarations.append(IdentityDeclaration(...))
        if (meta := adapter.on_owner_declared(...)) is not None:
            aggregate_rows.append(meta)
        # existing identity_table + entity_source_adapters handling (unchanged)
```

### Error policy (preserved exactly)

The nested core/profile/`strict_core_schema`/missing-identity conditional
(`sources.py:416–470`) is preserved exactly. The *only* adapter-specific input lifted out
of it is `skip_core_on_missing_identity`. Severity rules — core kinds fail loud under
strict load, profile kinds skip-warn, unknown kinds skip-warn, the distinct
`core_schema_validation_failed` vs missing-identity `entity_schema_validation_failed`
reasons (fb-2026-05-30-008) — remain shared loop policy, unchanged. No adapter's
fail-loud vs skip-warn disposition changes.

## Non-goals / explicit follow-ups

These are deliberately deferred and documented so transitional state does not become
permanent architecture:

1. **Rationalizing inconsistent malformed-input handling.** Adapters disagree today
   (e.g. `AggregateAdapter` silently skips malformed YAML; `WorkflowRunAdapter` and
   `CurieRefAdapter` raise). The keystone preserves every quirk. Normalizing the policy
   is real design work for a later slice, not a rider on a structural refactor.
2. **Legacy/structured-source loaders becoming real adapters.** `_load_legacy_records`
   and `_load_structured_source_records` run outside the adapter loop and emit string
   `ref.adapter_name`. Converting them to `StorageAdapter`s (which would also let
   `classify_owner_scope` consult adapter policy uniformly) is future work.
3. **`SourceRecord` / `SourceSnapshot` / freshness-origin** — Slices B and C.

## Behavior-neutral guarantee & testing

Mirror Spec 2's equivalence discipline:

- **Equivalence fixture (the keystone's pinning test).** Add a representative
  multi-adapter fixture project that exercises every branch being collapsed: a markdown
  owner, an `entities.yaml` aggregate row, a datapackage that defers onto a markdown
  owner *and* a true-orphan datapackage, a bib/curie external-reference that defers, an
  aggregate row captured for triage, and at least one core entity missing identity
  fields (the strict skip-warn path). Capture the full load output —
  `entities`, `identity_declarations`, `skipped_entities`, `markdown_documents`,
  `aggregate_rows`, `dataset_datapackages`, `entity_source_adapters` — as frozen expected
  values. (`entity_source_adapters` is load-bearing: the collapsed defer/owner branches
  directly shape it — `sources.py:529`, returned at `:688` — and existing datapackage
  tests assert deferred-vs-orphan behavior through it.) The test asserts the post-refactor
  load equals the frozen capture, field for field. Any difference is a bug, not a judgment
  call.
- **Full regression suite.** `cd ~/d/science && uv run --frozen pytest` (5500+ tests)
  must stay green — the existing per-adapter tests already cover each behavior; the
  equivalence fixture adds the cross-adapter interaction guarantee.
- **No new behavior tests** are added for the policy fields beyond the equivalence
  fixture and the existing suite, because the keystone introduces no new behavior.

## File structure

- **Add** `science/src/science_tool/graph/source_records.py` (leaf) — relocate
  `MarkdownSourceDocument` and `AggregateRowMeta` here (depends only on `science_model`).
- **Modify** `science/src/science_tool/graph/storage_adapters/base.py` — add the policy
  fields + hook method signatures with common-case defaults (imports record types from
  the leaf).
- **Modify** `storage_adapters/markdown.py` — override `skip_core_on_missing_identity`,
  `source_document`.
- **Modify** `storage_adapters/datapackage.py` — override `should_defer`,
  `deferred_dataset_datapackage`.
- **Modify** `storage_adapters/aggregate.py` — override `on_owner_declared`.
- **Modify** `science/src/science_tool/graph/sources.py` — rewrite the loop body to read
  the policy surface; remove the `isinstance`/`name ==` branches; import the record types
  from the leaf and re-export them from this module to preserve the current public import
  path.
- **Add** fixture project + equivalence test under `science/tests/`.
- **Unchanged** `identity_table.py` (`classify_owner_scope` kept).

## Success criteria

- `load_project_sources` contains no `isinstance(adapter, ...)` and no
  `adapter.name == "..."` (the `classify_owner_scope(adapter.name, ...)` value lookup is
  the only remaining use of `adapter.name`, and it is policy lookup, not branching).
- The equivalence fixture load is byte-identical before and after.
- Full suite green.
- Each collapsed behavior now lives on the adapter class that owns it.

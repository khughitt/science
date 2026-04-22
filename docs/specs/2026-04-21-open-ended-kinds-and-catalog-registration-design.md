# Open-Ended Entity Kinds and Ontology Catalog Kind Registration

**Date:** 2026-04-21
**Status:** Draft
**Builds on:**
- `2026-04-20-multi-backend-entity-resolver-design.md` — unified entity model + storage adapters
- `2026-04-21-unified-entity-references-design.md` — identifies open-ended kind support as the prerequisite for phase 2A catalog kinds

## Motivation

The unified entity model and adapter architecture are in place, but one
model-layer constraint still blocks the intended domain-entity flow.

Today:

- `science_model.entities.Entity` requires `type: EntityType`
- loader normalization in `science_tool.graph.sources._enrich_raw()` copies
  `kind` into that closed enum
- downstream code compensates by degrading non-core kinds to
  `EntityType.UNKNOWN`
- ontology catalogs contribute only external CURIE prefixes, not loadable
  kind vocabulary

This means the system can *name* domain concepts such as `gene:PHF19`, but
cannot load them as first-class entities unless they are forced through a
core enum they do not belong to.

The result is a persistent mismatch:

- the registry architecture is open-ended
- the reference-resolution design assumes domain kinds can eventually load
- the entity model is still closed at the point where records are validated

This spec defines the smallest end-to-end change needed to remove that
blocker and make phase 2A of the unified references design implementable.

## Goals

- Decouple load-time `kind` handling from the closed `EntityType` enum.
- Preserve current typed behavior for Science core kinds such as `task`,
  `dataset`, `workflow-run`, and `research-package`.
- Let declared ontology catalogs register domain kinds such as `gene`,
  `protein`, and `disease` to `DomainEntity`.
- Define downstream compatibility rules for code that still assumes every
  entity must round-trip through `EntityType`.
- Keep the change additive for core kinds and explicit for non-core kinds.

## Non-goals

- Catalog-provided entity instances or snapshot/provider contracts.
- Local overlay / merge semantics for catalog-provided entities.
- New reference-resolution rules beyond what the 2026-04-21 unified
  references spec already defines.
- Redesigning the RDF materialization layer beyond the minimum compatibility
  changes forced by the model contract.
- Introducing ontology-specific typed subclasses such as `GeneEntity` in
  Science core.

## Design Overview

This spec makes two connected changes:

1. **Open-ended load-time kinds**
   - `kind` becomes the authoritative load-time discriminator.
   - `Entity.type` no longer determines whether an entity is admissible.

2. **Phase 2A catalog kind registration**
   - declared ontology catalogs contribute valid kind vocabulary
   - catalog kinds register to `DomainEntity`
   - project extensions may not shadow catalog kinds

The design intentionally does **not** yet make catalogs provide entity
instances. It only makes their kinds first-class and loadable.

## Current Problem

The current architecture has four concrete issues:

1. **Model gating is closed**
   - `Entity.type` is a required `EntityType`, so only enum-listed kinds can
     validate directly.

2. **Normalization collapses `kind` into `type`**
   - `_enrich_raw()` derives `type` from `kind`, which prevents arbitrary
     domain kinds from surviving validation intact.

3. **Consumers compensate with `UNKNOWN`**
   - downstream paths such as registry sync preserve the entity record only by
     degrading non-core kinds to `EntityType.UNKNOWN`.

4. **Catalogs do not yet own loadable kinds**
   - catalog metadata is already available through `load_catalogs_for_names()`,
     but those kinds are not registered into `EntityRegistry`.

Together these make domain kinds liminal: visible in strings, absent in the
validated model.

## Canonical Model Contract

### Core decision

`kind` becomes the authoritative open-ended discriminator on base `Entity`.

`type` remains available only as a core semantic classification field. It is
no longer the universal gate for admissible entities.

### Base `Entity` contract

Base `Entity` should carry:

- `kind: str` — required, open-ended, authoritative
- `type: EntityType | None` — optional, populated only for core kinds

The rest of the shared entity contract remains unchanged unless a later spec
refines it.

### Normative core-kind mapping

This spec introduces a single source of truth:

- `core_entity_type_for_kind(kind: str) -> EntityType | None`

Loader normalization, model validation, registry setup, and downstream
compatibility code must all use that mapping rather than maintaining parallel
hard-coded notions of "core."

Initial mapping:

- typed core kinds
  - `task -> EntityType.TASK`
  - `dataset -> EntityType.DATASET`
  - `workflow-run -> EntityType.WORKFLOW_RUN`
  - `research-package -> EntityType.RESEARCH_PACKAGE`

- generic core kinds
  - `concept -> EntityType.CONCEPT`
  - `hypothesis -> EntityType.HYPOTHESIS`
  - `question -> EntityType.QUESTION`
  - `proposition -> EntityType.PROPOSITION`
  - `observation -> EntityType.OBSERVATION`
  - `inquiry -> EntityType.INQUIRY`
  - `topic -> EntityType.TOPIC`
  - `interpretation -> EntityType.INTERPRETATION`
  - `discussion -> EntityType.DISCUSSION`
  - `model -> EntityType.MODEL`
  - `plan -> EntityType.PLAN`
  - `assumption -> EntityType.ASSUMPTION`
  - `transformation -> EntityType.TRANSFORMATION`
  - `variable -> EntityType.VARIABLE`
  - `method -> EntityType.METHOD`
  - `experiment -> EntityType.EXPERIMENT`
  - `article -> EntityType.ARTICLE`
  - `workflow -> EntityType.WORKFLOW`
  - `workflow-step -> EntityType.WORKFLOW_STEP`
  - `data-package -> EntityType.DATA_PACKAGE`
  - `finding -> EntityType.FINDING`
  - `story -> EntityType.STORY`
  - `paper -> EntityType.PAPER`
  - `search -> EntityType.SEARCH`
  - `report -> EntityType.REPORT`
  - `validation-report -> EntityType.VALIDATION_REPORT`
  - `spec -> EntityType.SPEC`
  - `canonical_parameter -> EntityType.CANONICAL_PARAMETER`

- compatibility-only core kind
  - `unknown -> EntityType.UNKNOWN`

Any kind not listed above is non-core and must yield `None`.

Legacy naming note:

- `canonical_parameter` is the canonical core kind name for this mapping
- legacy storage or registry code that still uses `parameter` must normalize
  to `canonical_parameter` before validation or registry registration

### Semantics

- `kind` preserves the authored or registry-resolved kind string exactly:
  `task`, `dataset`, `gene`, `protein`, `cytogenetic-event`, etc.
- `type` is populated only when a kind belongs to Science core semantics.
- non-core entities load with `type=None`, not `UNKNOWN`
- kind matching is exact string matching; this spec does not introduce
  automatic hyphen/underscore normalization for catalog or extension kinds

### Examples

| Entity | `kind` | `type` | Schema |
|---|---|---|---|
| `task:t001` | `task` | `EntityType.TASK` | `TaskEntity` |
| `concept:selection-bias` | `concept` | `EntityType.CONCEPT` | `ProjectEntity` |
| `gene:PHF19` | `gene` | `None` | `DomainEntity` |
| `cytogenetic-event:del17p` | `cytogenetic-event` | `None` | project extension schema |

### Why `type: EntityType | None`

This spec chooses `EntityType | None` rather than a derived property because:

- it keeps migration straightforward for existing core-kind consumers
- it avoids compatibility layers that silently rewrite non-core kinds
- it makes the distinction explicit: some entities are Science-core typed,
  others are not

### Invariants

The model must enforce a consistency invariant so `kind` and `type` cannot
drift.

Required invariant:

- if `type is not None`, then `type == core_entity_type_for_kind(kind)`
- if `type is None`, then `core_entity_type_for_kind(kind) is None`

This makes `kind` the authoritative field and `type` a checked projection of
the core subset rather than a competing source of truth.

Type-specific invariants must no longer rely on every entity passing through
`EntityType`.

In practice:

- validators that currently branch on `self.type` in base `Entity`
  should move to the typed subclass that owns the invariant
- when a branch is kind-dependent, it should key off `self.kind` or the
  actual schema class, not a forced enum fallback

For example, dataset origin/access/derivation invariants belong on
`DatasetEntity`, not on base `Entity` guarded by `type == DATASET`.

## Storage Compatibility

This spec changes the canonical in-memory model contract, not the authored
storage format all at once.

Storage compatibility rule:

- loaders and adapters must accept legacy `type:` source fields
- if a raw record does not provide `kind`, the adapter or normalization layer
  may derive `kind` from legacy `type`
- if a raw record carries legacy `kind: parameter`, normalization must rewrite
  it to `canonical_parameter`
- `kind` is the canonical field after normalization

This preserves current markdown and aggregate sources while making the model
itself explicit and open-ended.

This spec chooses a stable compatibility answer now:

- authored storage may use `type:` or `kind:`
- adapter-level normalization accepts both indefinitely
- no project-wide frontmatter migration is required by this spec

## Loader Behavior

The loader flow becomes:

1. storage adapters produce raw records with `kind` present, either authored
   directly or derived from legacy `type`
2. `EntityRegistry.resolve(kind)` chooses the schema class
3. normalization fills shared defaults but does **not** force `kind` through
   `EntityType`
4. `type` is populated from a central core-kind mapping only when `kind` is a
   Science core kind
5. the selected schema validates the record

This rule applies to **all** normalization call sites, not just the main
adapter loop:

- the primary adapter-discovery load path
- legacy model loading
- legacy parameter loading

### Normalization rule

Loader normalization must stop doing:

- "`type` = `kind` for every entity"

and instead do:

- `kind` is always preserved
- `type = core_entity_type_for_kind(kind)` for core kinds
- `type = None` for non-core kinds

### Unknown kinds

Unknown kinds continue to behave according to existing caller policy:

- registry resolution failure remains explicit
- warn-and-skip or fail-fast behavior is chosen by the caller

This spec does not weaken the current posture on truly unregistered kinds.

### `unknown` policy

`EntityType.UNKNOWN` remains temporarily as a **compatibility-only** value.

Policy:

- an explicitly authored legacy record with `type: unknown` may normalize to
  `kind="unknown"` and `type=EntityType.UNKNOWN`
- loader code must never synthesize `UNKNOWN` from an arbitrary non-core kind
- `unknown` is not a fallback for catalog kinds, profile kinds, or project
  extension kinds

In other words, `unknown` remains readable as legacy data but is not part of
the new open-ended-kind strategy.

## Registry Model

`EntityRegistry` needs four ownership tiers:

- **core kinds**
- **profile kinds**
- **catalog kinds**
- **project extension kinds**

The current two-tier model (`core`, `extension`) is no longer sufficient once
profile kinds and catalog-contributed kinds both become first-class and must
not be shadowed by projects.

### Registration behavior

Core registration remains as it is conceptually:

- Science-owned core kinds register first
- typed core kinds map to typed subclasses
- untyped core kinds map to `ProjectEntity`

Profile registration is explicit:

- enabled profile manifests contribute additional valid kinds
- profile kinds register after core kinds and before catalog kinds
- profile-owned kinds keep the existing profile behavior already reflected in
  `known_kinds()`

Catalog registration is added:

- each declared ontology catalog contributes its `entity_types[].name`
- those kinds register to `DomainEntity`

Project extension registration remains last:

- project-defined kinds register after core and catalog kinds

### Resolution behavior

`EntityRegistry.resolve(kind)` should consult:

1. core kinds
2. profile kinds
3. catalog kinds
4. project extension kinds

The result is still exactly one schema class.

## Phase 2A: Catalog Kind Registration

### Input

`science.yaml` already declares:

```yaml
ontologies: [biology, chemistry]
```

and `load_catalogs_for_names()` already loads catalog metadata.

### New behavior

For each declared catalog:

- register every `entity_types[].name` into `EntityRegistry`
- route those kinds to `DomainEntity`
- preserve the catalog metadata separately for prefix and profile behavior as
  today

Examples from a biology catalog:

- `gene`
- `protein`
- `disease`
- `pathway`
- `phenotypic_feature`
- `biological_process`
- `anatomical_entity`
- `chemical_entity`

### What this enables

After this change:

- a locally authored entity with `kind: gene` can validate as a first-class
  `DomainEntity`
- the unified references spec can resolve shorthand to domain entities without
  relying on fake core types
- catalogs become owners of valid domain kind vocabulary, not just owners of
  external CURIE prefixes

### What it does not enable

This phase still does **not** provide:

- catalog-provided entity instances
- synonym expansion from catalogs
- local-vs-catalog overlay merge
- provider contracts or caching

Those belong to a later catalog-instance spec.

## Collision Policy

Kind ownership must stay explicit. This spec standardizes the following as
hard errors:

- core kind vs profile kind
- profile kind vs profile kind
- profile kind vs catalog kind
- project extension kind vs profile kind
- core kind vs catalog kind
- catalog kind vs catalog kind
- project extension kind vs core kind
- project extension kind vs catalog kind
- duplicate registration within the same tier

Rationale:

- a given `kind` must map to exactly one schema owner
- project customization should happen through local entities and `same_as`,
  not by redefining catalog vocabulary

Transition rule:

- enabling a new ontology in `science.yaml` may retroactively surface a hard
  collision with an existing profile or project-extension kind
- that failure should happen at load/registration time
- the diagnostic should identify both the pre-existing local/profile owner and
  the newly declared catalog owner so the project can rename or remove the
  conflicting kind deliberately

## Downstream Compatibility Rules

The main migration rule is simple:

- code that means "what kind of entity is this?" should use `entity.kind`
- code that means "is this one of the Science core semantic types?" may use
  `entity.type`, but must tolerate `None`

### Prohibited compatibility pattern

Code must not map arbitrary non-core kinds to `EntityType.UNKNOWN` merely to
preserve a closed-enum assumption.

That pattern hides exactly the domain information this spec is trying to make
first-class.

### Affected areas

#### Registry sync and indexing

Code that currently degrades domain kinds to `UNKNOWN` must:

- preserve `kind` exactly
- leave `type=None` for non-core entities

#### Generic graph and listing tooling

Code that filters, displays, or groups entities generically should prefer
`kind`.

#### Materialization and export

Code that currently assumes every entity kind has a corresponding
`entity.type.value` must be updated to key off `kind` when the operation is
about entity identity or category.

Minimum rule for RDF materialization:

- generic RDF class emission uses `entity.kind`, not `entity.type`
- the default class URI is `SCI_NS[_kind_class_name(entity.kind)]`
- kind-sensitive edge branches also key off `entity.kind`

So the current task special-case becomes conceptually:

- if `entity.kind == "task"` and `target.kind in {"hypothesis", "question"}`
  then emit `sci:tests`
- otherwise emit the generic relation

This spec does not require a full RDF redesign, but it does require
materialization paths to stop depending on the closed enum as the source of
truth.

#### Typed validators

Typed validators should live on the typed subclass that owns them. Base
`Entity` should not contain invariants that require every possible entity to
pretend it is a core enum member.

### Registry sync migration

Registry/index state that previously preserved only `entity.type.value` should
be refreshed from `entity.kind`.

Operationally:

- re-sync is authoritative for rebuilding correct `kind` values
- pre-existing rows degraded to `unknown` may be regenerated or explicitly
  migrated, but new sync runs must not perpetuate the degradation

## Backward Compatibility

This change is backward-compatible for existing core kinds:

- core entities still load with the same typed schemas
- existing frontmatter using `type:` continues to load
- code that branches on core semantic type can keep doing so after making
  `None` explicit

This change is intentionally **not** backward-compatible for consumers that
assume:

- every kind must exist in `EntityType`
- non-core kinds should silently degrade to `UNKNOWN`

Those are the assumptions the spec is replacing.

## Testing Strategy

The implementation should add coverage for:

- core entities still loading with expected typed schemas
- `kind/type` consistency invariants rejecting mismatched pairs
- catalog kinds registering successfully to `DomainEntity`
- a locally authored `gene:*` entity loading when the biology catalog is
  declared
- undeclared domain kinds still raising `EntityKindNotRegisteredError`
- project extensions being unable to shadow catalog kinds
- profile kinds and catalog kinds colliding as hard errors
- registry/index paths preserving `kind="gene"` and `type=None`
- loader compatibility with legacy `type:` storage when `kind` is absent
- legacy `type: unknown` records continuing to load as explicit compatibility
  data rather than silently breaking

Suggested test modules:

- `science-model/tests/test_entities.py` or a new focused model contract test
- `science-tool/tests/test_entity_registry.py`
- `science-tool/tests/test_load_project_sources_unified.py`
- `science-tool/tests/test_registry_sync.py`

## Implementation Order

Recommended sequence:

1. Add `kind: str` and make `type: EntityType | None` in the base entity model.
2. Move type-specific invariants from base `Entity` to the owning typed
   subclass where needed.
3. Update loader normalization to preserve `kind` and populate `type` only for
   core kinds across all normalization call sites.
4. Extend `EntityRegistry` with explicit profile and catalog registration
   tiers.
5. Register declared ontology catalog kinds to `DomainEntity`.
6. Update downstream sync/index code to preserve `entity.kind` and stop
   degrading non-core kinds to `UNKNOWN`.
7. Update materialization/export code to use `entity.kind` for generic RDF
   typing and kind-sensitive branching.
8. Update remaining CLI/display code that still treats `entity.type` as the
   authoritative kind label.
9. Update tests and fixtures.

## Resolved Decisions

- `kind` is the authoritative open-ended discriminator at load time.
- `type` remains only as an optional Science-core semantic classification
  field.
- This spec chooses `EntityType | None` rather than a derived compatibility
  property.
- `core_entity_type_for_kind(kind)` is the normative source of truth for the
  core-kind subset.
- Catalog phase 2A registers kind vocabulary only; it does not provide entity
  instances.
- Profile kinds are an explicit ownership tier distinct from core, catalog,
  and project-extension kinds.
- Catalog kinds route to `DomainEntity` initially.
- Project extensions may not shadow catalog-contributed kinds.
- `EntityType.UNKNOWN` remains only as a legacy compatibility value, never as
  a fallback for non-core kinds.

## Open Questions

- For materialization, what is the minimal generic RDF typing strategy for
  catalog kinds once catalogs begin contributing instances and domain-specific
  graph terms beyond the default `sci:<Kind>` class naming?
- When a future catalog-instance phase lands, should locally authored domain
  entity extensions reuse the same `DomainEntity` schema class or introduce
  catalog-specific subtypes?

## Relationship To Other Specs

- **2026-04-20 unified entity model**
  - this spec operationalizes the open-ended extension principle by making
    `kind` authoritative and by adding catalog-owned kind registration

- **2026-04-21 unified entity references**
  - this spec supplies the explicit prerequisite that change 2A depends on:
    domain kinds must be loadable before catalogs can contribute them

- **Future catalog-instance spec**
  - that later spec can build on this document's kind-registration contract to
    define instance providers, merge tiers, and cache/refresh behavior

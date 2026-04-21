# Unified Entity Model and Storage Adapter Design

**Date:** 2026-04-20
**Status:** Draft (replacement spec)
**Replaces:** `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md` rev 1.1
**Builds on:** `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` rev 2.2
**Forward:** implementation plan and migration sequencing to follow in a separate planning doc

## Motivation

The current entity-loading architecture in `science` has a deeper problem than "too many loaders."
It has multiple modeling centers:

- `Entity` in `science_model.entities`
- task-specific models
- source-contract models for models / parameters
- storage-shaped records in markdown frontmatter, `entities.yaml`, task files, and datapackages

This has led to two kinds of complexity:

1. **Storage complexity**
- entities can be stored in several unrelated ways
- adding a new storage convention requires new loader logic
- generic functionality has to understand too many persistence details

2. **Model complexity**
- there is not one clear canonical model family for authored things in Science
- specialized cases are modeled as separate schemas rather than typed extensions of a shared base
- loader code is forced to smooth over schema differences after the fact

This spec replaces the provider-first framing with a model-first framing.

The core idea is simple:

- Science should have **one canonical entity model family**
- specialized entity types should extend that family
- storage formats should be adapters over that family
- project-specific entity kinds should be extensible without becoming permanent core types

## Problem Statement

There are three distinct goals:

1. Provide a common API / shape for first-class authored things in Science.
2. Reduce the number of storage conventions to a smaller, simpler set.
3. Abstract the logic for reading and writing entities so storage concerns are isolated.

The goal is **not** to flatten all entity types into one giant generic record.
Tasks, datasets, workflow runs, research packages, and future project-specific types can remain specialized.

The goal is to give them:

- a common core contract when they need to be handled generically
- type-specific schemas when they need stronger rules or richer semantics

## Design Principles

- **One model family.** There must be one canonical entity model family in Science. No parallel core schemas for authored entities.
- **Model first, storage second.** Decide what an entity is before deciding how it is stored.
- **Specialize only when rules differ.** A specialized entity type is warranted when it adds real invariants or lifecycle semantics, not just a handful of optional fields.
- **Storage adapters are not ontology.** Markdown, aggregate files, datapackages, and task files are persistence formats, not the definition of the entity model.
- **Core types are few.** Science core should own only genuinely cross-project typed entities.
- **Project types are extensible.** A project must be able to define new entity variants without introducing a new parallel data model.
- **Generic tooling targets the base contract.** Graph loading, entity resolution, aliasing, linking, and generic listing should rely on the shared base entity interface.
- **Type-specific tooling targets typed entities.** Dataset gates, task workflows, and similar logic should operate on the appropriate typed entity schema.

## Architecture Overview

The design has four layers:

1. **Canonical entity layer**
- Shared base contract used by generic tooling.

2. **Entity subfamily layer**
- Shared semantic sub-bases for project-facing and domain-facing entities.

3. **Typed entity layer**
- Science-owned specialized entity types such as `TaskEntity` and `DatasetEntity`.

4. **Project extension layer**
- Project-defined entity variants that extend the same base model family.

5. **Storage adapter layer**
- Adapters that read and write entities from markdown, aggregate files, datapackages, and other supported formats.

The critical separation is:

- entity schemas define validity and semantics
- storage adapters define persistence and discovery

## Canonical Base Model

### `Entity`

`Entity` becomes the canonical base model for first-class authored things in Science.

It should remain intentionally small and stable. It exists to support generic behavior across many entity kinds, especially:

- graph materialization
- identity resolution
- aliasing
- linking
- generic listing / search
- provenance and source attribution
- storage-independent loading

### Base fields

The exact field list can evolve, but the base contract should include only cross-cutting fields such as:

- `id`
- `canonical_id`
- `kind`
- `title`
- `status`
- `profile`
- `aliases`
- `same_as`
- `related`
- `source_refs`
- `ontology_terms`
- `description` or canonical prose body
- source-location / provenance metadata

Existing fields like `content_preview` may remain as derived or compatibility fields during migration, but they should not drive the architecture.

### What does not belong in base `Entity`

Type-specific workflow or provenance rules do not belong in the base model. Examples:

- dataset origin / access / derivation blocks
- task blocking semantics
- workflow-run production semantics
- research-package display composition rules

Those belong in typed entity schemas.

## Entity Subfamilies

The canonical `Entity` base is intentionally minimal. Most semantic structure should begin one level below it.

Science should distinguish two important subfamilies:

- `ProjectEntity`
- `DomainEntity`

These are not separate model systems. They are semantic sub-bases inside one model family.

### `ProjectEntity`

`ProjectEntity` represents entities about the conduct of a science project.

Examples:

- task
- hypothesis
- question
- dataset
- workflow-run
- research-package
- plan

These entities are usually:

- authored inside a project workspace
- lifecycle-driven
- operational or epistemic in purpose
- tied to project-local provenance and source locations

Likely fields or assumptions that often belong here:

- project-local status or maturity
- authored prose / notes
- source-path metadata
- project profile / namespace metadata where applicable

### `DomainEntity`

`DomainEntity` represents entities about the external domain being studied.

Examples:

- biological entities
- diseases
- pathways
- phenotypes
- chemicals
- environmental exposures

These entities are usually:

- grounded in external authorities or ontologies
- less tied to project-local workflow state
- more concerned with canonicalization, synonyms, and ontology alignment

Likely fields or assumptions that often belong here:

- external identifiers
- authority / ontology grounding metadata
- synonym sets
- grounding confidence or provenance

### Why formalize the split

This distinction helps keep two graphs legible:

1. the **project graph**
- the operational / epistemic structure of the research process

2. the **domain graph**
- the modeled subject matter the research is trying to understand

These graphs interact constantly, but they are not the same thing. Formalizing the distinction helps prevent project-operational fields from leaking into domain entities, and vice versa.

## Typed Entity Model

Specialized entity types extend `Entity` when they carry real additional invariants or lifecycle semantics.

An **invariant** here means a rule that must always be true for an instance of that type to be valid.

Examples:

- if a dataset has `origin == "external"`, it must satisfy one set of provenance requirements
- if a dataset has `origin == "derived"`, it must satisfy a different set
- a task may impose stricter rules around dependency references or state transitions

Extra optional fields alone are not enough reason to create a subtype.

In practice, typed entities will usually extend either `ProjectEntity` or `DomainEntity`, not `Entity` directly.

### Core Science typed entities

The initial core typed entities should be:

- `TaskEntity`
- `DatasetEntity`
- `WorkflowRunEntity`
- `ResearchPackageEntity`

These are concepts Science already appears to own across projects and tool behavior.

### `TaskEntity`

`TaskEntity` is a core Science typed entity and should extend `ProjectEntity`.

It extends `Entity` with task-specific fields and validations, for example:

- task namespace / task identifier handling
- dependency fields such as `blocked_by`
- task-specific state semantics
- any structural rules currently implied by the task DSL

Tasks should no longer be treated as a separate modeling center. They are a specialized entity type in the same model family.

### `DatasetEntity`

`DatasetEntity` is a core Science typed entity and should extend `ProjectEntity`.

It extends `Entity` with dataset-specific provenance and lifecycle fields, such as:

- `origin`
- `access`
- `derivation`
- `accessions`
- `datapackage`
- `local_path`
- `consumed_by`
- `parent_dataset`
- `siblings`

Dataset-specific invariants remain on this type, not on generic `Entity`.

### `WorkflowRunEntity`

`WorkflowRunEntity` is a core Science typed entity because Science already treats workflow-run provenance as a first-class concept in dataset logic and graph materialization. It should extend `ProjectEntity`.

This type should own workflow-run-specific semantics rather than leaving them as loose frontmatter conventions.

### `ResearchPackageEntity`

`ResearchPackageEntity` is a core Science typed entity because package composition and dataset-display relationships are already treated as cross-project semantics in Science tooling. It should extend `ProjectEntity`.

Science does not need to ship built-in `DomainEntity` subtypes immediately. The domain side can be introduced incrementally through project extensions unless and until true cross-project domain primitives emerge.

## Model Registry and Kind Resolution

The load-bearing mechanism in this design is a registry that resolves `kind -> schema`.

This must be explicit.

### Registry responsibilities

The model registry is responsible for:

- registering built-in core schemas
- registering project extension schemas
- resolving a raw record's `kind` to the correct schema
- preventing conflicting registrations

### Registration rules

For v1, registration should be explicit Python registration during project load.

A minimal conceptual API is enough:

```python
registry.register_core_kind("task", TaskEntity)
registry.register_core_kind("dataset", DatasetEntity)
registry.register_extension_kind("natural-system:model", NaturalSystemModelEntity)
```

The exact API names can differ, but the behavior should be:

- core kinds are registered by Science
- extension kinds are registered by the project
- duplicate registrations are hard errors
- extension code may not shadow a core kind

If a project wants stricter validation for a core type such as `dataset`, it should do so through hooks or additional project-level checks, not by replacing the core schema for the same kind in v1.

### Resolution flow

The resolution flow should look like this:

```python
for source_ref in adapter.discover(project_root):
    raw_record = adapter.load_raw(source_ref)
    kind = raw_record["kind"]
    schema = registry.resolve(kind)
    entity = schema.model_validate(raw_record)
    identity_table.add(entity.canonical_id, source_ref)
    entities.append(entity)
```

Key points:

- dispatch is on the record's declared `kind`
- adapters do not choose the final schema
- the registry does
- validation happens at construction time through the resolved schema

This preserves the existing Science preference for early, schema-level validation rather than delayed post-load cleanup.

## Project Extension Mechanism

Science core should not hardcode every historical or project-local entity kind.

Instead, projects should be able to define their own typed entity variants by extending the same base model family.

### Extension goals

A project-defined extension should be able to:

- declare a new `kind`
- extend `Entity` with additional fields
- attach type-specific validation or normalization logic
- participate in generic graph loading and resolution
- optionally register storage serialization rules

### Registration mechanism

For v1, the extension mechanism should be explicit and local:

- project code provides one or more extension schema classes
- project startup registers them with the model registry
- graph loading uses the already-built registry

This should not rely on plugin entry points in v1.

Entry-point discovery or plugin packaging can come later if it becomes necessary.

### What Science core must know

Science core should know only enough to:

- recognize the kind
- instantiate the registered schema
- validate it
- expose it through generic entity tooling

Science core should not need to special-case the extension in the core architecture.

### Conflict policy

The conflict policy should be strict:

- no duplicate registration for the same `kind`
- no extension may shadow a core kind
- conflicting extension registrations are hard errors

This avoids ambiguous schema dispatch.

### Implication for current `model` / `parameter`

Current `model` and `parameter` records should not be treated as permanent core architectural concepts unless there is a clear cross-project case for them.

This spec makes the following v1 decision:

- `model` and `parameter` are **not** core Science typed entities

If they still matter for one or a small number of projects, they should be expressed as extension-defined entity kinds or as project-local source records that materialize into entities through the same model family.

This removes the need for permanent hardcoded exceptions in core `science`.

## Storage Model

Storage is a separate concern from modeling.

Science should converge on a small number of storage patterns:

1. **Single-entity storage**
- one authored entity per file
- typically markdown or another human-authored format

2. **Multi-entity storage**
- many entities in one file
- typically JSON or YAML for thin records

3. **Datapackage-backed storage**
- a datapackage file also serves as the authored representation of an entity, usually for datasets

Other storage conventions should be added only when they provide real value.

## Storage Adapters

Storage adapters are responsible for reading and writing entities from a persistence format.

They are not the place to define entity semantics.

### Responsibilities

A storage adapter may:

- discover files
- parse storage-specific syntax
- load records into the canonical entity model family
- serialize entity instances back to storage
- provide source-location metadata

It may not redefine what counts as a valid dataset, task, or workflow run. That belongs to typed entity schemas.

### Adapter contract

The old provider abstraction is replaced by a narrower storage-adapter contract.

A minimal v1 interface should look conceptually like:

```python
class SourceRef(BaseModel):
    adapter_name: str
    path: str
    line: int | None = None


class StorageAdapter(Protocol):
    name: str

    def discover(self, project_root: Path) -> list[SourceRef]:
        ...

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        ...

    def dump(self, entity: Entity) -> str | dict[str, Any]:
        ...
```

Notes:

- `discover()` owns file discovery and storage-specific conventions
- `load_raw()` returns a raw record in a registry-dispatchable shape, including `kind`
- `dump()` is optional in early migration if write support is deferred for an adapter
- `SourceRef` carries source-location metadata used in error messages and collision reporting

The exact names can differ, but the design should preserve these responsibilities.

### Discovery semantics

Discovery semantics should be adapter-defined by default.

Each adapter should declare:

- its discovery roots relative to `project_root`
- the file naming or glob conventions it recognizes
- any format-specific recognition rules

In v1:

- roots are defined by the adapter
- roots may become project-configurable later
- all discovery resolves relative to the active project root

This restores the lost discovery semantics without reintroducing a provider-heavy abstraction.

### Initial adapter families

The initial design should support adapters for:

- single-entity markdown files
- multi-entity JSON / YAML files
- datapackage-backed dataset entities

Task storage may continue to use a task-specific file adapter during migration, but that adapter should load `TaskEntity` instances, not a separate task model family.

### Task adapter plan

The task DSL remains supported in v1 as a storage adapter, not as a separate model system.

That means:

- the task parser continues to parse the existing DSL
- the adapter converts parsed task records into `TaskEntity` raw records
- registry resolution and schema validation then produce `TaskEntity` instances

The DSL is therefore a persistence detail. A future migration to a more standard single-entity storage format remains possible, but is not required by this spec.

## Read / Write Architecture

The old "resolver over unrelated loaders" design should be replaced by a simpler read / write architecture:

- storage adapters discover and parse records
- a model registry resolves the target entity schema
- records are validated into `Entity` or a typed subclass
- generic tooling consumes the base contract
- specialized tooling consumes typed entity instances where needed

This gives Science a single conceptual flow:

`storage format -> storage adapter -> entity schema -> validated entity instance`

not:

`format-specific loader -> ad hoc source type -> normalization bridge -> pseudo-common shape`

### Collision mechanism

Identity collisions across adapters remain hard errors, and the mechanism should be explicit.

During load, Science maintains a global identity table keyed by canonical entity identity.

Conceptually:

```python
identity_table: dict[str, SourceRef] = {}

for entity, ref in loaded_entities:
    existing = identity_table.get(entity.canonical_id)
    if existing is not None:
        raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
    identity_table[entity.canonical_id] = ref
```

This check happens after schema validation and applies across all adapters, not just within one adapter.

## Source Location and Error Reporting

Source-location metadata must survive the architectural rewrite.

Science needs usable error messages for:

- validation failures
- collision reporting
- malformed authored records

At minimum, source-location metadata should include:

- adapter name
- file path
- optional line number where available

This metadata may travel as a dedicated `SourceRef`, as provenance metadata attached to the entity instance, or both.

The important requirement is architectural, not cosmetic:

- the load pipeline must preserve enough location information to produce actionable error messages

## Identity and Generic Behavior

Generic entity behavior should operate on the canonical base contract.

This includes:

- canonical ID resolution
- alias registration
- cross-entity linking
- generic graph node materialization
- generic entity search and listing

This is the main reason to insist on one model family.

A tool should not need to care whether the entity came from:

- a markdown file
- an aggregate JSON file
- a datapackage
- a task file

It should care only about the validated entity instance and its typed kind when type-specific behavior is needed.

## Relationships and Graph Materialization

This spec does not redesign the graph store, but it does need one clear statement about relationships.

In v1:

- authored entity records may carry relationship-bearing fields
- some of those are generic base references, such as `related`, `same_as`, `source_refs`, and `ontology_terms`
- others are typed references, such as `blocked_by`, `consumed_by`, `siblings`, or package display lists

These fields remain part of entity schemas where they are authored as part of the entity record.

Graph materialization may still normalize them into graph edges in downstream code.

This spec does **not** decide:

- the final in-memory edge store
- a new query API
- a reworked RDF materialization layer

Those remain follow-on concerns.

## Datapackage-backed Entities

Datapackage-backed storage remains a supported pattern, especially for datasets.

This spec preserves the important separation introduced in rev 2.2:

- the authored dataset entity may be represented by the datapackage
- the datapackage may still contain runtime-only structures that are not fields on `DatasetEntity`

In particular, runtime package details such as `resources[]` remain runtime datapackage concerns unless and until they are explicitly promoted into the entity schema.

So the adapter boundary is:

- adapter reads the datapackage file
- adapter extracts the subset that maps to `DatasetEntity`
- runtime-only package detail remains in the datapackage layer rather than bloating the entity schema

## Migration of Existing Concepts

### Markdown-backed authored entities

Existing markdown-authored entities should migrate into the unified entity model directly.

This is mostly a storage-adapter concern, not a modeling change.

### Tasks

Tasks should migrate from a separate task model into `TaskEntity`.

The task file format may remain temporarily, but it becomes a persistence format for `TaskEntity`, not a separate data model.

### Datasets

Dataset entities should migrate into `DatasetEntity`.

The markdown-sidecar versus datapackage-backed distinction becomes a storage question only.

The "promoted dataset" idea still makes sense, but it should be framed as:

- one `DatasetEntity`
- multiple supported storage adapters

not as a separate category of entity source.

### Models and parameters

Current model / parameter source contracts should be re-evaluated.

Decision in this spec:

- they are **not** core Science typed entities
- they should be removed from the core architecture
- if needed, they should be handled through the project extension mechanism

## Collision and Validation Policy

Identity collisions remain hard errors.

If two storage adapters produce distinct authored sources for the same canonical entity identity, that is a project-state error and should fail early.

Validation should happen at instance construction time through the resolved schema:

- base `Entity` validation for shared rules
- typed entity validation for type-specific invariants
- extension validation for project-defined kinds

This preserves the current Science bias toward early validation rather than permissive loading plus cleanup.

This avoids encoding validity rules inside storage-adapter code.

## Compatibility with Rev 2.2 Commitments

This spec is an architectural replacement, not a rollback of rev 2.2 commitments.

The following remain in force unless explicitly superseded in a later implementation plan:

- dataset-specific invariants remain enforced
- recursion-safe gate logic remains required
- comment-preserving edits remain a write-path expectation where already committed
- existing migration and reconcile workflows are not implicitly removed by this spec

What changes here is the architectural framing:

- those behaviors should be implemented against the unified entity model family
- they should not require parallel model systems to exist

## Worked Examples

### Example 1: markdown-authored hypothesis

1. markdown adapter discovers `doc/hypotheses/foo.md`
2. adapter parses frontmatter + body into a raw record with `kind = "hypothesis"`
3. registry resolves `"hypothesis"` to the registered schema
4. schema validates into a `ProjectEntity`-family instance
5. entity is added to the identity table and generic graph-loading pipeline

### Example 2: aggregate JSON topics file

1. aggregate adapter discovers `doc/topics/topics.json`
2. adapter loads one entry and produces a raw record with `kind = "topic"`
3. registry resolves `"topic"` to the registered schema
4. schema validates into the correct entity type
5. each validated entity is collision-checked globally

### Example 3: datapackage-backed dataset

1. datapackage adapter discovers `data/myset/datapackage.yaml`
2. adapter extracts dataset-authored fields from the datapackage into a raw record with `kind = "dataset"`
3. registry resolves `"dataset"` to `DatasetEntity`
4. `DatasetEntity` validates dataset-specific invariants at construction time
5. runtime-only package fields such as `resources[]` remain in the datapackage layer

## Scope

### In scope

- define `Entity` as the canonical base model
- define `ProjectEntity` and `DomainEntity` as semantic sub-bases
- define the initial set of Science-owned typed entities
- define a project extension mechanism
- define a model registry and `kind -> schema` resolution flow
- define the storage-adapter concept around the unified model family
- define a minimal storage-adapter contract
- reduce supported storage patterns to a smaller, explicit set
- establish migration direction for tasks and datasets
- remove `model` / `parameter` from the core architecture in v1

### Out of scope

- the exact implementation plan and commit sequencing
- caching and indexing
- plugin packaging details
- full CLI migration tooling
- final decisions on every possible built-in typed entity beyond the initial core set

### Non-goals

- redesigning the graph store
- redesigning RDF materialization
- defining a new query API
- solving caching, watching, or index persistence
- flattening project and domain entities into one undifferentiated record shape

## Testing Strategy

Testing should follow the architecture.

### Model tests

First, test the model family:

- base `Entity` validation
- `TaskEntity` invariants
- `DatasetEntity` invariants
- `WorkflowRunEntity` invariants
- `ResearchPackageEntity` invariants
- extension registration behavior

### Adapter tests

Then test storage adapters:

- markdown single-entity read / write
- aggregate JSON / YAML read / write
- datapackage-backed dataset read / write
- task file adapter roundtrip into `TaskEntity`

### Migration and regression tests

Finally, test migration behavior:

- existing projects still load into the unified entity model family
- mixed storage modes work where explicitly supported
- identity collisions fail early
- generic graph-loading behavior stays stable

Regression fixtures and golden snapshots remain valuable and should be preserved in the follow-on implementation plan, especially where they protect against behavior drift during migration.

## Resolved Decisions

- Science should have one canonical entity model family.
- `Entity` is the base contract for generic behavior.
- `ProjectEntity` and `DomainEntity` are semantic sub-bases inside the same model family.
- Specialized entity types extend `Entity` when they add real invariants or lifecycle semantics.
- `TaskEntity` is a core Science typed entity.
- `DatasetEntity`, `WorkflowRunEntity`, and `ResearchPackageEntity` are the initial additional core typed entities.
- Project-specific types should extend the same model family rather than creating parallel core schemas.
- `kind -> schema` dispatch is handled by an explicit model registry.
- storage adapters discover files and produce raw records; the registry resolves final schemas.
- collisions are detected through a global identity table across all adapters.
- Storage adapters are persistence concerns only.
- Supported storage patterns should converge on a small set: single-entity, multi-entity, and datapackage-backed.
- Current `model` / `parameter` concepts are not core typed entities in v1.

## Follow-on Work

- write the implementation plan for migrating current code to this architecture
- decide which current `Entity` fields remain base fields versus become typed fields or derived fields
- define the exact supported single-entity and multi-entity file formats
- define write-path behavior and migration tooling
- decide whether core domain-side built-in entity types are warranted in a later phase
- revisit caching only after the model boundary is clean

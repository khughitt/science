# Multi-Backend Entity Resolver

**Date:** 2026-04-20
**Status:** Draft (rev 1.1 — design-review revisions)
**Revision history:**
- rev 1 — initial design (provider abstraction, three v1 providers, single-layer interface, hard-error collisions).
- rev 1.1 (this rev) — design-review fixes: `EntityDiscoveryContext` carries shared loading state; `SourceEntity` and shared types lifted to neutral `source_types.py` (no import cycle); global collision check in `load_project_sources` covers both resolver output and specialized parsers; `provider` field is required-with-explicit-values (no defaulting); aggregate inputs validate through dedicated `EntityRecord` schema with shared normalizer; entity-profile datapackage with invalid schema raises `EntityDatapackageInvalidError` (silent-skip only for non-entity datapackages); regression snapshot uses a projection that excludes new fields. Plus: `SourceEntity.description` field added (mirrors `Entity.content`); each provider sources prose from its native location.
**Builds on:** `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (rev 2.2). The forward-reference there now resolves here.
**Supersedes:** `docs/specs/2026-04-19-multi-backend-entity-resolver-handoff.md` (the stub captured during dataset-lifecycle handoff; this spec replaces it).
**Forward (Spec Z):** caching, indexing, in-memory store shape, edge representation. Not in this spec; a follow-on with a handoff note at the end.

## Motivation

The framework already has multiple entity loaders. They evolved organically and live side-by-side in `science-tool/src/science_tool/graph/sources.py`'s `load_project_sources`:

- `_load_markdown_entities` — walks `doc/`, `specs/`, `research/packages/` for `*.md` with YAML frontmatter
- `_load_structured_entities` — reads `entities.yaml` (one file lists papers, concepts, etc.)
- `_load_task_entities` — parses tasks from a custom markdown DSL
- `_load_model_sources` — reads model definitions
- `_load_parameter_sources` — reads parameter sources

This is multi-backend storage in disguise. The pattern works, but the ad-hoc structure has three concrete pain points:

1. **Adding a new storage convention requires a sixth named loader, not a clean extension.** The dataset-entity-lifecycle spec (rev 2.2) introduced datasets that logically want to live as `data/<slug>/datapackage.yaml` — the runtime datapackage IS the entity, with no markdown sidecar. Adding this requires either a new `_load_datapackage_directory_entities` function or wedging the logic into the existing markdown loader. Neither is clean.
2. **Aggregate-storage is hardcoded to one file** (`entities.yaml`). The mm30 project has ~200 rare topics whose health-check warnings are blocked because each lacks a thin markdown file. Creating 200 stub `.md` files is overhead for no analytical value. Putting them in one `topics.json` is the natural fit, but the existing aggregate loader can't be pointed at arbitrary aggregate files.
3. **Type-driven specialized parsers** (tasks, models, parameters) are conflated with format-driven generic loaders (markdown, structured-entities). The first kind has legitimate reasons to be one-off (custom DSLs, custom semantics); the second kind should be a clean abstraction.

The dataset-entity-lifecycle spec made one small concession to the right design — a "per-entity-type discovery rule" hardcoded into the markdown loader's roots list — and explicitly deferred the broader cleanup to this spec.

## Goal

Extract the format-driven loaders into a single `EntityProvider` abstraction and an `EntityResolver` coordinator. Add the missing `DatapackageDirectoryProvider` for promoted datasets. Generalize the existing aggregate loader so single-type aggregate files (`topics.json`) work alongside the existing multi-type `entities.yaml`. Specialized parsers (tasks/models/parameters) stay outside the resolver — they're not providers.

The result: zero per-project config required. Each provider knows where to look on disk and what signals "this is an entity"; all providers run on every load; results merge by `canonical_id`; collisions are hard errors. Adding a new storage convention later means writing one new `EntityProvider` subclass; no changes to call sites.

## Design Principles

- **Format-driven backends only.** A "provider" handles a generic file format that multiple entity types can share. Type-driven specialized parsers (custom DSL per entity type) stay outside the abstraction. Conflating the two would water down the interface or require carve-outs.
- **No per-entity-type configuration.** Providers don't care about entity types. Each provider auto-discovers what it can read; the resolver merges all outputs. mm30 doesn't declare "topics use the aggregate provider" — it just creates `doc/topics/topics.json`, and the AggregateProvider finds it.
- **No per-project configuration in v1.** All providers always run. Optional opt-out via `science.yaml` is a future addition if false positives appear.
- **Auto-discovery is filesystem-convention-driven.** Each provider has its own scan roots and recognition heuristics. Where ambiguity exists (a directory could hold either entity files or non-entity files), the provider uses an explicit signal: the `DatapackageDirectoryProvider` only emits entities for datapackages whose `profiles:` includes `"science-pkg-entity-1.0"`.
- **ID collisions are hard errors.** If two providers both claim to produce the same `canonical_id`, that's a project-state error (mid-migration mistake or legitimately ambiguous file). Halt with both source paths in the message; let the user resolve. Never silently pick a winner.
- **Mid-migration mixed mode is supported.** During a migration (e.g., promoting datasets from markdown to datapackage-directory), some entities live in the old provider and some in the new. Both providers find their respective entities; resolver merges them. Only collisions (same ID in both) error.
- **Behavior preservation is the refactor's success criterion.** Every existing project must produce byte-identical `load_project_sources` output before and after the refactor (excluding any new providers' outputs the project chooses to add). A snapshot regression test is the acceptance gate.
- **Cache-friendly interface, but no cache in v1.** The provider interface (`discover() -> list[SourceEntity]`) is shape-compatible with a future memoizing wrapper. Caching, indexing, and in-memory store shape are deferred to Spec Z.
- **Specialized parsers stay in `load_project_sources`'s direct callsites.** They're not providers and don't pretend to be. The resolver replaces only the format-driven loaders.

## Scope

### In scope (v1)

- New module `science-tool/src/science_tool/graph/source_types.py` housing shared types: `SourceEntity`, `SourceRelation`, `KnowledgeProfiles`, `EntityIdCollisionError`, `EntityDatapackageInvalidError`. Lifted out of `graph/sources.py` so `entity_providers/` can import them without creating an import cycle.
- New module `science-tool/src/science_tool/graph/entity_providers/` containing:
  - `EntityProvider` abstract base class + `EntityDiscoveryContext` dataclass (`base.py`)
  - `EntityRecord` Pydantic schema for normalized aggregate input + shared `_normalize_record(...)` helper (`base.py` or `record.py`)
  - `MarkdownProvider` (refactor of `_load_markdown_entities`)
  - `DatapackageDirectoryProvider` (NEW — promotes datasets to live as `data/<slug>/datapackage.yaml`)
  - `AggregateProvider` (refactor of `_load_structured_entities`, generalized to support single-type aggregate files like `doc/topics/topics.json`)
  - `EntityResolver` coordinator (`resolver.py`)
  - `default_providers()` factory returning the v1 provider list
- `load_project_sources` in `graph/sources.py` builds an `EntityDiscoveryContext`, switches from direct loader calls to `EntityResolver(default_providers()).discover(ctx)` for the format-driven path, and runs a **final global collision check** across BOTH resolver output and specialized-parser output (so a task or model with the same `canonical_id` as a markdown entity is caught).
- Specialized parsers (`parse_tasks`, `_load_model_sources`, `_load_parameter_sources`) keep their existing direct callsites in `load_project_sources` — UNCHANGED in shape, but each is updated to set its `SourceEntity.provider` value explicitly (`task` / `model` / `parameter`).
- `SourceEntity` gains two new required fields:
  - **`provider: str`** — explicit, no default. Six valid values in v1: `markdown`, `aggregate`, `datapackage-directory`, `task`, `model`, `parameter`. Every loader sets it. Downstream consumers can branch on origin (specifically: the `dataset_cached_field_drift` health check skips entities with `provider == "datapackage-directory"`).
  - **`description: str = ""`** — entity prose body. Mirrors `Entity.content` from `science_model.entities`. Sourced per-provider: MarkdownProvider from the post-frontmatter body, DatapackageDirectoryProvider from the datapackage's top-level Frictionless `description:` field, AggregateProvider from each entry's optional `description:` field, `parse_tasks` from `task.description`. Models/parameters leave it empty (no current source).
- All three format-driven providers funnel their raw records through a shared `_normalize_record(record: EntityRecord, ctx: EntityDiscoveryContext, provider_name: str) -> SourceEntity` helper that applies paper-ID canonicalization, alias derivation, profile defaulting, and kind validation. Single source of truth for normalization, regardless of which provider extracted the record.
- DatapackageDirectoryProvider raises `EntityDatapackageInvalidError` (with file path + field-level message) when a datapackage with `science-pkg-entity-1.0` in its `profiles:` has invalid YAML or is missing required fields. Datapackages without that profile remain silently ignored (existing behavior for the non-entity case).
- Snapshot-based regression test: a "kitchen-sink" fixture project containing one of each existing entity type. The snapshot uses a **projected dict** that excludes `provider` and `description` (the new fields) until those fields are intentionally rolled out (later steps in the implementation plan). The projection makes "behavior-preserving refactor" defensible across the early commits; new-field assertions live in separate tests.
- Per-provider unit tests, resolver tests, integration tests for the new capabilities (single-type aggregate, datapackage-directory promotion, prose roundtrip per provider).

### Out of scope (v1)

- **Caching, indexing, in-memory store** — Spec Z, with a handoff stub planted at the end of this spec.
- **`science.yaml` provider opt-out** (`entity_providers: { disabled: [...] }`). Documented as follow-on; no concrete demand yet.
- **Migration commands** — `science-tool dataset promote <slug>` (markdown dataset → datapackage-directory entity), `science-tool entities aggregate <type>` (collect markdown entities into a single-type aggregate file). Manual migration is straightforward; helpers can be added if usage patterns warrant.
- **Specialized-parser refactor.** Tasks, models, parameters keep their existing structure. Their bespoke formats don't fit a generic provider interface and there's no demand for a unification.
- **Plugin discovery** (e.g., entry-points-based provider registration). v1's `default_providers()` is a hardcoded list. Pluggable registration can come later if a project ever needs a project-specific provider.
- **Cross-project shared providers.** Each project runs its own provider list against its own filesystem. No federated entity discovery.
- **Filesystem watching / live reload.** Discovery is on-demand (per `science-tool` invocation). Spec Z may add this.

## Architecture Overview

Two distinct kinds of entity-loading code, made explicit:

```
┌──────────────────────────────────────────────────────────────────────┐
│  load_project_sources(project_root) → ProjectSources                 │
└──────────────────────────────────────────────────────────────────────┘
            │                                 │
            ▼                                 ▼
┌──────────────────────────┐    ┌────────────────────────────────────┐
│  Generic providers       │    │  Specialized parsers (UNCHANGED)   │
│  (format-driven,         │    │  (type-driven, custom DSL)         │
│   handle many types)     │    │                                    │
│                          │    │  - parse_tasks (markdown DSL)       │
│  - MarkdownProvider      │    │  - _load_model_sources              │
│  - DatapackageDirectory  │    │  - _load_parameter_sources          │
│      Provider (NEW)      │    │                                    │
│  - AggregateProvider     │    │  Stay direct callsites — they       │
│                          │    │  don't fit a generic interface.    │
│  Run via EntityResolver  │    │                                    │
└──────────────────────────┘    └────────────────────────────────────┘
            │                                 │
            └─────────┬───────────────────────┘
                      ▼
         ┌─────────────────────────────┐
         │  Combined entity list       │
         │  Dedup by canonical_id      │
         │  Collisions = hard error    │
         └─────────────────────────────┘
```

**Three providers in v1:**

1. **`MarkdownProvider`** (refactor of existing `_load_markdown_entities`). Walks `doc/**/*.md`, `specs/**/*.md`, `research/packages/**/research-package.md`. Treats files with YAML frontmatter as entities; type from frontmatter `type:` (or filename inference for legacy entries). All entity types currently using markdown continue to work unchanged.

2. **`DatapackageDirectoryProvider`** (NEW). Walks for `**/datapackage.yaml` files under `data/`, `results/`. **Filters strictly:** only files whose `profiles:` includes `"science-pkg-entity-1.0"` are emitted as entities — without this, every staged data package would become a phantom entity. Promoted datasets live here; no markdown sidecar required.

3. **`AggregateProvider`** (refactor of existing `_load_structured_entities`, generalized). Two file conventions, both supported:
   - **Multi-type aggregate** — `entities.yaml` (existing convention; one file lists papers, concepts, etc., each entry has `kind:` field). Backward-compatible.
   - **Single-type aggregate** — `<dir>/<plural>/<plural>.{json,yaml}` (e.g., `doc/topics/topics.json`). Each list entry becomes one entity; type inferred from the filename (singular form of the parent directory's plural name).

**`EntityResolver`** is a tiny coordinator (~50 lines) that holds the list of providers, calls `discover()` on each, concatenates results, and checks for ID collisions. No magic, no per-type dispatch.

**Cache-friendly, but no cache in v1.** `EntityProvider.discover()` returns full `SourceEntity` lists. A future cache layer (Spec Z) can wrap providers transparently — memoize by directory mtime, watch the filesystem, or rebuild on init — without changing the provider interface itself. v1 inherits today's "rescan every command" baseline; that pain is pre-existing.

## Interfaces and Data Shapes

### Shared types in `graph/source_types.py`

To eliminate the import cycle between `graph/sources.py` and the new `entity_providers/` package, the shared types move to a neutral module:

```python
# science-tool/src/science_tool/graph/source_types.py
"""Shared types consumed by both the legacy graph/sources.py and the new entity_providers package."""

from pydantic import BaseModel, Field

# (existing definitions, lifted from graph/sources.py without behavior change)
class SourceEntity(BaseModel):
    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    provider: str                       # NEW — required, explicit
    description: str = ""               # NEW — entity prose body
    # ... all existing fields unchanged ...


class SourceRelation(BaseModel):
    # ... existing definition lifted unchanged ...


class KnowledgeProfiles(BaseModel):
    # ... existing definition lifted unchanged ...


class EntityIdCollisionError(ValueError):
    """Raised when two providers (or a provider + a specialized parser) produce the same canonical_id."""

    def __init__(self, canonical_id: str, sources: list[tuple[str, str]]) -> None:
        self.canonical_id = canonical_id
        self.sources = sources  # list of (provider_name, source_path)
        msg = f"entity {canonical_id!r} produced by multiple sources:\n"
        for provider, path in sources:
            msg += f"  - {provider}: {path}\n"
        msg += "Resolve by removing one source, or migrate to a single backend."
        super().__init__(msg)


class EntityDatapackageInvalidError(ValueError):
    """Raised when a datapackage with science-pkg-entity-1.0 profile has invalid schema."""

    def __init__(self, datapackage_path: str, message: str) -> None:
        self.datapackage_path = datapackage_path
        super().__init__(f"{datapackage_path}: invalid entity-profile datapackage — {message}")
```

`graph/sources.py` re-exports these for back-compat with any current consumers (`from science_tool.graph.sources import SourceEntity` continues to work).

### `EntityDiscoveryContext` and `EntityProvider`

```python
# science-tool/src/science_tool/graph/entity_providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from science_model.ontologies.schema import OntologyCatalog
from science_tool.graph.source_types import SourceEntity


@dataclass(frozen=True)
class EntityDiscoveryContext:
    """Shared loading state passed to every EntityProvider.

    Carries everything the existing loaders depend on (local_profile, active_kinds,
    ontology_catalogs) so providers can compute profiles, validate kinds, and apply
    catalog-aware behavior without needing to be reconstructed per-project.
    """

    project_root: Path
    project_slug: str
    local_profile: str
    active_kinds: frozenset[str] | None = None
    ontology_catalogs: list[OntologyCatalog] | None = None


class EntityProvider(ABC):
    """Discovers entities from a particular storage convention.

    Each provider is self-contained: knows where to look, knows how to read what
    it finds, returns ready-to-use SourceEntity objects with provider field set.
    Stateless across calls (a future cache layer wraps providers).
    """

    name: str  # short human-readable identifier matching SourceEntity.provider

    @abstractmethod
    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        """Walk the filesystem under ctx.project_root and return all entities found."""
```

Three concrete implementations:
- `markdown.py` — `MarkdownProvider` (`name = "markdown"`)
- `datapackage_directory.py` — `DatapackageDirectoryProvider` (`name = "datapackage-directory"`)
- `aggregate.py` — `AggregateProvider` (`name = "aggregate"`)

Each is one focused file (target <200 lines).

### `EntityRecord` schema and shared `_normalize_record` helper

The format-driven providers extract raw records in three different shapes (markdown frontmatter dict, datapackage YAML dict, aggregate-list-entry dict). They funnel ALL records through one normalization helper so paper-ID canonicalization, alias derivation, profile defaulting, and kind validation stay consistent.

```python
# science-tool/src/science_tool/graph/entity_providers/record.py
from typing import Any
from pydantic import BaseModel, Field


class EntityRecord(BaseModel):
    """Normalized input record produced by a provider's extraction step.

    Shared across all format-driven providers so the downstream normalize step
    (paper-ID canonicalization, alias derivation, profile defaulting, kind
    validation) can be a single function with one input shape.
    """

    canonical_id: str
    kind: str
    title: str
    description: str = ""               # entity prose body, optional
    source_path: str                    # filesystem path (relative to project root) where this came from
    profile: str | None = None          # provider may leave None to let normalizer default
    domain: str | None = None
    related: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    status: str | None = None
    confidence: float | None = None
    # Extension hatch for provider-specific fields (e.g., reasoning metadata).
    extra: dict[str, Any] = Field(default_factory=dict)


def _normalize_record(
    record: EntityRecord,
    ctx: EntityDiscoveryContext,
    provider_name: str,
) -> SourceEntity:
    """Apply shared normalization rules and produce a SourceEntity.

    Single source of truth for:
    - Paper-ID canonicalization (kind == "paper" → canonical_paper_id(canonical_id))
    - Profile defaulting (uses ctx.local_profile + ctx.active_kinds + ctx.ontology_catalogs)
    - Alias derivation (_derive_aliases)
    - Reasoning-metadata wiring (when record.extra carries the relevant fields)
    - provider field set to provider_name (passed in by the caller)
    """
    # ... extracts existing logic from _load_markdown_entities + _load_structured_entities ...
```

### `EntityResolver` — coordinator

```python
# science-tool/src/science_tool/graph/entity_providers/resolver.py
from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.source_types import EntityIdCollisionError, SourceEntity


class EntityResolver:
    """Runs a list of providers and merges their outputs."""

    def __init__(self, providers: list[EntityProvider]) -> None:
        self._providers = providers

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        seen: dict[str, list[tuple[str, str]]] = {}
        all_entities: list[SourceEntity] = []
        for provider in self._providers:
            for entity in provider.discover(ctx):
                seen.setdefault(entity.canonical_id, []).append(
                    (provider.name, entity.source_path)
                )
                all_entities.append(entity)
        collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
        if collisions:
            cid, sources = next(iter(collisions.items()))
            raise EntityIdCollisionError(cid, sources)
        return all_entities
```

Resolver only catches collisions among its own providers. The **global collision check** lives in `load_project_sources` (next section) and covers BOTH resolver output and specialized-parser output.

### `default_providers()` factory

Module-level function in `resolver.py`:

```python
def default_providers() -> list[EntityProvider]:
    """The set of providers active in every project. No config required."""
    from .markdown import MarkdownProvider
    from .datapackage_directory import DatapackageDirectoryProvider
    from .aggregate import AggregateProvider
    return [
        MarkdownProvider(),
        DatapackageDirectoryProvider(),
        AggregateProvider(),
    ]
```

Function (not constant) supports dependency injection from tests without monkey-patching.

### Integration into `load_project_sources` — with global collision check

```python
# science-tool/src/science_tool/graph/sources.py
from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.resolver import EntityResolver, default_providers
from science_tool.graph.source_types import EntityIdCollisionError


def load_project_sources(project_root: Path) -> ProjectSources:
    # ... existing config/profile/catalog loading unchanged ...

    ctx = EntityDiscoveryContext(
        project_root=project_root,
        project_slug=project_root.name,
        local_profile=local_profile,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )

    entities: list[SourceEntity] = []

    # Format-driven providers via the resolver (catches intra-resolver collisions).
    resolver = EntityResolver(default_providers())
    entities.extend(resolver.discover(ctx))

    # Specialized parsers (UNCHANGED shape; each now sets provider explicitly).
    entities.extend(_load_task_entities(project_root, paths.tasks_dir, ...))
    model_entities, model_relations = _load_model_sources(project_root, ...)
    parameter_entities, parameter_relations = _load_parameter_sources(project_root, ...)
    entities.extend(model_entities)
    entities.extend(parameter_entities)

    # Final global collision check across resolver + specialized parsers.
    # Catches the case where (e.g.) a task and a markdown entity share canonical_id.
    seen: dict[str, list[tuple[str, str]]] = {}
    for e in entities:
        seen.setdefault(e.canonical_id, []).append((e.provider, e.source_path))
    collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
    if collisions:
        cid, sources = next(iter(collisions.items()))
        raise EntityIdCollisionError(cid, sources)

    # ... existing relations/bindings loading unchanged ...
```

### Data shapes (summary of additions)

The existing `SourceEntity` Pydantic model gains two required fields:
- `provider: str` (no default — every loader must set it explicitly)
- `description: str = ""` (default empty; populated by providers that have a prose source)

`EntityRecord` is new (shared input shape for the format-driven providers' normalizer).

`EntityDatapackageInvalidError` is new (raised by DatapackageDirectoryProvider on invalid entity datapackages).

No other entity-level data types are introduced.

### `EntityResolver` and `EntityIdCollisionError`

Same package, `resolver.py`:

```python
class EntityIdCollisionError(ValueError):
    """Raised when two providers produce the same canonical_id."""

    def __init__(self, canonical_id: str, sources: list[tuple[str, str]]) -> None:
        self.canonical_id = canonical_id
        self.sources = sources  # list of (provider_name, source_path)
        msg = f"entity {canonical_id!r} produced by multiple providers:\n"
        for provider, path in sources:
            msg += f"  - {provider}: {path}\n"
        msg += "Resolve by removing one source, or migrate to a single backend."
        super().__init__(msg)


class EntityResolver:
    """Runs a list of providers and merges their outputs."""

    def __init__(self, providers: list[EntityProvider]) -> None:
        self._providers = providers

    def discover(self, project_root: Path) -> list[SourceEntity]:
        seen: dict[str, list[tuple[str, str]]] = {}
        all_entities: list[SourceEntity] = []
        for provider in self._providers:
            for entity in provider.discover(project_root):
                seen.setdefault(entity.canonical_id, []).append(
                    (provider.name, entity.source_path)
                )
                all_entities.append(entity)
        collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
        if collisions:
            cid, sources = next(iter(collisions.items()))
            raise EntityIdCollisionError(cid, sources)
        return all_entities
```

### `default_providers()` factory

Module-level function in `resolver.py`:

```python
def default_providers() -> list[EntityProvider]:
    """The set of providers active in every project. No config required."""
    from .markdown import MarkdownProvider
    from .datapackage_directory import DatapackageDirectoryProvider
    from .aggregate import AggregateProvider
    return [
        MarkdownProvider(),
        DatapackageDirectoryProvider(),
        AggregateProvider(),
    ]
```

Keeping it as a function (not a constant) lets tests inject custom provider lists via dependency injection without monkey-patching.

### Integration into `load_project_sources`

In `science-tool/src/science_tool/graph/sources.py`, the existing call sites for `_load_markdown_entities` and `_load_structured_entities` get replaced with one resolver call:

```python
# BEFORE:
entities.extend(_load_markdown_entities(project_root, [paths.doc_dir, paths.specs_dir, project_root / "research" / "packages"], ...))
entities.extend(_load_structured_entities(project_root, ...))

# AFTER:
resolver = EntityResolver(default_providers())
entities.extend(resolver.discover(project_root))
```

Specialized parsers remain direct callsites — same as today:

```python
entities.extend(_load_task_entities(project_root, paths.tasks_dir, ...))
model_entities, model_relations = _load_model_sources(project_root, ...)
parameter_entities, parameter_relations = _load_parameter_sources(project_root, ...)
entities.extend(model_entities)
entities.extend(parameter_entities)
```

### `SourceEntity.provider` and `SourceEntity.description` fields

Both fields are added to the `SourceEntity` Pydantic model in `graph/source_types.py`:

```python
class SourceEntity(BaseModel):
    # ... existing fields ...
    provider: str                       # NEW — required, no default
    description: str = ""               # NEW — entity prose body
```

The `provider` field is **required** with **no default** — every loader (format-driven providers AND specialized parsers) must set it explicitly. Six legal values in v1: `markdown` / `aggregate` / `datapackage-directory` / `task` / `model` / `parameter`. This avoids the wrong-by-default trap (defaulting non-markdown entities to `"markdown"` is a lie).

The `description` field defaults to empty and is populated per-provider from each provider's natural prose source. See the per-provider details in the next section.

## Provider Implementations

All three providers follow the same shape: extract raw records from disk → call shared `_normalize_record` to produce `SourceEntity`. The provider's job is extraction; normalization is shared.

### `MarkdownProvider`

Refactor of existing `_load_markdown_entities`. Behavior preserved via the shared normalizer.

```python
class MarkdownProvider(EntityProvider):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["doc", "specs", "research/packages"]

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = ctx.project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                entity = parse_entity_file(path, project_slug=ctx.project_slug)
                if entity is None:
                    continue
                record = self._extract_record(path, entity, ctx)
                source_entity = _normalize_record(record, ctx, provider_name=self.name)
                entities.append(source_entity)
        return entities

    def _extract_record(self, path: Path, entity, ctx: EntityDiscoveryContext) -> EntityRecord:
        # Build EntityRecord from the parsed Entity.
        # description = entity.content (full markdown body after frontmatter).
        # extra carries reasoning-metadata, aspects, etc., for the normalizer to lift.
        rel_path = str(path.relative_to(ctx.project_root))
        return EntityRecord(
            canonical_id=entity.canonical_id,
            kind=entity.type.value,
            title=entity.title,
            description=entity.content,
            source_path=rel_path,
            domain=entity.domain,
            related=entity.related,
            source_refs=entity.source_refs,
            ontology_terms=entity.ontology_terms,
            aliases=entity.aliases,
            same_as=entity.same_as,
            status=entity.status,
            confidence=entity.confidence,
            extra={
                # Reasoning metadata + per-entity-type fields — picked up by normalizer.
                "claim_layer": entity.claim_layer,
                # ... etc.
            },
        )
```

The `_normalize_record` helper sets `provider="markdown"`, applies paper-ID canonicalization (which kicks in only when `kind == "paper"`), wires aliases via `_derive_aliases`, defaults the profile via `_default_profile_for_kind`. Behavior matches existing `_load_markdown_entities` line-for-line.

### `DatapackageDirectoryProvider`

NEW. Scans for entity-flavored datapackages. **Hard-errors on malformed entity-profile datapackages.**

```python
class DatapackageDirectoryProvider(EntityProvider):
    name = "datapackage-directory"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["data", "results"]

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = ctx.project_root / rel
            if not root.is_dir():
                continue
            for dp_path in sorted(root.rglob("datapackage.yaml")):
                rel_path = str(dp_path.relative_to(ctx.project_root))
                # Read with hard-error catch only for entity-profile cases.
                try:
                    with dp_path.open() as f:
                        dp = yaml.safe_load(f) or {}
                except yaml.YAMLError as exc:
                    # Malformed YAML — but we don't yet know if it's an entity datapackage.
                    # Conservative: only error when we can confirm the entity profile.
                    # Without parseable YAML, skip silently (could be a non-entity datapackage).
                    continue
                profiles = dp.get("profiles") or []
                if "science-pkg-entity-1.0" not in profiles:
                    continue  # non-entity datapackage; ignore quietly
                # From here, this IS an entity datapackage. Any failure raises.
                self._validate_required_fields(rel_path, dp)
                record = self._extract_record(rel_path, dp)
                entities.append(_normalize_record(record, ctx, provider_name=self.name))
        return entities

    def _validate_required_fields(self, source_path: str, dp: dict) -> None:
        """Hard-error when a science-pkg-entity-1.0 datapackage is missing required fields."""
        for field in ("id", "type", "title"):
            if not dp.get(field):
                raise EntityDatapackageInvalidError(
                    source_path,
                    f"missing required entity field {field!r} (science-pkg-entity-1.0 profile present)",
                )

    def _extract_record(self, source_path: str, dp: dict) -> EntityRecord:
        return EntityRecord(
            canonical_id=str(dp["id"]),
            kind=str(dp["type"]),
            title=str(dp["title"]),
            description=str(dp.get("description", "")),  # Frictionless top-level description
            source_path=source_path,
            ontology_terms=list(dp.get("ontology_terms") or []),
            related=list(dp.get("related") or []),
            source_refs=list(dp.get("source_refs") or []),
            status=dp.get("status"),
            extra={
                # Pass through dataset-specific fields the normalizer / consumers may use.
                "origin": dp.get("origin"),
                "tier": dp.get("tier"),
                "access": dp.get("access"),
                "derivation": dp.get("derivation"),
                "datapackage_path": source_path,
            },
        )
```

**Failure-mode contract** (per review fix #5):
- Non-entity datapackage (no `science-pkg-entity-1.0` in profiles, or unparseable YAML before profile check): ignore quietly.
- Entity-profile datapackage with valid YAML but missing required fields (`id`/`type`/`title`): raise `EntityDatapackageInvalidError` with file path and the missing field name.

The Frictionless top-level `description:` field is the standard prose home; reading it for `EntityRecord.description` is a Frictionless-aligned default.

**Migration enabler** (Path 4 below): when a user wants to promote a markdown dataset entity to live as the datapackage, they:
1. Move the markdown frontmatter fields into the datapackage YAML's top-level keys (id, type, title, description, status, origin, tier, ontology_terms, access:, etc.).
2. Add `"science-pkg-entity-1.0"` to the datapackage's `profiles:` list.
3. Delete the `doc/datasets/<slug>.md` file.

The Frictionless `description:` field naturally absorbs the markdown body. DatapackageDirectoryProvider now finds it; MarkdownProvider doesn't. No collision.

### `AggregateProvider`

Refactor of existing `_load_structured_entities`, generalized to two file conventions. Both routes funnel through `EntityRecord` + `_normalize_record`.

```python
class AggregateProvider(EntityProvider):
    name = "aggregate"

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        # Convention 1: multi-type aggregate (existing entities.yaml)
        entities.extend(self._load_multi_type_aggregate(ctx))
        # Convention 2: single-type aggregate (doc/<plural>/<plural>.{json,yaml})
        entities.extend(self._load_single_type_aggregates(ctx))
        return entities

    def _load_multi_type_aggregate(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities_path = local_profile_sources_dir(ctx.project_root, local_profile=ctx.local_profile) / "entities.yaml"
        if not entities_path.is_file():
            return []
        data = yaml.safe_load(entities_path.read_text(encoding="utf-8")) or {}
        items = data.get("entities") or []
        if not isinstance(items, list):
            return []
        rel_path = str(entities_path.relative_to(ctx.project_root))
        results: list[SourceEntity] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            record = self._record_from_dict(raw, kind=raw.get("kind"), source_path=rel_path)
            if record is None:
                continue
            results.append(_normalize_record(record, ctx, provider_name=self.name))
        return results

    def _load_single_type_aggregates(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        from science_model.frontmatter import _DIR_TO_TYPE
        results: list[SourceEntity] = []
        for plural, singular in _DIR_TO_TYPE.items():
            for ext in ("json", "yaml"):
                f = ctx.project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                rel_path = str(f.relative_to(ctx.project_root))
                items = self._load_list(f)  # JSON list or YAML list
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    # Type defaults to <singular> from filename (e.g., topics.json → "topic").
                    record = self._record_from_dict(raw, kind=singular, source_path=rel_path)
                    if record is None:
                        continue
                    results.append(_normalize_record(record, ctx, provider_name=self.name))
        return results

    def _record_from_dict(self, raw: dict, *, kind: str | None, source_path: str) -> EntityRecord | None:
        """Build EntityRecord from an aggregate-entry dict. Validates via Pydantic."""
        try:
            return EntityRecord(
                canonical_id=str(raw.get("canonical_id") or raw.get("id") or ""),
                kind=str(raw.get("kind") or kind or ""),
                title=str(raw.get("title") or ""),
                description=str(raw.get("description") or ""),
                source_path=source_path,
                profile=raw.get("profile"),
                domain=raw.get("domain"),
                status=raw.get("status"),
                related=list(raw.get("related") or []),
                source_refs=list(raw.get("source_refs") or []),
                ontology_terms=list(raw.get("ontology_terms") or []),
                aliases=list(raw.get("aliases") or []),
                same_as=list(raw.get("same_as") or []),
                extra={k: v for k, v in raw.items() if k not in EntityRecord.model_fields},
            )
        except ValidationError:
            return None  # Skip malformed entries; surfaced separately via health check
```

**Single-type aggregate format** (mm30's `doc/topics/topics.json`):

```json
[
  {
    "id": "topic:rare-condition-X",
    "title": "Rare Condition X",
    "description": "Optional markdown prose describing this topic.",
    "ontology_terms": ["MONDO:..."],
    "status": "active"
  },
  {
    "id": "topic:rare-condition-Y",
    "title": "Rare Condition Y"
  }
]
```

YAML equivalent supported. Each entry is a dict; required: `id`, `title`. Optional: anything `EntityRecord` accepts (including the new `description:` field). Type defaults to the singular form of the parent directory name; can be overridden by `kind:` in the entry.

**Filename convention is intentional:** `doc/<plural>/<plural>.json` — the file lives *inside* the canonical entity directory, sharing namespace with any `<plural>/<slug>.md` markdown entries. A project can mix per-entity markdown files AND an aggregate file in the same directory; both providers find their entries; ID collisions across them are still errors.

### Specialized parsers — explicit provider strings

The unchanged-in-shape specialized parsers each set `SourceEntity.provider` explicitly. Snippets (only the new line shown):

```python
# parse_tasks-using path in _load_task_entities:
SourceEntity(..., provider="task", description=task.description, ...)

# _load_model_sources:
SourceEntity(..., provider="model", description="", ...)

# _load_parameter_sources:
SourceEntity(..., provider="parameter", description="", ...)
```

This is the cleanup from review fix #3 — every loader is responsible for a correct `provider` value; no defaulting that could silently mislabel non-markdown entities.

For tasks specifically: `description` now also receives `task.description` (currently only `content_preview` does). This makes task prose available to the same downstream consumers that may use `description` on other entity types.

The profile filter is the only thing that distinguishes "this is an entity" from "this is just a Frictionless data package describing some files." Without it, every staged dataset's runtime datapackage would become a phantom entity.

**Migration enabler:** when a user wants to promote a markdown dataset entity to live as the datapackage, they:
1. Move `doc/datasets/<slug>.md`'s frontmatter fields into the existing `data/<slug>/datapackage.yaml` under top-level keys.
2. Add `"science-pkg-entity-1.0"` to the datapackage's `profiles:` list.
3. Delete the `doc/datasets/<slug>.md` file.

DatapackageDirectoryProvider now finds it; MarkdownProvider doesn't. No collision. A future `science-tool dataset promote <slug>` command can automate this (follow-on, not v1 scope).

### `AggregateProvider`

Refactor of existing `_load_structured_entities`, generalized to two file conventions:

```python
class AggregateProvider(EntityProvider):
    name = "aggregate"

    def discover(self, project_root: Path) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        # Convention 1: multi-type aggregate (existing entities.yaml)
        entities.extend(self._load_multi_type_aggregate(project_root))
        # Convention 2: single-type aggregate (doc/<plural>/<plural>.{json,yaml})
        entities.extend(self._load_single_type_aggregates(project_root))
        return entities

    def _load_multi_type_aggregate(self, project_root: Path) -> list[SourceEntity]:
        # Carries forward the existing _load_structured_entities logic.
        # Reads entities.yaml from local_profile_sources_dir.
        ...

    def _load_single_type_aggregates(self, project_root: Path) -> list[SourceEntity]:
        # Walks doc/<plural>/<plural>.{json,yaml} where <plural> matches a known
        # entity type's plural directory name (uses _DIR_TO_TYPE from
        # science_model.frontmatter, inverted: "topics" → "topic", etc.)
        from science_model.frontmatter import _DIR_TO_TYPE
        plural_to_type = {plural: singular for plural, singular in _DIR_TO_TYPE.items()}
        for plural, singular in plural_to_type.items():
            for ext in ("json", "yaml"):
                f = project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                # Each entry: a dict with at minimum {id, title}.
                # Type defaulted to <singular>.
                ...
```

**Single-type aggregate format** (mm30's `doc/topics/topics.json`):

```json
[
  {
    "id": "topic:rare-condition-X",
    "title": "Rare Condition X",
    "ontology_terms": ["MONDO:..."],
    "status": "active"
  },
  {
    "id": "topic:rare-condition-Y",
    "title": "Rare Condition Y"
  }
]
```

YAML equivalent supported. Each entry is a thin dict; required: `id`, `title`. Optional: anything `SourceEntity` accepts. Type defaults to the singular form of the parent directory name.

**Filename convention is intentional:** `doc/<plural>/<plural>.json` — the file lives *inside* the canonical entity directory, sharing namespace with any `<plural>/<slug>.md` markdown entries. A project can mix per-entity markdown files AND an aggregate file in the same directory; both providers find their entries; ID collisions across them are still errors.

## Migration and Integration

Three migration paths, each independently opt-in and incremental.

### Path 1: Existing markdown loaders → `MarkdownProvider`

Behavior-preserving refactor. The existing `_load_markdown_entities` function in `graph/sources.py` becomes the body of `MarkdownProvider.discover()`. Same scan roots, same per-file logic, same `SourceEntity` output (with `provider="markdown"` added).

**Migration:** internal-only. No project changes. All existing markdown entities continue to load identically.

**Verification:** the snapshot regression test (described below) MUST stay green across this commit.

### Path 2: Existing `entities.yaml` → `AggregateProvider` (multi-type aggregate)

Behavior-preserving refactor. The existing `_load_structured_entities` becomes `AggregateProvider._load_multi_type_aggregate()`. Existing `entities.yaml` files in `local_profile_sources_dir(project_root)` continue to load identically (with `provider="aggregate"`).

**Migration:** internal-only. No project changes.

### Path 3: New entity files via `AggregateProvider` (single-type aggregate) — mm30's case

The new capability. Projects with many of one entity type can put them in a single file:

**Before:** mm30 has ~200 thin markdown files at `doc/topics/<slug>.md`, each with minimal frontmatter.

**After (opt-in):**
1. Create `doc/topics/topics.json` (or `topics.yaml`) listing the entries.
2. Delete the corresponding `doc/topics/<slug>.md` files for entities now in the aggregate.
3. Run `science-tool create-graph`. AggregateProvider finds all 200 in the JSON; MarkdownProvider finds zero (the .md files are gone). No collision.

Mixed mode is fine: some topics can stay as markdown (e.g., topics with rich prose narrative), others move to the aggregate (thin metadata only). The two providers find both; no collision because IDs differ.

**No migration command in v1.** Manual move-and-delete is straightforward and one-time; a `science-tool entities aggregate <type>` helper is documented as follow-on.

### Path 4: Markdown dataset entities → `DatapackageDirectoryProvider` — promotes datasets

This is the dataset-entity-lifecycle spec's "datapackage IS the entity" promotion that was deferred to Spec Y.

**Before:** dataset entity at `doc/datasets/<slug>.md` (markdown frontmatter) plus runtime `data/<slug>/datapackage.yaml` (resource manifest). Two surfaces, drift-warned by `dataset reconcile`.

**After (opt-in):**
1. Move the entity-surface fields from the markdown frontmatter into the runtime datapackage's top-level YAML (id, type, title, status, origin, tier, ontology_terms, access:, etc.).
2. Add `"science-pkg-entity-1.0"` to the datapackage's `profiles:` list (alongside `"science-pkg-runtime-1.0"`).
3. Delete `doc/datasets/<slug>.md`.

DatapackageDirectoryProvider picks it up; MarkdownProvider stops seeing it; no sidecar.

**Drift impact:** `dataset reconcile` becomes a no-op for promoted datasets — there's only one surface now. Reconcile keeps working for datasets still in markdown.

**Health impact:** the existing `dataset_cached_field_drift` anomaly skips entities whose `provider == "datapackage-directory"` (no two surfaces to drift between). One small change to the existing health check from dataset-entity-lifecycle Phase 6.

**No migration command in v1.** Manual is reasonable for the small number of datasets per project. A `science-tool dataset promote <slug>` follow-on is documented but not built.

### Path 5: Specialized parsers — minimal touch only

`parse_tasks`, `_load_model_sources`, `_load_parameter_sources` stay as direct callsites in `load_project_sources`. No wrapper, no `EntityProvider` inheritance. They're not providers; they're end-to-end specialized.

The minimal touch each receives:
- Set `SourceEntity.provider` explicitly to one of `task` / `model` / `parameter` (per review fix #3).
- For `parse_tasks`: also populate `SourceEntity.description` from `task.description` so task prose flows through the same field as other entity types' prose.
- Models/parameters: leave `description` empty (no current source); when a future YAML format adds a `description:` per record, populate then.

These are the only changes to the specialized-parser code paths.

### Implementation sequencing

The implementation plan will land in this order:

1. Lift `SourceEntity`, `SourceRelation`, `KnowledgeProfiles` into new `graph/source_types.py` (re-exported from `graph/sources.py` for back-compat). Add `EntityIdCollisionError` and `EntityDatapackageInvalidError` to the same module. No behavior change.
2. Add the snapshot regression test fixture + checked-in snapshot using a **projected dict that excludes the new `provider` and `description` fields**. Canary for subsequent commits.
3. Add the `entity_providers/` package skeleton: `EntityDiscoveryContext`, `EntityProvider` ABC, `EntityRecord`, `_normalize_record` helper, `EntityResolver`, `default_providers()`. No integration yet.
4. Refactor `MarkdownProvider` (Path 1) — invisible behavior under the projection; snapshot stays green.
5. Refactor `AggregateProvider` for multi-type (Path 2) — invisible behavior; snapshot stays green.
6. Switch `load_project_sources` to use the resolver + add the global collision check across resolver + specialized parsers.
7. Add `provider: str` field to `SourceEntity` (required, no default) AND update every loader (markdown, aggregate, tasks, models, parameters) to set it explicitly. Snapshot projection still excludes the field; a new test asserts each loader produces the correct `provider` value.
8. Add `description: str = ""` field to `SourceEntity`. Wire MarkdownProvider (from `entity.content`), AggregateProvider (from `EntityRecord.description`), task parser (from `task.description`). Snapshot projection still excludes the field; a new test asserts roundtrip per loader.
9. Add `AggregateProvider`'s single-type convention (Path 3) — new capability, mm30 can opt in.
10. Add `DatapackageDirectoryProvider` (Path 4) — new capability, dataset promotion possible. Includes hard-error contract via `EntityDatapackageInvalidError`.
11. Update `dataset_cached_field_drift` health check to skip `provider == "datapackage-directory"` entities.
12. Tests + docs.

Each step ships as one or two commits; the codebase stays green at every commit; existing projects see no behavior change until they explicitly adopt new conventions.

### Optional opt-out lever (not in v1)

For the rare case where a provider misbehaves on a project (false positives, unwanted scanning), a `science.yaml` opt-out:

```yaml
entity_providers:
  disabled: [datapackage-directory]
```

is a small add. Documented in Follow-on Work; not built v1 because no concrete need exists.

## Testing

### Per-provider unit tests

Each provider's behavior tested in isolation with a `tmp_path` fixture seeding a small synthetic project.

`science-tool/tests/test_entity_providers/test_markdown_provider.py`:
- Discovers entities under each scan root (doc/, specs/, research/packages/).
- Skips files without YAML frontmatter.
- Falls back to filename-based type inference when frontmatter omits `type:`.
- Returns empty list when no markdown files exist.
- Custom `scan_roots=` constructor param honored.

`science-tool/tests/test_entity_providers/test_datapackage_directory_provider.py`:
- Discovers `datapackage.yaml` files under `data/` and `results/`.
- **Filters out** datapackages whose `profiles:` doesn't include `"science-pkg-entity-1.0"` (the critical false-positive guard).
- Returns the entity with correct `canonical_id` from the datapackage's `id:` field.
- Handles missing/malformed YAML gracefully (skip, don't crash).
- Custom `scan_roots=` honored.

`science-tool/tests/test_entity_providers/test_aggregate_provider.py`:
- Multi-type aggregate: existing `entities.yaml` test fixtures continue to work (regression).
- Single-type aggregate: `doc/topics/topics.json` with multiple entries produces multiple `SourceEntity` objects with `kind: "topic"`.
- Single-type aggregate: `.yaml` produces same result as `.json`.
- Type inference: filename-based (singular form of parent directory's plural).
- Multi-type AND single-type files coexisting in the same project both get loaded.

### Resolver tests

`science-tool/tests/test_entity_providers/test_resolver.py`:
- Empty provider list → empty entity list.
- Single provider → its output passes through unchanged.
- Multiple providers → outputs concatenated.
- ID collision across two providers → raises `EntityIdCollisionError` with both source paths in the message.
- ID collision within a single provider's output → raises (provider returned dups; same error type).
- `default_providers()` returns the three v1 implementations in stable order.

### Behavior-preservation regression tests

The most important tests in this spec — they prove the refactor doesn't change observable behavior for any existing project.

`science-tool/tests/test_load_project_sources_regression.py`:
- Fixture: a "kitchen-sink" mini-project with one of each existing entity type (one markdown dataset, one markdown hypothesis, one entities.yaml entry, one task, one model, etc.) under `tests/fixtures/spec_y_kitchen_sink/`.
- Test: call `load_project_sources(fixture_root)` → project the result through `_project_for_snapshot()` (a helper that drops the new `provider` and `description` fields) → assert it equals a checked-in snapshot.
- **Why a projection** (per review fix #6): the new `provider` and `description` fields are added in steps 7-8 of the implementation sequencing. Before they exist, the snapshot has the projected shape (no new fields). After they exist, the snapshot still has the projected shape — so the regression test stays byte-identical across every commit. Separate per-step tests assert the new fields appear with correct values when their commit lands.
- The fixture and snapshot are committed in step 2 of the implementation plan (before the package skeleton lands).
- After EACH commit in steps 3-12, this test must continue to pass with the same snapshot.

This is the canary that catches "the refactor changed something subtly." The projection lets the snapshot survive intentional additions cleanly.

```python
def _project_for_snapshot(entities: list[SourceEntity]) -> list[dict]:
    """Drop new fields the spec adds incrementally; the snapshot stays stable."""
    excluded = {"provider", "description"}
    return [
        {k: v for k, v in e.model_dump().items() if k not in excluded}
        for e in entities
    ]
```

### New-field assertion tests

Separate from the regression snapshot, each new field gets dedicated assertions when its commit lands:

`science-tool/tests/test_entity_providers/test_provider_field.py` (introduced in step 7):
- After loading the kitchen-sink fixture, every `SourceEntity` has `provider` set to one of the six legal values.
- markdown entities → `"markdown"`; entities.yaml entries → `"aggregate"`; tasks → `"task"`; models → `"model"`; parameters → `"parameter"`.
- (Datapackage-directory entities don't appear in the kitchen-sink yet; covered in step-10 integration test.)

`science-tool/tests/test_entity_providers/test_description_field.py` (introduced in step 8):
- Markdown entity with body → `description` matches the body content.
- entities.yaml entry without `description:` → `description == ""`.
- entities.yaml entry with `description:` → `description` matches the given prose.
- Single-type aggregate entry with `description:` → roundtrip works.
- Datapackage-directory entity with top-level `description:` → roundtrip works.
- Task with prose after the bullets → `description` matches `task.description`.

### Tests for the global collision check

`science-tool/tests/test_load_project_sources_global_collision.py`:
- Markdown entity `dataset:x` + entities.yaml entry `dataset:x` → resolver-level `EntityIdCollisionError`.
- Markdown entity `task:t01` + a task with `id: t01` (canonical_id `task:t01`) → global-level `EntityIdCollisionError` raised by the new check in `load_project_sources` (after both resolver and specialized parsers have run).
- No collision case → no error.

### Tests for hard-error datapackage failures

`science-tool/tests/test_entity_providers/test_datapackage_directory_hard_errors.py`:
- Datapackage with `science-pkg-entity-1.0` profile and missing `id:` → raises `EntityDatapackageInvalidError` with file path and `'id'` in the message.
- Same for missing `type:` / `title:`.
- Datapackage WITHOUT the entity profile and missing those fields → no error (silently ignored as a non-entity datapackage).
- Malformed YAML on a non-entity datapackage → silently ignored (we can't determine if it was an entity datapackage; conservative behavior).

### Integration tests for new capabilities

`science-tool/tests/test_aggregate_single_type_e2e.py`:
- Project has a `doc/topics/topics.json` with 5 entries.
- `load_project_sources(project_root)` returns 5 topic entities.
- `science-tool create-graph` produces a graph with those 5 nodes.

`science-tool/tests/test_datapackage_directory_e2e.py`:
- Project has a dataset entity stored as `data/myset/datapackage.yaml` with `profiles: [science-pkg-runtime-1.0, science-pkg-entity-1.0]`.
- No `doc/datasets/myset.md` exists.
- `load_project_sources` returns the dataset entity with `canonical_id == "dataset:myset"`.
- The existing `dataset_cached_field_drift` health check does NOT fire for this entity.
- The existing dataset gate-check tests (from dataset-entity-lifecycle Phase 6/7) still pass — derived dataset behavior unchanged.

### Migration scenario tests

`science-tool/tests/test_provider_migration.py`:
- Mid-migration mixed mode: 3 datasets in markdown, 2 datasets as datapackage-directory. Both providers find their respective entities. No collision. Resolver returns all 5.
- Bad-migration collision: dataset entity exists in BOTH `doc/datasets/x.md` AND `data/x/datapackage.yaml` (with the entity profile). Resolver raises `EntityIdCollisionError`, message names both source paths.
- Recovery: delete the markdown file, rerun, succeeds.

### Test fixtures

`science-tool/tests/fixtures/spec_y_kitchen_sink/` — the regression baseline project (one of each existing entity type, snapshot of expected output).

`science-tool/tests/fixtures/aggregate_single_type/` — minimal project with a `doc/topics/topics.json` for the single-type aggregate tests.

`science-tool/tests/fixtures/datapackage_entity/` — minimal project with a promoted dataset entity at `data/myset/datapackage.yaml`.

### Tests that don't change

The dataset-entity-lifecycle test suites (40 in `test_health.py`, 11 in `test_dataset_register_run.py`, etc.) keep working unchanged. Spec Y's refactor is invisible to them.

The science-model test suites (188 tests) are completely unaffected — Spec Y is a science-tool change.

## Resolved Decisions

- **Format-driven providers only.** Specialized parsers (tasks, models, parameters) stay outside the resolver. They don't fit a generic interface.
- **No per-entity-type configuration.** Providers don't care about types; resolver just merges all outputs.
- **No per-project configuration in v1.** All providers always run. Opt-out is a future addition.
- **Auto-discovery is filesystem-convention-driven.** Each provider knows its scan roots and recognition heuristics. Datapackages need an explicit profile signal to be recognized as entities.
- **`EntityProvider` single-layer interface (`α`).** `discover() -> list[SourceEntity]` returns full entities. The two-layer split (extraction → construction) is rejected for v1 because the three providers have genuinely different input formats; a shared builder would need branching anyway.
- **Cache-friendly but uncached.** v1 inherits the existing "rescan every command" baseline. Spec Z addresses caching, indexing, and store shape.
- **`EntityResolver` is a thin coordinator** (~50 lines). No magic, no per-type dispatch, no plugin registration. Constructor takes a list of providers; `discover()` calls each and merges.
- **ID collisions are hard errors** (`EntityIdCollisionError`). Raised on first collision found. Message includes both source paths and a recovery hint. Never silently pick a winner.
- **`default_providers()` is a function, not a constant** — supports test injection without monkey-patching.
- **AggregateProvider's single-type convention is `doc/<plural>/<plural>.{json,yaml}`** — file inside the per-type directory, sharing namespace with markdown entries. Type inference reuses `_DIR_TO_TYPE` from `science_model/frontmatter.py`.
- **Provider scan roots are constructor parameters** with sensible defaults — supports test injection and future per-project knobs without redesign.
- **Behavior preservation is the refactor's success criterion.** A snapshot regression test on a kitchen-sink fixture must stay green across every commit in the implementation plan.
- **No migration commands in v1.** `dataset promote`, `entities aggregate` are documented as follow-on work; manual migration is the documented v1 path.
- **No symlinks, no fallback ordering.** Each entity has exactly one source path. If two providers find the same ID, that's an error to fix, not a runtime decision to absorb.
- **`EntityDiscoveryContext` carries shared loading state.** Providers receive `project_root`, `project_slug`, `local_profile`, `active_kinds`, `ontology_catalogs` via this dataclass. Avoids globals, avoids per-provider re-derivation, makes test injection clean.
- **Shared types live in `graph/source_types.py`** (lifted from `graph/sources.py`). `entity_providers/` and `sources.py` both import from `source_types`; no import cycle. `sources.py` re-exports for back-compat.
- **Global collision check in `load_project_sources`.** Resolver catches collisions among its own providers (with provider names in error messages — best UX). A second pass in `load_project_sources` catches collisions across ALL entities (resolver output + specialized parsers). Same `EntityIdCollisionError` exception.
- **`provider` field is required and explicit on every loader.** No default value, no implicit `"markdown"` for non-markdown entities. Six v1 values: `markdown` / `aggregate` / `datapackage-directory` / `task` / `model` / `parameter`. Format-driven providers are named after the file format they handle; specialized parsers are named after the entity type they produce (since each handles exactly one).
- **`EntityRecord` schema + shared `_normalize_record` helper** for format-driven providers. Each provider extracts records in its native format; all records pass through the same normalizer (paper-ID canonicalization, alias derivation, profile defaulting, kind validation). Single source of truth for normalization.
- **Hard-error contract for entity-profile datapackages.** A datapackage with `science-pkg-entity-1.0` in its `profiles:` MUST have valid YAML and required entity fields (`id`, `type`, `title`). Missing fields → `EntityDatapackageInvalidError` with file path and field name. Non-entity datapackages remain silently ignored.
- **`SourceEntity.description` field** mirrors the prose-body capability that `Entity.content` already provides. Each provider sources prose from its native location: markdown body (MarkdownProvider), Frictionless top-level `description:` (DatapackageDirectoryProvider), per-entry `description:` (AggregateProvider), `task.description` (parse_tasks). Models/parameters leave it empty for now; future YAML format additions can populate it without breaking changes.
- **Snapshot regression test uses a projection.** The snapshot drops `provider` and `description` (the new fields rolled out in steps 7-8 of the implementation plan), so the regression assertion stays byte-identical across every commit. New-field assertions live in separate tests that land alongside the field additions.

### Resolved open questions (from the design review)

- **"Should entities.yaml and single-type aggregates share one normalized source-record schema?"** Yes — both feed `EntityRecord` and pass through `_normalize_record`. The aggregate input format is a SCHEMA (`EntityRecord` Pydantic model), not "anything SourceEntity accepts."
- **"Is `provider` storage backend or parser origin?"** It's the parser/provider that produced the entity — covers both format-driven providers (`markdown` / `aggregate` / `datapackage-directory`) and specialized parsers (`task` / `model` / `parameter`). Naming logic: format-driven providers are named after the format they handle; specialized parsers are named after the entity type they produce.

## Follow-on Work

- **`science-tool dataset promote <slug>` CLI.** Automates the markdown-dataset-to-datapackage-directory promotion: reads the markdown entity, writes its fields into the existing runtime datapackage, adds the entity profile, deletes the markdown sidecar. Idempotent.
- **`science-tool entities aggregate <type>` CLI.** Collects markdown entities of the named type into a single-type aggregate file (`doc/<plural>/<plural>.json`), then deletes the source markdown files. Useful for projects that accumulate many thin entities of one type and decide to consolidate.
- **`science.yaml` provider opt-out.** Per-project disabling of providers. Trigger: a project where a provider produces false positives (e.g., a `data/` tree full of non-entity datapackages that get picked up by the profile check). Defer until observed.
- **Per-project provider configuration knobs.** Beyond opt-out: custom scan roots, per-provider parameters. Defer until needed.
- **Plugin registration.** Entry-points-based provider discovery so projects can ship project-specific `EntityProvider` subclasses without modifying framework code. Defer until a project actually needs a custom provider.
- **Cross-project shared providers / federated entity discovery.** A provider that surfaces entities from a sibling project's filesystem. Non-trivial; out of scope for v1 and Spec Z.
- **Spec Z — caching, indexing, in-memory store, edge representation.** The stub handoff note below captures the design space.

## Spec Z preview (handoff)

When Spec Y ships, the next architectural concern is performance and structure of the in-memory entity graph. Spec Z addresses:

- **Caching.** When to (re)scan: app init, daily, on-update, fs-watcher-driven, mtime-based invalidation. The `EntityProvider` interface is intentionally cache-friendly — a future memoizing wrapper can sit between providers and the resolver without changing provider code.
- **Index shape.** In-memory representation: KV `entity_id → SourceEntity` for fast lookup; separate edge representation. Loaded once per `science-tool` invocation today; could be persisted between invocations.
- **Graph store.** The codebase already uses `rdflib` for materialized graphs in `science-tool/src/science_tool/graph/`. Spec Z consolidates the in-memory cache + the RDF graph: which lives where, who owns updates, how they synchronize.
- **Lazy loading.** The cache holds metadata; full content (e.g., a dataset's per-resource manifest) fetched on-demand for large entities.
- **Cache-bypass flag.** A `science-tool` command-line flag (`--rescan` or similar) for explicit cache invalidation.

This handoff intentionally leaves the design space open. Brainstorm Spec Z with real performance data once Spec Y ships and the new providers are in active use.

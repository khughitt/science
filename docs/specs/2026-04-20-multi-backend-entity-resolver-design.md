# Multi-Backend Entity Resolver

**Date:** 2026-04-20
**Status:** Draft (rev 1)
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

- New module `science-tool/src/science_tool/graph/entity_providers/` containing:
  - `EntityProvider` abstract base class (`__init__.py` or `base.py`)
  - `MarkdownProvider` (refactor of `_load_markdown_entities`)
  - `DatapackageDirectoryProvider` (NEW — promotes datasets to live as `data/<slug>/datapackage.yaml`)
  - `AggregateProvider` (refactor of `_load_structured_entities`, generalized to support single-type aggregate files like `doc/topics/topics.json`)
  - `EntityResolver` coordinator + `EntityIdCollisionError` exception (`resolver.py`)
  - `default_providers()` factory returning the v1 provider list
- `load_project_sources` in `graph/sources.py` switches from direct loader calls to `EntityResolver(default_providers()).discover(project_root)` for the format-driven path.
- Specialized parsers (`parse_tasks`, `_load_model_sources`, `_load_parameter_sources`) keep their existing direct callsites in `load_project_sources` — UNCHANGED.
- `SourceEntity` gains a `provider: str` field (default `"markdown"` for back-compat) so downstream consumers can branch on origin (specifically: the `dataset_cached_field_drift` health check skips entities with `provider == "datapackage-directory"`, since they have no two surfaces to drift between).
- Snapshot-based regression test: a "kitchen-sink" fixture project containing one of each existing entity type, with `load_project_sources` output snapshotted in the first commit. Every refactor commit must keep this snapshot green.
- Per-provider unit tests, resolver tests, integration tests for the new capabilities (single-type aggregate, datapackage-directory promotion).

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

### `EntityProvider` — abstract base

Lives at `science-tool/src/science_tool/graph/entity_providers/base.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path

from science_tool.graph.sources import SourceEntity


class EntityProvider(ABC):
    """Discovers entities from a particular storage convention.

    Each provider is self-contained: knows where to look, knows how to
    read what it finds, returns ready-to-use SourceEntity objects.
    Stateless across calls (a future cache layer wraps providers).
    """

    name: str  # short human-readable identifier (e.g. "markdown", "datapackage-directory")

    @abstractmethod
    def discover(self, project_root: Path) -> list[SourceEntity]:
        """Walk the filesystem under `project_root` and return all entities found."""
```

Three concrete implementations:
- `markdown.py` — `MarkdownProvider`
- `datapackage_directory.py` — `DatapackageDirectoryProvider`
- `aggregate.py` — `AggregateProvider`

Each is one focused file (target <200 lines).

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

### `SourceEntity.provider` field

Add to the `SourceEntity` Pydantic model (in `graph/sources.py`):

```python
class SourceEntity(BaseModel):
    # ... existing fields ...
    provider: str = "markdown"  # which EntityProvider produced this entity
```

Default `"markdown"` keeps existing direct-callsite specialized parsers (which don't go through providers) compatible without code changes — they just produce entities labeled as if from markdown, which is harmless because health checks that branch on provider only filter on the new `"datapackage-directory"` value.

### Data shapes (no other new types)

Spec Y introduces no new entity-level data types. The existing `SourceEntity` is what providers produce and what `load_project_sources` already consumes.

## Provider Implementations

### `MarkdownProvider`

Refactor of existing `_load_markdown_entities`. Same behavior, packaged as a class.

```python
class MarkdownProvider(EntityProvider):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        # Roots relative to project_root. Defaults match the existing convention.
        self._scan_roots = scan_roots or [
            "doc",
            "specs",
            "research/packages",
        ]

    def discover(self, project_root: Path) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                entity = parse_entity_file(path, project_slug=project_root.name)
                if entity is None:
                    continue
                entities.append(self._build_source_entity(path, entity, project_root))
        return entities

    def _build_source_entity(self, path: Path, entity, project_root: Path) -> SourceEntity:
        # Existing per-file logic from _load_markdown_entities (alias derivation,
        # reasoning-metadata wiring, profile resolution) lifted into the provider.
        # provider="markdown" set on the resulting SourceEntity.
        ...
```

### `DatapackageDirectoryProvider`

New. Scans for entity-flavored datapackages.

```python
class DatapackageDirectoryProvider(EntityProvider):
    name = "datapackage-directory"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["data", "results"]

    def discover(self, project_root: Path) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for dp_path in sorted(root.rglob("datapackage.yaml")):
                with dp_path.open() as f:
                    dp = yaml.safe_load(f) or {}
                profiles = dp.get("profiles") or []
                if "science-pkg-entity-1.0" not in profiles:
                    continue  # data-only datapackage, not an entity
                entity = self._build_entity(project_root, dp_path, dp)
                if entity is not None:
                    entities.append(entity)
        return entities

    def _build_entity(self, project_root: Path, dp_path: Path, dp: dict) -> SourceEntity | None:
        # Construct SourceEntity from the datapackage's science-pkg-entity-1.0 fields.
        # canonical_id from dp["id"]; source_path is dp_path.relative_to(project_root).
        # provider="datapackage-directory" set on the resulting SourceEntity.
        ...
```

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

### Path 5: Specialized parsers — UNCHANGED

`parse_tasks`, `_load_model_sources`, `_load_parameter_sources` stay as direct callsites in `load_project_sources`. No wrapper, no `EntityProvider` inheritance. They're not providers; they're end-to-end specialized.

### Implementation sequencing

The implementation plan will land in this order:

1. Add the `entity_providers/` package, `EntityProvider` base, and `EntityResolver` + `EntityIdCollisionError` (no integration yet)
2. Add the snapshot regression test fixture + checked-in snapshot (canary for the next steps)
3. Refactor `MarkdownProvider` (Path 1) — invisible behavior, snapshot stays green
4. Refactor `AggregateProvider` for multi-type (Path 2) — invisible behavior, snapshot stays green
5. Switch `load_project_sources` to use the resolver — still invisible
6. Add `provider: str` field to `SourceEntity` (default `"markdown"`) — invisible
7. Add `AggregateProvider`'s single-type convention (Path 3) — new capability, mm30 can opt in
8. Add `DatapackageDirectoryProvider` (Path 4) — new capability, dataset promotion possible
9. Update `dataset_cached_field_drift` health check to skip provider==`"datapackage-directory"` entities
10. Tests + docs

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
- Test: call `load_project_sources(fixture_root)` → assert the result equals a checked-in snapshot of expected `ProjectSources` data.
- The fixture and snapshot are committed in the SECOND commit of the implementation plan (after the new package skeleton, before any refactor) so subsequent commits' regressions are caught immediately.
- After EACH refactor commit (steps 3, 4, 5 in the implementation sequencing above), this test must continue to pass with the same snapshot.

This is the canary that catches "the refactor changed something subtly."

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
- **`SourceEntity.provider: str` field** added (default `"markdown"`) so downstream consumers (specifically the `dataset_cached_field_drift` health check) can branch on origin without parallel data structures.
- **`default_providers()` is a function, not a constant** — supports test injection without monkey-patching.
- **AggregateProvider's single-type convention is `doc/<plural>/<plural>.{json,yaml}`** — file inside the per-type directory, sharing namespace with markdown entries. Type inference reuses `_DIR_TO_TYPE` from `science_model/frontmatter.py`.
- **Provider scan roots are constructor parameters** with sensible defaults — supports test injection and future per-project knobs without redesign.
- **Behavior preservation is the refactor's success criterion.** A snapshot regression test on a kitchen-sink fixture must stay green across every commit in the implementation plan.
- **No migration commands in v1.** `dataset promote`, `entities aggregate` are documented as follow-on work; manual migration is the documented v1 path.
- **No symlinks, no fallback ordering.** Each entity has exactly one source path. If two providers find the same ID, that's an error to fix, not a runtime decision to absorb.

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

# Unified Entity Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current multi-model entity loading architecture with one canonical entity model family, typed core project entities, an explicit kind registry, and storage adapters that load into the unified model.

**Architecture:** Start in `science-model` by defining the new model family and locking field placement with tests. Then add an explicit registry and storage-adapter layer in `science-tool`, migrate current markdown/task/dataset loading onto that path, preserve source-location and collision behavior, and defer non-core legacy model/parameter concepts out of the core load path. Keep rev-2.2 dataset guarantees intact throughout.

**Tech Stack:** Python, Pydantic, pytest, uv, ruff, pyright

---

### Task 1: Lock the Entity Family Boundary in Tests

**Files:**
- Modify: `science-model/tests/test_entities.py`
- Modify: `science-model/tests/test_dataset_models.py`
- Modify: `science-model/tests/test_tasks.py`
- Reference: `science-model/src/science_model/entities.py`
- Reference: `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`

**Step 1: Write the failing tests**

Add tests that define the intended hierarchy and field ownership before any implementation change:

```python
def test_project_entity_inherits_entity() -> None:
    entity = ProjectEntity(
        id="hypothesis:test",
        canonical_id="hypothesis:test",
        kind="hypothesis",
        title="Test",
        project="demo",
    )
    assert entity.kind == "hypothesis"


def test_dataset_entity_inherits_project_entity() -> None:
    entity = DatasetEntity(
        id="dataset:test",
        canonical_id="dataset:test",
        kind="dataset",
        title="Test Dataset",
        project="demo",
        origin="external",
        access={"url": "https://example.com", "license": "CC-BY"},
    )
    assert entity.kind == "dataset"


def test_task_entity_inherits_project_entity() -> None:
    entity = TaskEntity(
        id="task:t01",
        canonical_id="task:t01",
        kind="task",
        title="Test task",
        project="demo",
    )
    assert entity.kind == "task"
```

Add one explicit field-placement test so the architecture cannot drift silently:

```python
def test_entity_base_keeps_cross_cutting_fields() -> None:
    entity = Entity(
        id="concept:x",
        canonical_id="concept:x",
        kind="concept",
        title="X",
        ontology_terms=["skos:Concept"],
    )
    assert entity.ontology_terms == ["skos:Concept"]
```

Add a second field-placement test that forces a decision on `profile`:

```python
def test_project_entity_owns_project_profile_metadata() -> None:
    entity = ProjectEntity(
        id="question:q1",
        canonical_id="question:q1",
        kind="question",
        title="Q1",
        project="demo",
        profile="local",
    )
    assert entity.profile == "local"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_dataset_models.py science-model/tests/test_tasks.py -q
```

Expected: FAIL with missing `ProjectEntity`, `DatasetEntity`, or `TaskEntity` symbols.

**Step 3: Write the minimal implementation**

Implement the smallest possible model-family scaffolding in `science-model/src/science_model/entities.py`:

- add `ProjectEntity(Entity)`
- add `DomainEntity(Entity)`
- add `TaskEntity(ProjectEntity)`
- add `DatasetEntity(ProjectEntity)`
- add placeholder `WorkflowRunEntity(ProjectEntity)`
- add placeholder `ResearchPackageEntity(ProjectEntity)`

Keep `ontology_terms` on base `Entity`.

Treat `profile` as project-facing metadata unless existing tests prove it must remain on base `Entity`. If moving `profile` would create excessive churn, keep it temporarily on `Entity` and add a TODO comment plus a plan note in code.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_dataset_models.py science-model/tests/test_tasks.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-model/tests/test_entities.py science-model/tests/test_dataset_models.py science-model/tests/test_tasks.py science-model/src/science_model/entities.py
git commit -m "feat: add unified entity model hierarchy"
```

### Task 2: Rehome Task Into the Entity Model Family

**Files:**
- Modify: `science-model/src/science_model/tasks.py`
- Modify: `science-tool/src/science_tool/tasks.py`
- Modify: `science-model/tests/test_tasks.py`
- Modify: `science-tool/tests/test_tasks.py`
- Modify: `science-tool/tests/test_tasks_cli.py`
- Reference: `science-model/src/science_model/entities.py`

**Step 1: Write the failing tests**

Add tests that require the task parser to produce task data that can be losslessly converted into `TaskEntity` fields:

```python
def test_parsed_task_maps_to_task_entity_fields(task_path: Path) -> None:
    task = parse_tasks(task_path)[0]
    entity = TaskEntity.from_task(task, project="demo")
    assert entity.kind == "task"
    assert entity.blocked_by == task.blocked_by
    assert entity.description == task.description
```

Add one CLI-level test that still exercises current task file behavior but asserts the modeled type is `TaskEntity`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py science-tool/tests/test_tasks.py science-tool/tests/test_tasks_cli.py -q
```

Expected: FAIL because `TaskEntity.from_task()` or equivalent conversion path does not exist.

**Step 3: Write minimal implementation**

In `science-model/src/science_model/tasks.py`:

- either deprecate the standalone `Task` model in favor of `TaskEntity`
- or keep `Task` as a parse-layer helper, but add an explicit conversion path into `TaskEntity`

In `science-tool/src/science_tool/tasks.py`:

- keep the DSL parser
- convert parsed tasks into `TaskEntity`-compatible raw records or instances

Do not redesign the task DSL in this task.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py science-tool/tests/test_tasks.py science-tool/tests/test_tasks_cli.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-model/src/science_model/tasks.py science-tool/src/science_tool/tasks.py science-model/tests/test_tasks.py science-tool/tests/test_tasks.py science-tool/tests/test_tasks_cli.py
git commit -m "feat: map task parsing onto task entity"
```

### Task 3: Add the Kind Registry

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_registry.py`
- Modify: `science-tool/src/science_tool/graph/__init__.py`
- Modify: `science-tool/tests/test_graph_build_strict.py`
- Create: `science-tool/tests/test_entity_registry.py`
- Reference: `science-model/src/science_model/entities.py`

**Step 1: Write the failing tests**

Create `science-tool/tests/test_entity_registry.py` with tests like:

```python
def test_registry_resolves_core_kind() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("task") is TaskEntity


def test_registry_rejects_duplicate_core_kind() -> None:
    registry = EntityRegistry()
    registry.register_core_kind("task", TaskEntity)
    with pytest.raises(ValueError, match="task"):
        registry.register_core_kind("task", TaskEntity)


def test_registry_rejects_extension_shadowing_core_kind() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(ValueError, match="dataset"):
        registry.register_extension_kind("dataset", CustomDatasetEntity)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entity_registry.py -q
```

Expected: FAIL because `EntityRegistry` does not exist.

**Step 3: Write minimal implementation**

Implement `EntityRegistry` with:

- `register_core_kind(kind: str, schema: type[Entity]) -> None`
- `register_extension_kind(kind: str, schema: type[Entity]) -> None`
- `resolve(kind: str) -> type[Entity]`
- `with_core_types() -> EntityRegistry`

Register the v1 core project kinds here.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entity_registry.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/entity_registry.py science-tool/tests/test_entity_registry.py science-tool/src/science_tool/graph/__init__.py
git commit -m "feat: add explicit entity kind registry"
```

### Task 4: Add the Storage Adapter Base Contract

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/base.py`
- Create: `science-tool/src/science_tool/graph/storage_adapters/__init__.py`
- Create: `science-tool/tests/test_storage_adapters_base.py`
- Reference: `science-tool/src/science_tool/graph/sources.py`

**Step 1: Write the failing tests**

Create base-contract tests:

```python
def test_source_ref_carries_adapter_and_path() -> None:
    ref = SourceRef(adapter_name="markdown", path="doc/x.md", line=12)
    assert ref.adapter_name == "markdown"
    assert ref.path == "doc/x.md"


def test_storage_adapter_protocol_can_be_implemented() -> None:
    class DummyAdapter:
        name = "dummy"

        def discover(self, project_root: Path) -> list[SourceRef]:
            return [SourceRef(adapter_name="dummy", path="x.json")]

        def load_raw(self, ref: SourceRef) -> dict[str, object]:
            return {"kind": "task", "id": "task:t1", "canonical_id": "task:t1", "title": "T1"}

    adapter = DummyAdapter()
    assert adapter.load_raw(adapter.discover(Path("."))[0])["kind"] == "task"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapters_base.py -q
```

Expected: FAIL because `SourceRef` and adapter base types do not exist.

**Step 3: Write minimal implementation**

Add:

- `SourceRef` Pydantic model
- `StorageAdapter` `Protocol`
- optional `dump()` signature, but do not implement full write support yet

Keep the contract small.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapters_base.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/storage_adapters/base.py science-tool/src/science_tool/graph/storage_adapters/__init__.py science-tool/tests/test_storage_adapters_base.py
git commit -m "feat: add storage adapter base contract"
```

### Task 5: Implement Markdown and Task Adapters on the New Path

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/markdown.py`
- Create: `science-tool/src/science_tool/graph/storage_adapters/tasks.py`
- Modify: `science-model/src/science_model/frontmatter.py`
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Create: `science-tool/tests/test_storage_adapter_markdown.py`
- Create: `science-tool/tests/test_storage_adapter_tasks.py`
- Reference: `science-tool/tests/test_sources_research_package.py`

**Step 1: Write the failing tests**

Add one markdown adapter test:

```python
def test_markdown_adapter_loads_raw_record(project_root: Path) -> None:
    adapter = MarkdownEntityAdapter()
    ref = adapter.discover(project_root)[0]
    raw = adapter.load_raw(ref)
    assert raw["kind"] == "hypothesis"
    assert raw["canonical_id"].startswith("hypothesis:")
```

Add one task adapter test:

```python
def test_task_adapter_loads_task_entity_record(project_root: Path) -> None:
    adapter = TaskEntityAdapter()
    ref = adapter.discover(project_root)[0]
    raw = adapter.load_raw(ref)
    assert raw["kind"] == "task"
    assert "blocked_by" in raw
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapter_markdown.py science-tool/tests/test_storage_adapter_tasks.py -q
```

Expected: FAIL because the adapters do not exist.

**Step 3: Write minimal implementation**

Implement:

- `MarkdownEntityAdapter`
- `TaskEntityAdapter`

Keep `parse_entity_file()` as the markdown parsing helper for the markdown adapter rather than rewriting it.

Have each adapter return registry-dispatchable raw records with:

- `kind`
- `id`
- `canonical_id`
- `title`
- base fields
- type-specific fields where applicable

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapter_markdown.py science-tool/tests/test_storage_adapter_tasks.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/storage_adapters/markdown.py science-tool/src/science_tool/graph/storage_adapters/tasks.py science-model/src/science_model/frontmatter.py science-tool/tests/test_storage_adapter_markdown.py science-tool/tests/test_storage_adapter_tasks.py
git commit -m "feat: add markdown and task entity adapters"
```

### Task 6: Implement Aggregate and Datapackage Adapters

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/aggregate.py`
- Create: `science-tool/src/science_tool/graph/storage_adapters/datapackage.py`
- Modify: `science-model/src/science_model/frontmatter.py`
- Modify: `science-model/src/science_model/packages/schema.py`
- Modify: `science-tool/tests/test_dataset_reconcile.py`
- Create: `science-tool/tests/test_storage_adapter_aggregate.py`
- Create: `science-tool/tests/test_storage_adapter_datapackage.py`
- Reference: `science-tool/tests/test_dataset_register_run.py`

**Step 1: Write the failing tests**

Aggregate:

```python
def test_aggregate_adapter_loads_multi_entity_file(project_root: Path) -> None:
    adapter = AggregateEntityAdapter()
    ref = adapter.discover(project_root)[0]
    raw = adapter.load_raw(ref)
    assert raw["kind"] == "topic"
```

Datapackage:

```python
def test_datapackage_adapter_extracts_dataset_entity_fields(project_root: Path) -> None:
    adapter = DatapackageEntityAdapter()
    ref = adapter.discover(project_root)[0]
    raw = adapter.load_raw(ref)
    assert raw["kind"] == "dataset"
    assert "resources" not in raw
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapter_aggregate.py science-tool/tests/test_storage_adapter_datapackage.py -q
```

Expected: FAIL because the adapters do not exist.

**Step 3: Write minimal implementation**

Implement:

- `AggregateEntityAdapter`
- `DatapackageEntityAdapter`

For datapackages:

- extract only the subset that maps to `DatasetEntity`
- leave runtime-only data such as `resources[]` in the datapackage layer
- preserve rev-2.2 dataset invariants during `DatasetEntity` validation

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapter_aggregate.py science-tool/tests/test_storage_adapter_datapackage.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/storage_adapters/aggregate.py science-tool/src/science_tool/graph/storage_adapters/datapackage.py science-model/src/science_model/packages/schema.py science-tool/tests/test_storage_adapter_aggregate.py science-tool/tests/test_storage_adapter_datapackage.py
git commit -m "feat: add aggregate and datapackage entity adapters"
```

### Task 7: Replace `graph/sources.py` Load Flow With Registry + Adapters

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Modify: `science-tool/src/science_tool/graph/health.py`
- Create: `science-tool/tests/test_sources_unified_entity_load.py`
- Modify: `science-tool/tests/test_health.py`
- Modify: `science-tool/tests/test_graph_materialize.py`
- Modify: `science-tool/tests/test_sources_research_package.py`

**Step 1: Write the failing tests**

Create an end-to-end load test:

```python
def test_load_project_sources_uses_unified_entity_registry(fixture_project: Path) -> None:
    project = load_project_sources(fixture_project)
    by_kind = {entity.kind for entity in project.entities}
    assert "task" in by_kind
    assert "dataset" in by_kind
```

Add one collision test:

```python
def test_load_project_sources_rejects_duplicate_canonical_id(fixture_project: Path) -> None:
    with pytest.raises(EntityIdentityCollisionError, match="dataset:x"):
        load_project_sources(fixture_project)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_sources_unified_entity_load.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_health.py -q
```

Expected: FAIL because `load_project_sources()` still uses the old loader graph.

**Step 3: Write minimal implementation**

In `science-tool/src/science_tool/graph/sources.py`:

- build `EntityRegistry.with_core_types()`
- build the active adapter list
- discover refs
- load raw records
- resolve schemas
- validate typed entities
- maintain a global identity table

Keep source-location metadata attached to errors.

In `science-tool/src/science_tool/graph/health.py`:

- update any code that assumes only markdown-sidecar dataset entities
- preserve existing rev-2.2 semantics

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_sources_unified_entity_load.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_health.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py science-tool/src/science_tool/graph/health.py science-tool/tests/test_sources_unified_entity_load.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_health.py science-tool/tests/test_sources_research_package.py
git commit -m "feat: switch graph sources to unified entity loading"
```

### Task 8: Remove Core `model` / `parameter` Loading and Add Extension Path

**Files:**
- Modify: `science-model/src/science_model/source_contracts.py`
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Create: `science-tool/tests/test_entity_extensions.py`
- Modify: `science-model/tests/test_source_contracts.py`
- Modify: `science-tool/tests/test_graph_build_strict.py`

**Step 1: Write the failing tests**

Add an extension-registration test:

```python
def test_project_extension_kind_can_be_registered() -> None:
    class CustomModelEntity(ProjectEntity):
        equation: str

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", CustomModelEntity)
    assert registry.resolve("natural-system:model") is CustomModelEntity
```

Add a load-path test that asserts core `graph/sources.py` no longer hardcodes `ModelSource` / `ParameterSource`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entity_extensions.py science-model/tests/test_source_contracts.py -q
```

Expected: FAIL because the old source-contract assumptions are still core behavior.

**Step 3: Write minimal implementation**

Make the v1 decision real:

- remove hardcoded core loading of model / parameter entities from `graph/sources.py`
- keep `source_contracts.py` only if needed for compatibility or extension-layer helpers
- update tests to reflect that model / parameter are no longer core typed entities

Do not remove code that is still needed by a project extension path in the same commit unless replacement coverage exists.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entity_extensions.py science-model/tests/test_source_contracts.py science-tool/tests/test_graph_build_strict.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add science-model/src/science_model/source_contracts.py science-tool/src/science_tool/graph/sources.py science-tool/tests/test_entity_extensions.py science-model/tests/test_source_contracts.py science-tool/tests/test_graph_build_strict.py
git commit -m "refactor: move model and parameter concepts out of core entity loading"
```

### Task 9: Run Full Verification and Update Docs

**Files:**
- Modify: `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`
- Modify: `docs/plans/2026-04-20-unified-entity-model-implementation.md`
- Modify: any touched module docstrings if they became inaccurate

**Step 1: Write the failing test or doc check**

No new feature test here. Add one small regression test only if a gap was discovered during Tasks 1-8 and is not yet covered.

**Step 2: Run focused and full verification**

Run:

```bash
uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_tasks.py science-model/tests/test_dataset_models.py science-tool/tests/test_tasks.py science-tool/tests/test_health.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_dataset_register_run.py -q
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected: PASS

**Step 3: Write minimal cleanup implementation**

Update stale docstrings and spec notes uncovered during verification. Keep this task for cleanup only; do not slip new architecture into it.

**Step 4: Run verification again**

Run:

```bash
uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_tasks.py science-model/tests/test_dataset_models.py science-tool/tests/test_tasks.py science-tool/tests/test_health.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_dataset_register_run.py -q
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected: PASS

**Step 5: Commit**

```bash
git add docs/specs/2026-04-20-multi-backend-entity-resolver-design.md docs/plans/2026-04-20-unified-entity-model-implementation.md
git commit -m "docs: finalize unified entity model migration notes"
```

## Implementation Notes

- Keep `parse_entity_file()` as the canonical markdown parsing helper unless a later task proves it should move behind a thinner adapter wrapper.
- Preserve source-location metadata in all adapter outputs; errors must still point to concrete files and lines where available.
- Do not redesign the graph store in this plan.
- Do not redesign caching in this plan.
- If moving `profile` off base `Entity` creates broad churn, stage that move in a separate follow-up after the unified load path is stable.
- Keep `ontology_terms` on base `Entity` unless concrete breakage demonstrates a better placement. This matches the current spec direction and your note that ontology-backed meta entities may legitimately use ontology grounding too.

## Suggested Verification Commands by Phase

```bash
uv run --frozen pytest science-model/tests/test_entities.py -q
uv run --frozen pytest science-model/tests/test_tasks.py science-tool/tests/test_tasks.py -q
uv run --frozen pytest science-tool/tests/test_entity_registry.py science-tool/tests/test_storage_adapters_base.py -q
uv run --frozen pytest science-tool/tests/test_storage_adapter_markdown.py science-tool/tests/test_storage_adapter_tasks.py -q
uv run --frozen pytest science-tool/tests/test_storage_adapter_aggregate.py science-tool/tests/test_storage_adapter_datapackage.py -q
uv run --frozen pytest science-tool/tests/test_sources_unified_entity_load.py science-tool/tests/test_health.py science-tool/tests/test_graph_materialize.py -q
uv run --frozen ruff check .
uv run --frozen pyright
```

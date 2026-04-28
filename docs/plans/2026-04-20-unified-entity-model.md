# Unified Entity Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the provider-first entity-loading architecture (Spec Y, merged 2026-04-20) with the model-first unified architecture from `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`: one canonical `Entity` model family, explicit kind registry, narrow storage-adapter contract.

**Architecture:** Decompose the current flat `Entity` / `SourceEntity` into `Entity` (base) → `ProjectEntity` / `DomainEntity` (subfamilies) → `TaskEntity`, `DatasetEntity`, `WorkflowRunEntity`, `ResearchPackageEntity` (typed). Adapters discover files and return raw dicts keyed on `kind`; an `EntityRegistry` dispatches to the right schema; `schema.model_validate(raw)` produces the final typed instance. Identity collisions are detected through a global table keyed on `canonical_id`. Spec Y's `EntityProvider` / `EntityRecord` / `_normalize_record` / `SourceEntity` artifacts are removed; the `MarkdownProvider` / `AggregateProvider` / `DatapackageDirectoryProvider` logic is relocated into the new adapter layer.

**Tech Stack:** Python 3.11+, Pydantic, pytest, uv, ruff, pyright.

**Supersedes:** `docs/plans/2026-04-20-unified-entity-model-implementation.md` (earlier draft that predates the replacement spec).

**Key reference paths:**
- Spec: `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md` (replacement)
- Existing `Entity`: `science-model/src/science_model/entities.py`
- Existing `Task`: `science-model/src/science_model/tasks.py`
- Existing `SourceEntity` + resolver (to delete): `science-tool/src/science_tool/graph/source_types.py`, `science-tool/src/science_tool/graph/entity_providers/`
- Existing `load_project_sources`: `science-tool/src/science_tool/graph/sources.py`
- Regression canary: `science-tool/tests/test_load_project_sources_regression.py` + `science-tool/tests/fixtures/spec_y_kitchen_sink/snapshot.json`

**Conventions (from project CLAUDE.md):**
- All Python invocations: `uv run --frozen <command>`
- Lint: `uv run --frozen ruff check .`
- Format: `uv run --frozen ruff format .`
- Type check: `uv run --frozen pyright`
- Tests: `uv run --frozen pytest <path>`
- Line length: 120 chars

**Key invariants (read before any task):**

- **All work happens in an isolated git worktree.** The executing skill sets up `.worktrees/unified-entity-model/` before Task 1.
- **Every commit must keep the existing test suite green.** Run `cd science-tool && uv run --frozen pytest -q` after every task.
- **The regression snapshot canary** (`test_load_project_sources_regression.py`) stays green until Task 10 (cutover). Task 10 regenerates `snapshot.json` because the entity class structure changes — the regeneration commit documents the structural diff and is reviewed specifically. After Task 10 the canary catches drift from the new baseline going forward.
- **The kitchen-sink fixture** (`tests/fixtures/spec_y_kitchen_sink/`) is storage, not model — it does NOT change during this plan.
- **Pre-existing pyright errors** in `science-tool/src/science_tool/cli.py` and similar legacy files (listed as out-of-scope in Spec Y's plan header) remain out-of-scope here.
- **Spec non-goals apply:** no graph-store redesign, no RDF materialization change, no new query API, no caching.

**Phases:**
1. Model family foundation (Tasks 1–3): Entity/ProjectEntity/DomainEntity + typed entities + SourceRef
2. Registry (Task 4)
3. Storage adapters (Tasks 5–9)
4. Integration cutover (Task 10)
5. Cleanup + migration (Tasks 11–13)

---

## Phase 1: Model Family Foundation

### Task 1: Carve out `Entity` base; add `ProjectEntity` and `DomainEntity`

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Test: `science-model/tests/test_entity_hierarchy.py` (new)

- [ ] **Step 1: Write failing test**

Create `science-model/tests/test_entity_hierarchy.py`:

```python
"""Tests for the three-layer entity model family: Entity → ProjectEntity / DomainEntity."""
from __future__ import annotations

import pytest

from science_model.entities import Entity, ProjectEntity, DomainEntity, EntityType


def test_entity_base_has_cross_cutting_fields_only() -> None:
    """Entity base carries only cross-cutting fields per spec §Canonical Base Model."""
    # Minimal construction — no project/domain/dataset-specific fields required.
    e = Entity(
        id="concept:x",
        canonical_id="concept:x",
        type=EntityType.CONCEPT,
        title="X",
        ontology_terms=["skos:Concept"],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/concepts/x.md",
    )
    assert e.canonical_id == "concept:x"
    assert e.ontology_terms == ["skos:Concept"]
    # ProjectEntity-only fields not present on base:
    assert not hasattr(e, "blocked_by")
    assert not hasattr(e, "maturity")
    assert not hasattr(e, "pre_registered")
    # DatasetEntity-only fields not on base:
    assert not hasattr(e, "origin")
    assert not hasattr(e, "access")


def test_project_entity_inherits_entity() -> None:
    pe = ProjectEntity(
        id="hypothesis:h01",
        canonical_id="hypothesis:h01",
        type=EntityType.HYPOTHESIS,
        title="H01",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/hypotheses/h01.md",
        blocked_by=["hypothesis:h00"],
        maturity="exploratory",
    )
    assert isinstance(pe, Entity)
    assert pe.blocked_by == ["hypothesis:h00"]
    assert pe.project == "demo"


def test_domain_entity_inherits_entity() -> None:
    de = DomainEntity(
        id="disease:DOID:0001",
        canonical_id="disease:DOID:0001",
        type=EntityType.UNKNOWN,  # DomainEntity kinds may be project-extension-defined
        title="Example Disease",
        ontology_terms=["DOID:0001"],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="",
    )
    assert isinstance(de, Entity)
    # DomainEntity should not carry project-operational fields:
    assert not hasattr(de, "blocked_by")
    assert not hasattr(de, "maturity")


def test_project_entity_does_not_allow_dataset_specific_fields() -> None:
    """Dataset-specific fields live on DatasetEntity (Task 2), not on base ProjectEntity."""
    with pytest.raises(Exception):  # pydantic ValidationError for unknown field
        ProjectEntity(  # type: ignore[call-arg]
            id="hypothesis:h01",
            canonical_id="hypothesis:h01",
            type=EntityType.HYPOTHESIS,
            title="H01",
            project="demo",
            ontology_terms=[],
            related=[],
            source_refs=[],
            content_preview="",
            file_path="doc/hypotheses/h01.md",
            origin="external",  # dataset-specific; must not validate on ProjectEntity
        )
```

- [ ] **Step 2: Run failing test**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/unified-entity-model
uv run --frozen pytest science-model/tests/test_entity_hierarchy.py -v
```

Expected: ImportError on `ProjectEntity` / `DomainEntity`.

- [ ] **Step 3: Refactor `Entity` + add subfamilies**

In `science-model/src/science_model/entities.py`:

1. **Keep on base `Entity`** — cross-cutting fields only (per spec §Canonical Base Model):
   - `id`, `canonical_id`, `type`, `title`, `status`
   - `aliases`, `same_as`, `related`, `source_refs`, `ontology_terms`
   - `content`, `content_preview`, `file_path`
   - `created`, `updated`
   - `profile` (spec includes in base)
   - `sync_source` (already present; cross-cutting)
   - The existing `_fill_derived_defaults` validator (auto-populates `canonical_id`)

2. **Remove from base `Entity`** and move to `ProjectEntity`:
   - `project`, `domain`, `maturity`, `confidence`, `datasets`
   - `pre_registered`, `pre_registered_date`
   - Reasoning fields: `claim_layer`, `identification_strength`, `proxy_directness`, `supports_scope`, `independence_group`, `measurement_model`, `rival_model_packet_ref`
   - Add new field: `blocked_by: list[str] = Field(default_factory=list)` (previously lived only on `SourceEntity`; now lives on `ProjectEntity` since tasks/hypotheses can both have blockers)

3. **Remove from base `Entity`** and move to `DatasetEntity` (Task 2):
   - `origin`, `access`, `derivation`, `accessions`, `datapackage`, `local_path`, `consumed_by`, `parent_dataset`, `siblings`
   - The existing `_enforce_origin_block_invariants` validator

4. **Add** `DomainEntity(Entity)`: empty subclass (fields can be added incrementally as project extensions register domain kinds). Include a class docstring referencing the spec.

Pattern sketch:

```python
class Entity(BaseModel):
    """Canonical base entity per spec §Canonical Base Model.

    Carries only cross-cutting fields used by generic tooling (graph
    materialization, identity resolution, aliasing, linking). Type-specific
    invariants live in ProjectEntity / DomainEntity and their subclasses.
    """

    id: str
    canonical_id: str = ""
    type: EntityType
    title: str
    status: str | None = None
    profile: str = "core"
    ontology_terms: list[str]
    created: date | None = None
    updated: date | None = None
    related: list[str]
    same_as: list[str] = Field(default_factory=list)
    source_refs: list[str]
    aliases: list[str] = Field(default_factory=list)
    content_preview: str
    content: str = ""
    file_path: str
    sync_source: SyncSource | None = None

    @model_validator(mode="after")
    def _fill_derived_defaults(self) -> "Entity":
        if not self.canonical_id:
            self.canonical_id = self.id
        return self


class ProjectEntity(Entity):
    """Entity about the conduct of a science project (tasks, hypotheses, datasets…).

    Sub-base for the operational / epistemic side of the model family.
    See spec §Entity Subfamilies.
    """

    project: str
    domain: str | None = None
    blocked_by: list[str] = Field(default_factory=list)
    maturity: str | None = None
    confidence: float | None = None
    datasets: list[str] | None = None
    pre_registered: bool = False
    pre_registered_date: date | None = None
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet_ref: str | None = None

    model_config = {"extra": "forbid"}  # reject unknown fields (dataset-specific etc.)


class DomainEntity(Entity):
    """Entity about external domain subject matter (diseases, pathways, chemicals…).

    Sub-base for domain-grounded entities. Initial Science core ships empty —
    domain-specific fields arrive through project extensions.
    See spec §Entity Subfamilies.
    """

    model_config = {"extra": "forbid"}
```

**Important:** `DatasetEntity` is defined in Task 2, but `ProjectEntity` must not accept dataset-specific fields like `origin`. The `extra="forbid"` above enforces that. The `test_project_entity_does_not_allow_dataset_specific_fields` test validates the constraint.

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest science-model/tests/test_entity_hierarchy.py -v
uv run --frozen pytest science-model/tests/ -q
```

Expected: new tests PASS. Other science-model tests may fail because existing code still constructs `Entity(...)` with `project=` / `origin=` / etc. — do NOT fix those yet. Task 2 + Task 11 migrate those usages.

**Interim approach for Task 1 only:** temporarily disable the `extra="forbid"` on `ProjectEntity` if existing `science-model` tests break, and re-enable it at Task 2 once `DatasetEntity` exists. Note any deferred fix in the commit message.

- [ ] **Step 5: Commit**

```bash
cd science-model
uv run --frozen ruff format src/science_model/entities.py tests/test_entity_hierarchy.py
git add src/science_model/entities.py tests/test_entity_hierarchy.py
git commit -m "feat(entities): carve Entity base; add ProjectEntity + DomainEntity subfamilies"
```

---

### Task 2: Add typed core entities

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Test: `science-model/tests/test_typed_entities.py` (new)

- [ ] **Step 1: Write failing test**

Create `science-model/tests/test_typed_entities.py`:

```python
"""Tests for Science-core typed entities per spec §Typed Entity Model."""
from __future__ import annotations

from datetime import date

import pytest

from science_model.entities import (
    DatasetEntity,
    EntityType,
    ProjectEntity,
    ResearchPackageEntity,
    TaskEntity,
    WorkflowRunEntity,
)
from science_model.packages.schema import AccessBlock


def test_task_entity_extends_project_entity() -> None:
    t = TaskEntity(
        id="task:t01",
        canonical_id="task:t01",
        type=EntityType.HYPOTHESIS,  # use HYPOTHESIS placeholder if TASK kind missing;
                                      # real kind mapping lives in registry (Task 4).
        title="T01",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="tasks/active.md",
        priority="P1",
        created=date(2026, 4, 20),
    )
    assert isinstance(t, ProjectEntity)
    assert t.priority == "P1"


def test_dataset_entity_requires_access_when_origin_external() -> None:
    """Invariant #7 from rev 2.2 stays on DatasetEntity."""
    with pytest.raises(ValueError, match="origin=external requires an access block"):
        DatasetEntity(
            id="dataset:ds01",
            canonical_id="dataset:ds01",
            type=EntityType.DATASET,
            title="DS01",
            project="demo",
            ontology_terms=[],
            related=[],
            source_refs=[],
            content_preview="",
            file_path="doc/datasets/ds01.md",
            origin="external",
            access=None,  # intentionally None; invariant must fire
        )


def test_dataset_entity_accepts_valid_external_origin() -> None:
    ds = DatasetEntity(
        id="dataset:ds01",
        canonical_id="dataset:ds01",
        type=EntityType.DATASET,
        title="DS01",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/datasets/ds01.md",
        origin="external",
        access=AccessBlock(level="public", verified=False),
    )
    assert isinstance(ds, ProjectEntity)
    assert ds.origin == "external"
    assert ds.access is not None


def test_workflow_run_entity_placeholder() -> None:
    wr = WorkflowRunEntity(
        id="workflow-run:r1",
        canonical_id="workflow-run:r1",
        type=EntityType.WORKFLOW_RUN,
        title="R1",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="results/wf/r1/workflow-run.md",
    )
    assert isinstance(wr, ProjectEntity)


def test_research_package_entity_placeholder() -> None:
    rp = ResearchPackageEntity(
        id="research-package:rp1",
        canonical_id="research-package:rp1",
        type=EntityType.RESEARCH_PACKAGE,
        title="RP1",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="research/packages/lens/rp1/research-package.md",
    )
    assert isinstance(rp, ProjectEntity)
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest science-model/tests/test_typed_entities.py -v
```

Expected: ImportError on new classes.

- [ ] **Step 3: Add the typed entities**

In `science-model/src/science_model/entities.py`, add after `ProjectEntity`:

```python
class TaskEntity(ProjectEntity):
    """Task — extends ProjectEntity with task-specific fields.

    Task fields (priority, blocked_by, completed, etc.) now live here rather
    than in a separate Task model. The existing science_model.tasks.Task stays
    during migration as a parse-layer helper until Task 9 wires the TaskAdapter.
    """

    priority: str = "P2"
    completed: date | None = None
    group: str = ""
    aspects: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)


class DatasetEntity(ProjectEntity):
    """Dataset — extends ProjectEntity with rev 2.2 dataset fields + invariants."""

    origin: str | None = None  # "external" | "derived"
    access: AccessBlock | None = None
    derivation: DerivationBlock | None = None
    accessions: list[str] = Field(default_factory=list)
    datapackage: str = ""
    local_path: str = ""
    consumed_by: list[str] = Field(default_factory=list)
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_origin_block_invariants(self) -> "DatasetEntity":
        """Invariants #7/#8 — unchanged from rev 2.2."""
        if self.origin is None:
            return self
        if self.origin == "external":
            if self.access is None:
                raise ValueError(f"{self.id}: origin=external requires an access block (invariant #7)")
        elif self.origin == "derived":
            if self.derivation is None:
                raise ValueError(f"{self.id}: origin=derived requires a derivation block (invariant #8)")
        return self


class WorkflowRunEntity(ProjectEntity):
    """Workflow run — placeholder typed entity.

    Fields populated as workflow-run semantics are formalized. For now,
    workflow-run records validate through this class so they carry the
    ProjectEntity contract but no type-specific invariants yet.
    """

    pass


class ResearchPackageEntity(ProjectEntity):
    """Research package — placeholder typed entity for package composition."""

    pass
```

Re-enable `extra="forbid"` on `ProjectEntity` from Task 1 if it was deferred. Verify that `DatasetEntity` and `TaskEntity` don't trip their own typed fields against the constraint (subclasses define their own fields, so they're allowed).

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest science-model/tests/test_typed_entities.py -v
uv run --frozen pytest science-model/tests/ -q
```

Expected: new tests PASS. Existing science-model tests may fail where they construct `Entity(...)` with dataset/task-specific fields. Those are migrated in Task 11. Run focused tests on just the new files for now.

- [ ] **Step 5: Commit**

```bash
cd science-model
uv run --frozen ruff format src/science_model/entities.py tests/test_typed_entities.py
git add src/science_model/entities.py tests/test_typed_entities.py
git commit -m "feat(entities): add typed core entities (Task/Dataset/WorkflowRun/ResearchPackage)"
```

---

### Task 3: Add `SourceRef` + `EntityIdentityCollisionError`

**Files:**
- Create: `science-model/src/science_model/source_ref.py`
- Create: `science-tool/src/science_tool/graph/errors.py`
- Test: `science-model/tests/test_source_ref.py`
- Test: `science-tool/tests/test_entity_errors.py`

- [ ] **Step 1: Write failing test (science-model side)**

Create `science-model/tests/test_source_ref.py`:

```python
"""Tests for SourceRef — first-class source-location metadata per spec §Source Location."""
from __future__ import annotations

from science_model.source_ref import SourceRef


def test_source_ref_minimal() -> None:
    ref = SourceRef(adapter_name="markdown", path="doc/hypotheses/h01.md")
    assert ref.adapter_name == "markdown"
    assert ref.path == "doc/hypotheses/h01.md"
    assert ref.line is None


def test_source_ref_with_line() -> None:
    ref = SourceRef(adapter_name="aggregate", path="knowledge/sources/local/entities.yaml", line=42)
    assert ref.line == 42


def test_source_ref_str_is_actionable_in_errors() -> None:
    ref = SourceRef(adapter_name="markdown", path="doc/hypotheses/h01.md", line=7)
    s = str(ref)
    assert "markdown" in s
    assert "doc/hypotheses/h01.md" in s
    assert "7" in s
```

- [ ] **Step 2: Write failing test (science-tool side)**

Create `science-tool/tests/test_entity_errors.py`:

```python
"""Tests for EntityIdentityCollisionError — global identity-table violations."""
from __future__ import annotations

import pytest

from science_model.source_ref import SourceRef
from science_tool.graph.errors import EntityIdentityCollisionError


def test_collision_message_includes_both_sources() -> None:
    first = SourceRef(adapter_name="markdown", path="doc/datasets/x.md")
    second = SourceRef(adapter_name="datapackage", path="data/x/datapackage.yaml")
    err = EntityIdentityCollisionError("dataset:x", first, second)
    msg = str(err)
    assert "dataset:x" in msg
    assert "doc/datasets/x.md" in msg
    assert "data/x/datapackage.yaml" in msg


def test_collision_is_valueerror_subclass() -> None:
    """Consumers catching ValueError should still catch identity collisions."""
    first = SourceRef(adapter_name="a", path="p1")
    second = SourceRef(adapter_name="b", path="p2")
    err = EntityIdentityCollisionError("x:1", first, second)
    assert isinstance(err, ValueError)
```

- [ ] **Step 3: Run failing tests**

```bash
uv run --frozen pytest science-model/tests/test_source_ref.py science-tool/tests/test_entity_errors.py -v
```

Expected: ImportError on both.

- [ ] **Step 4: Implement `SourceRef`**

Create `science-model/src/science_model/source_ref.py`:

```python
"""SourceRef — first-class source-location metadata.

Per spec §Source Location and Error Reporting: the load pipeline must
preserve enough location information to produce actionable error messages.
SourceRef travels alongside entities during load and is embedded in error
messages for collisions and validation failures.
"""

from __future__ import annotations

from pydantic import BaseModel


class SourceRef(BaseModel):
    """A pointer to where an entity record came from."""

    adapter_name: str  # "markdown" | "aggregate" | "datapackage" | "task" | extension-defined
    path: str          # project-relative file path
    line: int | None = None  # line number where available

    def __str__(self) -> str:
        suffix = f":{self.line}" if self.line is not None else ""
        return f"[{self.adapter_name}] {self.path}{suffix}"
```

- [ ] **Step 5: Implement `EntityIdentityCollisionError`**

Create `science-tool/src/science_tool/graph/errors.py`:

```python
"""Load-path errors for the unified entity model."""

from __future__ import annotations

from science_model.source_ref import SourceRef


class EntityIdentityCollisionError(ValueError):
    """Raised when two storage adapters produce records with the same canonical_id."""

    def __init__(self, canonical_id: str, first: SourceRef, second: SourceRef) -> None:
        self.canonical_id = canonical_id
        self.first = first
        self.second = second
        super().__init__(
            f"entity {canonical_id!r} produced by multiple sources:\n"
            f"  - {first}\n"
            f"  - {second}\n"
            f"Resolve by removing one source, or migrate to a single adapter."
        )
```

- [ ] **Step 6: Verify**

```bash
uv run --frozen pytest science-model/tests/test_source_ref.py science-tool/tests/test_entity_errors.py -v
```

- [ ] **Step 7: Commit**

```bash
uv run --frozen ruff format science-model/src/science_model/source_ref.py science-tool/src/science_tool/graph/errors.py science-model/tests/test_source_ref.py science-tool/tests/test_entity_errors.py
git add science-model/src/science_model/source_ref.py science-tool/src/science_tool/graph/errors.py science-model/tests/test_source_ref.py science-tool/tests/test_entity_errors.py
git commit -m "feat: add SourceRef + EntityIdentityCollisionError for unified load path"
```

---

## Phase 2: Registry

### Task 4: `EntityRegistry` with core + extension registration

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_registry.py`
- Test: `science-tool/tests/test_entity_registry.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_entity_registry.py`:

```python
"""Tests for EntityRegistry — kind → schema dispatch per spec §Model Registry."""
from __future__ import annotations

import pytest

from science_model.entities import (
    DatasetEntity,
    Entity,
    ProjectEntity,
    TaskEntity,
)
from science_tool.graph.entity_registry import (
    EntityRegistry,
    EntityKindShadowError,
    EntityKindAlreadyRegisteredError,
    EntityKindNotRegisteredError,
)


def test_with_core_types_registers_all_core_kinds() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("task") is TaskEntity
    assert registry.resolve("dataset") is DatasetEntity
    # Placeholders (WorkflowRunEntity, ResearchPackageEntity) also registered:
    assert registry.resolve("workflow-run").__name__ == "WorkflowRunEntity"
    assert registry.resolve("research-package").__name__ == "ResearchPackageEntity"


def test_generic_kinds_default_to_project_entity() -> None:
    """Kinds without a dedicated typed entity (concept, hypothesis, topic, question, paper…)
    are registered against ProjectEntity so generic tooling still works."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("concept") is ProjectEntity
    assert registry.resolve("hypothesis") is ProjectEntity
    assert registry.resolve("topic") is ProjectEntity


def test_unknown_kind_raises() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError, match="frobnicator"):
        registry.resolve("frobnicator")


def test_duplicate_core_registration_is_hard_error() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_core_kind("task", TaskEntity)


def test_duplicate_extension_registration_is_hard_error() -> None:
    class ProjectExtA(ProjectEntity):
        pass

    class ProjectExtB(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", ProjectExtA)
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_extension_kind("natural-system:model", ProjectExtB)


def test_extension_cannot_shadow_core() -> None:
    class BogusDataset(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindShadowError, match="dataset"):
        registry.register_extension_kind("dataset", BogusDataset)


def test_resolve_round_trip_extension() -> None:
    class CustomModelEntity(ProjectEntity):
        equation: str = ""

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", CustomModelEntity)
    assert registry.resolve("natural-system:model") is CustomModelEntity


def test_registered_class_must_subclass_entity() -> None:
    class NotAnEntity:
        pass

    registry = EntityRegistry()
    with pytest.raises(TypeError, match="must subclass Entity"):
        registry.register_core_kind("x", NotAnEntity)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_registry.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the registry**

Create `science-tool/src/science_tool/graph/entity_registry.py`:

```python
"""EntityRegistry — explicit kind → schema dispatch.

Per spec §Model Registry and Kind Resolution. Core kinds are registered by
Science; extension kinds are registered by the project. Duplicate
registrations are hard errors; extensions may not shadow core kinds.
"""

from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    Entity,
    ProjectEntity,
    ResearchPackageEntity,
    TaskEntity,
    WorkflowRunEntity,
)


class EntityKindAlreadyRegisteredError(ValueError):
    """Raised when a kind is registered twice (core+core, core+ext, ext+ext)."""


class EntityKindShadowError(ValueError):
    """Raised when an extension tries to register a core kind."""


class EntityKindNotRegisteredError(KeyError):
    """Raised when resolve() is called with an unregistered kind."""


class EntityRegistry:
    """Resolves kind strings to their Entity subclass at load time."""

    def __init__(self) -> None:
        self._core: dict[str, type[Entity]] = {}
        self._extensions: dict[str, type[Entity]] = {}

    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds."""
        r = cls()
        # Typed entities
        r.register_core_kind("task", TaskEntity)
        r.register_core_kind("dataset", DatasetEntity)
        r.register_core_kind("workflow-run", WorkflowRunEntity)
        r.register_core_kind("research-package", ResearchPackageEntity)
        # Generic project kinds that currently have no typed invariants —
        # route to ProjectEntity so they still validate through the subfamily.
        for kind in (
            "concept", "hypothesis", "question", "proposition", "observation",
            "inquiry", "topic", "interpretation", "discussion", "plan",
            "assumption", "transformation", "variable", "method", "experiment",
            "article", "workflow", "workflow-step", "data-package",
            "finding", "story", "paper", "search", "report",
            "validation-report", "unknown", "model", "parameter",
            "spec",
        ):
            r.register_core_kind(kind, ProjectEntity)
        return r

    def register_core_kind(self, kind: str, cls: type[Entity]) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"kind {kind!r} already registered")
        self._core[kind] = cls

    def register_extension_kind(self, kind: str, cls: type[Entity]) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            raise EntityKindShadowError(
                f"extension kind {kind!r} shadows a core kind; use a project-specific prefix"
            )
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"extension kind {kind!r} already registered")
        self._extensions[kind] = cls

    def resolve(self, kind: str) -> type[Entity]:
        if kind in self._core:
            return self._core[kind]
        if kind in self._extensions:
            return self._extensions[kind]
        raise EntityKindNotRegisteredError(f"no schema registered for kind {kind!r}")

    @staticmethod
    def _require_entity_subclass(cls: object) -> None:
        if not (isinstance(cls, type) and issubclass(cls, Entity)):
            raise TypeError(f"registered class must subclass Entity, got {cls!r}")
```

**Note on `model` and `parameter`:** Spec §Implication for current model / parameter says these are NOT core typed entities. We register them against `ProjectEntity` here purely to keep the kitchen-sink snapshot loadable through the new path; Task 12 deletes their source-contract loaders and makes them extension-only. This is a transitional compromise — acceptable because we're routing them through the generic base, not creating new typed classes for them.

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_entity_registry.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/entity_registry.py tests/test_entity_registry.py
git add src/science_tool/graph/entity_registry.py tests/test_entity_registry.py
git commit -m "feat(graph): EntityRegistry with core + extension registration"
```

---

## Phase 3: Storage Adapters

### Task 5: `StorageAdapter` Protocol + package skeleton

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/__init__.py`
- Create: `science-tool/src/science_tool/graph/storage_adapters/base.py`
- Test: `science-tool/tests/test_storage_adapters/test_base.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_storage_adapters/__init__.py` (empty).

Create `science-tool/tests/test_storage_adapters/test_base.py`:

```python
"""Tests for StorageAdapter Protocol — persistence-only contract."""
from __future__ import annotations

from pathlib import Path

from science_model.source_ref import SourceRef
from science_tool.graph.storage_adapters.base import StorageAdapter


class _FakeAdapter(StorageAdapter):
    name = "fake"

    def discover(self, project_root: Path) -> list[SourceRef]:
        return [SourceRef(adapter_name=self.name, path="x.md")]

    def load_raw(self, ref: SourceRef) -> dict[str, object]:
        return {"id": "x:1", "canonical_id": "x:1", "kind": "concept", "title": "X"}


def test_fake_adapter_satisfies_protocol() -> None:
    a = _FakeAdapter()
    refs = a.discover(Path("/tmp"))
    assert refs[0].adapter_name == "fake"
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "concept"


def test_dump_is_optional_raises_not_implemented_by_default() -> None:
    import pytest
    a = _FakeAdapter()
    with pytest.raises(NotImplementedError):
        a.dump(object())  # type: ignore[arg-type]
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_base.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the base**

Create `science-tool/src/science_tool/graph/storage_adapters/__init__.py` (empty).

Create `science-tool/src/science_tool/graph/storage_adapters/base.py`:

```python
"""StorageAdapter base — persistence-only contract.

Per spec §Storage Adapters: an adapter may discover files, parse
storage-specific syntax, and load records into the canonical entity
model family. It may NOT define entity semantics — validation belongs
to the registered entity schema.
"""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Any

from science_model.entities import Entity
from science_model.source_ref import SourceRef


class StorageAdapter(ABC):
    """Abstract base class all storage adapters inherit from.

    Subclasses MUST override `discover()` and `load_raw()`. `dump()` is
    optional during migration; the default raises NotImplementedError.
    """

    name: str  # human-readable adapter name; travels in SourceRef.adapter_name

    def discover(self, project_root: Path) -> list[SourceRef]:
        """Walk `project_root` and return one SourceRef per discoverable record.

        For adapters where one file contains many records (multi-entity
        aggregates), discover() returns one SourceRef per entry — line number
        included where practical. For single-entity files, discover() returns
        one SourceRef per file.
        """
        raise NotImplementedError

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        """Return a registry-dispatchable raw record.

        The returned dict MUST contain a `kind` field (string) so the registry
        can resolve the target schema. All other fields become kwargs to
        `SchemaClass.model_validate(raw)`.
        """
        raise NotImplementedError

    def dump(self, entity: Entity) -> str | dict[str, Any]:
        """Serialize an entity back to this adapter's storage format.

        Optional during migration. Subclasses raise NotImplementedError if
        write support is not yet implemented. Read-only adapters should
        never need dump().
        """
        raise NotImplementedError(f"adapter {self.name!r} does not support write")
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_base.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/storage_adapters/ tests/test_storage_adapters/
git add src/science_tool/graph/storage_adapters/ tests/test_storage_adapters/
git commit -m "feat(storage-adapters): add StorageAdapter base contract"
```

---

### Task 6: `MarkdownAdapter` (single-entity storage)

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/markdown.py`
- Test: `science-tool/tests/test_storage_adapters/test_markdown.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_storage_adapters/test_markdown.py`:

```python
"""Tests for MarkdownAdapter — single-entity markdown + YAML frontmatter."""
from __future__ import annotations

from pathlib import Path

from science_tool.graph.storage_adapters.markdown import MarkdownAdapter


def test_adapter_name() -> None:
    assert MarkdownAdapter().name == "markdown"


def test_discovers_under_default_scan_roots(tmp_path: Path) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nProse.\n',
        encoding="utf-8",
    )
    (tmp_path / "specs").mkdir(parents=True)
    (tmp_path / "specs" / "rq.md").write_text(
        '---\nid: "spec:rq"\ntype: "spec"\ntitle: "RQ"\n---\n',
        encoding="utf-8",
    )
    refs = MarkdownAdapter().discover(tmp_path)
    paths = {r.path for r in refs}
    assert "doc/hypotheses/h1.md" in paths
    assert "specs/rq.md" in paths
    for r in refs:
        assert r.adapter_name == "markdown"


def test_load_raw_returns_dispatchable_dict(tmp_path: Path) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    p = tmp_path / "doc" / "hypotheses" / "h1.md"
    p.write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nBody prose.\n',
        encoding="utf-8",
    )
    adapter = MarkdownAdapter()
    refs = adapter.discover(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["canonical_id"] == "hypothesis:h1"
    assert raw["kind"] == "hypothesis"
    assert raw["title"] == "H1"
    assert raw["content"].startswith("Body prose")
    # `file_path` must be project-relative so downstream users see a stable value:
    assert raw["file_path"] == "doc/hypotheses/h1.md"


def test_custom_scan_roots_honored(tmp_path: Path) -> None:
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom" / "c.md").write_text(
        '---\nid: "concept:c"\ntype: "concept"\ntitle: "C"\n---\n', encoding="utf-8",
    )
    refs = MarkdownAdapter(scan_roots=["custom"]).discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].path == "custom/c.md"


def test_returns_empty_when_no_markdown_files(tmp_path: Path) -> None:
    refs = MarkdownAdapter().discover(tmp_path)
    assert refs == []
```

- [ ] **Step 2: Run failing test**

Expected: ImportError.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/storage_adapters/markdown.py`:

```python
"""MarkdownAdapter — single-entity markdown with YAML frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


class MarkdownAdapter(StorageAdapter):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        # Roots relative to project_root. Defaults mirror the previous MarkdownProvider.
        self._scan_roots = scan_roots or ["doc", "specs", "research/packages"]

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                try:
                    rel_path = str(path.relative_to(project_root))
                except ValueError:
                    rel_path = str(path)
                refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        # ref.path is project-relative; the caller is load_project_sources, which
        # knows the absolute project_root. For unit tests we reconstruct via cwd +
        # ref.path — but load_project_sources passes an absolute path into discover
        # and we resolve relative to it. Simplest: adapter stores no project_root
        # and reads from cwd. Since tests use tmp_path as cwd via monkeypatch OR
        # construct full Path manually, we accept an absolute OR project-relative
        # path and prefer the absolute form when the file exists.
        path = Path(ref.path)
        if not path.is_absolute():
            # Assume cwd is project_root (load_project_sources sets this).
            pass
        fm, body = _parse_markdown(Path(ref.path) if Path(ref.path).exists() else _resolve_relative(ref.path))
        raw: dict[str, Any] = dict(fm)
        raw["content"] = body
        raw["file_path"] = ref.path
        # Normalize `type` → `kind` for registry dispatch while keeping `type` for
        # back-compat with existing Entity code that reads `.type`.
        if "kind" not in raw and "type" in raw:
            raw["kind"] = raw["type"]
        return raw


def _resolve_relative(rel_path: str) -> Path:
    """Resolve a project-relative path against cwd (load_project_sources sets cwd)."""
    return Path.cwd() / rel_path


def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_string). Missing frontmatter → ({}, full_text)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ({}, text)
    try:
        _, fm_raw, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, dict):
        return ({}, body)
    return (fm, body.lstrip("\n"))
```

**Implementation note on path resolution:** `load_project_sources` (Task 10) calls `adapter.discover(project_root)`, which produces SourceRefs with project-relative paths. For `load_raw(ref)`, the adapter needs to resolve relative paths — the cleanest pattern is for adapters to store `project_root` at construction time OR for `load_raw` to accept it. To keep the Protocol narrow (per spec), we use cwd resolution: `load_project_sources` changes into `project_root` before running adapters. If that's not acceptable, change `discover()` to return absolute paths in `SourceRef.path` and document the convention. Pick one and apply consistently; the test fixture uses `tmp_path` which can be passed as absolute.

**Simpler alternative:** have `load_project_sources` pass absolute paths (as `str(project_root / rel_path)`) into SourceRef. Downstream error messages can display `Path(ref.path).relative_to(project_root)` when needed. Adopt this if `cwd` manipulation feels fragile.

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_markdown.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/storage_adapters/markdown.py tests/test_storage_adapters/test_markdown.py
git add src/science_tool/graph/storage_adapters/markdown.py tests/test_storage_adapters/test_markdown.py
git commit -m "feat(storage-adapters): add MarkdownAdapter (single-entity)"
```

---

### Task 7: `AggregateAdapter` (multi-entity + single-type storage)

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/aggregate.py`
- Test: `science-tool/tests/test_storage_adapters/test_aggregate.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_storage_adapters/test_aggregate.py`:

```python
"""Tests for AggregateAdapter — multi-entity and single-type (kind-from-filename) storage."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_tool.graph.storage_adapters.aggregate import AggregateAdapter


def test_adapter_name() -> None:
    assert AggregateAdapter().name == "aggregate"


def test_multi_type_entities_yaml(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({
        "entities": [
            {"canonical_id": "paper:doe2024", "kind": "paper", "title": "Doe 2024"},
            {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"},
        ]
    }), encoding="utf-8")
    a = AggregateAdapter(local_profile="local")
    refs = a.discover(tmp_path)
    assert len(refs) == 2
    raws = [a.load_raw(r) for r in refs]
    kinds = {r["kind"] for r in raws}
    assert kinds == {"paper", "concept"}


def test_single_type_json_kind_from_filename(tmp_path: Path) -> None:
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.json").write_text(json.dumps([
        {"id": "topic:rare-x", "title": "Rare X"},
        {"id": "topic:rare-y", "title": "Rare Y"},
    ]), encoding="utf-8")
    a = AggregateAdapter(local_profile="local")
    refs = a.discover(tmp_path)
    raws = [a.load_raw(r) for r in refs]
    assert all(r["kind"] == "topic" for r in raws)
    ids = {r.get("id") or r.get("canonical_id") for r in raws}
    assert ids == {"topic:rare-x", "topic:rare-y"}


def test_skips_non_dict_entries(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({
        "entities": ["not-a-dict", {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"}, 42],
    }), encoding="utf-8")
    refs = AggregateAdapter(local_profile="local").discover(tmp_path)
    assert len(refs) == 1  # only the one valid dict entry


def test_returns_empty_when_no_aggregate_files(tmp_path: Path) -> None:
    assert AggregateAdapter(local_profile="local").discover(tmp_path) == []


def test_source_ref_line_present_for_multi_entity_entries(tmp_path: Path) -> None:
    """For multi-entity files, SourceRef.line should carry the list index (or YAML line) for actionable errors."""
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({
        "entities": [
            {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"},
            {"canonical_id": "concept:c2", "kind": "concept", "title": "C2"},
        ]
    }), encoding="utf-8")
    refs = AggregateAdapter(local_profile="local").discover(tmp_path)
    assert refs[0].line is not None
    assert refs[1].line is not None
    assert refs[0].line != refs[1].line
```

- [ ] **Step 2: Run failing test** — expect ImportError.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/storage_adapters/aggregate.py`:

```python
"""AggregateAdapter — multi-entity (entities.yaml) and single-type aggregate storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


# Mapping: directory plural → singular kind. Used by single-type aggregate files
# (doc/<plural>/<plural>.{json,yaml}). Mirrors science_model.frontmatter._DIR_TO_TYPE.
_DIR_TO_KIND = {
    "topics": "topic",
    "datasets": "dataset",
    "hypotheses": "hypothesis",
    "questions": "question",
    "concepts": "concept",
    "observations": "observation",
    "findings": "finding",
    "papers": "paper",
    "methods": "method",
    "experiments": "experiment",
    "workflows": "workflow",
    "models": "model",
}


class AggregateAdapter(StorageAdapter):
    """Multi-entity (entities.yaml) + single-type aggregate (doc/<plural>/<plural>.{json,yaml})."""

    name = "aggregate"

    def __init__(self, local_profile: str) -> None:
        # `local_profile` needed to locate knowledge/sources/<profile>/entities.yaml.
        # Task 10 threads this from project config into the adapter constructor.
        self._local_profile = local_profile

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        refs.extend(self._discover_multi_type(project_root))
        refs.extend(self._discover_single_type(project_root))
        return refs

    def _discover_multi_type(self, project_root: Path) -> list[SourceRef]:
        path = project_root / "knowledge" / "sources" / self._local_profile / "entities.yaml"
        if not path.is_file():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return []
        items = data.get("entities") or []
        if not isinstance(items, list):
            return []
        try:
            rel = str(path.relative_to(project_root))
        except ValueError:
            rel = str(path)
        refs: list[SourceRef] = []
        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def _discover_single_type(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for plural, _kind in _DIR_TO_KIND.items():
            for ext in ("json", "yaml"):
                f = project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                items = self._read_list(f)
                try:
                    rel = str(f.relative_to(project_root))
                except ValueError:
                    rel = str(f)
                for idx, raw in enumerate(items):
                    if not isinstance(raw, dict):
                        continue
                    refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        """Load one entry from its aggregate file.

        ref.line is the entry index within the file. For multi-type, `kind` comes
        from the entry itself; for single-type, `kind` comes from the filename
        (via _DIR_TO_KIND). Canonical identity is the `id` / `canonical_id` field.
        """
        assert ref.line is not None, "AggregateAdapter SourceRef must carry line (entry index)"
        path = _resolve_relative_or_absolute(ref.path)
        if path.name == "entities.yaml":
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            items = data.get("entities") or []
            raw = dict(items[ref.line])
            # Kind from entry itself.
        else:
            # Single-type: kind from directory name.
            plural = path.parent.name
            kind = _DIR_TO_KIND.get(plural, "unknown")
            items = self._read_list(path)
            raw = dict(items[ref.line])
            raw.setdefault("kind", kind)
        # Normalize canonical_id from id if needed.
        if "canonical_id" not in raw and "id" in raw:
            raw["canonical_id"] = raw["id"]
        # Preserve file_path so downstream code has it.
        raw.setdefault("file_path", ref.path)
        return raw

    def _read_list(self, path: Path) -> list[Any]:
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, yaml.YAMLError, OSError):
            return []


def _resolve_relative_or_absolute(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (Path.cwd() / path)
```

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_aggregate.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/storage_adapters/aggregate.py tests/test_storage_adapters/test_aggregate.py
git add src/science_tool/graph/storage_adapters/aggregate.py tests/test_storage_adapters/test_aggregate.py
git commit -m "feat(storage-adapters): add AggregateAdapter (multi-entity + single-type)"
```

---

### Task 8: `DatapackageAdapter` (datapackage-backed storage)

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/datapackage.py`
- Test: `science-tool/tests/test_storage_adapters/test_datapackage.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_storage_adapters/test_datapackage.py`:

```python
"""Tests for DatapackageAdapter — promoted datasets (datapackage.yaml IS the entity)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.storage_adapters.datapackage import (
    DatapackageAdapter,
    EntityDatapackageInvalidError,
)


def test_adapter_name() -> None:
    assert DatapackageAdapter().name == "datapackage"


def test_discovers_entity_profile_only(tmp_path: Path) -> None:
    # Non-entity datapackage (silently skipped):
    (tmp_path / "data" / "runtime-only").mkdir(parents=True)
    (tmp_path / "data" / "runtime-only" / "datapackage.yaml").write_text(
        yaml.safe_dump({"profiles": ["science-pkg-runtime-1.0"], "name": "r"}), encoding="utf-8",
    )
    # Entity-profile datapackage:
    (tmp_path / "data" / "myset").mkdir(parents=True)
    (tmp_path / "data" / "myset" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
        "name": "myset",
        "id": "dataset:myset",
        "type": "dataset",
        "title": "My set",
    }), encoding="utf-8")
    refs = DatapackageAdapter().discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].path.endswith("data/myset/datapackage.yaml")


def test_load_raw_extracts_entity_subset(tmp_path: Path) -> None:
    (tmp_path / "data" / "myset").mkdir(parents=True)
    (tmp_path / "data" / "myset" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "myset",
        "id": "dataset:myset",
        "type": "dataset",
        "title": "My set",
        "description": "Set description.",
        "resources": [{"name": "r", "path": "r.csv"}],  # runtime-only
        "origin": "external",
        "access": {"level": "public", "verified": False},
    }), encoding="utf-8")
    adapter = DatapackageAdapter()
    refs = adapter.discover(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "dataset"
    assert raw["canonical_id"] == "dataset:myset"
    assert raw["title"] == "My set"
    assert raw["origin"] == "external"
    # Runtime-only `resources` should NOT be in the raw entity dict:
    assert "resources" not in raw


def test_entity_profile_missing_id_raises(tmp_path: Path) -> None:
    (tmp_path / "data" / "broken").mkdir(parents=True)
    (tmp_path / "data" / "broken" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "broken",
        "title": "Broken",
    }), encoding="utf-8")
    adapter = DatapackageAdapter()
    with pytest.raises(EntityDatapackageInvalidError, match="id"):
        # discover() reads and validates; errors surface here (fail-fast).
        _ = adapter.discover(tmp_path)


def test_walks_results_directory(tmp_path: Path) -> None:
    (tmp_path / "results" / "wf" / "r1" / "out").mkdir(parents=True)
    (tmp_path / "results" / "wf" / "r1" / "out" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "wf-r1",
        "id": "dataset:wf-r1",
        "type": "dataset",
        "title": "WF R1",
    }), encoding="utf-8")
    refs = DatapackageAdapter().discover(tmp_path)
    assert any(r.path.endswith("results/wf/r1/out/datapackage.yaml") for r in refs)


def test_malformed_yaml_silently_skipped(tmp_path: Path) -> None:
    (tmp_path / "data" / "bad").mkdir(parents=True)
    (tmp_path / "data" / "bad" / "datapackage.yaml").write_text("not: valid: yaml: at: all", encoding="utf-8")
    assert DatapackageAdapter().discover(tmp_path) == []
```

- [ ] **Step 2: Run failing test** — expect ImportError.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/storage_adapters/datapackage.py`:

```python
"""DatapackageAdapter — datasets promoted to live as <dir>/datapackage.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


_ENTITY_FIELDS = (
    "id", "canonical_id", "type", "kind", "title", "description", "status",
    "origin", "access", "derivation", "accessions", "datapackage", "local_path",
    "consumed_by", "parent_dataset", "siblings", "ontology_terms", "related",
    "source_refs", "same_as", "aliases",
)


class EntityDatapackageInvalidError(ValueError):
    """Raised when a science-pkg-entity-1.0 datapackage is missing required entity fields."""

    def __init__(self, datapackage_path: str, message: str) -> None:
        super().__init__(f"{datapackage_path}: invalid entity-profile datapackage — {message}")


class DatapackageAdapter(StorageAdapter):
    name = "datapackage"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["data", "results"]

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for dp_path in sorted(root.rglob("datapackage.yaml")):
                try:
                    dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
                except (yaml.YAMLError, OSError):
                    continue  # malformed → can't tell if entity; skip quietly
                profiles = dp.get("profiles") or []
                if "science-pkg-entity-1.0" not in profiles:
                    continue  # non-entity datapackage → ignore
                try:
                    rel_path = str(dp_path.relative_to(project_root))
                except ValueError:
                    rel_path = str(dp_path)
                # Fail-fast validation: entity-profile must carry required fields.
                for field in ("id", "type", "title"):
                    if not dp.get(field):
                        raise EntityDatapackageInvalidError(
                            rel_path,
                            f"missing required entity field {field!r} (science-pkg-entity-1.0 profile present)",
                        )
                refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path) if Path(ref.path).is_absolute() else Path.cwd() / ref.path
        dp = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw = {k: dp[k] for k in _ENTITY_FIELDS if k in dp}
        raw.setdefault("kind", raw.get("type") or "dataset")
        raw.setdefault("canonical_id", raw.get("id", ""))
        raw.setdefault("file_path", ref.path)
        return raw
```

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_datapackage.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/storage_adapters/datapackage.py tests/test_storage_adapters/test_datapackage.py
git add src/science_tool/graph/storage_adapters/datapackage.py tests/test_storage_adapters/test_datapackage.py
git commit -m "feat(storage-adapters): add DatapackageAdapter (promoted-dataset storage)"
```

---

### Task 9: `TaskAdapter` (task-DSL storage)

**Files:**
- Create: `science-tool/src/science_tool/graph/storage_adapters/task.py`
- Test: `science-tool/tests/test_storage_adapters/test_task.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_storage_adapters/test_task.py`:

```python
"""Tests for TaskAdapter — wraps the existing task DSL parser."""
from __future__ import annotations

from pathlib import Path

from science_tool.graph.storage_adapters.task import TaskAdapter


def test_adapter_name() -> None:
    assert TaskAdapter().name == "task"


def test_discovers_tasks_under_tasks_dir(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody.\n",
        encoding="utf-8",
    )
    refs = TaskAdapter().discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].adapter_name == "task"


def test_load_raw_produces_task_entity_shape(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody prose.\n",
        encoding="utf-8",
    )
    a = TaskAdapter()
    refs = a.discover(tmp_path)
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "task"
    assert raw["canonical_id"] == "task:t01"
    assert raw["title"] == "T01"
    assert raw["priority"] == "P1"
    assert raw["status"] == "active"
    assert raw["content"].strip().startswith("Body prose")
```

- [ ] **Step 2: Run failing test** — expect ImportError.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/storage_adapters/task.py`:

```python
"""TaskAdapter — wraps the existing task DSL parser and emits TaskEntity raw records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.tasks import parse_tasks


class TaskAdapter(StorageAdapter):
    name = "task"

    def discover(self, project_root: Path) -> list[SourceRef]:
        tasks_dir = project_root / "tasks"
        if not tasks_dir.is_dir():
            return []
        refs: list[SourceRef] = []
        for path in sorted(tasks_dir.rglob("*.md")):
            try:
                rel = str(path.relative_to(project_root))
            except ValueError:
                rel = str(path)
            parsed = parse_tasks(path)
            for idx, _task in enumerate(parsed):
                refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        assert ref.line is not None, "TaskAdapter SourceRef must carry line (task index)"
        path = Path(ref.path) if Path(ref.path).is_absolute() else Path.cwd() / ref.path
        tasks = parse_tasks(path)
        task = tasks[ref.line]
        return {
            "id": f"task:{task.id}",
            "canonical_id": f"task:{task.id}",
            "kind": "task",
            "type": "task",  # EntityType-compatible
            "title": task.title,
            "project": task.project or "",
            "priority": task.priority,
            "status": task.status,
            "blocked_by": task.blocked_by,
            "related": task.related,
            "group": task.group,
            "aspects": task.aspects,
            "artifacts": task.artifacts,
            "findings": task.findings,
            "created": task.created,
            "completed": task.completed,
            "content": task.description,
            "content_preview": task.description[:200] if task.description else "",
            "file_path": ref.path,
            "ontology_terms": [],
            "source_refs": [],
        }
```

- [ ] **Step 4: Run tests**

```bash
uv run --frozen pytest tests/test_storage_adapters/test_task.py -v
```

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/storage_adapters/task.py tests/test_storage_adapters/test_task.py
git add src/science_tool/graph/storage_adapters/task.py tests/test_storage_adapters/test_task.py
git commit -m "feat(storage-adapters): add TaskAdapter wrapping task DSL parser"
```

---

## Phase 4: Integration Cutover

### Task 10: Cut over `load_project_sources` to registry + adapters + identity table

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Modify: `science-tool/tests/test_load_project_sources_regression.py` (projection helper)
- Modify: `science-tool/tests/fixtures/spec_y_kitchen_sink/snapshot.json` (regenerate)
- Test: `science-tool/tests/test_load_project_sources_unified.py` (new)

This is the LOAD-BEARING change. The old flow (SourceEntity + EntityResolver + providers) is replaced with the new flow (Entity + EntityRegistry + StorageAdapters + global identity table).

- [ ] **Step 1: Write the new end-to-end test**

Create `science-tool/tests/test_load_project_sources_unified.py`:

```python
"""End-to-end tests for the unified load flow (registry + adapters)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entities import (
    DatasetEntity,
    Entity,
    ProjectEntity,
    TaskEntity,
)
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.sources import load_project_sources


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\n",
        encoding="utf-8",
    )


def test_load_produces_typed_entity_instances(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n', encoding="utf-8",
    )
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    # Markdown hypothesis → ProjectEntity
    assert isinstance(by_id["hypothesis:h1"], ProjectEntity)
    assert not isinstance(by_id["hypothesis:h1"], TaskEntity)
    # Task DSL → TaskEntity
    assert isinstance(by_id["task:t01"], TaskEntity)
    assert by_id["task:t01"].priority == "P1"


def test_load_produces_dataset_entity_for_datapackage(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "data" / "ds1").mkdir(parents=True)
    (tmp_path / "data" / "ds1" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "ds1",
        "id": "dataset:ds1",
        "type": "dataset",
        "title": "DS1",
        "origin": "external",
        "access": {"level": "public", "verified": False},
    }), encoding="utf-8")
    sources = load_project_sources(tmp_path)
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:ds1")
    assert isinstance(ds, DatasetEntity)
    assert ds.origin == "external"


def test_global_identity_collision_across_adapters(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\norigin: "external"\naccess: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "x",
        "id": "dataset:x",
        "type": "dataset",
        "title": "X dp",
        "origin": "external",
        "access": {"level": "public", "verified": False},
    }), encoding="utf-8")
    with pytest.raises(EntityIdentityCollisionError, match="dataset:x"):
        load_project_sources(tmp_path)


def test_all_entities_inherit_from_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n', encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    assert all(isinstance(e, Entity) for e in sources.entities)
```

- [ ] **Step 2: Run failing test** — expect many failures (new flow not yet wired).

- [ ] **Step 3: Rewrite `load_project_sources`**

In `science-tool/src/science_tool/graph/sources.py`:

a) Replace the existing `load_project_sources` body with:

```python
from pathlib import Path

from science_model.entities import Entity
from science_model.source_ref import SourceRef

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.storage_adapters.aggregate import AggregateAdapter
from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter


def default_adapters(local_profile: str) -> list[StorageAdapter]:
    """Return the Science-core adapter set. Project extensions may add more."""
    return [
        MarkdownAdapter(),
        AggregateAdapter(local_profile=local_profile),
        DatapackageAdapter(),
        TaskAdapter(),
    ]


def load_project_sources(project_root: Path) -> ProjectSources:
    """Load all project entities through the unified registry + adapters flow."""
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    local_profile = profiles.local
    # Ontology catalogs: keep existing loader for now (out of scope for this plan).
    declared_ontologies: list[str] = list(config.get("ontologies") or [])  # type: ignore[union-attr]
    ontology_catalogs = load_catalogs_for_names(declared_ontologies) if declared_ontologies else []

    # Changing cwd lets adapters resolve relative SourceRef paths simply.
    # Alternative: thread project_root into every load_raw call; rejected to keep
    # StorageAdapter Protocol narrow per spec.
    import os
    prev_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        registry = EntityRegistry.with_core_types()
        adapters = default_adapters(local_profile=local_profile)
        identity_table: dict[str, SourceRef] = {}
        entities: list[Entity] = []
        for adapter in adapters:
            for ref in adapter.discover(project_root):
                raw = adapter.load_raw(ref)
                kind = raw.get("kind")
                if not isinstance(kind, str):
                    raise ValueError(f"{ref}: raw record missing string 'kind' field")
                schema = registry.resolve(kind)
                # Pydantic validates into the right typed class.
                entity = schema.model_validate(raw)
                existing = identity_table.get(entity.canonical_id)
                if existing is not None:
                    raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                identity_table[entity.canonical_id] = ref
                entities.append(entity)
    finally:
        os.chdir(prev_cwd)

    entities.sort(key=lambda e: e.canonical_id)
    # Keep existing relations / bindings / manual_aliases loaders untouched:
    relations = _load_structured_relations(project_root, local_profile=local_profile)
    relations.sort(key=lambda r: (r.graph_layer, r.subject, r.predicate, r.object))
    bindings = _load_binding_sources(project_root, local_profile=local_profile)
    bindings.sort(key=lambda b: (b.model, b.parameter, b.source_path))

    return ProjectSources(
        project_name=str(config["name"]),
        project_root=str(project_root),
        profiles=profiles,
        entities=entities,  # now list[Entity] (typed subclasses)
        relations=relations,
        bindings=bindings,
        manual_aliases=_load_manual_aliases(project_root, local_profile=local_profile),
        ontology_catalogs=ontology_catalogs,
    )
```

b) Update `ProjectSources` to hold `entities: list[Entity]` instead of `list[SourceEntity]`:

```python
class ProjectSources(BaseModel):
    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[Entity]  # was list[SourceEntity]
    # rest unchanged
```

c) Remove the now-unused `EntityResolver`, `EntityProvider` imports and the old `entities.extend(...)` calls for `_load_task_entities`, `_load_model_sources`, `_load_parameter_sources`. Those are deleted in Task 11 (this task focuses on the cutover; the file gets cleaned up in Task 11).

- [ ] **Step 4: Regenerate the regression snapshot**

The kitchen-sink snapshot stored SourceEntity shape. The entity classes now differ in field layout (dataset fields moved to DatasetEntity, reasoning fields moved to ProjectEntity). Update the projection helper AND regenerate the baseline:

Modify `tests/test_load_project_sources_regression.py` `_project_for_snapshot()`:

```python
def _project_for_snapshot(entities: list) -> list[dict]:
    """Project to a stable subset comparable across schema changes."""
    excluded = {
        # Fields whose presence depends on class (flatten across subclasses):
        "provider",  # old Spec Y field; gone after this task
        # Spec-Y-era content_preview; kept for compat but not load-bearing:
    }
    projected: list[dict] = []
    for e in entities:
        d = e.model_dump()
        projected.append({k: v for k, v in d.items() if k not in excluded})
    projected.sort(key=lambda d: d.get("canonical_id", ""))
    return projected
```

Regenerate `tests/fixtures/spec_y_kitchen_sink/snapshot.json`:

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/unified-entity-model/science-tool
uv run --frozen python -c "
import json
from pathlib import Path
from science_tool.graph.sources import load_project_sources
from tests.test_load_project_sources_regression import _project_for_snapshot

FIXTURE = Path('tests/fixtures/spec_y_kitchen_sink')
SNAPSHOT = FIXTURE / 'snapshot.json'
sources = load_project_sources(FIXTURE)
SNAPSHOT.write_text(json.dumps(_project_for_snapshot(sources.entities), indent=2) + chr(10))
print(f'wrote {len(sources.entities)} entities to {SNAPSHOT}')
"
```

Expected: `wrote 5 entities to ...`. Inspect the diff vs the old snapshot — verify only expected structural changes (field-location shifts driven by the hierarchy migration).

- [ ] **Step 5: Run the full test suite**

```bash
uv run --frozen pytest -q
```

Many tests will fail because they construct `SourceEntity(...)` or assert `isinstance(..., SourceEntity)`. **Expected — those tests migrate in Task 11.** Verify at minimum:
- `tests/test_load_project_sources_regression.py` — PASSES against the new snapshot
- `tests/test_load_project_sources_unified.py` — PASSES
- `tests/test_storage_adapters/` — all PASS
- `tests/test_entity_registry.py` — PASS

- [ ] **Step 6: Commit (big commit — the architectural hinge)**

```bash
uv run --frozen ruff format src/science_tool/graph/sources.py tests/
git add src/science_tool/graph/sources.py tests/test_load_project_sources_unified.py tests/test_load_project_sources_regression.py tests/fixtures/spec_y_kitchen_sink/snapshot.json
git commit -m "feat(graph): cut over load_project_sources to EntityRegistry + adapters

Replaces the Spec Y EntityProvider+EntityResolver+SourceEntity flow with
the unified-model flow per the replacement spec:
- EntityRegistry.with_core_types() dispatches kind -> schema
- StorageAdapter.discover()/load_raw() per adapter (markdown, aggregate,
  datapackage, task)
- Pydantic validates raw records into Entity / ProjectEntity / DatasetEntity
  / TaskEntity subclasses
- Global identity table detects collisions across adapters, raising
  EntityIdentityCollisionError with both SourceRefs

Snapshot regenerated: field layout shifts per the new hierarchy (dataset
fields moved to DatasetEntity, reasoning fields to ProjectEntity). Projection
helper updated accordingly.

Many tests still reference SourceEntity — migrated in Task 11."
```

---

## Phase 5: Cleanup

### Task 11: Delete Spec Y artifacts + migrate downstream consumers

**Files:**
- Delete: `science-tool/src/science_tool/graph/entity_providers/` (whole directory)
- Delete: `science-tool/src/science_tool/graph/source_types.py`
- Modify: many callers that reference `SourceEntity`
- Delete: `science-tool/tests/test_entity_providers/` (whole directory — obsoleted by storage-adapter tests)
- Delete: `science-tool/tests/test_provider_migration.py`, `test_load_project_sources_global_collision.py` (replaced by unified tests)
- Delete: `science-tool/tests/test_source_types.py`
- Modify: `science-tool/tests/test_load_project_sources_regression.py`, any test constructing SourceEntity directly

- [ ] **Step 1: Find all SourceEntity references**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/unified-entity-model
grep -rn "SourceEntity\|entity_providers\|EntityProvider\|EntityResolver\|EntityRecord\|_normalize_record\|source_types" science-tool/src/ science-tool/tests/ | grep -v __pycache__ > /tmp/sources-entity-refs.txt
wc -l /tmp/sources-entity-refs.txt
head -30 /tmp/sources-entity-refs.txt
```

Expected: significant list (Task 4.1 of Spec Y reported 17+ files touched `SourceEntity`).

- [ ] **Step 2: Migrate non-test callers**

For each non-test file referencing `SourceEntity` (grep output above), replace with `Entity` (import from `science_model.entities`). The Spec Y `SourceEntity.provider` field is gone; callers that read `.provider` must be updated to read `SourceRef.adapter_name` via identity-table lookup OR the field is removed from their code (if not load-bearing).

Likely touched: `science-tool/src/science_tool/graph/health.py`, `science-tool/src/science_tool/graph/store.py`, `science-tool/src/science_tool/cli.py`, possibly others. For each:
- Replace `SourceEntity` with `Entity` in type hints.
- Remove references to `entity.provider` — the caller never actually needed provider attribution in v1, or it did and we thread it via a separate identity-table param.

If the grep reveals `ProjectSources.entities` consumers assuming specific fields (e.g., `entity.blocked_by`), confirm those fields exist on `Entity` or on `ProjectEntity` and do an `isinstance(entity, ProjectEntity)` check before access.

- [ ] **Step 3: Migrate test callers**

Tests constructing `SourceEntity(...)` directly: replace with the appropriate typed class (usually `ProjectEntity(...)` unless the test is dataset- or task-specific).

For example, `tests/test_ontology_suggest.py`:

```python
# BEFORE
from science_tool.graph.source_types import SourceEntity
def _entity(cid: str) -> SourceEntity:
    return SourceEntity(canonical_id=cid, kind="concept", ..., provider="markdown")

# AFTER
from science_model.entities import ProjectEntity, EntityType
def _entity(cid: str) -> ProjectEntity:
    return ProjectEntity(
        id=cid, canonical_id=cid, type=EntityType.CONCEPT, title=cid, project="test",
        ontology_terms=[], related=[], source_refs=[], content_preview="", file_path="",
    )
```

- [ ] **Step 4: Delete obsolete files**

```bash
rm -rf science-tool/src/science_tool/graph/entity_providers/
rm science-tool/src/science_tool/graph/source_types.py
rm -rf science-tool/tests/test_entity_providers/
rm science-tool/tests/test_provider_migration.py
rm science-tool/tests/test_load_project_sources_global_collision.py
rm science-tool/tests/test_source_types.py
```

- [ ] **Step 5: Verify**

```bash
uv run --frozen pytest -q
uv run --frozen ruff check .
```

Expected: 100% of the suite passes. `ruff` clean. Snapshot regression stays green.

- [ ] **Step 6: Commit**

```bash
git add -A  # captures deletions + migrations
git commit -m "refactor: delete Spec Y entity_providers + migrate SourceEntity callers to Entity

Removes:
- graph/entity_providers/ (replaced by graph/storage_adapters/)
- graph/source_types.py (SourceEntity absorbed into Entity hierarchy)
- tests/test_entity_providers/ (replaced by tests/test_storage_adapters/)
- tests/test_provider_migration.py, test_load_project_sources_global_collision.py,
  test_source_types.py (replaced by tests/test_load_project_sources_unified.py)

All downstream consumers now hold Entity / ProjectEntity / typed-entity
instances instead of SourceEntity. provider-attribution moves from an
entity field to SourceRef from the identity table."
```

---

### Task 12: Remove `model` / `parameter` from core; add extension path example

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py` (delete `_load_model_sources`, `_load_parameter_sources`)
- Modify: `science-tool/src/science_tool/graph/entity_registry.py` (remove `"model"` / `"parameter"` from core kinds)
- Modify: `science-model/src/science_model/source_contracts.py` (keep for now; add deprecation note)
- Create: `science-tool/tests/test_extension_registration.py` (demonstrates extension path)
- Delete or move tests that depend on core model/parameter loading

- [ ] **Step 1: Write failing test for extension path**

Create `science-tool/tests/test_extension_registration.py`:

```python
"""Demonstrate and test the project-extension registration path for custom kinds."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entities import ProjectEntity
from science_tool.graph.entity_registry import (
    EntityKindNotRegisteredError,
    EntityKindShadowError,
    EntityRegistry,
)


class _CustomModelEntity(ProjectEntity):
    equation: str = ""
    parameters: list[str] = []


def test_extension_kind_cannot_shadow_core() -> None:
    r = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindShadowError):
        r.register_extension_kind("dataset", _CustomModelEntity)


def test_extension_kind_rejected_when_not_registered(tmp_path: Path) -> None:
    """A project using a not-yet-registered extension kind fails fast."""
    (tmp_path / "science.yaml").write_text(
        "name: x\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8",
    )
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    (tmp_path / "knowledge" / "sources" / "local" / "entities.yaml").write_text(
        yaml.safe_dump({
            "entities": [{"canonical_id": "natural-system:model:x", "kind": "natural-system:model", "title": "X"}],
        }),
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    with pytest.raises(EntityKindNotRegisteredError):
        load_project_sources(tmp_path)


def test_extension_kind_load_path_round_trip() -> None:
    """Demonstrate how a project project registers its extension and loads."""
    r = EntityRegistry.with_core_types()
    r.register_extension_kind("natural-system:model", _CustomModelEntity)
    resolved = r.resolve("natural-system:model")
    assert resolved is _CustomModelEntity
```

- [ ] **Step 2: Run failing test** — expect `model` / `parameter` still in the core kind list or extension not-registered behavior not exercised yet.

- [ ] **Step 3: Remove model/parameter from core**

a) In `science-tool/src/science_tool/graph/entity_registry.py` `with_core_types()`, remove `"model"` and `"parameter"` from the generic kinds list.

b) In `science-tool/src/science_tool/graph/sources.py`, delete the `_load_model_sources` and `_load_parameter_sources` calls and the helper functions themselves. Remove related imports (`ModelSource`, `ParameterSource`).

c) Any tests that depended on core model/parameter loading (`tests/test_graph_build_strict.py` or similar): migrate them to register `model`/`parameter` as extension kinds in a local test registry, OR mark them as "extension-path demonstrations" and route them through `register_extension_kind`. If a test was purely verifying the OLD core behavior and is no longer meaningful, delete it.

d) In `science-model/src/science_model/source_contracts.py`: add a module docstring note that the models here (`ModelSource`, `ParameterSource`, `BindingSource`) are NOT core typed entities per the replacement spec. Keep the classes (they may still be useful as extension-layer helpers), but discourage direct use from science-core.

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_extension_registration.py -v
uv run --frozen pytest -q
```

Expected: new tests PASS. Any previously-passing test that relied on core `model` / `parameter` loading either fails with `EntityKindNotRegisteredError` (if the project entity records use those kinds) or needs migration as above.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/ tests/
git add -A
git commit -m "refactor: remove model/parameter from core kinds; add extension registration demo

Per spec §Implication for current model / parameter: these are not core
Science typed entities. Core loading no longer handles them; projects that
need them register extension kinds via EntityRegistry.register_extension_kind.

Source contracts module (ModelSource/ParameterSource/BindingSource) is kept
as an extension-layer helper but is no longer imported from graph/sources.py."
```

---

### Task 13: Final sweep — lint, type, test, docs

**Files:**
- No new code; touches: `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (update forward reference), README-style touches if needed.

- [ ] **Step 1: Ruff**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/unified-entity-model/science-tool
uv run --frozen ruff check . --fix
uv run --frozen ruff format .
cd ../science-model
uv run --frozen ruff check . --fix
uv run --frozen ruff format .
```

Commit auto-fixes if any:

```bash
cd ..
git add -A
git commit -m "chore: ruff autofix + format after unified entity model migration" || true
```

- [ ] **Step 2: Pyright**

```bash
cd science-tool && uv run --frozen pyright 2>&1 | tail -3
cd ../science-model && uv run --frozen pyright 2>&1 | tail -3
```

Compare to main's pre-migration count. New errors introduced by this plan must be fixed OR have a `# type: ignore[...]` justified in a code comment. Pre-existing errors listed as out-of-scope remain out-of-scope.

- [ ] **Step 3: Full test sweep**

```bash
cd science-tool && uv run --frozen pytest -q
cd ../science-model && uv run --frozen pytest -q
```

Expected: all green.

- [ ] **Step 4: Regression snapshot sanity check**

```bash
cd science-tool && uv run --frozen pytest tests/test_load_project_sources_regression.py -v
```

Expected: PASS. The snapshot was regenerated in Task 10 and has been stable through Tasks 11 and 12.

- [ ] **Step 5: Update spec cross-references**

Verify `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` forward-reference still resolves to the replacement spec (`docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`). No commit needed if already correct.

Optionally update the replacement spec with an "Implementation" section pointing at this plan (`docs/specs/plans/2026-04-20-unified-entity-model.md`).

- [ ] **Step 6: Commit any doc updates**

```bash
git add docs/
git commit -m "docs: cross-reference unified entity model implementation plan" || true
```

- [ ] **Step 7: Finish the branch**

Invoke `superpowers:finishing-a-development-branch` to merge / PR the work.

---

## Self-review (run mentally before declaring done)

**Spec coverage (from `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`):**

- §Canonical Base Model — `Entity` with cross-cutting fields → Task 1.
- §Entity Subfamilies — `ProjectEntity` / `DomainEntity` → Task 1.
- §Typed Entity Model — `TaskEntity` / `DatasetEntity` / `WorkflowRunEntity` / `ResearchPackageEntity` → Task 2.
- §Model Registry — `EntityRegistry.with_core_types()` + `register_extension_kind` + shadow/conflict errors → Task 4.
- §Project Extension Mechanism — demonstrated in Task 12 test.
- §Storage Model (three patterns: single-entity, multi-entity, datapackage-backed) → Tasks 6, 7, 8.
- §Storage Adapters — narrow Protocol (`discover`/`load_raw`/`dump?`) → Task 5.
- §Task adapter plan — TaskAdapter wraps parse_tasks → Task 9.
- §Read / Write Architecture — unified flow → Task 10.
- §Collision mechanism — global identity table with `EntityIdentityCollisionError` → Tasks 3, 10.
- §Source Location — `SourceRef` model → Task 3.
- §Identity and Generic Behavior — Entity base contract preserved → Task 1.
- §Datapackage-backed Entities — runtime-only fields stay in datapackage layer → Task 8 (`_ENTITY_FIELDS` allowlist).
- §Migration — tasks/datasets/markdown all migrate → Tasks 2, 10, 11.
- §Implication for model / parameter — removed from core → Task 12.
- §Collision and Validation Policy — construction-time validation via registered schema → Task 10.
- §Compatibility with Rev 2.2 — DatasetEntity keeps `_enforce_origin_block_invariants` → Task 2.

**Out of scope (per spec non-goals):**
- Graph store redesign — not touched.
- RDF materialization — not touched.
- Query API — not touched.
- Caching, watching, index persistence — not touched.

**Placeholder scan:** no "TBD" / "TODO" / "implement later" strings in the plan. Each step has real code.

**Type consistency:** `Entity`, `ProjectEntity`, `DomainEntity`, `TaskEntity`, `DatasetEntity`, `WorkflowRunEntity`, `ResearchPackageEntity`, `SourceRef`, `EntityIdentityCollisionError`, `EntityRegistry`, `StorageAdapter`, `MarkdownAdapter`, `AggregateAdapter`, `DatapackageAdapter`, `TaskAdapter`, `EntityKindNotRegisteredError`, `EntityKindAlreadyRegisteredError`, `EntityKindShadowError`, `EntityDatapackageInvalidError` — all referenced consistently.

**Known risks:**

1. **`extra="forbid"` on `ProjectEntity`** in Task 1 may cause existing science-model tests to fail because the current `Entity` accepts dataset-specific fields. The plan notes this and offers a "defer forbid until Task 2" fallback.
2. **cwd manipulation in `load_project_sources`** (Task 10) is pragmatic but fragile. If rejected, switch to absolute paths in `SourceRef.path` and update adapters accordingly; this is a one-line change per adapter.
3. **`EntityType` enum vs `kind: str`** — the spec uses `kind: str` for registry dispatch, but `Entity.type` is still `EntityType` (enum). The adapters' `load_raw()` returns `raw["kind"]` as a string derived from `raw["type"]`. During validation, Pydantic coerces. If the enum is too strict (rejects unknown kinds), Task 4 may need to relax `Entity.type` to `str` OR extend the enum dynamically. Flag as a potential Task 2 adjustment if it surfaces.
4. **The regression snapshot regeneration in Task 10** is a trust point — the diff between the old and new snapshot must be reviewed carefully. The commit message documents expected structural shifts; anything unexpected must be explained before committing.

---

## Execution Handoff

Plan complete and saved to `docs/specs/plans/2026-04-20-unified-entity-model.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using `executing-plans`, batch execution with checkpoints

Which approach?

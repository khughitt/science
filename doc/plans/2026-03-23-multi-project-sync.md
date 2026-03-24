# Multi-Project Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable cross-project knowledge model alignment and content propagation via a shared registry profile, auto-registration, and a `/sync` command.

**Architecture:** A new `registry/` module in `science-tool` manages a global config (`~/.config/science/`) containing a project list, sync state, and a cross-project profile (entity+relation index). The `science-model` package gains `SyncSource` provenance and dynamic profile loading. Sync collects project sources, aligns entities/relations, promotes shared types, and propagates content-bearing entities across projects.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, Click (CLI), pytest (testing). Existing packages: `science-model` (models), `science-tool` (CLI + graph ops).

**Spec:** `doc/specs/2026-03-23-multi-project-sync-design.md`

---

## File Structure

### New files

```
science-model/src/science_model/sync.py                    # SyncSource model
science-model/tests/test_sync_source.py                    # SyncSource + Entity integration tests

science-tool/src/science_tool/registry/__init__.py         # Package init, re-exports
science-tool/src/science_tool/registry/config.py           # GlobalConfig, RegisteredProject, ensure_registered()
science-tool/src/science_tool/registry/state.py            # SyncState, ProjectSyncState, entity_hash()
science-tool/src/science_tool/registry/index.py            # RegistryEntity, RegistryRelation, index I/O
science-tool/src/science_tool/registry/matching.py         # Tiered entity matching (exact/alias/ontology/fuzzy)
science-tool/src/science_tool/registry/sync.py             # Sync orchestrator (phases 1-5)
science-tool/src/science_tool/registry/propagation.py      # Content propagation + markdown writer
science-tool/src/science_tool/registry/checks.py           # Proactive registry checks (check_registry)

science-tool/tests/test_registry_config.py                 # Global config + registration tests
science-tool/tests/test_registry_state.py                  # Sync state + entity hash tests
science-tool/tests/test_registry_index.py                  # Registry index I/O tests
science-tool/tests/test_registry_matching.py               # Entity matching tests
science-tool/tests/test_registry_sync.py                   # Sync orchestrator integration tests
science-tool/tests/test_registry_propagation.py            # Propagation tests
science-tool/tests/test_registry_checks.py                 # Proactive check tests
science-tool/tests/test_sync_cli.py                        # CLI command tests

commands/sync.md                                           # /science:sync command prompt
```

### Modified files

```
science-model/src/science_model/entities.py                # Add RELATION_CLAIM to EntityType
science-model/src/science_model/frontmatter.py             # Parse sync_source from frontmatter
science-model/src/science_model/profiles/__init__.py       # Add load_cross_project_profile()
science-model/src/science_model/__init__.py                # Re-export SyncSource

science-tool/src/science_tool/graph/sources.py             # Dynamic _known_kinds(), cross-project profile resolution, add tags to SourceEntity
science-tool/src/science_tool/cli.py                       # New sync command group, proactive checks in graph build

commands/status.md                                         # Add sync staleness nudge
commands/next-steps.md                                     # Add sync staleness nudge
commands/create-graph.md                                   # Add proactive check guidance
commands/update-graph.md                                   # Add proactive check guidance
```

---

## Task 1: Add `RELATION_CLAIM` to `EntityType` and `SyncSource` model

**Files:**
- Modify: `science-model/src/science_model/entities.py:39` (add enum member before UNKNOWN)
- Create: `science-model/src/science_model/sync.py`
- Modify: `science-model/src/science_model/__init__.py`
- Modify: `science-model/src/science_model/frontmatter.py:66-85`
- Test: `science-model/tests/test_entities.py`
- Test: `science-model/tests/test_sync_source.py`
- Test: `science-model/tests/test_frontmatter.py`

- [ ] **Step 1: Write test for `RELATION_CLAIM` enum member**

In `science-model/tests/test_entities.py`, add:

```python
def test_relation_claim_entity_type():
    assert EntityType.RELATION_CLAIM == "relation_claim"
    assert EntityType("relation_claim") == EntityType.RELATION_CLAIM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-model && uv run --frozen pytest tests/test_entities.py::test_relation_claim_entity_type -v`
Expected: FAIL — `AttributeError: RELATION_CLAIM`

- [ ] **Step 3: Add `RELATION_CLAIM` to `EntityType`**

In `science-model/src/science_model/entities.py`, add before `UNKNOWN`:

```python
    RELATION_CLAIM = "relation_claim"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-model && uv run --frozen pytest tests/test_entities.py::test_relation_claim_entity_type -v`
Expected: PASS

- [ ] **Step 5: Write `SyncSource` model and tests**

Create `science-model/src/science_model/sync.py`:

```python
"""Provenance model for cross-project sync-propagated entities."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SyncSource(BaseModel):
    """Provenance marker for sync-propagated entities."""

    project: str
    entity_id: str
    sync_date: date
```

Create `science-model/tests/test_sync_source.py`:

```python
from datetime import date

from science_model.sync import SyncSource


def test_sync_source_round_trip():
    ss = SyncSource(project="aging-clocks", entity_id="question:q4-tp53", sync_date=date(2026, 3, 23))
    d = ss.model_dump()
    assert d == {"project": "aging-clocks", "entity_id": "question:q4-tp53", "sync_date": date(2026, 3, 23)}
    assert SyncSource.model_validate(d) == ss
```

- [ ] **Step 6: Run SyncSource test**

Run: `cd science-model && uv run --frozen pytest tests/test_sync_source.py -v`
Expected: PASS

- [ ] **Step 7: Add `sync_source` field to `Entity` model**

In `science-model/src/science_model/entities.py`, add import and field:

```python
from science_model.sync import SyncSource
```

Add field to `Entity` class (after `aliases`):

```python
    sync_source: SyncSource | None = None
```

- [ ] **Step 8: Write test for Entity with sync_source**

In `science-model/tests/test_sync_source.py`, add:

```python
from science_model.entities import Entity, EntityType


def test_entity_with_sync_source():
    e = Entity(
        id="question:q-tp53-methylation",
        type=EntityType.QUESTION,
        title="TP53 methylation question",
        project="protein-folding",
        tags=["sync-propagated"],
        ontology_terms=[],
        related=["gene:tp53"],
        source_refs=[],
        content_preview="Propagated question",
        file_path="doc/sync/q-tp53-methylation.md",
        sync_source=SyncSource(
            project="aging-clocks",
            entity_id="question:q4-tp53-methylation-age",
            sync_date=date(2026, 3, 23),
        ),
    )
    assert e.sync_source is not None
    assert e.sync_source.project == "aging-clocks"
    d = e.model_dump()
    e2 = Entity.model_validate(d)
    assert e2.sync_source == e.sync_source


def test_entity_without_sync_source_defaults_none():
    e = Entity(
        id="question:q1",
        type=EntityType.QUESTION,
        title="Local question",
        project="p",
        tags=[],
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/q1.md",
    )
    assert e.sync_source is None
```

- [ ] **Step 9: Run all sync_source tests**

Run: `cd science-model && uv run --frozen pytest tests/test_sync_source.py -v`
Expected: PASS

- [ ] **Step 10: Add sync_source parsing to frontmatter.py**

In `science-model/src/science_model/frontmatter.py`, add import:

```python
from science_model.sync import SyncSource
```

In `parse_entity_file()`, after `datasets=fm.get("datasets"),` add:

```python
        sync_source=_parse_sync_source(fm.get("sync_source")),
```

Add helper function:

```python
def _parse_sync_source(raw: dict | None) -> SyncSource | None:
    if not isinstance(raw, dict):
        return None
    project = raw.get("project")
    entity_id = raw.get("entity_id")
    sync_date = raw.get("sync_date")
    if not project or not entity_id or not sync_date:
        return None
    return SyncSource(project=str(project), entity_id=str(entity_id), sync_date=_coerce_date(sync_date))
```

- [ ] **Step 11: Write test for frontmatter sync_source parsing**

In `science-model/tests/test_frontmatter.py`, add (or create if needed):

```python
def test_parse_entity_file_with_sync_source(tmp_path):
    config = tmp_path / "science.yaml"
    config.write_text("name: test-project\n", encoding="utf-8")
    doc = tmp_path / "doc" / "sync"
    doc.mkdir(parents=True)
    f = doc / "q-from-other.md"
    f.write_text(
        "---\n"
        'id: "question:q-from-other"\n'
        "type: question\n"
        'title: "Propagated question"\n'
        "sync_source:\n"
        '  project: "aging-clocks"\n'
        '  entity_id: "question:q4-tp53"\n'
        '  sync_date: "2026-03-23"\n'
        "---\n"
        "Body text.\n",
        encoding="utf-8",
    )
    from science_model.frontmatter import parse_entity_file

    entity = parse_entity_file(f, project_slug="test-project")
    assert entity is not None
    assert entity.sync_source is not None
    assert entity.sync_source.project == "aging-clocks"
    assert entity.sync_source.entity_id == "question:q4-tp53"
```

- [ ] **Step 12: Run frontmatter test**

Run: `cd science-model && uv run --frozen pytest tests/test_frontmatter.py::test_parse_entity_file_with_sync_source -v`
Expected: PASS

- [ ] **Step 13: Re-export SyncSource from package __init__**

In `science-model/src/science_model/__init__.py`, add `SyncSource` to imports and `__all__`.

- [ ] **Step 14: Run full science-model test suite**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: All tests PASS

- [ ] **Step 15: Commit**

```bash
git add science-model/src/science_model/entities.py \
       science-model/src/science_model/sync.py \
       science-model/src/science_model/frontmatter.py \
       science-model/src/science_model/__init__.py \
       science-model/tests/test_entities.py \
       science-model/tests/test_sync_source.py \
       science-model/tests/test_frontmatter.py
git commit -m "feat(science-model): add RELATION_CLAIM type and SyncSource provenance model"
```

---

## Task 2: Global Config & Auto-Registration

**Files:**
- Create: `science-tool/src/science_tool/registry/__init__.py`
- Create: `science-tool/src/science_tool/registry/config.py`
- Test: `science-tool/tests/test_registry_config.py`

- [ ] **Step 1: Write tests for GlobalConfig models and I/O**

Create `science-tool/tests/test_registry_config.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.registry.config import (
    GlobalConfig,
    RegisteredProject,
    SyncSettings,
    ensure_registered,
    load_global_config,
    save_global_config,
)


def test_global_config_defaults():
    cfg = GlobalConfig()
    assert cfg.sync.stale_after_days == 7
    assert cfg.projects == []


def test_global_config_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    cfg = GlobalConfig(
        sync=SyncSettings(stale_after_days=14),
        projects=[
            RegisteredProject(path="/home/user/proj-a", name="proj-a", registered=date(2026, 3, 15)),
        ],
    )
    save_global_config(cfg, config_path)
    loaded = load_global_config(config_path)
    assert loaded.sync.stale_after_days == 14
    assert len(loaded.projects) == 1
    assert loaded.projects[0].name == "proj-a"


def test_load_global_config_missing_file(tmp_path):
    cfg = load_global_config(tmp_path / "missing.yaml")
    assert cfg.projects == []
    assert cfg.sync.stale_after_days == 7


def test_ensure_registered_adds_new_project(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(
        project_root=Path("/home/user/proj-a"),
        project_name="proj-a",
        config_path=config_path,
    )
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 1
    assert cfg.projects[0].name == "proj-a"
    assert cfg.projects[0].path == "/home/user/proj-a"


def test_ensure_registered_idempotent(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 1


def test_ensure_registered_multiple_projects(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    ensure_registered(Path("/home/user/proj-b"), "proj-b", config_path)
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 2
    names = {p.name for p in cfg.projects}
    assert names == {"proj-a", "proj-b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement registry config module**

Create `science-tool/src/science_tool/registry/__init__.py`:

```python
"""Cross-project registry for Science multi-project sync."""
```

Create `science-tool/src/science_tool/registry/config.py`:

```python
"""Global config and project registration for cross-project sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

SCIENCE_CONFIG_DIR = Path.home() / ".config" / "science"
DEFAULT_CONFIG_PATH = SCIENCE_CONFIG_DIR / "config.yaml"


class SyncSettings(BaseModel):
    """Sync-related settings."""

    stale_after_days: int = 7


class RegisteredProject(BaseModel):
    """A project registered in the global config."""

    path: str
    name: str
    registered: date


class GlobalConfig(BaseModel):
    """Global science config at ~/.config/science/config.yaml."""

    sync: SyncSettings = Field(default_factory=SyncSettings)
    projects: list[RegisteredProject] = Field(default_factory=list)


def load_global_config(config_path: Path = DEFAULT_CONFIG_PATH) -> GlobalConfig:
    """Load global config from YAML. Returns defaults if file missing."""
    if not config_path.is_file():
        return GlobalConfig()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return GlobalConfig.model_validate(data)


def save_global_config(config: GlobalConfig, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save global config to YAML."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def ensure_registered(
    project_root: Path,
    project_name: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Register a project if not already in the global config."""
    config = load_global_config(config_path)
    resolved = str(project_root.resolve())
    for project in config.projects:
        if project.path == resolved:
            return
    config.projects.append(
        RegisteredProject(path=resolved, name=project_name, registered=date.today())
    )
    save_global_config(config, config_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/__init__.py \
       science-tool/src/science_tool/registry/config.py \
       science-tool/tests/test_registry_config.py
git commit -m "feat(registry): add global config and auto-registration"
```

---

## Task 3: Sync State & Entity Hashing

**Files:**
- Create: `science-tool/src/science_tool/registry/state.py`
- Test: `science-tool/tests/test_registry_state.py`

- [ ] **Step 1: Write tests**

Create `science-tool/tests/test_registry_state.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from science_tool.registry.state import (
    ProjectSyncState,
    SyncState,
    compute_entity_hash,
    load_sync_state,
    save_sync_state,
)


def test_compute_entity_hash_deterministic():
    ids_a = ["question:q1", "hypothesis:h1", "claim:c1"]
    ids_b = ["claim:c1", "hypothesis:h1", "question:q1"]
    assert compute_entity_hash(ids_a) == compute_entity_hash(ids_b)


def test_compute_entity_hash_differs():
    assert compute_entity_hash(["a:1"]) != compute_entity_hash(["a:2"])


def test_compute_entity_hash_empty():
    h = compute_entity_hash([])
    assert isinstance(h, str) and len(h) == 64


def test_sync_state_round_trip(tmp_path):
    state_path = tmp_path / "sync_state.yaml"
    now = datetime(2026, 3, 23, 14, 30, 0)
    state = SyncState(
        last_sync=now,
        projects={
            "proj-a": ProjectSyncState(last_synced=now, entity_count=42, entity_hash="abc123"),
        },
    )
    save_sync_state(state, state_path)
    loaded = load_sync_state(state_path)
    assert loaded.last_sync == now
    assert loaded.projects["proj-a"].entity_count == 42


def test_load_sync_state_missing(tmp_path):
    state = load_sync_state(tmp_path / "missing.yaml")
    assert state.last_sync is None
    assert state.projects == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement state module**

Create `science-tool/src/science_tool/registry/state.py`:

```python
"""Sync state tracking for cross-project sync."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from science_tool.registry.config import SCIENCE_CONFIG_DIR

DEFAULT_STATE_PATH = SCIENCE_CONFIG_DIR / "sync_state.yaml"


class ProjectSyncState(BaseModel):
    """Per-project sync state."""

    last_synced: datetime
    entity_count: int
    entity_hash: str


class SyncState(BaseModel):
    """Global sync state at ~/.config/science/sync_state.yaml."""

    last_sync: datetime | None = None
    projects: dict[str, ProjectSyncState] = Field(default_factory=dict)


def compute_entity_hash(canonical_ids: list[str]) -> str:
    """SHA-256 of sorted, newline-joined canonical IDs."""
    joined = "\n".join(sorted(canonical_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def load_sync_state(state_path: Path = DEFAULT_STATE_PATH) -> SyncState:
    """Load sync state from YAML. Returns defaults if file missing."""
    if not state_path.is_file():
        return SyncState()
    data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    return SyncState.model_validate(data)


def save_sync_state(state: SyncState, state_path: Path = DEFAULT_STATE_PATH) -> None:
    """Save sync state to YAML."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    data = state.model_dump(mode="json")
    state_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_state.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/state.py \
       science-tool/tests/test_registry_state.py
git commit -m "feat(registry): add sync state tracking and entity hashing"
```

---

## Task 4: Registry Entity & Relation Index I/O

**Files:**
- Create: `science-tool/src/science_tool/registry/index.py`
- Test: `science-tool/tests/test_registry_index.py`

- [ ] **Step 1: Write tests for registry index models and I/O**

Create `science-tool/tests/test_registry_index.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
    RegistryRelation,
    load_registry_index,
    save_registry_index,
)


def test_registry_entity_round_trip():
    entity = RegistryEntity(
        canonical_id="gene:tp53",
        kind="gene",
        title="TP53",
        profile="bio",
        aliases=["p53", "TP53"],
        ontology_terms=["NCBIGene:7157"],
        source_projects=[
            RegistryEntitySource(project="proj-a", status="active", first_seen=date(2026, 3, 15)),
        ],
    )
    d = entity.model_dump()
    assert RegistryEntity.model_validate(d) == entity


def test_registry_index_round_trip(tmp_path):
    registry_dir = tmp_path / "registry"
    index = RegistryIndex(
        entities=[
            RegistryEntity(
                canonical_id="gene:tp53",
                kind="gene",
                title="TP53",
                profile="bio",
                source_projects=[
                    RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 15)),
                ],
            ),
        ],
        relations=[
            RegistryRelation(
                subject="gene:tp53",
                predicate="biolink:participates_in",
                object="pathway:apoptosis",
                source_projects=["proj-a"],
            ),
        ],
    )
    save_registry_index(index, registry_dir)
    loaded = load_registry_index(registry_dir)
    assert len(loaded.entities) == 1
    assert loaded.entities[0].canonical_id == "gene:tp53"
    assert len(loaded.relations) == 1
    assert loaded.relations[0].predicate == "biolink:participates_in"


def test_load_registry_index_missing(tmp_path):
    index = load_registry_index(tmp_path / "registry")
    assert index.entities == []
    assert index.relations == []


def test_registry_entity_multi_project():
    entity = RegistryEntity(
        canonical_id="gene:tp53",
        kind="gene",
        title="TP53",
        profile="bio",
        source_projects=[
            RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1)),
            RegistryEntitySource(project="proj-b", first_seen=date(2026, 3, 10)),
        ],
    )
    assert len(entity.source_projects) == 2
    project_names = {sp.project for sp in entity.source_projects}
    assert project_names == {"proj-a", "proj-b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_index.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement registry index module**

Create `science-tool/src/science_tool/registry/index.py`:

```python
"""Registry entity and relation index for cross-project sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from science_tool.registry.config import SCIENCE_CONFIG_DIR

DEFAULT_REGISTRY_DIR = SCIENCE_CONFIG_DIR / "registry"


class RegistryEntitySource(BaseModel):
    """Per-project presence record in the registry."""

    project: str
    status: str | None = None
    first_seen: date


class RegistryEntity(BaseModel):
    """An entity tracked across projects in the registry."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    aliases: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    source_projects: list[RegistryEntitySource] = Field(default_factory=list)


class RegistryRelation(BaseModel):
    """A relation tracked across projects in the registry."""

    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_projects: list[str] = Field(default_factory=list)


class RegistryIndex(BaseModel):
    """The complete registry index (entities + relations)."""

    entities: list[RegistryEntity] = Field(default_factory=list)
    relations: list[RegistryRelation] = Field(default_factory=list)


def load_registry_index(registry_dir: Path = DEFAULT_REGISTRY_DIR) -> RegistryIndex:
    """Load entity and relation indices from the registry directory."""
    entities: list[RegistryEntity] = []
    relations: list[RegistryRelation] = []

    entities_path = registry_dir / "entities.yaml"
    if entities_path.is_file():
        data = yaml.safe_load(entities_path.read_text(encoding="utf-8")) or {}
        for item in data.get("entities") or []:
            if isinstance(item, dict):
                entities.append(RegistryEntity.model_validate(item))

    relations_path = registry_dir / "relations.yaml"
    if relations_path.is_file():
        data = yaml.safe_load(relations_path.read_text(encoding="utf-8")) or {}
        for item in data.get("relations") or []:
            if isinstance(item, dict):
                relations.append(RegistryRelation.model_validate(item))

    return RegistryIndex(entities=entities, relations=relations)


def save_registry_index(index: RegistryIndex, registry_dir: Path = DEFAULT_REGISTRY_DIR) -> None:
    """Save entity and relation indices to the registry directory."""
    registry_dir.mkdir(parents=True, exist_ok=True)

    entities_data = {"entities": [e.model_dump(mode="json") for e in index.entities]}
    (registry_dir / "entities.yaml").write_text(
        yaml.dump(entities_data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    relations_data = {"relations": [r.model_dump(mode="json") for r in index.relations]}
    (registry_dir / "relations.yaml").write_text(
        yaml.dump(relations_data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_index.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/index.py \
       science-tool/tests/test_registry_index.py
git commit -m "feat(registry): add entity and relation index I/O"
```

---

## Task 5: Tiered Entity Matching

**Files:**
- Create: `science-tool/src/science_tool/registry/matching.py`
- Test: `science-tool/tests/test_registry_matching.py`

- [ ] **Step 1: Write tests for tiered matching**

Create `science-tool/tests/test_registry_matching.py`:

```python
from __future__ import annotations

from datetime import date

from science_tool.registry.index import RegistryEntity, RegistryEntitySource
from science_tool.registry.matching import MatchResult, MatchTier, find_matches


def _make_entity(
    canonical_id: str,
    kind: str = "gene",
    title: str = "Test",
    aliases: list[str] | None = None,
    ontology_terms: list[str] | None = None,
) -> RegistryEntity:
    return RegistryEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="bio",
        aliases=aliases or [],
        ontology_terms=ontology_terms or [],
        source_projects=[RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1))],
    )


def test_exact_canonical_id_match():
    registry = [_make_entity("gene:tp53")]
    matches = find_matches("gene:tp53", aliases=[], ontology_terms=[], registry_entities=registry)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT
    assert matches[0].entity.canonical_id == "gene:tp53"


def test_alias_match():
    registry = [_make_entity("gene:tp53", aliases=["p53", "TP53"])]
    matches = find_matches("gene:p53-variant", aliases=["p53"], ontology_terms=[], registry_entities=registry)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.ALIAS


def test_ontology_term_match():
    registry = [_make_entity("gene:tp53", ontology_terms=["NCBIGene:7157"])]
    matches = find_matches(
        "gene:tumor-protein-53", aliases=[], ontology_terms=["NCBIGene:7157"], registry_entities=registry
    )
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.ONTOLOGY


def test_fuzzy_title_match():
    registry = [_make_entity("gene:tp53", title="TP53 (Tumor Protein P53)")]
    matches = find_matches(
        "gene:tumor-protein-p53",
        aliases=[],
        ontology_terms=[],
        registry_entities=registry,
        candidate_kind="gene",
        candidate_title="Tumor Protein P53",
    )
    fuzzy = [m for m in matches if m.tier == MatchTier.FUZZY]
    assert len(fuzzy) == 1


def test_no_match():
    registry = [_make_entity("gene:tp53")]
    matches = find_matches("gene:brca1", aliases=[], ontology_terms=[], registry_entities=registry)
    assert matches == []


def test_highest_tier_wins():
    entity = _make_entity("gene:tp53", aliases=["p53"], ontology_terms=["NCBIGene:7157"])
    registry = [entity]
    matches = find_matches(
        "gene:tp53", aliases=["p53"], ontology_terms=["NCBIGene:7157"], registry_entities=registry
    )
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT  # highest tier
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_matching.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement matching module**

Create `science-tool/src/science_tool/registry/matching.py`:

```python
"""Tiered entity matching for cross-project registry lookups."""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel

from science_tool.registry.index import RegistryEntity


class MatchTier(IntEnum):
    """Match confidence tiers, ordered from highest to lowest."""

    EXACT = 1
    ALIAS = 2
    ONTOLOGY = 3
    FUZZY = 4


class MatchResult(BaseModel):
    """A match between a candidate entity and a registry entry."""

    entity: RegistryEntity
    tier: MatchTier


def find_matches(
    canonical_id: str,
    *,
    aliases: list[str],
    ontology_terms: list[str],
    registry_entities: list[RegistryEntity],
    candidate_kind: str | None = None,
    candidate_title: str | None = None,
) -> list[MatchResult]:
    """Find registry entities matching a candidate, returning highest-tier match only.

    Tiers 1-3 are auto-resolvable. Tier 4 (fuzzy) is for user review.
    """
    best: MatchResult | None = None

    candidate_aliases = {a.lower() for a in aliases}
    candidate_aliases.add(canonical_id.lower())
    candidate_ontology = set(ontology_terms)

    for entry in registry_entities:
        tier = _match_tier(
            entry,
            canonical_id=canonical_id,
            candidate_aliases=candidate_aliases,
            candidate_ontology=candidate_ontology,
            candidate_kind=candidate_kind,
            candidate_title=candidate_title,
        )
        if tier is None:
            continue
        if best is None or tier < best.tier:
            best = MatchResult(entity=entry, tier=tier)

    return [best] if best is not None else []


def _match_tier(
    entry: RegistryEntity,
    *,
    canonical_id: str,
    candidate_aliases: set[str],
    candidate_ontology: set[str],
    candidate_kind: str | None,
    candidate_title: str | None,
) -> MatchTier | None:
    # Tier 1: exact canonical ID
    if entry.canonical_id == canonical_id:
        return MatchTier.EXACT

    # Tier 2: alias overlap
    entry_aliases = {a.lower() for a in entry.aliases}
    entry_aliases.add(entry.canonical_id.lower())
    if candidate_aliases & entry_aliases:
        return MatchTier.ALIAS

    # Tier 3: ontology term overlap
    if candidate_ontology and candidate_ontology & set(entry.ontology_terms):
        return MatchTier.ONTOLOGY

    # Tier 4: fuzzy title + kind match
    if candidate_kind and candidate_title and entry.kind == candidate_kind:
        if _titles_similar(candidate_title, entry.title):
            return MatchTier.FUZZY

    return None


def _titles_similar(a: str, b: str) -> bool:
    """Simple containment-based title similarity."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if a_lower == b_lower:
        return True
    return a_lower in b_lower or b_lower in a_lower
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_matching.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/matching.py \
       science-tool/tests/test_registry_matching.py
git commit -m "feat(registry): add tiered entity matching"
```

---

## Task 6: Dynamic Profile Loading

**Files:**
- Modify: `science-model/src/science_model/profiles/__init__.py`
- Modify: `science-tool/src/science_tool/graph/sources.py:18-21, 85-123, 540-543`
- Test: `science-model/tests/test_profile_manifests.py`
- Test: `science-tool/tests/test_graph_materialize.py` (existing tests still pass)

- [ ] **Step 1: Write test for `load_cross_project_profile()`**

In `science-model/tests/test_profile_manifests.py`, add:

```python
import yaml
from science_model.profiles import load_cross_project_profile


def test_load_cross_project_profile_from_yaml(tmp_path):
    manifest = {
        "name": "cross-project",
        "imports": ["core"],
        "strictness": "curated",
        "entity_kinds": [
            {"name": "protein-complex", "canonical_prefix": "protein-complex",
             "layer": "layer/cross-project", "description": "Shared protein complex kind."},
        ],
        "relation_kinds": [],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest), encoding="utf-8")
    profile = load_cross_project_profile(manifest_path)
    assert profile is not None
    assert profile.name == "cross-project"
    assert profile.strictness == "curated"
    assert len(profile.entity_kinds) == 1
    assert profile.entity_kinds[0].name == "protein-complex"


def test_load_cross_project_profile_missing(tmp_path):
    profile = load_cross_project_profile(tmp_path / "missing.yaml")
    assert profile is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py::test_load_cross_project_profile_from_yaml -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `load_cross_project_profile()`**

In `science-model/src/science_model/profiles/__init__.py`, add:

```python
from pathlib import Path

import yaml

from science_model.profiles.schema import ProfileManifest

_DEFAULT_MANIFEST_PATH = Path.home() / ".config" / "science" / "registry" / "manifest.yaml"


def load_cross_project_profile(
    manifest_path: Path = _DEFAULT_MANIFEST_PATH,
) -> ProfileManifest | None:
    """Load the cross-project profile from YAML. Returns None if not found."""
    if not manifest_path.is_file():
        return None
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return ProfileManifest.model_validate(data)
```

Update `__all__` to include `load_cross_project_profile`.

- [ ] **Step 4: Run profile tests**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -v`
Expected: All PASS

- [ ] **Step 5: Write test for dynamic `_known_kinds` in sources.py**

In `science-tool/tests/test_graph_materialize.py`, add:

```python
from science_model.profiles.schema import EntityKind, ProfileManifest
from science_tool.graph.sources import known_kinds


def test_known_kinds_includes_cross_project():
    cross_project = ProfileManifest(
        name="cross-project",
        imports=["core"],
        strictness="curated",
        entity_kinds=[
            EntityKind(
                name="protein-complex",
                canonical_prefix="protein-complex",
                layer="layer/cross-project",
                description="Shared kind.",
            ),
        ],
        relation_kinds=[],
    )
    kinds = known_kinds(extra_profiles=[cross_project])
    assert "protein-complex" in kinds
    assert "hypothesis" in kinds  # core kinds still present
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_materialize.py::test_known_kinds_includes_cross_project -v`
Expected: FAIL — `ImportError: cannot import name 'known_kinds'`

- [ ] **Step 7: Refactor `_CORE_KINDS` to `known_kinds()` in sources.py**

In `science-tool/src/science_tool/graph/sources.py`:

Keep `_CORE_KINDS` constant but add a function that extends it:

```python
from science_model.profiles.schema import ProfileManifest

_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)


def known_kinds(extra_profiles: list[ProfileManifest] | None = None) -> frozenset[str]:
    """Return entity kind names from core + any extra profiles."""
    kinds = set(_CORE_KINDS)
    for profile in extra_profiles or []:
        kinds.update(kind.name for kind in profile.entity_kinds)
    return frozenset(kinds)
```

Update `_default_profile_for_kind` to accept `active_kinds` parameter:

```python
def _default_profile_for_kind(kind: str, *, local_profile: str, active_kinds: frozenset[str] | None = None) -> str:
    check = active_kinds if active_kinds is not None else _CORE_KINDS
    if kind in check:
        return "core"
    return local_profile
```

Update `load_project_sources()` to resolve the cross-project profile if listed in curated profiles:

```python
from science_model.profiles import load_cross_project_profile

def load_project_sources(project_root: Path) -> ProjectSources:
    ...
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])

    # Resolve dynamic profiles
    extra_profiles: list[ProfileManifest] = []
    if "cross-project" in profiles.curated:
        xp = load_cross_project_profile()
        if xp is not None:
            extra_profiles.append(xp)

    active_kinds = known_kinds(extra_profiles=extra_profiles)
    local_profile = profiles.local
    # Pass active_kinds to all _load_* functions that call _default_profile_for_kind
    ...
```

- [ ] **Step 8: Run all existing materialize tests + new test**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_materialize.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add science-model/src/science_model/profiles/__init__.py \
       science-model/tests/test_profile_manifests.py \
       science-tool/src/science_tool/graph/sources.py \
       science-tool/tests/test_graph_materialize.py
git commit -m "feat: dynamic profile loading and known_kinds() for cross-project support"
```

---

## Task 7: Sync Orchestrator — Collect & Align (Phases 1-2)

**Files:**
- Create: `science-tool/src/science_tool/registry/sync.py`
- Modify: `science-tool/src/science_tool/graph/sources.py` (add `tags` to `SourceEntity`)
- Test: `science-tool/tests/test_registry_sync.py`

**Prerequisite:** Before implementing sync, add `tags: list[str] = Field(default_factory=list)` to `SourceEntity` in `sources.py` and wire it through `_load_markdown_entities` (from frontmatter `fm.get("tags") or []`). This is needed for tag-gated propagation of `task`/`dataset`/`method` entities.

- [ ] **Step 1: Add `tags` field to `SourceEntity`**

In `science-tool/src/science_tool/graph/sources.py`, add to `SourceEntity`:

```python
    tags: list[str] = Field(default_factory=list)
```

In `_load_markdown_entities`, add to the `SourceEntity(...)` constructor:

```python
    tags=[str(t) for t in (entity.tags or [])],
```

- [ ] **Step 2: Write tests for collect and align phases**

Create `science-tool/tests/test_registry_sync.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryEntity, RegistryEntitySource, RegistryIndex
from science_tool.registry.sync import collect_all_project_sources, align_registry


def _write_project(root: Path, name: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        f"name: {name}\nknowledge_profiles:\n  curated: []\n  local: project_specific\n",
        encoding="utf-8",
    )
    for subdir in ("doc", "specs", "tasks", "knowledge"):
        (root / subdir).mkdir(exist_ok=True)


def _write_entity_md(project_root: Path, filename: str, entity_id: str, entity_type: str, title: str,
                     related: list[str] | None = None, ontology_terms: list[str] | None = None,
                     aliases: list[str] | None = None) -> None:
    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    rel = related or []
    ont = ontology_terms or []
    als = aliases or []
    (doc_dir / filename).write_text(
        f"---\nid: \"{entity_id}\"\ntype: {entity_type}\ntitle: \"{title}\"\n"
        f"related: {rel}\nontology_terms: {ont}\naliases: {als}\n---\nBody.\n",
        encoding="utf-8",
    )


def _source_entity(canonical_id: str, kind: str, title: str,
                    aliases: list[str] | None = None,
                    ontology_terms: list[str] | None = None) -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="core",
        source_path=f"doc/{canonical_id.replace(':', '-')}.md",
        aliases=aliases or [],
        ontology_terms=ontology_terms or [],
    )


def test_collect_skips_missing_paths(tmp_path):
    results = collect_all_project_sources(
        project_paths=[tmp_path / "nonexistent"],
    )
    assert results == []


def test_collect_loads_project(tmp_path):
    proj = tmp_path / "proj-a"
    _write_project(proj, "proj-a")
    _write_entity_md(proj, "q1.md", "question:q1", "question", "Question 1")
    results = collect_all_project_sources(project_paths=[proj])
    assert len(results) == 1
    assert results[0].project_name == "proj-a"
    assert any(e.canonical_id == "question:q1" for e in results[0].entities)


def test_align_deduplicates_across_projects():
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [_source_entity("gene:tp53", "gene", "TP53", ["p53"], ["NCBIGene:7157"])],
        "proj-b": [_source_entity("gene:tp53", "gene", "TP53 tumor protein", ["TP53"], ["NCBIGene:7157"])],
    }
    result = align_registry(existing, project_sources)
    tp53_entries = [e for e in result.entities if e.canonical_id == "gene:tp53"]
    assert len(tp53_entries) == 1
    projects = {sp.project for sp in tp53_entries[0].source_projects}
    assert projects == {"proj-a", "proj-b"}
    # Aliases merged
    aliases = set(tp53_entries[0].aliases)
    assert "p53" in aliases
    assert "TP53" in aliases
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement collect and align**

Create `science-tool/src/science_tool/registry/sync.py`:

```python
"""Sync orchestrator for cross-project alignment and propagation."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from science_tool.graph.sources import ProjectSources, SourceEntity, load_project_sources
from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
)

logger = logging.getLogger(__name__)


def collect_all_project_sources(
    *,
    project_paths: list[Path],
) -> list[ProjectSources]:
    """Phase 1: Load sources for each registered project, skipping missing."""
    results: list[ProjectSources] = []
    for path in project_paths:
        if not path.is_dir() or not (path / "science.yaml").is_file():
            logger.warning("Skipping missing project at %s", path)
            continue
        try:
            sources = load_project_sources(path)
            results.append(sources)
        except Exception:
            logger.warning("Failed to load project at %s", path, exc_info=True)
    return results


def align_registry(
    existing: RegistryIndex,
    project_sources: dict[str, list[SourceEntity]],
) -> RegistryIndex:
    """Phase 2: Align entities across projects into the registry.

    project_sources maps project_name -> list of SourceEntity.
    """
    entity_map: dict[str, RegistryEntity] = {e.canonical_id: e for e in existing.entities}

    for project_name, entities in project_sources.items():
        today = date.today()
        for src in entities:
            if src.canonical_id in entity_map:
                entry = entity_map[src.canonical_id]
                _merge_aliases(entry, src.aliases)
                _merge_ontology_terms(entry, src.ontology_terms)
                _ensure_project_listed(entry, project_name, today)
            else:
                entity_map[src.canonical_id] = RegistryEntity(
                    canonical_id=src.canonical_id,
                    kind=src.kind,
                    title=src.title,
                    profile=src.profile,
                    aliases=list(src.aliases),
                    ontology_terms=list(src.ontology_terms),
                    source_projects=[
                        RegistryEntitySource(project=project_name, first_seen=today),
                    ],
                )

    entities = sorted(entity_map.values(), key=lambda e: e.canonical_id)
    return RegistryIndex(entities=entities, relations=existing.relations)


def _merge_aliases(entry: RegistryEntity, new_aliases: list[str]) -> None:
    existing = set(entry.aliases)
    for alias in new_aliases:
        if alias not in existing:
            entry.aliases.append(alias)
            existing.add(alias)


def _merge_ontology_terms(entry: RegistryEntity, new_terms: list[str]) -> None:
    existing = set(entry.ontology_terms)
    for term in new_terms:
        if term not in existing:
            entry.ontology_terms.append(term)
            existing.add(term)


def _ensure_project_listed(entry: RegistryEntity, project_name: str, today: date) -> None:
    project_names = {sp.project for sp in entry.source_projects}
    if project_name not in project_names:
        entry.source_projects.append(
            RegistryEntitySource(project=project_name, first_seen=today)
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py \
       science-tool/src/science_tool/registry/sync.py \
       science-tool/tests/test_registry_sync.py
git commit -m "feat(registry): add sync collect and align phases"
```

---

## Task 8: Content Propagation (Phase 3)

**Files:**
- Create: `science-tool/src/science_tool/registry/propagation.py`
- Test: `science-tool/tests/test_registry_propagation.py`

- [ ] **Step 1: Write tests for propagation logic**

Create `science-tool/tests/test_registry_propagation.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryEntity, RegistryEntitySource
from science_tool.registry.propagation import (
    PropagationAction,
    compute_propagations,
    write_propagated_entity,
)


def _reg_entity(canonical_id: str, projects: list[str]) -> RegistryEntity:
    return RegistryEntity(
        canonical_id=canonical_id,
        kind="gene",
        title="Test",
        profile="bio",
        source_projects=[
            RegistryEntitySource(project=p, first_seen=date(2026, 3, 1)) for p in projects
        ],
    )


def _source_entity(canonical_id: str, kind: str, title: str, related: list[str],
                    source_path: str | None = None, tags: list[str] | None = None) -> SourceEntity:
    """Helper to build a SourceEntity for propagation tests."""
    return SourceEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="core",
        source_path=source_path or f"doc/{canonical_id.replace(':', '-')}.md",
        related=related,
        content_preview="Test content preview.",
        tags=tags or [],
    )


def test_propagation_finds_cross_project_content():
    shared = [_reg_entity("gene:tp53", ["proj-a", "proj-b"])]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [],
    }
    actions = compute_propagations(
        shared_entities=shared,
        project_sources=project_sources,
    )
    assert len(actions) == 1
    assert actions[0].source_project == "proj-a"
    assert actions[0].target_project == "proj-b"
    assert actions[0].entity.canonical_id == "question:q1"


def test_propagation_skips_already_present():
    shared = [_reg_entity("gene:tp53", ["proj-a", "proj-b"])]
    q1 = _source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])
    project_sources = {
        "proj-a": [q1],
        "proj-b": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
    }
    actions = compute_propagations(shared_entities=shared, project_sources=project_sources)
    assert actions == []


def test_propagation_skips_sync_sourced_entities():
    """Entities from doc/sync/ (sync-propagated) must not re-propagate."""
    shared = [_reg_entity("gene:tp53", ["proj-a", "proj-b"])]
    q1 = _source_entity(
        "question:q1", "question", "Q about TP53", ["gene:tp53"],
        source_path="doc/sync/q1-from-proj-c.md",
        tags=["sync-propagated"],
    )
    project_sources = {"proj-a": [q1], "proj-b": []}
    actions = compute_propagations(shared_entities=shared, project_sources=project_sources)
    assert actions == []


def test_propagation_tag_gated_task():
    """Tasks only propagate if tagged with cross-project."""
    shared = [_reg_entity("gene:tp53", ["proj-a", "proj-b"])]
    # Task without cross-project tag — should NOT propagate
    t1 = _source_entity("task:t1", "task", "Run analysis", ["gene:tp53"])
    # Task WITH cross-project tag — should propagate
    t2 = _source_entity("task:t2", "task", "Shared task", ["gene:tp53"], tags=["cross-project"])
    project_sources = {"proj-a": [t1, t2], "proj-b": []}
    actions = compute_propagations(shared_entities=shared, project_sources=project_sources)
    ids = {a.entity.canonical_id for a in actions}
    assert "task:t1" not in ids
    assert "task:t2" in ids


def test_propagation_excludes_non_propagatable_types():
    shared = [_reg_entity("gene:tp53", ["proj-a", "proj-b"])]
    project_sources = {
        "proj-a": [_source_entity("workflow:w1", "workflow", "Pipeline", ["gene:tp53"])],
        "proj-b": [],
    }
    actions = compute_propagations(shared_entities=shared, project_sources=project_sources)
    assert actions == []


def test_write_propagated_entity(tmp_path):
    entity = _source_entity("question:q1-tp53", "question", "TP53 methylation?", ["gene:tp53"])
    output_path = write_propagated_entity(
        entity=entity,
        source_project="aging-clocks",
        target_project_root=tmp_path,
        sync_date=date(2026, 3, 23),
    )
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "sync_source:" in content
    assert 'project: "aging-clocks"' in content
    assert "sync-propagated" in content
    assert output_path.parent.name == "sync"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_propagation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement propagation module**

Create `science-tool/src/science_tool/registry/propagation.py`:

```python
"""Cross-project content propagation for sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryEntity

# Entity kinds eligible for propagation
_ALWAYS_PROPAGATE = frozenset({"question", "claim", "relation_claim", "hypothesis", "evidence"})
_TAG_PROPAGATE = frozenset({"task", "dataset", "method"})


class PropagationAction(BaseModel):
    """A pending propagation of an entity from one project to another."""

    source_project: str
    target_project: str
    entity: SourceEntity
    shared_via: str  # canonical_id of the shared entity that triggered propagation


def compute_propagations(
    *,
    shared_entities: list[RegistryEntity],
    project_sources: dict[str, list[SourceEntity]],
) -> list[PropagationAction]:
    """Compute which entities should be propagated across projects."""
    # Build lookup: project -> set of canonical_ids
    project_ids: dict[str, set[str]] = {
        name: {e.canonical_id for e in entities} for name, entities in project_sources.items()
    }

    actions: list[PropagationAction] = []

    for shared in shared_entities:
        shared_project_names = {sp.project for sp in shared.source_projects}
        if len(shared_project_names) < 2:
            continue

        for source_project, entities in project_sources.items():
            if source_project not in shared_project_names:
                continue

            for entity in entities:
                if not _is_propagatable(entity):
                    continue
                if shared.canonical_id not in entity.related:
                    continue

                for target_project in shared_project_names:
                    if target_project == source_project:
                        continue
                    if entity.canonical_id in project_ids.get(target_project, set()):
                        continue
                    actions.append(
                        PropagationAction(
                            source_project=source_project,
                            target_project=target_project,
                            entity=entity,
                            shared_via=shared.canonical_id,
                        )
                    )

    return actions


def write_propagated_entity(
    *,
    entity: SourceEntity,
    source_project: str,
    target_project_root: Path,
    sync_date: date,
) -> Path:
    """Write a propagated entity as a markdown file in doc/sync/."""
    sync_dir = target_project_root / "doc" / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)

    slug = entity.canonical_id.replace(":", "-").replace("/", "-")
    filename = f"{slug}-from-{source_project}.md"
    output_path = sync_dir / filename

    related_yaml = "\n".join(f'  - "{r}"' for r in entity.related) if entity.related else "  []"
    content = (
        f"---\n"
        f'id: "{entity.canonical_id}"\n'
        f"type: {entity.kind}\n"
        f'title: "{entity.title}"\n'
        f"status: open\n"
        f"tags: [sync-propagated]\n"
        f"related:\n{related_yaml}\n"
        f"source_refs: []\n"
        f"sync_source:\n"
        f'  project: "{source_project}"\n'
        f'  entity_id: "{entity.canonical_id}"\n'
        f'  sync_date: "{sync_date.isoformat()}"\n'
        f"---\n"
        f"\n"
        f"*Propagated from {source_project} on {sync_date.isoformat()}.*\n"
        f"\n"
        f"{entity.content_preview}\n"
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _is_propagatable(entity: SourceEntity) -> bool:
    """Check if an entity is eligible for propagation."""
    # Never re-propagate sync-sourced entities (prevents A→B→A storms)
    if "sync-propagated" in entity.tags:
        return False
    if entity.source_path.startswith("doc/sync/"):
        return False

    if entity.kind in _ALWAYS_PROPAGATE:
        return True
    if entity.kind in _TAG_PROPAGATE:
        return "cross-project" in entity.tags
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_propagation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/propagation.py \
       science-tool/tests/test_registry_propagation.py
git commit -m "feat(registry): add cross-project content propagation"
```

---

## Task 9: Proactive Registry Checks

**Files:**
- Create: `science-tool/src/science_tool/registry/checks.py`
- Test: `science-tool/tests/test_registry_checks.py`

- [ ] **Step 1: Write tests for proactive checks**

Create `science-tool/tests/test_registry_checks.py`:

```python
from __future__ import annotations

from datetime import date

from science_tool.registry.checks import check_registry
from science_tool.registry.matching import MatchResult
from science_tool.registry.index import RegistryEntity, RegistryEntitySource, RegistryIndex
from science_tool.registry.matching import MatchTier


def _index_with_entity(canonical_id: str, aliases: list[str] | None = None,
                        ontology_terms: list[str] | None = None) -> RegistryIndex:
    return RegistryIndex(
        entities=[
            RegistryEntity(
                canonical_id=canonical_id,
                kind="gene",
                title="Test entity",
                profile="bio",
                aliases=aliases or [],
                ontology_terms=ontology_terms or [],
                source_projects=[
                    RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1)),
                ],
            ),
        ],
    )


def test_check_registry_exact_match():
    index = _index_with_entity("gene:tp53")
    matches = check_registry("gene:tp53", aliases=[], ontology_terms=[], registry_index=index)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT


def test_check_registry_no_match():
    index = _index_with_entity("gene:tp53")
    matches = check_registry("gene:brca1", aliases=[], ontology_terms=[], registry_index=index)
    assert matches == []


def test_check_registry_empty_index():
    matches = check_registry("gene:tp53", aliases=[], ontology_terms=[], registry_index=RegistryIndex())
    assert matches == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_checks.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement proactive checks**

Create `science-tool/src/science_tool/registry/checks.py`:

```python
"""Proactive registry checks for entity deduplication."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from science_tool.registry.index import RegistryIndex, load_registry_index
from science_tool.registry.matching import MatchResult, MatchTier, find_matches

_cached_index: RegistryIndex | None = None


def check_registry(
    canonical_id: str,
    *,
    aliases: list[str],
    ontology_terms: list[str],
    candidate_kind: str | None = None,
    candidate_title: str | None = None,
    registry_index: RegistryIndex | None = None,
) -> list[MatchResult]:
    """Check if an entity matches anything in the registry.

    Read-only, advisory. Returns matches sorted by tier (highest first).
    If registry_index is not provided, loads from default path (cached).
    """
    if registry_index is None:
        registry_index = _get_cached_index()

    return find_matches(
        canonical_id,
        aliases=aliases,
        ontology_terms=ontology_terms,
        registry_entities=registry_index.entities,
        candidate_kind=candidate_kind,
        candidate_title=candidate_title,
    )


def _get_cached_index() -> RegistryIndex:
    global _cached_index
    if _cached_index is None:
        _cached_index = load_registry_index()
    return _cached_index


def clear_cache() -> None:
    """Clear the cached registry index (for testing)."""
    global _cached_index
    _cached_index = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_checks.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/checks.py \
       science-tool/tests/test_registry_checks.py
git commit -m "feat(registry): add proactive registry checks"
```

---

## Task 10: Full Sync Orchestrator (Phases 3-5) & `run_sync()`

**Files:**
- Modify: `science-tool/src/science_tool/registry/sync.py`
- Test: `science-tool/tests/test_registry_sync.py` (extend)

- [ ] **Step 1: Write integration test for full sync run**

Add to `science-tool/tests/test_registry_sync.py`:

```python
from science_tool.registry.sync import run_sync, SyncReport


def test_full_sync_two_projects(tmp_path):
    # Set up two projects sharing gene:tp53
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")

    # proj-a has question:q1 about gene:tp53
    _write_entity_md(proj_a, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"])
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "TP53 question",
                     related=["gene:tp53"])

    # proj-b also has gene:tp53
    _write_entity_md(proj_b, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"])

    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "sync_state.yaml"
    registry_dir = tmp_path / "registry"

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=state_path,
        registry_dir=registry_dir,
    )

    assert isinstance(report, SyncReport)
    assert report.entities_total > 0
    # Check propagation created file in proj-b
    sync_files = list((proj_b / "doc" / "sync").glob("*.md"))
    assert len(sync_files) >= 1


def test_sync_idempotent(tmp_path):
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    _write_entity_md(proj_a, "tp53.md", "gene:tp53", "concept", "TP53")
    _write_entity_md(proj_b, "tp53.md", "gene:tp53", "concept", "TP53")
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "Q1", related=["gene:tp53"])

    kwargs = dict(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    run_sync(**kwargs)
    report2 = run_sync(**kwargs)
    # Second run should not duplicate propagations
    sync_files = list((proj_b / "doc" / "sync").glob("*.md"))
    assert len(sync_files) <= 1  # at most 1, not duplicated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py::test_full_sync_two_projects -v`
Expected: FAIL — `ImportError: cannot import name 'run_sync'`

- [ ] **Step 3: Implement `run_sync()` and `SyncReport`**

Add to `science-tool/src/science_tool/registry/sync.py`:

```python
from datetime import datetime
from pydantic import BaseModel, Field

from science_tool.registry.index import (
    RegistryIndex,
    load_registry_index,
    save_registry_index,
)
from science_tool.registry.propagation import compute_propagations, write_propagated_entity
from science_tool.registry.state import (
    ProjectSyncState,
    SyncState,
    compute_entity_hash,
    load_sync_state,
    save_sync_state,
)


class SyncReport(BaseModel):
    """Summary of a sync run."""

    entities_total: int = 0
    entities_new: int = 0
    relations_total: int = 0
    propagated: dict[str, int] = Field(default_factory=dict)  # "proj-a → proj-b": count
    drift_warnings: list[str] = Field(default_factory=list)


def run_sync(
    *,
    project_paths: list[Path],
    registry_dir: Path,
    state_path: Path,
    dry_run: bool = False,
) -> SyncReport:
    """Execute full sync: collect → align → propagate → save → update state."""
    report = SyncReport()

    # Phase 1: Collect
    all_sources = collect_all_project_sources(project_paths=project_paths)
    if not all_sources:
        return report

    # Phase 2: Align
    existing_index = load_registry_index(registry_dir)
    old_count = len(existing_index.entities)

    project_entity_map: dict[str, list[SourceEntity]] = {}
    for sources in all_sources:
        project_entity_map[sources.project_name] = sources.entities

    new_index = align_registry(existing_index, project_entity_map)
    report.entities_total = len(new_index.entities)
    report.entities_new = len(new_index.entities) - old_count
    report.relations_total = len(new_index.relations)

    # Phase 3: Propagate
    shared = [e for e in new_index.entities if len(e.source_projects) >= 2]
    actions = compute_propagations(
        shared_entities=shared,
        project_sources=project_entity_map,
    )

    if not dry_run:
        name_to_root: dict[str, Path] = {s.project_name: Path(s.project_root) for s in all_sources}
        today = date.today()
        for action in actions:
            target_root = name_to_root.get(action.target_project)
            if target_root:
                write_propagated_entity(
                    entity=action.entity,
                    source_project=action.source_project,
                    target_project_root=target_root,
                    sync_date=today,
                )
                key = f"{action.source_project} → {action.target_project}"
                report.propagated[key] = report.propagated.get(key, 0) + 1

        # Phase 4/5: Save registry and update state
        save_registry_index(new_index, registry_dir)

        now = datetime.now()
        state = SyncState(last_sync=now, projects={})
        for sources in all_sources:
            ids = [e.canonical_id for e in sources.entities]
            state.projects[sources.project_name] = ProjectSyncState(
                last_synced=now,
                entity_count=len(ids),
                entity_hash=compute_entity_hash(ids),
            )
        save_sync_state(state, state_path)

    return report
```

- [ ] **Step 4: Run integration tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/sync.py \
       science-tool/tests/test_registry_sync.py
git commit -m "feat(registry): complete sync orchestrator with propagation and reporting"
```

---

## Task 11: CLI Commands — `sync` Group

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_sync_cli.py`

- [ ] **Step 1: Write CLI tests**

Create `science-tool/tests/test_sync_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _setup_projects(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create two minimal projects and a config."""
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    for proj, name in [(proj_a, "proj-a"), (proj_b, "proj-b")]:
        proj.mkdir()
        (proj / "science.yaml").write_text(
            f"name: {name}\nknowledge_profiles:\n  curated: []\n  local: project_specific\n"
        )
        (proj / "doc").mkdir()
        (proj / "specs").mkdir()
        (proj / "tasks").mkdir()

    config_path = tmp_path / "config.yaml"
    return proj_a, proj_b, config_path


def test_sync_status_no_config(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "status", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 0
    assert "No sync" in result.output or "never" in result.output.lower()


def test_sync_projects_list(tmp_path):
    from science_tool.registry.config import ensure_registered

    config_path = tmp_path / "config.yaml"
    ensure_registered(tmp_path / "proj-a", "proj-a", config_path)
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "projects", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "proj-a" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_sync_cli.py -v`
Expected: FAIL — no `sync` command group

- [ ] **Step 3: Add sync CLI commands to cli.py**

Add to `science-tool/src/science_tool/cli.py`:

```python
@main.group()
def sync() -> None:
    """Cross-project sync commands."""


@sync.command("run")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--dry-run", is_flag=True, help="Preview without writing changes")
def sync_run(config_path: str | None, dry_run: bool) -> None:
    """Run cross-project sync."""
    from science_tool.registry.config import DEFAULT_CONFIG_PATH, SCIENCE_CONFIG_DIR, load_global_config
    from science_tool.registry.index import DEFAULT_REGISTRY_DIR
    from science_tool.registry.state import DEFAULT_STATE_PATH
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects. Run science commands in project directories first.")
        return

    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=DEFAULT_REGISTRY_DIR,
        state_path=DEFAULT_STATE_PATH,
        dry_run=dry_run,
    )
    prefix = "[dry run] " if dry_run else ""
    click.echo(f"{prefix}Sync complete.")
    click.echo(f"  Entities: {report.entities_total} (+{report.entities_new} new)")
    click.echo(f"  Relations: {report.relations_total}")
    if report.propagated:
        click.echo("  Propagated:")
        for key, count in report.propagated.items():
            click.echo(f"    {key}: {count}")
    if report.drift_warnings:
        click.echo("  Drift warnings:")
        for warning in report.drift_warnings:
            click.echo(f"    {warning}")


@sync.command("status")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_status(config_path: str | None) -> None:
    """Show sync status and staleness."""
    from datetime import datetime

    from science_tool.registry.config import DEFAULT_CONFIG_PATH, load_global_config
    from science_tool.registry.state import load_sync_state

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    config = load_global_config(cfg_path)
    state = load_sync_state()

    if state.last_sync is None:
        click.echo("No sync has been performed yet.")
        if config.projects:
            click.echo(f"  {len(config.projects)} registered project(s). Run `science-tool sync run`.")
        return

    days = (datetime.now() - state.last_sync).days
    click.echo(f"Last sync: {state.last_sync.isoformat()} ({days} days ago)")
    stale_threshold = config.sync.stale_after_days
    if days > stale_threshold:
        click.echo(f"  Sync is stale (threshold: {stale_threshold} days). Run `science-tool sync run`.")
    for name, pstate in state.projects.items():
        click.echo(f"  {name}: {pstate.entity_count} entities (hash: {pstate.entity_hash[:8]})")


@sync.command("projects")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_projects(config_path: str | None) -> None:
    """List registered projects."""
    from science_tool.registry.config import DEFAULT_CONFIG_PATH, load_global_config

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects.")
        return
    for p in config.projects:
        click.echo(f"  {p.name}: {p.path} (registered {p.registered})")


@sync.command("rebuild")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_rebuild(config_path: str | None) -> None:
    """Rebuild registry from scratch by scanning all projects."""
    import shutil

    from science_tool.registry.config import DEFAULT_CONFIG_PATH, load_global_config
    from science_tool.registry.index import DEFAULT_REGISTRY_DIR
    from science_tool.registry.state import DEFAULT_STATE_PATH
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects.")
        return

    # Clear existing registry
    if DEFAULT_REGISTRY_DIR.is_dir():
        shutil.rmtree(DEFAULT_REGISTRY_DIR)
    click.echo("Registry cleared. Rebuilding...")

    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=DEFAULT_REGISTRY_DIR,
        state_path=DEFAULT_STATE_PATH,
    )
    click.echo(f"Rebuild complete. {report.entities_total} entities, {report.relations_total} relations.")
```

- [ ] **Step 4: Run CLI tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_sync_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Run full science-tool test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/cli.py \
       science-tool/tests/test_sync_cli.py
git commit -m "feat(cli): add sync command group (run, status, projects, rebuild)"
```

---

## Task 12: Wire Auto-Registration into CLI Entry Point

**Note:** The spec says registration should happen on "any science CLI command that resolves a project root." For v1, we wire it into `graph build` as the primary integration point — this is the command that most directly interacts with project sources. Other commands can be wired in as a follow-up.

**Files:**
- Modify: `science-tool/src/science_tool/cli.py:69-71`
- Test: `science-tool/tests/test_sync_cli.py` (extend)

- [ ] **Step 1: Write test for auto-registration**

Add to `science-tool/tests/test_sync_cli.py`:

```python
def test_graph_build_registers_project(tmp_path, monkeypatch):
    """Running graph build in a project dir auto-registers it."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "science.yaml").write_text(
        "name: auto-reg-test\nknowledge_profiles:\n  curated: []\n  local: project_specific\n"
    )
    (proj / "doc").mkdir()
    (proj / "specs").mkdir()
    (proj / "tasks").mkdir()
    (proj / "knowledge").mkdir()

    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("science_tool.registry.config.DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.chdir(proj)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build"])

    from science_tool.registry.config import load_global_config

    cfg = load_global_config(config_path)
    assert any(p.name == "auto-reg-test" for p in cfg.projects)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_sync_cli.py::test_graph_build_registers_project -v`
Expected: FAIL — project not registered

- [ ] **Step 3: Wire `ensure_registered` into CLI**

Add a callback to the `graph` group (or to `main`) that detects when running in a project directory and calls `ensure_registered()`. The cleanest approach: add it to commands that load project sources (e.g., `graph build`).

In the `graph_build` command handler, after resolving the project root, add:

```python
import yaml
from science_tool.registry.config import ensure_registered

project_root = Path.cwd()
science_yaml = project_root / "science.yaml"
if science_yaml.is_file():
    project_name = (yaml.safe_load(science_yaml.read_text()) or {}).get("name", project_root.name)
    ensure_registered(project_root, str(project_name))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_sync_cli.py::test_graph_build_registers_project -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/cli.py \
       science-tool/tests/test_sync_cli.py
git commit -m "feat(cli): auto-register project on graph build"
```

---

## Task 13: Command Prompts — `/science:sync` and Staleness Nudges

**Files:**
- Create: `commands/sync.md`
- Modify: `commands/status.md`
- Modify: `commands/next-steps.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/update-graph.md`

- [ ] **Step 1: Create `/science:sync` command prompt**

Create `commands/sync.md` with the sync command template. This should instruct Claude to:
1. Run `science-tool sync run` to execute the sync
2. Present the sync report to the user
3. Summarize propagated entities and fuzzy matches requiring attention
4. Suggest next actions (review propagated entities, resolve drift)

- [ ] **Step 2: Add staleness nudge to `/science:status`**

In `commands/status.md`, add a section near the end:

```markdown
## Cross-Project Sync Status

Run `science-tool sync status` to check when the last cross-project sync was performed.
If sync is stale (over the configured threshold), mention it:

> Cross-project sync is N days stale. Run `/science:sync` to align with N other registered projects.

If the current project has new entities since last sync, also mention:

> This project has N new entities since last sync.
```

- [ ] **Step 3: Add staleness nudge to `/science:next-steps`**

Similar addition to `commands/next-steps.md`.

- [ ] **Step 4: Add proactive check guidance to graph commands**

In `commands/create-graph.md` and `commands/update-graph.md`, add guidance to check the registry for duplicates when creating new entities.

- [ ] **Step 5: Commit**

```bash
git add commands/sync.md commands/status.md commands/next-steps.md \
       commands/create-graph.md commands/update-graph.md
git commit -m "feat(commands): add /science:sync and staleness nudges"
```

---

## Task 14: Final Integration Test & Cleanup

**Files:**
- All modified files
- Test: `science-tool/tests/test_registry_sync.py` (extend with end-to-end)

- [ ] **Step 1: Run full science-model test suite**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 2: Run full science-tool test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 3: Run ruff check on both packages**

Run: `cd science-model && uv run --frozen ruff check . && cd ../science-tool && uv run --frozen ruff check .`
Expected: No errors

- [ ] **Step 4: Run ruff format on both packages**

Run: `cd science-model && uv run --frozen ruff format . && cd ../science-tool && uv run --frozen ruff format .`
Expected: No formatting changes (or apply them)

- [ ] **Step 5: Run pyright on both packages**

Run: `cd science-model && uv run --frozen pyright && cd ../science-tool && uv run --frozen pyright`
Expected: No type errors

- [ ] **Step 6: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: final cleanup for multi-project sync"
```

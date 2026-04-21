# Multi-Backend Entity Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the 5 ad-hoc entity loaders in `science-tool/src/science_tool/graph/sources.py` into a clean `EntityProvider` abstraction, add the missing `DatapackageDirectoryProvider` (for promoted datasets), and generalize the existing aggregate loader to support per-type aggregate files (the mm30 rare-topics case).

**Architecture:** Three format-driven providers (`MarkdownProvider`, `DatapackageDirectoryProvider`, `AggregateProvider`) coordinated by an `EntityResolver` and an `EntityDiscoveryContext`. Specialized parsers (tasks/models/parameters) keep their direct callsites in `load_project_sources` but each sets `SourceEntity.provider` explicitly. All format-driven extraction funnels through a shared `EntityRecord` schema and `_normalize_record` helper. Behavior preservation enforced by a snapshot regression test that uses a projection excluding new fields.

**Tech Stack:** Python 3.11+, uv, Pydantic, pytest, ruff, pyright. Code lives entirely in `science-tool/`. No `science-model` changes (the unchanged-shape `Entity` continues to populate the markdown provider's records).

**Reference paths used throughout:**
- Spec: `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md` (rev 1.1)
- Existing entity-loading code: `science-tool/src/science_tool/graph/sources.py`
- Health module (touched in step 11): `science-tool/src/science_tool/graph/health.py`
- `Entity` model (read-only — used by MarkdownProvider): `science-model/src/science_model/entities.py`
- `parse_entity_file` (read-only): `science-model/src/science_model/frontmatter.py:177`

**Conventions used in this codebase:**
- All Python invocations: `uv run --frozen <command>`
- Lint: `uv run --frozen ruff check .`
- Format: `uv run --frozen ruff format .`
- Type check: `uv run --frozen pyright`
- Tests: `uv run --frozen pytest <path>`
- Line length: 120 chars

**Key cross-cutting invariants (read before any task):**

- **All paths in this plan are relative to the worktree root** (`/mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/`). The worktree is set up by the executing skill before Task 1.
- **Every commit must keep the existing test suite green.** Run `cd science-tool && uv run --frozen pytest -q` after every task before committing.
- **Snapshot regression** (`test_load_project_sources_regression.py`) uses a `_project_for_snapshot()` helper that excludes the new `provider` and `description` fields. This is the canary; it must stay green across every commit in this plan.
- **Specialized parsers** (`parse_tasks`, `_load_model_sources`, `_load_parameter_sources`) keep their existing direct callsites — DO NOT wrap them in EntityProvider classes.
- **Pre-existing pyright errors** in `science-tool/src/science_tool/cli.py` (CrossImpactRow + PropositionInteractionTerm invariance) and `science-tool/src/science_tool/graph/sources.py` (~19 object→typed assignment errors) are NOT to be fixed in this plan. They predate Spec Y.

**Phases:**
1. Foundation (types module, snapshot fixture, package skeleton)
2. Refactor existing loaders (MarkdownProvider, multi-type AggregateProvider)
3. Integration (switch load_project_sources, global collision check)
4. New fields (provider, description)
5. New capabilities (single-type aggregate, DatapackageDirectoryProvider)
6. Health integration
7. Final cleanup

---

## Phase 1: Foundation

### Task 1.1: Create `graph/source_types.py` with shared types

**Files:**
- Create: `science-tool/src/science_tool/graph/source_types.py`
- Modify: `science-tool/src/science_tool/graph/sources.py` (re-export from new module for back-compat)
- Test: `science-tool/tests/test_source_types.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_source_types.py`:

```python
"""Tests for graph.source_types — the neutral home for SourceEntity, SourceRelation, etc."""
from __future__ import annotations

import pytest


def test_source_types_module_exposes_canonical_types() -> None:
    """The new neutral module exports the types the entity_providers package needs."""
    from science_tool.graph.source_types import (
        EntityIdCollisionError,
        EntityDatapackageInvalidError,
        KnowledgeProfiles,
        SourceEntity,
        SourceRelation,
    )
    # Smoke check: exported symbols are real classes
    assert isinstance(EntityIdCollisionError, type)
    assert isinstance(EntityDatapackageInvalidError, type)
    assert issubclass(EntityIdCollisionError, ValueError)
    assert issubclass(EntityDatapackageInvalidError, ValueError)


def test_sources_module_re_exports_for_back_compat() -> None:
    """Existing consumers `from science_tool.graph.sources import SourceEntity` continue to work."""
    from science_tool.graph.sources import SourceEntity as SourceEntityFromSources
    from science_tool.graph.source_types import SourceEntity as SourceEntityFromTypes
    assert SourceEntityFromSources is SourceEntityFromTypes


def test_entity_id_collision_error_message_includes_sources() -> None:
    from science_tool.graph.source_types import EntityIdCollisionError
    err = EntityIdCollisionError("dataset:x", [("markdown", "doc/datasets/x.md"), ("aggregate", "entities.yaml")])
    msg = str(err)
    assert "dataset:x" in msg
    assert "markdown" in msg
    assert "doc/datasets/x.md" in msg
    assert "aggregate" in msg
    assert "entities.yaml" in msg


def test_entity_datapackage_invalid_error_message_includes_path_and_field() -> None:
    from science_tool.graph.source_types import EntityDatapackageInvalidError
    err = EntityDatapackageInvalidError("data/x/datapackage.yaml", "missing required entity field 'id'")
    msg = str(err)
    assert "data/x/datapackage.yaml" in msg
    assert "missing required entity field 'id'" in msg
```

- [ ] **Step 2: Run failing test**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-tool
uv run --frozen pytest tests/test_source_types.py -v
```

Expected: ImportError on `science_tool.graph.source_types` (module doesn't exist).

- [ ] **Step 3: Read existing definitions to lift**

```bash
sed -n '79,140p' src/science_tool/graph/sources.py
```

You'll see `SourceEntity`, `SourceRelation`, `KnowledgeProfiles` (and `_SourceRecordT` TypeVar). Note the imports they need at the top of `sources.py` (lines 1-31): `pydantic.BaseModel`, `pydantic.Field`, `enum.StrEnum`, the reasoning enum imports (`ClaimLayer`, `EvidenceRole`, `IdentificationStrength`, etc.), `RivalModelPacket`.

- [ ] **Step 4: Create `source_types.py`**

Create `science-tool/src/science_tool/graph/source_types.py`:

```python
"""Shared types consumed by both graph/sources.py and the entity_providers package.

Lifted out of graph/sources.py so the entity_providers package can import these
types without creating an import cycle (entity_providers needs SourceEntity;
sources.py would otherwise need entity_providers for the resolver, closing the loop).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)


class SourceEntity(BaseModel):
    """A canonical entity collected from project source files."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    domain: str | None = None
    confidence: float | None = None
    status: str | None = None
    content_preview: str = ""
    related: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    evidence_role: EvidenceRole | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet: RivalModelPacket | None = None


class SourceRelation(BaseModel):
    """An authored relation collected from structured source files."""

    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_path: str


class KnowledgeProfiles(BaseModel):
    """Selected knowledge profiles for a project."""

    local: str = "local"


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

- [ ] **Step 5: Update `graph/sources.py` to re-export from `source_types`**

In `science-tool/src/science_tool/graph/sources.py`, REMOVE the existing class definitions of `SourceEntity`, `SourceRelation`, `KnowledgeProfiles` (lines ~79-130), and ADD this near the top of the file (after the existing imports, before any class/function defs):

```python
# Re-export shared types from the neutral module for back-compat.
# The canonical home is graph.source_types; existing imports continue to work.
from science_tool.graph.source_types import (
    EntityDatapackageInvalidError,
    EntityIdCollisionError,
    KnowledgeProfiles,
    SourceEntity,
    SourceRelation,
)
```

Keep the `_SourceRecordT = TypeVar("_SourceRecordT", bound=BaseModel)` line where it is — it's only used inside `sources.py`, not lifted.

- [ ] **Step 6: Verify tests pass + no regression**

```bash
uv run --frozen pytest tests/test_source_types.py -v
uv run --frozen pytest -q
uv run --frozen ruff format src/science_tool/graph/source_types.py src/science_tool/graph/sources.py tests/test_source_types.py
```

Expected: all new tests PASS, full suite PASS, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/graph/source_types.py src/science_tool/graph/sources.py tests/test_source_types.py
git commit -m "feat(graph): lift shared types into source_types.py module"
```

---

### Task 1.2: Snapshot regression fixture + checked-in baseline

**Files:**
- Create: `science-tool/tests/fixtures/spec_y_kitchen_sink/` (directory tree)
- Create: `science-tool/tests/fixtures/spec_y_kitchen_sink/snapshot.json` (baseline output)
- Create: `science-tool/tests/test_load_project_sources_regression.py`

This task seeds the canary — the regression baseline that every subsequent commit must keep green.

- [ ] **Step 1: Create the kitchen-sink fixture project**

Create `science-tool/tests/fixtures/spec_y_kitchen_sink/science.yaml`:

```yaml
name: spec-y-kitchen-sink
profile: research
profiles:
  local: local
```

Create the directory structure and files:

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-tool
mkdir -p tests/fixtures/spec_y_kitchen_sink/doc/hypotheses
mkdir -p tests/fixtures/spec_y_kitchen_sink/doc/datasets
mkdir -p tests/fixtures/spec_y_kitchen_sink/doc/topics
mkdir -p tests/fixtures/spec_y_kitchen_sink/specs
mkdir -p tests/fixtures/spec_y_kitchen_sink/tasks
mkdir -p tests/fixtures/spec_y_kitchen_sink/knowledge/sources/local
```

Write each entity file:

`tests/fixtures/spec_y_kitchen_sink/doc/hypotheses/h01.md`:
```markdown
---
id: "hypothesis:h01"
type: "hypothesis"
title: "Test hypothesis"
status: "active"
related: []
source_refs: []
ontology_terms: []
---
A simple hypothesis for testing.
```

`tests/fixtures/spec_y_kitchen_sink/doc/datasets/ds01.md`:
```markdown
---
id: "dataset:ds01"
type: "dataset"
title: "Test dataset"
status: "active"
ontology_terms: []
related: []
source_refs: []
---
A simple dataset for testing.
```

`tests/fixtures/spec_y_kitchen_sink/specs/research-question.md`:
```markdown
---
id: "spec:research-question"
type: "spec"
title: "Research question spec"
status: "active"
related: []
source_refs: []
ontology_terms: []
---
The research question.
```

`tests/fixtures/spec_y_kitchen_sink/tasks/active.md`:
```markdown
## [t001] Test task
- type: research
- priority: P1
- status: active
- created: 2026-04-20

A test task.
```

`tests/fixtures/spec_y_kitchen_sink/knowledge/sources/local/entities.yaml`:
```yaml
entities:
  - canonical_id: "paper:doe2024"
    kind: "paper"
    title: "Doe et al. 2024"
    profile: "local"
    source_path: "knowledge/sources/local/entities.yaml"
```

- [ ] **Step 2: Write the regression test**

Create `science-tool/tests/test_load_project_sources_regression.py`:

```python
"""Snapshot-based regression test for load_project_sources.

The snapshot uses a projection that excludes the new `provider` and `description`
fields (added in steps 7-8 of the multi-backend-entity-resolver plan). This lets
the regression assertion stay byte-identical across every commit in the plan,
even when those fields are intentionally added.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources


FIXTURE = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink"
SNAPSHOT = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink" / "snapshot.json"


def _project_for_snapshot(entities: list) -> list[dict]:
    """Drop fields the spec adds incrementally; the snapshot stays stable across commits."""
    excluded = {"provider", "description"}
    projected: list[dict] = []
    for e in entities:
        d = e.model_dump()
        projected.append({k: v for k, v in d.items() if k not in excluded})
    # Sort by canonical_id for deterministic ordering.
    projected.sort(key=lambda d: d.get("canonical_id", ""))
    return projected


def test_load_project_sources_kitchen_sink_snapshot() -> None:
    sources = load_project_sources(FIXTURE)
    actual = _project_for_snapshot(sources.entities)
    expected = json.loads(SNAPSHOT.read_text())
    assert actual == expected, (
        f"Snapshot regression: load_project_sources output diverged.\n"
        f"To inspect: diff <(echo '{json.dumps(actual, indent=2)}') {SNAPSHOT}\n"
        f"If the diff is intentional, regenerate via:\n"
        f"  python -c 'import json; from pathlib import Path; "
        f"from science_tool.graph.sources import load_project_sources; "
        f"from tests.test_load_project_sources_regression import _project_for_snapshot, FIXTURE, SNAPSHOT; "
        f"SNAPSHOT.write_text(json.dumps(_project_for_snapshot(load_project_sources(FIXTURE).entities), indent=2))'"
    )
```

- [ ] **Step 3: Generate the baseline snapshot**

Run the helper to produce `snapshot.json` from the current (pre-refactor) behavior:

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-tool
uv run --frozen python -c "
import json
from pathlib import Path
from science_tool.graph.sources import load_project_sources

FIXTURE = Path('tests/fixtures/spec_y_kitchen_sink')
SNAPSHOT = FIXTURE / 'snapshot.json'

def _project_for_snapshot(entities):
    excluded = {'provider', 'description'}
    projected = []
    for e in entities:
        d = e.model_dump()
        projected.append({k: v for k, v in d.items() if k not in excluded})
    projected.sort(key=lambda d: d.get('canonical_id', ''))
    return projected

sources = load_project_sources(FIXTURE)
SNAPSHOT.write_text(json.dumps(_project_for_snapshot(sources.entities), indent=2) + '\n')
print(f'wrote {len(sources.entities)} entities to {SNAPSHOT}')
"
```

Expected: prints `wrote 5 entities to ...` (one hypothesis, one dataset, one spec, one task, one paper).

- [ ] **Step 4: Verify the regression test now passes**

```bash
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/spec_y_kitchen_sink/ tests/test_load_project_sources_regression.py
git commit -m "test(graph): kitchen-sink snapshot regression baseline (Spec Y canary)"
```

---

### Task 1.3: `entity_providers/` package skeleton — `EntityDiscoveryContext` + `EntityProvider` ABC

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/__init__.py`
- Create: `science-tool/src/science_tool/graph/entity_providers/base.py`
- Test: `science-tool/tests/test_entity_providers/test_base.py`

- [ ] **Step 1: Write failing test**

```bash
mkdir -p science-tool/tests/test_entity_providers
touch science-tool/tests/test_entity_providers/__init__.py
```

Create `science-tool/tests/test_entity_providers/__init__.py` (empty file).

Create `science-tool/tests/test_entity_providers/test_base.py`:

```python
"""Tests for EntityProvider ABC + EntityDiscoveryContext."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import (
    EntityDiscoveryContext,
    EntityProvider,
)
from science_tool.graph.source_types import SourceEntity


def test_entity_discovery_context_construction() -> None:
    ctx = EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
        active_kinds=None,
        ontology_catalogs=None,
    )
    assert ctx.project_root == Path("/tmp/x")
    assert ctx.project_slug == "x"
    assert ctx.local_profile == "local"


def test_entity_discovery_context_is_frozen() -> None:
    ctx = EntityDiscoveryContext(
        project_root=Path("/tmp/x"), project_slug="x", local_profile="local",
    )
    with pytest.raises(Exception):  # FrozenInstanceError or similar
        ctx.project_slug = "y"  # type: ignore[misc]


def test_entity_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        EntityProvider()  # type: ignore[abstract]


def test_subclass_with_discover_can_instantiate() -> None:
    class FakeProvider(EntityProvider):
        name = "fake"

        def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
            return []

    p = FakeProvider()
    assert p.name == "fake"
    assert p.discover(EntityDiscoveryContext(
        project_root=Path("/tmp/x"), project_slug="x", local_profile="local",
    )) == []
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_base.py -v
```

Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Create the package**

Create `science-tool/src/science_tool/graph/entity_providers/__init__.py` (empty file).

Create `science-tool/src/science_tool/graph/entity_providers/base.py`:

```python
"""EntityDiscoveryContext + EntityProvider abstract base.

The provider abstraction extracted from the existing 5-loader pattern in
graph/sources.py. Each provider implements discover(ctx) and returns a list
of SourceEntity. The resolver coordinates multiple providers; this module
contains only the base definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from science_model.ontologies.schema import OntologyCatalog

from science_tool.graph.source_types import SourceEntity


@dataclass(frozen=True)
class EntityDiscoveryContext:
    """Shared loading state passed to every EntityProvider.

    Carries everything the existing loaders depend on (local_profile, active_kinds,
    ontology_catalogs) so providers can compute profiles, validate kinds, and apply
    catalog-aware behavior without globals or per-provider re-derivation.
    """

    project_root: Path
    project_slug: str
    local_profile: str
    active_kinds: frozenset[str] | None = None
    ontology_catalogs: list["OntologyCatalog"] | None = None


class EntityProvider(ABC):
    """Discovers entities from a particular storage convention.

    Each provider is self-contained: knows where to look, knows how to read
    what it finds, returns ready-to-use SourceEntity objects with the provider
    field set. Stateless across calls (a future cache layer wraps providers).
    """

    name: str  # short human-readable identifier matching SourceEntity.provider

    @abstractmethod
    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        """Walk the filesystem under ctx.project_root and return all entities found."""
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_base.py -v
uv run --frozen pytest -q  # full sweep — must stay green
uv run --frozen ruff format src/science_tool/graph/entity_providers/ tests/test_entity_providers/
```

Expected: new tests PASS, full suite PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/graph/entity_providers/__init__.py src/science_tool/graph/entity_providers/base.py tests/test_entity_providers/__init__.py tests/test_entity_providers/test_base.py
git commit -m "feat(entity-providers): add EntityProvider ABC + EntityDiscoveryContext"
```

---

### Task 1.4: `EntityRecord` schema + `_normalize_record` helper

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/record.py`
- Test: `science-tool/tests/test_entity_providers/test_record.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_entity_providers/test_record.py`:

```python
"""Tests for EntityRecord schema + _normalize_record helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record


def _ctx() -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
    )


def test_entity_record_minimal_construction() -> None:
    r = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
    )
    assert r.canonical_id == "hypothesis:h01"
    assert r.description == ""
    assert r.related == []
    assert r.aliases == []


def test_entity_record_with_description() -> None:
    r = EntityRecord(
        canonical_id="topic:t1",
        kind="topic",
        title="T1",
        source_path="doc/topics/topics.json",
        description="Some prose about t1.",
    )
    assert r.description == "Some prose about t1."


def test_normalize_record_produces_source_entity_with_provider_set() -> None:
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test hypothesis",
        source_path="doc/hypotheses/h01.md",
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    assert se.canonical_id == "hypothesis:h01"
    assert se.kind == "hypothesis"
    assert se.title == "Test hypothesis"
    assert se.provider == "markdown"


def test_normalize_record_canonicalizes_paper_ids() -> None:
    """kind=='paper' triggers canonical_paper_id() rewriting."""
    record = EntityRecord(
        canonical_id="paper:DOE2024",  # uppercase prefix gets normalized
        kind="paper",
        title="Doe 2024",
        source_path="entities.yaml",
    )
    se = _normalize_record(record, _ctx(), provider_name="aggregate")
    # canonical_paper_id lowercases — exact behavior verified by existing tests; here we just
    # confirm the normalizer applies it. The prefix should be lowercase post-normalization.
    assert se.canonical_id.startswith("paper:")
    assert se.canonical_id == se.canonical_id.lower()


def test_normalize_record_derives_aliases() -> None:
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
        aliases=["H01"],
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    # _derive_aliases adds the canonical_id + lowercase variants alongside the user-provided ones.
    assert "H01" in se.aliases
    assert se.canonical_id in se.aliases or se.canonical_id.lower() in se.aliases


def test_normalize_record_defaults_profile_when_unset() -> None:
    """When EntityRecord.profile is None, the normalizer applies _default_profile_for_kind."""
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
        profile=None,
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    # The default for hypothesis without active_kinds/catalogs is the local profile.
    assert se.profile == "local"
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_record.py -v
```

Expected: ImportError on `record` module.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/entity_providers/record.py`:

```python
"""EntityRecord — normalized input shape for format-driven providers.

All three providers (MarkdownProvider, DatapackageDirectoryProvider, AggregateProvider)
extract raw records into this shape, then funnel them through `_normalize_record` to
produce SourceEntity. This keeps paper-ID canonicalization, alias derivation, profile
defaulting, and kind validation in ONE place rather than duplicated per provider.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.source_types import SourceEntity


class EntityRecord(BaseModel):
    """Normalized input record produced by a provider's extraction step.

    Required: canonical_id, kind, title, source_path. Everything else optional.
    The `extra` field is a dict for provider-specific passthrough fields (reasoning
    metadata, dataset access blocks, etc.) that the normalizer can lift selectively.
    """

    canonical_id: str
    kind: str
    title: str
    source_path: str
    description: str = ""
    profile: str | None = None
    domain: str | None = None
    related: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    status: str | None = None
    confidence: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def _derive_aliases(canonical_id: str, raw_aliases: list[str]) -> list[str]:
    """Mirror the existing _derive_aliases logic from graph/sources.py."""
    aliases: list[str] = []
    seen: set[str] = set()
    for alias in (canonical_id, canonical_id.lower(), *raw_aliases):
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _default_profile_for_kind(
    kind: str,
    *,
    local_profile: str,
    active_kinds: frozenset[str] | None,
    ontology_catalogs: list | None,
) -> str:
    """Default profile resolution: kinds in core profile → 'core'; everything else → local."""
    # Core kinds live in CORE_PROFILE; other kinds default to the project's local profile.
    # This mirrors the existing _default_profile_for_kind in graph/sources.py.
    from science_model.profiles import CORE_PROFILE
    core_kind_names = frozenset(k.name for k in CORE_PROFILE.entity_kinds)
    if kind in core_kind_names:
        return "core"
    return local_profile


def _normalize_record(
    record: EntityRecord,
    ctx: EntityDiscoveryContext,
    *,
    provider_name: str,
) -> SourceEntity:
    """Apply shared normalization rules and produce a SourceEntity.

    Single source of truth for:
    - Paper-ID canonicalization (kind == "paper" → canonical_paper_id)
    - Profile defaulting (uses ctx.local_profile + ctx.active_kinds + ctx.ontology_catalogs)
    - Alias derivation
    - provider field set to provider_name
    """
    canonical_id = record.canonical_id
    if record.kind == "paper":
        canonical_id = canonical_paper_id(canonical_id)

    profile = record.profile or _default_profile_for_kind(
        record.kind,
        local_profile=ctx.local_profile,
        active_kinds=ctx.active_kinds,
        ontology_catalogs=ctx.ontology_catalogs,
    )

    return SourceEntity(
        canonical_id=canonical_id,
        kind=record.kind,
        title=record.title,
        profile=profile,
        source_path=record.source_path,
        domain=record.domain,
        confidence=record.confidence,
        status=record.status,
        related=record.related,
        blocked_by=record.blocked_by,
        source_refs=record.source_refs,
        ontology_terms=record.ontology_terms,
        same_as=record.same_as,
        aliases=_derive_aliases(canonical_id, record.aliases),
        # provider + description come from the record/provider context — added in steps 7-8.
    )
```

Note: `provider_name` parameter is captured but NOT yet written into `SourceEntity` (the field doesn't exist on SourceEntity until Task 4.1). The parameter is in place so later tasks can wire it without changing the helper's signature.

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_record.py -v
uv run --frozen pytest -q
```

Expected: new tests PASS (with one caveat — the `provider` assertion in `test_normalize_record_produces_source_entity_with_provider_set` will FAIL because `SourceEntity.provider` doesn't exist yet). Mark that one as `pytest.mark.xfail(reason="provider field added in Task 4.1")`:

Modify the test:

```python
@pytest.mark.xfail(reason="SourceEntity.provider added in Task 4.1; placeholder until then")
def test_normalize_record_produces_source_entity_with_provider_set() -> None:
    ...
```

Re-run:

```bash
uv run --frozen pytest tests/test_entity_providers/test_record.py -v
```

Expected: 5 PASS, 1 XFAIL.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/entity_providers/record.py tests/test_entity_providers/test_record.py
git add src/science_tool/graph/entity_providers/record.py tests/test_entity_providers/test_record.py
git commit -m "feat(entity-providers): add EntityRecord schema + _normalize_record helper"
```

---

### Task 1.5: `EntityResolver` + `default_providers()`

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/resolver.py`
- Test: `science-tool/tests/test_entity_providers/test_resolver.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_entity_providers/test_resolver.py`:

```python
"""Tests for EntityResolver — coordinates multiple providers, merges by canonical_id."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.resolver import EntityResolver, default_providers
from science_tool.graph.source_types import EntityIdCollisionError, SourceEntity


def _ctx() -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=Path("/tmp/x"), project_slug="x", local_profile="local",
    )


def _entity(canonical_id: str, source_path: str) -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id, kind="hypothesis", title=canonical_id,
        profile="local", source_path=source_path,
    )


class _StaticProvider(EntityProvider):
    """Test double — returns a fixed list."""

    def __init__(self, name: str, entities: list[SourceEntity]) -> None:
        self.name = name
        self._entities = entities

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        return self._entities


def test_empty_provider_list_yields_empty_result() -> None:
    resolver = EntityResolver([])
    assert resolver.discover(_ctx()) == []


def test_single_provider_passes_through() -> None:
    p = _StaticProvider("a", [_entity("hypothesis:h1", "doc/hypotheses/h1.md")])
    resolver = EntityResolver([p])
    out = resolver.discover(_ctx())
    assert len(out) == 1
    assert out[0].canonical_id == "hypothesis:h1"


def test_multiple_providers_concatenated() -> None:
    p1 = _StaticProvider("a", [_entity("hypothesis:h1", "h1.md")])
    p2 = _StaticProvider("b", [_entity("dataset:d1", "d1.md")])
    resolver = EntityResolver([p1, p2])
    out = resolver.discover(_ctx())
    ids = {e.canonical_id for e in out}
    assert ids == {"hypothesis:h1", "dataset:d1"}


def test_collision_across_providers_raises() -> None:
    p1 = _StaticProvider("a", [_entity("hypothesis:h1", "via-a.md")])
    p2 = _StaticProvider("b", [_entity("hypothesis:h1", "via-b.md")])
    resolver = EntityResolver([p1, p2])
    with pytest.raises(EntityIdCollisionError) as exc_info:
        resolver.discover(_ctx())
    msg = str(exc_info.value)
    assert "hypothesis:h1" in msg
    assert "a: via-a.md" in msg
    assert "b: via-b.md" in msg


def test_collision_within_one_provider_raises() -> None:
    p = _StaticProvider("a", [
        _entity("hypothesis:h1", "h1.md"),
        _entity("hypothesis:h1", "h1-dup.md"),
    ])
    resolver = EntityResolver([p])
    with pytest.raises(EntityIdCollisionError):
        resolver.discover(_ctx())


def test_default_providers_returns_three_v1_implementations() -> None:
    providers = default_providers()
    names = [p.name for p in providers]
    assert names == ["markdown", "datapackage-directory", "aggregate"]
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_resolver.py -v
```

Expected: ImportError on `resolver` module + `default_providers`.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/entity_providers/resolver.py`:

```python
"""EntityResolver — coordinates a list of EntityProvider implementations.

Runs all providers, concatenates their outputs, raises EntityIdCollisionError
on duplicate canonical_ids. The collision error names BOTH provider sources so
debugging is direct.
"""

from __future__ import annotations

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


def default_providers() -> list[EntityProvider]:
    """The set of providers active in every project. No config required.

    Function (not constant) so tests can construct ad-hoc providers without
    monkey-patching, and so the import order doesn't force eager construction.
    """
    from science_tool.graph.entity_providers.markdown import MarkdownProvider
    from science_tool.graph.entity_providers.datapackage_directory import DatapackageDirectoryProvider
    from science_tool.graph.entity_providers.aggregate import AggregateProvider
    return [
        MarkdownProvider(),
        DatapackageDirectoryProvider(),
        AggregateProvider(),
    ]
```

Note: `default_providers()` references three classes that DON'T EXIST YET (created in Phase 2 + Phase 5). The function will fail at runtime if called now. The test `test_default_providers_returns_three_v1_implementations` will FAIL until those classes exist. Mark it xfail:

Update the test:

```python
@pytest.mark.xfail(reason="MarkdownProvider/DatapackageDirectoryProvider/AggregateProvider added in later tasks")
def test_default_providers_returns_three_v1_implementations() -> None:
    ...
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_resolver.py -v
uv run --frozen pytest -q
```

Expected: 5 PASS, 1 XFAIL.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/entity_providers/resolver.py tests/test_entity_providers/test_resolver.py
git add src/science_tool/graph/entity_providers/resolver.py tests/test_entity_providers/test_resolver.py
git commit -m "feat(entity-providers): add EntityResolver + default_providers factory"
```

---

## Phase 2: Refactor existing loaders

### Task 2.1: `MarkdownProvider` (Path 1 — invisible behavior)

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/markdown.py`
- Test: `science-tool/tests/test_entity_providers/test_markdown_provider.py`

- [ ] **Step 1: Read the existing implementation**

```bash
sed -n '245,305p' src/science_tool/graph/sources.py
```

You'll see `_load_markdown_entities` — the function being refactored. The provider preserves its behavior end-to-end.

- [ ] **Step 2: Write failing test**

Create `science-tool/tests/test_entity_providers/test_markdown_provider.py`:

```python
"""Tests for MarkdownProvider — behavior matches existing _load_markdown_entities."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.markdown import MarkdownProvider


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=root, project_slug=root.name, local_profile="local",
    )


def test_markdown_provider_name_is_markdown() -> None:
    assert MarkdownProvider().name == "markdown"


def test_discovers_entities_under_default_scan_roots(tmp_path: Path) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nProse.\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    ids = [e.canonical_id for e in out]
    assert "hypothesis:h1" in ids


def test_discovers_under_specs_root(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir(parents=True)
    (tmp_path / "specs" / "research-question.md").write_text(
        '---\nid: "spec:rq"\ntype: "spec"\ntitle: "RQ"\n---\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "spec:rq" for e in out)


def test_discovers_under_research_packages_root(tmp_path: Path) -> None:
    rp = tmp_path / "research" / "packages" / "lens" / "rp1"
    rp.mkdir(parents=True)
    (rp / "research-package.md").write_text(
        '---\nid: "research-package:rp1"\ntype: "research-package"\ntitle: "RP1"\n---\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "research-package:rp1" for e in out)


def test_returns_empty_when_no_scan_roots_exist(tmp_path: Path) -> None:
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert out == []


def test_custom_scan_roots_are_honored(tmp_path: Path) -> None:
    (tmp_path / "custom" / "hypotheses").mkdir(parents=True)
    (tmp_path / "custom" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    p = MarkdownProvider(scan_roots=["custom"])
    out = p.discover(_ctx(tmp_path))
    assert any(e.canonical_id == "hypothesis:h1" for e in out)
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_markdown_provider.py -v
```

Expected: ImportError on `markdown` module.

- [ ] **Step 4: Implement**

Create `science-tool/src/science_tool/graph/entity_providers/markdown.py`:

```python
"""MarkdownProvider — refactor of the existing _load_markdown_entities loader.

Walks the configured scan roots for *.md files; uses parse_entity_file to
extract Entity; lifts each into an EntityRecord and runs _normalize_record.
Behavior matches existing _load_markdown_entities (verified by the snapshot
regression test).
"""

from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import parse_entity_file, parse_frontmatter

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record
from science_tool.graph.source_types import SourceEntity


class MarkdownProvider(EntityProvider):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        # Roots relative to project_root. Defaults match the existing convention.
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
                entities.append(_normalize_record(record, ctx, provider_name=self.name))
        return entities

    def _extract_record(self, path: Path, entity, ctx: EntityDiscoveryContext) -> EntityRecord:
        """Build EntityRecord from the parsed Entity. Mirrors what _load_markdown_entities did inline."""
        try:
            rel_path = str(path.relative_to(ctx.project_root))
        except ValueError:
            rel_path = str(path)
        # Pull aliases from frontmatter (parse_frontmatter is cheap; the parse_entity_file
        # call above already opened the file once but doesn't return raw frontmatter).
        raw_aliases: list[str] = []
        fm_result = parse_frontmatter(path)
        if fm_result is not None:
            fm, _ = fm_result
            if isinstance(fm.get("aliases"), list):
                raw_aliases = [str(a) for a in fm["aliases"]]
        return EntityRecord(
            canonical_id=entity.canonical_id,
            kind=entity.type.value,
            title=entity.title,
            source_path=rel_path,
            profile=None,  # let normalizer default
            domain=entity.domain,
            related=list(entity.related or []),
            source_refs=list(entity.source_refs or []),
            ontology_terms=list(entity.ontology_terms or []),
            aliases=raw_aliases,
            same_as=list(entity.same_as or []),
            status=entity.status,
            confidence=entity.confidence,
            extra={},  # reasoning metadata wired in step 7+; stays empty for now
        )
```

- [ ] **Step 5: Verify all targeted tests + regression snapshot still green**

```bash
uv run --frozen pytest tests/test_entity_providers/test_markdown_provider.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
uv run --frozen pytest -q
```

Expected: all PASS, snapshot still green (this task doesn't touch `load_project_sources`, so its output is identical).

- [ ] **Step 6: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/entity_providers/markdown.py tests/test_entity_providers/test_markdown_provider.py
git add src/science_tool/graph/entity_providers/markdown.py tests/test_entity_providers/test_markdown_provider.py
git commit -m "feat(entity-providers): add MarkdownProvider (refactor of _load_markdown_entities)"
```

---

### Task 2.2: `AggregateProvider` (multi-type only — Path 2)

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/aggregate.py`
- Test: `science-tool/tests/test_entity_providers/test_aggregate_provider.py`

- [ ] **Step 1: Read the existing implementation**

```bash
sed -n '341,400p' src/science_tool/graph/sources.py
```

`_load_structured_entities` reads `entities.yaml` from the local-profile sources dir. Multi-type — each entry has `kind:` field.

- [ ] **Step 2: Write failing test**

Create `science-tool/tests/test_entity_providers/test_aggregate_provider.py`:

```python
"""Tests for AggregateProvider — multi-type aggregate (entities.yaml) for Phase 2."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.entity_providers.aggregate import AggregateProvider
from science_tool.graph.entity_providers.base import EntityDiscoveryContext


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=root, project_slug=root.name, local_profile="local",
    )


def test_aggregate_provider_name_is_aggregate() -> None:
    assert AggregateProvider().name == "aggregate"


def test_returns_empty_when_no_entities_yaml(tmp_path: Path) -> None:
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert out == []


def test_loads_multi_type_entries_from_entities_yaml(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({
        "entities": [
            {"canonical_id": "paper:doe2024", "kind": "paper", "title": "Doe 2024", "profile": "local"},
            {"canonical_id": "concept:c1", "kind": "concept", "title": "C1", "profile": "local"},
        ]
    }), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    # Note: paper IDs are canonicalized — exact value depends on canonical_paper_id logic.
    assert any("paper:" in i for i in ids)
    assert "concept:c1" in ids


def test_skips_non_dict_entries_silently(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({
        "entities": [
            "not a dict",
            {"canonical_id": "concept:c1", "kind": "concept", "title": "C1", "profile": "local"},
            42,
        ]
    }), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    assert ids == {"concept:c1"}


def test_skips_when_top_level_not_a_list(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": "not-a-list"}), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert out == []
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_aggregate_provider.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement (multi-type only — single-type added in Task 5.1)**

Create `science-tool/src/science_tool/graph/entity_providers/aggregate.py`:

```python
"""AggregateProvider — refactor of the existing _load_structured_entities loader.

Multi-type aggregate (entities.yaml): one file lists papers, concepts, etc., each
entry has a `kind:` field. Single-type aggregate (doc/<plural>/<plural>.{json,yaml})
is added in Task 5.1.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record
from science_tool.graph.source_types import SourceEntity


def _local_profile_sources_dir(project_root: Path, *, local_profile: str) -> Path:
    """Mirror the existing helper from graph/sources.py."""
    return project_root / "knowledge" / "sources" / local_profile


class AggregateProvider(EntityProvider):
    name = "aggregate"

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        # Convention 1: multi-type aggregate (existing entities.yaml)
        entities.extend(self._load_multi_type_aggregate(ctx))
        # Convention 2: single-type aggregate added in Task 5.1
        return entities

    def _load_multi_type_aggregate(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities_path = _local_profile_sources_dir(
            ctx.project_root, local_profile=ctx.local_profile
        ) / "entities.yaml"
        if not entities_path.is_file():
            return []
        try:
            data = yaml.safe_load(entities_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return []
        items = data.get("entities") or []
        if not isinstance(items, list):
            return []
        try:
            rel_path = str(entities_path.relative_to(ctx.project_root))
        except ValueError:
            rel_path = str(entities_path)
        results: list[SourceEntity] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            record = self._record_from_dict(raw, kind=raw.get("kind"), source_path=rel_path)
            if record is None:
                continue
            results.append(_normalize_record(record, ctx, provider_name=self.name))
        return results

    def _record_from_dict(
        self,
        raw: dict,
        *,
        kind: str | None,
        source_path: str,
    ) -> EntityRecord | None:
        """Build an EntityRecord from an aggregate-entry dict; return None if invalid."""
        canonical_id = str(raw.get("canonical_id") or raw.get("id") or "")
        kind_str = str(raw.get("kind") or kind or "")
        title = str(raw.get("title") or "")
        if not canonical_id or not kind_str or not title:
            return None
        try:
            return EntityRecord(
                canonical_id=canonical_id,
                kind=kind_str,
                title=title,
                source_path=source_path,
                description=str(raw.get("description") or ""),
                profile=raw.get("profile"),
                domain=raw.get("domain"),
                status=raw.get("status"),
                related=list(raw.get("related") or []),
                source_refs=list(raw.get("source_refs") or []),
                ontology_terms=list(raw.get("ontology_terms") or []),
                aliases=list(raw.get("aliases") or []),
                same_as=list(raw.get("same_as") or []),
                blocked_by=list(raw.get("blocked_by") or []),
                extra={
                    k: v for k, v in raw.items()
                    if k not in {
                        "canonical_id", "id", "kind", "title", "description", "profile",
                        "domain", "status", "related", "source_refs", "ontology_terms",
                        "aliases", "same_as", "blocked_by",
                    }
                },
            )
        except Exception:
            return None
```

- [ ] **Step 5: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_aggregate_provider.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
uv run --frozen pytest -q
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/entity_providers/aggregate.py tests/test_entity_providers/test_aggregate_provider.py
git add src/science_tool/graph/entity_providers/aggregate.py tests/test_entity_providers/test_aggregate_provider.py
git commit -m "feat(entity-providers): add AggregateProvider (multi-type entities.yaml refactor)"
```

---

## Phase 3: Integration

### Task 3.1: Switch `load_project_sources` to use `EntityResolver` + global collision check

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Test: `science-tool/tests/test_load_project_sources_global_collision.py`

This is the load-bearing change. The existing `_load_markdown_entities` and `_load_structured_entities` callsites are replaced with the resolver. Specialized parsers stay direct callsites. A new global collision check covers everything.

- [ ] **Step 1: Write failing test for the global collision**

Create `science-tool/tests/test_load_project_sources_global_collision.py`:

```python
"""Tests for the global collision check in load_project_sources."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.source_types import EntityIdCollisionError


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text("name: collide\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_no_collision_no_error(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    sources = load_project_sources(tmp_path)
    assert any(e.canonical_id == "hypothesis:h1" for e in sources.entities)


def test_collision_between_markdown_and_aggregate_raises(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "hypothesis:h1"\n    kind: "hypothesis"\n    title: "H1 dup"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    assert "hypothesis:h1" in str(exc_info.value)


def test_collision_between_resolver_and_specialized_parser_raises(tmp_path: Path) -> None:
    """A markdown entity and a task with the same canonical_id collide globally."""
    _seed_project(tmp_path)
    # Markdown entity at task:t01.
    (tmp_path / "doc").mkdir(parents=True)
    (tmp_path / "doc" / "task-t01.md").write_text(
        '---\nid: "task:t01"\ntype: "task"\ntitle: "T01 from markdown"\n---\n',
        encoding="utf-8",
    )
    # Task-DSL entity also at task:t01.
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        '## [t01] T01 from task DSL\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    assert "task:t01" in str(exc_info.value)
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_load_project_sources_global_collision.py -v
```

Expected: the cross-resolver test may or may not pass (resolver-internal collisions already work), but the resolver-to-specialized test FAILS (no global check exists yet).

- [ ] **Step 3: Refactor `load_project_sources`**

In `science-tool/src/science_tool/graph/sources.py`, find the existing `load_project_sources` function (line 139). Locate the block around lines 158-185 that does:

```python
entities.extend(_load_markdown_entities(project_root, [paths.doc_dir, paths.specs_dir, project_root / "research" / "packages"], ...))
# ...
entities.extend(_load_structured_entities(project_root, ...))
```

Replace those two `entities.extend(...)` calls with a single resolver call. The exact patch:

```python
# === BEFORE (delete) ===
entities.extend(
    _load_markdown_entities(
        project_root,
        [paths.doc_dir, paths.specs_dir, project_root / "research" / "packages"],
        local_profile=local_profile,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
)
# ... (intervening _load_task_entities call STAYS) ...
entities.extend(
    _load_structured_entities(
        project_root,
        local_profile=local_profile,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
)

# === AFTER (insert) ===
from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.resolver import EntityResolver, default_providers

ctx = EntityDiscoveryContext(
    project_root=project_root,
    project_slug=project_root.name,
    local_profile=local_profile,
    active_kinds=active_kinds,
    ontology_catalogs=ontology_catalogs,
)
resolver = EntityResolver(default_providers())
entities.extend(resolver.discover(ctx))
# ... (intervening _load_task_entities call STAYS) ...
# (no second `entities.extend(_load_structured_entities(...))` — folded into resolver via AggregateProvider)
```

The order MUST keep `_load_task_entities` BEFORE the resolver — check the existing source. Specifically:
1. Resolver runs (covers markdown + aggregate; eventually datapackage-directory).
2. Specialized parsers run after (tasks, then models, then parameters).
3. Final global collision check.

Now add the global collision check at the END of the function, just before the existing `relations = _load_structured_relations(...)` line:

```python
# Final global collision check across resolver + specialized parsers.
seen: dict[str, list[tuple[str, str]]] = {}
for e in entities:
    # provider field doesn't exist yet (added in Task 4.1) — fall back to "unknown"
    provider_name = getattr(e, "provider", "unknown")
    seen.setdefault(e.canonical_id, []).append((provider_name, e.source_path))
collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
if collisions:
    cid, sources = next(iter(collisions.items()))
    raise EntityIdCollisionError(cid, sources)
```

Optional: REMOVE the now-unused `_load_markdown_entities` and `_load_structured_entities` functions from `sources.py` (they're replaced by providers). Or leave them in place as DEAD code for one commit and remove in a follow-up; prefer remove-now to keep the diff focused.

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_load_project_sources_global_collision.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
uv run --frozen pytest -q
```

Expected: collision tests PASS, regression snapshot PASS (resolver output equals previous loader output under the projection), full suite PASS.

If the snapshot regression FAILS, the resolver's output differs from the original loaders' output — investigate (most common cause: ordering of entities; the snapshot sorts by `canonical_id`, so order alone shouldn't matter; check field-by-field).

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/sources.py tests/test_load_project_sources_global_collision.py
git add src/science_tool/graph/sources.py tests/test_load_project_sources_global_collision.py
git commit -m "feat(graph): switch load_project_sources to EntityResolver + global collision check"
```

---

## Phase 4: New fields

### Task 4.1: Add `SourceEntity.provider` field (required, no default) + update every loader

**Files:**
- Modify: `science-tool/src/science_tool/graph/source_types.py`
- Modify: `science-tool/src/science_tool/graph/entity_providers/record.py` (`_normalize_record`)
- Modify: `science-tool/src/science_tool/graph/sources.py` (specialized parsers)
- Modify: existing tests where `SourceEntity` is constructed (likely a few — search and update)
- Test: `science-tool/tests/test_entity_providers/test_provider_field.py`

- [ ] **Step 1: Locate every `SourceEntity(` construction site**

```bash
grep -rn "SourceEntity(" src/ tests/ | head -20
```

You'll find construction in: `_load_task_entities`, `_load_structured_entities` (no longer called but may still exist), `_load_model_sources`, `_load_parameter_sources`, plus tests. Each needs `provider=` added.

- [ ] **Step 2: Write failing test**

Create `science-tool/tests/test_entity_providers/test_provider_field.py`:

```python
"""Tests for the SourceEntity.provider field — every loader sets it explicitly."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: prov\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_markdown_provider_sets_markdown(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n', encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "hypothesis:h1"]
    assert len(es) == 1
    assert es[0].provider == "markdown"


def test_aggregate_provider_sets_aggregate(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c1"\n    kind: "concept"\n    title: "C1"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c1"]
    assert len(es) == 1
    assert es[0].provider == "aggregate"


def test_task_specialized_parser_sets_task(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        '## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "task:t01"]
    assert len(es) == 1
    assert es[0].provider == "task"


def test_model_source_specialized_parser_sets_model(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "models.yaml").write_text(
        'models:\n  - canonical_id: "model:m1"\n    title: "M1"\n    profile: "local"\n    source_path: "knowledge/sources/local/models.yaml"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "model:m1"]
    assert len(es) == 1
    assert es[0].provider == "model"


def test_parameter_source_specialized_parser_sets_parameter(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "parameters.yaml").write_text(
        'parameters:\n  - canonical_id: "parameter:p1"\n    title: "P1"\n    symbol: "p"\n    profile: "local"\n    source_path: "knowledge/sources/local/parameters.yaml"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "parameter:p1"]
    assert len(es) == 1
    assert es[0].provider == "parameter"


def test_provider_field_is_required(tmp_path: Path) -> None:
    """SourceEntity construction without provider is a Pydantic error."""
    from science_tool.graph.source_types import SourceEntity
    with pytest.raises(Exception):  # pydantic.ValidationError
        SourceEntity(canonical_id="x:1", kind="x", title="x", profile="local", source_path="x.md")
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_provider_field.py -v
```

Expected: most tests FAIL (provider field doesn't exist yet OR loaders don't set it).

- [ ] **Step 4: Add `provider` field to `SourceEntity`**

In `science-tool/src/science_tool/graph/source_types.py`, add the field:

```python
class SourceEntity(BaseModel):
    """A canonical entity collected from project source files."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    provider: str  # NEW — required, no default. Six v1 values: markdown, aggregate, datapackage-directory, task, model, parameter.
    # ... existing optional fields ...
```

- [ ] **Step 5: Update `_normalize_record` to populate `provider`**

In `science-tool/src/science_tool/graph/entity_providers/record.py`, modify `_normalize_record` to pass `provider=provider_name` into the SourceEntity construction. Update the existing return:

```python
    return SourceEntity(
        canonical_id=canonical_id,
        kind=record.kind,
        title=record.title,
        profile=profile,
        source_path=record.source_path,
        provider=provider_name,  # NEW — set explicitly per provider
        domain=record.domain,
        # ... rest unchanged ...
    )
```

Remove the previously-added xfail decorator from `test_normalize_record_produces_source_entity_with_provider_set` in `tests/test_entity_providers/test_record.py`.

- [ ] **Step 6: Update specialized parsers to set `provider` explicitly**

In `science-tool/src/science_tool/graph/sources.py`:

a) `_load_task_entities` — find the `SourceEntity(...)` construction and add `provider="task"`.
b) `_load_model_sources` — find both `SourceEntity(...)` construction sites and add `provider="model"`.
c) `_load_parameter_sources` — find both and add `provider="parameter"`.

Example for `_load_task_entities`:

```python
entities.append(
    SourceEntity(
        canonical_id=canonical_id,
        kind="task",
        title=task.title,
        profile=_default_profile_for_kind("task", local_profile=local_profile, ...),
        source_path=rel_path,
        provider="task",  # NEW
        status=task.status,
        content_preview=task.description,
        related=task.related,
        blocked_by=task.blocked_by,
        aliases=_derive_aliases(canonical_id, [task.id, task.id.upper()]),
    )
)
```

Update `_load_model_sources` similarly with `provider="model"`, and `_load_parameter_sources` with `provider="parameter"`.

- [ ] **Step 7: Update the global collision check in `load_project_sources`**

The fallback `getattr(e, "provider", "unknown")` from Task 3.1 can now be a direct attribute access:

```python
seen.setdefault(e.canonical_id, []).append((e.provider, e.source_path))
```

- [ ] **Step 8: Update other tests that construct `SourceEntity` directly**

```bash
grep -rn "SourceEntity(" tests/ | grep -v "provider="
```

For each match, add `provider="..."` (use a sensible default like `provider="markdown"` for tests where the value doesn't matter).

The tests in `test_resolver.py`'s `_StaticProvider` and the `_entity()` helper need `provider="..."` added too. Update `_entity()`:

```python
def _entity(canonical_id: str, source_path: str, provider: str = "markdown") -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id, kind="hypothesis", title=canonical_id,
        profile="local", source_path=source_path, provider=provider,
    )
```

- [ ] **Step 9: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_provider_field.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v  # snapshot must STILL pass (projection excludes provider)
uv run --frozen pytest -q
```

Expected: all PASS. If snapshot fails, the projection is missing `provider` from the excluded set — verify `_project_for_snapshot` definition.

- [ ] **Step 10: Commit**

```bash
uv run --frozen ruff format src/ tests/
git add src/science_tool/graph/source_types.py src/science_tool/graph/entity_providers/record.py src/science_tool/graph/sources.py tests/test_entity_providers/
git commit -m "feat(graph): require explicit provider on every SourceEntity (six legal values)"
```

---

### Task 4.2: Add `SourceEntity.description` field + per-provider sourcing

**Files:**
- Modify: `science-tool/src/science_tool/graph/source_types.py`
- Modify: `science-tool/src/science_tool/graph/entity_providers/record.py`
- Modify: `science-tool/src/science_tool/graph/entity_providers/markdown.py`
- Modify: `science-tool/src/science_tool/graph/sources.py` (task parser)
- Test: `science-tool/tests/test_entity_providers/test_description_field.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_entity_providers/test_description_field.py`:

```python
"""Tests for the SourceEntity.description field — per-provider prose sourcing."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: desc\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_markdown_entity_with_body_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nThis is the prose body.\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "hypothesis:h1"]
    assert es[0].description.strip() == "This is the prose body."


def test_aggregate_entry_with_description_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c1"\n    kind: "concept"\n    title: "C1"\n    profile: "local"\n    description: "Aggregate-entry prose."\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c1"]
    assert es[0].description == "Aggregate-entry prose."


def test_aggregate_entry_without_description_defaults_empty(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c2"\n    kind: "concept"\n    title: "C2"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c2"]
    assert es[0].description == ""


def test_task_description_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        '## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nTask prose body.\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources
    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "task:t01"]
    assert es[0].description == "Task prose body."


def test_description_field_defaults_empty_string() -> None:
    from science_tool.graph.source_types import SourceEntity
    se = SourceEntity(
        canonical_id="x:1", kind="x", title="x", profile="local", source_path="x.md", provider="markdown",
    )
    assert se.description == ""
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_entity_providers/test_description_field.py -v
```

Expected: most FAIL (field doesn't exist yet).

- [ ] **Step 3: Add `description` field to `SourceEntity`**

In `science-tool/src/science_tool/graph/source_types.py`, after the `provider` field:

```python
    description: str = ""  # NEW — entity prose body. Defaults empty.
```

- [ ] **Step 4: Wire description through `_normalize_record`**

In `science-tool/src/science_tool/graph/entity_providers/record.py`, update the `SourceEntity` construction in `_normalize_record`:

```python
    return SourceEntity(
        # ... existing fields ...
        description=record.description,  # NEW — pass through from record
    )
```

`EntityRecord` already has the `description` field from Task 1.4, so this just plumbs it through.

- [ ] **Step 5: Wire description through `MarkdownProvider`**

In `science-tool/src/science_tool/graph/entity_providers/markdown.py`, update `_extract_record` to populate description from `entity.content`:

```python
        return EntityRecord(
            canonical_id=entity.canonical_id,
            kind=entity.type.value,
            title=entity.title,
            description=entity.content or "",  # NEW — pull from Entity.content (markdown body)
            source_path=rel_path,
            # ... rest unchanged ...
        )
```

- [ ] **Step 6: Wire description through specialized task parser**

In `science-tool/src/science_tool/graph/sources.py`, find the `_load_task_entities` function (line 306) and update its `SourceEntity(...)` call to add `description`:

```python
SourceEntity(
    # ... existing fields ...
    provider="task",
    description=task.description,  # NEW — same source as content_preview
    content_preview=task.description,
    # ... rest unchanged ...
)
```

(Models and parameters: leave description empty for now — no source.)

- [ ] **Step 7: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_description_field.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v  # snapshot must STILL pass
uv run --frozen pytest -q
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
uv run --frozen ruff format src/ tests/
git add src/ tests/test_entity_providers/test_description_field.py
git commit -m "feat(graph): SourceEntity.description field + per-provider prose sourcing"
```

---

## Phase 5: New capabilities

### Task 5.1: AggregateProvider single-type aggregate (Path 3 — mm30 case)

**Files:**
- Modify: `science-tool/src/science_tool/graph/entity_providers/aggregate.py`
- Modify: `science-tool/tests/test_entity_providers/test_aggregate_provider.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_entity_providers/test_aggregate_provider.py`:

```python
import json


def test_single_type_aggregate_json_loads_topics(tmp_path: Path) -> None:
    """doc/topics/topics.json with multiple entries produces multiple topic entities."""
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.json").write_text(json.dumps([
        {"id": "topic:rare-x", "title": "Rare X"},
        {"id": "topic:rare-y", "title": "Rare Y", "description": "Some prose."},
    ]), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    assert ids == {"topic:rare-x", "topic:rare-y"}
    rare_y = next(e for e in out if e.canonical_id == "topic:rare-y")
    assert rare_y.description == "Some prose."
    assert rare_y.kind == "topic"


def test_single_type_aggregate_yaml_works_same_as_json(tmp_path: Path) -> None:
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.yaml").write_text(yaml.safe_dump([
        {"id": "topic:rare-z", "title": "Rare Z"},
    ]), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "topic:rare-z" for e in out)


def test_single_type_aggregate_kind_inferred_from_filename(tmp_path: Path) -> None:
    """topics.json → kind: topic, datasets.json → kind: dataset, etc."""
    ds_dir = tmp_path / "doc" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "datasets.json").write_text(json.dumps([
        {"id": "dataset:agg1", "title": "Aggregate dataset 1"},
    ]), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    es = [e for e in out if e.canonical_id == "dataset:agg1"]
    assert len(es) == 1
    assert es[0].kind == "dataset"


def test_single_type_aggregate_coexists_with_markdown_in_same_directory(tmp_path: Path) -> None:
    """A markdown file and an aggregate file in the same dir both load (different IDs)."""
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "rich-topic.md").write_text(
        '---\nid: "topic:rich"\ntype: "topic"\ntitle: "Rich"\n---\nNarrative.\n',
        encoding="utf-8",
    )
    (topics_dir / "topics.json").write_text(json.dumps([
        {"id": "topic:thin1", "title": "Thin 1"},
    ]), encoding="utf-8")
    # Markdown loaded by MarkdownProvider; aggregate by AggregateProvider.
    # AggregateProvider.discover only loads the aggregate.
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "topic:thin1" for e in out)
    # The markdown one is NOT the aggregate provider's job; we skip it here.
```

- [ ] **Step 2: Run failing tests**

```bash
uv run --frozen pytest tests/test_entity_providers/test_aggregate_provider.py -v
```

Expected: 4 new tests FAIL.

- [ ] **Step 3: Implement single-type aggregate loader**

In `science-tool/src/science_tool/graph/entity_providers/aggregate.py`, ADD `_load_single_type_aggregates` and call it from `discover`:

```python
import json


class AggregateProvider(EntityProvider):
    name = "aggregate"

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        entities.extend(self._load_multi_type_aggregate(ctx))
        entities.extend(self._load_single_type_aggregates(ctx))  # NEW
        return entities

    def _load_single_type_aggregates(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        from science_model.frontmatter import _DIR_TO_TYPE
        results: list[SourceEntity] = []
        for plural, singular in _DIR_TO_TYPE.items():
            for ext in ("json", "yaml"):
                f = ctx.project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                items = self._load_list(f)
                try:
                    rel_path = str(f.relative_to(ctx.project_root))
                except ValueError:
                    rel_path = str(f)
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    record = self._record_from_dict(raw, kind=singular, source_path=rel_path)
                    if record is None:
                        continue
                    results.append(_normalize_record(record, ctx, provider_name=self.name))
        return results

    def _load_list(self, path: Path) -> list:
        """Read a list from a JSON or YAML file. Returns empty list on read failure."""
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, yaml.YAMLError, OSError):
            return []

    # _load_multi_type_aggregate, _record_from_dict — unchanged from Task 2.2
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_entity_providers/test_aggregate_provider.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v  # snapshot still green
uv run --frozen pytest -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/ tests/
git add src/science_tool/graph/entity_providers/aggregate.py tests/test_entity_providers/test_aggregate_provider.py
git commit -m "feat(entity-providers): AggregateProvider single-type convention (mm30 rare-topics)"
```

---

### Task 5.2: `DatapackageDirectoryProvider` (Path 4 — dataset promotion)

**Files:**
- Create: `science-tool/src/science_tool/graph/entity_providers/datapackage_directory.py`
- Test: `science-tool/tests/test_entity_providers/test_datapackage_directory_provider.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_entity_providers/test_datapackage_directory_provider.py`:

```python
"""Tests for DatapackageDirectoryProvider — entity-flavored datapackages only."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.datapackage_directory import DatapackageDirectoryProvider
from science_tool.graph.source_types import EntityDatapackageInvalidError


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(project_root=root, project_slug=root.name, local_profile="local")


def test_provider_name_is_datapackage_directory() -> None:
    assert DatapackageDirectoryProvider().name == "datapackage-directory"


def test_returns_empty_when_no_datapackages_exist(tmp_path: Path) -> None:
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []


def test_skips_non_entity_datapackages(tmp_path: Path) -> None:
    """A datapackage WITHOUT science-pkg-entity-1.0 in profiles is silently ignored."""
    dp_dir = tmp_path / "data" / "non-entity"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0"],  # runtime only, not entity
        "name": "non-entity",
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []


def test_loads_entity_profile_datapackage(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "myset"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
        "name": "myset",
        "id": "dataset:myset",
        "type": "dataset",
        "title": "My set",
        "description": "Frictionless top-level description.",
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert len(out) == 1
    assert out[0].canonical_id == "dataset:myset"
    assert out[0].kind == "dataset"
    assert out[0].title == "My set"
    assert out[0].description == "Frictionless top-level description."
    assert out[0].provider == "datapackage-directory"


def test_walks_results_directory_too(tmp_path: Path) -> None:
    dp_dir = tmp_path / "results" / "wf" / "r1" / "out"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "wf-r1-out",
        "id": "dataset:wf-r1-out",
        "type": "dataset",
        "title": "WF r1 out",
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "dataset:wf-r1-out" for e in out)


def test_entity_profile_datapackage_missing_id_raises(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "broken"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "broken",
        # missing id, type, title
        "resources": [],
    }), encoding="utf-8")
    with pytest.raises(EntityDatapackageInvalidError) as exc_info:
        DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    msg = str(exc_info.value)
    assert "broken" in msg
    assert "id" in msg


def test_entity_profile_datapackage_missing_type_raises(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "broken2"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "broken2",
        "id": "dataset:b2",
        "title": "Broken 2",
        # missing type
        "resources": [],
    }), encoding="utf-8")
    with pytest.raises(EntityDatapackageInvalidError):
        DatapackageDirectoryProvider().discover(_ctx(tmp_path))


def test_malformed_yaml_in_non_entity_datapackage_silently_ignored(tmp_path: Path) -> None:
    """We can't determine if malformed YAML was an entity datapackage; conservative skip."""
    dp_dir = tmp_path / "data" / "bad-yaml"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text("not: valid: yaml: at: all", encoding="utf-8")
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []
```

- [ ] **Step 2: Run failing tests**

```bash
uv run --frozen pytest tests/test_entity_providers/test_datapackage_directory_provider.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/graph/entity_providers/datapackage_directory.py`:

```python
"""DatapackageDirectoryProvider — datasets promoted to live as data/<slug>/datapackage.yaml.

Walks for **/datapackage.yaml under data/ and results/. Filters strictly: only datapackages
whose profiles[] includes "science-pkg-entity-1.0" are emitted as entities. Datapackages
without that profile are silently ignored (existing behavior for the non-entity case).

Hard-error contract: an entity-profile datapackage with valid YAML but missing required
fields (id, type, title) raises EntityDatapackageInvalidError. Silently dropping a promoted
entity would be worse than failing.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record
from science_tool.graph.source_types import EntityDatapackageInvalidError, SourceEntity


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
                try:
                    rel_path = str(dp_path.relative_to(ctx.project_root))
                except ValueError:
                    rel_path = str(dp_path)
                try:
                    dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
                except (yaml.YAMLError, OSError):
                    # Malformed YAML — can't determine if entity; conservative skip.
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
            description=str(dp.get("description", "")),  # Frictionless top-level
            source_path=source_path,
            ontology_terms=list(dp.get("ontology_terms") or []),
            related=list(dp.get("related") or []),
            source_refs=list(dp.get("source_refs") or []),
            status=dp.get("status"),
            extra={
                # Pass-through dataset-specific fields downstream consumers may use.
                "origin": dp.get("origin"),
                "tier": dp.get("tier"),
                "access": dp.get("access"),
                "derivation": dp.get("derivation"),
                "datapackage_path": source_path,
            },
        )
```

- [ ] **Step 4: Verify + remove the xfail from `test_default_providers_returns_three_v1_implementations`**

In `tests/test_entity_providers/test_resolver.py`, REMOVE the `@pytest.mark.xfail(...)` decorator from `test_default_providers_returns_three_v1_implementations` — all three providers exist now.

```bash
uv run --frozen pytest tests/test_entity_providers/test_datapackage_directory_provider.py -v
uv run --frozen pytest tests/test_entity_providers/test_resolver.py -v
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
uv run --frozen pytest -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/ tests/
git add src/science_tool/graph/entity_providers/datapackage_directory.py tests/test_entity_providers/test_datapackage_directory_provider.py tests/test_entity_providers/test_resolver.py
git commit -m "feat(entity-providers): DatapackageDirectoryProvider for promoted datasets"
```

---

## Phase 6: Health integration

### Task 6.1: Update `dataset_cached_field_drift` to skip datapackage-directory entities

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Write failing test**

Append to `science-tool/tests/test_health.py`:

```python
def test_cached_field_drift_skips_datapackage_directory_entities(tmp_path: Path) -> None:
    """Promoted datasets (provider=datapackage-directory) have no two surfaces to drift between."""
    import yaml
    # Promoted entity: lives only as data/myset/datapackage.yaml; no markdown sidecar.
    dp_dir = tmp_path / "data" / "myset"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
        "name": "myset",
        "id": "dataset:myset",
        "type": "dataset",
        "title": "My promoted set",
        "license": "CC-BY-4.0",
        "ontology_terms": ["UBERON:0001"],
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    # The runtime AND entity are the same file. No sidecar markdown to drift against.
    issues = check_dataset_anomalies(tmp_path)
    drift_issues = [i for i in issues if i["code"] == "dataset_cached_field_drift"]
    assert drift_issues == [], f"unexpected drift on promoted dataset: {drift_issues}"
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_health.py::test_cached_field_drift_skips_datapackage_directory_entities -v
```

Expected: behavior may already pass if the existing drift check already returns no issues for this case (since the entity has no `datapackage:` field pointing at a separate file). If it fails, identify why.

- [ ] **Step 3: Inspect the existing check + add the skip**

```bash
grep -n "dataset_cached_field_drift\|provider" src/science_tool/graph/health.py | head -10
```

The existing `dataset_cached_field_drift` check (from dataset-entity-lifecycle Phase 6) reads the entity's frontmatter and compares fields against the runtime datapackage. For promoted entities, the entity IS the runtime file — there's no second surface to drift against. The check should explicitly skip when `provider == "datapackage-directory"`.

In `science-tool/src/science_tool/graph/health.py`, find the `dataset_cached_field_drift` block in `check_dataset_anomalies`. The current check loads `parse_frontmatter` directly — it doesn't have access to `provider` info from there. Add a guard: skip the drift check for any dataset whose source_path is a `datapackage.yaml` file (heuristic — these are the promoted entities).

```python
        # Skip cached-field drift for promoted entities (datapackage IS the entity surface).
        if md.name == "datapackage.yaml":
            continue
        # ... existing dataset_cached_field_drift logic ...
```

Place the guard at the top of the per-entity loop's drift-check block.

Alternatively, if you've made `check_dataset_anomalies` use `parse_entity_file` (which now sets `provider`), check `entity.provider == "datapackage-directory"` directly.

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_health.py -v -k "drift"
uv run --frozen pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff format src/science_tool/graph/health.py tests/test_health.py
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): skip cached_field_drift for datapackage-directory entities"
```

---

## Phase 7: Final cleanup

### Task 7.1: Migration scenario tests

**Files:**
- Create: `science-tool/tests/test_provider_migration.py`

End-to-end scenarios for the dataset migration story (mid-migration mixed mode, bad-migration collision recovery).

- [ ] **Step 1: Write tests**

Create `science-tool/tests/test_provider_migration.py`:

```python
"""End-to-end migration scenarios: mixed-mode coexistence, collision detection, recovery."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.source_types import EntityIdCollisionError


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: mig\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_mid_migration_mixed_mode(tmp_path: Path) -> None:
    """3 datasets in markdown + 2 as datapackage-directory both load. No collision."""
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    for slug in ("ds-md-1", "ds-md-2", "ds-md-3"):
        (tmp_path / "doc" / "datasets" / f"{slug}.md").write_text(
            f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\n---\n',
            encoding="utf-8",
        )
    for slug in ("ds-dp-1", "ds-dp-2"):
        dp_dir = tmp_path / "data" / slug
        dp_dir.mkdir(parents=True)
        (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
            "profiles": ["science-pkg-entity-1.0"],
            "name": slug,
            "id": f"dataset:{slug}",
            "type": "dataset",
            "title": slug,
            "resources": [{"name": "r", "path": "r.csv"}],
        }), encoding="utf-8")
    from science_tool.graph.sources import load_project_sources
    sources = load_project_sources(tmp_path)
    ids = {e.canonical_id for e in sources.entities}
    assert "dataset:ds-md-1" in ids
    assert "dataset:ds-md-2" in ids
    assert "dataset:ds-md-3" in ids
    assert "dataset:ds-dp-1" in ids
    assert "dataset:ds-dp-2" in ids


def test_bad_migration_collision_then_recovery(tmp_path: Path) -> None:
    """Markdown + datapackage-directory with same canonical_id raises; deleting markdown recovers."""
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    md = tmp_path / "doc" / "datasets" / "x.md"
    md.write_text('---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n---\n', encoding="utf-8")
    dp_dir = tmp_path / "data" / "x"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "x",
        "id": "dataset:x",
        "type": "dataset",
        "title": "X dp",
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    from science_tool.graph.sources import load_project_sources
    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    msg = str(exc_info.value)
    assert "dataset:x" in msg
    assert "doc/datasets/x.md" in msg
    assert "data/x/datapackage.yaml" in msg
    # Recovery: delete the markdown, re-run.
    md.unlink()
    sources = load_project_sources(tmp_path)
    es = [e for e in sources.entities if e.canonical_id == "dataset:x"]
    assert len(es) == 1
    assert es[0].provider == "datapackage-directory"
```

- [ ] **Step 2: Verify + commit**

```bash
uv run --frozen pytest tests/test_provider_migration.py -v
uv run --frozen pytest -q
git add tests/test_provider_migration.py
git commit -m "test: end-to-end migration scenarios (mixed mode + collision recovery)"
```

---

### Task 7.2: Lint, type-check, and full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Lint + format**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-tool
uv run --frozen ruff check . 2>&1 | tail -10
uv run --frozen ruff format --check . 2>&1 | tail -10
```

If `ruff check` reports issues introduced by Spec Y, fix with `uv run --frozen ruff check --fix .` and the corresponding `ruff format .`. Commit any auto-fix changes:

```bash
git add . && git commit -m "chore: ruff format + autofix from Spec Y work"
```

- [ ] **Step 2: Type-check**

```bash
uv run --frozen pyright 2>&1 | tail -10
```

Pre-existing pyright errors are LISTED in the plan header — confirm the count matches main; new errors from Spec Y must be fixed.

```bash
# Count pre-existing on main:
cd /mnt/ssd/Dropbox/science && git stash -u 2>&1 | head -1 ; git checkout main -- science-tool/ 2>&1 | head -1 ; cd science-tool && uv run --frozen pyright 2>&1 | tail -1 ; cd .. && git checkout HEAD -- science-tool/ ; git stash pop 2>&1 | head -1
# (Or alternative: just confirm the worktree's pyright count is no worse than main's.)
```

If new errors exist, fix them and commit:

```bash
git add . && git commit -m "fix: address pyright errors introduced by Spec Y"
```

- [ ] **Step 3: Full test sweep**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-tool
uv run --frozen pytest -q 2>&1 | tail -5

cd /mnt/ssd/Dropbox/science/.worktrees/multi-backend-entity-resolver/science-model
uv run --frozen pytest -q 2>&1 | tail -5
```

Expected: all green (188 science-model + previous-count-plus-new science-tool).

- [ ] **Step 4: Snapshot regression sanity check**

```bash
uv run --frozen pytest tests/test_load_project_sources_regression.py -v
```

Expected: PASS — the canary stays green from Task 1.2 through Task 7.2.

---

### Task 7.3: Update spec cross-references + handoff for Spec Z

**Files:**
- Modify: `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (already points at Spec Y design doc; verify still correct)

- [ ] **Step 1: Verify forward-reference is correct**

```bash
grep -n "multi-backend-entity-resolver" docs/specs/2026-04-19-dataset-entity-lifecycle-design.md
```

Expected: one match pointing at `2026-04-20-multi-backend-entity-resolver-design.md`. If a stale handoff reference remains, update to the design.

- [ ] **Step 2: No commit needed if reference is already correct**

This task is verification-only; the dataset-lifecycle spec was updated when Spec Y was committed.

---

## Self-review (run mentally before declaring done)

**Spec coverage check:** Map each Resolved Decision in Spec Y to a task above:

- Format-driven providers only / specialized parsers stay outside resolver: Phases 2, 3, 4 (specialized parsers updated, not wrapped)
- No per-entity-type / per-project configuration: providers always run, no config — confirmed in Tasks 2.1, 2.2, 5.2
- Auto-discovery filesystem-convention-driven: each provider has its own scan roots — Tasks 2.1 (markdown), 5.2 (datapackage), 5.1 (aggregate single-type)
- EntityProvider single-layer interface (α): `discover() -> list[SourceEntity]` — Task 1.3
- Cache-friendly but uncached: no cache code in v1 — confirmed by absence
- EntityResolver thin coordinator: Task 1.5
- ID collisions are hard errors: Tasks 1.5 (resolver), 3.1 (global)
- EntityDiscoveryContext carries shared loading state: Task 1.3
- Shared types in `graph/source_types.py`: Task 1.1
- Global collision check covers resolver + specialized: Task 3.1
- `provider` field required and explicit (six values): Task 4.1
- `EntityRecord` schema + shared `_normalize_record`: Task 1.4
- Hard-error contract for entity-profile datapackages: Task 5.2
- `SourceEntity.description` field + per-provider sourcing: Task 4.2
- Snapshot regression test uses projection: Task 1.2

**Placeholder scan:** No "TBD"/"TODO"/"implement later" — every step contains real test code, real implementation code, real commands.

**Type/name consistency:** `EntityProvider`, `EntityDiscoveryContext`, `EntityRecord`, `_normalize_record`, `EntityResolver`, `default_providers`, `EntityIdCollisionError`, `EntityDatapackageInvalidError`, `MarkdownProvider`, `DatapackageDirectoryProvider`, `AggregateProvider`, `SourceEntity.provider`, `SourceEntity.description` — all referenced consistently across tasks.

---

## Execution Handoff

**Plan complete and saved to `docs/specs/plans/2026-04-20-multi-backend-entity-resolver.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?

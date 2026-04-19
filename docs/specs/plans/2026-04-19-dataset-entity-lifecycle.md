# Dataset Entity Lifecycle (rev 2.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify external + workflow-derived data under one `dataset` entity (discriminated by `origin: external | derived`), backed by a `science-pkg` Frictionless DataPackage profile. Split legacy `data-package` into derived `dataset` entities + a renamed `research-package` entity. Add gate machinery and health checks across the pipeline.

**Architecture:** Two surface-specific JSON Schemas (`science-pkg-entity-1.0`, `science-pkg-runtime-1.0`) share a base. Entity surface (markdown frontmatter under `doc/datasets/`) carries project-level metadata; runtime surface (`datapackage.yaml` next to staged data) carries per-resource info. Single source of truth: entity drops `resources[]` entirely. Workflow registration (`science-tool dataset register-run`) emits per-output runtime datapackages plus matching derived dataset entities with symmetric backlinks. Strict migration of legacy `data-package` entities via shipped `science-tool data-package migrate`.

**Tech Stack:** Python 3.11+, uv, Pydantic, Click (CLI), pytest, ruff, pyright. Code lives across `science-model/src/science_model/` (schemas, models) and `science-tool/src/science_tool/` (CLI, graph, health). Tests under `science-tool/tests/` and `science-model/tests/`. Spec source of truth: `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (rev 2.1).

**Reference paths used throughout:**
- Spec: `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md`
- Existing entity model: `science-model/src/science_model/entities.py`
- Existing frontmatter parser: `science-model/src/science_model/frontmatter.py`
- Existing data-package schema: `science-model/src/science_model/packages/schema.py`
- Existing health module: `science-tool/src/science_tool/graph/health.py`
- CLI entry point: `science-tool/src/science_tool/cli.py`
- Templates: `templates/`
- Command docs: `commands/`

**Conventions used in this codebase:**
- All Python invocations: `uv run --frozen <command>`
- Lint: `uv run --frozen ruff check .`
- Format: `uv run --frozen ruff format .`
- Type check: `uv run --frozen pyright`
- Tests: `uv run --frozen pytest <path>`
- Line length: 120 chars

**Phases:**
1. JSON Schemas (foundation)
2. Pydantic models for entity surface
3. Frontmatter parsing extensions
4. Templates
5. Per-entity-type discovery
6. Health anomalies (12 of them)
7. `science-tool dataset` CLI extensions
8. `science-tool data-package migrate` + strict mode
9. Command-doc updates
10. Integration tests
11. Final cleanup

---

## Phase 1: JSON Schemas (foundation)

### Task 1.1: Define `science-pkg-entity-1.0.json`

**Files:**
- Create: `science-model/src/science_model/schemas/science-pkg-entity-1.0.json`
- Test: `science-model/tests/test_science_pkg_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# science-model/tests/test_science_pkg_schema.py
"""Tests for science-pkg JSON Schema family."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).parent.parent / "src" / "science_model" / "schemas"


@pytest.fixture
def entity_schema() -> dict:
    return json.loads((SCHEMA_DIR / "science-pkg-entity-1.0.json").read_text())


def _valid_external_entity() -> dict:
    return {
        "profiles": ["science-pkg-entity-1.0"],
        "id": "dataset:example",
        "type": "dataset",
        "title": "Example",
        "status": "active",
        "origin": "external",
        "tier": "use-now",
        "access": {
            "level": "public",
            "verified": True,
            "verification_method": "retrieved",
            "last_reviewed": "2026-04-19",
            "verified_by": "claude",
            "source_url": "https://example.com/x",
            "credentials_required": "",
            "exception": {"mode": "", "decision_date": "", "followup_task": "", "superseded_by_dataset": "", "rationale": ""},
        },
    }


def test_external_entity_minimal_valid(entity_schema: dict) -> None:
    jsonschema.validate(_valid_external_entity(), entity_schema)


def test_entity_rejects_resources_field(entity_schema: dict) -> None:
    """Entity surface MUST NOT carry resources[] (single source of truth)."""
    e = _valid_external_entity()
    e["resources"] = [{"name": "x", "path": "data/x.csv"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv add --dev jsonschema
uv run --frozen pytest tests/test_science_pkg_schema.py -v
```

Expected: FAIL — schema file does not exist.

- [ ] **Step 3: Write the schema**

Create `science-model/src/science_model/schemas/science-pkg-entity-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science-tool/science-pkg-entity-1.0.json",
  "title": "science-pkg entity surface",
  "type": "object",
  "required": ["profiles", "id", "type", "title", "status", "origin", "tier"],
  "properties": {
    "profiles": {
      "type": "array",
      "items": {"type": "string"},
      "contains": {"const": "science-pkg-entity-1.0"}
    },
    "id": {"type": "string", "pattern": "^dataset:"},
    "type": {"const": "dataset"},
    "title": {"type": "string"},
    "status": {"type": "string"},
    "origin": {"enum": ["external", "derived"]},
    "tier": {"enum": ["use-now", "evaluate-next", "track"]},
    "license": {"type": "string"},
    "update_cadence": {"enum": ["", "static", "rolling", "monthly", "quarterly", "annual", "versioned-releases"]},
    "ontology_terms": {"type": "array", "items": {"type": "string"}},
    "datapackage": {"type": "string"},
    "local_path": {"type": "string"},
    "consumed_by": {"type": "array", "items": {"type": "string"}},
    "parent_dataset": {"type": "string"},
    "siblings": {"type": "array", "items": {"type": "string"}},
    "accessions": {"type": "array", "items": {"type": "string"}},
    "access": {"$ref": "#/$defs/access"},
    "derivation": {"$ref": "#/$defs/derivation"},
    "source_refs": {"type": "array", "items": {"type": "string"}},
    "related": {"type": "array", "items": {"type": "string"}},
    "created": {"type": "string"},
    "updated": {"type": "string"}
  },
  "not": {"required": ["resources"]},
  "allOf": [
    {
      "if": {"properties": {"origin": {"const": "external"}}},
      "then": {
        "required": ["access"],
        "not": {"required": ["derivation"]}
      }
    },
    {
      "if": {"properties": {"origin": {"const": "derived"}}},
      "then": {
        "required": ["derivation"],
        "not": {"anyOf": [{"required": ["access"]}, {"required": ["accessions"]}, {"required": ["local_path"]}]}
      }
    }
  ],
  "$defs": {
    "access": {
      "type": "object",
      "required": ["level", "verified"],
      "properties": {
        "level": {"enum": ["public", "registration", "controlled", "commercial", "mixed"]},
        "verified": {"type": "boolean"},
        "verification_method": {"enum": ["", "retrieved", "credential-confirmed"]},
        "last_reviewed": {"type": "string"},
        "verified_by": {"type": "string"},
        "source_url": {"type": "string"},
        "credentials_required": {"type": "string"},
        "exception": {
          "type": "object",
          "properties": {
            "mode": {"enum": ["", "scope-reduced", "expanded-to-acquire", "substituted"]},
            "decision_date": {"type": "string"},
            "followup_task": {"type": "string"},
            "superseded_by_dataset": {"type": "string"},
            "rationale": {"type": "string"}
          }
        }
      }
    },
    "derivation": {
      "type": "object",
      "required": ["workflow", "workflow_run", "git_commit", "config_snapshot", "produced_at", "inputs"],
      "properties": {
        "workflow": {"type": "string", "pattern": "^workflow:"},
        "workflow_run": {"type": "string", "pattern": "^workflow-run:"},
        "git_commit": {"type": "string"},
        "config_snapshot": {"type": "string"},
        "produced_at": {"type": "string"},
        "inputs": {"type": "array", "items": {"type": "string", "pattern": "^dataset:"}}
      }
    }
  }
}
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run --frozen pytest tests/test_science_pkg_schema.py -v
```

Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/schemas/science-pkg-entity-1.0.json science-model/tests/test_science_pkg_schema.py science-model/pyproject.toml science-model/uv.lock
git commit -m "feat(science-model): add science-pkg-entity-1.0 JSON Schema"
```

---

### Task 1.2: Define `science-pkg-runtime-1.0.json`

**Files:**
- Create: `science-model/src/science_model/schemas/science-pkg-runtime-1.0.json`
- Modify: `science-model/tests/test_science_pkg_schema.py`

- [ ] **Step 1: Add failing test**

Append to `science-model/tests/test_science_pkg_schema.py`:

```python
@pytest.fixture
def runtime_schema() -> dict:
    return json.loads((SCHEMA_DIR / "science-pkg-runtime-1.0.json").read_text())


def _valid_runtime_pkg() -> dict:
    return {
        "profiles": ["science-pkg-runtime-1.0"],
        "name": "example",
        "resources": [
            {
                "name": "table",
                "path": "data/table.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "bytes": 1234,
                "hash": "sha256:abc",
            }
        ],
    }


def test_runtime_pkg_minimal_valid(runtime_schema: dict) -> None:
    jsonschema.validate(_valid_runtime_pkg(), runtime_schema)


def test_runtime_rejects_top_level_access(runtime_schema: dict) -> None:
    """Runtime surface MUST NOT carry top-level access: (entity-only block)."""
    pkg = _valid_runtime_pkg()
    pkg["access"] = {"level": "public", "verified": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pkg, runtime_schema)


def test_runtime_rejects_top_level_derivation(runtime_schema: dict) -> None:
    pkg = _valid_runtime_pkg()
    pkg["derivation"] = {"workflow_run": "workflow-run:x"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pkg, runtime_schema)
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run --frozen pytest tests/test_science_pkg_schema.py -v
```

Expected: 3 new tests FAIL — runtime schema file missing.

- [ ] **Step 3: Write the runtime schema**

Create `science-model/src/science_model/schemas/science-pkg-runtime-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science-tool/science-pkg-runtime-1.0.json",
  "title": "science-pkg runtime surface (datapackage.yaml on disk)",
  "type": "object",
  "required": ["profiles", "name", "resources"],
  "properties": {
    "profiles": {
      "type": "array",
      "items": {"type": "string"},
      "contains": {"const": "science-pkg-runtime-1.0"}
    },
    "name": {"type": "string"},
    "title": {"type": "string"},
    "description": {"type": "string"},
    "licenses": {"type": "array"},
    "ontology_terms": {"type": "array", "items": {"type": "string"}},
    "license": {"type": "string"},
    "update_cadence": {"type": "string"},
    "resources": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "path"],
        "properties": {
          "name": {"type": "string"},
          "path": {"type": "string"},
          "format": {"type": "string"},
          "mediatype": {"type": "string"},
          "bytes": {"type": "integer"},
          "hash": {"type": "string"},
          "schema": {"type": "object"}
        }
      }
    }
  },
  "not": {
    "anyOf": [
      {"required": ["access"]},
      {"required": ["derivation"]},
      {"required": ["origin"]}
    ]
  }
}
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run --frozen pytest tests/test_science_pkg_schema.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/schemas/science-pkg-runtime-1.0.json science-model/tests/test_science_pkg_schema.py
git commit -m "feat(science-model): add science-pkg-runtime-1.0 JSON Schema"
```

---

### Task 1.3: Add invariant tests for #7, #8 origin/block exclusion

**Files:**
- Modify: `science-model/tests/test_science_pkg_schema.py`

- [ ] **Step 1: Add invariant tests**

Append:

```python
def test_invariant_7_external_with_derivation_rejects(entity_schema: dict) -> None:
    """origin: external + derivation: -> reject (#7)."""
    e = _valid_external_entity()
    e["derivation"] = {"workflow_run": "workflow-run:x", "workflow": "workflow:x", "git_commit": "abc", "config_snapshot": "", "produced_at": "", "inputs": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def _valid_derived_entity() -> dict:
    return {
        "profiles": ["science-pkg-entity-1.0"],
        "id": "dataset:wf-r1-out1",
        "type": "dataset",
        "title": "Derived",
        "status": "active",
        "origin": "derived",
        "tier": "use-now",
        "datapackage": "results/wf/r1/out1/datapackage.yaml",
        "derivation": {
            "workflow": "workflow:wf",
            "workflow_run": "workflow-run:wf-r1",
            "git_commit": "abc1234",
            "config_snapshot": "results/wf/r1/config.yaml",
            "produced_at": "2026-04-19T12:00:00Z",
            "inputs": ["dataset:upstream"],
        },
    }


def test_invariant_8_derived_with_access_rejects(entity_schema: dict) -> None:
    """origin: derived + access: -> reject (#8)."""
    e = _valid_derived_entity()
    e["access"] = {"level": "public", "verified": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def test_invariant_8_derived_with_accessions_rejects(entity_schema: dict) -> None:
    e = _valid_derived_entity()
    e["accessions"] = ["EGAD00001"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def test_derived_entity_minimal_valid(entity_schema: dict) -> None:
    jsonschema.validate(_valid_derived_entity(), entity_schema)
```

- [ ] **Step 2: Run tests**

```bash
uv run --frozen pytest tests/test_science_pkg_schema.py -v
```

Expected: all PASS (invariants #7, #8 are enforced by the schema's `allOf` clauses already written in Task 1.1).

- [ ] **Step 3: Commit**

```bash
git add science-model/tests/test_science_pkg_schema.py
git commit -m "test(science-model): cover origin/block-exclusion invariants (#7, #8)"
```

---

## Phase 2: Pydantic models for entity surface

### Task 2.1: `AccessException` and `AccessBlock` models

**Files:**
- Modify: `science-model/src/science_model/packages/schema.py`
- Create: `science-model/tests/test_dataset_models.py`

- [ ] **Step 1: Write failing test**

Create `science-model/tests/test_dataset_models.py`:

```python
"""Tests for unified dataset entity Pydantic models."""
from __future__ import annotations

import pytest

from science_model.packages.schema import AccessBlock, AccessException


class TestAccessException:
    def test_default_empty(self) -> None:
        ex = AccessException()
        assert ex.mode == ""
        assert ex.decision_date == ""
        assert ex.followup_task == ""
        assert ex.superseded_by_dataset == ""
        assert ex.rationale == ""

    def test_scope_reduced(self) -> None:
        ex = AccessException(mode="scope-reduced", decision_date="2026-04-19", followup_task="task:t112", rationale="deferred")
        assert ex.mode == "scope-reduced"

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            AccessException(mode="invalid")


class TestAccessBlock:
    def test_minimal_unverified(self) -> None:
        a = AccessBlock(level="public", verified=False)
        assert a.level == "public"
        assert a.verified is False
        assert a.verification_method == ""
        assert a.exception.mode == ""

    def test_verified_retrieved(self) -> None:
        a = AccessBlock(level="public", verified=True, verification_method="retrieved", last_reviewed="2026-04-19", verified_by="claude", source_url="https://x")
        assert a.verified is True
        assert a.verification_method == "retrieved"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen pytest tests/test_dataset_models.py -v
```

Expected: ImportError on `AccessBlock`, `AccessException`.

- [ ] **Step 3: Add models**

Append to `science-model/src/science_model/packages/schema.py`:

```python
from typing import Literal


class AccessException(BaseModel):
    """Structured Branch-B decision for an unverified-but-consumable external dataset."""

    mode: Literal["", "scope-reduced", "expanded-to-acquire", "substituted"] = ""
    decision_date: str = ""
    followup_task: str = ""
    superseded_by_dataset: str = ""
    rationale: str = ""


class AccessBlock(BaseModel):
    """External dataset access verification gate state."""

    level: Literal["public", "registration", "controlled", "commercial", "mixed"]
    verified: bool
    verification_method: Literal["", "retrieved", "credential-confirmed"] = ""
    last_reviewed: str = ""
    verified_by: str = ""
    source_url: str = ""
    credentials_required: str = ""
    exception: AccessException = Field(default_factory=AccessException)
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run --frozen pytest tests/test_dataset_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/packages/schema.py science-model/tests/test_dataset_models.py
git commit -m "feat(science-model): add AccessBlock + AccessException models"
```

---

### Task 2.2: `DerivationBlock` model

**Files:**
- Modify: `science-model/src/science_model/packages/schema.py`
- Modify: `science-model/tests/test_dataset_models.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_dataset_models.py`:

```python
from science_model.packages.schema import DerivationBlock


class TestDerivationBlock:
    def test_minimal_valid(self) -> None:
        d = DerivationBlock(
            workflow="workflow:wf",
            workflow_run="workflow-run:wf-r1",
            git_commit="abc1234",
            config_snapshot="results/wf/r1/config.yaml",
            produced_at="2026-04-19T12:00:00Z",
            inputs=["dataset:upstream"],
        )
        assert d.workflow == "workflow:wf"
        assert d.inputs == ["dataset:upstream"]

    def test_workflow_id_pattern_required(self) -> None:
        with pytest.raises(ValueError):
            DerivationBlock(
                workflow="not-a-workflow-id",
                workflow_run="workflow-run:x",
                git_commit="a", config_snapshot="c", produced_at="t", inputs=[],
            )

    def test_inputs_must_be_dataset_ids(self) -> None:
        with pytest.raises(ValueError):
            DerivationBlock(
                workflow="workflow:x",
                workflow_run="workflow-run:x",
                git_commit="a", config_snapshot="c", produced_at="t",
                inputs=["not-a-dataset"],
            )
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_models.py::TestDerivationBlock -v
```

Expected: ImportError.

- [ ] **Step 3: Add model**

Append to `science-model/src/science_model/packages/schema.py`:

```python
from pydantic import field_validator


class DerivationBlock(BaseModel):
    """Derived dataset provenance pointing at the producing workflow-run."""

    workflow: str
    workflow_run: str
    git_commit: str
    config_snapshot: str
    produced_at: str
    inputs: list[str] = Field(default_factory=list)

    @field_validator("workflow")
    @classmethod
    def _wf_id(cls, v: str) -> str:
        if not v.startswith("workflow:"):
            raise ValueError("workflow must be a workflow:<slug> entity reference")
        return v

    @field_validator("workflow_run")
    @classmethod
    def _wfrun_id(cls, v: str) -> str:
        if not v.startswith("workflow-run:"):
            raise ValueError("workflow_run must be a workflow-run:<slug> entity reference")
        return v

    @field_validator("inputs")
    @classmethod
    def _input_ids(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.startswith("dataset:"):
                raise ValueError(f"inputs must be dataset:<slug> entity references; got {item!r}")
        return v
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run --frozen pytest tests/test_dataset_models.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/packages/schema.py science-model/tests/test_dataset_models.py
git commit -m "feat(science-model): add DerivationBlock model with id-pattern validators"
```

---

### Task 2.3: Add `EntityType.RESEARCH_PACKAGE`

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Test: `science-model/tests/test_dataset_models.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_dataset_models.py`:

```python
from science_model.entities import EntityType


def test_research_package_entity_type_exists() -> None:
    assert EntityType("research-package") == EntityType.RESEARCH_PACKAGE


def test_data_package_entity_type_still_parses() -> None:
    """Back-compat: legacy data-package entries continue to parse as their own type."""
    assert EntityType("data-package") == EntityType.DATA_PACKAGE
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_models.py::test_research_package_entity_type_exists -v
```

Expected: FAIL — `RESEARCH_PACKAGE` undefined.

- [ ] **Step 3: Add enum value**

In `science-model/src/science_model/entities.py`, in the `EntityType` enum (around line 44, after `DATA_PACKAGE = "data-package"`):

```python
    DATA_PACKAGE = "data-package"
    RESEARCH_PACKAGE = "research-package"
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_dataset_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_dataset_models.py
git commit -m "feat(science-model): add EntityType.RESEARCH_PACKAGE"
```

---

### Task 2.4: Extend `Entity` with new dataset fields

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Test: `science-model/tests/test_dataset_models.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_dataset_models.py`:

```python
from science_model.entities import Entity, EntityType
from science_model.packages.schema import AccessBlock, DerivationBlock


def _entity_kwargs() -> dict:
    return dict(
        id="dataset:x",
        type=EntityType.DATASET,
        title="X",
        project="testproj",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/datasets/x.md",
    )


def test_entity_external_origin_with_access_block() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="external",
        access=AccessBlock(level="public", verified=True, verification_method="retrieved", last_reviewed="2026-04-19", source_url="https://x"),
        accessions=["EGAD0001"],
        datapackage="data/x/datapackage.yaml",
        local_path="",
        consumed_by=["plan:p1"],
        parent_dataset="",
        siblings=[],
    )
    assert e.origin == "external"
    assert e.access.verified is True
    assert e.derivation is None


def test_entity_derived_origin_with_derivation_block() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:wf",
            workflow_run="workflow-run:wf-r1",
            git_commit="abc",
            config_snapshot="c",
            produced_at="2026-04-19T12:00:00Z",
            inputs=["dataset:up"],
        ),
        datapackage="results/wf/r1/x/datapackage.yaml",
        consumed_by=[],
        parent_dataset="",
        siblings=[],
    )
    assert e.origin == "derived"
    assert e.derivation is not None
    assert e.access is None
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_models.py::test_entity_external_origin_with_access_block -v
```

Expected: FAIL — `Entity` lacks new fields.

- [ ] **Step 3: Extend `Entity`**

In `science-model/src/science_model/entities.py`, add an import and new fields:

```python
# At the top imports section, add:
from science_model.packages.schema import AccessBlock, DerivationBlock

# Inside the Entity class, after the existing fields (after line ~95):
    # Dataset entity unification (rev 2.1)
    origin: str | None = None  # "external" | "derived"
    access: AccessBlock | None = None
    derivation: DerivationBlock | None = None
    accessions: list[str] = Field(default_factory=list)
    datapackage: str = ""
    local_path: str = ""
    consumed_by: list[str] = Field(default_factory=list)
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_dataset_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_dataset_models.py
git commit -m "feat(science-model): extend Entity with origin/access/derivation/lineage fields"
```

---

## Phase 3: Frontmatter parsing extensions

### Task 3.1: Back-compat reads — flat `access:` and `datasets:` aliases

**Files:**
- Modify: `science-model/src/science_model/frontmatter.py`
- Test: `science-model/tests/test_frontmatter_dataset.py`

- [ ] **Step 1: Write failing test**

Create `science-model/tests/test_frontmatter_dataset.py`:

```python
"""Frontmatter parsing for dataset entities — back-compat + new shape."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from science_model.frontmatter import parse_frontmatter, frontmatter_to_entity


@pytest.fixture
def tmp_md(tmp_path: Path):
    def _write(content: str) -> Path:
        p = tmp_path / "x.md"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p
    return _write


def test_legacy_flat_access_parses_as_access_level(tmp_md) -> None:
    p = tmp_md("""
        ---
        id: "dataset:legacy"
        type: "dataset"
        title: "Legacy"
        access: "public"
        datasets:
          - "EGAD00001"
        ---
        Body.
    """)
    fm, _ = parse_frontmatter(p)
    e = frontmatter_to_entity(fm, project="testproj", file_path=str(p))
    assert e.origin == "external"  # default for legacy
    assert e.access is not None
    assert e.access.level == "public"
    assert e.access.verified is False
    assert e.accessions == ["EGAD00001"]  # `datasets:` aliased


def test_new_shape_origin_external(tmp_md) -> None:
    p = tmp_md("""
        ---
        id: "dataset:new"
        type: "dataset"
        title: "New"
        profiles: ["science-pkg-entity-1.0"]
        origin: "external"
        tier: "use-now"
        access:
          level: "public"
          verified: true
          verification_method: "retrieved"
          last_reviewed: "2026-04-19"
          verified_by: "claude"
          source_url: "https://x"
        accessions: ["E1"]
        datapackage: "data/new/datapackage.yaml"
        ---
    """)
    fm, _ = parse_frontmatter(p)
    e = frontmatter_to_entity(fm, project="testproj", file_path=str(p))
    assert e.origin == "external"
    assert e.access.verified is True
    assert e.datapackage == "data/new/datapackage.yaml"
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_frontmatter_dataset.py -v
```

Expected: ImportError on `frontmatter_to_entity` (does not exist yet) OR fields not populated.

- [ ] **Step 3: Add or extend `frontmatter_to_entity`**

In `science-model/src/science_model/frontmatter.py`, add (or extend if it exists) a function that builds an `Entity` from a frontmatter dict. Insert after the existing helpers:

```python
from science_model.entities import Entity, EntityType
from science_model.packages.schema import AccessBlock, AccessException, DerivationBlock


def _coerce_access(fm: dict) -> AccessBlock | None:
    """Build AccessBlock from frontmatter, supporting legacy flat `access: <level>` shorthand."""
    raw = fm.get("access")
    if raw is None:
        return None
    if isinstance(raw, str):
        # Legacy: flat scalar -> AccessBlock with level only, verified=False.
        return AccessBlock(level=raw, verified=False)
    if isinstance(raw, dict):
        ex_raw = raw.get("exception") or {}
        return AccessBlock(
            level=raw.get("level", "public"),
            verified=bool(raw.get("verified", False)),
            verification_method=raw.get("verification_method", ""),
            last_reviewed=raw.get("last_reviewed", ""),
            verified_by=raw.get("verified_by", ""),
            source_url=raw.get("source_url", ""),
            credentials_required=raw.get("credentials_required", ""),
            exception=AccessException(**ex_raw) if ex_raw else AccessException(),
        )
    return None


def _coerce_derivation(fm: dict) -> DerivationBlock | None:
    raw = fm.get("derivation")
    if not isinstance(raw, dict):
        return None
    return DerivationBlock(
        workflow=raw.get("workflow", ""),
        workflow_run=raw.get("workflow_run", ""),
        git_commit=raw.get("git_commit", ""),
        config_snapshot=raw.get("config_snapshot", ""),
        produced_at=raw.get("produced_at", ""),
        inputs=list(raw.get("inputs") or []),
    )


def frontmatter_to_entity(fm: dict, *, project: str, file_path: str) -> Entity:
    """Build an Entity model from a frontmatter dict.

    Applies back-compat read rules:
    - `datasets:` alias for `accessions:` (legacy field name)
    - flat scalar `access: <level>` -> AccessBlock with level only, verified=False
    - missing `origin:` defaults to "external" (legacy entries)
    """
    type_str = fm.get("type", "unknown")
    accessions = list(fm.get("accessions") or fm.get("datasets") or [])
    origin = fm.get("origin")
    if origin is None and type_str == "dataset":
        origin = "external"
    return Entity(
        id=fm.get("id", ""),
        type=EntityType(type_str) if type_str in {t.value for t in EntityType} else EntityType.UNKNOWN,
        title=fm.get("title", ""),
        status=fm.get("status"),
        project=project,
        ontology_terms=list(fm.get("ontology_terms") or []),
        created=_coerce_date(fm.get("created")),
        updated=_coerce_date(fm.get("updated")),
        related=list(fm.get("related") or []),
        source_refs=list(fm.get("source_refs") or []),
        content_preview="",
        file_path=file_path,
        origin=origin,
        access=_coerce_access(fm),
        derivation=_coerce_derivation(fm),
        accessions=accessions,
        datapackage=fm.get("datapackage", ""),
        local_path=fm.get("local_path", ""),
        consumed_by=list(fm.get("consumed_by") or []),
        parent_dataset=fm.get("parent_dataset", ""),
        siblings=list(fm.get("siblings") or []),
    )
```

- [ ] **Step 4: Verify**

```bash
uv run --frozen pytest tests/test_frontmatter_dataset.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/frontmatter.py science-model/tests/test_frontmatter_dataset.py
git commit -m "feat(science-model): frontmatter_to_entity with dataset back-compat reads"
```

---

### Task 3.2: Derived-origin frontmatter parses through the new path

**Files:**
- Modify: `science-model/tests/test_frontmatter_dataset.py`

- [ ] **Step 1: Add failing test**

Append:

```python
def test_derived_frontmatter_parses(tmp_md) -> None:
    p = tmp_md("""
        ---
        id: "dataset:wf-r1-out1"
        type: "dataset"
        title: "Derived"
        profiles: ["science-pkg-entity-1.0"]
        origin: "derived"
        tier: "use-now"
        datapackage: "results/wf/r1/out1/datapackage.yaml"
        derivation:
          workflow: "workflow:wf"
          workflow_run: "workflow-run:wf-r1"
          git_commit: "abc"
          config_snapshot: "results/wf/r1/config.yaml"
          produced_at: "2026-04-19T12:00:00Z"
          inputs:
            - "dataset:upstream"
        consumed_by:
          - "plan:p1"
          - "research-package:rp1"
        ---
    """)
    fm, _ = parse_frontmatter(p)
    e = frontmatter_to_entity(fm, project="testproj", file_path=str(p))
    assert e.origin == "derived"
    assert e.access is None
    assert e.derivation is not None
    assert e.derivation.workflow_run == "workflow-run:wf-r1"
    assert e.derivation.inputs == ["dataset:upstream"]
    assert "research-package:rp1" in e.consumed_by
```

- [ ] **Step 2: Run**

```bash
uv run --frozen pytest tests/test_frontmatter_dataset.py -v
```

Expected: PASS (the parser from Task 3.1 already handles this).

- [ ] **Step 3: Commit**

```bash
git add science-model/tests/test_frontmatter_dataset.py
git commit -m "test(science-model): cover derived-origin frontmatter parsing"
```

---
## Phase 4: Templates

### Task 4.1: Replace `templates/dataset.md`

**Files:**
- Modify: `templates/dataset.md`
- Test: `science-tool/tests/test_command_docs.py` (verify reference still resolves)

- [ ] **Step 1: Read existing template**

```bash
cat templates/dataset.md
```

Make a mental note of the legacy frontmatter and prose sections; the new template inherits the discovery prose verbatim, only the frontmatter changes.

- [ ] **Step 2: Write the new template**

Replace `templates/dataset.md` with:

```markdown
---
id: "dataset:<slug>"
type: "dataset"
title: "<Dataset Name — artefact-level specific>"
status: "active"
profiles: ["science-pkg-entity-1.0"]
origin: "external"                # external | derived
tier: "evaluate-next"             # use-now | evaluate-next | track
license: ""                       # SPDX identifier or "unknown"
update_cadence: ""                # static | rolling | monthly | ...
ontology_terms: []                # CURIEs

# Pointer to the runtime datapackage.yaml (entity surface does NOT carry resources[])
datapackage: ""
local_path: ""                    # external single-file escape hatch (mutually exclusive with datapackage)

# External-only — REMOVE if origin: derived
accessions: []                    # external accession IDs (renamed from `datasets:`)
access:
  level: "public"                 # public | registration | controlled | commercial | mixed
  verified: false
  verification_method: ""         # "" | retrieved | credential-confirmed
  last_reviewed: ""               # YYYY-MM-DD
  verified_by: ""
  source_url: ""
  credentials_required: ""
  exception:
    mode: ""                      # "" | scope-reduced | expanded-to-acquire | substituted
    decision_date: ""
    followup_task: ""
    superseded_by_dataset: ""
    rationale: ""

# Derived-only — UNCOMMENT and populate when origin: derived; REMOVE access: above
# derivation:
#   workflow: "workflow:<slug>"
#   workflow_run: "workflow-run:<slug>"
#   git_commit: ""
#   config_snapshot: ""
#   produced_at: ""
#   inputs:
#     - "dataset:<upstream-slug>"

# Lineage
parent_dataset: ""
siblings: []

# Backlinks (written by plan-pipeline Step 4.5 / register-run)
consumed_by: []

source_refs: []
related: []
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Dataset Name>

## Summary

<What the dataset contains and why it is relevant.>

## Access verification log

<!-- Append-only chronological log; one entry per verification event. -->
<!-- Format: - YYYY-MM-DD (agent-or-user): brief note. -->

## Granularity at this access level

<!-- For granular siblings: state explicitly what THIS entity covers vs what sibling entities cover. -->

## Connections to Project

- Questions/hypotheses it can inform:
- Variables likely available:
- Planned usage:

## Related

- Topic notes:
- Method notes:
- Article notes:
```

- [ ] **Step 3: Verify the template renders no parser errors**

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen python -c "
from pathlib import Path
from science_model.frontmatter import parse_frontmatter, frontmatter_to_entity
fm, _ = parse_frontmatter(Path('../templates/dataset.md'))
print('parsed origin:', fm.get('origin'))
print('parsed access keys:', list((fm.get('access') or {}).keys()))
"
```

Expected output: `parsed origin: external`; `parsed access keys: ['level', 'verified', ...]`.

- [ ] **Step 4: Commit**

```bash
git add templates/dataset.md
git commit -m "feat(templates): unified dataset.md template (rev 2.1)"
```

---

### Task 4.2: Create `templates/research-package.md`

**Files:**
- Read: `templates/data-package.md` (legacy template, to copy narrative bundle fields)
- Create: `templates/research-package.md`

- [ ] **Step 1: Inspect legacy template**

```bash
cat templates/data-package.md 2>/dev/null || echo "no data-package.md template — check skills/research/provenance.md for the shape"
```

- [ ] **Step 2: Write the new template**

Create `templates/research-package.md`:

```markdown
---
id: "research-package:<slug>"
type: "research-package"
title: "<Rendered analysis title>"
status: "active"

# What derived datasets this rendering bundle displays.
# MUST be symmetric with each dataset's consumed_by (state invariant #11).
displays: []                       # ["dataset:<slug>", ...]

location: ""                       # research/packages/<lens>/<section>/
manifest: ""                       # research/packages/<lens>/<section>/datapackage.yaml

# Narrative bundle (shape unchanged from legacy data-package; data resources removed).
cells: ""                          # path to cells.json
figures: []                        # [{name, path, caption}]
vegalite_specs: []                 # [{name, path, caption}]
code_excerpts: []                  # [{name, path, source, lines, github_permalink}]

related: []                        # ["workflow-run:<slug>", ...]
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Rendered analysis title>

## Summary

<What this rendering bundle illustrates and which derived datasets it draws from.>

## Related

- Workflow run: <workflow-run:slug>
- Datasets displayed: <dataset:slug>, ...
```

- [ ] **Step 3: Commit**

```bash
git add templates/research-package.md
git commit -m "feat(templates): research-package template (renamed from data-package)"
```

---

### Task 4.3: Add `outputs:` to `templates/workflow.md`

**Files:**
- Modify: `templates/workflow.md`

- [ ] **Step 1: Inspect existing template**

```bash
cat templates/workflow.md
```

- [ ] **Step 2: Insert `outputs:` block**

Edit `templates/workflow.md`. After the existing `method: "<method-slug>"` line in frontmatter, insert:

```yaml
# Logical outputs declared by this workflow. Used by `science-tool dataset register-run`
# to emit one derived `dataset:<slug>` entity per output, plus a per-output runtime
# datapackage.yaml at results/<wf>/<run>/<output-slug>/datapackage.yaml.
outputs: []
# Each entry:
#   - slug: "<output-slug>"
#     title: "<Output title>"
#     resource_names: ["<frictionless-resource-name>", ...]
#     ontology_terms: []
```

- [ ] **Step 3: Commit**

```bash
git add templates/workflow.md
git commit -m "feat(templates): add outputs[] block to workflow template"
```

---

### Task 4.4: Add `produces:` and `inputs:` to `templates/workflow-run.md`

**Files:**
- Modify: `templates/workflow-run.md`

- [ ] **Step 1: Insert fields**

In `templates/workflow-run.md`, after the existing `workflow: "<workflow-slug>"` line:

```yaml
# Symmetric edges (populated by `science-tool dataset register-run`).
# `produces:` is the inverse of dataset.derivation.workflow_run (state invariant #9).
# `inputs:` enumerates upstream datasets the run consumed; symmetric with each
# upstream dataset's consumed_by listing this workflow-run.
produces: []                       # ["dataset:<slug>", ...]
inputs: []                         # ["dataset:<slug>", ...]
```

- [ ] **Step 2: Commit**

```bash
git add templates/workflow-run.md
git commit -m "feat(templates): add produces[]/inputs[] to workflow-run template"
```

---

## Phase 5: Per-entity-type discovery rule

### Task 5.1: Add discovery config + extend graph builder scan

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (or wherever entity discovery lives — check `materialize.py` if not in store)
- Test: `science-tool/tests/test_graph_paths.py`

- [ ] **Step 1: Locate entity discovery code**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
grep -rn "doc/" src/science_tool/graph/ | grep -E "glob|rglob|walk" | head
```

The output identifies the file that scans `doc/**/*.md`. Record the file path and function name (`<discovery_file>`, `<discovery_fn>`) for the next steps.

- [ ] **Step 2: Write failing test**

Create `science-tool/tests/test_graph_paths.py`:

```python
"""Per-entity-type discovery: research-package lives outside doc/."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "ds1.md").write_text(
        '---\nid: "dataset:ds1"\ntype: "dataset"\ntitle: "DS1"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "research" / "packages" / "lens" / "section").mkdir(parents=True)
    (tmp_path / "research" / "packages" / "lens" / "section" / "research-package.md").write_text(
        '---\nid: "research-package:rp1"\ntype: "research-package"\ntitle: "RP1"\n'
        'displays: ["dataset:ds1"]\n---\n',
        encoding="utf-8",
    )
    return tmp_path


def test_discovers_research_package_outside_doc(proj: Path) -> None:
    from science_tool.graph.store import discover_entities  # adjust import to actual module

    entities = list(discover_entities(proj))
    ids = {e.id for e in entities}
    assert "dataset:ds1" in ids
    assert "research-package:rp1" in ids
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_graph_paths.py -v
```

Expected: import error or `research-package:rp1` not found.

- [ ] **Step 4: Add per-entity-type config + scan rule**

In the discovery file identified in Step 1, add a config map and use it in the scanner:

```python
# Per-entity-type discovery (small precursor to Spec Y's resolver).
ENTITY_DISCOVERY_GLOBS: dict[str, str] = {
    "default": "doc/**/*.md",
    "research-package": "research/packages/**/research-package.md",
}


def _discovery_globs() -> list[str]:
    """Return the union of glob patterns to scan for entity files."""
    return list(set(ENTITY_DISCOVERY_GLOBS.values()))


def discover_entities(project_root: Path):
    """Yield Entity objects from all configured entity-discovery paths."""
    seen: set[Path] = set()
    for pattern in _discovery_globs():
        for md_path in project_root.glob(pattern):
            if md_path in seen:
                continue
            seen.add(md_path)
            fm, _ = parse_frontmatter(md_path)
            if fm:
                yield frontmatter_to_entity(fm, project=project_root.name, file_path=str(md_path))
```

(Adapt names to the actual existing discovery function. If it's already a generator over `doc/**/*.md`, extend it to iterate `_discovery_globs()` and dedupe.)

- [ ] **Step 5: Verify**

```bash
uv run --frozen pytest tests/test_graph_paths.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_paths.py
git commit -m "feat(graph): per-entity-type discovery globs (research-package outside doc/)"
```

---

## Phase 6: Health anomalies (twelve)

Goal: implement all twelve anomalies from spec §Health Check Additions. One task per related grouping; each task adds new test cases and the corresponding health-checker code.

### Task 6.1: Health-check skeleton — anomaly registry

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py` (existing)

- [ ] **Step 1: Inspect existing health module**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
sed -n '1,120p' src/science_tool/graph/health.py
```

Identify how anomalies are emitted today (likely a list of dicts or dataclass instances). The new anomalies follow that same shape.

- [ ] **Step 2: Write a registry-shape test**

Append to `science-tool/tests/test_health.py`:

```python
def test_dataset_anomaly_codes_registered() -> None:
    from science_tool.graph.health import DATASET_ANOMALY_CODES

    expected = {
        "dataset_consumed_but_unverified",
        "dataset_stale_review",
        "dataset_missing_source_url",
        "dataset_cached_field_drift",
        "dataset_invariant_violation",
        "dataset_derived_missing_workflow_run",
        "dataset_derived_asymmetric_edge",
        "dataset_derived_input_chain_broken",
        "dataset_origin_block_mismatch",
        "dataset_verified_but_unstageable",
        "dataset_research_package_asymmetric",
        "data_package_unmigrated",
    }
    assert expected.issubset(set(DATASET_ANOMALY_CODES))
```

- [ ] **Step 3: Add the registry constant**

In `science-tool/src/science_tool/graph/health.py`, add:

```python
DATASET_ANOMALY_CODES: tuple[str, ...] = (
    "dataset_consumed_but_unverified",
    "dataset_stale_review",
    "dataset_missing_source_url",
    "dataset_cached_field_drift",
    "dataset_invariant_violation",
    "dataset_derived_missing_workflow_run",
    "dataset_derived_asymmetric_edge",
    "dataset_derived_input_chain_broken",
    "dataset_origin_block_mismatch",
    "dataset_verified_but_unstageable",
    "dataset_research_package_asymmetric",
    "data_package_unmigrated",
)
```

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "anomaly_codes"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): register twelve dataset-related anomaly codes"
```

---

### Task 6.2: `dataset_origin_block_mismatch` (#7, #8)

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_health.py`:

```python
from pathlib import Path
from science_tool.graph.health import check_dataset_anomalies


def _write_dataset(p: Path, slug: str, *, origin: str, body: str) -> Path:
    f = p / "doc" / "datasets" / f"{slug}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "{origin}"\n{body}\n---\n', encoding="utf-8")
    return f


def test_external_with_derivation_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "x", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19"}\n'
                        'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:w-r1", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}')
    issues = check_dataset_anomalies(tmp_path)
    codes = {i["code"] for i in issues}
    assert "dataset_origin_block_mismatch" in codes


def test_derived_with_access_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "y", origin="derived",
                   body='derivation: {workflow: "workflow:w", workflow_run: "workflow-run:w-r1", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}\n'
                        'access: {level: "public", verified: true}')
    issues = check_dataset_anomalies(tmp_path)
    codes = {i["code"] for i in issues}
    assert "dataset_origin_block_mismatch" in codes
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_health.py::test_external_with_derivation_flagged -v
```

Expected: import error on `check_dataset_anomalies`.

- [ ] **Step 3: Implement the checker**

In `science-tool/src/science_tool/graph/health.py`, add:

```python
from science_model.frontmatter import frontmatter_to_entity, parse_frontmatter


def _iter_dataset_entities(project_root: Path):
    """Yield (entity, raw_frontmatter, file_path) for every dataset entity in the project."""
    for md in (project_root / "doc" / "datasets").rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") != "dataset":
            continue
        e = frontmatter_to_entity(fm, project=project_root.name, file_path=str(md))
        yield e, fm, md


def check_dataset_anomalies(project_root: Path) -> list[dict]:
    """Run all twelve dataset-related health checks and return found anomalies.

    Each anomaly dict has: code, severity, entity_id, file_path, message.
    """
    issues: list[dict] = []
    for entity, fm, path in _iter_dataset_entities(project_root):
        # #7: external must not carry derivation:
        if entity.origin == "external" and entity.derivation is not None:
            issues.append({
                "code": "dataset_origin_block_mismatch",
                "severity": "error",
                "entity_id": entity.id,
                "file_path": str(path),
                "message": "origin: external entity carries a derivation: block (invariant #7)",
            })
        # #8: derived must not carry access:, accessions:, or local_path:
        if entity.origin == "derived":
            forbidden = []
            if entity.access is not None:
                forbidden.append("access")
            if entity.accessions:
                forbidden.append("accessions")
            if entity.local_path:
                forbidden.append("local_path")
            if forbidden:
                issues.append({
                    "code": "dataset_origin_block_mismatch",
                    "severity": "error",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": f"origin: derived entity carries forbidden field(s): {', '.join(forbidden)} (invariant #8)",
                })
    return issues
```

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "origin_block"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_origin_block_mismatch (#7, #8)"
```

---

### Task 6.3: `dataset_consumed_but_unverified` + `dataset_stale_review` + `dataset_missing_source_url`

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_external_consumed_unverified_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "u", origin="external",
                   body='access: {level: "public", verified: false}\nconsumed_by: ["plan:p1"]')
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_consumed_but_unverified" for i in issues)


def test_external_stale_review_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "s", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2024-01-01", source_url: "https://x"}')
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_stale_review" for i in issues)


def test_external_verified_no_source_url_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "n", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "credential-confirmed", last_reviewed: "2026-04-19"}')
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_missing_source_url" for i in issues)
```

- [ ] **Step 2: Implement**

In `check_dataset_anomalies`, add inside the per-entity loop after the #7/#8 checks:

```python
        if entity.origin == "external" and entity.access is not None:
            a = entity.access
            # consumed_by non-empty + unverified + no exception
            if entity.consumed_by and not a.verified and a.exception.mode == "":
                issues.append({
                    "code": "dataset_consumed_but_unverified",
                    "severity": "error",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": f"consumed by {entity.consumed_by} but access.verified is false and no exception is set",
                })
            # stale review
            if a.verified and a.last_reviewed:
                from datetime import date
                try:
                    reviewed = date.fromisoformat(a.last_reviewed)
                    if (date.today() - reviewed).days > 365:
                        issues.append({
                            "code": "dataset_stale_review",
                            "severity": "warning",
                            "entity_id": entity.id,
                            "file_path": str(path),
                            "message": f"last_reviewed {a.last_reviewed} is older than 12 months",
                        })
                except ValueError:
                    pass
            # missing source_url on verified entity
            if a.verified and not a.source_url:
                issues.append({
                    "code": "dataset_missing_source_url",
                    "severity": "warning",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": "access.verified is true but source_url is empty",
                })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "consumed_unverified or stale_review or no_source_url"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): three external-access anomalies"
```

---

### Task 6.4: `dataset_derived_missing_workflow_run` + `dataset_derived_asymmetric_edge` (#9)

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def _write_workflow_run(p: Path, slug: str, *, produces: list[str], inputs: list[str]) -> None:
    f = p / "doc" / "workflow-runs" / f"{slug}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        f'---\nid: "workflow-run:{slug}"\ntype: "workflow-run"\ntitle: "{slug}"\n'
        f'workflow: "workflow:wf"\nproduces: {produces}\ninputs: {inputs}\n---\n',
        encoding="utf-8",
    )


def _derived_dataset_body(workflow_run: str, inputs: list[str]) -> str:
    inp = "[" + ", ".join(f'"{i}"' for i in inputs) + "]"
    return (
        'derivation:\n'
        '  workflow: "workflow:wf"\n'
        f'  workflow_run: "{workflow_run}"\n'
        '  git_commit: "a"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        f'  inputs: {inp}'
    )


def test_derived_missing_workflow_run_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "d1", origin="derived", body=_derived_dataset_body("workflow-run:does-not-exist", []))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_missing_workflow_run" for i in issues)


def test_derived_asymmetric_edge_flagged(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r1", produces=[], inputs=[])  # missing dataset:d2 in produces
    _write_dataset(tmp_path, "d2", origin="derived", body=_derived_dataset_body("workflow-run:w-r1", []))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_asymmetric_edge" for i in issues)


def test_derived_symmetric_edge_no_flag(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r2", produces=["dataset:d3"], inputs=[])
    _write_dataset(tmp_path, "d3", origin="derived", body=_derived_dataset_body("workflow-run:w-r2", []))
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] in {"dataset_derived_missing_workflow_run", "dataset_derived_asymmetric_edge"} for i in issues)
```

- [ ] **Step 2: Implement**

Extend `check_dataset_anomalies` to load workflow-runs first, then check derived entities:

```python
def _load_workflow_runs(project_root: Path) -> dict[str, dict]:
    """Map workflow-run:<slug> -> raw frontmatter dict."""
    runs: dict[str, dict] = {}
    runs_dir = project_root / "doc" / "workflow-runs"
    if not runs_dir.exists():
        return runs
    for md in runs_dir.rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") == "workflow-run" and fm.get("id"):
            runs[str(fm["id"])] = fm
    return runs
```

Then inside `check_dataset_anomalies`, before the per-entity loop, build:

```python
    workflow_runs = _load_workflow_runs(project_root)
```

Inside the loop, after the #7/#8 block, add:

```python
        if entity.origin == "derived" and entity.derivation is not None:
            wf_run_id = entity.derivation.workflow_run
            run_fm = workflow_runs.get(wf_run_id)
            if run_fm is None:
                issues.append({
                    "code": "dataset_derived_missing_workflow_run",
                    "severity": "error",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": f"derivation.workflow_run {wf_run_id} does not resolve to a workflow-run entity",
                })
            else:
                produces = list(run_fm.get("produces") or [])
                if entity.id not in produces:
                    issues.append({
                        "code": "dataset_derived_asymmetric_edge",
                        "severity": "error",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"workflow-run {wf_run_id} does not list {entity.id} in produces:",
                    })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "derived_missing or asymmetric"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_derived_missing_workflow_run + asymmetric_edge (#9)"
```

---

### Task 6.5: `dataset_derived_input_chain_broken` (#10) — transitive walk

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_derived_input_chain_unverified_external_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "u_ext", origin="external",
                   body='access: {level: "public", verified: false}')
    _write_workflow_run(tmp_path, "w-r3", produces=["dataset:d4"], inputs=["dataset:u_ext"])
    _write_dataset(tmp_path, "d4", origin="derived", body=_derived_dataset_body("workflow-run:w-r3", ["dataset:u_ext"]))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_input_chain_broken" for i in issues)


def test_derived_cycle_detected(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r4", produces=["dataset:d5"], inputs=["dataset:d6"])
    _write_workflow_run(tmp_path, "w-r5", produces=["dataset:d6"], inputs=["dataset:d5"])
    _write_dataset(tmp_path, "d5", origin="derived", body=_derived_dataset_body("workflow-run:w-r4", ["dataset:d6"]))
    _write_dataset(tmp_path, "d6", origin="derived", body=_derived_dataset_body("workflow-run:w-r5", ["dataset:d5"]))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_input_chain_broken" for i in issues)
```

- [ ] **Step 2: Implement transitive walk**

Add to `health.py`:

```python
def _passes_gate(entity_id: str, datasets_by_id: dict[str, "Entity"], visited: set[str]) -> tuple[bool, str]:
    """Recursively check whether `entity_id` transitively passes the gate.

    Returns (pass, broken_link_msg). Cycles return (False, "cycle at <id>").
    """
    if entity_id in visited:
        return False, f"cycle at {entity_id}"
    visited.add(entity_id)
    e = datasets_by_id.get(entity_id)
    if e is None:
        return False, f"missing entity {entity_id}"
    if e.origin == "external":
        if e.access is None:
            return False, f"external {entity_id} missing access block"
        if e.access.verified or e.access.exception.mode != "":
            return True, ""
        return False, f"external {entity_id} unverified and no exception"
    if e.origin == "derived":
        if e.derivation is None:
            return False, f"derived {entity_id} missing derivation"
        for inp in e.derivation.inputs:
            ok, msg = _passes_gate(inp, datasets_by_id, visited)
            if not ok:
                return False, f"{entity_id} -> {msg}"
        return True, ""
    return False, f"{entity_id} has no origin"
```

In `check_dataset_anomalies`, before the per-entity loop, build:

```python
    datasets_by_id = {e.id: e for e, _, _ in _iter_dataset_entities(project_root)}
```

(Materialize once; the existing iterator runs again inside the loop. Convert the loop to use `datasets_by_id.items()` plus a parallel dict of (fm, path) if you need raw frontmatter — see existing pattern.)

In the per-entity loop's derived branch:

```python
            for inp in entity.derivation.inputs:
                ok, msg = _passes_gate(inp, datasets_by_id, visited=set())
                if not ok:
                    issues.append({
                        "code": "dataset_derived_input_chain_broken",
                        "severity": "error",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"input chain broken: {msg}",
                    })
                    break  # one error per entity is enough
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "input_chain or cycle"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_derived_input_chain_broken with cycle detection (#10)"
```

---

### Task 6.6: `dataset_verified_but_unstageable`

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing test**

```python
def test_verified_no_datapackage_no_localpath_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "us", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}')
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_verified_but_unstageable" for i in issues)


def test_verified_with_local_path_no_flag(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "ls", origin="external",
                   body='local_path: "data/ls/file.csv"\n'
                        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}')
    (tmp_path / "data" / "ls").mkdir(parents=True)
    (tmp_path / "data" / "ls" / "file.csv").write_text("col\n", encoding="utf-8")
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] == "dataset_verified_but_unstageable" for i in issues)
```

- [ ] **Step 2: Implement**

In the external-branch of `check_dataset_anomalies`:

```python
            stageable_path = entity.datapackage or entity.local_path
            if (a.verified or a.exception.mode != "") and not stageable_path:
                issues.append({
                    "code": "dataset_verified_but_unstageable",
                    "severity": "warning",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": "verified entity has neither datapackage: nor local_path:",
                })
            elif stageable_path:
                full = project_root / stageable_path
                if not full.exists():
                    issues.append({
                        "code": "dataset_verified_but_unstageable",
                        "severity": "warning",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"runtime path {stageable_path} does not exist on disk",
                    })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "unstageable"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_verified_but_unstageable"
```

---

### Task 6.7: `dataset_research_package_asymmetric` (#11)

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing test**

```python
def _write_research_package(p: Path, slug: str, *, displays: list[str]) -> None:
    f = p / "research" / "packages" / "lens" / slug / "research-package.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        f'---\nid: "research-package:{slug}"\ntype: "research-package"\ntitle: "{slug}"\n'
        f'displays: {displays}\n---\n',
        encoding="utf-8",
    )


def test_rp_displays_dataset_missing_consumed_by_flagged(tmp_path: Path) -> None:
    _write_research_package(tmp_path, "rp1", displays=["dataset:dr1"])
    _write_workflow_run(tmp_path, "w-r6", produces=["dataset:dr1"], inputs=[])
    _write_dataset(tmp_path, "dr1", origin="derived", body=_derived_dataset_body("workflow-run:w-r6", []))
    # dataset:dr1 has no consumed_by entry for research-package:rp1 -> asymmetric
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_research_package_asymmetric" for i in issues)


def test_dataset_consumed_by_rp_missing_displays_flagged(tmp_path: Path) -> None:
    _write_research_package(tmp_path, "rp2", displays=[])  # empty displays
    _write_workflow_run(tmp_path, "w-r7", produces=["dataset:dr2"], inputs=[])
    body = _derived_dataset_body("workflow-run:w-r7", []) + '\nconsumed_by: ["research-package:rp2"]'
    _write_dataset(tmp_path, "dr2", origin="derived", body=body)
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_research_package_asymmetric" for i in issues)
```

- [ ] **Step 2: Implement**

In `health.py`:

```python
def _load_research_packages(project_root: Path) -> dict[str, list[str]]:
    """Map research-package:<slug> -> displays list."""
    rps: dict[str, list[str]] = {}
    rp_root = project_root / "research" / "packages"
    if not rp_root.exists():
        return rps
    for md in rp_root.rglob("research-package.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") == "research-package" and fm.get("id"):
            rps[str(fm["id"])] = list(fm.get("displays") or [])
    return rps
```

In `check_dataset_anomalies`, before the per-entity loop:

```python
    research_packages = _load_research_packages(project_root)
```

Inside the loop, after the existing checks:

```python
        # #11 forward: dataset.consumed_by -> research-package.displays
        for cons in entity.consumed_by:
            if cons.startswith("research-package:"):
                rp_displays = research_packages.get(cons)
                if rp_displays is None:
                    issues.append({
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"consumed_by lists {cons} but it doesn't resolve to a research-package",
                    })
                elif entity.id not in rp_displays:
                    issues.append({
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"consumed_by lists {cons} but its displays: doesn't include {entity.id}",
                    })

    # #11 reverse: research-package.displays -> dataset.consumed_by
    datasets_by_id_local = {e.id: e for e, _, _ in _iter_dataset_entities(project_root)}
    for rp_id, displays in research_packages.items():
        for ds_id in displays:
            ds = datasets_by_id_local.get(ds_id)
            if ds is None:
                issues.append({
                    "code": "dataset_research_package_asymmetric",
                    "severity": "error",
                    "entity_id": rp_id,
                    "file_path": "",
                    "message": f"research-package.displays lists {ds_id} but no such dataset entity",
                })
            elif rp_id not in ds.consumed_by:
                issues.append({
                    "code": "dataset_research_package_asymmetric",
                    "severity": "error",
                    "entity_id": rp_id,
                    "file_path": "",
                    "message": f"{rp_id} displays {ds_id} but the dataset's consumed_by doesn't include the research-package",
                })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "research_package"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_research_package_asymmetric (#11)"
```

---

### Task 6.8: `data_package_unmigrated` (strict mode)

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing test**

```python
def test_data_package_without_superseded_status_flagged(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "old.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Legacy"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "data_package_unmigrated" for i in issues)


def test_superseded_data_package_no_flag(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "migrated.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:migrated"\ntype: "data-package"\ntitle: "Migrated"\n'
        'status: "superseded"\nsuperseded_by: "research-package:migrated"\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] == "data_package_unmigrated" for i in issues)
```

- [ ] **Step 2: Implement**

After the per-entity loop in `check_dataset_anomalies`:

```python
    dp_dir = project_root / "doc" / "data-packages"
    if dp_dir.exists():
        for md in dp_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            if not result:
                continue
            fm, _ = result
            if fm.get("type") != "data-package":
                continue
            if fm.get("status") != "superseded":
                issues.append({
                    "code": "data_package_unmigrated",
                    "severity": "error",
                    "entity_id": str(fm.get("id", "")),
                    "file_path": str(md),
                    "message": "unmigrated data-package; run `science-tool data-package migrate` to split into derived dataset(s) + research-package",
                })
    return issues
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "unmigrated or superseded"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): data_package_unmigrated (strict mode signal)"
```

---

### Task 6.9: `dataset_invariant_violation` (umbrella for #1, #4, #5, #6)

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing tests for #1 (umbrella consumed) and #5 (lineage drift)**

```python
def test_umbrella_in_consumed_by_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "umb", origin="external",
                   body='access: {level: "mixed", verified: false}\nsiblings: ["dataset:c1"]')
    _write_dataset(tmp_path, "c1", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
                        'parent_dataset: "dataset:umb"\nconsumed_by: ["plan:p"]')
    _write_dataset(tmp_path, "wrong", origin="external",
                   body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://y"}\n'
                        'consumed_by: []')
    # Now create a plan that references the umbrella in another entity's consumed_by — synthetic via consumed_by mention
    f = tmp_path / "doc" / "datasets" / "consumer.md"
    f.write_text(
        '---\nid: "dataset:consumer"\ntype: "dataset"\ntitle: "Consumer"\norigin: "external"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://z"}\n'
        'consumed_by: ["dataset:umb"]\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_invariant_violation" and "umbrella" in i["message"].lower() for i in issues)


def test_lineage_drift_flagged(tmp_path: Path) -> None:
    # parent claims sibling, child doesn't claim parent
    _write_dataset(tmp_path, "p1", origin="external",
                   body='access: {level: "public", verified: false}\nsiblings: ["dataset:c2"]')
    _write_dataset(tmp_path, "c2", origin="external",
                   body='access: {level: "public", verified: false}\nparent_dataset: ""')
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_invariant_violation" and "lineage" in i["message"].lower() for i in issues)
```

- [ ] **Step 2: Implement umbrella + lineage checks**

After the per-entity loop and before the data-package check:

```python
    # #1 umbrella consumed: an entity with siblings: non-empty must not appear in any
    # other entity's consumed_by.
    umbrellas = {e.id for e, _, _ in _iter_dataset_entities(project_root) if e.siblings}
    for entity, _, path in _iter_dataset_entities(project_root):
        for cons in entity.consumed_by:
            if cons in umbrellas:
                issues.append({
                    "code": "dataset_invariant_violation",
                    "severity": "warning",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": f"umbrella {cons} appears in {entity.id}.consumed_by (invariant #1)",
                })

    # #5 lineage symmetry: parent_dataset ↔ siblings
    by_id = {e.id: e for e, _, _ in _iter_dataset_entities(project_root)}
    for entity, _, path in _iter_dataset_entities(project_root):
        for sib_id in entity.siblings:
            child = by_id.get(sib_id)
            if child is not None and child.parent_dataset != entity.id:
                issues.append({
                    "code": "dataset_invariant_violation",
                    "severity": "warning",
                    "entity_id": entity.id,
                    "file_path": str(path),
                    "message": f"lineage drift: {entity.id} lists sibling {sib_id} but {sib_id}.parent_dataset != {entity.id}",
                })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "umbrella or lineage"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_invariant_violation for umbrella + lineage drift"
```

---

### Task 6.10: `dataset_cached_field_drift`

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Add failing test**

```python
import yaml


def test_cached_field_drift_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "drift", origin="external",
                   body='license: "CC-BY-4.0"\n'
                        'ontology_terms: ["UBERON:0001"]\n'
                        'datapackage: "data/drift/datapackage.yaml"\n'
                        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}')
    rt = tmp_path / "data" / "drift" / "datapackage.yaml"
    rt.parent.mkdir(parents=True)
    rt.write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0"],
        "name": "drift",
        "license": "CC0-1.0",  # drift!
        "ontology_terms": ["UBERON:0002"],  # drift!
        "resources": [{"name": "x", "path": "x.csv", "format": "csv"}],
    }))
    issues = check_dataset_anomalies(tmp_path)
    drift_msgs = [i["message"] for i in issues if i["code"] == "dataset_cached_field_drift"]
    assert any("license" in m for m in drift_msgs)
    assert any("ontology_terms" in m for m in drift_msgs)
```

- [ ] **Step 2: Implement**

In `health.py`, add a helper and extend the loop:

```python
import yaml as _yaml


def _load_runtime_pkg(project_root: Path, datapackage_path: str) -> dict | None:
    p = project_root / datapackage_path
    if not p.exists():
        return None
    try:
        return _yaml.safe_load(p.read_text(encoding="utf-8"))
    except _yaml.YAMLError:
        return None
```

Inside the per-entity loop (any origin):

```python
        if entity.datapackage:
            rt = _load_runtime_pkg(project_root, entity.datapackage)
            if rt is not None:
                # The narrow set of legitimately-mirrored cached fields.
                fm_license = fm.get("license", "")
                rt_license = rt.get("license", "")
                if fm_license and rt_license and fm_license != rt_license:
                    issues.append({
                        "code": "dataset_cached_field_drift",
                        "severity": "warning",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"license drift: entity={fm_license!r} runtime={rt_license!r}",
                    })
                fm_ot = sorted(fm.get("ontology_terms") or [])
                rt_ot = sorted(rt.get("ontology_terms") or [])
                if fm_ot and rt_ot and fm_ot != rt_ot:
                    issues.append({
                        "code": "dataset_cached_field_drift",
                        "severity": "warning",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"ontology_terms drift: entity={fm_ot} runtime={rt_ot}",
                    })
                fm_uc = fm.get("update_cadence", "")
                rt_uc = rt.get("update_cadence", "")
                if fm_uc and rt_uc and fm_uc != rt_uc:
                    issues.append({
                        "code": "dataset_cached_field_drift",
                        "severity": "warning",
                        "entity_id": entity.id,
                        "file_path": str(path),
                        "message": f"update_cadence drift: entity={fm_uc!r} runtime={rt_uc!r}",
                    })
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "cached_field_drift"
git add src/science_tool/graph/health.py tests/test_health.py
git commit -m "feat(health): dataset_cached_field_drift on the three legitimately-mirrored fields"
```

---

### Task 6.11: Wire `check_dataset_anomalies` into `science-tool health` CLI

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py` (or wherever `science-tool health` is wired — probably `cli.py` or a sub-cli)
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Locate the existing CLI wiring**

```bash
grep -rn "def health" src/science_tool/ | head
grep -rn "health" src/science_tool/cli.py | head
```

Identify where the `health` command builds its result dict.

- [ ] **Step 2: Add an integration test**

Append:

```python
def test_health_cli_includes_dataset_section(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "u", origin="external",
                   body='access: {level: "public", verified: false}\nconsumed_by: ["plan:p"]')
    from science_tool.graph.health import collect_project_health  # adjust to actual entry point
    result = collect_project_health(tmp_path)
    assert "dataset_anomalies" in result
    codes = {i["code"] for i in result["dataset_anomalies"]}
    assert "dataset_consumed_but_unverified" in codes
```

- [ ] **Step 3: Wire it in**

In the existing project-health aggregator function, add:

```python
    project_health["dataset_anomalies"] = check_dataset_anomalies(project_root)
```

(Adapt the dict key name to match existing convention — e.g., if other groups are nested under `anomalies`, follow that.)

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_health.py -v -k "cli_includes_dataset"
git add src/science_tool/graph/health.py src/science_tool/cli.py tests/test_health.py
git commit -m "feat(health): expose dataset anomalies via science-tool health"
```

---

## Phase 7: `science-tool dataset` CLI extensions

### Task 7.1: `dataset list --origin external|derived` filter

**Files:**
- Modify: `science-tool/src/science_tool/cli.py` (or wherever `dataset list` lives — search first)
- Modify: `science-tool/tests/test_datasets_cli.py` (existing)

- [ ] **Step 1: Locate the existing `dataset list` command**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
grep -rn "@.*group\|def.*dataset\|name=\"dataset\"" src/science_tool/ | head
```

Identify the file and the existing list subcommand. Note the pattern (Click group → `@dataset.command(name="list")`).

- [ ] **Step 2: Write failing test**

Append to `tests/test_datasets_cli.py` (or create the file if needed):

```python
from click.testing import CliRunner
from pathlib import Path

from science_tool.cli import main as science_cli  # adjust to actual entry


def _seed_two_origins(root: Path) -> None:
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "ext.md").write_text(
        '---\nid: "dataset:ext"\ntype: "dataset"\ntitle: "Ext"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n', encoding="utf-8",
    )
    (root / "doc" / "datasets" / "der.md").write_text(
        '---\nid: "dataset:der"\ntype: "dataset"\ntitle: "Der"\norigin: "derived"\n'
        'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:r", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}\n---\n',
        encoding="utf-8",
    )


def test_dataset_list_origin_filter(tmp_path: Path) -> None:
    _seed_two_origins(tmp_path)
    runner = CliRunner()
    res = runner.invoke(science_cli, ["dataset", "list", "--origin", "external"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code == 0
    assert "dataset:ext" in res.output
    assert "dataset:der" not in res.output

    res2 = runner.invoke(science_cli, ["dataset", "list", "--origin", "derived"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert "dataset:der" in res2.output
    assert "dataset:ext" not in res2.output
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_datasets_cli.py -v -k "origin_filter"
```

Expected: FAIL — `--origin` flag not recognized.

- [ ] **Step 4: Add the flag**

Locate the `dataset list` Click command and extend its decorators:

```python
@dataset_group.command(name="list")
@click.option("--origin", type=click.Choice(["external", "derived"]), default=None,
              help="Filter by dataset origin.")
# ... existing options ...
def dataset_list(origin: str | None, ...) -> None:
    project_root = _project_root()  # existing helper
    entities = _list_dataset_entities(project_root)  # existing
    if origin is not None:
        entities = [e for e in entities if e.origin == origin]
    # ... existing rendering ...
```

(The exact decorator layout depends on the existing pattern; follow it.)

- [ ] **Step 5: Verify + commit**

```bash
uv run --frozen pytest tests/test_datasets_cli.py -v -k "origin_filter"
git add src/science_tool/cli.py tests/test_datasets_cli.py
git commit -m "feat(dataset cli): add --origin filter to list"
```

---

### Task 7.2: `dataset register-run` — read inputs and write per-output datapackages

**Files:**
- Create: `science-tool/src/science_tool/datasets_register.py`
- Test: `science-tool/tests/test_dataset_register_run.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_dataset_register_run.py`:

```python
"""Tests for `science-tool dataset register-run`."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_workflow_and_run(root: Path, *, run_resources: list[dict]) -> None:
    """Create workflow.md (with outputs:), workflow-run.md, and a run-aggregate datapackage.yaml."""
    wf_dir = root / "doc" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "wf.md").write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n'
        'outputs:\n'
        '  - slug: "kappa"\n'
        '    title: "Kappa"\n'
        '    resource_names: ["kappa"]\n'
        '    ontology_terms: []\n'
        '  - slug: "structural"\n'
        '    title: "Structural"\n'
        '    resource_names: ["structural"]\n'
        '    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    runs_dir = root / "doc" / "workflow-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "WF r1"\n'
        'workflow: "workflow:wf"\nproduces: []\ninputs: []\n---\n',
        encoding="utf-8",
    )
    rt_dir = root / "results" / "wf" / "r1"
    rt_dir.mkdir(parents=True, exist_ok=True)
    (rt_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0"],
        "name": "wf-r1",
        "resources": run_resources,
    }), encoding="utf-8")


def test_register_run_writes_per_output_datapackages(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[
        {"name": "kappa", "path": "kappa.csv", "format": "csv", "bytes": 100, "hash": "sha256:a"},
        {"name": "structural", "path": "structural.csv", "format": "csv", "bytes": 200, "hash": "sha256:b"},
    ])
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0, res.output
    kappa_dp = tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml"
    structural_dp = tmp_path / "results" / "wf" / "r1" / "structural" / "datapackage.yaml"
    assert kappa_dp.exists()
    assert structural_dp.exists()
    kappa = yaml.safe_load(kappa_dp.read_text())
    assert [r["name"] for r in kappa["resources"]] == ["kappa"]
    structural = yaml.safe_load(structural_dp.read_text())
    assert [r["name"] for r in structural["resources"]] == ["structural"]
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "per_output"
```

Expected: FAIL — `register-run` subcommand doesn't exist.

- [ ] **Step 3: Implement core**

Create `science-tool/src/science_tool/datasets_register.py`:

```python
"""`science-tool dataset register-run` — emit derived dataset entities + per-output datapackages."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter


def _read_workflow_outputs(project_root: Path, workflow_id: str) -> list[dict]:
    """Return the workflow's `outputs:` block. Raises FileNotFoundError if missing."""
    slug = workflow_id.removeprefix("workflow:")
    wf_path = project_root / "doc" / "workflows" / f"{slug}.md"
    if not wf_path.exists():
        raise FileNotFoundError(f"workflow entity not found: {wf_path}")
    fm, _ = parse_frontmatter(wf_path) or ({}, "")
    return list(fm.get("outputs") or [])


def _read_run(project_root: Path, run_id: str) -> tuple[Path, dict]:
    slug = run_id.removeprefix("workflow-run:")
    run_path = project_root / "doc" / "workflow-runs" / f"{slug}.md"
    if not run_path.exists():
        raise FileNotFoundError(f"workflow-run entity not found: {run_path}")
    fm, _ = parse_frontmatter(run_path) or ({}, "")
    return run_path, fm


def _read_run_aggregate_datapackage(project_root: Path, workflow_slug: str, run_slug: str) -> tuple[Path, dict]:
    rt = project_root / "results" / workflow_slug / run_slug / "datapackage.yaml"
    if not rt.exists():
        raise FileNotFoundError(f"run-aggregate datapackage not found: {rt}")
    return rt, yaml.safe_load(rt.read_text(encoding="utf-8"))


def write_per_output_datapackages(project_root: Path, workflow_run_id: str) -> list[Path]:
    """Write one datapackage.yaml per declared output. Returns list of written paths."""
    run_path, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_slug = workflow_run_id.removeprefix("workflow-run:")
    outputs = _read_workflow_outputs(project_root, workflow_id)
    if not outputs:
        raise ValueError(f"workflow {workflow_id} has no outputs[] block; add one before registering")
    rt_path, rt = _read_run_aggregate_datapackage(project_root, workflow_slug, run_slug)
    by_name = {r["name"]: r for r in (rt.get("resources") or [])}
    written: list[Path] = []
    for out in outputs:
        slug = str(out["slug"])
        names = list(out.get("resource_names") or [])
        out_resources = []
        for n in names:
            if n not in by_name:
                raise ValueError(f"output {slug!r} declares resource_name {n!r} but run datapackage has no such resource")
            r = dict(by_name[n])
            # Make path relative to the per-output directory.
            r["path"] = Path(r["path"]).name  # strip parent dirs; resources sit alongside the per-output datapackage
            out_resources.append(r)
        out_dir = rt_path.parent / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_dp_path = out_dir / "datapackage.yaml"
        out_dp = {
            "profiles": ["science-pkg-runtime-1.0"],
            "name": f"{workflow_slug}-{run_slug}-{slug}",
            "title": str(out.get("title", "")),
            "resources": out_resources,
        }
        if out.get("ontology_terms"):
            out_dp["ontology_terms"] = list(out["ontology_terms"])
        out_dp_path.write_text(yaml.safe_dump(out_dp, sort_keys=False), encoding="utf-8")
        written.append(out_dp_path)
    return written
```

Then wire it into the CLI. In the same file or `cli.py`:

```python
import click


@click.command(name="register-run")
@click.argument("workflow_run_id")
def register_run(workflow_run_id: str) -> None:
    """Emit derived dataset entities + per-output datapackages for a completed workflow run."""
    project_root = _project_root()
    paths = write_per_output_datapackages(project_root, workflow_run_id)
    for p in paths:
        click.echo(f"wrote {p.relative_to(project_root)}")
    # Entity emission and symmetric edges land in Tasks 7.3 and 7.4.
```

Register `register_run` under the `dataset` Click group (follow the existing `dataset list` pattern).

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "per_output"
git add src/science_tool/datasets_register.py src/science_tool/cli.py tests/test_dataset_register_run.py
git commit -m "feat(dataset cli): register-run writes per-output datapackages"
```

---

### Task 7.3: `register-run` writes derived dataset entities

**Files:**
- Modify: `science-tool/src/science_tool/datasets_register.py`
- Modify: `science-tool/tests/test_dataset_register_run.py`

- [ ] **Step 1: Add failing test**

```python
def test_register_run_writes_dataset_entities(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[
        {"name": "kappa", "path": "kappa.csv", "format": "csv"},
    ])
    runner = CliRunner()
    res = runner.invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code == 0, res.output
    ds_path = tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md"
    assert ds_path.exists()
    body = ds_path.read_text()
    assert 'origin: "derived"' in body
    assert 'workflow_run: "workflow-run:wf-r1"' in body
    assert 'datapackage: "results/wf/r1/kappa/datapackage.yaml"' in body
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "writes_dataset_entities"
```

Expected: FAIL — entity not written.

- [ ] **Step 3: Implement entity writer**

In `datasets_register.py`, add:

```python
def _entity_yaml_block(*, slug: str, title: str, workflow_id: str, workflow_run_id: str, git_commit: str, config_snapshot: str, produced_at: str, inputs: list[str], dp_path_rel: str, ontology_terms: list[str]) -> str:
    entity_id = f"dataset:{slug}"
    return (
        "---\n"
        f'id: "{entity_id}"\n'
        'type: "dataset"\n'
        f'title: "{title}"\n'
        'status: "active"\n'
        'profiles: ["science-pkg-entity-1.0"]\n'
        'origin: "derived"\n'
        'tier: "use-now"\n'
        'license: "internal"\n'
        'update_cadence: "static"\n'
        f'ontology_terms: {ontology_terms!r}\n'
        f'datapackage: "{dp_path_rel}"\n'
        'derivation:\n'
        f'  workflow: "{workflow_id}"\n'
        f'  workflow_run: "{workflow_run_id}"\n'
        f'  git_commit: "{git_commit}"\n'
        f'  config_snapshot: "{config_snapshot}"\n'
        f'  produced_at: "{produced_at}"\n'
        f'  inputs: {inputs!r}\n'
        'consumed_by: []\n'
        f'created: "{produced_at[:10]}"\n'
        f'updated: "{produced_at[:10]}"\n'
        "---\n"
    )


def write_derived_dataset_entities(project_root: Path, workflow_run_id: str) -> list[Path]:
    run_path, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_slug = workflow_run_id.removeprefix("workflow-run:")
    outputs = _read_workflow_outputs(project_root, workflow_id)
    git_commit = str(run_fm.get("git_commit", ""))
    config_snapshot = str(run_fm.get("config_snapshot", ""))
    produced_at = str(run_fm.get("last_run") or datetime.now(timezone.utc).isoformat())
    inputs = list(run_fm.get("inputs") or [])
    written: list[Path] = []
    for out in outputs:
        slug = f"{workflow_slug}-{run_slug}-{out['slug']}"
        ds_path = project_root / "doc" / "datasets" / f"{slug}.md"
        ds_path.parent.mkdir(parents=True, exist_ok=True)
        dp_rel = f"results/{workflow_slug}/{run_slug}/{out['slug']}/datapackage.yaml"
        body = _entity_yaml_block(
            slug=slug, title=str(out.get("title", slug)),
            workflow_id=workflow_id, workflow_run_id=workflow_run_id,
            git_commit=git_commit, config_snapshot=config_snapshot,
            produced_at=produced_at, inputs=inputs, dp_path_rel=dp_rel,
            ontology_terms=list(out.get("ontology_terms") or []),
        )
        ds_path.write_text(body, encoding="utf-8")
        written.append(ds_path)
    return written
```

In the CLI command, after `write_per_output_datapackages`:

```python
    ds_paths = write_derived_dataset_entities(project_root, workflow_run_id)
    for p in ds_paths:
        click.echo(f"wrote {p.relative_to(project_root)}")
```

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "writes_dataset_entities"
git add src/science_tool/datasets_register.py src/science_tool/cli.py tests/test_dataset_register_run.py
git commit -m "feat(dataset cli): register-run writes derived dataset entities"
```

---

### Task 7.4: `register-run` writes symmetric edges

**Files:**
- Modify: `science-tool/src/science_tool/datasets_register.py`
- Modify: `science-tool/tests/test_dataset_register_run.py`

- [ ] **Step 1: Add failing test**

```python
def test_register_run_appends_to_workflow_run_produces(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[
        {"name": "kappa", "path": "kappa.csv", "format": "csv"},
    ])
    CliRunner().invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    body = (tmp_path / "doc" / "workflow-runs" / "wf-r1.md").read_text()
    assert "dataset:wf-wf-r1-kappa" in body  # produces gained the new dataset


def test_register_run_appends_workflow_run_to_upstream_consumed_by(tmp_path: Path) -> None:
    # Pre-seed an upstream input dataset.
    (tmp_path / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "doc" / "datasets" / "up.md").write_text(
        '---\nid: "dataset:up"\ntype: "dataset"\ntitle: "Up"\norigin: "external"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        'consumed_by: []\n---\n', encoding="utf-8",
    )
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    # Add inputs to the workflow-run.
    runs = tmp_path / "doc" / "workflow-runs" / "wf-r1.md"
    runs.write_text(runs.read_text().replace("inputs: []", 'inputs: ["dataset:up"]'), encoding="utf-8")
    CliRunner().invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    body = (tmp_path / "doc" / "datasets" / "up.md").read_text()
    assert "workflow-run:wf-r1" in body  # appended to upstream consumed_by
```

- [ ] **Step 2: Implement symmetric edge writers**

Add to `datasets_register.py`:

```python
import re


def _append_to_yaml_list_field(file_path: Path, field: str, value: str) -> None:
    """Append `value` to a YAML list field in the frontmatter, deduplicated. In-place edit."""
    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    fm = yaml.safe_load(parts[1]) or {}
    current = list(fm.get(field) or [])
    if value in current:
        return  # deduplicated; no-op
    current.append(value)
    fm[field] = current
    new_fm = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    file_path.write_text(f"---\n{new_fm}---{parts[2]}", encoding="utf-8")


def write_symmetric_edges(project_root: Path, workflow_run_id: str, written_dataset_ids: list[str]) -> None:
    """Append produces[] on workflow-run + consumed_by on each upstream input."""
    run_slug = workflow_run_id.removeprefix("workflow-run:")
    run_path = project_root / "doc" / "workflow-runs" / f"{run_slug}.md"
    for ds_id in written_dataset_ids:
        _append_to_yaml_list_field(run_path, "produces", ds_id)
    # Also append workflow-run to each upstream input dataset's consumed_by.
    fm, _ = parse_frontmatter(run_path) or ({}, "")
    for upstream_id in list(fm.get("inputs") or []):
        slug = upstream_id.removeprefix("dataset:")
        upstream_path = project_root / "doc" / "datasets" / f"{slug}.md"
        if upstream_path.exists():
            _append_to_yaml_list_field(upstream_path, "consumed_by", workflow_run_id)
```

Wire into the CLI command:

```python
    write_symmetric_edges(project_root, workflow_run_id, [p.stem.replace(".md", "") and f"dataset:{p.stem}" for p in ds_paths])
```

(Cleaner: track the IDs as you write the entities — keep a list returned from `write_derived_dataset_entities` of `(path, id)` tuples instead.)

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "produces or consumed_by"
git add src/science_tool/datasets_register.py src/science_tool/cli.py tests/test_dataset_register_run.py
git commit -m "feat(dataset cli): register-run writes symmetric edges (produces, consumed_by)"
```

---

### Task 7.5: `register-run` idempotency

**Files:**
- Modify: `science-tool/tests/test_dataset_register_run.py`

- [ ] **Step 1: Add idempotency test**

```python
def test_register_run_idempotent(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    runner = CliRunner()
    res1 = runner.invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res1.exit_code == 0
    body1 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rt1 = (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").read_text()
    res2 = runner.invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res2.exit_code == 0
    body2 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rt2 = (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").read_text()
    # Files unchanged on second invocation. (Allow updated-date jitter if your writer uses now().)
    assert rt1 == rt2
    # Symmetric edges deduplicated.
    runs_body = (tmp_path / "doc" / "workflow-runs" / "wf-r1.md").read_text()
    assert runs_body.count("dataset:wf-wf-r1-kappa") == 1
```

- [ ] **Step 2: Verify**

```bash
uv run --frozen pytest tests/test_dataset_register_run.py -v -k "idempotent"
```

If failing, the entity writer must be made idempotent (skip writing when the entity exists with identical content; the dedup in `_append_to_yaml_list_field` already handles symmetric edges). Adjust `write_derived_dataset_entities` to compare and skip on identical content.

- [ ] **Step 3: Commit**

```bash
git add src/science_tool/datasets_register.py tests/test_dataset_register_run.py
git commit -m "feat(dataset cli): register-run idempotent"
```

---

### Task 7.6: `dataset reconcile <slug>` — narrow cached-field drift check

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_dataset_reconcile.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_dataset_reconcile.py`:

```python
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(tmp_path: Path, *, entity_license: str, runtime_license: str) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X"\norigin: "external"\n'
        f'license: "{entity_license}"\n'
        'datapackage: "data/x/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        '---\n', encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0"], "name": "x",
        "license": runtime_license,
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")


def test_reconcile_in_sync_exits_zero(tmp_path: Path) -> None:
    _seed(tmp_path, entity_license="CC-BY-4.0", runtime_license="CC-BY-4.0")
    res = CliRunner().invoke(science_cli, ["dataset", "reconcile", "x"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code == 0


def test_reconcile_drift_exits_nonzero(tmp_path: Path) -> None:
    _seed(tmp_path, entity_license="CC-BY-4.0", runtime_license="CC0-1.0")
    res = CliRunner().invoke(science_cli, ["dataset", "reconcile", "x"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code != 0
    assert "license" in res.output
```

- [ ] **Step 2: Run failing test**

```bash
uv run --frozen pytest tests/test_dataset_reconcile.py -v
```

Expected: FAIL — `reconcile` subcommand missing.

- [ ] **Step 3: Implement**

Add to `cli.py` (under the `dataset` group):

```python
@dataset_group.command(name="reconcile")
@click.argument("slug")
def dataset_reconcile(slug: str) -> None:
    """Check cached-field drift between dataset entity and its runtime datapackage.yaml."""
    project_root = _project_root()
    md = project_root / "doc" / "datasets" / f"{slug}.md"
    if not md.exists():
        click.echo(f"no such dataset entity: {md}", err=True)
        raise click.exceptions.Exit(2)
    fm, _ = parse_frontmatter(md) or ({}, "")
    dp_rel = fm.get("datapackage", "")
    if not dp_rel:
        click.echo("no datapackage: pointer; nothing to reconcile", err=True)
        raise click.exceptions.Exit(0)
    rt_path = project_root / dp_rel
    if not rt_path.exists():
        click.echo(f"runtime datapackage missing: {rt_path}", err=True)
        raise click.exceptions.Exit(1)
    rt = yaml.safe_load(rt_path.read_text(encoding="utf-8"))
    drifts = []
    for field in ("license", "update_cadence"):
        e_v = fm.get(field, "")
        r_v = rt.get(field, "")
        if e_v and r_v and e_v != r_v:
            drifts.append(f"{field}: entity={e_v!r} runtime={r_v!r}")
    e_ot = sorted(fm.get("ontology_terms") or [])
    r_ot = sorted(rt.get("ontology_terms") or [])
    if e_ot and r_ot and e_ot != r_ot:
        drifts.append(f"ontology_terms: entity={e_ot} runtime={r_ot}")
    if drifts:
        for d in drifts:
            click.echo(d)
        raise click.exceptions.Exit(1)
    click.echo("in sync")
```

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_dataset_reconcile.py -v
git add src/science_tool/cli.py tests/test_dataset_reconcile.py
git commit -m "feat(dataset cli): reconcile checks narrow cached-field drift"
```

---

## Phase 8: `science-tool data-package migrate` + strict mode

### Task 8.1: `data-package migrate` core split

**Files:**
- Create: `science-tool/src/science_tool/datapackage_migrate.py`
- Test: `science-tool/tests/test_data_package_migrate.py`

- [ ] **Step 1: Write failing test**

Create `science-tool/tests/test_data_package_migrate.py`:

```python
"""Tests for `science-tool data-package migrate <slug>`."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_legacy_data_package(root: Path) -> None:
    # Workflow with outputs:
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "wf.md").write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n'
        'outputs:\n'
        '  - slug: "kappa"\n'
        '    title: "Kappa"\n'
        '    resource_names: ["kappa"]\n'
        '    ontology_terms: []\n---\n', encoding="utf-8",
    )
    # Workflow run.
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "WF r1"\n'
        'workflow: "workflow:wf"\nproduces: []\ninputs: []\n'
        'git_commit: "abc1234"\nlast_run: "2026-04-19T12:00:00Z"\n---\n', encoding="utf-8",
    )
    # Legacy data-package entity.
    (root / "doc" / "data-packages").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "data-packages" / "old.md").write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Old DP"\nstatus: "active"\n'
        'manifest: "research/packages/old/datapackage.json"\n'
        'cells: "research/packages/old/cells.json"\n'
        'workflow_run: "workflow-run:wf-r1"\n---\n', encoding="utf-8",
    )
    rp_dir = root / "research" / "packages" / "old"
    rp_dir.mkdir(parents=True, exist_ok=True)
    (rp_dir / "datapackage.json").write_text(json.dumps({
        "name": "old", "title": "Old DP", "profile": "science-research-package", "version": "0.1",
        "resources": [{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        "research": {
            "cells": "cells.json", "figures": [], "vegalite_specs": [], "code_excerpts": [],
            "provenance": {
                "workflow": "workflow:wf", "config": "config.yaml",
                "last_run": "2026-04-19T12:00:00Z", "git_commit": "abc1234",
                "repository": "", "inputs": [], "scripts": [],
            },
        },
    }), encoding="utf-8")


def test_migrate_emits_derived_dataset_entity(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    res = CliRunner().invoke(science_cli, ["data-package", "migrate", "old"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code == 0, res.output
    ds_path = tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md"
    assert ds_path.exists()
    body = ds_path.read_text()
    assert 'origin: "derived"' in body
    assert 'workflow_run: "workflow-run:wf-r1"' in body


def test_migrate_emits_research_package_entity(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    CliRunner().invoke(science_cli, ["data-package", "migrate", "old"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    rp_path = tmp_path / "research" / "packages" / "old" / "research-package.md"
    assert rp_path.exists()
    body = rp_path.read_text()
    assert 'type: "research-package"' in body
    assert "dataset:wf-wf-r1-kappa" in body  # in displays


def test_migrate_marks_old_data_package_superseded(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    CliRunner().invoke(science_cli, ["data-package", "migrate", "old"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    body = (tmp_path / "doc" / "data-packages" / "old.md").read_text()
    assert 'status: "superseded"' in body
    assert "research-package:old" in body  # superseded_by
```

- [ ] **Step 2: Run failing test**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_data_package_migrate.py -v -k "emits_derived"
```

Expected: FAIL — `data-package migrate` subcommand doesn't exist.

- [ ] **Step 3: Implement**

Create `science-tool/src/science_tool/datapackage_migrate.py`:

```python
"""`science-tool data-package migrate <slug>` — split legacy data-package into derived datasets + research-package."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter
from science_tool.datasets_register import (
    write_per_output_datapackages,
    write_derived_dataset_entities,
    write_symmetric_edges,
    _read_workflow_outputs,
    _read_run,
)


def _research_package_yaml(*, slug: str, dp_dir_rel: str, manifest_rel: str, cells_rel: str, figures: list[dict], vegalite: list[dict], excerpts: list[dict], displays: list[str], related: list[str]) -> str:
    rp_id = f"research-package:{slug}"
    return (
        "---\n"
        f'id: "{rp_id}"\n'
        'type: "research-package"\n'
        f'title: "{slug}"\n'
        'status: "active"\n'
        f'displays: {displays!r}\n'
        f'location: "{dp_dir_rel}"\n'
        f'manifest: "{manifest_rel}"\n'
        f'cells: "{cells_rel}"\n'
        f'figures: {figures!r}\n'
        f'vegalite_specs: {vegalite!r}\n'
        f'code_excerpts: {excerpts!r}\n'
        f'related: {related!r}\n'
        "---\n"
    )


def migrate_data_package(project_root: Path, dp_slug: str) -> None:
    """Split a legacy data-package entity into derived datasets + a research-package."""
    dp_path = project_root / "doc" / "data-packages" / f"{dp_slug}.md"
    if not dp_path.exists():
        raise FileNotFoundError(f"no such data-package: {dp_path}")
    dp_fm, _ = parse_frontmatter(dp_path) or ({}, "")
    workflow_run_id = str(dp_fm.get("workflow_run", ""))
    if not workflow_run_id:
        raise ValueError("data-package has no workflow_run pointer; cannot migrate")
    # Validate that the workflow has outputs:
    run_path, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    outputs = _read_workflow_outputs(project_root, workflow_id)
    if not outputs:
        raise ValueError(f"{workflow_id} has no outputs[] block; add one before migrating data-package:{dp_slug}")
    # Reuse register-run to write per-output runtime datapackages + derived dataset entities + symmetric edges.
    write_per_output_datapackages(project_root, workflow_run_id)
    ds_paths = write_derived_dataset_entities(project_root, workflow_run_id)
    written_ids = [f"dataset:{p.stem}" for p in ds_paths]
    write_symmetric_edges(project_root, workflow_run_id, written_ids)
    # Locate the legacy bundle dir + load the research extension fields from datapackage.json.
    manifest_rel = str(dp_fm.get("manifest", ""))
    bundle_dir = project_root / Path(manifest_rel).parent if manifest_rel else None
    figures: list[dict] = []
    vegalite: list[dict] = []
    excerpts: list[dict] = []
    cells_rel = str(dp_fm.get("cells", ""))
    if bundle_dir and (bundle_dir / "datapackage.json").exists():
        descriptor = json.loads((bundle_dir / "datapackage.json").read_text(encoding="utf-8"))
        research = descriptor.get("research") or {}
        figures = list(research.get("figures") or [])
        vegalite = list(research.get("vegalite_specs") or [])
        excerpts = list(research.get("code_excerpts") or [])
        if not cells_rel:
            cells_rel = research.get("cells", "")
    # Write the research-package entity.
    rp_path = (bundle_dir / "research-package.md") if bundle_dir else (project_root / "research" / "packages" / dp_slug / "research-package.md")
    rp_path.parent.mkdir(parents=True, exist_ok=True)
    rp_dir_rel = str(rp_path.parent.relative_to(project_root))
    rp_yaml = _research_package_yaml(
        slug=dp_slug, dp_dir_rel=rp_dir_rel,
        manifest_rel=manifest_rel, cells_rel=cells_rel,
        figures=figures, vegalite=vegalite, excerpts=excerpts,
        displays=written_ids, related=[workflow_run_id],
    )
    rp_path.write_text(rp_yaml, encoding="utf-8")
    # Append research-package to each derived dataset's consumed_by (invariant #11 symmetry).
    from science_tool.datasets_register import _append_to_yaml_list_field
    for ds_id in written_ids:
        slug = ds_id.removeprefix("dataset:")
        ds_path = project_root / "doc" / "datasets" / f"{slug}.md"
        _append_to_yaml_list_field(ds_path, "consumed_by", f"research-package:{dp_slug}")
    # Mark the old data-package as superseded.
    dp_text = dp_path.read_text(encoding="utf-8")
    parts = dp_text.split("---", 2)
    fm = yaml.safe_load(parts[1]) or {}
    fm["status"] = "superseded"
    fm["superseded_by"] = f"research-package:{dp_slug}"
    new_fm = yaml.safe_dump(fm, sort_keys=False)
    dp_path.write_text(f"---\n{new_fm}---{parts[2]}", encoding="utf-8")
```

In `cli.py`, register the command under a new `data-package` group:

```python
@main.group(name="data-package")
def data_package_group() -> None:
    """Legacy data-package commands."""


@data_package_group.command(name="migrate")
@click.argument("slug")
def data_package_migrate_cmd(slug: str) -> None:
    """Split a legacy data-package into derived dataset(s) + research-package."""
    from science_tool.datapackage_migrate import migrate_data_package
    project_root = _project_root()
    migrate_data_package(project_root, slug)
    click.echo(f"migrated data-package:{slug}")
```

- [ ] **Step 4: Verify + commit**

```bash
uv run --frozen pytest tests/test_data_package_migrate.py -v -k "emits_derived or research_package or superseded"
git add src/science_tool/datapackage_migrate.py src/science_tool/cli.py tests/test_data_package_migrate.py
git commit -m "feat(data-package cli): migrate splits legacy entity into dataset + research-package"
```

---

### Task 8.2: `data-package migrate` fails fast when workflow lacks `outputs:`

**Files:**
- Modify: `science-tool/tests/test_data_package_migrate.py`

- [ ] **Step 1: Add failing-fast test**

```python
def test_migrate_fails_when_workflow_has_no_outputs(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    # Strip outputs:
    wf = tmp_path / "doc" / "workflows" / "wf.md"
    wf.write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n---\n',
        encoding="utf-8",
    )
    res = CliRunner().invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code != 0
    assert "outputs" in res.output or "outputs" in res.stderr_bytes.decode() if res.stderr_bytes else "outputs" in res.output
```

- [ ] **Step 2: Verify (already implemented from `_read_workflow_outputs`)**

```bash
uv run --frozen pytest tests/test_data_package_migrate.py -v -k "no_outputs"
```

Expected: PASS — the existing implementation already raises ValueError; surface as Click error in the CLI:

In `data_package_migrate_cmd`:

```python
    try:
        migrate_data_package(project_root, slug)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(2) from exc
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_data_package_migrate.py -v
git add src/science_tool/cli.py tests/test_data_package_migrate.py
git commit -m "feat(data-package cli): migrate fails fast when workflow lacks outputs"
```

---

### Task 8.3: `data-package migrate` idempotency

**Files:**
- Modify: `science-tool/tests/test_data_package_migrate.py`

- [ ] **Step 1: Add idempotency test**

```python
def test_migrate_idempotent(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    runner = CliRunner()
    runner.invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    snap1 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rp_snap1 = (tmp_path / "research" / "packages" / "old" / "research-package.md").read_text()
    runner.invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    snap2 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rp_snap2 = (tmp_path / "research" / "packages" / "old" / "research-package.md").read_text()
    assert snap1 == snap2
    assert rp_snap1 == rp_snap2
```

- [ ] **Step 2: Verify**

```bash
uv run --frozen pytest tests/test_data_package_migrate.py -v -k "idempotent"
```

Expected: PASS if entity writers from Tasks 7.3 + 8.1 are content-identical. If failing, make `_research_package_yaml` deterministic (no datestamps that change, sort lists), and have `migrate_data_package` short-circuit when the data-package already has `status: superseded` (no-op + log).

- [ ] **Step 3: Add short-circuit**

In `migrate_data_package`, near the top:

```python
    if dp_fm.get("status") == "superseded":
        return  # already migrated; no-op
```

- [ ] **Step 4: Commit**

```bash
git add src/science_tool/datapackage_migrate.py tests/test_data_package_migrate.py
git commit -m "feat(data-package cli): migrate idempotent (no-op on superseded entries)"
```

---

### Task 8.4: `data-package list` (read-only)

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_data_package_migrate.py`

- [ ] **Step 1: Add failing test**

```python
def test_data_package_list_lists_unmigrated(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    res = CliRunner().invoke(science_cli, ["data-package", "list"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    assert res.exit_code == 0
    assert "data-package:old" in res.output
```

- [ ] **Step 2: Implement**

In `cli.py`:

```python
@data_package_group.command(name="list")
def data_package_list_cmd() -> None:
    """List legacy data-package entities (highlighting unmigrated ones)."""
    project_root = _project_root()
    dp_dir = project_root / "doc" / "data-packages"
    if not dp_dir.exists():
        click.echo("no doc/data-packages/ directory")
        return
    for md in sorted(dp_dir.rglob("*.md")):
        fm, _ = parse_frontmatter(md) or ({}, "")
        if fm.get("type") != "data-package":
            continue
        status = fm.get("status", "?")
        marker = " (UNMIGRATED)" if status != "superseded" else ""
        click.echo(f"{fm.get('id', md.stem)}\t{status}{marker}")
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_data_package_migrate.py -v -k "list_lists"
git add src/science_tool/cli.py tests/test_data_package_migrate.py
git commit -m "feat(data-package cli): list subcommand"
```

---

### Task 8.5: Strict graph-build mode — fail on unmigrated `data-package`

**Files:**
- Modify: `science-tool/src/science_tool/graph/materialize.py` (or wherever the graph build entry lives)
- Test: `science-tool/tests/test_graph_build_strict.py`

- [ ] **Step 1: Locate graph-build entry**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
grep -rn "def.*build\|create-graph" src/science_tool/graph/ | head
```

Identify the function that aggregates entities into the graph (`<build_fn>`).

- [ ] **Step 2: Write failing test**

Create `science-tool/tests/test_graph_build_strict.py`:

```python
from pathlib import Path

import pytest

from science_tool.graph.materialize import build_graph  # adjust to actual entry


def test_strict_build_fails_on_unmigrated_data_package(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "u.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:u"\ntype: "data-package"\ntitle: "U"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError) as exc_info:
        build_graph(tmp_path, strict=True)
    assert "data-package:u" in str(exc_info.value)
    assert "data-package migrate" in str(exc_info.value)


def test_strict_build_passes_on_superseded(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "s.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:s"\ntype: "data-package"\ntitle: "S"\nstatus: "superseded"\nsuperseded_by: "research-package:s"\n---\n',
        encoding="utf-8",
    )
    build_graph(tmp_path, strict=True)  # no exception
```

- [ ] **Step 3: Run failing test**

```bash
uv run --frozen pytest tests/test_graph_build_strict.py -v
```

Expected: FAIL — `strict` parameter not recognized OR no error raised.

- [ ] **Step 4: Implement**

In the build function:

```python
def build_graph(project_root: Path, *, strict: bool = True) -> ...:
    if strict:
        from science_model.frontmatter import parse_frontmatter
        unmigrated: list[str] = []
        dp_dir = project_root / "doc" / "data-packages"
        if dp_dir.exists():
            for md in dp_dir.rglob("*.md"):
                fm, _ = parse_frontmatter(md) or ({}, "")
                if fm.get("type") == "data-package" and fm.get("status") != "superseded":
                    unmigrated.append(str(fm.get("id", md.stem)))
        if unmigrated:
            slugs = ", ".join(unmigrated)
            raise RuntimeError(
                f"unmigrated data-package entities: {slugs}. "
                f"Run `science-tool data-package migrate <slug>` to split each into "
                f"derived dataset(s) + research-package."
            )
    # ... existing build logic ...
```

- [ ] **Step 5: Verify + commit**

```bash
uv run --frozen pytest tests/test_graph_build_strict.py -v
git add src/science_tool/graph/materialize.py tests/test_graph_build_strict.py
git commit -m "feat(graph): strict mode fails on unmigrated data-package entities"
```

---

## Phase 9: Command-doc updates

These tasks edit markdown files under `commands/` consumed by the `/science:*` slash commands. There are no unit tests for prose; the integration tests in Phase 10 cover end-to-end behavior.

### Task 9.1: `/science:plan-pipeline` — Step 2b + Step 4.5

**Files:**
- Modify: `commands/plan-pipeline.md`

- [ ] **Step 1: Read existing plan-pipeline.md**

```bash
cat commands/plan-pipeline.md | head -120
```

Locate the Workflow section. Identify the existing Steps 2 (computational requirements), 3 (computational nodes), 4 (write plan), 5 (inquiry-status update).

- [ ] **Step 2: Insert Step 2b after Step 2**

After the existing Step 2 closing (look for the header for Step 3), insert:

```markdown
### Step 2b: Data-access gate (both modes)

For each input data source identified in Step 2:

1. Resolve to a `dataset:<slug>` entity. If no entity exists:
   - For external sources: invoke `/science:find-datasets`. Do not proceed
     with a URL alone.
   - For derived sources: HALT with "no dataset entity found for `dataset:<slug>`;
     ensure the producing workflow has an `outputs:` block and run
     `science-tool dataset register-run <run-slug>`."
2. Check the gate per origin:
   - `origin: external`:
     - PASS if `access.verified: true`.
     - PASS if `access.verified: false` AND `access.exception.mode != ""`.
     - HALT otherwise with Branch A/B options:
       - **Branch A** — verifiable under current credentials → run verification
         (manual or future `science-tool dataset verify`), then re-run this step.
       - **Branch B** — requires credentials the project does not hold.
         Three sub-options:
         (a) **scope-reduce**: defer to a follow-up task; populate
             `access.exception` with `mode: "scope-reduced"`, `decision_date`,
             `followup_task`.
         (b) **expand**: add credential acquisition to the current task; populate
             `access.exception` with `mode: "expanded-to-acquire"`, `decision_date`.
         (c) **substitute**: pick an alternative dataset; populate
             `access.exception` with `mode: "substituted"`,
             `superseded_by_dataset: "dataset:<alternative>"`.
       After writing the structured exception + a prose log entry, re-run the gate.
   - `origin: derived`:
     - Check `derivation.workflow_run` resolves to a `workflow-run` entity. HALT if not.
     - Check that the workflow-run's `produces:` includes this dataset's ID. HALT if asymmetric.
     - Recursively check each ID in `derivation.inputs` passes the gate. HALT with the
       broken-link path if any input transitively fails. Cycle detection: maintain a
       visited-set; HALT on revisit.
3. Do NOT mutate `consumed_by` here. Backlink write is Step 4.5.
```

- [ ] **Step 3: Insert Step 4.5 after Step 4**

After the existing Step 4 (write plan) closing, insert:

```markdown
### Step 4.5: Register plan with consumed datasets (both modes)

The plan file now exists at a known path. Compute `plan:<plan-file-stem>` from the
filename (strip directory and `.md` extension).

For each dataset entity referenced in Step 2b, append `plan:<plan-file-stem>` to
`consumed_by`, deduplicated against existing entries. Also append any secondary
backlinks the planner has in scope (`task:<id>` if a task is being tracked;
`workflow:<slug>` if a new workflow is being registered). Do not rewrite existing
entries.

Append a short log entry to each dataset entity's verification log:

> "<YYYY-MM-DD> (<agent>): consumed by plan:<plan-file-stem>"
```

- [ ] **Step 4: Commit**

```bash
git add commands/plan-pipeline.md
git commit -m "docs(commands): plan-pipeline Steps 2b + 4.5 (data gate + backlink write)"
```

---

### Task 9.2: `/science:review-pipeline` — Dim 3 rewrite

**Files:**
- Modify: `commands/review-pipeline.md`

- [ ] **Step 1: Read existing**

```bash
sed -n '/Dimension 3/,/Dimension 4/p' commands/review-pipeline.md
```

- [ ] **Step 2: Replace Dim 3**

Replace the existing Dimension 3 section with:

```markdown
#### Dimension 3: Data Availability

For each input data source (every `BoundaryIn` node or data-acquisition step
in the plan):

- Does it resolve to a `dataset:<slug>` entity?
- Per origin (verification gate):
  - `external`: `access.verified: true` OR `access.exception.mode != ""`.
    `access.source_url` populated when verified.
    `access.last_reviewed` within the last 12 months.
  - `derived`: `derivation.workflow_run` exists; symmetric `produces:` edge present;
    `derivation.inputs` transitively pass.
- Runtime stageability (separate gate, runs in addition to verification):
  - At least one of `entity.datapackage` or `entity.local_path` is populated AND
    the referenced runtime file exists on disk.
- `consumed_by` includes `plan:<this-plan-file-stem>`.
- All eleven state invariants hold (see the spec at
  `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md`).

**Scoring:**

- **PASS** — all sources resolve; verification gate satisfied per origin; runtime
  stageability satisfied; backlink present; freshness OK; invariants hold.
- **WARN** — stale `last_reviewed` (> 12 months); missing canonical `plan:<stem>`
  backlink; cached-field drift between entity and runtime
  (`ontology_terms`/`license`/`update_cadence` only); lineage drift.
- **FAIL** — any of:
  - A source does not resolve to a dataset entity.
  - External `access.verified: false` with `access.exception.mode: ""`.
  - External `access.verified: true` but `verification_method: ""` or no
    `last_reviewed`.
  - Derived missing `workflow_run` entity, asymmetric `produces:` edge, or broken
    transitive input chain.
  - Runtime stageability fails: neither `datapackage` nor `local_path` populated,
    OR the referenced runtime file does not exist on disk.
  - A plan references an umbrella entity (non-empty `siblings:`).
  - Origin/block-exclusion violation (#7 or #8).
  - research-package symmetry violation (#11).
```

- [ ] **Step 3: Commit**

```bash
git add commands/review-pipeline.md
git commit -m "docs(commands): review-pipeline Dim 3 rewrite (verification + stageability)"
```

---

### Task 9.3: `/science:find-datasets` — emission rules

**Files:**
- Modify: `commands/find-datasets.md`

- [ ] **Step 1: Read existing**

```bash
cat commands/find-datasets.md
```

- [ ] **Step 2: Add emission-rules section**

After the existing Workflow section, add (or extend):

```markdown
### Emission rules (rev 2.1)

When emitting `doc/datasets/<slug>.md`:

- One entity per **distinguishable artefact** at a distinct access level. A paper
  with one public supplement and one controlled EGA deposit produces TWO entities,
  optionally plus a third umbrella entity linking them via `parent_dataset` /
  `siblings`.
- Always set `origin: "external"`.
- Default `access.verified: false`, `access.last_reviewed: ""`, `consumed_by: []`.
- Populate `access.level`, `access.source_url`, and `access.credentials_required`
  from discovery evidence. When uncertain, use the most restrictive known level
  — the verification step corrects it.
- The `accessions:` field carries external accession IDs (renamed from `datasets:`;
  legacy entries continue to read).
- Do NOT emit `origin: derived` entities — those are produced by `science-tool
  dataset register-run` after a workflow run.
```

- [ ] **Step 3: Commit**

```bash
git add commands/find-datasets.md
git commit -m "docs(commands): find-datasets emission rules (rev 2.1)"
```

---

## Phase 10: Integration tests

### Task 10.1: End-to-end gate test (mixed origins)

**Files:**
- Create: `science-tool/tests/test_plan_pipeline_data_gate.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: plan-pipeline Step 2b with mixed-origin inputs."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed_mixed_inputs(root: Path) -> None:
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    # Verified external.
    (root / "doc" / "datasets" / "ext_ok.md").write_text(
        '---\nid: "dataset:ext_ok"\ntype: "dataset"\ntitle: "OK"\norigin: "external"\n'
        'datapackage: "data/ext_ok/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        '---\n', encoding="utf-8",
    )
    # Unverified external (gate must HALT).
    (root / "doc" / "datasets" / "ext_bad.md").write_text(
        '---\nid: "dataset:ext_bad"\ntype: "dataset"\ntitle: "BAD"\norigin: "external"\n'
        'access: {level: "controlled", verified: false}\n---\n', encoding="utf-8",
    )
    # Derived OK (workflow-run + symmetric edge + transitive inputs all clean).
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "WF r1"\n'
        'workflow: "workflow:wf"\nproduces: ["dataset:der_ok"]\ninputs: ["dataset:ext_ok"]\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "datasets" / "der_ok.md").write_text(
        '---\nid: "dataset:der_ok"\ntype: "dataset"\ntitle: "DerOK"\norigin: "derived"\n'
        'datapackage: "results/wf/r1/out/datapackage.yaml"\n'
        'derivation:\n'
        '  workflow: "workflow:wf"\n'
        '  workflow_run: "workflow-run:wf-r1"\n'
        '  git_commit: "abc"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        '  inputs: ["dataset:ext_ok"]\n---\n',
        encoding="utf-8",
    )


def test_step2b_passes_for_verified_inputs(tmp_path: Path) -> None:
    """Ext-OK + Der-OK with clean upstream both PASS the gate."""
    _seed_mixed_inputs(tmp_path)
    from science_tool.plan_gate import check_inputs  # see Step 2 if not implemented
    pass_, halts = check_inputs(tmp_path, ["dataset:ext_ok", "dataset:der_ok"])
    assert pass_ is True
    assert halts == []


def test_step2b_halts_on_unverified_external(tmp_path: Path) -> None:
    _seed_mixed_inputs(tmp_path)
    from science_tool.plan_gate import check_inputs
    pass_, halts = check_inputs(tmp_path, ["dataset:ext_bad"])
    assert pass_ is False
    assert any("ext_bad" in h for h in halts)
```

- [ ] **Step 2: Implement `science_tool.plan_gate`**

If not implemented yet (and it isn't — Phase 9 only updates docs), create `science-tool/src/science_tool/plan_gate.py`:

```python
"""Programmatic gate check used by integration tests and (in future) by `/science:plan-pipeline`."""
from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import frontmatter_to_entity, parse_frontmatter


def _load_dataset(project_root: Path, ds_id: str):
    slug = ds_id.removeprefix("dataset:")
    md = project_root / "doc" / "datasets" / f"{slug}.md"
    if not md.exists():
        return None
    fm, _ = parse_frontmatter(md) or ({}, "")
    return frontmatter_to_entity(fm, project=project_root.name, file_path=str(md))


def check_inputs(project_root: Path, dataset_ids: list[str]) -> tuple[bool, list[str]]:
    """Run Step 2b gate logic against `dataset_ids`. Returns (pass, halt_messages)."""
    halts: list[str] = []
    for ds_id in dataset_ids:
        e = _load_dataset(project_root, ds_id)
        if e is None:
            halts.append(f"{ds_id}: no dataset entity found")
            continue
        if e.origin == "external":
            if e.access is None:
                halts.append(f"{ds_id}: external entity missing access block")
                continue
            if not (e.access.verified or e.access.exception.mode != ""):
                halts.append(f"{ds_id}: external access.verified=false and no exception")
                continue
        elif e.origin == "derived":
            if e.derivation is None:
                halts.append(f"{ds_id}: derived entity missing derivation block")
                continue
            run_slug = e.derivation.workflow_run.removeprefix("workflow-run:")
            run_path = project_root / "doc" / "workflow-runs" / f"{run_slug}.md"
            if not run_path.exists():
                halts.append(f"{ds_id}: derivation.workflow_run {e.derivation.workflow_run} not found")
                continue
            run_fm, _ = parse_frontmatter(run_path) or ({}, "")
            if e.id not in (run_fm.get("produces") or []):
                halts.append(f"{ds_id}: workflow-run does not list this dataset in produces:")
                continue
            # Transitive: recurse into inputs.
            for upstream in e.derivation.inputs:
                ok, sub_halts = check_inputs(project_root, [upstream])
                if not ok:
                    halts.append(f"{ds_id} -> {sub_halts[0]}")
                    break
    return (not halts, halts)
```

- [ ] **Step 3: Verify + commit**

```bash
uv run --frozen pytest tests/test_plan_pipeline_data_gate.py -v
git add src/science_tool/plan_gate.py tests/test_plan_pipeline_data_gate.py
git commit -m "feat(plan): programmatic Step 2b gate check + e2e tests"
```

---

### Task 10.2: End-to-end registration test (toy workflow)

**Files:**
- Create: `science-tool/tests/test_workflow_registration_e2e.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: workflow run -> register-run -> downstream plan-gate accepts result."""
from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_full_pipeline(root: Path) -> None:
    # Workflow with outputs:
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "toy.md").write_text(
        '---\nid: "workflow:toy"\ntype: "workflow"\ntitle: "Toy"\n'
        'outputs:\n'
        '  - slug: "result"\n'
        '    title: "Result"\n'
        '    resource_names: ["result"]\n'
        '    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    # Upstream verified external dataset (will become an input).
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "src.md").write_text(
        '---\nid: "dataset:src"\ntype: "dataset"\ntitle: "Src"\norigin: "external"\n'
        'datapackage: "data/src/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://s"}\n'
        '---\n', encoding="utf-8",
    )
    # Workflow-run with src as input.
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "toy-r1.md").write_text(
        '---\nid: "workflow-run:toy-r1"\ntype: "workflow-run"\ntitle: "Toy r1"\n'
        'workflow: "workflow:toy"\nproduces: []\ninputs: ["dataset:src"]\n'
        'git_commit: "abc"\nlast_run: "2026-04-19T12:00:00Z"\n---\n', encoding="utf-8",
    )
    # Run-aggregate datapackage.
    (root / "results" / "toy" / "r1").mkdir(parents=True)
    (root / "results" / "toy" / "r1" / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-runtime-1.0"],
        "name": "toy-r1",
        "resources": [{"name": "result", "path": "result.csv", "format": "csv"}],
    }), encoding="utf-8")


def test_register_run_then_gate_accepts_downstream(tmp_path: Path) -> None:
    _seed_full_pipeline(tmp_path)
    runner = CliRunner()
    res = runner.invoke(science_cli, ["dataset", "register-run", "workflow-run:toy-r1"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False)
    assert res.exit_code == 0, res.output
    # Now the derived dataset exists; gate accepts it.
    from science_tool.plan_gate import check_inputs
    pass_, halts = check_inputs(tmp_path, ["dataset:toy-toy-r1-result"])
    assert pass_ is True, halts
    # Symmetric edge: src.consumed_by includes workflow-run:toy-r1.
    body = (tmp_path / "doc" / "datasets" / "src.md").read_text()
    assert "workflow-run:toy-r1" in body
```

- [ ] **Step 2: Verify + commit**

```bash
uv run --frozen pytest tests/test_workflow_registration_e2e.py -v
git add tests/test_workflow_registration_e2e.py
git commit -m "test: end-to-end workflow registration -> gate acceptance"
```

---

### Task 10.3: End-to-end migration test (legacy data-package round-trip)

**Files:**
- Create: `science-tool/tests/test_data_package_migrate_e2e.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: legacy data-package -> migrate -> graph build (strict) succeeds."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    """Carve out a legacy data-package + matching workflow + run."""
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "wf.md").write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n'
        'outputs:\n'
        '  - slug: "result"\n'
        '    title: "Result"\n'
        '    resource_names: ["result"]\n'
        '    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "r1"\n'
        'workflow: "workflow:wf"\nproduces: []\ninputs: []\n'
        'git_commit: "a"\nlast_run: "2026-04-19T00:00:00Z"\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "data-packages").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "data-packages" / "old.md").write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Old"\nstatus: "active"\n'
        'workflow_run: "workflow-run:wf-r1"\n'
        'manifest: "research/packages/old/datapackage.json"\n'
        'cells: "research/packages/old/cells.json"\n---\n', encoding="utf-8",
    )
    rp = root / "research" / "packages" / "old"
    rp.mkdir(parents=True, exist_ok=True)
    (rp / "datapackage.json").write_text(json.dumps({
        "name": "old", "title": "Old", "profile": "science-research-package", "version": "0.1",
        "resources": [{"name": "result", "path": "result.csv", "format": "csv"}],
        "research": {
            "cells": "cells.json", "figures": [], "vegalite_specs": [], "code_excerpts": [],
            "provenance": {"workflow": "workflow:wf", "config": "c", "last_run": "2026-04-19", "git_commit": "a", "repository": "", "inputs": [], "scripts": []},
        },
    }), encoding="utf-8")


def test_strict_build_fails_then_migrate_unblocks(tmp_path: Path) -> None:
    _seed(tmp_path)
    runner = CliRunner()
    # Strict graph build fails first.
    from science_tool.graph.materialize import build_graph
    import pytest
    with pytest.raises(RuntimeError, match="data-package:old"):
        build_graph(tmp_path, strict=True)
    # Migrate.
    res = runner.invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False)
    assert res.exit_code == 0, res.output
    # Now strict build passes.
    build_graph(tmp_path, strict=True)
    # Verify research-package exists with correct symmetric backlink.
    rp_path = tmp_path / "research" / "packages" / "old" / "research-package.md"
    assert rp_path.exists()
    rp_body = rp_path.read_text()
    assert "dataset:wf-wf-r1-result" in rp_body  # in displays
    ds_body = (tmp_path / "doc" / "datasets" / "wf-wf-r1-result.md").read_text()
    assert "research-package:old" in ds_body  # symmetric
```

- [ ] **Step 2: Verify + commit**

```bash
uv run --frozen pytest tests/test_data_package_migrate_e2e.py -v
git add tests/test_data_package_migrate_e2e.py
git commit -m "test: end-to-end data-package migrate -> strict graph build unblocked"
```

---

## Phase 11: Final cleanup

### Task 11.1: Lint, type-check, and full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Lint**

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen ruff check .
uv run --frozen ruff format --check .

cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Expected: no errors.

- [ ] **Step 2: Type-check**

```bash
cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pyright
cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pyright
```

Expected: no errors.

- [ ] **Step 3: Full test sweep**

```bash
cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest -q
cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit any final fixups**

```bash
git status
# Stage and commit any auto-format adjustments.
```

---

### Task 11.2: Update `skills/research/provenance.md` cross-references

**Files:**
- Modify: `skills/research/provenance.md`

- [ ] **Step 1: Update entity-type references**

In `skills/research/provenance.md`, find references to `data-package` and update where it now means `research-package`:

- "produced by a `workflow-run`" sections — clarify that the **derived dataset entities** are the `produced_by` targets; the `research-package` `displays` them.
- The "Knowledge Graph Integration" section listing `data-package` — add a note that v2 (rev 2.1 of the dataset entity lifecycle spec) renames this to `research-package` and splits the data half into derived `dataset` entities.

Add a one-line pointer at the top: "See `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` for the v2 unified dataset model."

- [ ] **Step 2: Commit**

```bash
git add skills/research/provenance.md
git commit -m "docs(skill): cross-reference rev 2.1 dataset-entity-lifecycle spec"
```

---

### Task 11.3: Spec cross-reference verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm spec references resolve**

```bash
grep -n "docs/specs/2026-04-19-multi-backend-entity-resolver-design.md" docs/specs/2026-04-19-dataset-entity-lifecycle-design.md
```

If Spec Y has not been written yet, the spec contains a forward-reference. This is intentional. No action needed; document in your handoff that Spec Y should be written next.

- [ ] **Step 2: Notify completion**

Use the user-notification helper if running interactively:

```python
# If using the notify_user MCP tool:
# ohai("Implementation complete. All 12 health anomalies, 3 CLI commands, 3 command-doc updates shipped.", title="dataset-entity-lifecycle ✓")
```

---

## Self-review (run mentally before declaring done)

**Spec coverage check:** Map each Resolved Decision in the spec to a task above:

- Unification: Phases 1-4
- Schema family: Phase 1
- Entity vs runtime surface: Phases 1, 7
- data-package -> research-package rename: Phase 4 (template), Phase 8 (migrator), Task 11.2 (skill docs)
- research-package entity location: Phase 4, Phase 5
- Per-entity-type discovery rule: Phase 5
- Granularity for derived data: Phase 4 (workflow.outputs), Phase 7 (register-run)
- Workflow integration shape: Phase 7
- Strict migration with shipped migrator: Phase 8
- origin: external default for back-compat: Phase 3
- No symlinks: register-run writes files (Phase 7); no symlink machinery anywhere
- Forward-compatibility with Spec Y: design holds; no schema lock-in
- Single source of truth for resources: Phase 1 schema rejects entity resources[]; Phase 6.10 reconcile/health drift on cached fields only
- Per-output runtime datapackages: Phase 7.2
- Plan gate vs runtime stageability: Phase 6.6 (health), Phase 9.2 (review-pipeline FAIL)
- outputs[].resource_names: Phase 4.3, Phase 7.2
- Symmetric research-package backlinks: Phase 6.7 (health), Phase 8.1 (migrator writes them)

**Placeholder scan:** No "TBD"/"TODO"/"implement later" — every step contains either real code, a real command, or an explicit instruction to "follow the existing pattern at <path>".

**Type/name consistency:** `check_dataset_anomalies`, `discover_entities`, `migrate_data_package`, `write_per_output_datapackages`, `write_derived_dataset_entities`, `write_symmetric_edges`, `check_inputs`, `build_graph(strict=)`, `frontmatter_to_entity` — all referenced consistently across tasks.

---

## Execution Handoff

**Plan complete and saved to `docs/specs/plans/2026-04-19-dataset-entity-lifecycle.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?


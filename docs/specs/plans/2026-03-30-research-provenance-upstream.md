# Research Provenance Upstream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add research provenance support to the science framework — entity types, data package schema, CLI commands, and skills — so any science project can produce standardized, reproducible research packages.

**Architecture:** New entity kinds (`data-package`, `artifact`) and relations (`derived_from`, `produced_by`) added to science-model's core profile. A `packages` module in science-model provides Pydantic schemas and validation. A `research-package` command group in science-tool provides `init`/`validate`/`build` CLI commands. Three skills document the patterns.

**Tech Stack:** Python 3.11+, Pydantic v2, Click, rdflib, pytest

**Spec:** `docs/specs/2026-03-30-research-provenance-upstream-design.md`

---

## File Structure

### science-model — New files

```
src/science_model/packages/
  __init__.py                    # Re-exports schemas and validation
  schema.py                      # Pydantic models for package descriptor
  cells.py                       # Pydantic models for cell definitions
  validation.py                  # Package validation logic

tests/
  test_packages.py               # Schema validation and package validation tests
```

### science-model — Modified files

```
src/science_model/entities.py    # Add DATA_PACKAGE and ARTIFACT to EntityType
src/science_model/profiles/core.py  # Add 2 entity kinds + 2 relation kinds
src/science_model/__init__.py    # Re-export new types
```

### science-tool — New files

```
src/science_tool/research_package/
  __init__.py                    # Re-exports
  init_package.py                # Package scaffolding
  build_package.py               # Package assembly from workflow results
  cli.py                         # Click command group

tests/
  test_research_package_cli.py   # CLI integration tests
```

### science-tool — Modified files

```
src/science_tool/cli.py          # Register research-package command group
src/science_tool/graph/store.py  # Add PROJECT_ENTITY_PREFIXES + add_data_package + add_artifact
```

### skills — New files

```
skills/research/provenance.md    # Layer 1: reproducible workflow skill
skills/research/lab-notebook.md  # Layer 2: web app rendering skill
```

### skills — Modified files

```
skills/pipelines/snakemake.md    # Add research package integration section
```

---

## Task 1: Core Profile — Entity Types and Relations

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-model/src/science_model/profiles/core.py`
- Test: `science-model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write failing test for new entity kinds**

Add to `science-model/tests/test_profile_manifests.py`:

```python
def test_core_profile_has_data_package_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "data-package" in kind_names


def test_core_profile_has_artifact_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "artifact" in kind_names


def test_core_profile_has_derived_from_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "derived_from" in rel_names


def test_core_profile_has_produced_by_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "produced_by" in rel_names


def test_derived_from_connects_artifact_to_data_package() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "derived_from")
    assert "artifact" in rel.source_kinds
    assert "data-package" in rel.target_kinds


def test_produced_by_connects_data_package_to_workflow_run() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "produced_by")
    assert "data-package" in rel.source_kinds
    assert "workflow-run" in rel.target_kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_profile_manifests.py -v`
Expected: 6 new tests FAIL

- [ ] **Step 3: Add EntityType enum values**

In `science-model/src/science_model/entities.py`, add after `WORKFLOW_STEP = "workflow-step"`:

```python
    DATA_PACKAGE = "data-package"
    ARTIFACT = "artifact"
```

- [ ] **Step 4: Add entity kinds to core profile**

In `science-model/src/science_model/profiles/core.py`, add to `entity_kinds` list (after `workflow-step`):

```python
        EntityKind(
            name="data-package",
            canonical_prefix="data-package",
            layer="layer/core",
            description="Frictionless research package containing analysis results, prose, and provenance metadata.",
        ),
        EntityKind(
            name="artifact",
            canonical_prefix="artifact",
            layer="layer/core",
            description="Downstream consumer of research results (web page, figure, report section).",
        ),
```

- [ ] **Step 5: Add relation kinds to core profile**

In the same file, add to `relation_kinds` list (after `feeds_into`):

```python
        RelationKind(
            name="derived_from",
            predicate="sci:derivedFrom",
            source_kinds=["artifact"],
            target_kinds=["data-package"],
            layer="layer/core",
            description="An artifact is derived from a data package.",
        ),
        RelationKind(
            name="produced_by",
            predicate="sci:producedBy",
            source_kinds=["data-package"],
            target_kinds=["workflow-run"],
            layer="layer/core",
            description="A data package was produced by a specific workflow run.",
        ),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_profile_manifests.py -v`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite**

Run: `cd ~/d/science/science-model && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
cd ~/d/science/science-model
git add src/science_model/entities.py src/science_model/profiles/core.py tests/test_profile_manifests.py
git commit -m "feat(model): add data-package and artifact entity kinds to core profile"
```

---

## Task 2: Package Schema — Pydantic Models

**Files:**
- Create: `science-model/src/science_model/packages/__init__.py`
- Create: `science-model/src/science_model/packages/schema.py`
- Test: `science-model/tests/test_packages.py`

- [ ] **Step 1: Write failing tests for package descriptor schema**

Create `science-model/tests/test_packages.py`:

```python
"""Tests for research package schema and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.packages.schema import (
    CodeExcerpt,
    FigureRef,
    Provenance,
    ProvenanceInput,
    ResearchExtension,
    ResearchPackageDescriptor,
    ResourceSchema,
    VegaLiteSpec,
)


def _valid_provenance() -> dict:
    return {
        "workflow": "workflows/theme-validation/Snakefile",
        "config": "workflows/theme-validation/config.yaml",
        "last_run": "2026-03-30T10:00:00Z",
        "git_commit": "abc123def456",
        "repository": "https://github.com/user/repo",
        "inputs": [{"path": "src/foo.ts", "sha256": "aabb"}],
        "scripts": ["scripts/foo.ts"],
    }


def _valid_package() -> dict:
    return {
        "name": "theme-instability-bifurcation",
        "title": "Instability & Bifurcation",
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": [{"name": "scores", "path": "data/scores.csv"}],
        "research": {
            "cells": "cells.json",
            "figures": [],
            "vegalite_specs": [],
            "code_excerpts": [],
            "provenance": _valid_provenance(),
        },
    }


class TestResearchPackageDescriptor:
    def test_valid_package(self) -> None:
        pkg = ResearchPackageDescriptor(**_valid_package())
        assert pkg.name == "theme-instability-bifurcation"
        assert pkg.profile == "science-research-package"

    def test_rejects_wrong_profile(self) -> None:
        data = _valid_package()
        data["profile"] = "wrong-profile"
        with pytest.raises(ValidationError):
            ResearchPackageDescriptor(**data)

    def test_rejects_missing_provenance(self) -> None:
        data = _valid_package()
        del data["research"]["provenance"]
        with pytest.raises(ValidationError):
            ResearchPackageDescriptor(**data)

    def test_allows_empty_collections(self) -> None:
        pkg = ResearchPackageDescriptor(**_valid_package())
        assert pkg.research.figures == []
        assert pkg.research.vegalite_specs == []
        assert pkg.research.code_excerpts == []

    def test_target_route_optional(self) -> None:
        data = _valid_package()
        pkg = ResearchPackageDescriptor(**data)
        assert pkg.research.target_route is None

        data["research"]["target_route"] = "/guide/theme/chaos"
        pkg2 = ResearchPackageDescriptor(**data)
        assert pkg2.research.target_route == "/guide/theme/chaos"

    def test_resource_schema_field_alias(self) -> None:
        r = ResourceSchema(name="test", path="data/test.csv", **{"schema": {"fields": []}})
        assert r.schema_ == {"fields": []}

    def test_code_excerpt_lines_tuple(self) -> None:
        exc = CodeExcerpt(
            name="test",
            path="excerpts/test.ts",
            source="scripts/test.ts",
            lines=(10, 50),
            github_permalink="",
        )
        assert exc.lines == (10, 50)

    def test_github_permalink_defaults_empty(self) -> None:
        exc = CodeExcerpt(
            name="test",
            path="excerpts/test.ts",
            source="scripts/test.ts",
            lines=(1, 10),
        )
        assert exc.github_permalink == ""

    def test_vegalite_spec(self) -> None:
        spec = VegaLiteSpec(name="chart", path="figures/chart.vl.json")
        assert spec.caption is None

    def test_provenance_input(self) -> None:
        inp = ProvenanceInput(path="src/foo.ts", sha256="abc123")
        assert inp.sha256 == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py -v`
Expected: FAIL — cannot import from `science_model.packages.schema`

- [ ] **Step 3: Create the packages module**

Create `science-model/src/science_model/packages/__init__.py` (empty for now):

```python
"""Research package schema, cell definitions, and validation."""
```

Create `science-model/src/science_model/packages/schema.py`:

```python
"""Pydantic models for Frictionless research package descriptors."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResourceSchema(BaseModel):
    """A tabular data resource within the package."""

    name: str
    path: str
    schema_: dict[str, Any] | None = Field(None, alias="schema")

    model_config = {"populate_by_name": True}


class FigureRef(BaseModel):
    """A static figure (image) included in the package."""

    name: str
    path: str
    caption: str


class CodeExcerpt(BaseModel):
    """An extracted code snippet with source provenance."""

    name: str
    path: str
    source: str
    lines: tuple[int, int]
    github_permalink: str = ""


class VegaLiteSpec(BaseModel):
    """A Vega-Lite visualization specification."""

    name: str
    path: str
    caption: str | None = None


class ProvenanceInput(BaseModel):
    """An input file tracked for freshness via SHA-256."""

    path: str
    sha256: str


class Provenance(BaseModel):
    """Execution provenance for a research package."""

    workflow: str
    config: str
    last_run: str
    git_commit: str
    repository: str
    inputs: list[ProvenanceInput]
    scripts: list[str]


class ResearchExtension(BaseModel):
    """Custom extension block within the Frictionless descriptor."""

    target_route: str | None = None
    cells: str
    figures: list[FigureRef] = Field(default_factory=list)
    vegalite_specs: list[VegaLiteSpec] = Field(default_factory=list)
    code_excerpts: list[CodeExcerpt] = Field(default_factory=list)
    provenance: Provenance


class ResearchPackageDescriptor(BaseModel):
    """A Frictionless data package with science research extensions."""

    name: str
    title: str
    profile: Literal["science-research-package"]
    version: str
    resources: list[ResourceSchema]
    research: ResearchExtension
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science-model
git add src/science_model/packages/ tests/test_packages.py
git commit -m "feat(model): add research package descriptor schema"
```

---

## Task 3: Cell Schema

**Files:**
- Create: `science-model/src/science_model/packages/cells.py`
- Modify: `science-model/tests/test_packages.py`

- [ ] **Step 1: Write failing tests for cell schema**

Append to `science-model/tests/test_packages.py`:

```python
from science_model.packages.cells import (
    Cell,
    CodeReferenceCell,
    DataTableCell,
    FigureCell,
    NarrativeCell,
    ProvenanceCell,
    VegaLiteCell,
    parse_cells,
)


class TestCellSchema:
    def test_narrative_cell(self) -> None:
        cell = NarrativeCell(type="narrative", content="prose/01-intro.md")
        assert cell.content == "prose/01-intro.md"

    def test_data_table_cell(self) -> None:
        cell = DataTableCell(type="data-table", resource="scores")
        assert cell.columns is None
        assert cell.caption is None

    def test_data_table_cell_with_columns(self) -> None:
        cell = DataTableCell(
            type="data-table", resource="scores", columns=["a", "b"], caption="My table"
        )
        assert cell.columns == ["a", "b"]

    def test_figure_cell(self) -> None:
        cell = FigureCell(type="figure", ref="confusion-matrix")
        assert cell.ref == "confusion-matrix"

    def test_vegalite_cell(self) -> None:
        cell = VegaLiteCell(type="vegalite", ref="chart", caption="My chart")
        assert cell.caption == "My chart"

    def test_code_reference_cell(self) -> None:
        cell = CodeReferenceCell(type="code-reference", excerpt="kappa")
        assert cell.description is None

    def test_provenance_cell(self) -> None:
        cell = ProvenanceCell(type="provenance")
        assert cell.type == "provenance"

    def test_parse_cells_from_list(self) -> None:
        raw = [
            {"type": "narrative", "content": "prose/01.md"},
            {"type": "data-table", "resource": "scores"},
            {"type": "provenance"},
        ]
        cells = parse_cells(raw)
        assert len(cells) == 3
        assert isinstance(cells[0], NarrativeCell)
        assert isinstance(cells[1], DataTableCell)
        assert isinstance(cells[2], ProvenanceCell)

    def test_parse_cells_rejects_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown cell type"):
            parse_cells([{"type": "unknown"}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py::TestCellSchema -v`
Expected: FAIL — cannot import from `science_model.packages.cells`

- [ ] **Step 3: Create cells.py**

```python
# science-model/src/science_model/packages/cells.py
"""Pydantic models for research package cell definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class NarrativeCell(BaseModel):
    """Markdown prose cell. Content is a file path within the package."""

    type: Literal["narrative"]
    content: str


class DataTableCell(BaseModel):
    """Sortable data table rendered from a CSV resource."""

    type: Literal["data-table"]
    resource: str
    columns: list[str] | None = None
    caption: str | None = None


class FigureCell(BaseModel):
    """Static image with caption."""

    type: Literal["figure"]
    ref: str


class VegaLiteCell(BaseModel):
    """Interactive Vega-Lite chart."""

    type: Literal["vegalite"]
    ref: str
    caption: str | None = None


class CodeReferenceCell(BaseModel):
    """Collapsible code excerpt with optional GitHub permalink."""

    type: Literal["code-reference"]
    excerpt: str
    description: str | None = None


class ProvenanceCell(BaseModel):
    """Auto-rendered provenance summary from package metadata."""

    type: Literal["provenance"]


Cell = NarrativeCell | DataTableCell | FigureCell | VegaLiteCell | CodeReferenceCell | ProvenanceCell

_CELL_TYPE_MAP: dict[str, type[BaseModel]] = {
    "narrative": NarrativeCell,
    "data-table": DataTableCell,
    "figure": FigureCell,
    "vegalite": VegaLiteCell,
    "code-reference": CodeReferenceCell,
    "provenance": ProvenanceCell,
}


def parse_cells(raw: list[dict]) -> list[Cell]:
    """Parse a list of raw cell dicts into typed Cell instances."""
    cells: list[Cell] = []
    for item in raw:
        cell_type = item.get("type")
        model_class = _CELL_TYPE_MAP.get(cell_type) if isinstance(cell_type, str) else None
        if model_class is None:
            raise ValueError(f"Unknown cell type: {cell_type}")
        cells.append(model_class(**item))  # type: ignore[arg-type]
    return cells
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science-model
git add src/science_model/packages/cells.py tests/test_packages.py
git commit -m "feat(model): add cell schema for research package narratives"
```

---

## Task 4: Package Validation

**Files:**
- Create: `science-model/src/science_model/packages/validation.py`
- Modify: `science-model/tests/test_packages.py`

- [ ] **Step 1: Write failing tests for validation**

Append to `science-model/tests/test_packages.py`:

```python
import json
from pathlib import Path

from science_model.packages.validation import ValidationResult, check_freshness, validate_package


class TestValidatePackage:
    def test_valid_package(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "data").mkdir()
        (pkg_dir / "prose").mkdir()

        (pkg_dir / "data" / "scores.csv").write_text("a,b\n1,2\n")
        (pkg_dir / "prose" / "01-intro.md").write_text("# Intro\n")

        descriptor = _valid_package()
        descriptor["research"]["cells"] = "cells.json"
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))

        cells = [
            {"type": "narrative", "content": "prose/01-intro.md"},
            {"type": "data-table", "resource": "scores"},
            {"type": "provenance"},
        ]
        (pkg_dir / "cells.json").write_text(json.dumps(cells))

        result = validate_package(pkg_dir)
        assert result.ok
        assert result.errors == []

    def test_missing_datapackage_json(self, tmp_path: Path) -> None:
        result = validate_package(tmp_path)
        assert not result.ok
        assert any("datapackage.json" in e for e in result.errors)

    def test_missing_resource_file(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()

        descriptor = _valid_package()
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))
        (pkg_dir / "cells.json").write_text("[]")

        result = validate_package(pkg_dir)
        assert not result.ok
        assert any("scores" in e for e in result.errors)

    def test_cell_references_unknown_resource(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "data").mkdir()
        (pkg_dir / "data" / "scores.csv").write_text("a\n1\n")

        descriptor = _valid_package()
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))

        cells = [{"type": "data-table", "resource": "nonexistent"}]
        (pkg_dir / "cells.json").write_text(json.dumps(cells))

        result = validate_package(pkg_dir)
        assert not result.ok
        assert any("nonexistent" in e for e in result.errors)

    def test_narrative_cell_missing_file(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "data").mkdir()
        (pkg_dir / "data" / "scores.csv").write_text("a\n1\n")

        descriptor = _valid_package()
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))

        cells = [{"type": "narrative", "content": "prose/missing.md"}]
        (pkg_dir / "cells.json").write_text(json.dumps(cells))

        result = validate_package(pkg_dir)
        assert not result.ok
        assert any("missing.md" in e for e in result.errors)

    def test_validation_result_to_dict(self) -> None:
        result = ValidationResult(
            package_dir="/tmp/pkg",
            errors=["error1"],
            warnings=["warn1"],
        )
        d = result.to_dict()
        assert d["ok"] is False
        assert d["errors"] == ["error1"]
        assert d["warnings"] == ["warn1"]


class TestCheckFreshness:
    def test_fresh_inputs(self, tmp_path: Path) -> None:
        import hashlib

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        project_root = tmp_path / "project"
        project_root.mkdir()

        input_file = project_root / "src" / "foo.ts"
        input_file.parent.mkdir(parents=True)
        input_file.write_text("content")
        sha = hashlib.sha256(b"content").hexdigest()

        descriptor = _valid_package()
        descriptor["research"]["provenance"]["inputs"] = [
            {"path": "src/foo.ts", "sha256": sha},
        ]
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))

        result = check_freshness(pkg_dir, project_root)
        assert result.warnings == []

    def test_stale_input(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        project_root = tmp_path / "project"
        project_root.mkdir()

        input_file = project_root / "src" / "foo.ts"
        input_file.parent.mkdir(parents=True)
        input_file.write_text("changed content")

        descriptor = _valid_package()
        descriptor["research"]["provenance"]["inputs"] = [
            {"path": "src/foo.ts", "sha256": "wrong_hash"},
        ]
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))

        result = check_freshness(pkg_dir, project_root)
        assert len(result.warnings) == 1
        assert "stale" in result.warnings[0].lower() or "changed" in result.warnings[0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py::TestValidatePackage -v`
Expected: FAIL — cannot import from `science_model.packages.validation`

- [ ] **Step 3: Create validation.py**

```python
# science-model/src/science_model/packages/validation.py
"""Validation for research package directories."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from science_model.packages.cells import _CELL_TYPE_MAP
from science_model.packages.schema import ResearchPackageDescriptor


@dataclass
class ValidationResult:
    """Structured validation output, serializable to JSON."""

    package_dir: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "package_dir": self.package_dir,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_package(package_dir: Path) -> ValidationResult:
    """Validate a research package directory.

    Checks:
    - datapackage.json exists and conforms to ResearchPackageDescriptor
    - cells.json exists and all cells conform to Cell types
    - All resource paths resolve to existing files
    - All figure paths resolve
    - All vegalite spec paths resolve
    - All code excerpt paths resolve
    - All narrative content paths resolve
    - All cell cross-references match declarations
    """
    result = ValidationResult(package_dir=str(package_dir))
    descriptor_path = package_dir / "datapackage.json"

    if not descriptor_path.is_file():
        result.errors.append(f"Missing datapackage.json in {package_dir}")
        return result

    try:
        raw = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result.errors.append(f"Cannot read datapackage.json: {exc}")
        return result

    try:
        pkg = ResearchPackageDescriptor(**raw)
    except Exception as exc:
        result.errors.append(f"Invalid datapackage.json: {exc}")
        return result

    # Validate resource file existence
    for resource in pkg.resources:
        if not (package_dir / resource.path).is_file():
            result.errors.append(f'Resource "{resource.name}" file missing: {resource.path}')

    # Validate figure file existence
    for fig in pkg.research.figures:
        if not (package_dir / fig.path).is_file():
            result.errors.append(f'Figure "{fig.name}" file missing: {fig.path}')

    # Validate vegalite spec file existence
    for spec in pkg.research.vegalite_specs:
        if not (package_dir / spec.path).is_file():
            result.errors.append(f'Vega-Lite spec "{spec.name}" file missing: {spec.path}')

    # Validate code excerpt file existence
    for exc in pkg.research.code_excerpts:
        if not (package_dir / exc.path).is_file():
            result.errors.append(f'Code excerpt "{exc.name}" file missing: {exc.path}')

    # Validate cells
    cells_path = package_dir / pkg.research.cells
    if not cells_path.is_file():
        result.errors.append(f"Missing cells file: {pkg.research.cells}")
        return result

    try:
        raw_cells = json.loads(cells_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc_inner:
        result.errors.append(f"Cannot read cells file: {exc_inner}")
        return result

    if not isinstance(raw_cells, list):
        result.errors.append("cells.json must be a JSON array")
        return result

    resource_names = {r.name for r in pkg.resources}
    figure_names = {f.name for f in pkg.research.figures}
    vegalite_names = {s.name for s in pkg.research.vegalite_specs}
    excerpt_names = {e.name for e in pkg.research.code_excerpts}

    for i, cell in enumerate(raw_cells):
        if not isinstance(cell, dict):
            result.errors.append(f"Cell {i}: not a dict")
            continue
        cell_type = cell.get("type")
        if cell_type not in _CELL_TYPE_MAP:
            result.errors.append(f"Cell {i}: unknown type '{cell_type}'")
            continue

        if cell_type == "narrative":
            content_path = cell.get("content", "")
            if not (package_dir / content_path).is_file():
                result.errors.append(f"Cell {i}: narrative content file missing: {content_path}")
        elif cell_type == "data-table":
            resource = cell.get("resource", "")
            if resource not in resource_names:
                result.errors.append(f"Cell {i}: references unknown resource '{resource}'")
        elif cell_type == "figure":
            ref = cell.get("ref", "")
            if ref not in figure_names:
                result.errors.append(f"Cell {i}: references unknown figure '{ref}'")
        elif cell_type == "vegalite":
            ref = cell.get("ref", "")
            if ref not in vegalite_names:
                result.errors.append(f"Cell {i}: references unknown vegalite spec '{ref}'")
        elif cell_type == "code-reference":
            excerpt = cell.get("excerpt", "")
            if excerpt not in excerpt_names:
                result.errors.append(f"Cell {i}: references unknown code excerpt '{excerpt}'")

    return result


def check_freshness(package_dir: Path, project_root: Path) -> ValidationResult:
    """Check provenance input freshness by comparing SHA-256 hashes."""
    result = ValidationResult(package_dir=str(package_dir))
    descriptor_path = package_dir / "datapackage.json"

    if not descriptor_path.is_file():
        result.errors.append(f"Missing datapackage.json in {package_dir}")
        return result

    try:
        raw = json.loads(descriptor_path.read_text(encoding="utf-8"))
        pkg = ResearchPackageDescriptor(**raw)
    except Exception as exc:
        result.errors.append(f"Cannot parse datapackage.json: {exc}")
        return result

    for inp in pkg.research.provenance.inputs:
        input_path = project_root / inp.path
        if not input_path.is_file():
            result.warnings.append(f"Input file not found (may have moved): {inp.path}")
            continue
        current_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if current_hash != inp.sha256:
            result.warnings.append(
                f'Input "{inp.path}" has changed since last workflow run (stale package)'
            )

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science-model && uv run pytest tests/test_packages.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science-model
git add src/science_model/packages/validation.py tests/test_packages.py
git commit -m "feat(model): add research package validation with freshness checking"
```

---

## Task 5: Package Module Re-exports

**Files:**
- Modify: `science-model/src/science_model/packages/__init__.py`
- Modify: `science-model/src/science_model/__init__.py`

- [ ] **Step 1: Add re-exports to packages/__init__.py**

```python
# science-model/src/science_model/packages/__init__.py
"""Research package schema, cell definitions, and validation."""

from science_model.packages.cells import (
    Cell,
    CodeReferenceCell,
    DataTableCell,
    FigureCell,
    NarrativeCell,
    ProvenanceCell,
    VegaLiteCell,
    parse_cells,
)
from science_model.packages.schema import (
    CodeExcerpt,
    FigureRef,
    Provenance,
    ProvenanceInput,
    ResearchExtension,
    ResearchPackageDescriptor,
    ResourceSchema,
    VegaLiteSpec,
)
from science_model.packages.validation import ValidationResult, check_freshness, validate_package

__all__ = [
    "Cell",
    "CodeExcerpt",
    "CodeReferenceCell",
    "DataTableCell",
    "FigureCell",
    "FigureRef",
    "NarrativeCell",
    "Provenance",
    "ProvenanceCell",
    "ProvenanceInput",
    "ResearchExtension",
    "ResearchPackageDescriptor",
    "ResourceSchema",
    "ValidationResult",
    "VegaLiteCell",
    "VegaLiteSpec",
    "check_freshness",
    "parse_cells",
    "validate_package",
]
```

- [ ] **Step 2: Add packages to science_model/__init__.py**

Read `science-model/src/science_model/__init__.py` and add the packages module to its exports. Add at the end of the existing imports:

```python
from science_model.packages import (
    ResearchPackageDescriptor,
    ValidationResult,
    validate_package,
    check_freshness,
    parse_cells,
)
```

- [ ] **Step 3: Verify imports work**

Run: `cd ~/d/science/science-model && uv run python -c "from science_model import ResearchPackageDescriptor, validate_package, parse_cells; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run full test suite**

Run: `cd ~/d/science/science-model && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science-model
git add src/science_model/packages/__init__.py src/science_model/__init__.py
git commit -m "feat(model): wire packages module into science-model exports"
```

---

## Task 6: Graph Store — Entity Prefixes and add_* Functions

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_cli.py` (or new test file)

- [ ] **Step 1: Add to PROJECT_ENTITY_PREFIXES**

In `science-tool/src/science_tool/graph/store.py`, add to the `PROJECT_ENTITY_PREFIXES` set (around line 143-154):

```python
    "data-package",
    "artifact",
```

- [ ] **Step 2: Add add_data_package function**

Add after the existing `add_*` functions (before the helper functions section):

```python
def add_data_package(
    graph_path: Path,
    package_id: str,
    title: str,
    *,
    produced_by: str | None = None,
) -> URIRef:
    """Add a data-package entity to the knowledge graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    uri = URIRef(PROJECT_NS[f"data-package/{_slug(package_id)}"])
    knowledge.add((uri, RDF.type, SCI_NS.DataPackage))
    knowledge.add((uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(package_id)))

    if produced_by:
        knowledge.add((uri, SCI_NS.producedBy, _resolve_term(produced_by)))

    _save_dataset(dataset, graph_path)
    return uri
```

- [ ] **Step 3: Add add_artifact function**

```python
def add_artifact(
    graph_path: Path,
    artifact_id: str,
    title: str,
    *,
    artifact_type: str,
    target: str | None = None,
    derived_from: str | None = None,
) -> URIRef:
    """Add an artifact entity to the knowledge graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    uri = URIRef(PROJECT_NS[f"artifact/{_slug(artifact_id)}"])
    knowledge.add((uri, RDF.type, SCI_NS.Artifact))
    knowledge.add((uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(artifact_id)))
    knowledge.add((uri, SCI_NS.artifactType, Literal(artifact_type)))

    if target:
        knowledge.add((uri, SCI_NS.target, Literal(target)))
    if derived_from:
        knowledge.add((uri, SCI_NS.derivedFrom, _resolve_term(derived_from)))

    _save_dataset(dataset, graph_path)
    return uri
```

- [ ] **Step 4: Run existing graph tests**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_graph_cli.py -v`
Expected: All existing tests PASS (no regressions)

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/graph/store.py
git commit -m "feat(tool): add data-package and artifact to graph store"
```

---

## Task 7: research-package CLI Module

**Files:**
- Create: `science-tool/src/science_tool/research_package/__init__.py`
- Create: `science-tool/src/science_tool/research_package/init_package.py`
- Create: `science-tool/src/science_tool/research_package/build_package.py`
- Create: `science-tool/src/science_tool/research_package/cli.py`
- Test: `science-tool/tests/test_research_package_cli.py`

This is a large task. The implementer should read the existing `datasets` module and CLI pattern for reference. Key files to study:
- `src/science_tool/datasets/__init__.py` — module structure
- `src/science_tool/cli.py` lines 1212-1361 — datasets CLI pattern
- The spec Section 3 (science-tool Commands) for exact command signatures

- [ ] **Step 1: Create init_package.py**

```python
# science-tool/src/science_tool/research_package/init_package.py
"""Scaffold a new research package directory."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _read_workflow_config(workflow_dir: Path) -> dict:
    """Read config.yaml from a workflow directory using simple regex parsing."""
    config_path = workflow_dir / "config.yaml"
    result: dict = {}
    if not config_path.is_file():
        return result
    text = config_path.read_text(encoding="utf-8")

    for key in ("title", "lens", "section", "workflow_name", "repository"):
        match = re.search(rf"^{key}:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()

    scripts_match = re.search(r"^scripts:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if scripts_match:
        result["scripts"] = [s.strip() for s in re.findall(r"\s+- (.+)", scripts_match.group(1))]

    inputs_match = re.search(r"^provenance_inputs:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if inputs_match:
        result["inputs"] = [s.strip() for s in re.findall(r"\s+- (.+)", inputs_match.group(1))]

    return result


def init_research_package(
    name: str,
    title: str,
    output_dir: Path,
    *,
    workflow_dir: Path | None = None,
) -> Path:
    """Scaffold a research package directory with empty structure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "figures").mkdir(exist_ok=True)
    (output_dir / "prose").mkdir(exist_ok=True)
    (output_dir / "excerpts").mkdir(exist_ok=True)

    # Read workflow config if provided
    config: dict = {}
    if workflow_dir:
        config = _read_workflow_config(workflow_dir)

    provenance = {
        "workflow": str(workflow_dir / "Snakefile") if workflow_dir else "",
        "config": str(workflow_dir / "config.yaml") if workflow_dir else "",
        "last_run": "",
        "git_commit": "",
        "repository": config.get("repository", ""),
        "inputs": [{"path": p, "sha256": ""} for p in config.get("inputs", [])],
        "scripts": config.get("scripts", []),
    }

    descriptor = {
        "name": name,
        "title": title,
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": [],
        "research": {
            "cells": "cells.json",
            "figures": [],
            "vegalite_specs": [],
            "code_excerpts": [],
            "provenance": provenance,
        },
    }

    (output_dir / "datapackage.json").write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "cells.json").write_text("[]\n", encoding="utf-8")

    return output_dir
```

- [ ] **Step 2: Create build_package.py**

```python
# science-tool/src/science_tool/research_package/build_package.py
"""Assemble a research package from workflow results."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from science_model.packages.validation import validate_package


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _read_workflow_config(config_path: Path) -> dict:
    """Parse workflow config.yaml via regex."""
    result: dict = {}
    if not config_path.is_file():
        return result
    text = config_path.read_text(encoding="utf-8")

    for key in ("title", "lens", "section", "workflow_name", "repository"):
        match = re.search(rf"^{key}:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()

    scripts_match = re.search(r"^scripts:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if scripts_match:
        result["scripts"] = [s.strip() for s in re.findall(r"\s+- (.+)", scripts_match.group(1))]

    inputs_match = re.search(r"^provenance_inputs:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if inputs_match:
        result["inputs"] = [s.strip() for s in re.findall(r"\s+- (.+)", inputs_match.group(1))]

    prose_match = re.search(r"^prose_dir:\s*(.+)$", text, re.MULTILINE)
    if prose_match:
        result["prose_dir"] = prose_match.group(1).strip()

    cells_match = re.search(r"^cells_file:\s*(.+)$", text, re.MULTILINE)
    if cells_match:
        result["cells_file"] = cells_match.group(1).strip()

    # Parse code_excerpts block
    excerpts_match = re.search(
        r"^code_excerpts:\s*\n((?:\s+- .+\n?|\s+\w+:.+\n?)+)", text, re.MULTILINE
    )
    if excerpts_match:
        excerpt_blocks = re.findall(
            r"- name:\s*(.+)\n\s+source:\s*(.+)\n\s+lines:\s*\[(\d+),\s*(\d+)\]",
            excerpts_match.group(1),
        )
        result["code_excerpts"] = [
            {"name": n.strip(), "source": s.strip(), "lines": [int(a), int(b)]}
            for n, s, a, b in excerpt_blocks
        ]

    return result


def build_research_package(
    results_dir: Path,
    config_path: Path,
    output_dir: Path,
) -> list[str]:
    """Assemble a research package from workflow results. Returns error list."""
    config = _read_workflow_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    prose_dir = output_dir / "prose"
    prose_dir.mkdir(exist_ok=True)
    excerpts_dir = output_dir / "excerpts"
    excerpts_dir.mkdir(exist_ok=True)

    # Copy CSVs
    resources = []
    for csv_file in sorted(results_dir.glob("*.csv")):
        dest = data_dir / csv_file.name
        shutil.copy2(csv_file, dest)
        resources.append({"name": csv_file.stem, "path": f"data/{csv_file.name}"})

    # Copy figures (PNGs and Vega-Lite specs)
    figures = []
    vegalite_specs = []
    results_figures = results_dir / "figures"
    if results_figures.is_dir():
        for fig_file in sorted(results_figures.iterdir()):
            dest = figures_dir / fig_file.name
            shutil.copy2(fig_file, dest)
            if fig_file.suffix == ".png":
                figures.append({
                    "name": fig_file.stem,
                    "path": f"figures/{fig_file.name}",
                    "caption": fig_file.stem.replace("-", " ").replace("_", " "),
                })
            elif fig_file.name.endswith(".vl.json"):
                vegalite_specs.append({
                    "name": fig_file.stem.removesuffix(".vl"),
                    "path": f"figures/{fig_file.name}",
                })

    # Copy prose
    prose_src = Path(config.get("prose_dir", "prose"))
    if prose_src.is_dir():
        for md_file in sorted(prose_src.glob("*.md")):
            shutil.copy2(md_file, prose_dir / md_file.name)

    # Extract code excerpts
    commit = _git_commit()
    repository = config.get("repository", "")
    code_excerpts = []
    for exc_config in config.get("code_excerpts", []):
        src_path = Path(exc_config["source"])
        if not src_path.is_file():
            continue
        lines = src_path.read_text(encoding="utf-8").splitlines()
        start, end = exc_config["lines"]
        excerpt_text = "\n".join(lines[start - 1 : end])
        exc_dest = excerpts_dir / src_path.name
        exc_dest.write_text(excerpt_text, encoding="utf-8")

        permalink = ""
        if repository and commit:
            permalink = f"{repository}/blob/{commit}/{exc_config['source']}#L{start}-L{end}"

        code_excerpts.append({
            "name": exc_config.get("name", src_path.stem),
            "path": f"excerpts/{src_path.name}",
            "source": exc_config["source"],
            "lines": exc_config["lines"],
            "github_permalink": permalink,
        })

    # Copy cells.json
    cells_src = Path(config.get("cells_file", "cells.json"))
    if cells_src.is_file():
        shutil.copy2(cells_src, output_dir / "cells.json")

    # Compute input hashes
    input_hashes = []
    for inp_path_str in config.get("inputs", []):
        inp_path = Path(inp_path_str)
        if inp_path.is_file():
            input_hashes.append({"path": inp_path_str, "sha256": _sha256_file(inp_path)})
        else:
            input_hashes.append({"path": inp_path_str, "sha256": ""})

    # Assemble descriptor
    lens = config.get("lens", "")
    section = config.get("section", "")
    descriptor = {
        "name": f"{lens}-{section}" if lens and section else config.get("workflow_name", "package"),
        "title": config.get("title", "Research Package"),
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": resources,
        "research": {
            "target_route": f"/guide/{lens}/{section}" if lens and section else None,
            "cells": "cells.json",
            "figures": figures,
            "vegalite_specs": vegalite_specs,
            "code_excerpts": code_excerpts,
            "provenance": {
                "workflow": config.get("workflow_name", ""),
                "config": str(config_path),
                "last_run": datetime.now(timezone.utc).isoformat(),
                "git_commit": commit,
                "repository": repository,
                "inputs": input_hashes,
                "scripts": config.get("scripts", []),
            },
        },
    }

    (output_dir / "datapackage.json").write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Validate
    result = validate_package(output_dir)
    return result.errors
```

- [ ] **Step 3: Create CLI module**

```python
# science-tool/src/science_tool/research_package/cli.py
"""Click commands for the research-package command group."""

from __future__ import annotations

import json
from pathlib import Path

import click

from science_model.packages.validation import validate_package, check_freshness

from .build_package import build_research_package
from .init_package import init_research_package


@click.group("research-package")
def research_package_group() -> None:
    """Research package management."""


@research_package_group.command("init")
@click.option("--name", required=True, help="Package name (slug)")
@click.option("--title", required=True, help="Human-readable title")
@click.option(
    "--workflow",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Workflow directory to read config from",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
def init_cmd(name: str, title: str, workflow: Path | None, output: Path) -> None:
    """Scaffold a new research package directory."""
    pkg_dir = init_research_package(name, title, output, workflow_dir=workflow)
    click.echo(f"Scaffolded research package at {pkg_dir}")


@research_package_group.command("validate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--check-freshness", is_flag=True, help="Also check input freshness")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project root for freshness check",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def validate_cmd(path: Path, check_freshness_flag: bool, project_root: Path | None, as_json: bool) -> None:
    """Validate research package(s)."""
    # Find packages: either a single package dir or a parent with subdirs
    packages: list[Path] = []
    if (path / "datapackage.json").is_file():
        packages.append(path)
    else:
        for dp in sorted(path.rglob("datapackage.json")):
            try:
                raw = json.loads(dp.read_text(encoding="utf-8"))
                if raw.get("profile") == "science-research-package":
                    packages.append(dp.parent)
            except (json.JSONDecodeError, OSError):
                continue

    if not packages:
        click.echo("No research packages found.")
        raise SystemExit(0)

    results = []
    has_errors = False

    for pkg_dir in packages:
        result = validate_package(pkg_dir)

        if check_freshness_flag:
            root = project_root or Path.cwd()
            freshness = check_freshness(pkg_dir, root)
            result.warnings.extend(freshness.warnings)

        results.append(result)
        if not result.ok:
            has_errors = True

    if as_json:
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for result in results:
            pkg_name = Path(result.package_dir).name
            if result.ok and not result.warnings:
                click.echo(f"  \u2713 {result.package_dir}")
            elif result.ok:
                for w in result.warnings:
                    click.echo(f"  \u26a0 {pkg_name}: {w}")
            else:
                for e in result.errors:
                    click.echo(f"  \u2717 {pkg_name}: {e}")

    raise SystemExit(1 if has_errors else 0)


@research_package_group.command("build")
@click.option(
    "--results",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Results directory from workflow run",
)
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Workflow config.yaml path",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
def build_cmd(results: Path, config: Path, output: Path) -> None:
    """Assemble a research package from workflow results."""
    errors = build_research_package(results, config, output)
    if errors:
        for e in errors:
            click.echo(f"  \u2717 {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Built research package at {output}")
```

- [ ] **Step 4: Create __init__.py**

```python
# science-tool/src/science_tool/research_package/__init__.py
"""Research package management — init, validate, build."""

from .build_package import build_research_package
from .init_package import init_research_package

__all__ = ["build_research_package", "init_research_package"]
```

- [ ] **Step 5: Write CLI tests**

Create `science-tool/tests/test_research_package_cli.py`:

```python
"""Tests for research-package CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestResearchPackageInit:
    def test_init_creates_scaffold(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "pkg"
        result = runner.invoke(
            main,
            ["research-package", "init", "--name", "test-pkg", "--title", "Test Package", "--output", str(output)],
        )
        assert result.exit_code == 0
        assert (output / "datapackage.json").is_file()
        assert (output / "cells.json").is_file()
        assert (output / "data").is_dir()
        assert (output / "figures").is_dir()
        assert (output / "prose").is_dir()
        assert (output / "excerpts").is_dir()

        descriptor = json.loads((output / "datapackage.json").read_text())
        assert descriptor["name"] == "test-pkg"
        assert descriptor["profile"] == "science-research-package"

    def test_init_with_workflow(self, runner: CliRunner, tmp_path: Path) -> None:
        workflow_dir = tmp_path / "workflows" / "test"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "config.yaml").write_text(
            "lens: theme\nsection: chaos\nrepository: https://github.com/test\nscripts:\n  - scripts/foo.ts\nprovenance_inputs:\n  - src/bar.ts\n"
        )

        output = tmp_path / "pkg"
        result = runner.invoke(
            main,
            [
                "research-package", "init",
                "--name", "test-pkg",
                "--title", "Test",
                "--workflow", str(workflow_dir),
                "--output", str(output),
            ],
        )
        assert result.exit_code == 0
        descriptor = json.loads((output / "datapackage.json").read_text())
        assert descriptor["research"]["provenance"]["scripts"] == ["scripts/foo.ts"]


class TestResearchPackageValidate:
    def test_validate_valid_package(self, runner: CliRunner, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "data").mkdir()
        (pkg_dir / "prose").mkdir()
        (pkg_dir / "data" / "scores.csv").write_text("a,b\n1,2\n")
        (pkg_dir / "prose" / "01.md").write_text("# Intro\n")

        descriptor = {
            "name": "test",
            "title": "Test",
            "profile": "science-research-package",
            "version": "1.0.0",
            "resources": [{"name": "scores", "path": "data/scores.csv"}],
            "research": {
                "cells": "cells.json",
                "figures": [],
                "vegalite_specs": [],
                "code_excerpts": [],
                "provenance": {
                    "workflow": "w",
                    "config": "c",
                    "last_run": "2026-01-01",
                    "git_commit": "abc",
                    "repository": "",
                    "inputs": [],
                    "scripts": [],
                },
            },
        }
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))
        (pkg_dir / "cells.json").write_text(
            json.dumps([{"type": "narrative", "content": "prose/01.md"}, {"type": "data-table", "resource": "scores"}])
        )

        result = runner.invoke(main, ["research-package", "validate", str(pkg_dir)])
        assert result.exit_code == 0

    def test_validate_invalid_package(self, runner: CliRunner, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "datapackage.json").write_text('{"profile": "wrong"}')
        (pkg_dir / "cells.json").write_text("[]")

        result = runner.invoke(main, ["research-package", "validate", str(pkg_dir)])
        assert result.exit_code == 1

    def test_validate_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        # Missing datapackage.json entirely — but path exists
        result = runner.invoke(main, ["research-package", "validate", str(pkg_dir), "--json"])
        # No datapackage.json found, so no packages detected
        assert result.exit_code == 0
        assert "No research packages found" in result.output
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_research_package_cli.py -v`
Expected: FAIL — command group not registered

- [ ] **Step 7: Register command group in cli.py**

In `science-tool/src/science_tool/cli.py`, add the import and registration.

At the top, add:

```python
from science_tool.research_package.cli import research_package_group
```

After the last `main.add_command(...)` or `@main.group()` definition, add:

```python
main.add_command(research_package_group)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_research_package_cli.py -v`
Expected: All tests PASS

- [ ] **Step 9: Run full test suite**

Run: `cd ~/d/science/science-tool && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/research_package/ src/science_tool/cli.py tests/test_research_package_cli.py
git commit -m "feat(tool): add research-package command group (init, validate, build)"
```

---

## Task 8: Update Snakemake Skill

**Files:**
- Modify: `skills/pipelines/snakemake.md`

- [ ] **Step 1: Read the current skill**

Read `~/d/science/skills/pipelines/snakemake.md` to find the right insertion point.

- [ ] **Step 2: Add research package integration section**

Append a new section before the final tips/notes. The section should cover:

- Terminal rule pattern: `rule build_package` calling `science-tool research-package build --results results/ --config config.yaml --output research/packages/{lens}/{section}/`
- Workflow config structure for research packages: `prose_dir`, `cells_file`, `provenance_inputs`, `scripts`, `code_excerpts`, `repository`
- Example Snakemake rule:

```python
rule build_package:
    input:
        results=directory("results"),
    output:
        descriptor="research/packages/{config[lens]}/{config[section]}/datapackage.json",
    shell:
        "science-tool research-package build --results {input.results} --config config.yaml --output research/packages/{config[lens]}/{config[section]}/"
```

- Note that `workflow-step` entities should carry a `script_path` property for traceability
- Link to `research/provenance.md` skill for full schema documentation

- [ ] **Step 3: Commit**

```bash
cd ~/d/science
git add skills/pipelines/snakemake.md
git commit -m "doc: add research package integration section to Snakemake skill"
```

---

## Task 9: Research Provenance Skill (Layer 1)

**Files:**
- Create: `skills/research/provenance.md`

- [ ] **Step 1: Write the skill**

Create `~/d/science/skills/research/provenance.md` with these sections:

1. **Overview**: What is a research package — a Frictionless data package with the `science-research-package` profile that bundles analysis results, narrative prose, code excerpts, and execution provenance
2. **Package structure**: Directory layout (`datapackage.json`, `cells.json`, `data/`, `figures/`, `prose/`, `excerpts/`)
3. **Schema reference**: Key fields in `datapackage.json` — `resources`, `research.cells`, `research.figures`, `research.vegalite_specs`, `research.code_excerpts`, `research.provenance`
4. **Cell types**: narrative (file path to .md), data-table (resource name + optional columns/caption), figure (ref to figures[]), vegalite (ref to vegalite_specs[]), code-reference (ref to code_excerpts[]), provenance (auto-rendered)
5. **CLI commands**: `science-tool research-package init`, `validate`, `build` with usage examples
6. **Workflow integration**: How Snakemake workflows produce packages — terminal `build_package` rule, config.yaml structure, prose + cells alongside the Snakefile
7. **KG integration**: `data-package` and `artifact` entity types, `workflow-run` linkage via `produced_by`, `artifact` linkage via `derived_from`
8. **Provenance model**: Input SHA-256 hashing, git commit pinning, freshness checking via `--check-freshness`
9. **Non-GitHub repos**: `github_permalink` may be empty; code excerpts still work as embedded files
10. **Vega-Lite support**: Producing `.vl.json` specs from Altair (`chart.save("results/figures/chart.vl.json")`) or hand-written Vega-Lite JSON

- [ ] **Step 2: Commit**

```bash
cd ~/d/science
git add skills/research/provenance.md
git commit -m "doc: add research provenance skill (layer 1 — reproducible workflows)"
```

---

## Task 10: Lab Notebook Skill (Layer 2)

**Files:**
- Create: `skills/research/lab-notebook.md`

- [ ] **Step 1: Write the skill**

Create `~/d/science/skills/research/lab-notebook.md` with these sections:

1. **Overview**: Rendering research packages as notebook-like web pages — builds on the provenance skill
2. **Cell rendering guidance**: How each cell type maps to a web component:
   - `narrative` → fetch markdown file, render with remark/rehype or similar
   - `data-table` → parse CSV, render sortable/filterable table
   - `figure` → `<img>` with caption
   - `vegalite` → `vega-embed` library renders Vega-Lite JSON spec interactively
   - `code-reference` → collapsible code block, GitHub permalink (graceful fallback when empty)
   - `provenance` → metadata summary grid (workflow, commit, run date, scripts, inputs)
3. **Routing pattern**: Sub-routes at `{path}/src` using framework router (e.g., TanStack Router, Next.js, etc.)
4. **Manifest pattern**: Prebuild script validates/copies packages to public directory, generates `manifest.json` mapping route keys to package metadata
5. **ViewSourceButton pattern**: Conditional rendering — check manifest for current route, show/hide button accordingly
6. **DataPackageLoader pattern**: Runtime `fetch()` for `datapackage.json` + `cells.json`, schema validation at boundary, CSV parsing with RFC 4180 support
7. **Artifact entity**: `artifact_type: "web_route"` with `target` pointing to the rendered route, linked to `data-package` via `derived_from`
8. **Reference implementation**: Point to natural-systems project `src/research/` as a working TypeScript/React example

- [ ] **Step 2: Commit**

```bash
cd ~/d/science
git add skills/research/lab-notebook.md
git commit -m "doc: add lab notebook skill (layer 2 — web app rendering)"
```

---

## Task 11: natural-systems Migration

**Files:**
- Modify: `research/packages/theme/instability-bifurcation/datapackage.json`
- Modify: `public/research/theme/instability-bifurcation/datapackage.json`
- Modify: `src/research/types.ts`

- [ ] **Step 1: Update package profile**

In `/mnt/ssd/Dropbox/natural-systems/research/packages/theme/instability-bifurcation/datapackage.json`, change:

```json
"profile": "natural-systems-research-package"
```

to:

```json
"profile": "science-research-package"
```

- [ ] **Step 2: Update TypeScript schema**

In `/mnt/ssd/Dropbox/natural-systems/src/research/types.ts`, update the `ResearchPackageSchema` profile literal:

```typescript
profile: z.literal('science-research-package'),
```

Add `VegaLiteSpec` and `VegaLiteCell` schemas to prepare for future use:

In the research extension schema, add:

```typescript
vegalite_specs: z.array(z.object({
  name: z.string(),
  path: z.string(),
  caption: z.string().optional(),
})).default([]),
```

Add a new cell schema:

```typescript
const VegaLiteCellSchema = z.object({
  type: z.literal('vegalite'),
  ref: z.string(),
  caption: z.string().optional(),
});
```

Add it to the `CellSchema` discriminated union.

Export the new types.

- [ ] **Step 3: Regenerate public copy**

Run: `cd /mnt/ssd/Dropbox/natural-systems && npm run generate:research-packages`

- [ ] **Step 4: Run tests**

Run: `cd /mnt/ssd/Dropbox/natural-systems && npx vitest run src/research/`
Expected: All tests PASS (update test fixtures if they reference the old profile literal)

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/natural-systems
git add research/packages/ public/research/ src/research/types.ts src/research/__tests__/
git commit -m "feat(research): migrate to science-research-package profile"
```

# Science Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web dashboard (FastAPI + React) for visualizing and managing Science research projects, with a shared data model package.

**Architecture:** Three packages — `science-model` (shared Pydantic models, lives in science repo), `science-web` (separate repo, FastAPI backend + React frontend). `science-tool` and `science-web` both depend on `science-model`. Backend reads project directories via filesystem + SQLite index; frontend uses react-force-graph for KG visualization.

**Tech Stack:** Python 3.12+/uv, FastAPI, rdflib, aiosqlite, watchfiles, React 19, TypeScript, Vite, react-force-graph-2d/3d, zustand, Tailwind CSS, cmdk

**Spec:** `docs/superpowers/specs/2026-03-11-science-dashboard-design.md`

---

## Chunk 1: science-model — Shared Data Model Package

### Task 1: Scaffold science-model package

**Files:**
- Create: `science-model/pyproject.toml`
- Create: `science-model/src/science_model/__init__.py`
- Create: `science-model/src/science_model/py.typed`
- Create: `science-model/tests/__init__.py`

- [ ] **Step 1: Create package directory structure**

```bash
mkdir -p science-model/src/science_model science-model/tests
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[project]
name = "science-model"
version = "0.1.0"
description = "Shared data models for Science research framework"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.0",
]

[build-system]
requires = ["hatchling>=1.24"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/science_model"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.ruff]
line-length = 120

[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
venvPath = "."
venv = ".venv"

[dependency-groups]
dev = [
    "pytest>=9.0",
]
```

- [ ] **Step 3: Write __init__.py with re-exports**

```python
"""Shared data models for Science research framework."""
```

- [ ] **Step 4: Create py.typed marker and tests/__init__.py**

Empty files for PEP 561 and test discovery.

- [ ] **Step 5: Verify package installs**

Run: `cd science-model && uv sync && uv run python -c "import science_model; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add science-model/
git commit -m "feat: scaffold science-model shared data model package"
```

---

### Task 2: Define entity and project models

**Files:**
- Create: `science-model/src/science_model/entities.py`
- Create: `science-model/src/science_model/projects.py`
- Create: `science-model/tests/test_entities.py`
- Create: `science-model/tests/test_projects.py`

- [ ] **Step 1: Write test for Entity model**

```python
# tests/test_entities.py
from datetime import date
from science_model.entities import Entity, EntityType

def test_entity_round_trip():
    e = Entity(
        id="hypothesis:h01-foo",
        type=EntityType.HYPOTHESIS,
        title="Test hypothesis",
        status="proposed",
        project="my-project",
        tags=["genomics"],
        ontology_terms=["GO:0006915"],
        created=date(2026, 3, 1),
        updated=date(2026, 3, 10),
        related=["question:q01"],
        source_refs=[],
        content_preview="A test hypothesis about...",
        file_path="specs/hypotheses/h01-foo.md",
    )
    assert e.type == EntityType.HYPOTHESIS
    assert e.id == "hypothesis:h01-foo"
    d = e.model_dump()
    assert d["type"] == "hypothesis"
    e2 = Entity.model_validate(d)
    assert e2 == e

def test_entity_optional_fields_default_none():
    e = Entity(
        id="concept:foo",
        type=EntityType.CONCEPT,
        title="Foo",
        project="p",
        tags=[],
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/topics/foo.md",
    )
    assert e.status is None
    assert e.domain is None
    assert e.maturity is None
    assert e.confidence is None
    assert e.datasets is None
    assert e.created is None
    assert e.updated is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-model && uv run pytest tests/test_entities.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write entities.py**

```python
"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class EntityType(StrEnum):
    """Known entity types across Science projects."""

    CONCEPT = "concept"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    PAPER = "paper"
    CLAIM = "claim"
    INQUIRY = "inquiry"
    TOPIC = "topic"
    INTERPRETATION = "interpretation"
    DISCUSSION = "discussion"
    MODEL = "model"
    PRE_REGISTRATION = "pre-registration"
    PLAN = "plan"
    ASSUMPTION = "assumption"
    TRANSFORMATION = "transformation"
    VARIABLE = "variable"
    DATASET = "dataset"
    METHOD = "method"
    COMPARISON = "comparison"
    EXPERIMENT = "experiment"
    BIAS_AUDIT = "bias-audit"
    ARTICLE = "article"
    PIPELINE_STEP = "pipeline-step"
    UNKNOWN = "unknown"


class Entity(BaseModel):
    """A research entity parsed from frontmatter or the knowledge graph."""

    id: str
    type: EntityType
    title: str
    status: str | None = None
    project: str
    domain: str | None = None
    tags: list[str]
    ontology_terms: list[str]
    created: date | None = None
    updated: date | None = None
    related: list[str]
    source_refs: list[str]
    content_preview: str
    file_path: str
    # Type-specific
    maturity: str | None = None
    confidence: float | None = None
    datasets: list[str] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-model && uv run pytest tests/test_entities.py -v`
Expected: PASS

- [ ] **Step 5: Write test for Project model**

```python
# tests/test_projects.py
from datetime import date, datetime
from science_model.projects import Project, ProjectDetail, GraphSummary

def test_project_model():
    p = Project(
        slug="seq-feats",
        name="seq-feats",
        path="/home/user/d/seq-feats",
        summary="Research on sequence features",
        status="active",
        aspects=["hypothesis-testing"],
        tags=["genomics"],
        entity_counts={"hypothesis": 4, "question": 13},
        created=date(2026, 3, 2),
    )
    assert p.slug == "seq-feats"
    assert p.staleness_days is None

def test_project_detail_extends_project():
    pd = ProjectDetail(
        slug="test",
        name="test",
        path="/tmp/test",
        aspects=[],
        tags=[],
        entity_counts={},
        hypotheses=[],
        questions=[],
        tasks=[],
        graph_summary=GraphSummary(node_count=0, edge_count=0, top_domains=[]),
    )
    assert pd.graph_summary.node_count == 0
```

- [ ] **Step 6: Write projects.py**

```python
"""Project data models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from science_model.entities import Entity
from science_model.tasks import Task


class GraphSummary(BaseModel):
    """Summary statistics for a project's knowledge graph."""

    node_count: int
    edge_count: int
    top_domains: list[str]


class Project(BaseModel):
    """Summary of a Science project."""

    slug: str
    name: str
    path: str
    summary: str | None = None
    status: str | None = None
    aspects: list[str]
    tags: list[str]
    entity_counts: dict[str, int]
    created: date | None = None
    last_modified: date | None = None
    last_activity: datetime | None = None
    staleness_days: int | None = None


class ProjectDetail(Project):
    """Full project detail including top entities."""

    hypotheses: list[Entity]
    questions: list[Entity]
    tasks: list[Task]
    graph_summary: GraphSummary
```

- [ ] **Step 7: Run tests**

Run: `cd science-model && uv run pytest tests/ -v`
Expected: PASS (both files)

- [ ] **Step 8: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/src/science_model/projects.py
git add science-model/tests/test_entities.py science-model/tests/test_projects.py
git commit -m "feat(science-model): add Entity, Project, ProjectDetail models"
```

---

### Task 3: Define task models

**Files:**
- Create: `science-model/src/science_model/tasks.py`
- Create: `science-model/tests/test_tasks.py`

- [ ] **Step 1: Write test for Task model**

```python
# tests/test_tasks.py
from datetime import date
from science_model.tasks import Task, TaskCreate, TaskUpdate, TaskStatus

def test_task_model():
    t = Task(
        id="t001",
        project="seq-feats",
        title="Run baseline",
        description="Execute the baseline pipeline",
        type="analysis",
        priority="P1",
        status=TaskStatus.PROPOSED,
        blocked_by=[],
        related=[],
        created=date(2026, 3, 1),
    )
    assert t.status == "proposed"
    assert t.completed is None

def test_task_create_defaults():
    tc = TaskCreate(title="New task")
    assert tc.priority == "P2"
    assert tc.type == ""
    assert tc.description == ""

def test_task_update_partial():
    tu = TaskUpdate(status=TaskStatus.ACTIVE)
    assert tu.title is None
    assert tu.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-model && uv run pytest tests/test_tasks.py -v`
Expected: FAIL

- [ ] **Step 3: Write tasks.py**

```python
"""Task data models."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class TaskStatus(StrEnum):
    """Task status values used by science-tool."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    DONE = "done"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class Task(BaseModel):
    """A research task."""

    id: str
    project: str
    title: str
    description: str = ""
    type: str = ""
    priority: str = "P2"
    status: str = TaskStatus.PROPOSED
    blocked_by: list[str] = []
    related: list[str] = []
    created: date = date.today()
    completed: date | None = None


class TaskCreate(BaseModel):
    """Input for creating a new task."""

    title: str
    type: str = ""
    priority: str = "P2"
    related: list[str] = []
    blocked_by: list[str] = []
    description: str = ""


class TaskUpdate(BaseModel):
    """Partial update for a task."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    type: str | None = None
    related: list[str] | None = None
    blocked_by: list[str] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-model && uv run pytest tests/test_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/tasks.py science-model/tests/test_tasks.py
git commit -m "feat(science-model): add Task, TaskCreate, TaskUpdate models"
```

---

### Task 4: Define graph, search, config, and activity models

**Files:**
- Create: `science-model/src/science_model/graph.py`
- Create: `science-model/src/science_model/search.py`
- Create: `science-model/src/science_model/config.py`
- Create: `science-model/src/science_model/activity.py`
- Create: `science-model/tests/test_graph.py`

- [ ] **Step 1: Write test for graph models**

```python
# tests/test_graph.py
from datetime import date
from science_model.graph import GraphData, GraphNode, GraphEdge

def test_graph_data_structure():
    node = GraphNode(
        id="http://example.org/project/concept/foo",
        label="Foo",
        type="Concept",
        importance=0.8,
        graph_layer="graph/knowledge",
    )
    edge = GraphEdge(
        source=node.id,
        target="http://example.org/project/concept/bar",
        predicate="skos:related",
        graph_layer="graph/knowledge",
    )
    gd = GraphData(
        nodes=[node],
        edges=[edge],
        domains={"genomics": "#e06c75"},
        lod=0.5,
        total_nodes=10,
    )
    assert gd.total_nodes == 10
    assert gd.nodes[0].boundary_role is None
```

- [ ] **Step 2: Run test, verify fail**

Run: `cd science-model && uv run pytest tests/test_graph.py -v`

- [ ] **Step 3: Write graph.py**

```python
"""Knowledge graph data models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class GraphNode(BaseModel):
    """A node in the knowledge graph for visualization."""

    id: str
    label: str
    type: str
    domain: str | None = None
    importance: float = 0.0
    status: str | None = None
    maturity: str | None = None
    confidence: float | None = None
    updated: date | None = None
    graph_layer: str
    inquiry: str | None = None
    boundary_role: str | None = None


class GraphEdge(BaseModel):
    """An edge in the knowledge graph for visualization."""

    source: str
    target: str
    predicate: str
    graph_layer: str
    provenance: str | None = None


class GraphData(BaseModel):
    """Complete graph payload for the frontend."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    domains: dict[str, str]
    lod: float
    total_nodes: int


class GraphSummary(BaseModel):
    """Summary statistics for a project's knowledge graph."""

    node_count: int
    edge_count: int
    top_domains: list[str]
```

- [ ] **Step 4: Write search.py, activity.py, config.py**

```python
# search.py
"""Search and filter models."""

from __future__ import annotations

from pydantic import BaseModel

from science_model.entities import Entity


class Filters(BaseModel):
    """Query filters for entity listing."""

    project: str | None = None
    entity_type: str | None = None
    status: str | None = None
    domain: str | None = None
    tags: list[str] | None = None


class SearchResult(BaseModel):
    """A single search result."""

    entity: Entity
    score: float
    highlights: list[str]
```

```python
# activity.py
"""Activity feed models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityItem(BaseModel):
    """A single activity event."""

    project: str
    entity_id: str | None = None
    entity_type: str | None = None
    title: str
    action: str
    timestamp: datetime
    detail: str | None = None
```

```python
# config.py
"""Dashboard configuration models."""

from __future__ import annotations

from pydantic import BaseModel


class LodWeights(BaseModel):
    """Weights for the LoD importance scoring function."""

    degree: float = 0.4
    recency: float = 0.3
    status: float = 0.2
    evidence_density: float = 0.1


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    projects: list[str]
    palette: str = "onedark"
    domain_colors: dict[str, str] = {}
    lod_weights: LodWeights = LodWeights()
    sqlite_path: str | None = None


class ConfigUpdate(BaseModel):
    """Partial config update."""

    projects: list[str] | None = None
    palette: str | None = None
    domain_colors: dict[str, str] | None = None
    lod_weights: LodWeights | None = None
    sqlite_path: str | None = None
```

- [ ] **Step 5: Run all tests**

Run: `cd science-model && uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Update __init__.py with re-exports**

```python
"""Shared data models for Science research framework."""

from science_model.activity import ActivityItem
from science_model.config import ConfigUpdate, DashboardConfig, LodWeights
from science_model.entities import Entity, EntityType
from science_model.graph import GraphData, GraphEdge, GraphNode, GraphSummary
from science_model.projects import Project, ProjectDetail
from science_model.search import Filters, SearchResult
from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate

__all__ = [
    "ActivityItem",
    "ConfigUpdate",
    "DashboardConfig",
    "Entity",
    "EntityType",
    "Filters",
    "GraphData",
    "GraphEdge",
    "GraphNode",
    "GraphSummary",
    "LodWeights",
    "Project",
    "ProjectDetail",
    "SearchResult",
    "Task",
    "TaskCreate",
    "TaskStatus",
    "TaskUpdate",
]
```

- [ ] **Step 7: Commit**

```bash
git add science-model/
git commit -m "feat(science-model): add graph, search, activity, config models"
```

---

### Task 5: Define frontmatter parser

**Files:**
- Create: `science-model/src/science_model/frontmatter.py`
- Create: `science-model/tests/test_frontmatter.py`

- [ ] **Step 1: Write test for frontmatter parsing**

```python
# tests/test_frontmatter.py
from pathlib import Path
from science_model.frontmatter import parse_frontmatter, parse_entity_file

def test_parse_frontmatter_basic(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "hypothesis:h01-test"
type: hypothesis
title: "Test hypothesis"
status: proposed
tags: [genomics, ml]
ontology_terms: ["GO:0006915"]
created: 2026-03-01
updated: 2026-03-10
related: ["question:q01"]
source_refs: []
---

This is the body content of the hypothesis.

## Rationale

Some rationale here.
""")
    fm, body = parse_frontmatter(md)
    assert fm["id"] == "hypothesis:h01-test"
    assert fm["type"] == "hypothesis"
    assert fm["tags"] == ["genomics", "ml"]
    assert "This is the body content" in body

def test_parse_frontmatter_missing_file(tmp_path: Path):
    result = parse_frontmatter(tmp_path / "nonexistent.md")
    assert result is None

def test_parse_entity_file(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "question:q01-test"
type: question
title: "What is X?"
status: open
tags: []
created: 2026-03-01
---

Body text here.
""")
    entity = parse_entity_file(md, project_slug="my-project")
    assert entity.id == "question:q01-test"
    assert entity.type.value == "question"
    assert entity.project == "my-project"
    assert entity.content_preview == "Body text here."
```

- [ ] **Step 2: Run test, verify fail**

Run: `cd science-model && uv run pytest tests/test_frontmatter.py -v`

- [ ] **Step 3: Write frontmatter.py**

```python
"""YAML frontmatter parser for Science markdown documents."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_model.entities import Entity, EntityType


def parse_frontmatter(path: Path) -> tuple[dict, str] | None:
    """Parse YAML frontmatter and body from a markdown file.

    Returns (frontmatter_dict, body_text) or None if file doesn't exist.
    """
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return fm, body


def _coerce_date(val: str | date | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def _resolve_type(raw: str) -> EntityType:
    try:
        return EntityType(raw)
    except ValueError:
        return EntityType.UNKNOWN


def parse_entity_file(path: Path, project_slug: str) -> Entity | None:
    """Parse a markdown file into an Entity. Returns None on parse failure."""
    result = parse_frontmatter(path)
    if result is None:
        return None

    fm, body = result
    if not fm.get("type"):
        return None

    rel_path = str(path)
    # Try to make relative to project root
    for parent in path.parents:
        if (parent / "science.yaml").exists():
            rel_path = str(path.relative_to(parent))
            break

    return Entity(
        id=fm.get("id", f"{fm['type']}:{path.stem}"),
        type=_resolve_type(fm["type"]),
        title=fm.get("title", path.stem),
        status=fm.get("status"),
        project=project_slug,
        domain=None,  # computed later by domain assignment
        tags=fm.get("tags") or [],
        ontology_terms=fm.get("ontology_terms") or [],
        created=_coerce_date(fm.get("created")),
        updated=_coerce_date(fm.get("updated")),
        related=fm.get("related") or [],
        source_refs=fm.get("source_refs") or [],
        content_preview=body[:200] if body else "",
        file_path=rel_path,
        maturity=fm.get("maturity"),
        confidence=fm.get("confidence"),
        datasets=fm.get("datasets"),
    )
```

- [ ] **Step 4: Add pyyaml dependency**

```bash
cd science-model && uv add pyyaml
```

- [ ] **Step 5: Run tests**

Run: `cd science-model && uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add science-model/
git commit -m "feat(science-model): add frontmatter parser"
```

---

### Task 6: Wire science-tool to depend on science-model

**Files:**
- Modify: `science-tool/pyproject.toml`
- Modify: `science-tool/src/science_tool/tasks.py` (re-export from science-model)

- [ ] **Step 1: Add science-model as editable dependency of science-tool**

```bash
cd science-tool && uv add --editable ../science-model
```

- [ ] **Step 2: Verify existing science-tool tests still pass**

Run: `cd science-tool && uv run pytest tests/ -v`
Expected: all existing tests PASS

- [ ] **Step 3: Commit**

```bash
git add science-tool/pyproject.toml science-tool/uv.lock
git commit -m "feat(science-tool): add science-model as dependency"
```

Note: Full migration of science-tool's Task dataclass to science-model's Pydantic Task is deferred — it requires updating all call sites in cli.py and store.py. For now, both representations coexist; science-web uses science-model's models exclusively.

---

## Chunk 2: science-web Backend — Scaffold, Indexer, Store

### Task 7: Scaffold science-web repository

**Files:**
- Create: `~/d/science-web/pyproject.toml`
- Create: `~/d/science-web/backend/__init__.py`
- Create: `~/d/science-web/backend/app.py`
- Create: `~/d/science-web/Makefile`
- Create: `~/d/science-web/config.example.yaml`
- Create: `~/d/science-web/.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p ~/d/science-web/backend/routes ~/d/science-web/tests ~/d/science-web/frontend
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[project]
name = "science-web"
version = "0.1.0"
description = "Local web dashboard for Science research projects"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "science-model",
    "science-tool",
    "rdflib>=7.0",
    "aiosqlite>=0.20",
    "watchfiles>=1.0",
    "pyyaml>=6.0",
]

[build-system]
requires = ["hatchling>=1.24"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["backend"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.ruff]
line-length = 120

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "basic"

[dependency-groups]
dev = [
    "pytest>=9.0",
    "httpx>=0.27",
    "pytest-anyio>=0.0.0",
]
```

- [ ] **Step 3: Write backend/app.py (minimal FastAPI entry)**

```python
"""Science Dashboard — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Science Dashboard", version="0.1.0")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Write config.example.yaml**

```yaml
projects:
  - ~/d/seq-feats
  - ~/d/mindful/natural-systems-guide
  - ~/d/3d-attention-bias

palette: onedark
sqlite_path: null
```

- [ ] **Step 5: Write Makefile**

```makefile
.PHONY: dev backend frontend

dev:
	$(MAKE) -j2 backend frontend

backend:
	uv run uvicorn backend.app:app --reload --port 8000

frontend:
	cd frontend && npm run dev
```

- [ ] **Step 6: Write .gitignore, init git**

```
__pycache__/
*.pyc
.venv/
node_modules/
dist/
.env
*.db
```

```bash
cd ~/d/science-web && git init && git add . && git commit -m "feat: scaffold science-web project"
```

- [ ] **Step 7: Install dependencies, verify health endpoint**

```bash
cd ~/d/science-web && uv sync
uv run uvicorn backend.app:app --port 8000 &
sleep 2
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
kill %1
```

---

### Task 8: Config loader

**Files:**
- Create: `~/d/science-web/backend/config.py`
- Create: `~/d/science-web/tests/test_config.py`

- [ ] **Step 1: Write test**

```python
# tests/test_config.py
from pathlib import Path
from backend.config import load_config

def test_load_config_from_file(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("""
projects:
  - /tmp/project-a
  - /tmp/project-b
palette: catppuccin
""")
    cfg = load_config(cfg_path)
    assert len(cfg.projects) == 2
    assert cfg.palette == "catppuccin"
    assert cfg.sqlite_path is None

def test_load_config_defaults(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("projects: []\n")
    cfg = load_config(cfg_path)
    assert cfg.palette == "onedark"
    assert cfg.lod_weights.degree == 0.4
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Write config.py**

```python
"""Dashboard configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from science_model import DashboardConfig

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "science-dashboard" / "config.yaml"


def load_config(path: Path | None = None) -> DashboardConfig:
    """Load dashboard config from YAML file."""
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.is_file():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    # Expand ~ in project paths
    projects = [str(Path(p).expanduser()) for p in raw.get("projects", [])]
    raw["projects"] = projects

    return DashboardConfig.model_validate(raw)
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: add config loader"
```

---

### Task 9: Project scanner and entity indexer

**Files:**
- Create: `~/d/science-web/backend/indexer.py`
- Create: `~/d/science-web/tests/test_indexer.py`

- [ ] **Step 1: Write test for scanning a minimal project**

```python
# tests/test_indexer.py
from pathlib import Path
from backend.indexer import scan_project

def _make_project(tmp_path: Path) -> Path:
    """Create a minimal science project for testing."""
    root = tmp_path / "test-project"
    root.mkdir()
    (root / "science.yaml").write_text("""
name: test-project
created: "2026-03-01"
status: active
aspects: [hypothesis-testing]
tags: [testing]
summary: A test project.
""")
    # A hypothesis
    hyp_dir = root / "specs" / "hypotheses"
    hyp_dir.mkdir(parents=True)
    (hyp_dir / "h01-test.md").write_text("""---
id: "hypothesis:h01-test"
type: hypothesis
title: "Test hypothesis"
status: proposed
tags: [testing]
created: 2026-03-01
---
Body of hypothesis.
""")
    # A question
    q_dir = root / "doc" / "questions"
    q_dir.mkdir(parents=True)
    (q_dir / "q01.md").write_text("""---
id: "question:q01-test"
type: question
title: "What is X?"
status: open
tags: []
created: 2026-03-01
---
Question body.
""")
    # Tasks
    tasks_dir = root / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text("""## [t001] First task
- type: research
- priority: P1
- status: proposed
- created: 2026-03-01

Do the thing.
""")
    return root

def test_scan_project_finds_entities(tmp_path: Path):
    root = _make_project(tmp_path)
    result = scan_project(root)
    assert result.project.slug == "test-project"
    assert result.project.name == "test-project"
    assert result.project.status == "active"
    assert len(result.entities) == 2  # hypothesis + question
    assert len(result.tasks) == 1
    types = {e.type.value for e in result.entities}
    assert "hypothesis" in types
    assert "question" in types

def test_scan_project_task_parsed(tmp_path: Path):
    root = _make_project(tmp_path)
    result = scan_project(root)
    task = result.tasks[0]
    assert task.id == "t001"
    assert task.title == "First task"
    assert task.status == "proposed"
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Write indexer.py**

```python
"""Project scanner — reads project directories into science-model types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml
from science_model import Entity, Project, Task
from science_model.frontmatter import parse_entity_file
from science_tool.paths import resolve_paths
from science_tool.tasks import parse_tasks as st_parse_tasks


_SKIP_DIRS = {"templates", ".venv", "data", ".git", "__pycache__", "node_modules"}


@dataclass
class ProjectScan:
    """Result of scanning a single project directory."""

    project: Project
    entities: list[Entity] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)


def _parse_science_yaml(root: Path) -> dict:
    yaml_path = root / "science.yaml"
    if not yaml_path.is_file():
        return {}
    with open(yaml_path) as f:
        return yaml.safe_load(f) or {}


def _scan_markdown_dir(directory: Path, project_slug: str) -> list[Entity]:
    """Recursively scan a directory for markdown files with frontmatter."""
    entities: list[Entity] = []
    if not directory.is_dir():
        return entities
    for md_path in sorted(directory.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in md_path.parts):
            continue
        entity = parse_entity_file(md_path, project_slug)
        if entity is not None:
            entities.append(entity)
    return entities


def _coerce_date(val: str | date | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def _scan_tasks(root: Path, project_slug: str) -> list[Task]:
    """Parse tasks from active.md and done/ using science-tool's parser."""
    paths = resolve_paths(root)
    raw_tasks = st_parse_tasks(paths.tasks_dir / "active.md")
    return [
        Task(
            id=t.id,
            project=project_slug,
            title=t.title,
            description=t.description,
            type=t.type,
            priority=t.priority,
            status=t.status,
            blocked_by=list(t.blocked_by),
            related=list(t.related),
            created=t.created,
            completed=t.completed,
        )
        for t in raw_tasks
    ]


def _latest_mtime(root: Path) -> datetime | None:
    """Find the most recent mtime across project files."""
    latest: float = 0
    for p in root.rglob("*.md"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        mtime = p.stat().st_mtime
        if mtime > latest:
            latest = mtime
    trig = root / "knowledge" / "graph.trig"
    if trig.is_file():
        mtime = trig.stat().st_mtime
        if mtime > latest:
            latest = mtime
    return datetime.fromtimestamp(latest) if latest > 0 else None


def scan_project(root: Path) -> ProjectScan:
    """Scan a project directory and return structured data."""
    slug = root.name
    meta = _parse_science_yaml(root)
    paths = resolve_paths(root)

    # Scan entities from all relevant directories
    entities: list[Entity] = []
    for scan_dir in [paths.doc_dir, paths.specs_dir]:
        entities.extend(_scan_markdown_dir(scan_dir, slug))
    # papers/summaries (not in ProjectPaths but common convention)
    entities.extend(_scan_markdown_dir(paths.papers_dir / "summaries", slug))
    # notes/ (informal convention)
    entities.extend(_scan_markdown_dir(root / "notes", slug))

    # Tasks
    tasks = _scan_tasks(root, slug)

    # Entity counts
    counts: dict[str, int] = {}
    for e in entities:
        counts[e.type.value] = counts.get(e.type.value, 0) + 1
    counts["task"] = len(tasks)

    last_activity = _latest_mtime(root)
    staleness = None
    if last_activity:
        staleness = (datetime.now() - last_activity).days

    project = Project(
        slug=slug,
        name=meta.get("name", slug),
        path=str(root),
        summary=meta.get("summary"),
        status=meta.get("status"),
        aspects=meta.get("aspects") or [],
        tags=meta.get("tags") or [],
        entity_counts=counts,
        created=_coerce_date(meta.get("created")),
        last_modified=_coerce_date(meta.get("last_modified")),
        last_activity=last_activity,
        staleness_days=staleness,
    )

    return ProjectScan(project=project, entities=entities, tasks=tasks)
```

- [ ] **Step 4: Run test, verify pass**

Run: `cd ~/d/science-web && uv run pytest tests/test_indexer.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/indexer.py tests/test_indexer.py
git commit -m "feat: add project scanner and entity indexer"
```

---

### Task 10: DataStore protocol and filesystem implementation

**Files:**
- Create: `~/d/science-web/backend/store.py`
- Create: `~/d/science-web/tests/test_store.py`

- [ ] **Step 1: Write test for basic store operations**

```python
# tests/test_store.py
from pathlib import Path
from backend.store import FileSystemStore
from science_model import DashboardConfig
from tests.test_indexer import _make_project  # reuse fixture

def test_store_list_projects(tmp_path: Path):
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    store = FileSystemStore(cfg)
    store.rescan()
    projects = store.list_projects()
    assert len(projects) == 1
    assert projects[0].slug == "test-project"

def test_store_get_project(tmp_path: Path):
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    store = FileSystemStore(cfg)
    store.rescan()
    detail = store.get_project("test-project")
    assert detail.slug == "test-project"
    assert len(detail.hypotheses) >= 1

def test_store_list_entities_filter(tmp_path: Path):
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    store = FileSystemStore(cfg)
    store.rescan()
    hyps = store.list_entities(entity_type="hypothesis", project=None)
    assert len(hyps) == 1
    qs = store.list_entities(entity_type="question", project=None)
    assert len(qs) == 1
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Write store.py**

```python
"""DataStore — filesystem-backed implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from science_model import (
    ActivityItem,
    ConfigUpdate,
    DashboardConfig,
    Entity,
    Filters,
    GraphData,
    Project,
    ProjectDetail,
    SearchResult,
    Task,
    TaskCreate,
    TaskUpdate,
    GraphSummary,
)
from backend.indexer import ProjectScan, scan_project


class DataStore(Protocol):
    """Abstract data access interface."""

    def list_projects(self) -> list[Project]: ...
    def get_project(self, slug: str) -> ProjectDetail: ...
    def get_entity(self, project: str, entity_id: str) -> Entity: ...
    def list_entities(self, entity_type: str | None, project: str | None) -> list[Entity]: ...
    def search(self, query: str, filters: Filters) -> list[SearchResult]: ...
    def get_graph(self, project: str, lod: float) -> GraphData: ...
    def recent_activity(self, limit: int, project: str | None) -> list[ActivityItem]: ...
    def create_task(self, project: str, task: TaskCreate) -> Task: ...
    def update_task(self, project: str, task_id: str, update: TaskUpdate) -> Task: ...
    def update_entity(self, project: str, entity_id: str, update: dict) -> Entity: ...
    def rescan(self, project: str | None = None) -> None: ...
    def get_config(self) -> DashboardConfig: ...
    def update_config(self, update: ConfigUpdate) -> DashboardConfig: ...


class FileSystemStore:
    """Filesystem-backed DataStore implementation."""

    def __init__(self, config: DashboardConfig) -> None:
        self._config = config
        self._scans: dict[str, ProjectScan] = {}

    def rescan(self, project: str | None = None) -> None:
        if project:
            for p in self._config.projects:
                root = Path(p)
                if root.name == project:
                    self._scans[project] = scan_project(root)
                    return
        else:
            self._scans.clear()
            for p in self._config.projects:
                root = Path(p)
                if root.is_dir() and (root / "science.yaml").is_file():
                    scan = scan_project(root)
                    self._scans[scan.project.slug] = scan

    def list_projects(self) -> list[Project]:
        return [s.project for s in self._scans.values()]

    def get_project(self, slug: str) -> ProjectDetail:
        scan = self._scans[slug]
        p = scan.project
        hyps = [e for e in scan.entities if e.type.value == "hypothesis"][:3]
        qs = [e for e in scan.entities if e.type.value == "question"][:3]
        tasks = scan.tasks[:3]
        return ProjectDetail(
            **p.model_dump(),
            hypotheses=hyps,
            questions=qs,
            tasks=tasks,
            graph_summary=GraphSummary(node_count=0, edge_count=0, top_domains=[]),
        )

    def list_entities(self, entity_type: str | None = None, project: str | None = None) -> list[Entity]:
        entities: list[Entity] = []
        for slug, scan in self._scans.items():
            if project and slug != project:
                continue
            entities.extend(scan.entities)
        if entity_type:
            entities = [e for e in entities if e.type.value == entity_type]
        return entities

    def get_entity(self, project: str, entity_id: str) -> Entity:
        scan = self._scans[project]
        for e in scan.entities:
            if e.id == entity_id:
                return e
        msg = f"Entity {entity_id} not found in {project}"
        raise KeyError(msg)

    def search(self, query: str, filters: Filters) -> list[SearchResult]:
        # Basic in-memory search — full-text via SQLite FTS is a later task
        results: list[SearchResult] = []
        q = query.lower()
        for scan in self._scans.values():
            if filters.project and scan.project.slug != filters.project:
                continue
            for e in scan.entities:
                if filters.entity_type and e.type.value != filters.entity_type:
                    continue
                score = 0.0
                if q in e.title.lower():
                    score += 1.0
                if q in e.content_preview.lower():
                    score += 0.5
                if q in " ".join(e.tags).lower():
                    score += 0.3
                if score > 0:
                    results.append(SearchResult(entity=e, score=score, highlights=[]))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def recent_activity(self, limit: int, project: str | None = None) -> list[ActivityItem]:
        # Placeholder — full implementation after file watcher
        return []

    def create_task(self, project: str, task: TaskCreate) -> Task:
        from science_tool.paths import resolve_paths
        from science_tool.tasks import add_task

        root = Path(self._scans[project].project.path)
        paths = resolve_paths(root)
        raw = add_task(
            paths.tasks_dir,
            title=task.title,
            task_type=task.type,
            priority=task.priority,
            related=task.related,
            blocked_by=task.blocked_by,
            description=task.description,
        )
        result = Task(
            id=raw.id,
            project=project,
            title=raw.title,
            description=raw.description,
            type=raw.type,
            priority=raw.priority,
            status=raw.status,
            blocked_by=list(raw.blocked_by),
            related=list(raw.related),
            created=raw.created,
            completed=raw.completed,
        )
        # Refresh tasks in scan
        self.rescan(project=project)
        return result

    def update_task(self, project: str, task_id: str, update: TaskUpdate) -> Task:
        from science_tool.paths import resolve_paths
        from science_tool.tasks import edit_task, complete_task, defer_task, block_task

        root = Path(self._scans[project].project.path)
        paths = resolve_paths(root)
        if update.status == "done":
            raw = complete_task(paths.tasks_dir, task_id)
        elif update.status == "deferred":
            raw = defer_task(paths.tasks_dir, task_id)
        else:
            raw = edit_task(
                paths.tasks_dir,
                task_id,
                priority=update.priority,
                status=update.status,
                task_type=update.type,
                related=update.related,
            )
        self.rescan(project=project)
        return Task(
            id=raw.id,
            project=project,
            title=raw.title,
            description=raw.description,
            type=raw.type,
            priority=raw.priority,
            status=raw.status,
            blocked_by=list(raw.blocked_by),
            related=list(raw.related),
            created=raw.created,
            completed=raw.completed,
        )

    def update_entity(self, project: str, entity_id: str, update: dict) -> Entity:
        # Direct frontmatter edit — deferred to later task
        raise NotImplementedError("Entity frontmatter editing not yet implemented")

    def get_graph(self, project: str, lod: float) -> GraphData:
        # Graph loading deferred to Task 11
        return GraphData(nodes=[], edges=[], domains={}, lod=lod, total_nodes=0)

    def get_config(self) -> DashboardConfig:
        return self._config

    def update_config(self, update: ConfigUpdate) -> DashboardConfig:
        data = self._config.model_dump()
        for k, v in update.model_dump(exclude_none=True).items():
            data[k] = v
        self._config = DashboardConfig.model_validate(data)
        return self._config
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd ~/d/science-web && uv run pytest tests/test_store.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/store.py tests/test_store.py
git commit -m "feat: add FileSystemStore with DataStore protocol"
```

---

### Task 11: Graph loader and LoD subgraph computation

**Files:**
- Create: `~/d/science-web/backend/graph.py`
- Create: `~/d/science-web/tests/test_graph.py`

- [ ] **Step 1: Write test for graph loading**

```python
# tests/test_graph.py
from pathlib import Path
from backend.graph import load_graph, compute_subgraph
from science_model.graph import GraphData

MINIMAL_TRIG = """\
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix :     <http://example.org/project/> .

<http://example.org/project/graph/knowledge> {
    :concept/alpha rdf:type sci:Concept ;
        skos:prefLabel "Alpha" .
    :concept/beta rdf:type sci:Concept ;
        skos:prefLabel "Beta" .
    :concept/alpha skos:related :concept/beta .
}
"""

def test_load_graph(tmp_path: Path):
    trig = tmp_path / "graph.trig"
    trig.write_text(MINIMAL_TRIG)
    data = load_graph(trig, lod=1.0)
    assert data.total_nodes == 2
    assert len(data.nodes) == 2
    assert len(data.edges) == 1
    assert data.edges[0].predicate == "skos:related"

def test_lod_filters_nodes(tmp_path: Path):
    trig = tmp_path / "graph.trig"
    trig.write_text(MINIMAL_TRIG)
    data = load_graph(trig, lod=0.0)
    # At lod=0 only most important node(s) shown
    assert len(data.nodes) <= data.total_nodes
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Write graph.py**

```python
"""Graph loading, LoD computation, and subgraph extraction."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from rdflib import Dataset, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

from science_model.graph import GraphData, GraphEdge, GraphNode

SCI_NS = Namespace("http://example.org/science/vocab/")
SCIC_NS = Namespace("http://example.org/science/vocab/causal/")
PROJECT_NS = Namespace("http://example.org/project/")

# Map RDF types to display type names
_TYPE_MAP: dict[str, str] = {
    str(SCI_NS.Concept): "Concept",
    str(SCI_NS.Paper): "Paper",
    str(SCI_NS.Claim): "Claim",
    str(SCI_NS.Hypothesis): "Hypothesis",
    str(SCI_NS.Question): "Question",
    str(SCI_NS.Inquiry): "Inquiry",
    str(SCI_NS.Assumption): "Assumption",
    str(SCI_NS.Transformation): "Transformation",
    str(SCI_NS.Unknown): "Unknown",
    str(SCI_NS.Model): "Model",
    str(SCIC_NS.Variable): "Variable",
}

# Predicates to skip (metadata, not relationships)
_SKIP_PREDICATES = {
    str(RDF.type),
    str(SKOS.prefLabel),
    str(SKOS.definition),
    str(SKOS.note),
}


def _curie(uri: str) -> str:
    """Convert full URI to compact CURIE-like form."""
    prefixes = {
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://www.w3.org/ns/prov#": "prov:",
        "http://example.org/science/vocab/causal/": "scic:",
        "http://example.org/science/vocab/": "sci:",
        "http://purl.org/spar/cito/": "cito:",
        "https://schema.org/": "schema:",
    }
    for prefix, short in prefixes.items():
        if uri.startswith(prefix):
            return short + uri[len(prefix):]
    return uri


def load_graph(graph_path: Path, lod: float = 1.0) -> GraphData:
    """Load an RDF TriG graph and return visualization-ready data."""
    ds = Dataset()
    ds.parse(str(graph_path), format="trig")

    # Collect nodes: entities with rdf:type in the type map
    nodes_by_id: dict[str, GraphNode] = {}
    degree: Counter[str] = Counter()

    for ctx in ds.contexts():
        ctx_id = str(ctx.identifier)
        # Determine layer name
        layer = ctx_id.replace(str(PROJECT_NS), "")

        for s, p, o in ctx.triples((None, RDF.type, None)):
            s_str, o_str = str(s), str(o)
            if o_str in _TYPE_MAP and s_str not in nodes_by_id:
                label_triples = list(ctx.triples((s, SKOS.prefLabel, None)))
                label = str(label_triples[0][2]) if label_triples else s_str.split("/")[-1]

                status_triples = list(ctx.triples((s, SCI_NS.projectStatus, None)))
                status = str(status_triples[0][2]) if status_triples else None

                boundary_triples = list(ctx.triples((s, SCI_NS.boundaryRole, None)))
                boundary = None
                if boundary_triples:
                    br = str(boundary_triples[0][2])
                    boundary = "in" if "BoundaryIn" in br else "out" if "BoundaryOut" in br else None

                inquiry_name = layer if layer.startswith("inquiry/") else None

                nodes_by_id[s_str] = GraphNode(
                    id=s_str,
                    label=label,
                    type=_TYPE_MAP[o_str],
                    graph_layer=layer,
                    status=status,
                    inquiry=inquiry_name,
                    boundary_role=boundary,
                )

    # Collect edges
    edges: list[GraphEdge] = []
    for ctx in ds.contexts():
        ctx_id = str(ctx.identifier)
        layer = ctx_id.replace(str(PROJECT_NS), "")
        for s, p, o in ctx.triples((None, None, None)):
            s_str, p_str, o_str = str(s), str(p), str(o)
            if p_str in _SKIP_PREDICATES:
                continue
            if s_str in nodes_by_id and o_str in nodes_by_id:
                edges.append(GraphEdge(
                    source=s_str,
                    target=o_str,
                    predicate=_curie(p_str),
                    graph_layer=layer,
                ))
                degree[s_str] += 1
                degree[o_str] += 1

    # Compute importance scores
    total = len(nodes_by_id)
    max_degree = max(degree.values()) if degree else 1
    for nid, node in nodes_by_id.items():
        node.importance = degree.get(nid, 0) / max_degree

    # Apply LoD filter
    all_nodes = list(nodes_by_id.values())
    if total == 0 or lod >= 1.0:
        filtered_nodes = all_nodes
    else:
        k = max(1, math.ceil(lod * total))
        sorted_nodes = sorted(all_nodes, key=lambda n: n.importance, reverse=True)
        filtered_nodes = sorted_nodes[:k]

    # Filter edges to only include those between visible nodes
    visible_ids = {n.id for n in filtered_nodes}
    filtered_edges = [e for e in edges if e.source in visible_ids and e.target in visible_ids]

    return GraphData(
        nodes=filtered_nodes,
        edges=filtered_edges,
        domains={},
        lod=lod,
        total_nodes=total,
    )
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Wire into FileSystemStore.get_graph**

Modify `backend/store.py`: replace the placeholder `get_graph` with:

```python
def get_graph(self, project: str, lod: float) -> GraphData:
    from backend.graph import load_graph
    root = Path(self._scans[project].project.path)
    graph_path = root / "knowledge" / "graph.trig"
    if not graph_path.is_file():
        return GraphData(nodes=[], edges=[], domains={}, lod=lod, total_nodes=0)
    return load_graph(graph_path, lod=lod)
```

- [ ] **Step 6: Commit**

```bash
git add backend/graph.py tests/test_graph.py backend/store.py
git commit -m "feat: add graph loader with LoD subgraph computation"
```

---

## Chunk 3: science-web Backend — API Routes

### Task 12: Projects and entities API routes

**Files:**
- Create: `~/d/science-web/backend/routes/__init__.py`
- Create: `~/d/science-web/backend/routes/projects.py`
- Create: `~/d/science-web/backend/routes/entities.py`
- Create: `~/d/science-web/tests/test_api_projects.py`
- Modify: `~/d/science-web/backend/app.py`

- [ ] **Step 1: Write API test for projects**

```python
# tests/test_api_projects.py
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app
from science_model import DashboardConfig
from tests.test_indexer import _make_project

def _test_client(tmp_path: Path) -> TestClient:
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    app = create_app(cfg)
    return TestClient(app)

def test_list_projects(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["slug"] == "test-project"

def test_get_project_detail(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/projects/test-project")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "test-project"
    assert "hypotheses" in data

def test_get_project_not_found(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/projects/nonexistent")
    assert r.status_code == 404

def test_list_entities_filtered(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/entities?entity_type=hypothesis")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["type"] == "hypothesis"

def test_search(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/search?q=test")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Refactor app.py to use factory function**

```python
# backend/app.py
"""Science Dashboard — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from science_model import DashboardConfig
from backend.store import FileSystemStore


def create_app(config: DashboardConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Science Dashboard", version="0.1.0")

    if config is None:
        from backend.config import load_config
        config = load_config()

    store = FileSystemStore(config)
    store.rescan()
    app.state.store = store

    # Register routes
    from backend.routes.projects import router as projects_router
    from backend.routes.entities import router as entities_router
    app.include_router(projects_router, prefix="/api")
    app.include_router(entities_router, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Write routes/projects.py**

```python
# backend/routes/projects.py
"""Project API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["projects"])


@router.get("/projects")
async def list_projects(request: Request):
    store = request.app.state.store
    return store.list_projects()


@router.get("/projects/{slug}")
async def get_project(slug: str, request: Request):
    store = request.app.state.store
    try:
        return store.get_project(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project {slug} not found")


@router.get("/projects/{slug}/graph")
async def get_graph(slug: str, request: Request, lod: float = 1.0):
    store = request.app.state.store
    try:
        return store.get_graph(slug, lod)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project {slug} not found")


@router.post("/projects/rescan")
async def rescan(request: Request, project: str | None = None):
    store = request.app.state.store
    store.rescan(project=project)
    return {"status": "ok"}
```

- [ ] **Step 5: Write routes/entities.py**

```python
# backend/routes/entities.py
"""Entity and search API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from science_model import Filters

router = APIRouter(tags=["entities"])


@router.get("/entities")
async def list_entities(
    request: Request,
    entity_type: str | None = None,
    project: str | None = None,
):
    store = request.app.state.store
    return store.list_entities(entity_type=entity_type, project=project)


@router.get("/entities/{entity_id:path}")
async def get_entity(entity_id: str, request: Request, project: str | None = None):
    store = request.app.state.store
    # Search across projects if no project specified
    if project:
        try:
            return store.get_entity(project, entity_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    # Cross-project search
    for p in store.list_projects():
        try:
            return store.get_entity(p.slug, entity_id)
        except KeyError:
            continue
    raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")


@router.get("/hypotheses")
async def list_hypotheses(request: Request, project: str | None = None):
    return request.app.state.store.list_entities(entity_type="hypothesis", project=project)


@router.get("/questions")
async def list_questions(request: Request, project: str | None = None):
    return request.app.state.store.list_entities(entity_type="question", project=project)


@router.get("/search")
async def search(request: Request, q: str, project: str | None = None, type: str | None = None):
    store = request.app.state.store
    filters = Filters(project=project, entity_type=type)
    return store.search(q, filters)
```

- [ ] **Step 6: Create routes/__init__.py**

Empty file.

- [ ] **Step 7: Run tests, verify pass**

Run: `cd ~/d/science-web && uv run pytest tests/test_api_projects.py -v`

- [ ] **Step 8: Commit**

```bash
git add backend/ tests/test_api_projects.py
git commit -m "feat: add projects and entities API routes"
```

---

### Task 13: Tasks API routes

**Files:**
- Create: `~/d/science-web/backend/routes/tasks.py`
- Create: `~/d/science-web/tests/test_api_tasks.py`
- Modify: `~/d/science-web/backend/app.py` (register router)

- [ ] **Step 1: Write API test for tasks**

```python
# tests/test_api_tasks.py
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app
from science_model import DashboardConfig
from tests.test_indexer import _make_project

def _test_client(tmp_path: Path) -> TestClient:
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    app = create_app(cfg)
    return TestClient(app)

def test_list_tasks(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.get("/api/tasks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1

def test_create_task(tmp_path: Path):
    client = _test_client(tmp_path)
    r = client.post("/api/projects/test-project/tasks", json={
        "title": "New test task",
        "priority": "P1",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "New test task"
    assert data["status"] == "proposed"
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Write routes/tasks.py**

```python
# backend/routes/tasks.py
"""Task API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from science_model import TaskCreate, TaskUpdate

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
async def list_all_tasks(request: Request, project: str | None = None):
    store = request.app.state.store
    tasks = []
    for p in store.list_projects():
        if project and p.slug != project:
            continue
        scan = store._scans.get(p.slug)
        if scan:
            tasks.extend(scan.tasks)
    return tasks


@router.post("/projects/{slug}/tasks")
async def create_task(slug: str, task: TaskCreate, request: Request):
    store = request.app.state.store
    try:
        return store.create_task(slug, task)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project {slug} not found")


@router.patch("/projects/{slug}/tasks/{task_id}")
async def update_task(slug: str, task_id: str, update: TaskUpdate, request: Request):
    store = request.app.state.store
    try:
        return store.update_task(slug, task_id, update)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found in {slug}")
```

- [ ] **Step 4: Register router in app.py**

Add to `create_app`:
```python
from backend.routes.tasks import router as tasks_router
app.include_router(tasks_router, prefix="/api")
```

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```bash
git add backend/routes/tasks.py tests/test_api_tasks.py backend/app.py
git commit -m "feat: add tasks API routes with create/update"
```

---

### Task 14: File watcher and WebSocket

**Files:**
- Create: `~/d/science-web/backend/watcher.py`
- Create: `~/d/science-web/backend/routes/ws.py`
- Modify: `~/d/science-web/backend/app.py` (lifecycle events)

- [ ] **Step 1: Write watcher.py**

```python
# backend/watcher.py
"""File watcher — monitors project directories for changes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from watchfiles import awatch, Change

logger = logging.getLogger(__name__)


async def watch_projects(
    project_paths: list[str],
    on_change: Callable[[str, str, str], None],
) -> None:
    """Watch project directories and call on_change(project_slug, change_type, path)."""
    path_to_slug: dict[str, str] = {}
    watch_paths: list[str] = []
    for p in project_paths:
        root = Path(p)
        slug = root.name
        path_to_slug[str(root)] = slug
        watch_paths.append(str(root))

    if not watch_paths:
        return

    async for changes in awatch(*watch_paths):
        for change_type, changed_path in changes:
            # Determine which project this belongs to
            for root_str, slug in path_to_slug.items():
                if changed_path.startswith(root_str):
                    rel = changed_path[len(root_str) + 1:]
                    change_name = {
                        Change.added: "created",
                        Change.modified: "modified",
                        Change.deleted: "deleted",
                    }.get(change_type, "modified")
                    on_change(slug, change_name, rel)
                    break
```

- [ ] **Step 2: Write routes/ws.py**

```python
# backend/routes/ws.py
"""WebSocket endpoint for live updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple broadcast hub
_connections: set[WebSocket] = set()


async def broadcast(event: str, project: str, path: str | None = None, data: dict | None = None) -> None:
    """Send event to all connected WebSocket clients."""
    msg = json.dumps({"event": event, "project": project, "path": path, "data": data})
    disconnected = set()
    for ws in _connections:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.add(ws)
    _connections -= disconnected


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        _connections.discard(websocket)
```

- [ ] **Step 3: Wire watcher + WS into app lifecycle**

Update `backend/app.py` create_app to add startup/shutdown:

```python
from backend.routes.ws import router as ws_router, broadcast
from backend.watcher import watch_projects

app.include_router(ws_router)

@app.on_event("startup")
async def startup():
    import asyncio

    async def on_change(slug: str, change_type: str, path: str):
        store.rescan(project=slug)
        await broadcast("file_changed", slug, path)

    watcher_task = asyncio.create_task(
        watch_projects(config.projects, on_change)
    )
    app.state.watcher_task = watcher_task

@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "watcher_task", None)
    if task:
        task.cancel()
```

- [ ] **Step 4: Commit**

```bash
git add backend/watcher.py backend/routes/ws.py backend/app.py
git commit -m "feat: add file watcher and WebSocket broadcast"
```

---

## Chunk 4: science-web Frontend — Scaffold and Dashboard

### Task 15: React + Vite + TypeScript scaffold

**Files:**
- Create: `~/d/science-web/frontend/` (via Vite scaffolding)

- [ ] **Step 1: Scaffold with Vite**

```bash
cd ~/d/science-web && npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: Install dependencies**

```bash
cd ~/d/science-web/frontend
npm install react-router-dom zustand tailwindcss @tailwindcss/vite
npm install react-force-graph-2d react-force-graph-3d three @types/three
npm install cmdk
```

- [ ] **Step 3: Configure Vite proxy**

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 4: Configure Tailwind**

```css
/* src/index.css */
@import "tailwindcss";
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd ~/d/science-web/frontend && npm run dev
# Verify http://localhost:5173 loads
```

- [ ] **Step 6: Commit**

```bash
cd ~/d/science-web && git add frontend/ && git commit -m "feat: scaffold React + Vite + TypeScript frontend"
```

---

### Task 16: TypeScript types and API client

**Files:**
- Create: `~/d/science-web/frontend/src/types/index.ts`
- Create: `~/d/science-web/frontend/src/api/client.ts`

- [ ] **Step 1: Write TypeScript types (mirroring science-model)**

```typescript
// src/types/index.ts
export interface Project {
  slug: string
  name: string
  path: string
  summary: string | null
  status: string | null
  aspects: string[]
  tags: string[]
  entity_counts: Record<string, number>
  created: string | null
  last_modified: string | null
  last_activity: string | null
  staleness_days: number | null
}

export interface ProjectDetail extends Project {
  hypotheses: Entity[]
  questions: Entity[]
  tasks: Task[]
  graph_summary: GraphSummary
}

export interface Entity {
  id: string
  type: string
  title: string
  status: string | null
  project: string
  domain: string | null
  tags: string[]
  ontology_terms: string[]
  created: string | null
  updated: string | null
  related: string[]
  source_refs: string[]
  content_preview: string
  file_path: string
  maturity: string | null
  confidence: number | null
  datasets: string[] | null
}

export interface Task {
  id: string
  project: string
  title: string
  description: string
  type: string
  priority: string
  status: string
  blocked_by: string[]
  related: string[]
  created: string
  completed: string | null
}

export interface GraphNode {
  id: string
  label: string
  type: string
  domain: string | null
  importance: number
  status: string | null
  maturity: string | null
  confidence: number | null
  updated: string | null
  graph_layer: string
  inquiry: string | null
  boundary_role: string | null
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  graph_layer: string
  provenance: string | null
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  domains: Record<string, string>
  lod: number
  total_nodes: number
}

export interface GraphSummary {
  node_count: number
  edge_count: number
  top_domains: string[]
}

export interface SearchResult {
  entity: Entity
  score: number
  highlights: string[]
}

export interface ActivityItem {
  project: string
  entity_id: string | null
  entity_type: string | null
  title: string
  action: string
  timestamp: string
  detail: string | null
}
```

- [ ] **Step 2: Write API client**

```typescript
// src/api/client.ts
const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

import type { Project, ProjectDetail, Entity, Task, GraphData, SearchResult } from '../types'

export const api = {
  projects: {
    list: () => get<Project[]>('/projects'),
    get: (slug: string) => get<ProjectDetail>(`/projects/${slug}`),
    graph: (slug: string, lod = 1.0) => get<GraphData>(`/projects/${slug}/graph?lod=${lod}`),
    rescan: () => post('/projects/rescan'),
  },
  entities: {
    list: (params?: { entity_type?: string; project?: string }) => {
      const qs = new URLSearchParams()
      if (params?.entity_type) qs.set('entity_type', params.entity_type)
      if (params?.project) qs.set('project', params.project)
      return get<Entity[]>(`/entities?${qs}`)
    },
    get: (id: string) => get<Entity>(`/entities/${id}`),
  },
  tasks: {
    list: () => get<Task[]>('/tasks'),
    create: (slug: string, task: { title: string; priority?: string }) =>
      post<Task>(`/projects/${slug}/tasks`, task),
    update: (slug: string, id: string, update: Partial<Task>) =>
      patch<Task>(`/projects/${slug}/tasks/${id}`, update),
  },
  search: (q: string) => get<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/ frontend/src/api/
git commit -m "feat: add TypeScript types and API client"
```

---

### Task 17: Zustand stores and routing skeleton

**Files:**
- Create: `~/d/science-web/frontend/src/stores/appStore.ts`
- Create: `~/d/science-web/frontend/src/hooks/useKeyboard.ts`
- Create: `~/d/science-web/frontend/src/hooks/useWebSocket.ts`
- Modify: `~/d/science-web/frontend/src/App.tsx`

- [ ] **Step 1: Write app store**

```typescript
// src/stores/appStore.ts
import { create } from 'zustand'

export type ViewMode = 'projects' | 'entities' | 'activity'
export type Lens = 'domain' | 'activity' | 'status' | 'uncertainty'
export type GraphDim = '2d' | '3d'

interface AppState {
  view: ViewMode
  lens: Lens
  graphDim: GraphDim
  lod: number
  setView: (v: ViewMode) => void
  setLens: (l: Lens) => void
  setGraphDim: (d: GraphDim) => void
  setLod: (l: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  view: 'projects',
  lens: 'domain',
  graphDim: '2d',
  lod: 0.5,
  setView: (view) => set({ view }),
  setLens: (lens) => set({ lens }),
  setGraphDim: (graphDim) => set({ graphDim }),
  setLod: (lod) => set({ lod }),
}))
```

- [ ] **Step 2: Write keyboard hook**

```typescript
// src/hooks/useKeyboard.ts
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'

export function useKeyboard() {
  const navigate = useNavigate()
  const { setView, setLens, setGraphDim } = useAppStore()
  const commaPressed = useRef(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return

      if (e.key === ',') { commaPressed.current = true; return }
      if (commaPressed.current) {
        commaPressed.current = false
        if (e.key === 'd') setLens('domain')
        if (e.key === 'a') setLens('activity')
        if (e.key === 's') setLens('status')
        if (e.key === 'u') setLens('uncertainty')
        return
      }
      if (e.key === 'p') setView('projects')
      if (e.key === 'e') setView('entities')
      if (e.key === '2') setGraphDim('2d')
      if (e.key === '3') setGraphDim('3d')
      if (e.key === '/') { e.preventDefault(); document.getElementById('search-input')?.focus() }
      if (e.key === 'Escape') navigate(-1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate, setView, setLens, setGraphDim])
}
```

- [ ] **Step 3: Write WebSocket hook**

```typescript
// src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react'

interface WsMessage {
  event: string
  project: string
  path?: string
  data?: unknown
}

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const ws = new WebSocket(`ws://${window.location.host}/api/ws`)
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data) as WsMessage
      onMessage(msg)
    }
    ws.onclose = () => setTimeout(connect, 3000)
    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])
}
```

- [ ] **Step 4: Write App.tsx with routing**

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useKeyboard } from './hooks/useKeyboard'

function Home() { return <div className="p-4 text-neutral-200">Home — projects / entities / activity</div> }
function ProjectDashboard() { return <div className="p-4 text-neutral-200">Project Dashboard</div> }
function ProjectGraph() { return <div className="p-4 text-neutral-200">Graph Explorer</div> }
function EntityDetail() { return <div className="p-4 text-neutral-200">Entity Detail</div> }
function SearchResults() { return <div className="p-4 text-neutral-200">Search Results</div> }

function AppShell() {
  useKeyboard()
  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100">
      <header className="h-10 flex items-center px-4 border-b border-neutral-700 text-sm">
        <span className="font-semibold">Science Dashboard</span>
        <input id="search-input" placeholder="Search (/)" className="ml-4 bg-neutral-800 px-2 py-1 rounded text-sm w-64" />
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects/:slug" element={<ProjectDashboard />} />
        <Route path="/projects/:slug/graph" element={<ProjectGraph />} />
        <Route path="/entities/:id" element={<EntityDetail />} />
        <Route path="/search" element={<SearchResults />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Verify app renders**

```bash
cd ~/d/science-web && make dev
# Open http://localhost:5173 — should show "Home" placeholder
# Press 'p' — should stay on home (no navigation yet, just state change)
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: add routing, zustand store, keyboard/websocket hooks"
```

---

### Task 18: Home page with three views

**Files:**
- Create: `~/d/science-web/frontend/src/routes/Home.tsx`
- Create: `~/d/science-web/frontend/src/components/Dashboard/ProjectCard.tsx`
- Modify: `~/d/science-web/frontend/src/App.tsx`

- [ ] **Step 1: Write Home.tsx**

```tsx
// src/routes/Home.tsx
import { useEffect, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import { api } from '../api/client'
import type { Project, Entity, Task } from '../types'
import { ProjectCard } from '../components/Dashboard/ProjectCard'

export function Home() {
  const { view } = useAppStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [entities, setEntities] = useState<Entity[]>([])
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    api.projects.list().then(setProjects)
    api.entities.list().then(setEntities)
    api.tasks.list().then(setTasks)
  }, [])

  if (view === 'projects') {
    return (
      <div className="p-6 grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => <ProjectCard key={p.slug} project={p} />)}
      </div>
    )
  }

  if (view === 'entities') {
    return (
      <div className="p-6">
        <h2 className="text-lg font-semibold mb-4">All Entities</h2>
        <div className="space-y-2">
          {entities.slice(0, 50).map((e) => (
            <a key={`${e.project}:${e.id}`} href={`/entities/${encodeURIComponent(e.id)}`}
               className="block p-3 bg-neutral-800 rounded hover:bg-neutral-700">
              <span className="text-xs text-neutral-400 mr-2">{e.type}</span>
              <span>{e.title}</span>
              <span className="text-xs text-neutral-500 ml-2">{e.project}</span>
            </a>
          ))}
        </div>
      </div>
    )
  }

  // Activity view — placeholder, will be enriched with ActivityItem
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
      <p className="text-neutral-400">Activity feed — coming soon.</p>
    </div>
  )
}
```

- [ ] **Step 2: Write ProjectCard.tsx**

```tsx
// src/components/Dashboard/ProjectCard.tsx
import type { Project } from '../../types'

export function ProjectCard({ project }: { project: Project }) {
  const total = Object.values(project.entity_counts).reduce((a, b) => a + b, 0)
  return (
    <a href={`/projects/${project.slug}`}
       className="block p-4 bg-neutral-800 rounded-lg border border-neutral-700 hover:border-neutral-500 transition">
      <div className="flex justify-between items-start">
        <h3 className="font-semibold">{project.name}</h3>
        {project.status && (
          <span className="text-xs px-2 py-0.5 rounded bg-neutral-700">{project.status}</span>
        )}
      </div>
      {project.summary && (
        <p className="text-sm text-neutral-400 mt-1 line-clamp-2">{project.summary}</p>
      )}
      <div className="flex gap-3 mt-3 text-xs text-neutral-500">
        <span>{total} entities</span>
        {project.staleness_days !== null && (
          <span>{project.staleness_days === 0 ? 'today' : `${project.staleness_days}d ago`}</span>
        )}
        {project.aspects.map((a) => (
          <span key={a} className="px-1.5 py-0.5 bg-neutral-700 rounded">{a}</span>
        ))}
      </div>
    </a>
  )
}
```

- [ ] **Step 3: Wire Home into App.tsx routes**

Replace `function Home()` placeholder with import:
```tsx
import { Home } from './routes/Home'
// Replace <Route path="/" element={<Home />} /> to use imported component
```

- [ ] **Step 4: Verify all three views render**

Start `make dev`, open browser, press `p` / `e` to toggle views.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add home page with projects/entities/activity views"
```

---

### Task 19: Project dashboard page

**Files:**
- Create: `~/d/science-web/frontend/src/routes/ProjectDashboard.tsx`
- Modify: `~/d/science-web/frontend/src/App.tsx`

- [ ] **Step 1: Write ProjectDashboard.tsx**

```tsx
// src/routes/ProjectDashboard.tsx
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ProjectDetail } from '../types'

export function ProjectDashboard() {
  const { slug } = useParams<{ slug: string }>()
  const [project, setProject] = useState<ProjectDetail | null>(null)

  useEffect(() => {
    if (slug) api.projects.get(slug).then(setProject)
  }, [slug])

  if (!project) return <div className="p-6 text-neutral-400">Loading...</div>

  return (
    <div className="p-6">
      <div className="flex items-baseline gap-3 mb-6">
        <h1 className="text-xl font-bold">{project.name}</h1>
        {project.status && <span className="text-sm text-neutral-400">{project.status}</span>}
        <Link to={`/projects/${slug}/graph`} className="ml-auto text-sm text-blue-400 hover:underline">
          Open Graph
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Hypotheses card */}
        <div className="bg-neutral-800 rounded-lg p-4 border border-neutral-700">
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Hypotheses</h2>
          {project.hypotheses.length === 0 && <p className="text-sm text-neutral-500">None</p>}
          {project.hypotheses.map((h) => (
            <div key={h.id} className="mb-2">
              <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-700 mr-2">{h.status}</span>
              <span className="text-sm">{h.title}</span>
            </div>
          ))}
        </div>

        {/* Questions card */}
        <div className="bg-neutral-800 rounded-lg p-4 border border-neutral-700">
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Open Questions</h2>
          {project.questions.length === 0 && <p className="text-sm text-neutral-500">None</p>}
          {project.questions.map((q) => (
            <div key={q.id} className="mb-2">
              <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-700 mr-2">{q.status}</span>
              <span className="text-sm">{q.title}</span>
            </div>
          ))}
        </div>

        {/* Tasks card */}
        <div className="bg-neutral-800 rounded-lg p-4 border border-neutral-700">
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Active Tasks</h2>
          {project.tasks.length === 0 && <p className="text-sm text-neutral-500">None</p>}
          {project.tasks.map((t) => (
            <div key={t.id} className="mb-2 flex items-baseline gap-2">
              <span className="text-xs text-neutral-500">{t.id}</span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-700">{t.priority}</span>
              <span className="text-sm">{t.title}</span>
              {t.blocked_by.length > 0 && <span className="text-xs text-red-400">blocked</span>}
            </div>
          ))}
        </div>

        {/* KG minimap placeholder */}
        <div className="bg-neutral-800 rounded-lg p-4 border border-neutral-700">
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Knowledge Graph</h2>
          <Link to={`/projects/${slug}/graph`} className="text-sm text-blue-400 hover:underline">
            {project.graph_summary.node_count} nodes, {project.graph_summary.edge_count} edges — Open explorer
          </Link>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire into App.tsx**

- [ ] **Step 3: Verify renders with real data**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/ProjectDashboard.tsx frontend/src/App.tsx
git commit -m "feat: add project dashboard with hypothesis/question/task cards"
```

---

## Chunk 5: science-web Frontend — Graph Explorer

### Task 20: Graph Explorer component (2D)

**Files:**
- Create: `~/d/science-web/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Create: `~/d/science-web/frontend/src/components/GraphExplorer/nodeShapes.ts`
- Create: `~/d/science-web/frontend/src/components/GraphExplorer/LodSlider.tsx`
- Create: `~/d/science-web/frontend/src/routes/ProjectGraph.tsx`

- [ ] **Step 1: Write nodeShapes.ts — 2D canvas shape rendering**

```typescript
// src/components/GraphExplorer/nodeShapes.ts
import type { GraphNode } from '../../types'

const SHAPE_MAP: Record<string, (ctx: CanvasRenderingContext2D, x: number, y: number, r: number) => void> = {
  Concept: (ctx, x, y, r) => { ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill(); ctx.stroke() },
  Hypothesis: (ctx, x, y, r) => {
    ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y + r); ctx.lineTo(x - r, y + r); ctx.closePath(); ctx.fill(); ctx.stroke()
  },
  Question: (ctx, x, y, r) => {
    ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath(); ctx.fill(); ctx.stroke()
  },
  Paper: (ctx, x, y, r) => { ctx.fillRect(x - r, y - r, 2 * r, 2 * r); ctx.strokeRect(x - r, y - r, 2 * r, 2 * r) },
  Claim: (ctx, x, y, r) => {
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 2
      const px = x + r * Math.cos(a), py = y + r * Math.sin(a)
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
    }
    ctx.closePath(); ctx.fill(); ctx.stroke()
  },
  Inquiry: (ctx, x, y, r) => {
    ctx.beginPath()
    for (let i = 0; i < 5; i++) {
      const outer = (Math.PI * 2 / 5) * i - Math.PI / 2
      const inner = outer + Math.PI / 5
      ctx.lineTo(x + r * Math.cos(outer), y + r * Math.sin(outer))
      ctx.lineTo(x + r * 0.5 * Math.cos(inner), y + r * 0.5 * Math.sin(inner))
    }
    ctx.closePath(); ctx.fill(); ctx.stroke()
  },
}

const DEFAULT_SHAPE = SHAPE_MAP.Concept

export function drawNode(ctx: CanvasRenderingContext2D, node: GraphNode, x: number, y: number, r: number, color: string) {
  ctx.fillStyle = color
  ctx.strokeStyle = '#555'
  ctx.lineWidth = 1
  const draw = SHAPE_MAP[node.type] || DEFAULT_SHAPE
  draw(ctx, x, y, r)
  // Label
  ctx.fillStyle = '#ccc'
  ctx.font = `${Math.max(8, r * 0.8)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.fillText(node.label, x, y + r + 10, 80)
}
```

- [ ] **Step 2: Write LodSlider.tsx**

```tsx
// src/components/GraphExplorer/LodSlider.tsx
import { useAppStore } from '../../stores/appStore'

export function LodSlider() {
  const { lod, setLod } = useAppStore()
  return (
    <div className="flex items-center gap-2 text-xs text-neutral-400">
      <span>LoD</span>
      <input type="range" min={0.05} max={1} step={0.05} value={lod}
        onChange={(e) => setLod(parseFloat(e.target.value))}
        className="w-32" />
      <span>{Math.round(lod * 100)}%</span>
    </div>
  )
}
```

- [ ] **Step 3: Write GraphExplorer.tsx**

```tsx
// src/components/GraphExplorer/GraphExplorer.tsx
import { useEffect, useState, useCallback, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { api } from '../../api/client'
import { useAppStore } from '../../stores/appStore'
import { drawNode } from './nodeShapes'
import { LodSlider } from './LodSlider'
import type { GraphData, GraphNode } from '../../types'

interface Props {
  projectSlug: string
}

export function GraphExplorer({ projectSlug }: Props) {
  const { lod, lens } = useAppStore()
  const [data, setData] = useState<GraphData | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  useEffect(() => {
    api.projects.graph(projectSlug, lod).then(setData)
  }, [projectSlug, lod])

  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D) => {
    const r = 4 + (node.importance || 0) * 8
    const color = node.domain && data?.domains[node.domain] ? data.domains[node.domain] : '#888'
    drawNode(ctx, node, node.x, node.y, r, color)
  }, [data, lens])

  if (!data) return <div className="p-4 text-neutral-400">Loading graph...</div>

  const graphData = {
    nodes: data.nodes.map((n) => ({ ...n })),
    links: data.edges.map((e) => ({ source: e.source, target: e.target, predicate: e.predicate })),
  }

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-2 left-2 z-10 flex gap-4 items-center bg-neutral-900/80 px-3 py-2 rounded">
        <LodSlider />
        <span className="text-xs text-neutral-500">{data.nodes.length}/{data.total_nodes} nodes</span>
      </div>
      <ForceGraph2D
        graphData={graphData}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        onNodeClick={(node: any) => setSelected(node)}
        linkDirectionalArrowLength={4}
        linkColor={() => '#444'}
        backgroundColor="#111"
        width={window.innerWidth}
        height={window.innerHeight - 40}
      />
      {selected && (
        <div className="absolute top-2 right-2 w-72 bg-neutral-800 border border-neutral-700 rounded-lg p-4 z-10">
          <h3 className="font-semibold">{selected.label}</h3>
          <p className="text-xs text-neutral-400 mt-1">{selected.type} · {selected.graph_layer}</p>
          {selected.status && <p className="text-xs mt-1">Status: {selected.status}</p>}
          <button onClick={() => setSelected(null)} className="text-xs text-neutral-500 mt-2 hover:text-neutral-300">Close</button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Write ProjectGraph.tsx route**

```tsx
// src/routes/ProjectGraph.tsx
import { useParams } from 'react-router-dom'
import { GraphExplorer } from '../components/GraphExplorer/GraphExplorer'

export function ProjectGraph() {
  const { slug } = useParams<{ slug: string }>()
  if (!slug) return null
  return <GraphExplorer projectSlug={slug} />
}
```

- [ ] **Step 5: Wire into App.tsx**

- [ ] **Step 6: Test with real project data**

Start backend with config pointing to real projects, open `/projects/seq-feats/graph`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/GraphExplorer/ frontend/src/routes/ProjectGraph.tsx frontend/src/App.tsx
git commit -m "feat: add 2D graph explorer with LoD slider and node shapes"
```

---

### Task 21: 3D graph mode toggle

**Files:**
- Create: `~/d/science-web/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`
- Modify: `~/d/science-web/frontend/src/routes/ProjectGraph.tsx`

- [ ] **Step 1: Write GraphExplorer3D.tsx**

```tsx
// src/components/GraphExplorer/GraphExplorer3D.tsx
import { useEffect, useState, useCallback } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import { api } from '../../api/client'
import { useAppStore } from '../../stores/appStore'
import { LodSlider } from './LodSlider'
import type { GraphData, GraphNode } from '../../types'

const GEOMETRY_MAP: Record<string, THREE.BufferGeometry> = {
  Concept: new THREE.SphereGeometry(5),
  Hypothesis: new THREE.TetrahedronGeometry(6),
  Question: new THREE.OctahedronGeometry(5),
  Paper: new THREE.BoxGeometry(8, 8, 8),
  Claim: new THREE.DodecahedronGeometry(5),
  Inquiry: new THREE.IcosahedronGeometry(5),
  Model: new THREE.TorusKnotGeometry(3, 1, 32, 8),
  Assumption: new THREE.ConeGeometry(4, 8, 5),
  Transformation: new THREE.TorusGeometry(4, 1.5),
  Variable: new THREE.SphereGeometry(3),
}

const DEFAULT_GEOM = new THREE.SphereGeometry(4)

interface Props {
  projectSlug: string
}

export function GraphExplorer3D({ projectSlug }: Props) {
  const { lod } = useAppStore()
  const [data, setData] = useState<GraphData | null>(null)

  useEffect(() => {
    api.projects.graph(projectSlug, lod).then(setData)
  }, [projectSlug, lod])

  const nodeThreeObject = useCallback((node: any) => {
    const geom = GEOMETRY_MAP[node.type] || DEFAULT_GEOM
    const color = node.domain && data?.domains[node.domain] ? data.domains[node.domain] : '#888'
    const mat = new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.9 })
    return new THREE.Mesh(geom, mat)
  }, [data])

  if (!data) return <div className="p-4 text-neutral-400">Loading graph...</div>

  const graphData = {
    nodes: data.nodes.map((n) => ({ ...n })),
    links: data.edges.map((e) => ({ source: e.source, target: e.target })),
  }

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-2 left-2 z-10 flex gap-4 items-center bg-neutral-900/80 px-3 py-2 rounded">
        <LodSlider />
        <span className="text-xs text-neutral-500">{data.nodes.length}/{data.total_nodes} nodes</span>
      </div>
      <ForceGraph3D
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        linkColor={() => '#444'}
        backgroundColor="#111"
        width={window.innerWidth}
        height={window.innerHeight - 40}
      />
    </div>
  )
}
```

- [ ] **Step 2: Update ProjectGraph.tsx to toggle 2D/3D**

```tsx
// src/routes/ProjectGraph.tsx
import { useParams } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'
import { GraphExplorer } from '../components/GraphExplorer/GraphExplorer'
import { GraphExplorer3D } from '../components/GraphExplorer/GraphExplorer3D'

export function ProjectGraph() {
  const { slug } = useParams<{ slug: string }>()
  const { graphDim } = useAppStore()
  if (!slug) return null
  return graphDim === '3d' ? <GraphExplorer3D projectSlug={slug} /> : <GraphExplorer projectSlug={slug} />
}
```

- [ ] **Step 3: Test 2D/3D toggle with `2` and `3` keys**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/GraphExplorer/ frontend/src/routes/ProjectGraph.tsx
git commit -m "feat: add 3D graph explorer with Three.js geometries and 2D/3D toggle"
```

---

## Summary

| Chunk | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-6 | `science-model` package: entity types, project/task/graph models, frontmatter parser, science-tool wiring |
| 2 | 7-11 | `science-web` backend: scaffold, config, indexer, FileSystemStore, graph loader + LoD |
| 3 | 12-14 | API routes: projects, entities, tasks, search, file watcher, WebSocket |
| 4 | 15-19 | Frontend scaffold: React/Vite/TS, types, API client, stores, routing, home page, project dashboard |
| 5 | 20-21 | Graph explorer: 2D canvas shapes, 3D Three.js geometries, LoD slider, lens/mode toggle |

**Follow-up tasks (not in this plan, tracked for future iteration):**
- Domain color assignment pipeline (palette system, domain extraction)
- Lens color remapping (activity heatmap, status colors, uncertainty)
- Graph right-click context menu (create task, find across projects)
- Entity detail page
- Full-text search with SQLite FTS
- Activity feed from file watcher events
- Entity frontmatter write-back
- GraphSummary computation from actual graph data
- Quality monitoring (refs.py integration)
- KG minimap on project dashboard (small embedded force graph)
- Graph layer toggle (knowledge/causal/provenance/inquiry filtering)
- Inquiry subgraph visualization (boundary node pinning)

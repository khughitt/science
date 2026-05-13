# Science Entity Inventory And Dashboard Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this plan.

**Goal:** Move science project entity discovery, identity validation, DAG finding candidates, workflow-run records, and migration reporting into `~/d/science/`, then update the dashboard to consume the Science inventory contract instead of scanning project files directly.

**Architecture:** Add a versioned `science_model.contracts.inventory_v1` payload as the shared contract. `science-tool` builds and validates that payload from existing storage adapters, new workflow-run and DAG inventory helpers, identity health checks, aliases, graph addresses, warnings, and watch paths. The dashboard imports `science_tool.entities_inventory.build_inventory` directly, validates the returned payload with the imported contract, converts it into the existing dashboard project state, caches dashboard rebuilds by `content_hash` and `audit_hash`, and watches only Science-declared paths.

**Tech Stack:** Python 3.12, Pydantic, Click, PyYAML, pytest, FastAPI backend, existing dashboard store/indexer models.

The dashboard already declares editable dependencies on `science` and `science-model` in `~/d/dashboard/pyproject.toml`, so v1 uses in-process imports rather than a subprocess transport. A future daemon or CLI transport should be justified by a real process-isolation requirement before replacing the direct import path.

---

## Repositories

Primary implementation spans two local repositories:

- `~/d/science/science`
- `~/d/dashboard`

Keep commits separate by repository. Do not vendor Science code into the dashboard.

---

## Current Touch Points

Science:

- `~/d/science/science/model/src/science_model/entities.py`
- `~/d/science/science/src/science_tool/cli.py`
- `~/d/science/science/src/science_tool/graph/sources.py`
- `~/d/science/science/src/science_tool/graph/health.py`
- `~/d/science/science/src/science_tool/graph/storage_adapters/`
- `~/d/science/science/src/science_tool/dag/`
- `~/d/science/science/tests/`

Dashboard:

- `~/d/dashboard/backend/store.py`
- `~/d/dashboard/backend/indexer.py`
- `~/d/dashboard/backend/findings.py`
- `~/d/dashboard/backend/attention.py`
- `~/d/dashboard/backend/watcher.py`
- `~/d/dashboard/tests/`

---

## Task 1: Add The Inventory V1 Contract To `science_model`

**Files:**

- Create: `~/d/science/science/model/src/science_model/contracts/__init__.py`
- Create: `~/d/science/science/model/src/science_model/contracts/inventory_v1.py`
- Create: `~/d/science/science/model/tests/test_inventory_contract_v1.py`

**Step 1: Write contract tests first**

Create `~/d/science/science/model/tests/test_inventory_contract_v1.py`:

```python
from __future__ import annotations

from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventorySourceLocation,
    InventoryWarning,
    compute_audit_hash,
    compute_content_hash,
)


def test_inventory_payload_hashes_ignore_generated_at() -> None:
    entity = InventoryEntity(
        id="finding:landscape-topology",
        kind="finding",
        local_id="landscape-topology",
        title="Landscape topology",
        status="active",
        activity="active",
        source=InventorySourceLocation(
            adapter="markdown",
            path="doc/findings/landscape-topology.md",
            address="frontmatter",
        ),
    )
    alias = InventoryAlias(alias="f001", canonical_id="finding:landscape-topology")
    warning = InventoryWarning(
        code="deprecated-prose-reference",
        severity="warning",
        message="Markdown prose references deprecated ID h4.",
        path="doc/summary.md",
    )

    first = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="multiple-myeloma",
        entities=[entity],
        aliases=[alias],
        warnings=[warning],
        watch_paths=["doc", "knowledge", "results", "tasks"],
    )
    second = first.model_copy(update={"generated_at": "2026-05-12T10:01:00Z"})

    assert compute_content_hash(first) == compute_content_hash(second)
    assert compute_audit_hash(first) == compute_audit_hash(second)


def test_inventory_payload_sorts_stable_collections_for_hashing() -> None:
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        entities=[
            InventoryEntity(
                id="question:q02",
                kind="question",
                local_id="q02",
                title="Second",
                source=InventorySourceLocation(adapter="markdown", path="doc/q02.md"),
            ),
            InventoryEntity(
                id="question:q01",
                kind="question",
                local_id="q01",
                title="First",
                source=InventorySourceLocation(adapter="markdown", path="doc/q01.md"),
            ),
        ],
    )
    right = left.model_copy(update={"entities": list(reversed(left.entities))})

    assert compute_content_hash(left) == compute_content_hash(right)
```

Run:

```bash
cd ~/d/science/science/model
uv run --frozen pytest tests/test_inventory_contract_v1.py -q
```

Expected: fails because `science_model.contracts.inventory_v1` does not exist.

**Step 2: Implement the contract**

Create `~/d/science/science/model/src/science_model/contracts/__init__.py`:

```python
"""Versioned external contracts shared by Science tools and consumers."""
```

Create `~/d/science/science/model/src/science_model/contracts/inventory_v1.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1"

WarningSeverity = Literal["error", "warning", "info"]


class InventorySourceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str
    path: str
    address: str | None = None
    line: int | None = Field(default=None, ge=1)


class InventoryAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    canonical_id: str


class InventoryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: str
    target_id: str


class InventoryGraphAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str
    kind: str
    source: InventorySourceLocation
    canonical_id: str | None = None
    label: str | None = None


class InventoryFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    title: str
    targets: list[str] = Field(default_factory=list)
    source: InventorySourceLocation
    reason: str


class InventoryWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: WarningSeverity
    message: str
    path: str | None = None
    canonical_id: str | None = None


class InventoryProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    path: str | None = None
    summary: str | None = None
    status: str | None = None
    aspects: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class InventoryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    local_id: str
    title: str | None = None
    status: str | None = None
    activity: str | None = None
    registration_state: Literal["core", "ontology", "local", "unknown"] = "unknown"
    scope: Literal["project", "cross-project"] = "project"
    source: InventorySourceLocation
    aliases: list[str] = Field(default_factory=list)
    related: list[InventoryReference] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    review_state: str | None = None
    deprecated_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def canonical_id_has_separator(cls, value: str) -> str:
        if ":" not in value:
            msg = f"Inventory entity id must be canonical '<kind>:<local-id>', got {value!r}."
            raise ValueError(msg)
        return value


class InventoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    generated_at: str
    project_id: str
    project_path: str | None = None
    project: InventoryProjectMetadata | None = None
    content_hash: str | None = None
    audit_hash: str | None = None
    entities: list[InventoryEntity] = Field(default_factory=list)
    aliases: list[InventoryAlias] = Field(default_factory=list)
    graph_addresses: list[InventoryGraphAddress] = Field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = Field(default_factory=list)
    warnings: list[InventoryWarning] = Field(default_factory=list)
    watch_paths: list[str] = Field(default_factory=list)


def canonical_json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    data = value.model_dump(mode="json", exclude_none=True) if isinstance(value, BaseModel) else value
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _payload_for_content_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in ("generated_at", "content_hash", "audit_hash", "warnings"):
        data.pop(key, None)
    data["entities"] = sorted(data.get("entities", []), key=lambda item: item["id"])
    data["aliases"] = sorted(data.get("aliases", []), key=lambda item: item["alias"])
    data["graph_addresses"] = sorted(data.get("graph_addresses", []), key=lambda item: item["address"])
    data["finding_candidates"] = sorted(data.get("finding_candidates", []), key=lambda item: item["candidate_id"])
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def _payload_for_audit_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in ("generated_at", "content_hash", "audit_hash", "entities", "aliases", "graph_addresses", "finding_candidates"):
        data.pop(key, None)
    data["warnings"] = sorted(
        data.get("warnings", []),
        key=lambda item: (item["severity"], item["code"], item.get("path") or "", item.get("canonical_id") or ""),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def compute_content_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(canonical_json_bytes(_payload_for_content_hash(payload))).hexdigest()


def compute_audit_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(canonical_json_bytes(_payload_for_audit_hash(payload))).hexdigest()


def finalize_inventory_payload(payload: InventoryPayload) -> InventoryPayload:
    content_hash = compute_content_hash(payload)
    audit_hash = compute_audit_hash(payload)
    return payload.model_copy(update={"content_hash": content_hash, "audit_hash": audit_hash})
```

**Step 3: Verify**

Run:

```bash
cd ~/d/science/science/model
uv run --frozen pytest tests/test_inventory_contract_v1.py -q
uv run --frozen pyright
```

Expected: contract tests pass and type checking reports no errors from the new module.

---

## Task 2: Add WorkflowRunAdapter For Result Manifests

**Files:**

- Create: `~/d/science/science/src/science_tool/graph/storage_adapters/workflow_run.py`
- Edit: `~/d/science/science/src/science_tool/graph/storage_adapters/__init__.py`
- Edit: `~/d/science/science/src/science_tool/graph/sources.py`
- Create: `~/d/science/science/tests/test_storage_adapters/test_workflow_run_adapter.py`

**Step 1: Write adapter tests**

Create `~/d/science/science/tests/test_storage_adapters/test_workflow_run_adapter.py`:

```python
from __future__ import annotations

from science_tool.graph.storage_adapters.workflow_run import WorkflowRunAdapter


def test_workflow_run_adapter_loads_results_datapackage_json(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    manifest = project / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
{
  "name": "run-a",
  "title": "Run A",
  "resources": [{"path": "table.csv"}],
  "created": "2026-05-12T10:00:00Z"
}
""".strip(),
        encoding="utf-8",
    )

    adapter = WorkflowRunAdapter()
    refs = adapter.discover(project)
    monkeypatch.chdir(project)
    raw = adapter.load_raw(refs[0])

    assert len(refs) == 1
    assert raw["kind"] == "workflow-run"
    assert raw["id"] == "workflow-run:run-a"
    assert raw["title"] == "Run A"
    assert raw["manifest_path"] == "results/run-a/datapackage.json"
```

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_storage_adapters/test_workflow_run_adapter.py -q
```

Expected: fails because `workflow_run.py` does not exist.

**Step 2: Implement the adapter**

Create `~/d/science/science/src/science_tool/graph/storage_adapters/workflow_run.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


class WorkflowRunAdapter(StorageAdapter):
    """Load workflow-run entities from results/**/datapackage.json manifests."""

    name = "workflow-run"

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        root = project_root / "results"
        if not root.is_dir():
            return refs
        for path in sorted(root.glob("**/datapackage.json")):
            rel_path = path.relative_to(project_root).as_posix()
            refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        local_id = str(manifest.get("name") or path.parent.name)
        canonical_id = f"workflow-run:{local_id}"
        title = str(manifest.get("title") or local_id)
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "workflow-run",
            "title": title,
            "manifest_path": ref.path,
            "resources": manifest.get("resources", []),
            "created": manifest.get("created"),
            "file_path": ref.path,
        }
```

Edit `~/d/science/science/src/science_tool/graph/storage_adapters/__init__.py` to export:

```python
from science_tool.graph.storage_adapters.workflow_run import WorkflowRunAdapter
```

Edit `~/d/science/science/src/science_tool/graph/sources.py` so the adapter list includes `WorkflowRunAdapter()` after `DatapackageAdapter()`:

```python
adapters: list[StorageAdapter] = [
    MarkdownAdapter(),
    AggregateAdapter(),
    DatapackageAdapter(),
    WorkflowRunAdapter(),
    TaskAdapter(),
]
```

**Step 3: Verify**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_storage_adapters/test_workflow_run_adapter.py -q
uv run --frozen pytest tests/test_graph_sources.py -q
```

Expected: workflow-run manifests are loaded as Science-owned entities, with no regression in source loading tests.

---

## Task 3: Add DAG Graph Addresses And Finding Candidates

**Files:**

- Create: `~/d/science/science/src/science_tool/dag/inventory.py`
- Create: `~/d/science/science/tests/dag/test_dag_inventory.py`

**Step 1: Write DAG inventory tests**

Create `~/d/science/science/tests/dag/test_dag_inventory.py`:

```python
from __future__ import annotations

from science_tool.dag.inventory import load_dag_inventory_records


def test_dag_edges_require_stable_declared_ids(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4-attractor-convergence.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: landscape
    target: attractor
    relation: converges_to
    interpretation: Landscape topology supports attractor convergence.
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert [address.address for address in records.graph_addresses] == [
        "dag-edge:h4-attractor-convergence:e001"
    ]
    assert records.finding_candidates[0].targets == ["dag-edge:h4-attractor-convergence:e001"]


def test_dag_edges_without_ids_emit_warning_instead_of_position_address(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - source: a
    target: b
    relation: supports
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert records.graph_addresses == []
    assert records.finding_candidates == []
    assert records.warnings[0].code == "missing-dag-edge-id"
    assert records.warnings[0].severity == "warning"
```

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/dag/test_dag_inventory.py -q
```

Expected: fails because `science_tool.dag.inventory` does not exist.

**Step 2: Implement DAG inventory records**

Create `~/d/science/science/src/science_tool/dag/inventory.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from science_model import Entity
from science_model.contracts.inventory_v1 import (
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventorySourceLocation,
    InventoryWarning,
)


@dataclass(frozen=True)
class DagInventoryRecords:
    graph_addresses: list[InventoryGraphAddress] = field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = field(default_factory=list)
    warnings: list[InventoryWarning] = field(default_factory=list)


def load_dag_inventory_records(project_root: Path) -> DagInventoryRecords:
    graph_addresses: list[InventoryGraphAddress] = []
    finding_candidates: list[InventoryFindingCandidate] = []
    warnings: list[InventoryWarning] = []

    for path in sorted((project_root / "doc" / "figures" / "dags").glob("*.edges.yaml")):
        rel_path = path.relative_to(project_root).as_posix()
        dag_slug = path.name.removesuffix(".edges.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        edges = payload.get("edges") or []
        seen_ids: set[str] = set()
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge_id = edge.get("id")
            if not isinstance(edge_id, str) or not edge_id:
                warnings.append(
                    InventoryWarning(
                        code="missing-dag-edge-id",
                        severity="warning",
                        message="DAG edge is missing a stable declared id.",
                        path=rel_path,
                    )
                )
                continue
            if edge_id in seen_ids:
                warnings.append(
                    InventoryWarning(
                        code="duplicate-dag-edge-id",
                        severity="warning",
                        message=f"DAG edge id {edge_id!r} appears more than once in this DAG.",
                        path=rel_path,
                    )
                )
                continue
            seen_ids.add(edge_id)
            address = f"dag-edge:{dag_slug}:{edge_id}"
            graph_addresses.append(
                InventoryGraphAddress(
                    address=address,
                    kind="dag-edge",
                    label=_edge_label(edge),
                    source=InventorySourceLocation(adapter="dag", path=rel_path, address=edge_id),
                )
            )
            interpretation = edge.get("interpretation") or edge.get("finding") or edge.get("claim")
            if isinstance(interpretation, str) and interpretation.strip():
                finding_candidates.append(
                    InventoryFindingCandidate(
                        candidate_id=f"finding-candidate:{address}",
                        title=interpretation.strip(),
                        targets=[address],
                        source=InventorySourceLocation(adapter="dag", path=rel_path, address=edge_id),
                        reason="DAG edge contains claim-bearing interpretation text.",
                    )
                )

    return DagInventoryRecords(
        graph_addresses=graph_addresses,
        finding_candidates=finding_candidates,
        warnings=warnings,
    )


def _edge_label(edge: dict[str, Any]) -> str:
    source = str(edge.get("source") or "")
    relation = str(edge.get("relation") or "edge")
    target = str(edge.get("target") or "")
    return " ".join(part for part in (source, relation, target) if part)
```

**Step 3: Verify**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/dag/test_dag_inventory.py -q
```

Expected: tests pass. The implementation must never derive addresses from YAML array positions.

---

## Task 4: Build The Science Inventory Payload And CLI

**Files:**

- Create: `~/d/science/science/src/science_tool/entities_inventory.py`
- Edit: `~/d/science/science/src/science_tool/graph/sources.py`
- Edit: `~/d/science/science/src/science_tool/cli.py`
- Create: `~/d/science/science/tests/test_entities_inventory.py`
- Edit: `~/d/science/science/tests/test_entities_cli.py`

**Step 1: Write builder tests**

Create `~/d/science/science/tests/test_entities_inventory.py`:

```python
from __future__ import annotations

import json

from science_model.contracts.inventory_v1 import InventoryPayload
from science_tool.entities_inventory import build_inventory


def test_build_inventory_includes_entities_aliases_dag_candidates_and_watch_paths(tmp_path) -> None:
    project = tmp_path / "project"
    for rel_path in ("doc", "knowledge", "notes", "papers", "results", "specs", "tasks"):
        (project / rel_path).mkdir(parents=True)
    (project / "science.yaml").write_text(
        """
id: test-project
knowledge_profiles:
  local: knowledge/profiles/local.yaml
""".strip(),
        encoding="utf-8",
    )
    (project / "doc" / "finding.md").write_text(
        """
---
kind: finding
id: finding:f001
aliases: [f001]
title: Test finding
---
Body.
""".strip(),
        encoding="utf-8",
    )
    dag_path = project / "doc" / "figures" / "dags" / "h1.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: a
    target: b
    relation: supports
    interpretation: Edge interpretation.
""".strip(),
        encoding="utf-8",
    )

    inventory = build_inventory(project)

    InventoryPayload.model_validate(json.loads(inventory.model_dump_json()))
    assert inventory.schema_version == "1"
    assert inventory.project_id == "test-project"
    assert inventory.content_hash
    assert inventory.audit_hash
    assert [entity.id for entity in inventory.entities] == ["finding:f001"]
    assert inventory.aliases[0].alias == "f001"
    assert inventory.graph_addresses[0].address == "dag-edge:h1:e001"
    assert inventory.finding_candidates[0].targets == ["dag-edge:h1:e001"]
    assert inventory.watch_paths == ["doc", "knowledge", "notes", "papers", "results", "specs", "tasks"]
```

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entities_inventory.py -q
```

Expected: fails because `science_tool.entities_inventory` does not exist.

**Step 2: Expose source adapter names from source loading**

Edit `~/d/science/science/src/science_tool/graph/sources.py` so adapter identity travels with each loaded entity. Add this field to `ProjectSources`:

```python
entity_source_adapters: dict[str, str] = Field(default_factory=dict)
```

In `load_project_sources`, initialize the mapping before the adapter loop:

```python
entity_source_adapters: dict[str, str] = {}
```

Immediately after `entities.append(entity)`, record the adapter that produced the entity:

```python
entity_source_adapters[entity.canonical_id] = adapter.name
```

For the structured-source records that `load_project_sources` appends after the storage-adapter loop, set the same mapping at each append site with the concrete source family, for example `entity_source_adapters[entity.canonical_id] = "structured-source"`.

Pass the mapping into the returned `ProjectSources`:

```python
entity_source_adapters=entity_source_adapters,
```

Do not recover adapter identity from path strings in the inventory builder.

**Step 3: Implement the inventory builder**

Create `~/d/science/science/src/science_tool/entities_inventory.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    finalize_inventory_payload,
)
from science_tool.dag.inventory import load_dag_inventory_records
from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.sources import load_project_sources

DEFAULT_WATCH_PATHS = ["doc", "knowledge", "notes", "papers", "results", "specs", "tasks"]
PROMOTED_ENTITY_DATA_FIELDS = {
    "id",
    "canonical_id",
    "kind",
    "type",
    "title",
    "status",
    "project",
    "ontology_terms",
    "related",
    "relations",
    "source_refs",
    "aliases",
    "deprecated_ids",
    "review_state",
    "file_path",
}


def build_inventory(project_root: Path) -> InventoryPayload:
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)
    dag_records = load_dag_inventory_records(project_root)
    project_metadata = _read_project_metadata(project_root)

    entities: list[InventoryEntity] = []
    aliases: list[InventoryAlias] = []
    warnings: list[InventoryWarning] = [*collect_identity_warnings(project_root, sources=sources), *dag_records.warnings]

    for entity in sorted(sources.entities, key=lambda item: item.canonical_id or item.id):
        canonical_id = entity.canonical_id or entity.id
        kind = entity.kind
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else canonical_id
        source = InventorySourceLocation(
            adapter=sources.entity_source_adapters.get(canonical_id, "unknown"),
            path=entity.file_path,
        )
        data = entity.model_dump(mode="json", exclude_none=True, exclude=PROMOTED_ENTITY_DATA_FIELDS)
        entities.append(
            InventoryEntity(
                id=canonical_id,
                kind=kind,
                local_id=local_id,
                title=entity.title,
                status=entity.status,
                source=source,
                aliases=entity.aliases,
                related=_references_from_entity(entity),
                source_refs=entity.source_refs,
                targets=[str(value) for value in data.get("targets", []) if value],
                review_state=str(entity.review_state) if entity.review_state is not None else None,
                deprecated_ids=entity.deprecated_ids,
                data=data,
            )
        )
        aliases.extend(InventoryAlias(alias=alias, canonical_id=canonical_id) for alias in entity.aliases)

    payload = InventoryPayload(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted(aliases, key=lambda item: item.alias),
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=_watch_paths(project_root),
    )
    return finalize_inventory_payload(payload)


def _read_project_metadata(project_root: Path) -> InventoryProjectMetadata:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return InventoryProjectMetadata(id=project_root.name, name=project_root.name, path=project_root.as_posix())
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    project_id = data.get("id")
    canonical_id = str(project_id) if project_id else project_root.name
    return InventoryProjectMetadata(
        id=canonical_id,
        name=str(data.get("name") or canonical_id),
        path=project_root.as_posix(),
        summary=_optional_str(data.get("summary")),
        status=_optional_str(data.get("status")),
        aspects=[str(value) for value in data.get("aspects", [])],
        tags=[str(value) for value in data.get("tags", [])],
    )


def _watch_paths(project_root: Path) -> list[str]:
    return [path for path in DEFAULT_WATCH_PATHS if (project_root / path).exists()]


def _references_from_entity(entity: Entity) -> list[InventoryReference]:
    return [InventoryReference(relation="related", target_id=target) for target in entity.related]


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None
```

**Step 4: Add `science entities inventory` CLI**

Edit `~/d/science/science/src/science_tool/cli.py`:

```python
@main.group("entities")
def entities_group() -> None:
    """Inspect and migrate Science entity inventories."""


@entities_group.command("inventory")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json")
@click.option("--output", type=click.Path(path_type=Path), default=None)
def entities_inventory_command(project_path: Path, output_format: str, output: Path | None) -> None:
    """Emit the versioned Science entity inventory for a project."""
    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")
```

Add the import near the other Science CLI imports:

```python
from science_tool.entities_inventory import build_inventory
```

**Step 5: Write CLI tests**

Add to `~/d/science/science/tests/test_entities_cli.py`:

```python
def test_entities_inventory_cli_outputs_contract_json(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: cli-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )

    result = runner.invoke(cli.main, ["entities", "inventory", "--project", str(project), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = InventoryPayload.model_validate_json(result.output)
    assert payload.project_id == "cli-project"
    assert payload.entities[0].id == "finding:f001"
```

Add imports:

```python
from science_model.contracts.inventory_v1 import InventoryPayload
```

**Step 6: Verify**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entities_inventory.py tests/test_entities_cli.py -q
```

Expected: inventory builder and CLI pass. If existing entity CLI tests fail because the new `entities` group conflicts with imports or names, fix the import/name collision in `cli.py` without changing the existing `entity` group behavior.

---

## Task 5: Add Identity Health Checks, Baseline Loading, And Prose Reference Warnings

**Files:**

- Create: `~/d/science/science/src/science_tool/entity_identity.py`
- Edit: `~/d/science/science/src/science_tool/graph/sources.py`
- Edit: `~/d/science/science/src/science_tool/graph/health.py`
- Create: `~/d/science/science/tests/test_entity_identity_health.py`

**Step 1: Write health tests**

Create `~/d/science/science/tests/test_entity_identity_health.py`:

```python
from __future__ import annotations

from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import KnowledgeProfiles, MarkdownSourceDocument, ProjectSources, load_project_sources


def _sources_with_documents(project, documents: list[MarkdownSourceDocument]) -> ProjectSources:
    return ProjectSources(
        project_name="project",
        project_root=str(project),
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
        markdown_documents=documents,
    )


def test_identity_health_flags_missing_canonical_id_as_warning_for_baselined_record(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "knowledge").mkdir(parents=True)
    (project / "knowledge" / "entity-identity-baseline.yaml").write_text(
        """
records:
  - path: doc/finding.md
    accepted_at: "2026-05-12T10:00:00Z"
""".strip(),
        encoding="utf-8",
    )
    sources = _sources_with_documents(
        project,
        [
            MarkdownSourceDocument(
                path="doc/finding.md",
                frontmatter={"kind": "finding", "title": "Legacy"},
                body="",
            )
        ],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert warnings[0].code == "missing-canonical-id"
    assert warnings[0].severity == "warning"


def test_identity_health_flags_unresolved_markdown_prose_reference_as_warning(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [MarkdownSourceDocument(path="doc/summary.md", frontmatter={}, body="This cites [[h999]] in prose.\n")],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert any(
        warning.code == "unresolved-prose-reference" and warning.severity == "warning"
        for warning in warnings
    )


def test_identity_health_resolves_markdown_aliases_from_loaded_sources(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: alias-project\n", encoding="utf-8")
    (project / "doc" / "h001.md").write_text(
        "---\nkind: hypothesis\nid: hypothesis:h001\naliases: [h001]\ntitle: H001\n---\n",
        encoding="utf-8",
    )
    (project / "doc" / "summary.md").write_text("This cites [[h001]] in prose.\n", encoding="utf-8")

    warnings = collect_identity_warnings(project, sources=load_project_sources(project))

    assert not [warning for warning in warnings if warning.code == "unresolved-prose-reference"]
```

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entity_identity_health.py -q
```

Expected: fails because `science_tool.entity_identity` and `MarkdownSourceDocument` do not exist.

**Step 2: Implement identity warning collection**

First, expose the markdown documents already parsed during source loading. Edit `~/d/science/science/src/science_tool/graph/sources.py`:

```python
class MarkdownSourceDocument(BaseModel):
    path: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""
```

Add the field to `ProjectSources`:

```python
markdown_documents: list[MarkdownSourceDocument] = Field(default_factory=list)
```

In `load_project_sources`, initialize `markdown_documents` before the adapter loop:

```python
markdown_documents: list[MarkdownSourceDocument] = []
```

Immediately after `raw = adapter.load_raw(ref)`, capture markdown documents without reading the file again:

```python
if isinstance(adapter, MarkdownAdapter):
    markdown_documents.append(
        MarkdownSourceDocument(
            path=ref.path,
            frontmatter={key: value for key, value in raw.items() if key != "content"},
            body=str(raw.get("content") or ""),
        )
    )
```

Include `markdown_documents=markdown_documents` when constructing the returned `ProjectSources`.

Create `~/d/science/science/src/science_tool/entity_identity.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

import yaml
from science_model.contracts.inventory_v1 import InventoryWarning
from science_tool.graph.sources import ProjectSources

CANONICAL_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROSE_REFERENCE_PATTERN = re.compile(
    r"\[\[((?:[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*)|(?:[thqf]\d{2,}[a-z0-9_.-]*))\]\]",
)


def collect_identity_warnings(project_root: Path, *, sources: ProjectSources) -> list[InventoryWarning]:
    warnings: list[InventoryWarning] = []
    baseline_paths = _baseline_paths(project_root)
    canonical_ids = _canonical_ids(sources)

    for document in sorted(sources.markdown_documents, key=lambda item: item.path):
        rel_path = document.path
        frontmatter = document.frontmatter
        if not frontmatter:
            warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
            continue
        kind = frontmatter.get("kind")
        if not kind:
            warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
            continue
        entity_id = frontmatter.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            severity = "warning" if rel_path in baseline_paths else "error"
            warnings.append(
                InventoryWarning(
                    code="missing-canonical-id",
                    severity=severity,
                    message="Entity frontmatter is missing canonical '<kind>:<local-id>' id.",
                    path=rel_path,
                )
            )
        elif not CANONICAL_ID_PATTERN.match(entity_id):
            severity = "warning" if rel_path in baseline_paths else "error"
            warnings.append(
                InventoryWarning(
                    code="invalid-canonical-id",
                    severity=severity,
                    message=f"Entity id {entity_id!r} does not match '<kind>:<local-id>'.",
                    path=rel_path,
                    canonical_id=entity_id,
                )
            )
        warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
    return warnings


def _baseline_paths(project_root: Path) -> set[str]:
    path = project_root / "knowledge" / "entity-identity-baseline.yaml"
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(record["path"]) for record in data.get("records", []) if isinstance(record, dict) and record.get("path")}


def _canonical_ids(sources: ProjectSources) -> set[str]:
    ids: set[str] = set()
    for entity in sources.entities:
        ids.add(entity.canonical_id or entity.id)
        ids.update(str(alias) for alias in entity.aliases)
    return ids


def _prose_reference_warnings(rel_path: str, text: str, canonical_ids: set[str]) -> list[InventoryWarning]:
    warnings: list[InventoryWarning] = []
    for match in PROSE_REFERENCE_PATTERN.finditer(text):
        target = match.group(1)
        if target not in canonical_ids:
            warnings.append(
                InventoryWarning(
                    code="unresolved-prose-reference",
                    severity="warning",
                    message=f"Markdown prose reference {target!r} does not resolve to a canonical id or alias.",
                    path=rel_path,
                    canonical_id=target,
                )
            )
    return warnings
```

**Step 3: Feed identity warnings into inventory and health**

The inventory builder already has `sources = load_project_sources(project_root)`. Pass that object to identity checks instead of causing another source-load or markdown walk:

```python
warnings: list[InventoryWarning] = [*collect_identity_warnings(project_root, sources=sources), *dag_records.warnings]
```

Edit `~/d/science/science/src/science_tool/graph/health.py`.

Add imports:

```python
from science_model.contracts.inventory_v1 import InventoryWarning
from science_tool.entity_identity import collect_identity_warnings
```

Add a health finding row type near the other `TypedDict` definitions:

```python
class EntityIdentityFinding(TypedDict):
    code: str
    severity: str
    message: str
    path: str | None
    canonical_id: str | None
```

Add the field to `HealthReport`:

```python
entity_identity: list[EntityIdentityFinding]
```

Add the collector:

```python
def _collect_entity_identity(context: HealthContext) -> list[EntityIdentityFinding]:
    rows: list[EntityIdentityFinding] = []
    sources = _context_sources(context)
    for warning in collect_identity_warnings(context.project_root, sources=sources):
        rows.append(
            {
                "code": warning.code,
                "severity": warning.severity,
                "message": warning.message,
                "path": warning.path,
                "canonical_id": warning.canonical_id,
            }
        )
    return rows
```

Add the health check:

```python
HealthCheck(
    name="entity_identity",
    description="Validate canonical entity identifiers, baseline status, and prose references.",
    requires_sources=True,
    run=_collect_entity_identity,
),
```

In `build_health_report`, read the check result and include it in `total_issues`:

```python
entity_identity = cast("list[EntityIdentityFinding]", check_results.get("entity_identity", []))
```

Add `+ len(entity_identity)` to `total_issues`, and add the report field:

```python
"entity_identity": entity_identity,
```

**Step 4: Verify**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entity_identity_health.py tests/test_health.py tests/test_entities_inventory.py -q
```

Expected: identity health tests pass, and existing health tests still pass with the new warnings included.

---

## Task 6: Add `register-kind` For Local Kind Resolution

**Files:**

- Create: `~/d/science/science/src/science_tool/entity_kinds.py`
- Edit: `~/d/science/science/src/science_tool/cli.py`
- Edit: `~/d/science/science/tests/test_entities_cli.py`

**Step 1: Write CLI tests**

Add to `~/d/science/science/tests/test_entities_cli.py`:

```python
def test_entities_register_kind_is_idempotent_with_same_metadata(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "knowledge" / "profiles").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles:\n  local: knowledge/profiles/local.yaml\n",
        encoding="utf-8",
    )

    first = runner.invoke(
        cli.main,
        ["entities", "register-kind", "critique", "--class", "interpretation", "--project", str(project)],
    )
    second = runner.invoke(
        cli.main,
        ["entities", "register-kind", "critique", "--class", "interpretation", "--project", str(project)],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "already registered" in second.output


def test_entities_register_kind_errors_on_changed_semantics(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "knowledge" / "profiles").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles:\n  local: knowledge/profiles/local.yaml\n",
        encoding="utf-8",
    )
    runner.invoke(cli.main, ["entities", "register-kind", "critique", "--class", "interpretation", "--project", str(project)])

    result = runner.invoke(cli.main, ["entities", "register-kind", "critique", "--class", "artifact", "--project", str(project)])

    assert result.exit_code != 0
    assert "already registered with different metadata" in result.output
```

**Step 2: Implement local profile registration**

Create `~/d/science/science/src/science_tool/entity_kinds.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


def register_local_kind(project_root: Path, kind: str, entity_class: str) -> str:
    profile_path = _local_profile_path(project_root)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    if not isinstance(profile, dict):
        profile = {}
    kinds = profile.setdefault("kinds", {})
    existing = kinds.get(kind)
    requested = {"class": entity_class}
    if existing == requested:
        return "already registered"
    if existing is not None and existing != requested:
        msg = f"kind {kind!r} already registered with different metadata"
        raise ValueError(msg)
    kinds[kind] = requested
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
    return "registered"


def _local_profile_path(project_root: Path) -> Path:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return project_root / "knowledge" / "profiles" / "local.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    local_path = (config.get("knowledge_profiles") or {}).get("local")
    if local_path:
        return project_root / str(local_path)
    return project_root / "knowledge" / "profiles" / "local.yaml"
```

Add CLI command:

```python
from science_tool.entity_kinds import register_local_kind
```

```python
@entities_group.command("register-kind")
@click.argument("kind")
@click.option("--class", "entity_class", required=True)
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
def entities_register_kind_command(kind: str, entity_class: str, project_path: Path) -> None:
    """Register a project-local entity kind in the local profile."""
    try:
        result = register_local_kind(project_path, kind, entity_class)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{kind}: {result}")
```

**Step 3: Verify**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entities_cli.py -q
```

Expected: existing entity CLI tests and the new `entities register-kind` tests pass.

---

## Task 7: Add Migration And Audit Commands

**Files:**

- Create: `~/d/science/science/src/science_tool/entity_migrations.py`
- Edit: `~/d/science/science/src/science_tool/cli.py`
- Create: `~/d/science/science/tests/test_entity_migrations.py`

**Step 1: Write migration tests**

Create `~/d/science/science/tests/test_entity_migrations.py`:

```python
from __future__ import annotations

from science_tool.entity_migrations import audit_identifiers, migrate_identifiers


def test_audit_identifiers_reports_baselined_missing_ids(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "doc" / "finding.md").write_text("---\nkind: finding\ntitle: Legacy\n---\n", encoding="utf-8")

    report = audit_identifiers(project)

    assert report["missing_canonical_ids"] == ["doc/finding.md"]


def test_migrate_identifiers_dry_run_reports_changes_without_rewriting(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text("---\nkind: finding\ntitle: Legacy\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["planned_changes"][0]["new_id"] == "finding:finding"
    assert "id: finding:finding" not in path.read_text(encoding="utf-8")


def test_migrate_identifiers_apply_inserts_id_without_rewriting_body(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text(
        "---\nkind: finding\n# keep this comment\ntitle: Legacy\n---\n\nBody text.\n",
        encoding="utf-8",
    )

    report = migrate_identifiers(project, apply=True)

    text = path.read_text(encoding="utf-8")
    assert report["applied"] is True
    assert "kind: finding\nid: finding:finding\n# keep this comment\n" in text
    assert text.endswith("\nBody text.\n")


def test_migrate_identifiers_reports_collisions_without_rewriting(tmp_path) -> None:
    project = tmp_path / "project"
    left = project / "doc" / "a" / "summary.md"
    right = project / "doc" / "b" / "summary.md"
    left.parent.mkdir(parents=True)
    right.parent.mkdir(parents=True)
    for path in (left, right):
        path.write_text("---\nkind: finding\ntitle: Summary\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["collisions"] == [{"new_id": "finding:summary", "paths": ["doc/a/summary.md", "doc/b/summary.md"]}]


def test_migrate_identifiers_reports_collision_with_existing_id(tmp_path) -> None:
    project = tmp_path / "project"
    existing = project / "doc" / "a" / "summary.md"
    new = project / "doc" / "b" / "summary.md"
    existing.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    existing.write_text("---\nkind: finding\nid: finding:summary\ntitle: Existing\n---\n", encoding="utf-8")
    new.write_text("---\nkind: finding\ntitle: New\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["collisions"] == [{"new_id": "finding:summary", "paths": ["doc/a/summary.md", "doc/b/summary.md"]}]
```

**Step 2: Implement audit and migration report functions**

Create `~/d/science/science/src/science_tool/entity_migrations.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def audit_identifiers(project_root: Path) -> dict[str, Any]:
    missing: list[str] = []
    invalid: list[str] = []
    for path in sorted(project_root.glob("**/*.md")):
        rel_path = path.relative_to(project_root).as_posix()
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        if not frontmatter.get("kind"):
            continue
        entity_id = frontmatter.get("id")
        if not entity_id:
            missing.append(rel_path)
        elif ":" not in str(entity_id):
            invalid.append(rel_path)
    return {"missing_canonical_ids": missing, "invalid_canonical_ids": invalid}


def migrate_identifiers(project_root: Path, *, apply: bool) -> dict[str, Any]:
    planned_changes: list[dict[str, str]] = []
    existing_by_id = _existing_canonical_ids(project_root)
    planned_by_id: dict[str, list[str]] = {entity_id: paths.copy() for entity_id, paths in existing_by_id.items()}
    for path in sorted(project_root.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = _frontmatter(text)
        kind = frontmatter.get("kind")
        if not kind or frontmatter.get("id"):
            continue
        rel_path = path.relative_to(project_root).as_posix()
        new_id = f"{kind}:{path.stem}"
        planned_changes.append({"path": rel_path, "new_id": new_id})
        planned_by_id.setdefault(new_id, []).append(rel_path)
    planned_ids = {change["new_id"] for change in planned_changes}
    collisions = [
        {"new_id": new_id, "paths": paths}
        for new_id, paths in sorted(planned_by_id.items())
        if len(paths) > 1 and new_id in planned_ids
    ]
    if apply and collisions:
        msg = f"identifier collisions prevent migration: {collisions}"
        raise ValueError(msg)
    if apply:
        for change in planned_changes:
            path = project_root / change["path"]
            _write_frontmatter_id(path, path.read_text(encoding="utf-8"), change["new_id"])
    return {"planned_changes": planned_changes, "collisions": collisions, "applied": apply}


def _existing_canonical_ids(project_root: Path) -> dict[str, list[str]]:
    existing: dict[str, list[str]] = {}
    for path in sorted(project_root.glob("**/*.md")):
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        entity_id = frontmatter.get("id")
        if isinstance(entity_id, str) and entity_id:
            rel_path = path.relative_to(project_root).as_posix()
            existing.setdefault(entity_id, []).append(rel_path)
    return existing


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    value = yaml.safe_load(text[4:end]) or {}
    return value if isinstance(value, dict) else {}


def _write_frontmatter_id(path: Path, text: str, new_id: str) -> None:
    end = text.find("\n---", 4)
    frontmatter_lines = text[4:end].splitlines()
    insert_at = next((index + 1 for index, line in enumerate(frontmatter_lines) if line.startswith("kind:")), 0)
    frontmatter_lines.insert(insert_at, f"id: {new_id}")
    body = text[end + 4 :]
    rendered = "---\n" + "\n".join(frontmatter_lines) + "\n---" + body
    path.write_text(rendered, encoding="utf-8")
```

**Step 3: Add CLI commands**

Add imports:

```python
from science_tool.entity_migrations import audit_identifiers, migrate_identifiers
```

Add commands:

```python
@entities_group.command("audit-identifiers")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
def entities_audit_identifiers_command(project_path: Path) -> None:
    click.echo(json.dumps(audit_identifiers(project_path), indent=2))


@entities_group.command("migrate-identifiers")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--apply", "apply_changes", is_flag=True, default=False)
def entities_migrate_identifiers_command(project_path: Path, apply_changes: bool) -> None:
    try:
        report = migrate_identifiers(project_path, apply=apply_changes)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, indent=2))
```

Ensure `json` is imported in `cli.py`.

**Step 4: Verify on audit projects**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entity_migrations.py -q
uv run --frozen science entities audit-identifiers --project ~/d/cancer/cancer-types/multiple-myeloma
uv run --frozen science entities audit-identifiers --project ~/d/natural-systems
```

Expected: pytest passes and both audit commands print JSON reports without mutating either project.

---

## Task 8: Add Dashboard Inventory Client And Contract Validation

**Files:**

- Create: `~/d/dashboard/backend/science_inventory.py`
- Create: `~/d/dashboard/tests/test_science_inventory.py`

**Step 1: Write dashboard client tests**

Create `~/d/dashboard/tests/test_science_inventory.py`:

```python
from __future__ import annotations

import pytest
from science_model.contracts.inventory_v1 import InventoryPayload

from backend.science_inventory import load_science_inventory


def test_load_science_inventory_imports_science_builder_and_validates_payload(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="project",
        entities=[],
        aliases=[],
        graph_addresses=[],
        finding_candidates=[],
        warnings=[],
        watch_paths=["doc"],
    )

    monkeypatch.setattr("backend.science_inventory.build_inventory", lambda root: payload)

    inventory = load_science_inventory(project)

    assert inventory.schema_version == "1"
    assert inventory.project_id == "project"


def test_load_science_inventory_fails_early_on_invalid_payload(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr("backend.science_inventory.build_inventory", lambda root: {"schema_version": "2"})

    with pytest.raises(ValueError, match="Invalid Science inventory payload"):
        load_science_inventory(project)
```

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_science_inventory.py -q
```

Expected: fails because `backend.science_inventory` does not exist.

**Step 2: Implement the client**

Create `~/d/dashboard/backend/science_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from science_model.contracts.inventory_v1 import InventoryPayload
from science_tool.entities_inventory import build_inventory


def load_science_inventory(project_root: Path) -> InventoryPayload:
    raw_inventory = build_inventory(project_root)
    try:
        return InventoryPayload.model_validate(raw_inventory)
    except ValidationError as exc:
        msg = f"Invalid Science inventory payload for {project_root}: {exc}"
        raise ValueError(msg) from exc
```

**Step 3: Verify**

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_science_inventory.py -q
```

Expected: tests pass. Do not add subprocess or local-scanning fallback paths to this client.

---

## Task 9: Convert Inventory Payloads Into Dashboard Project State

**Files:**

- Create: `~/d/dashboard/backend/inventory_indexer.py`
- Edit: `~/d/dashboard/backend/store.py`
- Create: `~/d/dashboard/tests/test_inventory_indexer.py`
- Edit: `~/d/dashboard/tests/test_store.py`

**Step 1: Write conversion tests**

Create `~/d/dashboard/tests/test_inventory_indexer.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_model.contracts.inventory_v1 import InventoryEntity, InventoryPayload, InventorySourceLocation

from backend.inventory_indexer import scan_from_inventory


def test_scan_from_inventory_preserves_entity_kind_status_and_source() -> None:
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="project",
        entities=[
            InventoryEntity(
                id="finding:f001",
                kind="finding",
                local_id="f001",
                title="Finding",
                status="accepted",
                source=InventorySourceLocation(adapter="markdown", path="doc/finding.md"),
                data={"summary": "Evidence."},
            )
        ],
        watch_paths=["doc"],
    )

    scan = scan_from_inventory(Path("/project"), payload)

    assert len(scan.entities) == 1
    entity = scan.entities[0]
    assert entity.id == "finding:f001"
    assert entity.kind == "finding"
    assert entity.status == "accepted"
    assert entity.file_path == "/project/doc/finding.md"


def test_scan_from_science_inventory_round_trips_markdown_entity(tmp_path) -> None:
    from science_tool.entities_inventory import build_inventory

    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: project\nname: Project\naspects: [mechanism]\ntags: [myeloma]\n",
        encoding="utf-8",
    )
    (project / "doc" / "finding.md").write_text(
        """
---
kind: finding
id: finding:f001
title: Finding
status: accepted
source_refs: [paper:smith-2024]
related: [hypothesis:h001]
---
Evidence summary.
""".strip(),
        encoding="utf-8",
    )

    scan = scan_from_inventory(project, build_inventory(project))

    assert scan.project.aspects == ["mechanism"]
    assert scan.project.tags == ["myeloma"]
    assert scan.entities[0].id == "finding:f001"
    assert scan.entities[0].source_refs == ["paper:smith-2024"]
```

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_indexer.py -q
```

Expected: fails because `backend.inventory_indexer` does not exist.

**Step 2: Implement conversion**

Create `~/d/dashboard/backend/inventory_indexer.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_model import Entity, Project, Task
from science_model.contracts.inventory_v1 import InventoryPayload

from backend.indexer import ProjectScan


def scan_from_inventory(project_root: Path, inventory: InventoryPayload) -> ProjectScan:
    entities: list[Entity] = []
    tasks: list[Task] = []
    for item in inventory.entities:
        path = project_root / item.source.path
        payload = {
            **item.data,
            "id": item.id,
            "canonical_id": item.id,
            "kind": item.kind,
            "title": item.title or item.local_id,
            "status": item.status,
            "project": inventory.project_id,
            "ontology_terms": item.data.get("ontology_terms", []),
            "related": [ref.target_id for ref in item.related],
            "source_refs": item.source_refs,
            "content_preview": str(item.data.get("summary") or item.title or item.local_id),
            "file_path": str(path),
            "aliases": item.aliases,
            "deprecated_ids": item.deprecated_ids,
        }
        if item.kind == "task":
            tasks.append(Task.model_validate(payload))
        else:
            entities.append(Entity.model_validate(payload))
    metadata = inventory.project
    project = Project(
        slug=inventory.project_id,
        name=metadata.name if metadata else inventory.project_id,
        path=str(project_root),
        summary=metadata.summary if metadata else None,
        status=metadata.status if metadata else None,
        aspects=metadata.aspects if metadata else [],
        tags=metadata.tags if metadata else [],
        entity_counts=_entity_counts(entities, tasks),
    )
    return ProjectScan(
        project=project,
        entities=entities,
        tasks=tasks,
    )


def _entity_counts(entities: list[Entity], tasks: list[Task]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.kind] = counts.get(entity.kind, 0) + 1
    counts["task"] = len(tasks)
    return counts
```

The conversion intentionally uses `Entity.model_validate` and `Task.model_validate`; invalid Science inventory records must fail during refresh.

**Step 3: Update store to use inventory**

Edit `~/d/dashboard/backend/store.py`:

```python
from backend.inventory_indexer import scan_from_inventory
from backend.science_inventory import load_science_inventory
```

In the project state refresh path, replace:

```python
scan = scan_project(project_root)
```

with:

```python
inventory = load_science_inventory(project_root)
current_hashes = (inventory.content_hash, inventory.audit_hash)
if self._inventory_hashes.get(inventory.project_id) == current_hashes and inventory.project_id in self._scans:
    return
scan = scan_from_inventory(project_root, inventory)
self._inventory_hashes[scan.project.slug] = current_hashes
self._inventory_watch_paths[scan.project.slug] = tuple(inventory.watch_paths)
```

Add `_inventory_hashes` and `_inventory_watch_paths` dictionaries to the store initializer. The hash check skips dashboard analysis, quality summarization, and API cache replacement when Science reports unchanged content and warnings. Do not keep local file scanning as a fallback path.

Add a store regression test for the hash short-circuit:

```python
from science_model import DashboardConfig
from science_model.contracts.inventory_v1 import InventoryPayload
from science_model.graph import GraphData

from backend.analysis import ProjectAnalysis, QualitySummary


def test_store_skips_dashboard_rebuild_when_inventory_hashes_are_unchanged(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="project",
        content_hash="content-a",
        audit_hash="audit-a",
        entities=[],
        watch_paths=[],
    )
    calls = {"analysis": 0}

    monkeypatch.setattr("backend.store.load_science_inventory", lambda root: payload)

    def fake_analyze(scan, root):
        calls["analysis"] += 1
        return ProjectAnalysis(
            project_slug=scan.project.slug,
            entity_link_evidence={},
            available_graph_layers=[],
            graph_layer_summaries=[],
            quality_summary=QualitySummary(broken_refs=0, orphaned_graph_nodes=0),
            graph=GraphData(nodes=[], edges=[], domains={}, lod=1.0, total_nodes=0),
        )

    monkeypatch.setattr("backend.store.analyze_project_scan", fake_analyze)

    store = FileSystemStore(DashboardConfig(projects=[str(project)]))
    store.rescan("project")
    store.rescan("project")

    assert calls["analysis"] == 1


def test_store_rebuilds_when_inventory_hash_changes(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payloads = iter(
        [
            InventoryPayload(
                generated_at="2026-05-12T10:00:00Z",
                project_id="project",
                content_hash="content-a",
                audit_hash="audit-a",
                entities=[],
                watch_paths=[],
            ),
            InventoryPayload(
                generated_at="2026-05-12T10:01:00Z",
                project_id="project",
                content_hash="content-b",
                audit_hash="audit-a",
                entities=[],
                watch_paths=[],
            ),
        ]
    )
    calls = {"analysis": 0}

    monkeypatch.setattr("backend.store.load_science_inventory", lambda root: next(payloads))

    def fake_analyze(scan, root):
        calls["analysis"] += 1
        return ProjectAnalysis(
            project_slug=scan.project.slug,
            entity_link_evidence={},
            available_graph_layers=[],
            graph_layer_summaries=[],
            quality_summary=QualitySummary(broken_refs=0, orphaned_graph_nodes=0),
            graph=GraphData(nodes=[], edges=[], domains={}, lod=1.0, total_nodes=0),
        )

    monkeypatch.setattr("backend.store.analyze_project_scan", fake_analyze)

    store = FileSystemStore(DashboardConfig(projects=[str(project)]))
    store.rescan("project")
    store.rescan("project")

    assert calls["analysis"] == 2
```

The assertions must prove unchanged hashes skip rebuilds and changed hashes invalidate the cache.

**Step 4: Verify**

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_indexer.py tests/test_store.py -q
```

Expected: inventory conversion passes and store tests are updated to monkeypatch `load_science_inventory` instead of creating local markdown scans.

---

## Task 10: Replace Dashboard DAG Finding Synthesis With Inventory Candidates

**Files:**

- Edit: `~/d/dashboard/backend/attention.py`
- Edit: `~/d/dashboard/backend/findings.py`
- Create: `~/d/dashboard/tests/test_inventory_attention.py`
- Edit: `~/d/dashboard/tests/test_attention_api.py`

**Step 1: Write attention tests**

Create `~/d/dashboard/tests/test_inventory_attention.py`:

```python
from __future__ import annotations

from science_model.contracts.inventory_v1 import (
    InventoryFindingCandidate,
    InventoryPayload,
    InventorySourceLocation,
)

from backend.attention import findings_from_inventory_candidates


def test_findings_from_inventory_candidates_keep_dag_edge_as_target_not_entity() -> None:
    inventory = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="project",
        finding_candidates=[
            InventoryFindingCandidate(
                candidate_id="finding-candidate:dag-edge:h4:e001",
                title="Landscape topology supports convergence.",
                targets=["dag-edge:h4:e001"],
                source=InventorySourceLocation(adapter="dag", path="doc/figures/dags/h4.edges.yaml", address="e001"),
                reason="DAG edge contains claim-bearing interpretation text.",
            )
        ],
    )

    findings = findings_from_inventory_candidates(inventory)

    assert findings[0].claim_text == "Landscape topology supports convergence."
    assert findings[0].related_entities == ["dag-edge:h4:e001"]
    assert findings[0].primary_source == "doc/figures/dags/h4.edges.yaml"
```

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_attention.py -q
```

Expected: fails because `findings_from_inventory_candidates` does not exist.

**Step 2: Implement candidate conversion**

Edit `~/d/dashboard/backend/attention.py`:

```python
from science_model.contracts.inventory_v1 import InventoryPayload


def findings_from_inventory_candidates(inventory: InventoryPayload) -> list[AttentionFinding]:
    return [
        AttentionFinding(
            id=candidate.candidate_id,
            project_id=inventory.project_id,
            claim_text=candidate.title,
            primary_source=candidate.source.path,
            related_entities=candidate.targets,
            source_refs=[candidate.source.path],
            support_breakdown=SupportBreakdown(),
        )
        for candidate in inventory.finding_candidates
    ]
```

Add `SupportBreakdown` to the existing import from `backend.attention_models`.

**Step 3: Stop using local DAG edge synthesis**

Edit `~/d/dashboard/backend/findings.py` so project attention surfaces consume inventory candidates already attached to store state. Remove calls that scan `doc/figures/dags/*.edges.yaml` locally.

Delete `_findings_from_dag_edges`, remove the `candidates.extend(_findings_from_dag_edges(scan, project_root))` call from `extract_project_findings`, and remove the now-unused `yaml` import. Do not leave a wrapper that silently reintroduces dashboard-owned DAG parsing.

**Step 4: Verify**

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_attention.py tests/test_attention_api.py -q
```

Expected: attention APIs render Science-provided entities and `finding_candidate` records, while DAG edges remain graph addresses rather than dashboard entities.

---

## Task 11: Use Science Watch Paths In The Dashboard Watcher

**Files:**

- Edit: `~/d/dashboard/backend/watcher.py`
- Edit: `~/d/dashboard/backend/store.py`
- Create: `~/d/dashboard/tests/test_inventory_watcher.py`

**Step 1: Write watcher tests**

Create `~/d/dashboard/tests/test_inventory_watcher.py`:

```python
from __future__ import annotations

from pathlib import Path

from backend.watcher import project_watch_roots


def test_project_watch_roots_are_science_declared_paths(tmp_path) -> None:
    project = tmp_path / "project"
    for name in ("doc", "knowledge", "results"):
        (project / name).mkdir(parents=True)

    roots = project_watch_roots(project, ["doc", "knowledge", "results"])

    assert roots == [project / "doc", project / "knowledge", project / "results"]
```

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_watcher.py -q
```

Expected: fails because `project_watch_roots` does not exist.

**Step 2: Implement watch roots**

Edit `~/d/dashboard/backend/watcher.py`:

```python
def project_watch_roots(project_root: Path, watch_paths: Sequence[str]) -> list[Path]:
    roots: list[Path] = []
    for rel_path in watch_paths:
        root = project_root / rel_path
        if root.exists():
            roots.append(root)
    return roots
```

Update the watcher startup path to read `store.inventory_watch_paths(project_slug)` after the initial inventory load and register those roots instead of registering the whole project root or hard-coded subdirectories.

Add a store accessor:

```python
def inventory_watch_paths(self, project_slug: str) -> tuple[str, ...]:
    return self._inventory_watch_paths.get(project_slug, ())
```

**Step 3: Verify**

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest tests/test_inventory_watcher.py tests/test_store.py -q
```

Expected: watcher tests pass and project rescans still trigger when a Science-declared path changes.

---

## Task 12: Remove Dashboard Local Project Entity Scanning From Runtime

**Files:**

- Edit: `~/d/dashboard/backend/store.py`
- Edit: `~/d/dashboard/backend/indexer.py`
- Edit: `~/d/dashboard/tests/test_indexer.py`
- Edit: `~/d/dashboard/tests/test_api_projects.py`

**Step 1: Add a regression test that store does not call local scanning**

Add to `~/d/dashboard/tests/test_store.py`:

```python
from science_model import DashboardConfig
from science_model.contracts.inventory_v1 import InventoryPayload


def test_store_uses_science_inventory_not_local_scan(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="project",
        entities=[],
        watch_paths=[],
    )

    monkeypatch.setattr("backend.store.load_science_inventory", lambda root: payload)

    def fail_local_scan(root):
        raise AssertionError("dashboard local project scanning must not be used")

    monkeypatch.setattr("backend.store.scan_project", fail_local_scan, raising=False)

    store = FileSystemStore(DashboardConfig(projects=[str(project)]))
    store.rescan("project")

    assert store.list_projects()[0].path == str(project)
```

**Step 2: Remove runtime imports and calls**

Edit `~/d/dashboard/backend/store.py` to remove `scan_project` imports and references.

Leave `backend/indexer.py` in place only if tests or developer tooling still use it directly. If it is no longer used by runtime code, mark its tests as indexer-unit tests and keep them isolated from store/API tests until a later cleanup commit removes the module.

**Step 3: Verify zero local project content reads in store/API path**

Run:

```bash
cd ~/d/dashboard
rg "scan_project|_findings_from_dag_edges|doc/figures/dags|results/\\*\\*/datapackage" backend tests
uv run --frozen pytest tests/test_store.py tests/test_api_projects.py tests/test_attention_api.py -q
```

Expected:

- `rg` shows no runtime `backend/store.py` or API route calls to local project scanning.
- Tests pass with inventory monkeypatched.

---

## Task 13: End-To-End Contract Verification On Audit Projects

**Files:**

- Edit tests only if real mismatches are found.

**Step 1: Run Science inventory on both audit projects**

Run:

```bash
cd ~/d/science/science
uv run --frozen science entities inventory --format json --project ~/d/cancer/cancer-types/multiple-myeloma --output /tmp/myeloma-inventory.json
uv run --frozen science entities inventory --format json --project ~/d/natural-systems --output /tmp/natural-systems-inventory.json
```

Expected:

- Each command exits 0.
- Each second consecutive run finishes under 10 seconds on a warm local checkout.
- `/tmp/myeloma-inventory.json` and `/tmp/natural-systems-inventory.json` validate as `InventoryPayload`.
- The payloads include `content_hash`, `audit_hash`, `watch_paths`, `entities`, `graph_addresses`, `finding_candidates`, and `warnings`.

**Step 2: Enforce the warm-run performance budget**

Run:

```bash
cd ~/d/science/science
uv run --frozen python scripts/check_inventory_perf.py --project ~/d/cancer/cancer-types/multiple-myeloma --project ~/d/natural-systems --max-seconds 10
```

Create `~/d/science/science/scripts/check_inventory_perf.py` if it does not exist:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from science_tool.entities_inventory import build_inventory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="append", required=True)
    parser.add_argument("--max-seconds", type=float, required=True)
    args = parser.parse_args()

    failures: list[str] = []
    for raw_project in args.project:
        project = Path(raw_project)
        build_inventory(project)
        started = perf_counter()
        build_inventory(project)
        elapsed = perf_counter() - started
        print(f"{project}: {elapsed:.3f}s")
        if elapsed > args.max_seconds:
            failures.append(f"{project}: {elapsed:.3f}s > {args.max_seconds:.3f}s")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
```

Expected: command exits 0 and prints a measured second-run duration for each audit project.

This v1 performance gate measures the Science inventory contract because dashboard refresh cost changes with the hash cache path. If dashboard responsiveness becomes the bottleneck, add a separate dashboard-side perf gate around `FileSystemStore.rescan()` instead of weakening the Science inventory budget.

**Step 3: Validate payloads through dashboard import path**

Run:

```bash
cd ~/d/dashboard
uv run --frozen python -c "from pathlib import Path; from science_model.contracts.inventory_v1 import InventoryPayload; InventoryPayload.model_validate_json(Path('/tmp/myeloma-inventory.json').read_text()); InventoryPayload.model_validate_json(Path('/tmp/natural-systems-inventory.json').read_text())"
```

Expected: command exits 0.

**Step 4: Run full backend verification**

Run:

```bash
cd ~/d/dashboard
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected: all pass.

**Step 5: Run Science verification**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected: all pass.

---

## Rollback Commitment

Tasks 9 through 12 deliberately remove dashboard-owned project parsing from the runtime path. If the inventory contract is missing a field after merge, rollback is a revert of the dashboard integration commits for Tasks 9 through 12 or a forward fix to the Science inventory contract. Do not reintroduce a silent dashboard fallback scanner.

---

## Implementation Order

Execute in this order:

1. Task 1: shared inventory contract.
2. Task 2: workflow-run adapter.
3. Task 3: DAG addresses and finding candidates.
4. Task 4: inventory builder and CLI.
5. Task 5: identity health checks and prose-reference warnings.
6. Task 6: local kind registration.
7. Task 7: audit and migration commands.
8. Task 8: dashboard inventory client.
9. Task 9: dashboard inventory-to-project-state conversion.
10. Task 10: dashboard attention from inventory candidates.
11. Task 11: dashboard watch paths.
12. Task 12: remove dashboard local scanner from runtime.
13. Task 13: end-to-end verification.

Do not start dashboard runtime rewiring before Task 4 passes. The dashboard must validate the exact Science contract it imports, not a copied schema.

---

## Acceptance Criteria

- `science entities inventory --format json --project <path>` emits schema version `1` and validates through `science_model.contracts.inventory_v1.InventoryPayload`.
- The inventory payload exposes separate `content_hash` and `audit_hash`, both stable across `generated_at` changes.
- DAG edges use declared edge IDs in addresses; YAML array order never affects the address.
- Claim-bearing DAG edges become `finding_candidate` records, not `finding` entities.
- `results/**/datapackage.json` records are represented by Science through `WorkflowRunAdapter`.
- Inventory entity source adapters come from `load_project_sources`, not path-string heuristics.
- `InventoryEntity.data` excludes fields promoted to top-level contract fields.
- `science health` and inventory warnings classify unresolved/deprecated markdown prose references as `warning`.
- Unknown kind resolution has an idempotent `science entities register-kind` path.
- Identifier migration collision checks include existing canonical IDs and newly planned IDs.
- Identifier audit and migration commands produce dry-run JSON reports for the myeloma and natural-systems projects.
- Dashboard store/API runtime uses the in-process Science inventory builder and does not read project markdown, DAG YAML, task markdown, or datapackage files directly.
- Dashboard watcher roots come from inventory `watch_paths`.
- Second consecutive inventory runs on both audit projects complete in under 10 seconds on a warm local checkout.

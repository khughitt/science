# RG2 Virtual Member Payload Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement RG2 by extending the generic `member_of` substrate with virtual payload resolution, then provide the first concrete resolver for `bio.reference_graph` members: node row plus directly incident edges.

**Architecture:** Keep the generic substrate small: it resolves a promoted `member_of` dataset to its parent and dispatches by parent collection profile. The concrete `bio.reference_graph` resolver reads the pinned parent node/edge projections once, returns a typed graph-member payload, and raises explicit errors for unresolved keys, unsupported collection kinds, or declared-but-unavailable resources. Gene-set payloads are detected but intentionally left as an explicit D2 follow-up, not silently handled.

**Tech Stack:** Python 3.12, dataclasses, existing commons adapter/resolver/datapackage helpers, `pytest`, `ruff`, `pyright`.

---

## Current Context

RG1 is implemented:

- `science/src/science_tool/commons/member.py` parses `derivation.kind: member_of` and returns `ResolvedMember`, but it does not resolve payload bytes.
- `science/src/science_tool/commons/reference_graph.py` parses node and edge CSV projections into `ReferenceGraphNode` and `ReferenceGraphEdge`.
- `science/src/science_tool/commons/reference_graph_resources.py` can read local/project reference graph resources and can fall back to the process-level commons resolver.
- `science/src/science_tool/validate/checks/reference_graphs.py` already validates promoted graph members against parsed node indexes.

RG2 must add runtime payload resolution without changing identity semantics:

- Exact `member_key` equality remains identity.
- Deprecated/withdrawn graph members remain resolvable payloads; callers decide how to warn.
- Cross-key relations such as `xref`, `equivalent_to`, and `close_match` remain edges, not identity rewrites.
- A graph-member payload is the node-index row plus directly incident normalized edges.
- Missing `edge_resource` means “no normalized edge projection exists”; a declared `edge_resource` that cannot resolve is an error.

## File Structure

- Modify `science/src/science_tool/commons/reference_graph_resources.py`
  - Add explicit commons-root/data-root CSV readers for node and edge resources.
  - Do not read or hash the large graph artifact for payload resolution.
- Create `science/src/science_tool/commons/reference_graph_payload.py`
  - Own `ReferenceGraphMemberPayload`.
  - Resolve one graph member from a parent `CommonsEntityRecord`, `MemberOf`, and pinned node/edge resources.
- Create `science/src/science_tool/commons/member_payload.py`
  - Own generic `VirtualMemberPayload`, payload errors, and dispatch from `member_of` parent profile to concrete resolvers.
- Modify `science/src/science_tool/commons/__init__.py`
  - Re-export the public RG2 payload API.
- Modify `docs/plans/2026-05-31-bio-reference-graph-design.md`
  - Mark RG2 implemented locally once code lands.
- Modify `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
  - Update the non-tabular reference status from “RG2 pending” to “RG2 implemented locally”.
- Test `science/tests/test_commons_reference_graph_resources.py`
  - New focused resource-helper tests.
- Test `science/tests/test_commons_member_payload.py`
  - Generic dispatch and explicit unsupported gene-set behavior.
- Test `science/tests/test_commons_reference_graph_payload.py`
  - Concrete graph-member payload behavior.

## Task 1: Explicit Commons Readers for Reference Graph Projections

**Files:**
- Modify: `science/src/science_tool/commons/reference_graph_resources.py`
- Create: `science/tests/test_commons_reference_graph_resources.py`

- [ ] **Step 1: Write failing tests for explicit commons node/edge readers**

Create `science/tests/test_commons_reference_graph_resources.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_commons_reference_graph(root: Path, data_root: Path, *, include_edges: bool = True) -> dict[str, object]:
    commons = root / "commons"
    dataset_dir = commons / "datasets" / "mondo"
    dataset_dir.mkdir(parents=True)
    nodes = (
        b"member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        b"MONDO:0005148,term,multiple myeloma,active,,[]\n"
    )
    edges = b"subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n"
    graph = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
    data_dir = data_root / "mondo"
    data_dir.mkdir(parents=True)
    data_dir.joinpath("nodes.csv").write_bytes(nodes)
    data_dir.joinpath("graph.nt").write_bytes(graph)
    resources = [
        {"name": "graph", "path": "graph.nt", "hash": f"sha256:{_sha256(graph)}"},
        {"name": "nodes", "path": "nodes.csv", "hash": f"sha256:{_sha256(nodes)}"},
    ]
    if include_edges:
        data_dir.joinpath("edges.csv").write_bytes(edges)
        resources.append({"name": "edges", "path": "edges.csv", "hash": f"sha256:{_sha256(edges)}"})
    dataset_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"name": "mondo", "resources": resources}),
        encoding="utf-8",
    )
    dataset_dir.joinpath("entity.md").write_text(
        """\
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0
id: dataset:mondo
type: dataset
title: MONDO
version: "1.0.0"
datapackage: datapackage.yaml
status: active
origin: external
tier: use-now
source_class: reference
created: "2026-05-31"
updated: "2026-05-31"
access:
  level: public
  availability: available
  verified: true
graph_resource: graph
graph_format: rdf_ntriples
member_key_space:
  kind: curie
  prefixes: [MONDO]
  resolution_status: resolved
node_index_resource: nodes
member_count: 1
---
""",
        encoding="utf-8",
    )
    fm: dict[str, object] = {
        "id": "dataset:mondo",
        "graph_resource": "graph",
        "node_index_resource": "nodes",
        "member_count": 1,
    }
    if include_edges:
        fm["edge_resource"] = "edges"
        fm["edge_count"] = 1
    return fm


def test_read_commons_node_rows_uses_explicit_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fm = _write_commons_reference_graph(tmp_path, tmp_path / "data")
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)

    rows = read_commons_node_rows(
        fm,
        commons_root=tmp_path / "commons",
        data_root=tmp_path / "data",
    )

    assert rows == [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        }
    ]


def test_read_commons_edge_rows_returns_none_when_edge_resource_absent(tmp_path: Path) -> None:
    fm = _write_commons_reference_graph(tmp_path, tmp_path / "data", include_edges=False)

    rows = read_commons_edge_rows(
        fm,
        commons_root=tmp_path / "commons",
        data_root=tmp_path / "data",
    )

    assert rows is None


def test_read_commons_edge_rows_reads_declared_edges(tmp_path: Path) -> None:
    fm = _write_commons_reference_graph(tmp_path, tmp_path / "data")

    rows = read_commons_edge_rows(
        fm,
        commons_root=tmp_path / "commons",
        data_root=tmp_path / "data",
    )

    assert rows == [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "",
            "dataset_usage": "[]",
        }
    ]


def test_read_commons_edge_rows_returns_exception_when_declared_edge_file_is_missing(tmp_path: Path) -> None:
    fm = _write_commons_reference_graph(tmp_path, tmp_path / "data")
    (tmp_path / "data" / "mondo" / "edges.csv").unlink()

    rows = read_commons_edge_rows(
        fm,
        commons_root=tmp_path / "commons",
        data_root=tmp_path / "data",
    )

    assert isinstance(rows, Exception)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_reference_graph_resources.py -q
```

Expected: FAIL with `ImportError` for `read_commons_node_rows` / `read_commons_edge_rows`.

- [ ] **Step 3: Implement explicit commons CSV readers**

In `science/src/science_tool/commons/reference_graph_resources.py`, add these functions near the existing `read_node_rows` / `read_edge_rows` helpers:

```python
def _read_commons_csv_resource(
    fm: dict[str, Any],
    *,
    kind: ResourceKind,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        resolved = resolve(
            dataset_id,
            resource_name,
            commons_root=commons_root,
            data_root=data_root,
        )
    except CommonsError as exc:
        return exc
    return _read_csv(resolved.path)


def read_commons_node_rows(
    fm: dict[str, Any],
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    return _read_commons_csv_resource(
        fm,
        kind="node",
        commons_root=commons_root,
        data_root=data_root,
    )


def read_commons_edge_rows(
    fm: dict[str, Any],
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    return _read_commons_csv_resource(
        fm,
        kind="edge",
        commons_root=commons_root,
        data_root=data_root,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_reference_graph_resources.py -q
```

Expected: PASS.

- [ ] **Step 5: Run existing RG1 resource tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/validate/test_checks_reference_graphs.py::test_reference_graph_resource_helper_reads_local_rows_and_checks_graph_availability science/tests/validate/test_checks_reference_graphs.py::test_graph_resource_available_uses_commons_existence_without_resolve -q
```

Expected: PASS. This verifies the new commons readers did not change local-resource behavior or reintroduce graph-resource hashing.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/reference_graph_resources.py science/tests/test_commons_reference_graph_resources.py
git commit -m "feat(commons): read reference graph projections from commons roots"
```

## Task 2: Generic Virtual Member Payload Dispatch

**Files:**
- Create: `science/src/science_tool/commons/member_payload.py`
- Modify: `science/src/science_tool/commons/__init__.py`
- Test: `science/tests/test_commons_member_payload.py`

- [ ] **Step 1: Write failing generic dispatch tests**

Create `science/tests/test_commons_member_payload.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.commons.member_payload import (
    UnsupportedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)


def _entity(dataset_dir: Path, *, dataset_id: str, schema_profile: str, extra: str = "") -> None:
    slug = dataset_id.split(":", 1)[1]
    dataset_dir.joinpath(slug).mkdir(parents=True)
    dataset_dir.joinpath(slug, "entity.md").write_text(
        f"""\
---
schema_profile: {schema_profile}
id: {dataset_id}
type: dataset
title: {slug}
version: "1.0.0"
datapackage: datapackage.yaml
status: active
origin: external
tier: use-now
source_class: reference
created: "2026-05-31"
updated: "2026-05-31"
access:
  level: public
  availability: available
  verified: true
{extra}---
""",
        encoding="utf-8",
    )
    dataset_dir.joinpath(slug, "datapackage.yaml").write_text(
        yaml.safe_dump({"name": slug, "resources": [{"name": "empty", "path": "empty.txt", "hash": "sha256:" + "0" * 64}]}),
        encoding="utf-8",
    )


def _member(dataset_dir: Path, *, member_id: str, parent_dataset: str, member_key: str) -> None:
    slug = member_id.split(":", 1)[1]
    dataset_dir.joinpath(slug).mkdir(parents=True)
    dataset_dir.joinpath(slug, "entity.md").write_text(
        f"""\
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0
id: {member_id}
type: dataset
title: member
version: "1.0.0"
datapackage: virtual:member-of
status: active
origin: derived
tier: use-now
source_class: reference
created: "2026-05-31"
updated: "2026-05-31"
parent_dataset: {parent_dataset}
derivation:
  kind: member_of
  parent_dataset: {parent_dataset}
  member_key: {member_key}
member_kind: term
label: member
status: active
---
""",
        encoding="utf-8",
    )
    dataset_dir.joinpath(slug, "datapackage.yaml").write_text(
        yaml.safe_dump({"name": slug, "resources": [{"name": "virtual", "path": "virtual.txt", "hash": "sha256:" + "0" * 64}]}),
        encoding="utf-8",
    )


def test_resolve_virtual_member_payload_returns_none_for_non_member(tmp_path: Path) -> None:
    datasets = tmp_path / "commons" / "datasets"
    _entity(
        datasets,
        dataset_id="dataset:plain",
        schema_profile="science-entity-base/1.0+dataset/1.0",
    )

    assert resolve_virtual_member_payload("dataset:plain", commons_root=tmp_path / "commons") is None


def test_resolve_virtual_member_payload_rejects_unsupported_parent_collection(tmp_path: Path) -> None:
    datasets = tmp_path / "commons" / "datasets"
    _entity(
        datasets,
        dataset_id="dataset:parent",
        schema_profile="science-entity-base/1.0+dataset/1.0",
    )
    _member(datasets, member_id="dataset:member", parent_dataset="dataset:parent", member_key="K")

    with pytest.raises(UnsupportedMemberPayloadError, match="unsupported parent collection profile"):
        resolve_virtual_member_payload("dataset:member", commons_root=tmp_path / "commons")


def test_resolve_virtual_member_payload_detects_geneset_parent_as_explicit_d2_followup(tmp_path: Path) -> None:
    datasets = tmp_path / "commons" / "datasets"
    _entity(
        datasets,
        dataset_id="dataset:reactome",
        schema_profile="science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
        extra=(
            "identifier_space:\n"
            "  tier: gene\n"
            "  namespace: entrez\n"
            "  registry: dataset:gene-crosswalk-hgnc\n"
            "  resolution_status: resolved\n"
            "members_resource: sets\n"
            "member_key_column: set_key\n"
            "n_sets: 1\n"
            "set_size_summary:\n"
            "  min: 1\n"
            "  median: 1\n"
            "  max: 1\n"
        ),
    )
    _member(datasets, member_id="dataset:pathway", parent_dataset="dataset:reactome", member_key="R-HSA-1")

    with pytest.raises(UnsupportedMemberPayloadError, match="bio.geneset virtual payload resolution is reserved for D2"):
        resolve_virtual_member_payload("dataset:pathway", commons_root=tmp_path / "commons")


def test_virtual_member_payload_dataclass_is_generic_container() -> None:
    payload = VirtualMemberPayload(
        member_id="dataset:member",
        parent_dataset="dataset:parent",
        parent_slug="parent",
        member_key="K",
        payload_kind="demo",
        payload={"k": "v"},
    )

    assert payload.payload["k"] == "v"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_member_payload.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `science_tool.commons.member_payload`.

- [ ] **Step 3: Implement generic payload dispatch**

Create `science/src/science_tool/commons/member_payload.py`:

```python
"""Virtual payload resolution for promoted reference-collection members."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.config import resolve_commons_data_root, resolve_commons_root
from science_tool.commons.geneset import is_geneset_frontmatter
from science_tool.commons.member import parse_member_of
from science_tool.commons.reference_graph import is_reference_graph_frontmatter


class MemberPayloadError(ValueError):
    """A promoted member payload cannot be resolved."""


class UnsupportedMemberPayloadError(MemberPayloadError):
    """The parent collection kind has no virtual payload resolver."""


class UnresolvedMemberPayloadError(MemberPayloadError):
    """The promoted member key does not resolve inside its parent payload surface."""


@dataclass(frozen=True, slots=True)
class VirtualMemberPayload:
    member_id: str
    parent_dataset: str
    parent_slug: str
    member_key: str
    payload_kind: str
    payload: dict[str, Any]


def _unsupported_message(parent: CommonsEntityRecord) -> str:
    profile = parent.schema_profile
    if is_geneset_frontmatter(parent.frontmatter):
        return "bio.geneset virtual payload resolution is reserved for D2"
    return f"unsupported parent collection profile for {parent.canonical_id}: {profile}"


def resolve_virtual_member_payload(
    member_id: str,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> VirtualMemberPayload | None:
    commons_root = commons_root or resolve_commons_root()
    data_root = data_root or resolve_commons_data_root()
    adapter = CommonsEntityAdapter(commons_root)
    member = adapter.load(member_id)
    member_of = parse_member_of(member.frontmatter)
    if member_of is None:
        return None
    parent = adapter.load(member_of.parent_dataset)
    if is_reference_graph_frontmatter(parent.frontmatter):
        from science_tool.commons.reference_graph_payload import resolve_reference_graph_member_payload

        graph_payload = resolve_reference_graph_member_payload(
            parent=parent,
            member_of=member_of,
            commons_root=commons_root,
            data_root=data_root,
        )
        return VirtualMemberPayload(
            member_id=member.canonical_id,
            parent_dataset=parent.canonical_id,
            parent_slug=parent.slug,
            member_key=member_of.member_key,
            payload_kind="bio.reference_graph.member",
            payload=graph_payload.to_dict(),
        )
    raise UnsupportedMemberPayloadError(_unsupported_message(parent))
```

Also add `is_geneset_frontmatter` to `science/src/science_tool/commons/geneset.py`:

```python
GENESET_PROFILE_TOKEN = "+bio.geneset/"


def is_geneset_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and GENESET_PROFILE_TOKEN in f"+{profile}"
```

- [ ] **Step 4: Add public exports**

Modify `science/src/science_tool/commons/__init__.py`:

```python
from science_tool.commons.member_payload import (
    MemberPayloadError,
    UnsupportedMemberPayloadError,
    UnresolvedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)
```

Add the same five names to `__all__`.

- [ ] **Step 5: Run tests to verify generic behavior passes**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_member_payload.py -q
```

Expected: the non-reference-graph tests pass; if the reference-graph import path is not covered yet, the whole file should pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/member_payload.py science/src/science_tool/commons/geneset.py science/src/science_tool/commons/__init__.py science/tests/test_commons_member_payload.py
git commit -m "feat(commons): add virtual member payload dispatch"
```

## Task 3: Reference Graph Member Payload Resolver

**Files:**
- Create: `science/src/science_tool/commons/reference_graph_payload.py`
- Test: `science/tests/test_commons_reference_graph_payload.py`

- [ ] **Step 1: Write failing graph payload tests**

Create `science/tests/test_commons_reference_graph_payload.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from science_tool.commons.member_payload import (
    MemberPayloadError,
    UnresolvedMemberPayloadError,
    resolve_virtual_member_payload,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_graph_commons(tmp_path: Path, *, member_key: str = "MONDO:0005148", include_edges: bool = True) -> tuple[Path, Path]:
    commons = tmp_path / "commons"
    data_root = tmp_path / "data"
    parent_dir = commons / "datasets" / "mondo"
    member_dir = commons / "datasets" / "mondo-0005148"
    parent_dir.mkdir(parents=True)
    member_dir.mkdir(parents=True)
    graph = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
    nodes = (
        b"member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        b'MONDO:0005148,term,multiple myeloma,active,,\"[{\"\"ref\"\":\"\"dataset:ordo\"\",\"\"role\"\":\"\"upstream\"\"}]\"\n'
        b"MONDO:0000001,term,disease,active,,[]\n"
        b"MONDO:obsolete,term,old label,deprecated,MONDO:0005148,[]\n"
    )
    edges = (
        b"subject,predicate,object,evidence,dataset_usage\n"
        b"MONDO:0005148,is_a,MONDO:0000001,,[]\n"
        b"MONDO:0000002,related_to,MONDO:0005148,ECO:1,[]\n"
        b"MONDO:0000002,is_a,MONDO:0000001,,[]\n"
    )
    data_dir = data_root / "mondo"
    data_dir.mkdir(parents=True)
    data_dir.joinpath("graph.nt").write_bytes(graph)
    data_dir.joinpath("nodes.csv").write_bytes(nodes)
    resources = [
        {"name": "graph", "path": "graph.nt", "hash": f"sha256:{_sha256(graph)}"},
        {"name": "nodes", "path": "nodes.csv", "hash": f"sha256:{_sha256(nodes)}"},
    ]
    edge_yaml = ""
    if include_edges:
        data_dir.joinpath("edges.csv").write_bytes(edges)
        resources.append({"name": "edges", "path": "edges.csv", "hash": f"sha256:{_sha256(edges)}"})
        edge_yaml = "edge_resource: edges\nedge_count: 3\n"
    parent_dir.joinpath("datapackage.yaml").write_text(yaml.safe_dump({"name": "mondo", "resources": resources}), encoding="utf-8")
    parent_dir.joinpath("entity.md").write_text(
        f"""\
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0
id: dataset:mondo
type: dataset
title: MONDO
version: "1.0.0"
datapackage: datapackage.yaml
status: active
origin: external
tier: use-now
source_class: reference
created: "2026-05-31"
updated: "2026-05-31"
access:
  level: public
  availability: available
  verified: true
graph_resource: graph
graph_format: rdf_ntriples
member_key_space:
  kind: curie
  prefixes: [MONDO]
  resolution_status: resolved
node_index_resource: nodes
member_count: 3
{edge_yaml}---
""",
        encoding="utf-8",
    )
    member_dir.joinpath("datapackage.yaml").write_text(yaml.safe_dump({"name": "mondo-0005148", "resources": [{"name": "virtual", "path": "virtual.txt", "hash": "sha256:" + "0" * 64}]}), encoding="utf-8")
    member_dir.joinpath("entity.md").write_text(
        f"""\
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0
id: dataset:mondo-0005148
type: dataset
title: MONDO member
version: "1.0.0"
datapackage: virtual:member-of
status: active
origin: derived
tier: use-now
source_class: reference
created: "2026-05-31"
updated: "2026-05-31"
parent_dataset: dataset:mondo
derivation:
  kind: member_of
  parent_dataset: dataset:mondo
  member_key: {member_key}
member_kind: term
label: multiple myeloma
status: active
---
""",
        encoding="utf-8",
    )
    return commons, data_root


def test_resolve_reference_graph_member_payload_returns_node_and_incident_edges(tmp_path: Path) -> None:
    commons, data_root = _write_graph_commons(tmp_path)

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons,
        data_root=data_root,
    )

    assert payload is not None
    assert payload.payload_kind == "bio.reference_graph.member"
    assert payload.member_key == "MONDO:0005148"
    assert payload.payload["node"]["label"] == "multiple myeloma"
    assert payload.payload["node"]["dataset_usage"][0]["ref"] == "dataset:ordo"
    assert {(edge["subject"], edge["predicate"], edge["object"]) for edge in payload.payload["incident_edges"]} == {
        ("MONDO:0005148", "is_a", "MONDO:0000001"),
        ("MONDO:0000002", "related_to", "MONDO:0005148"),
    }


def test_resolve_reference_graph_member_payload_allows_missing_edge_resource(tmp_path: Path) -> None:
    commons, data_root = _write_graph_commons(tmp_path, include_edges=False)

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons,
        data_root=data_root,
    )

    assert payload is not None
    assert payload.payload["incident_edges"] == []


def test_resolve_reference_graph_member_payload_errors_when_declared_edge_file_is_missing(tmp_path: Path) -> None:
    commons, data_root = _write_graph_commons(tmp_path)
    (data_root / "mondo" / "edges.csv").unlink()

    with pytest.raises(MemberPayloadError, match="edge resource cannot be read"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons,
            data_root=data_root,
        )


def test_resolve_reference_graph_member_payload_raises_for_absent_member_key(tmp_path: Path) -> None:
    commons, data_root = _write_graph_commons(tmp_path, member_key="MONDO:missing")

    with pytest.raises(UnresolvedMemberPayloadError, match="MONDO:missing"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons,
            data_root=data_root,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_reference_graph_payload.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `science_tool.commons.reference_graph_payload`, or a dispatch failure if Task 2 imported it lazily.

- [ ] **Step 3: Implement graph payload resolver**

Create `science/src/science_tool/commons/reference_graph_payload.py`:

```python
"""Virtual payload resolution for bio.reference_graph members."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.member import MemberOf
from science_tool.commons.member_payload import MemberPayloadError, UnresolvedMemberPayloadError
from science_tool.commons.reference_graph import (
    ReferenceGraphCollectionError,
    ReferenceGraphEdge,
    ReferenceGraphNode,
    parse_edge_rows,
    parse_node_index_rows,
)
from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows


@dataclass(frozen=True, slots=True)
class ReferenceGraphMemberPayload:
    node: ReferenceGraphNode
    incident_edges: tuple[ReferenceGraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": {
                "member_key": self.node.member_key,
                "member_kind": self.node.member_kind,
                "label": self.node.label,
                "status": self.node.status,
                "replaced_by": list(self.node.replaced_by),
                "dataset_usage": list(self.node.dataset_usage),
            },
            "incident_edges": [
                {
                    "subject": edge.subject,
                    "predicate": edge.predicate,
                    "object": edge.object,
                    "evidence": edge.evidence,
                    "dataset_usage": list(edge.dataset_usage),
                }
                for edge in self.incident_edges
            ],
        }


def _raise_resource_error(label: str, result: object) -> None:
    if isinstance(result, Exception):
        raise MemberPayloadError(f"{label} resource cannot be read: {result}") from result
    raise MemberPayloadError(f"{label} resource is unavailable")


def resolve_reference_graph_member_payload(
    *,
    parent: CommonsEntityRecord,
    member_of: MemberOf,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ReferenceGraphMemberPayload:
    node_rows = read_commons_node_rows(
        parent.frontmatter,
        commons_root=commons_root,
        data_root=data_root,
    )
    if not isinstance(node_rows, list):
        _raise_resource_error("node index", node_rows)
    try:
        nodes = parse_node_index_rows(node_rows)
    except ReferenceGraphCollectionError as exc:
        raise MemberPayloadError(f"node index is malformed: {exc}") from exc
    node_by_key = {node.member_key: node for node in nodes}
    node = node_by_key.get(member_of.member_key)
    if node is None:
        raise UnresolvedMemberPayloadError(
            f"member_key {member_of.member_key!r} is absent from {parent.canonical_id}"
        )

    edge_rows = read_commons_edge_rows(
        parent.frontmatter,
        commons_root=commons_root,
        data_root=data_root,
    )
    if edge_rows is None:
        return ReferenceGraphMemberPayload(node=node, incident_edges=())
    if isinstance(edge_rows, Exception):
        _raise_resource_error("edge", edge_rows)
    try:
        edges = parse_edge_rows(edge_rows)
    except ReferenceGraphCollectionError as exc:
        raise MemberPayloadError(f"edge resource is malformed: {exc}") from exc
    incident_edges = tuple(
        edge for edge in edges if edge.subject == member_of.member_key or edge.object == member_of.member_key
    )
    return ReferenceGraphMemberPayload(node=node, incident_edges=incident_edges)
```

- [ ] **Step 4: Run graph payload tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_reference_graph_payload.py -q
```

Expected: PASS.

- [ ] **Step 5: Run generic dispatch tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_member_payload.py -q
```

Expected: PASS. This confirms unsupported gene-set parents remain explicit and graph parents dispatch through the concrete resolver.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/reference_graph_payload.py science/tests/test_commons_reference_graph_payload.py science/tests/test_commons_member_payload.py
git commit -m "feat(commons): resolve reference graph member payloads"
```

## Task 4: Public API Coverage and Documentation Status

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py`
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
- Test: `science/tests/test_commons_member_payload.py`

- [ ] **Step 1: Add export coverage test**

Append to `science/tests/test_commons_member_payload.py`:

```python
def test_virtual_member_payload_api_is_exported_from_commons_package() -> None:
    from science_tool.commons import VirtualMemberPayload as ExportedPayload
    from science_tool.commons import resolve_virtual_member_payload as exported_resolver

    assert ExportedPayload is VirtualMemberPayload
    assert exported_resolver is resolve_virtual_member_payload
```

- [ ] **Step 2: Run export test to verify it fails if exports are missing**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_member_payload.py::test_virtual_member_payload_api_is_exported_from_commons_package -q
```

Expected: PASS if Task 2 already added exports; otherwise FAIL with `ImportError`.

- [ ] **Step 3: Verify public exports are complete**

Confirm `science/src/science_tool/commons/__init__.py` contains the Task 2 import:

```python
from science_tool.commons.member_payload import (
    MemberPayloadError,
    UnsupportedMemberPayloadError,
    UnresolvedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)
```

Confirm `__all__` contains:

```python
    "MemberPayloadError",
    "UnsupportedMemberPayloadError",
    "UnresolvedMemberPayloadError",
    "VirtualMemberPayload",
    "resolve_virtual_member_payload",
```

- [ ] **Step 4: Update reference graph design status**

In `docs/plans/2026-05-31-bio-reference-graph-design.md`, update:

```markdown
Status: RG1 implemented locally; RG2+ pending
```

to:

```markdown
Status: RG1 and RG2 implemented locally; RG3+ pending
```

Update the phasing table:

```markdown
| RG2 | Virtual member resolution and B materialization hooks for unpromoted graph members | pending |
```

to:

```markdown
| RG2 | Virtual member payload resolution for promoted graph members; payload includes node row plus directly incident edges and exposes member-level `dataset_usage` for later B hooks | implemented locally |
```

Update the paragraph below the table to say:

```markdown
RG2 is implemented locally for promoted `bio.reference_graph.member` datasets. The generic
`member_of` payload dispatcher now detects unsupported collection kinds explicitly, and the
reference-graph resolver returns the member node row plus directly incident normalized edges.
Automated B materialization from unpromoted graph members remains RG3+/B follow-up work; RG2
preserves the node/edge `dataset_usage` data needed for that work.
```

Replace the following stale dependency paragraph:

```markdown
RG2/RG3 depend on a generic virtual-member slice resolver: given a `member_of` child dataset, resolve the
parent artifact and return the member payload. Implementing that resolver here should benefit D2's
deferred promoted gene-set members as well. If that generic resolver is not implemented in RG2/RG3, those
phases are blocked on the equivalent D2 substrate.
```

with:

```markdown
RG2 implemented the generic virtual-member payload dispatcher and the first concrete
`bio.reference_graph.member` resolver. D2 can now add the sibling `bio.geneset.member` resolver without
reopening the generic dispatch boundary. Unpromoted-member B materialization remains separate follow-up
work because RG2 only returns payload data; it does not emit influence graph records.
```

Replace the final `## 11. Next step` section with:

```markdown
## 11. Next step

RG1 and RG2 are implemented locally. Next, plan RG3/RG4 follow-ups: broader graph-member promotion
workflows, unpromoted-member B materialization, and the first real MONDO or GO commons recipe with
pinned release artifacts. Later non-molecular identity resolvers remain subsequent phases.
```

- [ ] **Step 5: Update umbrella status**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update the non-tabular reference bullet from:

```markdown
`bio.reference_graph` RG1 is implemented for pinned graph-shaped reference datasets with node-index validation. Real GO/MONDO/Open Targets recipes,
virtual graph-member payload resolution, promoted graph members, and non-molecular identity resolvers
remain follow-up work.
```

to:

```markdown
`bio.reference_graph` RG1 and RG2 are implemented for pinned graph-shaped reference datasets:
RG1 validates node indexes, and RG2 resolves promoted graph-member virtual payloads as node rows plus
directly incident edges. Real GO/MONDO/Open Targets recipes, broader graph-member promotion workflows,
unpromoted-member B materialization, and non-molecular identity resolvers remain follow-up work.
```

- [ ] **Step 6: Run docs grep to verify status wording**

Run:

```bash
rg -n "RG2 is now|Next, plan RG2|RG2/RG3 depend|RG1 is implemented locally|virtual graph-member payload resolution, promoted" docs/plans/2026-05-31-bio-reference-graph-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
```

Expected: no output. These stale pre-RG2 phrases must be gone.

Then run:

```bash
rg -n "RG2|unpromoted-member B|promoted graph-member virtual payloads" docs/plans/2026-05-31-bio-reference-graph-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
```

Expected: output shows RG2 implemented locally and does not claim unpromoted-member B materialization shipped.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/commons/__init__.py science/tests/test_commons_member_payload.py docs/plans/2026-05-31-bio-reference-graph-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
git commit -m "docs: update reference graph rg2 status"
```

## Task 5: Final Verification

**Files:**
- No planned file edits.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_commons_member.py science/tests/test_commons_reference_graph.py science/tests/test_commons_reference_graph_resources.py science/tests/test_commons_member_payload.py science/tests/test_commons_reference_graph_payload.py science/tests/validate/test_checks_reference_graphs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatter/linter on touched files**

Run:

```bash
uv run --frozen --project science ruff check science/src/science_tool/commons/member.py science/src/science_tool/commons/member_payload.py science/src/science_tool/commons/reference_graph.py science/src/science_tool/commons/reference_graph_payload.py science/src/science_tool/commons/reference_graph_resources.py science/src/science_tool/commons/geneset.py science/src/science_tool/commons/__init__.py science/tests/test_commons_reference_graph_resources.py science/tests/test_commons_member_payload.py science/tests/test_commons_reference_graph_payload.py
```

Expected: PASS.

- [ ] **Step 3: Run pyright on touched implementation and tests**

Run:

```bash
uv run --frozen --project science pyright science/src/science_tool/commons/member_payload.py science/src/science_tool/commons/reference_graph_payload.py science/src/science_tool/commons/reference_graph_resources.py science/src/science_tool/commons/geneset.py science/tests/test_commons_reference_graph_resources.py science/tests/test_commons_member_payload.py science/tests/test_commons_reference_graph_payload.py
```

Expected: `0 errors`.

- [ ] **Step 4: Check whitespace**

Run:

```bash
rtk git diff --check
```

Expected: no output.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
rtk git diff --stat HEAD~4..HEAD
```

Expected: changed files match this plan; no unrelated files are included.

## Self-Review Checklist

- Spec coverage:
  - Generic `member_of` extension: Tasks 2 and 4.
  - Graph-member payload = node row plus directly incident edges: Task 3.
  - Explicit gene-set hooks kept minimal: Task 2 rejects `bio.geneset` parents with a D2-specific error.
  - No large graph artifact parsing: Task 1 reads node/edge CSV resources only.
  - Member-level provenance hooks: Task 3 preserves node and edge `dataset_usage` in the returned payload dict.
- Placeholder scan:
  - No task asks the implementer to invent behavior without code.
  - Follow-up work is named as out of scope rather than left as an implementation blank.
- Type consistency:
  - `VirtualMemberPayload.payload_kind` is a string in Task 2 and used as `"bio.reference_graph.member"` in Task 3.
  - `ReferenceGraphMemberPayload.to_dict()` returns JSON-compatible lists for tuples.
  - `commons_root` and `data_root` are threaded through generic dispatch and concrete resource reads.

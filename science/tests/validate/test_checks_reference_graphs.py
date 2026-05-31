from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from science_tool.commons.reference_graph_resources import graph_resource_available, read_edge_rows, read_node_rows
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result


_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True)


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _reference_graph(**extra: object) -> dict[str, object]:
    return {
        "id": "dataset:mondo",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "_path": "data/mondo/datapackage.yaml",
        "source_class": "reference",
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
        "node_index_resource": "nodes",
        "edge_resource": "edges",
        "member_count": 2,
        "edge_count": 1,
        **extra,
    }


def _node(**extra: object) -> dict[str, object]:
    return {
        "member_key": "MONDO:0005148",
        "member_kind": "term",
        "label": "multiple myeloma",
        "status": "active",
        "replaced_by": "",
        "dataset_usage": "[]",
        **extra,
    }


def _rules(results: list[Result]) -> list[str]:
    rules: list[str] = []
    for result in results:
        assert result.rule is not None
        rules.append(result.rule)
    return rules


def _write_reference_graph_datapackage(
    root: Path,
    *,
    graph_path: str = "graph.nt",
    nodes_path: str = "nodes.csv",
    edges_path: str | None = "edges.csv",
) -> Path:
    dp_dir = root / "data" / "mondo"
    dp_dir.mkdir(parents=True)
    resources: list[dict[str, str]] = [
        {"name": "graph", "path": graph_path},
        {"name": "nodes", "path": nodes_path},
    ]
    if edges_path is not None:
        resources.append({"name": "edges", "path": edges_path})
    dp_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:mondo",
                "type": "dataset",
                "title": "MONDO",
                "status": "active",
                "origin": "external",
                "tier": "use-now",
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
                "source_class": "reference",
                "access": {"level": "public", "verified": True},
                "graph_resource": "graph",
                "graph_format": "rdf_ntriples",
                "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
                "node_index_resource": "nodes",
                "edge_resource": "edges" if edges_path is not None else None,
                "member_count": 2,
                "edge_count": 1,
                "resources": resources,
            }
        ),
        encoding="utf-8",
    )
    return dp_dir


def _write_reference_graph_commons(root: Path, *, graph_bytes: bytes) -> Path:
    digest = hashlib.sha256(graph_bytes).hexdigest()
    commons = root / "commons"
    dataset_dir = commons / "datasets" / "mondo"
    dataset_dir.mkdir(parents=True)
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
edge_resource: edges
member_count: 2
edge_count: 1
---
""",
        encoding="utf-8",
    )
    dataset_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "mondo",
                "resources": [
                    {"name": "graph", "path": "graph.nt", "hash": f"sha256:{digest}"},
                    {"name": "nodes", "path": "nodes.csv", "hash": f"sha256:{digest}"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return commons


def test_reference_graph_resource_helper_reads_local_rows_and_checks_graph_availability(tmp_path: Path) -> None:
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path)
    dp_dir.joinpath("graph.nt").write_text("<MONDO:0005148> <is_a> <MONDO:0000001> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        "MONDO:0005148,term,multiple myeloma,active,,[]\n",
        encoding="utf-8",
    )
    dp_dir.joinpath("edges.csv").write_text(
        "subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n",
        encoding="utf-8",
    )
    fm = _reference_graph(_path="data/mondo/datapackage.yaml")

    assert graph_resource_available(tmp_path, fm) is True
    assert read_node_rows(tmp_path, fm) == [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        }
    ]
    assert read_edge_rows(tmp_path, fm) == [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "",
            "dataset_usage": "[]",
        }
    ]


def test_reference_graph_resource_helper_rejects_unsafe_resource_path(tmp_path: Path) -> None:
    _write_project(tmp_path)
    _write_reference_graph_datapackage(tmp_path, nodes_path="../outside.csv")

    rows = read_node_rows(tmp_path, _reference_graph(_path="data/mondo/datapackage.yaml"))

    assert isinstance(rows, Exception)
    assert "unsafe" in str(rows).lower() or "outside" in str(rows).lower()


def test_reference_graph_resource_helper_rejects_unsafe_datapackage_path(tmp_path: Path) -> None:
    _write_project(tmp_path)
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_dir.mkdir()
    outside_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"resources": [{"name": "nodes", "path": "nodes.csv"}]}),
        encoding="utf-8",
    )
    outside_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        "MONDO:0005148,term,multiple myeloma,active,,[]\n",
        encoding="utf-8",
    )

    rows = read_node_rows(
        tmp_path,
        _reference_graph(_path=f"../{outside_dir.name}/datapackage.yaml"),
    )

    assert isinstance(rows, Exception)


def test_graph_resource_available_uses_commons_existence_without_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_bytes = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
    commons = _write_reference_graph_commons(tmp_path, graph_bytes=graph_bytes)
    data_root = tmp_path / "data"
    graph_path = data_root / "mondo" / "graph.nt"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_bytes(graph_bytes)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("graph availability must not hash bytes through resolve()")

    monkeypatch.setattr("science_tool.commons.reference_graph_resources.resolve", fail_if_called)

    assert graph_resource_available(tmp_path, _reference_graph(_path="missing/datapackage.yaml")) is True


def test_reference_graph_resource_helper_missing_optional_edge_resource_returns_none(tmp_path: Path) -> None:
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path, edges_path=None)
    dp_dir.joinpath("graph.nt").write_text("<A> <p> <B> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\nA,term,A,active,,[]\n",
        encoding="utf-8",
    )

    fm = _reference_graph(_path="data/mondo/datapackage.yaml")
    fm.pop("edge_resource")

    assert read_edge_rows(tmp_path, fm) is None

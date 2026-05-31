from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from science_tool.commons.errors import DataResourceNotFoundError
from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows


_GRAPH_BYTES = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
_NODE_BYTES = (
    b"member_key,member_kind,label,status,replaced_by,dataset_usage\n"
    b"MONDO:0005148,term,multiple myeloma,active,,[]\n"
)
_EDGE_BYTES = b"subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n"


def _hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _reference_graph_frontmatter(*, edge_resource: bool = True) -> dict[str, Any]:
    fm: dict[str, Any] = {
        "id": "dataset:mondo",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "title": "MONDO",
        "version": "1.0.0",
        "status": "active",
        "origin": "external",
        "tier": "use-now",
        "source_class": "reference",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "access": {"level": "public", "availability": "available", "verified": True},
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
        "node_index_resource": "nodes",
        "member_count": 1,
    }
    if edge_resource:
        fm["edge_resource"] = "edges"
        fm["edge_count"] = 1
    return fm


def _write_commons_reference_graph(
    tmp_path: Path,
    *,
    include_edge_resource: bool = True,
    write_graph_file: bool = True,
    write_edge_file: bool = True,
) -> tuple[dict[str, Any], Path, Path]:
    commons_root = tmp_path / "commons"
    dataset_dir = commons_root / "datasets" / "mondo"
    dataset_dir.mkdir(parents=True)
    data_root = tmp_path / "data"
    data_dir = data_root / "mondo"
    data_dir.mkdir(parents=True)

    if write_graph_file:
        data_dir.joinpath("graph.nt").write_bytes(_GRAPH_BYTES)
    data_dir.joinpath("nodes.csv").write_bytes(_NODE_BYTES)
    if write_edge_file:
        data_dir.joinpath("edges.csv").write_bytes(_EDGE_BYTES)

    fm = _reference_graph_frontmatter(edge_resource=include_edge_resource)
    dataset_dir.joinpath("entity.md").write_text(
        "---\n" + yaml.safe_dump({"datapackage": "datapackage.yaml", **fm}, sort_keys=False) + "---\n",
        encoding="utf-8",
    )

    resources: list[dict[str, str]] = [
        {"name": "graph", "path": "graph.nt", "hash": _hash(_GRAPH_BYTES)},
        {"name": "nodes", "path": "nodes.csv", "hash": _hash(_NODE_BYTES)},
    ]
    if include_edge_resource:
        resources.append({"name": "edges", "path": "edges.csv", "hash": _hash(_EDGE_BYTES)})
    dataset_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"name": "mondo", "resources": resources}, sort_keys=False),
        encoding="utf-8",
    )
    return fm, commons_root, data_root


@pytest.fixture(autouse=True)
def _hermetic_commons_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "config"))


def test_read_commons_node_rows_uses_explicit_roots_without_env(tmp_path: Path) -> None:
    fm, commons_root, data_root = _write_commons_reference_graph(tmp_path)

    rows = read_commons_node_rows(fm, commons_root=commons_root, data_root=data_root)

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


def test_read_commons_edge_rows_returns_none_without_edge_resource(tmp_path: Path) -> None:
    fm, commons_root, data_root = _write_commons_reference_graph(tmp_path, include_edge_resource=False)

    rows = read_commons_edge_rows(fm, commons_root=commons_root, data_root=data_root)

    assert rows is None


def test_read_commons_edge_rows_reads_declared_edge_csv(tmp_path: Path) -> None:
    fm, commons_root, data_root = _write_commons_reference_graph(tmp_path)

    rows = read_commons_edge_rows(fm, commons_root=commons_root, data_root=data_root)

    assert rows == [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "",
            "dataset_usage": "[]",
        }
    ]


def test_read_commons_projection_rows_do_not_touch_declared_graph_resource(tmp_path: Path) -> None:
    fm, commons_root, data_root = _write_commons_reference_graph(tmp_path, write_graph_file=False)

    node_rows = read_commons_node_rows(fm, commons_root=commons_root, data_root=data_root)
    edge_rows = read_commons_edge_rows(fm, commons_root=commons_root, data_root=data_root)

    assert node_rows == [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        }
    ]
    assert edge_rows == [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "",
            "dataset_usage": "[]",
        }
    ]


def test_read_commons_edge_rows_returns_exception_when_declared_edge_file_is_missing(tmp_path: Path) -> None:
    fm, commons_root, data_root = _write_commons_reference_graph(tmp_path, write_edge_file=False)

    rows = read_commons_edge_rows(fm, commons_root=commons_root, data_root=data_root)

    assert isinstance(rows, DataResourceNotFoundError)

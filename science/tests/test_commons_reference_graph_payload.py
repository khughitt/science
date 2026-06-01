from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from science_tool.commons.member_payload import (
    MemberPayloadError,
    UnresolvedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)


def _hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _csv_bytes(rows: list[dict[str, str]], fieldnames: list[str]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _dataset_usage(ref: str) -> str:
    return json.dumps([{"ref": ref, "role": "upstream", "overlap": "partial"}])


def _write_entity(dataset_dir: Path, frontmatter: dict[str, Any]) -> None:
    dataset_dir.mkdir(parents=True)
    dataset_dir.joinpath("entity.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\nbody\n",
        encoding="utf-8",
    )


def _write_reference_graph_commons(
    tmp_path: Path,
    *,
    include_edge_resource: bool = True,
    write_edge_file: bool = True,
    member_key: str = "MONDO:0005148",
) -> tuple[Path, Path]:
    commons_root = tmp_path / "commons"
    data_root = tmp_path / "data"
    parent_dir = commons_root / "datasets" / "mondo"
    member_dir = commons_root / "datasets" / "mondo-0005148"
    data_dir = data_root / "mondo"
    data_dir.mkdir(parents=True)

    graph_bytes = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
    node_rows = [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": _dataset_usage("dataset:ordo"),
        },
        {
            "member_key": "MONDO:0000001",
            "member_kind": "term",
            "label": "disease",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:0008549",
            "member_kind": "term",
            "label": "obsolete thoracic dysostosis, isolated",
            "status": "deprecated",
            "replaced_by": "MONDO:0979242",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:9999999",
            "member_kind": "term",
            "label": "unrelated disease",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
    ]
    edge_rows = [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "ECO:0000269",
            "dataset_usage": _dataset_usage("dataset:mondo"),
        },
        {
            "subject": "MONDO:0000001",
            "predicate": "subsumes",
            "object": "MONDO:0005148",
            "evidence": "",
            "dataset_usage": "[]",
        },
        {
            "subject": "MONDO:9999999",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "",
            "dataset_usage": "[]",
        },
        {
            "subject": "MONDO:0008549",
            "predicate": "xref",
            "object": "OMIM:example",
            "evidence": "",
            "dataset_usage": "[]",
        },
    ]
    node_bytes = _csv_bytes(
        node_rows,
        ["member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"],
    )
    edge_bytes = _csv_bytes(edge_rows, ["subject", "predicate", "object", "evidence", "dataset_usage"])

    data_dir.joinpath("graph.nt").write_bytes(graph_bytes)
    data_dir.joinpath("nodes.csv").write_bytes(node_bytes)
    if write_edge_file:
        data_dir.joinpath("edges.csv").write_bytes(edge_bytes)

    parent_fm: dict[str, Any] = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "id": "dataset:mondo",
        "type": "dataset",
        "title": "MONDO",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "availability": "available", "verified": True},
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
        "node_index_resource": "nodes",
        "member_count": 4,
    }
    if include_edge_resource:
        parent_fm["edge_resource"] = "edges"
        parent_fm["edge_count"] = 4
    _write_entity(parent_dir, parent_fm)

    resources = [
        {"name": "graph", "path": "graph.nt", "hash": _hash(graph_bytes)},
        {"name": "nodes", "path": "nodes.csv", "hash": _hash(node_bytes)},
    ]
    if include_edge_resource:
        resources.append({"name": "edges", "path": "edges.csv", "hash": _hash(edge_bytes)})
    parent_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"name": "mondo", "resources": resources}, sort_keys=False),
        encoding="utf-8",
    )

    _write_entity(
        member_dir,
        {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
            "id": "dataset:mondo-0005148",
            "type": "dataset",
            "title": "MONDO:0005148",
            "version": "1.0.0",
            "status": "active",
            "created": "2026-05-31",
            "updated": "2026-05-31",
            "datapackage": "virtual:member-of",
            "origin": "derived",
            "tier": "use-now",
            "member_kind": "term",
            "label": "multiple myeloma",
            "derivation": {
                "kind": "member_of",
                "parent_dataset": "dataset:mondo",
                "member_key": member_key,
            },
        },
    )
    member_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"name": "mondo-0005148", "resources": []}, sort_keys=False),
        encoding="utf-8",
    )

    return commons_root, data_root


def _replace_resource_bytes(commons_root: Path, data_root: Path, *, name: str, path: str, content: bytes) -> None:
    data_root.joinpath("mondo", path).write_bytes(content)
    datapackage_path = commons_root / "datasets" / "mondo" / "datapackage.yaml"
    datapackage = yaml.safe_load(datapackage_path.read_text(encoding="utf-8"))
    for resource in datapackage["resources"]:
        if resource["name"] == name:
            resource["hash"] = _hash(content)
            datapackage_path.write_text(yaml.safe_dump(datapackage, sort_keys=False), encoding="utf-8")
            return
    raise AssertionError(f"test fixture resource {name!r} not found")


@pytest.fixture(autouse=True)
def _hermetic_commons_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "config"))


def test_resolve_virtual_reference_graph_member_payload_returns_node_and_incident_edges(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert isinstance(payload, VirtualMemberPayload)
    assert payload.payload_kind == "bio.reference_graph.member"
    assert payload.member_key == "MONDO:0005148"
    assert payload.payload["node"]["label"] == "multiple myeloma"
    assert payload.payload["node"]["dataset_usage"][0]["ref"] == "dataset:ordo"
    assert payload.payload["incident_edges"] == [
        {
            "subject": "MONDO:0005148",
            "predicate": "is_a",
            "object": "MONDO:0000001",
            "evidence": "ECO:0000269",
            "dataset_usage": [{"ref": "dataset:mondo", "role": "upstream", "overlap": "partial"}],
        },
        {
            "subject": "MONDO:0000001",
            "predicate": "subsumes",
            "object": "MONDO:0005148",
            "evidence": None,
            "dataset_usage": [],
        },
    ]


def test_resolve_reference_graph_member_payload_allows_missing_edge_resource(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path, include_edge_resource=False)

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert isinstance(payload, VirtualMemberPayload)
    assert payload.payload["incident_edges"] == []


def test_resolve_reference_graph_member_payload_rejects_missing_declared_edge_file(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path, write_edge_file=False)

    with pytest.raises(MemberPayloadError, match="edge resource cannot be read"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_reference_graph_member_payload_rejects_missing_declared_node_file(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)
    data_root.joinpath("mondo", "nodes.csv").unlink()

    with pytest.raises(MemberPayloadError, match="node index resource cannot be read"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_reference_graph_member_payload_rejects_malformed_node_csv(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)
    malformed_nodes = b"member_key,member_kind,status,replaced_by,dataset_usage\nMONDO:0005148,term,active,,[]\n"
    _replace_resource_bytes(commons_root, data_root, name="nodes", path="nodes.csv", content=malformed_nodes)

    with pytest.raises(MemberPayloadError, match="node index is malformed"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_reference_graph_member_payload_rejects_malformed_edge_csv(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)
    malformed_edges = b"subject,predicate,evidence,dataset_usage\nMONDO:0005148,is_a,,[]\n"
    _replace_resource_bytes(commons_root, data_root, name="edges", path="edges.csv", content=malformed_edges)

    with pytest.raises(MemberPayloadError, match="edge resource is malformed"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_reference_graph_member_payload_rejects_absent_member_key(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path, member_key="MONDO:404")

    with pytest.raises(UnresolvedMemberPayloadError, match="MONDO:404"):
        resolve_virtual_member_payload(
            "dataset:mondo-0005148",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_virtual_reference_graph_member_payload_returns_deprecated_node_and_xref_edges(
    tmp_path: Path,
) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path, member_key="MONDO:0008549")

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert isinstance(payload, VirtualMemberPayload)
    assert payload.member_key == "MONDO:0008549"
    assert payload.payload["node"]["status"] == "deprecated"
    assert payload.payload["node"]["replaced_by"] == ["MONDO:0979242"]
    assert ("MONDO:0008549", "xref", "OMIM:example") in {
        (edge["subject"], edge["predicate"], edge["object"])
        for edge in payload.payload["incident_edges"]
    }

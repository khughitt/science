from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import yaml

from science_tool.commons.reference_graph_identity import resolve_graph_member


def _hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _csv_bytes(rows: list[dict[str, str]], fieldnames: list[str]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_reference_graph_commons(tmp_path: Path) -> tuple[Path, Path]:
    commons_root = tmp_path / "commons"
    data_root = tmp_path / "data"
    dataset_dir = commons_root / "datasets" / "mondo"
    data_dir = data_root / "mondo"
    dataset_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    graph_bytes = b"<MONDO:0005148> <is_a> <MONDO:0000001> .\n"
    node_bytes = _csv_bytes(
        [
            {
                "member_key": "MONDO:0005148",
                "member_kind": "term",
                "label": "multiple myeloma",
                "status": "active",
                "replaced_by": "",
                "dataset_usage": '[{"ref":"dataset:ordo","role":"upstream","overlap":"partial"}]',
            },
            {
                "member_key": "MONDO:0008549",
                "member_kind": "term",
                "label": "obsolete thoracic dysostosis, isolated",
                "status": "deprecated",
                "replaced_by": "MONDO:0979242;MONDO:0979243",
                "dataset_usage": "[]",
            },
        ],
        ["member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"],
    )
    data_dir.joinpath("graph.nt").write_bytes(graph_bytes)
    data_dir.joinpath("nodes.csv").write_bytes(node_bytes)

    dataset_dir.joinpath("entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0\n"
        "id: dataset:mondo\n"
        "kind: dataset\n"
        "title: MONDO\n"
        "version: 1.0.0\n"
        "status: active\n"
        "created: '2026-05-31'\n"
        "updated: '2026-05-31'\n"
        "datapackage: datapackage.yaml\n"
        "origin: external\n"
        "tier: use-now\n"
        "access: {level: public, availability: available, verified: true}\n"
        "graph_resource: graph\n"
        "graph_format: rdf_ntriples\n"
        "member_key_space: {kind: curie, prefixes: [MONDO], resolution_status: resolved}\n"
        "node_index_resource: nodes\n"
        "member_count: 2\n"
        "---\n",
        encoding="utf-8",
    )
    dataset_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "mondo",
                "resources": [
                    {"name": "graph", "path": "graph.nt", "hash": _hash(graph_bytes)},
                    {"name": "nodes", "path": "nodes.csv", "hash": _hash(node_bytes)},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return commons_root, data_root


def test_resolve_graph_member_returns_active_reference_identity(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)

    match = resolve_graph_member(
        "MONDO:0005148",
        registry_id="dataset:mondo",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert match is not None
    assert match.member_key == "MONDO:0005148"
    assert match.member_kind == "term"
    assert match.label == "multiple myeloma"
    assert match.status == "active"
    assert match.replaced_by == ()
    assert match.dataset_usage == ({"ref": "dataset:ordo", "role": "upstream", "overlap": "partial"},)


def test_resolve_graph_member_surfaces_deprecated_replacements_without_following(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)

    match = resolve_graph_member(
        "MONDO:0008549",
        registry_id="dataset:mondo",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert match is not None
    assert match.member_key == "MONDO:0008549"
    assert match.status == "deprecated"
    assert match.replaced_by == ("MONDO:0979242", "MONDO:0979243")


def test_resolve_graph_member_returns_none_for_absent_key(tmp_path: Path) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path)

    match = resolve_graph_member(
        "MONDO:404",
        registry_id="dataset:mondo",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert match is None

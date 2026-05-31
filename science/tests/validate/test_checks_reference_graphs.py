from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from science_tool.commons.reference_graph_resources import graph_resource_available, read_edge_rows, read_node_rows
from science_tool.validate.checks.reference_graphs import evaluate_reference_graphs
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


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


def _edge(**extra: object) -> dict[str, object]:
    return {
        "subject": "MONDO:0005148",
        "predicate": "is_a",
        "object": "MONDO:0000001",
        "evidence": "",
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


def test_valid_reference_graph_passes_silently() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert results == []


def test_malformed_reference_graph_collection_errors() -> None:
    fm = _reference_graph(graph_format="obo")

    results = list(
        evaluate_reference_graphs(
            [fm],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node()]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.collection-malformed"]
    assert results[0].severity is Severity.ERROR


def test_missing_graph_resource_does_not_suppress_node_validation() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": None},
            node_rows_by_dataset_id={"dataset:mondo": [_node()]},
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert _rules(results) == [
        "reference-graph.graph-resource-unavailable",
        "reference-graph.member-count-mismatch",
    ]
    assert results[0].severity is Severity.INFO


def test_missing_node_index_is_info_not_silent() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={},
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.node-index-unavailable"]
    assert results[0].severity is Severity.INFO


def test_node_index_malformed_errors() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(status="obsolete")]},
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.node-index-malformed"]
    assert results[0].severity is Severity.ERROR


def test_member_count_counts_deprecated_rows() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(member_count=1)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.member-count-mismatch"]
    assert "has 2 node rows" in results[0].message


def test_edge_count_mismatch_errors_when_edge_resource_declared() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(edge_count=2)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {
                        "subject": "MONDO:0005148",
                        "predicate": "is_a",
                        "object": "MONDO:0000001",
                        "evidence": "",
                        "dataset_usage": "[]",
                    }
                ]
            },
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.edge-count-mismatch"]


def test_edge_validation_still_runs_after_member_count_mismatch() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(member_count=1, edge_count=2)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {
                        "subject": "MONDO:0005148",
                        "predicate": "is_a",
                        "object": "MONDO:0000001",
                        "evidence": "",
                        "dataset_usage": "[]",
                    }
                ]
            },
            member_datasets=[],
        )
    )

    assert _rules(results) == [
        "reference-graph.member-count-mismatch",
        "reference-graph.edge-count-mismatch",
    ]


def test_jsonl_edges_format_is_enum_validated_without_distinct_edge_resource() -> None:
    fm = _reference_graph(graph_format="jsonl_edges", edge_resource=None, edge_count=None)
    fm.pop("edge_resource")
    fm.pop("edge_count")
    results = list(
        evaluate_reference_graphs(
            [fm],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert results == []


def test_deprecated_promoted_member_warns_with_replaced_by() -> None:
    member = {
        "id": "dataset:mondo-obsolete",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "_path": "data/mondo-obsolete/entity.md",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:mondo", "member_key": "MONDO:obsolete"},
        "member_kind": "term",
        "label": "old label",
        "status": "deprecated",
    }
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [
                    _node(),
                    _node(member_key="MONDO:obsolete", status="deprecated", replaced_by="MONDO:0005148"),
                ]
            },
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {
                        "subject": "MONDO:0005148",
                        "predicate": "is_a",
                        "object": "MONDO:0000001",
                        "evidence": "",
                        "dataset_usage": "[]",
                    }
                ]
            },
            member_datasets=[member],
        )
    )

    assert _rules(results) == ["reference-graph.member-deprecated"]
    assert results[0].severity is Severity.WARN
    assert "MONDO:0005148" in results[0].message


@pytest.mark.parametrize(
    ("derivation", "message_part"),
    [
        ({"kind": "member_of", "parent_dataset": "dataset:mondo"}, "member_key"),
        ({"kind": "member_of", "parent_dataset": "mondo", "member_key": "MONDO:0005148"}, "parent_dataset"),
    ],
)
def test_malformed_promoted_member_derivation_errors_without_raising(
    derivation: dict[str, object], message_part: str
) -> None:
    member = {
        "id": "dataset:malformed",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "_path": "data/malformed/entity.md",
        "derivation": derivation,
        "member_kind": "term",
        "label": "malformed",
        "status": "active",
    }

    results = list(
        evaluate_reference_graphs(
            [],
            graph_available_by_dataset_id={},
            node_rows_by_dataset_id={},
            edge_rows_by_dataset_id={},
            member_datasets=[member],
        )
    )

    assert _rules(results) == ["reference-graph.member-malformed"]
    assert results[0].severity is Severity.ERROR
    assert message_part in results[0].message


def test_unresolved_promoted_member_errors() -> None:
    member = {
        "id": "dataset:missing",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "_path": "data/missing/entity.md",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:mondo", "member_key": "MONDO:missing"},
        "member_kind": "term",
        "label": "missing",
        "status": "active",
    }
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {
                        "subject": "MONDO:0005148",
                        "predicate": "is_a",
                        "object": "MONDO:0000001",
                        "evidence": "",
                        "dataset_usage": "[]",
                    }
                ]
            },
            member_datasets=[member],
        )
    )

    assert _rules(results) == ["reference-graph.member-unresolved"]
    assert results[0].severity is Severity.ERROR

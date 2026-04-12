"""Tests for shared graph export payload types."""

from pathlib import Path

import pytest

from science_tool.graph.export_types import (
    GraphExportOverlays,
    GraphExportPayload,
    GraphExportScope,
    build_graph_export_edge_id,
)
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for export tests."""
    graph_file = tmp_path / "knowledge" / "graph.trig"
    graph_file.parent.mkdir(parents=True)
    graph_file.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return graph_file


def test_export_types_roundtrip_minimal_payload() -> None:
    payload = GraphExportPayload(
        schema_version="1",
        nodes=[],
        edges=[],
        layers=[],
        scopes=[],
        overlays=GraphExportOverlays(),
        warnings=[],
    )

    assert payload.model_dump()["schema_version"] == "1"


def test_build_graph_export_edge_id_is_stable_for_same_inputs() -> None:
    edge_id_a = build_graph_export_edge_id(
        subject="http://example.org/project/concept/drug",
        predicate="http://example.org/science/vocab/causal/causes",
        obj="http://example.org/project/concept/recovery",
        graph_layer="graph/causal",
    )
    edge_id_b = build_graph_export_edge_id(
        subject="http://example.org/project/concept/drug",
        predicate="http://example.org/science/vocab/causal/causes",
        obj="http://example.org/project/concept/recovery",
        graph_layer="graph/causal",
    )

    assert edge_id_a == edge_id_b


def test_graph_export_scope_preserves_explicit_inquiry_membership_shape() -> None:
    scope = GraphExportScope(
        id="inquiry/test-dag",
        kind="inquiry",
        label="Test DAG",
        node_ids=["http://example.org/project/concept/drug"],
        edge_ids=["graph/causal::drug::causes::recovery"],
        metadata={"treatment": "http://example.org/project/concept/drug"},
    )

    assert scope.kind == "inquiry"
    assert scope.node_ids == ["http://example.org/project/concept/drug"]

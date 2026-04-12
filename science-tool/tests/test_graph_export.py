"""Tests for shared graph export payload types."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.graph.export_types import (
    GraphExportOverlays,
    GraphExportPayload,
    GraphExportScope,
    build_graph_export_edge_id,
    build_graph_export_node_id,
)
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


def test_graph_export_fixture_creates_fresh_graph(graph_path: Path) -> None:
    assert graph_path.read_text(encoding="utf-8") == INITIAL_GRAPH_TEMPLATE


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


def test_build_graph_export_node_id_returns_canonical_uri() -> None:
    uri = "http://example.org/project/concept/drug"

    assert build_graph_export_node_id(uri) == uri


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


def test_graph_export_scope_preserves_explicit_semantics() -> None:
    expected_edge_id = build_graph_export_edge_id(
        subject="http://example.org/project/concept/drug",
        predicate="http://example.org/science/vocab/causal/causes",
        obj="http://example.org/project/concept/recovery",
        graph_layer="graph/causal",
    )
    scope = GraphExportScope(
        id="inquiry/test-dag",
        kind="inquiry",
        label="Test DAG",
        node_ids=["http://example.org/project/concept/drug"],
        edge_ids=[expected_edge_id],
        metadata={"treatment": "http://example.org/project/concept/drug"},
    )

    assert scope.id == "inquiry/test-dag"
    assert scope.kind == "inquiry"
    assert scope.label == "Test DAG"
    assert scope.node_ids == ["http://example.org/project/concept/drug"]
    assert scope.edge_ids == [expected_edge_id]
    assert scope.metadata == {"treatment": "http://example.org/project/concept/drug"}


def test_graph_export_scope_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        GraphExportScope(
            id="project/test",
            kind="invalid",  # type: ignore[arg-type]
            label="Invalid",
            node_ids=[],
            edge_ids=[],
            metadata={},
        )

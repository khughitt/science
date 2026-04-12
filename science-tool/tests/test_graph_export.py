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
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    add_concept,
    add_edge,
    add_inquiry,
    add_inquiry_node,
    export_graph_payload,
    set_boundary_role,
    set_treatment_outcome,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    add_concept(gp, "Drug", None, None, source="http://example.org/project/source/drug")
    add_concept(gp, "Recovery", None, None, source="http://example.org/project/source/recovery")
    add_edge(
        gp,
        "concept/drug",
        "scic:causes",
        "concept/recovery",
        "graph/causal",
    )
    add_inquiry(gp, "test-dag", "Test DAG", "concept/recovery", inquiry_type="causal")
    set_boundary_role(gp, "test-dag", "concept/drug", "BoundaryIn")
    set_boundary_role(gp, "test-dag", "concept/recovery", "BoundaryOut")
    set_treatment_outcome(gp, "test-dag", "concept/drug", "concept/recovery")

    add_inquiry(gp, "dangling-dag", "Dangling DAG", "concept/recovery", inquiry_type="causal")
    set_treatment_outcome(gp, "dangling-dag", "concept/drug", "concept/unexported_outcome")
    set_boundary_role(gp, "dangling-dag", "concept/unexported_boundary", "BoundaryOut")

    return gp


def test_graph_export_fixture_builds_seeded_graph(graph_path: Path) -> None:
    content = graph_path.read_text(encoding="utf-8")

    assert content != INITIAL_GRAPH_TEMPLATE
    assert "Drug" in content
    assert "Test DAG" in content


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


def test_export_graph_payload_includes_base_nodes_edges_layers(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path)

    drug = next(node for node in payload.nodes if node.id == "http://example.org/project/concept/drug")
    edge = next(edge for edge in payload.edges if edge.predicate == "http://example.org/science/vocab/causal/causes")
    causal_layer = next(layer for layer in payload.layers if layer.id == "graph/causal")
    project_scope = next(scope for scope in payload.scopes if scope.kind == "project")
    inquiry_scope = next(scope for scope in payload.scopes if scope.kind == "inquiry")

    assert drug.label == "Drug"
    assert edge.graph_layer == "graph/causal"
    assert causal_layer.node_count == 2
    assert causal_layer.edge_count == 1
    assert "http://example.org/project/concept/drug" in inquiry_scope.node_ids
    assert edge.id in inquiry_scope.edge_ids
    assert edge.id in project_scope.edge_ids


def test_export_graph_payload_inquiry_scopes_only_reference_exported_nodes(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path)
    node_ids = {node.id for node in payload.nodes}
    inquiry_scopes = [scope for scope in payload.scopes if scope.kind == "inquiry"]

    assert all(
        "http://example.org/project/concept/unexported_outcome" not in scope.node_ids for scope in inquiry_scopes
    )
    assert all(set(scope.node_ids) <= node_ids for scope in inquiry_scopes)


def test_export_graph_payload_includes_causal_overlay_for_inquiry(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])

    causal_overlay = payload.overlays.causal
    inquiry = causal_overlay["inquiries"]["inquiry/test_dag"]
    edge_id = build_graph_export_edge_id(
        subject="http://example.org/project/concept/drug",
        predicate="http://example.org/science/vocab/causal/causes",
        obj="http://example.org/project/concept/recovery",
        graph_layer="graph/causal",
    )
    edge = inquiry["edges"][edge_id]

    assert inquiry["treatment"] == "http://example.org/project/concept/drug"
    assert inquiry["outcome"] == "http://example.org/project/concept/recovery"
    assert inquiry["boundary_roles"]["http://example.org/project/concept/drug"] == "BoundaryIn"
    assert inquiry["boundary_roles"]["http://example.org/project/concept/recovery"] == "BoundaryOut"
    assert edge["kind"] == "causes"


def test_export_graph_payload_includes_confounds_edges_in_causal_overlay(graph_path: Path) -> None:
    add_concept(graph_path, "Modifier", None, None, source="http://example.org/project/source/modifier")
    add_inquiry_node(graph_path, "test-dag", "concept/modifier")
    add_edge(
        graph_path,
        "concept/modifier",
        "scic:confounds",
        "concept/recovery",
        "graph/causal",
    )

    payload = export_graph_payload(graph_path, overlays=["causal"])
    inquiry = payload.overlays.causal["inquiries"]["inquiry/test_dag"]
    edge_id = build_graph_export_edge_id(
        subject="http://example.org/project/concept/modifier",
        predicate="http://example.org/science/vocab/causal/confounds",
        obj="http://example.org/project/concept/recovery",
        graph_layer="graph/causal",
    )

    assert inquiry["edges"][edge_id]["kind"] == "confounds"


def test_export_graph_payload_warns_for_missing_causal_referent(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])

    assert any(
        "skipped missing outcome ref http://example.org/project/concept/unexported_outcome" in warning
        for warning in payload.warnings
    )


def test_export_graph_payload_excludes_missing_boundary_roles_from_causal_overlay(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])

    inquiry = payload.overlays.causal["inquiries"]["inquiry/dangling_dag"]

    assert "http://example.org/project/concept/unexported_boundary" not in inquiry["boundary_roles"]

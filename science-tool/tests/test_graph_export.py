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
    add_hypothesis,
    add_proposition,
    export_graph_payload,
    _graph_uri,
    _load_dataset,
    _save_dataset,
    set_boundary_role,
    set_treatment_outcome,
    SCI_NS,
)
from rdflib import URIRef
from rdflib import Literal
from rdflib.namespace import PROV, RDF, SKOS


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    add_concept(gp, "Drug", None, None, source="http://example.org/project/source/drug")
    add_concept(gp, "Recovery", None, None, source="http://example.org/project/source/recovery")
    add_hypothesis(gp, "h1", "Hypothesis 1", source="paper:h1")
    add_hypothesis(gp, "h2", "Hypothesis 2", source="paper:h2")
    add_edge(
        gp,
        "concept/drug",
        "scic:causes",
        "concept/recovery",
        "graph/causal",
    )
    add_proposition(
        gp,
        text="Drug treatment improves recovery time",
        source="article:doi_10.1234/drug_recovery",
        confidence=0.85,
        subject="concept/drug",
        predicate="scic:causes",
        obj="concept/recovery",
        proposition_id="drug_causes_recovery_evidence",
        compositional_status="clr_attenuated",
        compositional_method="CLR",
        compositional_note="beta attenuates after CLR normalization",
        platform_pattern="MMRF-dominant",
        dataset_effects={"MMRF": 0.7, "GSE24080": 0.07},
        evidence_lines=[
            {"source": "Johnson 2024 ChIP", "kind": "external_biochem", "datasets": []},
            {"source": "t133", "kind": "internal_correlation", "datasets": ["MMRF"]},
        ],
        statistical_support="replicated",
        mechanistic_support="direct",
        replication_scope="cross_dataset",
        claim_status="active",
        pre_registration_refs=["pre-registration:edge-ribosome-e2f1"],
        interaction_terms=[
            {
                "modifier": "concept/kras",
                "effect": "amplifies",
                "note": "stronger slope in KRAS-mutant cases",
            }
        ],
        bridge_between_refs=["hypothesis:h1", "hypothesis:h2"],
    )
    add_concept(gp, "KRAS", None, None, source="http://example.org/project/source/kras")
    add_edge(
        gp,
        "concept/drug",
        "scic:causes",
        "concept/recovery",
        "graph/causal",
        claim_refs=["proposition:drug_causes_recovery_evidence"],
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


def test_export_graph_payload_includes_dashboard_style_named_layers(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    dataset = _load_dataset(graph_path)
    model_graph = dataset.graph(_graph_uri("graph/model"))
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    model_uri = URIRef("http://example.org/project/model/lorenz-attractor")

    model_graph.add((model_uri, RDF.type, SCI_NS.Model))
    model_graph.add((model_uri, SKOS.prefLabel, Literal("Lorenz attractor")))
    provenance_graph.add((model_uri, PROV.wasDerivedFrom, URIRef("http://example.org/project/source/model")))
    _save_dataset(dataset, graph_path)

    payload = export_graph_payload(graph_path)
    layer_ids = {layer.id for layer in payload.layers}
    model = next(node for node in payload.nodes if node.id == str(model_uri))

    assert "graph/model" in layer_ids
    assert "graph/provenance" in layer_ids
    assert model.label == "Lorenz attractor"
    assert model.graph_layer == "graph/model"
    assert next(layer for layer in payload.layers if layer.id == "graph/model").node_count == 1


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


def test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["evidence"])
    edge_id = next(edge.id for edge in payload.edges if edge.predicate.endswith("/causes"))
    edge_evidence = payload.overlays.evidence["edges"][edge_id]

    assert edge_evidence["claims"][0]["bridge_between"] == ["hypothesis/h1", "hypothesis/h2"]
    assert edge_evidence["claims"][0]["statistical_support"] == "replicated"
    assert edge_evidence["claims"][0]["pre_registrations"] == ["pre-registration/edge-ribosome-e2f1"]


def test_export_graph_payload_skips_missing_claim_refs_with_warning(graph_path: Path) -> None:
    dataset = _load_dataset(graph_path)
    causal_graph = dataset.graph(_graph_uri("graph/causal"))
    edge_subject = URIRef("http://example.org/project/concept/drug")
    statement_uri = next(causal_graph.subjects(RDF.subject, edge_subject))
    causal_graph.add(
        (statement_uri, SCI_NS.backedByClaim, URIRef("http://example.org/project/proposition/missing_claim"))
    )
    _save_dataset(dataset, graph_path)

    payload = export_graph_payload(graph_path, overlays=["evidence"])

    assert any("missing claim ref" in warning for warning in payload.warnings)

"""Tests for shared graph export payload types."""

from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml
from pydantic import ValidationError
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_tool.graph.export_types import (
    GraphExportOverlays,
    GraphExportPayload,
    GraphExportScope,
    build_graph_export_edge_id,
    build_graph_export_node_id,
)
from science_tool.graph.io import DCAT_NS
from science_tool.graph.materialize import _build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from conftest import build_entity_graph, build_inquiry_graph

from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    _save_dataset,
    export_graph_payload,
)


class CausalEdgeOverlay(TypedDict):
    kind: str


class CausalInquiryOverlay(TypedDict):
    treatment: str | None
    outcome: str | None
    boundary_roles: dict[str, str]
    edges: dict[str, CausalEdgeOverlay]


class CausalOverlays(TypedDict):
    inquiries: dict[str, CausalInquiryOverlay]


def _entity(kind: str, entity_id: str, title: str, **frontmatter: object) -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {"title": title, "status": "active", **frontmatter},
        "body": f"# {title}\n",
    }


def _concept(entity_id: str, title: str | None = None) -> dict:
    return _entity("concept", entity_id, title or entity_id.replace("-", " ").title())


def _hypothesis(entity_id: str, title: str) -> dict:
    return _entity("hypothesis", entity_id, title, source_refs=[])


def _proposition(entity_id: str, title: str, **frontmatter: object) -> dict:
    return _entity("proposition", entity_id, title, source_refs=[], **frontmatter)


def _causal_relation(subject: str, predicate: str, obj: str) -> dict:
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "graph_layer": "graph/causal",
    }


def _build_base_graph(
    project_root: Path,
    *,
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
) -> Path:
    graph_path = build_entity_graph(
        project_root,
        entities=[
            _concept("drug", "Drug"),
            _concept("recovery", "Recovery"),
            _concept("kras", "KRAS"),
            _hypothesis("h1", "Hypothesis 1"),
            _hypothesis("h2", "Hypothesis 2"),
            _proposition(
                "drug_causes_recovery_evidence",
                "Drug treatment improves recovery time",
                confidence=0.85,
            ),
            *(entities or []),
        ],
        relations=[
            _causal_relation("concept:drug", "scic:causes", "concept:recovery"),
            *(relations or []),
        ],
    )
    _build_fixture_inquiries(graph_path)
    return graph_path


def _build_fixture_inquiries(graph_path: Path) -> None:
    # test_dag: source-built causal inquiry. `concept:modifier` is an interior
    # node (flow-edge endpoint) so the confounds test can associate a graph/causal
    # confounds edge with the inquiry once it authors the concept — the
    # source-model equivalent of the retired `add_inquiry_node`.
    build_inquiry_graph(
        graph_path,
        slug="test_dag",
        title="Test DAG",
        profile="causal",
        focal="concept:recovery",
        treatment="concept:drug",
        outcome="concept:recovery",
        boundary_roles=[
            {"ref": "concept:drug", "role": "BoundaryIn"},
            {"ref": "concept:recovery", "role": "BoundaryOut"},
        ],
        flow_edges=[
            {
                "subject": "concept:drug",
                "predicate": "causes",
                "object": "concept:recovery",
                "claim_refs": ["proposition:drug_causes_recovery_evidence"],
            },
            {"subject": "concept:modifier", "predicate": "feedsInto", "object": "concept:recovery"},
        ],
    )
    # dangling_dag: outcome + boundary reference concepts that are never exported,
    # exercising the export overlay's missing-referent handling.
    build_inquiry_graph(
        graph_path,
        slug="dangling_dag",
        title="Dangling DAG",
        profile="causal",
        focal="concept:recovery",
        treatment="concept:drug",
        outcome="concept:unexported_outcome",
        boundary_roles=[
            {"ref": "concept:unexported_boundary", "role": "BoundaryOut"},
        ],
    )


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    return _build_base_graph(tmp_path)


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
    edge = next(
        edge
        for edge in payload.edges
        if edge.predicate == "http://example.org/science/vocab/causal/causes" and edge.graph_layer == "graph/causal"
    )
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


def test_export_graph_payload_includes_mechanism_nodes(graph_path: Path) -> None:
    build_entity_graph(
        graph_path.parent.parent,
        entities=[
            _entity(
                "mechanism",
                "phf19-prc2-ifn",
                "PHF19 / PRC2 / IFN",
                status="draft",
                summary="PHF19-PRC2 dampens IFN signaling.",
                participants=["concept:drug", "concept:recovery"],
                propositions=["proposition:drug_causes_recovery_evidence"],
            )
        ],
    )

    payload = export_graph_payload(graph_path)
    mechanism_node = next(node for node in payload.nodes if node.id.endswith("/mechanism/phf19-prc2-ifn"))

    assert mechanism_node.label == "PHF19 / PRC2 / IFN"
    assert mechanism_node.type is not None
    assert "sci:Mechanism" in mechanism_node.type
    assert mechanism_node.status == "draft"


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


def test_export_graph_payload_includes_dataset_usage_connectivity(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    paper_uri = URIRef("http://example.org/project/paper/Adams2025")
    usage_uri = URIRef("http://example.org/project/dataset-usage/abc123")
    dataset_uri = URIRef("http://example.org/project/dataset/gtex-v8")
    provenance.add((paper_uri, RDF.type, SCI_NS.Paper))
    provenance.add((paper_uri, SKOS.prefLabel, Literal("Adams 2025")))
    provenance.add((dataset_uri, RDF.type, SCI_NS.Dataset))
    provenance.add((dataset_uri, SKOS.prefLabel, Literal("GTEx v8")))
    provenance.add((paper_uri, SCI_NS.hasDatasetUsage, usage_uri))
    provenance.add((usage_uri, RDF.type, SCI_NS.DatasetUsage))
    provenance.add((usage_uri, SCI_NS.dataset, dataset_uri))
    provenance.add((usage_uri, SCI_NS.usageRole, Literal("analyzed")))
    _save_dataset(dataset, graph_path)

    payload = export_graph_payload(graph_path)
    edge_tuples = {(edge.subject, edge.predicate, edge.object) for edge in payload.edges}

    assert (
        str(paper_uri),
        str(SCI_NS.hasDatasetUsage),
        str(usage_uri),
    ) in edge_tuples
    assert (
        str(usage_uri),
        str(SCI_NS.dataset),
        str(dataset_uri),
    ) in edge_tuples
    assert str(usage_uri) in {node.id for node in payload.nodes}


def test_export_graph_payload_supports_legacy_project_named_layers(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        """\
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sci: <http://example.org/science/vocab/> .
@prefix schema: <https://schema.org/> .
@prefix project: <http://example.org/project/> .
@prefix gene: <http://example.org/project/gene/> .

project:knowledge {
    gene:tp53 rdf:type sci:Gene ;
        skos:prefLabel "TP53" ;
        schema:identifier "gene:tp53" ;
        sci:profile "biology" .
}
""",
        encoding="utf-8",
    )

    payload = export_graph_payload(graph_path)
    node = next(node for node in payload.nodes if node.id == "http://example.org/project/gene/tp53")

    assert node.label == "TP53"
    assert node.graph_layer == "graph/knowledge"
    assert next(layer for layer in payload.layers if layer.id == "graph/knowledge").node_count == 1


def test_export_graph_payload_excludes_unmaterialized_default_layers(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        """\
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix schema: <https://schema.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix model: <http://example.org/project/model/> .
@prefix source: <http://example.org/project/source/> .

<http://example.org/project/graph/model> {
    model:lorenz-attractor rdf:type sci:Model .
    model:lorenz-attractor skos:prefLabel "Lorenz attractor" .
    model:lorenz-attractor schema:identifier "model:lorenz-attractor" .
}

<http://example.org/project/graph/provenance> {
    model:lorenz-attractor prov:wasDerivedFrom source:model .
}
""",
        encoding="utf-8",
    )

    payload = export_graph_payload(graph_path)

    assert [layer.id for layer in payload.layers] == ["graph/model", "graph/provenance"]


def test_export_graph_payload_includes_causal_overlay_for_inquiry(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])

    causal_overlay = cast(CausalOverlays, payload.overlays.causal)
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
    # `concept:modifier` is already an interior node of test_dag (fixture flow
    # edge); authoring the concept makes it an exported member so the confounds
    # edge below is associated with the inquiry in the causal overlay.
    _build_base_graph(
        graph_path.parent.parent,
        entities=[_concept("modifier", "Modifier")],
        relations=[_causal_relation("concept:modifier", "scic:confounds", "concept:recovery")],
    )

    payload = export_graph_payload(graph_path, overlays=["causal"])
    inquiry = cast(CausalOverlays, payload.overlays.causal)["inquiries"]["inquiry/test_dag"]
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

    inquiry = cast(CausalOverlays, payload.overlays.causal)["inquiries"]["inquiry/dangling_dag"]

    assert "http://example.org/project/concept/unexported_boundary" not in inquiry["boundary_roles"]


# Removed in kernel-closure Phase 3a: evidence overlay fields such as
# bridge_between, statistical_support, and pre_registrations were mutator-only
# claim payload shapes with no authored-source form.


def test_export_graph_payload_skips_missing_claim_refs_with_warning(graph_path: Path) -> None:
    dataset = _load_dataset(graph_path)
    causal_graph = dataset.graph(_graph_uri("graph/causal"))
    edge_subject = URIRef("http://example.org/project/concept/drug")
    edge_predicate = URIRef("http://example.org/science/vocab/causal/causes")
    edge_object = URIRef("http://example.org/project/concept/recovery")
    statement_uri = URIRef("http://example.org/project/statement/missing-claim-test")
    causal_graph.add((statement_uri, RDF.type, RDF.Statement))
    causal_graph.add((statement_uri, RDF.subject, edge_subject))
    causal_graph.add((statement_uri, RDF.predicate, edge_predicate))
    causal_graph.add((statement_uri, RDF.object, edge_object))
    causal_graph.add(
        (statement_uri, SCI_NS.backedByClaim, URIRef("http://example.org/project/proposition/missing_claim"))
    )
    _save_dataset(dataset, graph_path)

    payload = export_graph_payload(graph_path, overlays=["evidence"])

    assert any("missing claim ref" in warning for warning in payload.warnings)


def test_dcat_downloadurl_is_metadata_not_an_edge(tmp_path: Path) -> None:
    # dcat:distribution is a real dataset->resource edge; dcat:downloadURL is metadata
    # about the distribution and must NOT become a spurious exported edge to the URL.
    (tmp_path / "science.yaml").write_text(
        "name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8"
    )
    pkg = tmp_path / "data" / "ds1"
    pkg.mkdir(parents=True)
    (pkg / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "ds1",
                "id": "dataset:ds1",
                "kind": "dataset",
                "title": "DS1",
                "origin": "external",
                "access": {"level": "public", "verified": False},
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.parquet",
                        "source": {"type": "url", "ref": "https://example.org/counts.parquet"},
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    dataset = _build_dataset_from_sources(load_project_sources(tmp_path, include_commons=False))
    graph_path = tmp_path / "graph.trig"
    _save_dataset(dataset, graph_path)

    edge_predicates = {edge.predicate for edge in export_graph_payload(graph_path).edges}
    assert str(DCAT_NS.distribution) in edge_predicates
    assert str(DCAT_NS.downloadURL) not in edge_predicates

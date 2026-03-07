"""Tests for inquiry abstraction."""

from pathlib import Path

import pytest
from rdflib import RDF, Literal, URIRef

from science_tool.graph.store import (
    DCTERMS_NS,
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    SCI_NS,
    add_assumption,
    add_concept,
    add_inquiry,
    add_inquiry_edge,
    set_boundary_role,
)
from rdflib.namespace import SKOS


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class TestOntologyExtensions:
    def test_inquiry_predicates_registered(self) -> None:
        """New inquiry predicates appear in the registry."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        for pred in [
            "sci:target",
            "sci:boundaryRole",
            "sci:inquiryStatus",
            "sci:feedsInto",
            "sci:assumes",
            "sci:produces",
            "sci:paramValue",
            "sci:paramSource",
            "sci:paramRef",
            "sci:paramNote",
            "sci:observability",
            "sci:validatedBy",
        ]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_inquiry_predicates_have_inquiry_layer(self) -> None:
        """Inquiry-specific predicates use 'inquiry' layer."""
        inquiry_preds = [
            p for p in PREDICATE_REGISTRY if p["layer"] == "inquiry"
        ]
        assert len(inquiry_preds) >= 8

    def test_boundary_role_constants(self) -> None:
        """BoundaryIn and BoundaryOut are defined as URIRefs."""
        assert SCI_NS.BoundaryIn is not None
        assert SCI_NS.BoundaryOut is not None
        assert str(SCI_NS.BoundaryIn).endswith("BoundaryIn")
        assert str(SCI_NS.BoundaryOut).endswith("BoundaryOut")

    def test_inquiry_type_constants(self) -> None:
        """Inquiry entity types are defined."""
        for type_name in ["Inquiry", "Variable", "Transformation", "Assumption", "Unknown", "ValidationCheck"]:
            attr = getattr(SCI_NS, type_name)
            assert str(attr).endswith(type_name)


class TestInquiryCreation:
    def test_add_inquiry(self, graph_path: Path) -> None:
        uri = add_inquiry(
            graph_path,
            slug="sp-geometry",
            label="Signal peptide geometry",
            target="hypothesis:h03",
            description="Test SP embedding geometry",
        )
        assert "inquiry/sp_geometry" in str(uri)
        from science_tool.graph.store import _load_dataset, _graph_uri

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/sp_geometry"))
        assert (uri, RDF.type, SCI_NS.Inquiry) in inquiry_graph
        assert (uri, SKOS.prefLabel, Literal("Signal peptide geometry")) in inquiry_graph
        assert (uri, SCI_NS.inquiryStatus, Literal("sketch")) in inquiry_graph

    def test_add_inquiry_custom_status(self, graph_path: Path) -> None:
        uri = add_inquiry(graph_path, slug="test-inq", label="Test", target="hypothesis:h01", status="specified")
        from science_tool.graph.store import _load_dataset

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test_inq"))
        assert (uri, SCI_NS.inquiryStatus, Literal("specified")) in inquiry_graph

    def test_add_inquiry_duplicate_raises(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="dup", label="First", target="hypothesis:h01")
        with pytest.raises(ValueError, match="already exists"):
            add_inquiry(graph_path, slug="dup", label="Second", target="hypothesis:h01")


class TestBoundaryRoles:
    def test_set_boundary_in(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        add_concept(graph_path, "uniprot_data", concept_type="sci:Variable", ontology_id=None)
        set_boundary_role(graph_path, "test", "concept:uniprot_data", "BoundaryIn")
        from science_tool.graph.store import _load_dataset

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        concept_uri = PROJECT_NS["concept/uniprot_data"]
        assert (concept_uri, SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in inquiry_graph

    def test_set_boundary_out(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        add_concept(graph_path, "results", concept_type="sci:Variable", ontology_id=None)
        set_boundary_role(graph_path, "test", "concept:results", "BoundaryOut")
        from science_tool.graph.store import _load_dataset

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        concept_uri = PROJECT_NS["concept/results"]
        assert (concept_uri, SCI_NS.boundaryRole, SCI_NS.BoundaryOut) in inquiry_graph

    def test_invalid_boundary_role_raises(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        add_concept(graph_path, "node", concept_type=None, ontology_id=None)
        with pytest.raises(ValueError, match="Invalid boundary role"):
            set_boundary_role(graph_path, "test", "concept:node", "Interior")

    def test_boundary_role_nonexistent_inquiry_raises(self, graph_path: Path) -> None:
        add_concept(graph_path, "node", concept_type=None, ontology_id=None)
        with pytest.raises(ValueError, match="does not exist"):
            set_boundary_role(graph_path, "nonexistent", "concept:node", "BoundaryIn")


class TestInquiryEdges:
    def test_add_inquiry_edge(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        add_concept(graph_path, "input_data", concept_type=None, ontology_id=None)
        add_concept(graph_path, "output_data", concept_type=None, ontology_id=None)
        add_inquiry_edge(graph_path, "test", "concept:input_data", "sci:feedsInto", "concept:output_data")
        from science_tool.graph.store import _load_dataset

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (
            PROJECT_NS["concept/input_data"],
            SCI_NS.feedsInto,
            PROJECT_NS["concept/output_data"],
        ) in inquiry_graph

    def test_add_assumption(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        uri = add_assumption(
            graph_path,
            label="Mean pooling sufficient",
            source="paper:doi_10_1234_test",
            inquiry_slug="test",
        )
        assert "concept/mean_pooling_sufficient" in str(uri)
        from science_tool.graph.store import _load_dataset, _graph_uri

        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        assert (uri, RDF.type, SCI_NS.Assumption) in knowledge
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert len(list(inquiry_graph.triples((uri, None, None)))) > 0

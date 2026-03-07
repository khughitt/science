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
    _graph_uri,
    _load_dataset,
    add_assumption,
    add_concept,
    add_inquiry,
    add_inquiry_edge,
    add_transformation,
    get_inquiry,
    list_inquiries,
    set_boundary_role,
    set_param_metadata,
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


class TestTransformations:
    def test_add_transformation(self, graph_path: Path) -> None:
        """Add a transformation step to an inquiry."""
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        uri = add_transformation(graph_path, label="Extract sequences", inquiry_slug="test", tool="BioPython")
        assert "concept/extract_sequences" in str(uri)
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (uri, RDF.type, SCI_NS.Transformation) in inquiry_graph
        assert (uri, SCI_NS.tool, Literal("BioPython")) in inquiry_graph

    def test_add_transformation_with_params(self, graph_path: Path) -> None:
        """Add a transformation with parameter metadata."""
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        params = {
            "batch_size": {"value": "32", "source": "design_decision", "note": "GPU memory constraint"},
        }
        uri = add_transformation(
            graph_path, label="Train model", inquiry_slug="test", tool="PyTorch", params=params
        )
        assert "concept/train_model" in str(uri)
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (uri, SCI_NS.tool, Literal("PyTorch")) in inquiry_graph

    def test_add_transformation_no_tool(self, graph_path: Path) -> None:
        """Add a transformation without specifying a tool."""
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        uri = add_transformation(graph_path, label="Normalize data", inquiry_slug="test")
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (uri, RDF.type, SCI_NS.Transformation) in inquiry_graph
        assert len(list(inquiry_graph.triples((uri, SCI_NS.tool, None)))) == 0


class TestParamMetadata:
    def test_set_param_metadata(self, graph_path: Path) -> None:
        """Attach AnnotatedParam-style metadata to an entity."""
        add_concept(graph_path, "pooling_method", concept_type=None, ontology_id=None)
        set_param_metadata(
            graph_path,
            entity="concept:pooling_method",
            value="mean",
            source="design_decision",
            refs=["doc/04-approach.md"],
            note="Captures SP-relevant information",
        )
        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        entity_uri = PROJECT_NS["concept/pooling_method"]
        assert (entity_uri, SCI_NS.paramValue, Literal("mean")) in knowledge
        assert (entity_uri, SCI_NS.paramSource, Literal("design_decision")) in knowledge
        assert (entity_uri, SCI_NS.paramNote, Literal("Captures SP-relevant information")) in knowledge
        assert (entity_uri, SCI_NS.paramRef, Literal("doc/04-approach.md")) in knowledge

    def test_set_param_metadata_no_optional(self, graph_path: Path) -> None:
        """Set param metadata without optional fields."""
        add_concept(graph_path, "learning_rate", concept_type=None, ontology_id=None)
        set_param_metadata(graph_path, entity="concept:learning_rate", value="0.001", source="hyperparameter_search")
        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        entity_uri = PROJECT_NS["concept/learning_rate"]
        assert (entity_uri, SCI_NS.paramValue, Literal("0.001")) in knowledge
        assert (entity_uri, SCI_NS.paramSource, Literal("hyperparameter_search")) in knowledge
        assert len(list(knowledge.triples((entity_uri, SCI_NS.paramNote, None)))) == 0


class TestInquiryQueries:
    def test_list_inquiries_empty(self, graph_path: Path) -> None:
        result = list_inquiries(graph_path)
        assert result == []

    def test_list_inquiries(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="inq-1", label="First", target="hypothesis:h01")
        add_inquiry(graph_path, slug="inq-2", label="Second", target="hypothesis:h02")
        result = list_inquiries(graph_path)
        assert len(result) == 2
        labels = {r["label"] for r in result}
        assert labels == {"First", "Second"}

    def test_list_inquiries_has_fields(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test Inquiry", target="hypothesis:h01", status="specified")
        result = list_inquiries(graph_path)
        assert len(result) == 1
        entry = result[0]
        assert entry["label"] == "Test Inquiry"
        assert entry["status"] == "specified"
        assert entry["slug"] == "test"

    def test_get_inquiry(self, graph_path: Path) -> None:
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01", description="Test inquiry")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "test", "concept:data_in", "BoundaryIn")
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "test", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "test", "concept:data_in", "sci:feedsInto", "concept:result_out")
        result = get_inquiry(graph_path, "test")
        assert result["label"] == "Test"
        assert result["status"] == "sketch"
        assert len(result["boundary_in"]) == 1
        assert len(result["boundary_out"]) == 1
        assert len(result["edges"]) >= 1

    def test_get_inquiry_nonexistent_raises(self, graph_path: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            get_inquiry(graph_path, "nonexistent")

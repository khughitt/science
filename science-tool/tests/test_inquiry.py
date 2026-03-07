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
    add_inquiry_node,
    add_transformation,
    get_inquiry,
    list_inquiries,
    render_inquiry_doc,
    set_boundary_role,
    set_param_metadata,
    validate_inquiry,
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


class TestInquiryValidation:
    def test_valid_inquiry_passes(self, graph_path: Path) -> None:
        """A well-formed inquiry passes all checks."""
        add_inquiry(graph_path, slug="valid", label="Valid", target="hypothesis:h01")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "valid", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "valid", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "valid", "concept:data_in", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "valid")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "pass"
        assert statuses["no_cycles"] == "pass"

    def test_unreachable_boundary_out_fails(self, graph_path: Path) -> None:
        """BoundaryOut not reachable from any BoundaryIn."""
        add_inquiry(graph_path, slug="unreach", label="Unreachable", target="hypothesis:h01")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        add_concept(graph_path, "disconnected_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "unreach", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "unreach", "concept:result_out", "BoundaryOut")
        set_boundary_role(graph_path, "unreach", "concept:disconnected_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "unreach", "concept:data_in", "sci:feedsInto", "concept:result_out")
        # disconnected_out has no incoming path

        results = validate_inquiry(graph_path, "unreach")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "fail"

    def test_cycle_in_feeds_into_fails(self, graph_path: Path) -> None:
        """Cycles in feedsInto edges fail."""
        add_inquiry(graph_path, slug="cycle", label="Cycle", target="hypothesis:h01")
        add_concept(graph_path, "a", concept_type=None, ontology_id=None)
        add_concept(graph_path, "b", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "cycle", "concept:a", "BoundaryIn")
        set_boundary_role(graph_path, "cycle", "concept:b", "BoundaryOut")
        add_inquiry_edge(graph_path, "cycle", "concept:a", "sci:feedsInto", "concept:b")
        add_inquiry_edge(graph_path, "cycle", "concept:b", "sci:feedsInto", "concept:a")

        results = validate_inquiry(graph_path, "cycle")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["no_cycles"] == "fail"

    def test_unknown_in_specified_fails(self, graph_path: Path) -> None:
        """sci:Unknown nodes in a specified inquiry fail."""
        add_inquiry(graph_path, slug="unk", label="Unknown", target="hypothesis:h01", status="specified")
        add_concept(graph_path, "mystery", concept_type="sci:Unknown", ontology_id=None)
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "unk", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "unk", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "unk", "concept:data_in", "sci:feedsInto", "concept:mystery")
        add_inquiry_edge(graph_path, "unk", "concept:mystery", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "fail"

    def test_unknown_in_sketch_passes(self, graph_path: Path) -> None:
        """sci:Unknown nodes in a sketch are allowed."""
        add_inquiry(graph_path, slug="sketch-unk", label="Sketch", target="hypothesis:h01", status="sketch")
        add_concept(graph_path, "mystery", concept_type="sci:Unknown", ontology_id=None)
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "sketch-unk", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "sketch-unk", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "sketch-unk", "concept:data_in", "sci:feedsInto", "concept:mystery")
        add_inquiry_edge(graph_path, "sketch-unk", "concept:mystery", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "sketch-unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "pass"


class TestInteriorNodes:
    def test_add_inquiry_node_interior(self, graph_path: Path) -> None:
        """Add an interior node (no boundary role) to an inquiry."""
        add_inquiry(graph_path, slug="test", label="Test", target="hypothesis:h01")
        add_concept(graph_path, "middle_step", concept_type="sci:Variable", ontology_id=None)
        add_inquiry_node(graph_path, "test", "concept:middle_step")
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        concept_uri = PROJECT_NS["concept/middle_step"]
        # Should have a type triple in the inquiry graph but no boundary role
        assert any(inquiry_graph.triples((concept_uri, RDF.type, None)))
        assert not any(inquiry_graph.triples((concept_uri, SCI_NS.boundaryRole, None)))

    def test_add_inquiry_node_nonexistent_inquiry_raises(self, graph_path: Path) -> None:
        add_concept(graph_path, "node", concept_type=None, ontology_id=None)
        with pytest.raises(ValueError, match="does not exist"):
            add_inquiry_node(graph_path, "nonexistent", "concept:node")


class TestInquiryRender:
    def test_render_inquiry_doc(self, graph_path: Path) -> None:
        add_inquiry(
            graph_path, slug="test", label="Test Inquiry", target="hypothesis:h01", description="A test inquiry"
        )
        add_concept(graph_path, "data_in", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "result_out", concept_type="sci:Variable", ontology_id=None)
        set_boundary_role(graph_path, "test", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "test", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "test", "concept:data_in", "sci:feedsInto", "concept:result_out")
        doc = render_inquiry_doc(graph_path, "test")
        assert "# Inquiry: Test Inquiry" in doc
        assert "data_in" in doc
        assert "result_out" in doc
        assert "## Data Flow" in doc
        assert "feedsInto" in doc
        assert "A test inquiry" in doc
        assert "## Unknowns" in doc

    def test_render_with_unknowns(self, graph_path: Path) -> None:
        """Unknowns section renders when sci:Unknown nodes are present."""
        add_inquiry(graph_path, slug="unk-render", label="Unknown Render", target="hypothesis:h01")
        add_concept(graph_path, "data_in", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "mystery_factor", concept_type="sci:Unknown", ontology_id=None)
        add_concept(graph_path, "result_out", concept_type="sci:Variable", ontology_id=None)
        set_boundary_role(graph_path, "unk-render", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "unk-render", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "unk-render", "concept:data_in", "sci:feedsInto", "concept:mystery_factor")
        add_inquiry_edge(graph_path, "unk-render", "concept:mystery_factor", "sci:feedsInto", "concept:result_out")
        doc = render_inquiry_doc(graph_path, "unk-render")
        assert "## Unknowns" in doc
        assert "mystery_factor" in doc


class TestOrphanedInteriorValidation:
    def test_orphaned_interior_warns(self, graph_path: Path) -> None:
        """Interior node with no outgoing flow edge triggers warning."""
        add_inquiry(graph_path, slug="orphan", label="Orphan", target="hypothesis:h01")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "middle", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "orphan", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "orphan", "concept:result_out", "BoundaryOut")
        # data_in -> middle, data_in -> result_out, but middle has no outgoing edge
        add_inquiry_edge(graph_path, "orphan", "concept:data_in", "sci:feedsInto", "concept:middle")
        add_inquiry_edge(graph_path, "orphan", "concept:data_in", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "orphan")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["orphaned_interior"] == "warn"

    def test_no_orphans_passes(self, graph_path: Path) -> None:
        """Well-connected interior node passes orphan check."""
        add_inquiry(graph_path, slug="connected", label="Connected", target="hypothesis:h01")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "middle", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "connected", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "connected", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "connected", "concept:data_in", "sci:feedsInto", "concept:middle")
        add_inquiry_edge(graph_path, "connected", "concept:middle", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "connected")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["orphaned_interior"] == "pass"


class TestProvenanceCompletenessValidation:
    def test_missing_provenance_fails_specified(self, graph_path: Path) -> None:
        """Assumption without prov:wasDerivedFrom fails in specified inquiry."""
        add_inquiry(graph_path, slug="no-prov", label="No Prov", target="hypothesis:h01", status="specified")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "no-prov", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "no-prov", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "no-prov", "concept:data_in", "sci:feedsInto", "concept:result_out")
        # Add assumption directly to inquiry graph without provenance
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/no_prov"))
        assumption_uri = URIRef(str(PROJECT_NS) + "concept/unproven_assumption")
        inquiry_graph.add((assumption_uri, RDF.type, SCI_NS.Assumption))
        from science_tool.graph.store import _save_dataset
        _save_dataset(dataset, graph_path)

        results = validate_inquiry(graph_path, "no-prov")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["provenance_completeness"] == "fail"

    def test_provenance_present_passes(self, graph_path: Path) -> None:
        """Assumption with provenance passes in specified inquiry."""
        add_inquiry(graph_path, slug="with-prov", label="With Prov", target="hypothesis:h01", status="specified")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "with-prov", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "with-prov", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "with-prov", "concept:data_in", "sci:feedsInto", "concept:result_out")
        # add_assumption uses add_concept which adds provenance via --source
        add_assumption(graph_path, label="Justified claim", source="paper:doi_test", inquiry_slug="with-prov")

        results = validate_inquiry(graph_path, "with-prov")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["provenance_completeness"] == "pass"

    def test_provenance_not_checked_in_sketch(self, graph_path: Path) -> None:
        """Provenance completeness is not checked for sketch inquiries."""
        add_inquiry(graph_path, slug="sketch-prov", label="Sketch", target="hypothesis:h01", status="sketch")
        add_concept(graph_path, "data_in", concept_type=None, ontology_id=None)
        add_concept(graph_path, "result_out", concept_type=None, ontology_id=None)
        set_boundary_role(graph_path, "sketch-prov", "concept:data_in", "BoundaryIn")
        set_boundary_role(graph_path, "sketch-prov", "concept:result_out", "BoundaryOut")
        add_inquiry_edge(graph_path, "sketch-prov", "concept:data_in", "sci:feedsInto", "concept:result_out")

        results = validate_inquiry(graph_path, "sketch-prov")
        check_names = [r["check"] for r in results]
        assert "provenance_completeness" not in check_names

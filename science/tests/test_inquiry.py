"""Tests for inquiry abstraction."""

from pathlib import Path

import pytest
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import SKOS

from conftest import build_inquiry_graph

from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    _save_dataset,
    add_concept,
    get_inquiry,
    list_inquiries,
    render_inquiry_doc,
    validate_inquiry,
)


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
            "sci:backedByClaim",
            "sci:validatedBy",
        ]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_inquiry_predicates_have_inquiry_layer(self) -> None:
        """Inquiry-specific predicates use 'inquiry' layer."""
        inquiry_preds = [p for p in PREDICATE_REGISTRY if p["layer"] == "inquiry"]
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


# The structural emission of inquiries (sci:Inquiry type/label/status, boundary
# roles, flow edges, reified edge-claims, minted assumptions with provenance) is
# proven directly against the source compiler in test_inquiry_compile.py — the
# path that replaced the retired add_inquiry / set_boundary_role / add_inquiry_edge
# / add_assumption mutators. Duplicate patch-definition ids are rejected at source
# load, not per-inquiry. The remaining inquiry tests below exercise the live
# readers/validators over source-built inquiry graphs.


class TestBoundaryRoleModel:
    def test_boundary_role_rejects_invalid_role(self) -> None:
        """An invalid boundary role fails early at model parse (was an
        add-time guard in the retired set_boundary_role mutator)."""
        from pydantic import ValidationError
        from science_model.patch_definition import BoundaryRole

        with pytest.raises(ValidationError):
            BoundaryRole(ref="concept:node", role="Interior")  # type: ignore[arg-type]


class TestTransformations:
    """Transformation nodes (and their params) are authored on the inquiry
    profile and minted by the compiler at inquiry/<slug>/transformation/<ref>."""

    @staticmethod
    def _transformation_node(slug: str, ref_local: str) -> URIRef:
        return URIRef(str(PROJECT_NS) + f"inquiry/{slug}/transformation/{ref_local}")

    def test_transformation_with_tool(self, graph_path: Path) -> None:
        build_inquiry_graph(
            graph_path,
            slug="test",
            transformations=[{"ref": "transformation:extract_sequences", "tool": "BioPython"}],
        )
        inquiry_graph = _load_dataset(graph_path).graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        node = self._transformation_node("test", "extract_sequences")
        assert (node, RDF.type, SCI_NS.Transformation) in inquiry_graph
        assert (node, SCI_NS.tool, Literal("BioPython")) in inquiry_graph

    def test_transformation_with_params(self, graph_path: Path) -> None:
        build_inquiry_graph(
            graph_path,
            slug="test",
            transformations=[
                {
                    "ref": "transformation:train_model",
                    "tool": "PyTorch",
                    "params": [{"value": "32", "source": "design_decision", "note": "GPU memory constraint"}],
                }
            ],
        )
        inquiry_graph = _load_dataset(graph_path).graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        node = self._transformation_node("test", "train_model")
        assert (node, SCI_NS.tool, Literal("PyTorch")) in inquiry_graph
        assert (node, SCI_NS.paramValue, Literal("32")) in inquiry_graph
        assert (node, SCI_NS.paramSource, Literal("design_decision")) in inquiry_graph
        assert (node, SCI_NS.paramNote, Literal("GPU memory constraint")) in inquiry_graph

    def test_transformation_no_tool(self, graph_path: Path) -> None:
        build_inquiry_graph(
            graph_path,
            slug="test",
            transformations=[{"ref": "transformation:normalize_data"}],
        )
        inquiry_graph = _load_dataset(graph_path).graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        node = self._transformation_node("test", "normalize_data")
        assert (node, RDF.type, SCI_NS.Transformation) in inquiry_graph
        assert len(list(inquiry_graph.triples((node, SCI_NS.tool, None)))) == 0


# Concept-level AnnotatedParam metadata (the retired set_param_metadata mutator)
# had no source-authoring path and no live reader; its tests were removed with the
# writer rather than migrated, and render_inquiry_doc's dead knowledge-graph param
# branch (the sole would-be consumer) has since been deleted too. Transformation-node
# params (which the compiler DOES support from source) are covered by
# TestTransformations above.


class TestInquiryQueries:
    def test_list_inquiries_empty(self, graph_path: Path) -> None:
        result = list_inquiries(graph_path)
        assert result == []

    def test_list_inquiries(self, graph_path: Path) -> None:
        build_inquiry_graph(graph_path, slug="inq_1", title="First")
        build_inquiry_graph(graph_path, slug="inq_2", title="Second", focal="hypothesis:h02")
        result = list_inquiries(graph_path)
        assert len(result) == 2
        labels = {r["label"] for r in result}
        assert labels == {"First", "Second"}

    def test_list_inquiries_has_fields(self, graph_path: Path) -> None:
        build_inquiry_graph(graph_path, slug="test", title="Test Inquiry", status="specified")
        result = list_inquiries(graph_path)
        assert len(result) == 1
        entry = result[0]
        assert entry["label"] == "Test Inquiry"
        assert entry["status"] == "specified"
        assert entry["slug"] == "test"

    def test_get_inquiry(self, graph_path: Path) -> None:
        build_inquiry_graph(
            graph_path,
            slug="test",
            title="Test",
            status="sketch",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
        )
        result = get_inquiry(graph_path, "test")
        assert result["label"] == "Test"
        assert result["status"] == "sketch"
        assert len(result["boundary_in"]) == 1
        assert len(result["boundary_out"]) == 1
        assert len(result["edges"]) >= 1

    def test_get_inquiry_nonexistent_raises(self, graph_path: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            get_inquiry(graph_path, "nonexistent")


def _add_materialized_inquiry(
    graph_path: Path,
    slug: str,
    label: str,
    *,
    status: str = "draft",
    related: tuple[str, ...] = (),
) -> URIRef:
    """Mimic `materialize_graph`: emit an inquiry as an entity inside the shared
    ``graph/knowledge`` layer (hyphen-preserving slug, ``sci:projectStatus``),
    rather than a dedicated per-inquiry named graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    uri = URIRef(PROJECT_NS[f"inquiry/{slug}"])
    knowledge.add((uri, RDF.type, SCI_NS.Inquiry))
    knowledge.add((uri, SKOS.prefLabel, Literal(label)))
    knowledge.add((uri, SCI_NS.projectStatus, Literal(status)))
    for rel in related:
        knowledge.add((uri, SKOS.related, URIRef(PROJECT_NS[rel])))
    _save_dataset(dataset, graph_path)
    return uri


class TestMaterializedInquiryQueries:
    """Inquiries built by `materialize_graph` live as entities in the shared
    ``graph/knowledge`` layer, not per-inquiry named graphs. The read commands
    must find them (fb-2026-05-12-001)."""

    def test_list_inquiries_finds_materialized_entity(self, graph_path: Path) -> None:
        _add_materialized_inquiry(graph_path, "h-3d-genome-substrate", "3D genome substrate")
        result = list_inquiries(graph_path)
        slugs = {r["slug"] for r in result}
        assert "h-3d-genome-substrate" in slugs

    def test_list_inquiries_materialized_status_from_project_status(self, graph_path: Path) -> None:
        _add_materialized_inquiry(graph_path, "h1-h2-bridge", "Bridge", status="draft")
        entry = next(r for r in list_inquiries(graph_path) if r["slug"] == "h1-h2-bridge")
        assert entry["label"] == "Bridge"
        assert entry["status"] == "draft"

    def test_get_inquiry_materialized_hyphenated_slug(self, graph_path: Path) -> None:
        _add_materialized_inquiry(
            graph_path,
            "h-3d-genome-substrate",
            "3D genome substrate",
            status="draft",
            related=("hypothesis/h01",),
        )
        result = get_inquiry(graph_path, "h-3d-genome-substrate")
        assert result["label"] == "3D genome substrate"
        assert result["status"] == "draft"
        # No per-inquiry subgraph exists in the materialized layout.
        assert result["boundary_in"] == []
        assert result["boundary_out"] == []
        assert result["edges"] == []
        # The rich `skos:related` list is the materialized inquiry's content.
        assert str(PROJECT_NS["hypothesis/h01"]) in result["related"]

    def test_get_inquiry_materialized_does_not_leak_knowledge_edges(self, graph_path: Path) -> None:
        """Reading a materialized inquiry must not treat every triple in the
        shared knowledge graph as one of its edges."""
        add_concept(graph_path, "unrelated_concept", concept_type=None, ontology_id=None)
        _add_materialized_inquiry(graph_path, "h-3d-genome-substrate", "3D genome substrate")
        result = get_inquiry(graph_path, "h-3d-genome-substrate")
        assert result["edges"] == []

    def test_validate_inquiry_materialized_hyphenated_slug(self, graph_path: Path) -> None:
        _add_materialized_inquiry(graph_path, "h-3d-genome-substrate", "3D genome substrate")

        results = validate_inquiry(graph_path, "h-3d-genome-substrate")

        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "pass"
        assert statuses["target_exists"] == "warn"


class TestInquiryValidation:
    def test_valid_inquiry_passes(self, graph_path: Path) -> None:
        """A well-formed inquiry passes all checks."""
        build_inquiry_graph(
            graph_path,
            slug="valid",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
        )

        results = validate_inquiry(graph_path, "valid")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "pass"
        assert statuses["no_cycles"] == "pass"

    def test_unreachable_boundary_out_fails(self, graph_path: Path) -> None:
        """BoundaryOut not reachable from any BoundaryIn."""
        build_inquiry_graph(
            graph_path,
            slug="unreach",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
                {"ref": "concept:disconnected_out", "role": "BoundaryOut"},  # no incoming path
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
        )

        results = validate_inquiry(graph_path, "unreach")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "fail"

    def test_cycle_in_feeds_into_fails(self, graph_path: Path) -> None:
        """Cycles in feedsInto edges fail."""
        build_inquiry_graph(
            graph_path,
            slug="cycle",
            boundary_roles=[
                {"ref": "concept:a", "role": "BoundaryIn"},
                {"ref": "concept:b", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:a", "predicate": "feedsInto", "object": "concept:b"},
                {"subject": "concept:b", "predicate": "feedsInto", "object": "concept:a"},
            ],
        )

        results = validate_inquiry(graph_path, "cycle")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["no_cycles"] == "fail"

    def test_unknown_in_specified_fails(self, graph_path: Path) -> None:
        """sci:Unknown nodes in a specified inquiry fail."""
        build_inquiry_graph(
            graph_path,
            slug="unk",
            status="specified",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:mystery"},
                {"subject": "concept:mystery", "predicate": "feedsInto", "object": "concept:result_out"},
            ],
            unknowns=["concept:mystery"],
        )

        results = validate_inquiry(graph_path, "unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "fail"

    def test_unknown_in_sketch_passes(self, graph_path: Path) -> None:
        """sci:Unknown nodes in a sketch are allowed."""
        build_inquiry_graph(
            graph_path,
            slug="sketch_unk",
            status="sketch",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:mystery"},
                {"subject": "concept:mystery", "predicate": "feedsInto", "object": "concept:result_out"},
            ],
            unknowns=["concept:mystery"],
        )

        results = validate_inquiry(graph_path, "sketch_unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "pass"


# Bare interior nodes (the retired add_inquiry_node) have no source-model form:
# an interior node exists by participating in a flow edge, which the compiler
# emits (test_inquiry_compile.py::test_boundary_and_flow_edges_emitted; the
# export-side interior-node behavior is exercised in test_graph_export.py). The
# "does not exist" guard was mutator-only.


class TestInquiryRender:
    def test_render_inquiry_doc(self, graph_path: Path) -> None:
        # Note: the inquiry free-text description (SKOS.note) is a retired-mutator
        # feature the source compiler does not emit, so it is not asserted here.
        build_inquiry_graph(
            graph_path,
            slug="test",
            title="Test Inquiry",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
        )
        doc = render_inquiry_doc(graph_path, "test")
        assert doc.startswith("---\n")
        assert 'id: "inquiry:test"' in doc
        assert 'type: "inquiry"' in doc
        assert 'title: "Test Inquiry"' in doc
        assert 'status: "' in doc
        assert 'target: "' in doc
        assert "# Inquiry: Test Inquiry" in doc
        assert "data_in" in doc
        assert "result_out" in doc
        assert "## Data Flow" in doc
        assert "feedsInto" in doc
        assert "## Unknowns" in doc

    def test_render_with_unknowns(self, graph_path: Path) -> None:
        """Unknowns section renders when sci:Unknown nodes are present."""
        build_inquiry_graph(
            graph_path,
            slug="unk_render",
            title="Unknown Render",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:mystery_factor"},
                {"subject": "concept:mystery_factor", "predicate": "feedsInto", "object": "concept:result_out"},
            ],
            unknowns=["concept:mystery_factor"],
        )
        doc = render_inquiry_doc(graph_path, "unk_render")
        assert "## Unknowns" in doc
        assert "mystery_factor" in doc


class TestOrphanedInteriorValidation:
    def test_orphaned_interior_warns(self, graph_path: Path) -> None:
        """Interior node with no outgoing flow edge triggers warning."""
        build_inquiry_graph(
            graph_path,
            slug="orphan",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            # data_in -> middle, data_in -> result_out, but middle has no outgoing edge
            flow_edges=[
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:middle"},
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"},
            ],
        )

        results = validate_inquiry(graph_path, "orphan")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["orphaned_interior"] == "warn"

    def test_no_orphans_passes(self, graph_path: Path) -> None:
        """Well-connected interior node passes orphan check."""
        build_inquiry_graph(
            graph_path,
            slug="connected",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:middle"},
                {"subject": "concept:middle", "predicate": "feedsInto", "object": "concept:result_out"},
            ],
        )

        results = validate_inquiry(graph_path, "connected")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["orphaned_interior"] == "pass"

    def test_causal_inquiry_allows_exogenous_roots_and_terminal_sinks(self, graph_path: Path) -> None:
        """Causal DAGs may have non-boundary source roots and terminal sink nodes."""
        # The causal profile requires an estimand at authoring time; treatment and
        # outcome are the boundary nodes here (a bare estimand-less causal inquiry
        # is not expressible from source, by design).
        build_inquiry_graph(
            graph_path,
            slug="causal_roots_sinks",
            profile="causal",
            treatment="concept:treatment",
            outcome="concept:outcome",
            boundary_roles=[
                {"ref": "concept:treatment", "role": "BoundaryIn"},
                {"ref": "concept:outcome", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {"subject": "concept:treatment", "predicate": "feedsInto", "object": "concept:mediator"},
                {"subject": "concept:latent_root", "predicate": "feedsInto", "object": "concept:mediator"},
                {"subject": "concept:mediator", "predicate": "feedsInto", "object": "concept:outcome"},
                {"subject": "concept:mediator", "predicate": "feedsInto", "object": "concept:selection_sink"},
            ],
        )

        results = validate_inquiry(graph_path, "causal_roots_sinks")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["orphaned_interior"] == "pass"


class TestProvenanceCompletenessValidation:
    def test_missing_provenance_fails_specified(self, graph_path: Path) -> None:
        """Assumption without prov:wasDerivedFrom fails in specified inquiry."""
        build_inquiry_graph(
            graph_path,
            slug="no_prov",
            status="specified",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
            # Assumption authored with no derived_from -> no prov:wasDerivedFrom emitted.
            assumptions=[{"ref": "assumption:unproven", "statement": "Unproven"}],
        )

        results = validate_inquiry(graph_path, "no_prov")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["provenance_completeness"] == "fail"

    def test_provenance_present_passes(self, graph_path: Path) -> None:
        """Assumption with provenance passes in specified inquiry."""
        build_inquiry_graph(
            graph_path,
            slug="with_prov",
            status="specified",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
            assumptions=[
                {"ref": "assumption:justified", "statement": "Justified claim", "derived_from": "paper:doi_test"}
            ],
        )

        results = validate_inquiry(graph_path, "with_prov")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["provenance_completeness"] == "pass"

    def test_provenance_not_checked_in_sketch(self, graph_path: Path) -> None:
        """Provenance completeness is not checked for sketch inquiries."""
        build_inquiry_graph(
            graph_path,
            slug="sketch_prov",
            status="sketch",
            boundary_roles=[
                {"ref": "concept:data_in", "role": "BoundaryIn"},
                {"ref": "concept:result_out", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:data_in", "predicate": "feedsInto", "object": "concept:result_out"}],
        )

        results = validate_inquiry(graph_path, "sketch_prov")
        check_names = [r["check"] for r in results]
        assert "provenance_completeness" not in check_names

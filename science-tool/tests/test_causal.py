"""Tests for causal inquiry type system."""

from pathlib import Path

import pytest

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    VALID_INQUIRY_TYPES,
    add_claim,
    add_concept,
    add_edge,
    add_hypothesis,
    add_inquiry,
    get_inquiry,
    set_boundary_role,
    set_treatment_outcome,
    validate_inquiry,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class TestInquiryType:
    def test_add_inquiry_with_type_causal(self, graph_path: Path) -> None:
        """Verify inquiry_type='causal' is stored and returned by get_inquiry."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        add_inquiry(
            graph_path,
            slug="causal-test",
            label="Causal Test",
            target="hypothesis:h01",
            inquiry_type="causal",
        )
        result = get_inquiry(graph_path, "causal-test")
        assert result["inquiry_type"] == "causal"

    def test_add_inquiry_default_type_general(self, graph_path: Path) -> None:
        """Verify default inquiry_type is 'general'."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        add_inquiry(
            graph_path,
            slug="general-test",
            label="General Test",
            target="hypothesis:h01",
        )
        result = get_inquiry(graph_path, "general-test")
        assert result["inquiry_type"] == "general"

    def test_invalid_inquiry_type_rejected(self, graph_path: Path) -> None:
        """Verify ValueError on invalid inquiry type."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        with pytest.raises(ValueError, match="Invalid inquiry type"):
            add_inquiry(
                graph_path,
                slug="bad-type",
                label="Bad Type",
                target="hypothesis:h01",
                inquiry_type="randomized",
            )

    def test_causal_predicates_registered(self) -> None:
        """Verify new causal predicates are in PREDICATE_REGISTRY."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        for pred in ["sci:inquiryType", "sci:treatment", "sci:outcome"]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_valid_inquiry_types_constant(self) -> None:
        """Verify the VALID_INQUIRY_TYPES constant."""
        assert "general" in VALID_INQUIRY_TYPES
        assert "causal" in VALID_INQUIRY_TYPES


class TestTreatmentOutcome:
    def test_set_treatment_outcome(self, graph_path: Path) -> None:
        """Setting treatment and outcome stores predicates in inquiry graph."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h01", text="Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "drug-effect", "Drug Effect", "hypothesis:h01", inquiry_type="causal")
        set_treatment_outcome(graph_path, "drug-effect", treatment="concept/drug", outcome="concept/recovery")
        info = get_inquiry(graph_path, "drug-effect")
        assert info["treatment"] == str(PROJECT_NS["concept/drug"])
        assert info["outcome"] == str(PROJECT_NS["concept/recovery"])

    def test_set_treatment_outcome_rejects_non_causal(self, graph_path: Path) -> None:
        """Setting treatment/outcome on a general inquiry raises error."""
        add_hypothesis(graph_path, "h01", text="Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h01")
        with pytest.raises(ValueError, match="only supported for causal"):
            set_treatment_outcome(graph_path, "gen", treatment="concept/x", outcome="concept/y")


class TestCausalValidation:
    def _setup_causal_inquiry(self, graph_path: Path) -> str:
        """Helper: create a causal inquiry with variables and edges."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "test_hyp", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "causal-test", "Causal Test", "hypothesis:test_hyp", inquiry_type="causal")
        set_boundary_role(graph_path, "causal-test", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "causal-test", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "causal-test", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "causal-test", treatment="concept/x", outcome="concept/y")
        return "causal-test"

    def test_acyclic_causal_edges_pass(self, graph_path: Path) -> None:
        """Acyclic causal edges pass validation."""
        slug = self._setup_causal_inquiry(graph_path)
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "pass"

    def test_cyclic_causal_edges_fail(self, graph_path: Path) -> None:
        """Cyclic causal edges fail validation."""
        slug = self._setup_causal_inquiry(graph_path)
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/y", "scic:causes", "concept/x", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "fail"

    def test_general_inquiry_skips_causal_checks(self, graph_path: Path) -> None:
        """General inquiries don't get causal validation checks."""
        add_hypothesis(graph_path, "test_hyp", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:test_hyp")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "causal_acyclicity" not in check_names


class TestExportPgmpy:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Build a simple X->Y<-Z causal inquiry."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "xy-dag", "XY DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "xy-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "xy-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "xy-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "xy-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "xy-dag"

    def test_export_pgmpy_generates_valid_script(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "from pgmpy.models import BayesianNetwork" in script
        assert "BayesianNetwork(" in script
        assert "CausalInference" in script

    def test_export_pgmpy_includes_provenance_comments(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "# Generated from inquiry:" in script

    def test_export_pgmpy_rejects_non_causal(self, graph_path: Path) -> None:
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        with pytest.raises(ValueError, match="only supported for causal"):
            export_pgmpy_script(graph_path, "gen")

    def test_export_pgmpy_contains_edge_tuples(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        # Should contain tuple pairs for edges
        assert '("x", "y")' in script or '("x","y")' in script

    def test_export_pgmpy_edge_level_provenance(self, graph_path: Path) -> None:
        """Export includes claim text, confidence, and source as comments on edges."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "prov-pgmpy", "Prov pgmpy", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-pgmpy", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-pgmpy", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prov-pgmpy", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/study", confidence=0.85)
        script = export_pgmpy_script(graph_path, "prov-pgmpy")
        assert "confidence: 0.85" in script
        assert "doi_10.1234/study" in script

    def test_export_pgmpy_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash when available."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "# Revision:" in script

    def test_export_pgmpy_todo_section(self, graph_path: Path) -> None:
        """Export includes TODO section noting latent variables."""
        add_concept(graph_path, "Hidden", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_concept(graph_path, "Outcome", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "latent-dag", "Latent DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "latent-dag", "concept/hidden", "BoundaryIn")
        set_boundary_role(graph_path, "latent-dag", "concept/outcome", "BoundaryOut")
        set_treatment_outcome(graph_path, "latent-dag", treatment="concept/hidden", outcome="concept/outcome")
        add_edge(graph_path, "concept/hidden", "scic:causes", "concept/outcome", graph_layer="graph/causal")
        script = export_pgmpy_script(graph_path, "latent-dag")
        assert "TODO" in script
        assert "latent" in script.lower()
        assert "hidden" in script.lower()


class TestExportChirho:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Build a simple X->Y<-Z causal inquiry."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "xy-dag", "XY DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "xy-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "xy-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "xy-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "xy-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "xy-dag"

    def test_export_chirho_generates_model_function(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "import pyro" in script
        assert "from chirho.interventional.handlers import do" in script
        assert "def causal_model(" in script
        assert "pyro.sample(" in script

    def test_export_chirho_includes_do_intervention(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "do(causal_model" in script

    def test_export_chirho_rejects_non_causal(self, graph_path: Path) -> None:
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        with pytest.raises(ValueError, match="only supported for causal"):
            export_chirho_script(graph_path, "gen")

    def test_export_chirho_topological_order(self, graph_path: Path) -> None:
        """Root variables appear before dependent variables in the model."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        # x and z are roots, y depends on them
        x_pos = script.index('x = pyro.sample("x"')
        z_pos = script.index('z = pyro.sample("z"')
        y_pos = script.index('y = pyro.sample("y"')
        assert x_pos < y_pos
        assert z_pos < y_pos

    def test_export_chirho_includes_provenance(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "# Generated from inquiry:" in script
        assert "# Treatment: x" in script
        assert "# Outcome: y" in script

    def test_export_chirho_edge_level_provenance(self, graph_path: Path) -> None:
        """Export includes claim provenance as comments on pyro.sample lines."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "prov-chirho", "Prov chirho", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-chirho", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-chirho", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prov-chirho", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/study", confidence=0.85)
        script = export_chirho_script(graph_path, "prov-chirho")
        assert "confidence: 0.85" in script
        assert "doi_10.1234/study" in script

    def test_export_chirho_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "# Revision:" in script

    def test_export_chirho_todo_latent_variables(self, graph_path: Path) -> None:
        """Export TODO section flags latent variables."""
        add_concept(graph_path, "Hidden", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_concept(graph_path, "Visible", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "latent-chirho", "Latent ChiRho", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "latent-chirho", "concept/hidden", "BoundaryIn")
        set_boundary_role(graph_path, "latent-chirho", "concept/visible", "BoundaryOut")
        set_treatment_outcome(graph_path, "latent-chirho", treatment="concept/hidden", outcome="concept/visible")
        add_edge(graph_path, "concept/hidden", "scic:causes", "concept/visible", graph_layer="graph/causal")
        script = export_chirho_script(graph_path, "latent-chirho")
        assert "TODO" in script
        assert "latent" in script.lower()
        assert "hidden" in script.lower()


class TestEdgeProvenance:
    """Tests for enriched edge metadata in causal exports."""

    def _build_dag_with_claims(self, graph_path: Path) -> str:
        """Build a DAG with claims supporting the causal edges."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_concept(graph_path, "Severity", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "prov-dag", "Provenance DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-dag", "concept/recovery", "BoundaryOut")
        set_boundary_role(graph_path, "prov-dag", "concept/severity", "BoundaryIn")
        set_treatment_outcome(graph_path, "prov-dag", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_edge(graph_path, "concept/severity", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_edge(graph_path, "concept/severity", "scic:causes", "concept/drug", graph_layer="graph/causal")
        # Add claims that mention both endpoints
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/drug_recovery", confidence=0.85)
        add_claim(graph_path, "Disease severity affects recovery outcomes",
                  source="paper:doi_10.5678/severity", confidence=0.90)
        return "prov-dag"

    def test_enriched_edges_contain_claims(self, graph_path: Path) -> None:
        """Edges returned by _get_causal_edges_for_inquiry include matched claims."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        slug = self._build_dag_with_claims(graph_path)
        edges = _get_causal_edges_for_inquiry(graph_path, slug)
        # Find the drug->recovery edge
        drug_recovery = [e for e in edges if "drug" in e["subject"] and "recovery" in e["object"]]
        assert len(drug_recovery) == 1
        edge = drug_recovery[0]
        assert "claims" in edge
        assert len(edge["claims"]) >= 1
        claim = edge["claims"][0]
        assert "text" in claim
        assert "confidence" in claim
        assert "source" in claim

    def test_enriched_edges_contain_observability(self, graph_path: Path) -> None:
        """Edges include observability metadata for both endpoints."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        slug = self._build_dag_with_claims(graph_path)
        edges = _get_causal_edges_for_inquiry(graph_path, slug)
        drug_recovery = [e for e in edges if "drug" in e["subject"] and "recovery" in e["object"]]
        edge = drug_recovery[0]
        assert "subject_observability" in edge
        assert "object_observability" in edge

    def test_edges_without_claims_have_empty_list(self, graph_path: Path) -> None:
        """Edges with no matching claims still have a 'claims' key with empty list."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        add_concept(graph_path, "A", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "B", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "no-claims", "No Claims", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-claims", "concept/a", "BoundaryIn")
        set_boundary_role(graph_path, "no-claims", "concept/b", "BoundaryOut")
        set_treatment_outcome(graph_path, "no-claims", treatment="concept/a", outcome="concept/b")
        add_edge(graph_path, "concept/a", "scic:causes", "concept/b", graph_layer="graph/causal")
        edges = _get_causal_edges_for_inquiry(graph_path, "no-claims")
        assert len(edges) == 1
        assert edges[0]["claims"] == []

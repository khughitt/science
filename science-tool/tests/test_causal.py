"""Tests for causal inquiry type system."""

from pathlib import Path

import pytest

try:
    import pgmpy  # noqa: F401

    HAS_PGMPY = True
except ImportError:
    HAS_PGMPY = False

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    VALID_INQUIRY_TYPES,
    add_concept,
    add_edge,
    add_falsification,
    add_hypothesis,
    add_inquiry,
    add_proposition,
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


class TestInquiryTypeDisplay:
    def test_list_inquiries_includes_type(self, graph_path: Path) -> None:
        """list_inquiries() returns inquiry_type in each dict."""
        from science_tool.graph.store import list_inquiries

        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "causal-1", "Causal", "hypothesis:h1", inquiry_type="causal")
        add_inquiry(graph_path, "general-1", "General", "hypothesis:h1")
        rows = list_inquiries(graph_path)
        causal_row = next(r for r in rows if r["slug"] == "causal_1")
        general_row = next(r for r in rows if r["slug"] == "general_1")
        assert causal_row["inquiry_type"] == "causal"
        assert general_row["inquiry_type"] == "general"


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
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/study",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery"],
        )
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
        add_concept(
            graph_path,
            "Hidden",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "latent")],
        )
        add_concept(
            graph_path,
            "Outcome",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "observed")],
        )
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
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/study",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery"],
        )
        script = export_chirho_script(graph_path, "prov-chirho")
        assert "confidence: 0.85" in script
        assert "doi_10.1234/study" in script

    def test_export_chirho_includes_bridge_comments(self, graph_path: Path) -> None:
        """ChiRho export comments include cross-hypothesis bridge metadata when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Hypothesis 1", source="paper:doi_h1")
        add_hypothesis(graph_path, "h2", "Hypothesis 2", source="paper:doi_h2")
        add_inquiry(graph_path, "bridge-chirho", "Bridge ChiRho", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "bridge-chirho", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "bridge-chirho", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "bridge-chirho", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/bridge",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_bridge_chirho",
            bridge_between_refs=["hypothesis:h1", "hypothesis:h2"],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_bridge_chirho"],
        )

        script = export_chirho_script(graph_path, "bridge-chirho")

        assert "bridge_between: 2" in script
        assert "bridges: hypothesis/h1, hypothesis/h2" in script

    def test_export_chirho_preserves_parent_specific_claims(self, graph_path: Path) -> None:
        """Each incoming causal edge keeps its own attached claim provenance."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "multi-parent", "Multi Parent", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "multi-parent", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "multi-parent", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "multi-parent", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "multi-parent", treatment="concept/x", outcome="concept/y")
        add_proposition(
            graph_path,
            text="X causes Y",
            source="article:doi_x",
            confidence=0.8,
            subject="concept/x",
            predicate="scic:causes",
            obj="concept/y",
            proposition_id="x_causes_y",
        )
        add_proposition(
            graph_path,
            text="Z causes Y",
            source="article:doi_z",
            confidence=0.9,
            subject="concept/z",
            predicate="scic:causes",
            obj="concept/y",
            proposition_id="z_causes_y",
        )
        add_edge(
            graph_path,
            "concept/x",
            "scic:causes",
            "concept/y",
            graph_layer="graph/causal",
            claim_refs=["proposition:x_causes_y"],
        )
        add_edge(
            graph_path,
            "concept/z",
            "scic:causes",
            "concept/y",
            graph_layer="graph/causal",
            claim_refs=["proposition:z_causes_y"],
        )

        script = export_chirho_script(graph_path, "multi-parent")
        assert "doi_x" in script
        assert "doi_z" in script

    def test_export_chirho_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "# Revision:" in script

    def test_export_chirho_todo_latent_variables(self, graph_path: Path) -> None:
        """Export TODO section flags latent variables."""
        add_concept(
            graph_path,
            "Hidden",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "latent")],
        )
        add_concept(
            graph_path,
            "Visible",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "observed")],
        )
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
        add_concept(
            graph_path,
            "Drug",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "observed")],
        )
        add_concept(
            graph_path,
            "Recovery",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "observed")],
        )
        add_concept(
            graph_path,
            "Severity",
            concept_type="sci:Variable",
            ontology_id=None,
            properties=[("sci:observability", "latent")],
        )
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "prov-dag", "Provenance DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-dag", "concept/recovery", "BoundaryOut")
        set_boundary_role(graph_path, "prov-dag", "concept/severity", "BoundaryIn")
        set_treatment_outcome(graph_path, "prov-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery",
        )
        add_proposition(
            graph_path,
            text="Disease severity affects recovery outcomes",
            source="article:doi_10.5678/severity",
            confidence=0.90,
            subject="concept/severity",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="severity_causes_recovery",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery"],
        )
        add_edge(
            graph_path,
            "concept/severity",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:severity_causes_recovery"],
        )
        add_edge(graph_path, "concept/severity", "scic:causes", "concept/drug", graph_layer="graph/causal")
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
        assert "sources" in claim

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

    def test_enriched_edges_include_phase1_claim_metadata(self, graph_path: Path) -> None:
        """Claim bundles expose compositional, heterogeneity, and evidence-line metadata."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "meta-dag", "Metadata DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "meta-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "meta-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "meta-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery",
            compositional_status="clr_attenuated",
            compositional_method="CLR",
            compositional_note="beta attenuates after CLR normalization",
            platform_pattern="MMRF-dominant",
            dataset_effects={"MMRF": 0.7, "GSE24080": 0.07},
            evidence_lines=[
                {"source": "Johnson 2024 ChIP", "kind": "external_biochem", "datasets": []},
                {"source": "t133", "kind": "internal_correlation", "datasets": ["MMRF"]},
                {"source": "t135", "kind": "internal_bayesian_edge", "datasets": ["MMRF", "GSE24080"]},
            ],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "meta-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert claim["compositional_status"] == "clr_attenuated"
        assert claim["compositional_method"] == "CLR"
        assert claim["platform_pattern"] == "MMRF-dominant"
        assert claim["dataset_effects"] == {"MMRF": 0.7, "GSE24080": 0.07}
        assert len(claim["evidence_lines"]) == 3
        assert claim["evidence_lines"][2]["datasets"] == ["MMRF", "GSE24080"]

    def test_enriched_edges_include_explicit_evidence_semantics(self, graph_path: Path) -> None:
        """Claim bundles expose explicit statistical/mechanistic semantics when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "semantics-dag", "Semantics DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "semantics-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "semantics-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "semantics-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causal_semantics",
            statistical_support="replicated",
            mechanistic_support="direct",
            replication_scope="cross_dataset",
            claim_status="active",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causal_semantics"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "semantics-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert claim["statistical_support"] == "replicated"
        assert claim["mechanistic_support"] == "direct"
        assert claim["replication_scope"] == "cross_dataset"
        assert claim["claim_status"] == "active"

    def test_enriched_edges_include_pre_registration_links(self, graph_path: Path) -> None:
        """Claim bundles expose linked pre-registration refs when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "prereg-dag", "Pre-reg DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prereg-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prereg-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prereg-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_preregistered",
            pre_registration_refs=[
                "pre-registration:edge-ribosome-e2f1",
                "pre-registration:edge-mtor-ribosome",
            ],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_preregistered"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "prereg-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert sorted(claim["pre_registrations"]) == [
            "pre-registration/edge-mtor-ribosome",
            "pre-registration/edge-ribosome-e2f1",
        ]

    def test_enriched_edges_include_interaction_terms(self, graph_path: Path) -> None:
        """Claim bundles expose interaction/effect-modification terms when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "KRAS", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "interaction-dag", "Interaction DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "interaction-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "interaction-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "interaction-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_interaction_claim",
            interaction_terms=[
                {
                    "modifier": "concept/kras",
                    "effect": "amplifies",
                    "note": "stronger slope in KRAS-mutant cases",
                }
            ],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_interaction_claim"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "interaction-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert len(claim["interaction_terms"]) == 1
        interaction_term = claim["interaction_terms"][0]
        assert interaction_term["modifier"] == "concept/kras"
        assert interaction_term["effect"] == "amplifies"

    def test_enriched_edges_include_cross_hypothesis_bridge_metadata(self, graph_path: Path) -> None:
        """Claim bundles expose cross-hypothesis bridge metadata when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Hypothesis 1", source="paper:doi_h1")
        add_hypothesis(graph_path, "h2", "Hypothesis 2", source="paper:doi_h2")
        add_inquiry(graph_path, "bridge-dag", "Bridge DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "bridge-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "bridge-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "bridge-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_bridge_claim",
            bridge_between_refs=["hypothesis:h1", "hypothesis:h2"],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_bridge_claim"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "bridge-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert claim["bridge_between"] == ["hypothesis/h1", "hypothesis/h2"]

    def test_export_pgmpy_includes_phase1_claim_metadata_comments(self, graph_path: Path) -> None:
        """pgmpy export comments include the richer claim metadata when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "meta-export", "Metadata Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "meta-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "meta-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "meta-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery_export",
            compositional_status="clr_attenuated",
            compositional_method="CLR",
            platform_pattern="MMRF-dominant",
            dataset_effects={"MMRF": 0.7, "GSE24080": 0.07},
            evidence_lines=[
                {"source": "t133", "kind": "internal_correlation", "datasets": ["MMRF"]},
            ],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery_export"],
        )

        script = export_pgmpy_script(graph_path, "meta-export")

        assert "compositional: clr_attenuated (CLR)" in script
        assert "platform: MMRF-dominant" in script
        assert "dataset_effects: MMRF=0.70, GSE24080=0.07" in script
        assert "evidence_lines: 1" in script

    def test_export_pgmpy_includes_explicit_evidence_semantics_comments(self, graph_path: Path) -> None:
        """pgmpy export comments include explicit evidence semantics when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "semantics-export", "Semantics Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "semantics-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "semantics-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "semantics-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causal_semantics_export",
            statistical_support="replicated",
            mechanistic_support="direct",
            replication_scope="cross_dataset",
            claim_status="active",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causal_semantics_export"],
        )

        script = export_pgmpy_script(graph_path, "semantics-export")

        assert "statistical_support: replicated" in script
        assert "mechanistic_support: direct" in script
        assert "replication_scope: cross_dataset" in script
        assert "claim_status: active" in script

    def test_export_pgmpy_includes_pre_registration_comments(self, graph_path: Path) -> None:
        """pgmpy export comments include linked pre-registration refs when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "prereg-export", "Pre-reg Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prereg-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prereg-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prereg-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_preregistered_export",
            pre_registration_refs=["pre-registration:edge-ribosome-e2f1"],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_preregistered_export"],
        )

        script = export_pgmpy_script(graph_path, "prereg-export")

        assert "pre_registrations: 1" in script
        assert "pre-registration/edge-ribosome-e2f1" in script

    def test_export_pgmpy_includes_interaction_comments(self, graph_path: Path) -> None:
        """pgmpy export comments include interaction/effect-modification terms when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "KRAS", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "interaction-export", "Interaction Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "interaction-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "interaction-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "interaction-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_interaction_export",
            interaction_terms=[
                {
                    "modifier": "concept/kras",
                    "effect": "amplifies",
                    "note": "stronger slope in KRAS-mutant cases",
                }
            ],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_interaction_export"],
        )

        script = export_pgmpy_script(graph_path, "interaction-export")

        assert "interaction_terms: 1" in script
        assert "modified_by: concept/kras(amplifies)" in script

    def test_export_pgmpy_includes_bridge_comments(self, graph_path: Path) -> None:
        """pgmpy export comments include cross-hypothesis bridge metadata when present."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Hypothesis 1", source="paper:doi_h1")
        add_hypothesis(graph_path, "h2", "Hypothesis 2", source="paper:doi_h2")
        add_inquiry(graph_path, "bridge-export", "Bridge Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "bridge-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "bridge-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "bridge-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_bridge_export",
            bridge_between_refs=["hypothesis:h1", "hypothesis:h2"],
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_bridge_export"],
        )

        script = export_pgmpy_script(graph_path, "bridge-export")

        assert "bridge_between: 2" in script
        assert "bridges: hypothesis/h1, hypothesis/h2" in script

    def test_enriched_edges_include_linked_falsifications(self, graph_path: Path) -> None:
        """Claim bundles include linked falsification records when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "fals-dag", "Falsification DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "fals-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "fals-dag", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "fals-dag", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery_falsified",
        )
        add_falsification(
            graph_path,
            predicted="Drug treatment improves recovery time",
            source_of_prediction="topic:drug-mechanism",
            observed="Randomized follow-up showed no improvement",
            decision="Reject mechanistic interpretation",
            proposition_ref="proposition:drug_causes_recovery_falsified",
            falsification_id="drug-recovery-null",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery_falsified"],
        )

        edges = _get_causal_edges_for_inquiry(graph_path, "fals-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert len(claim["falsifications"]) == 1
        falsification = claim["falsifications"][0]
        assert falsification["predicted"] == "Drug treatment improves recovery time"
        assert falsification["decision"] == "Reject mechanistic interpretation"

    def test_export_pgmpy_includes_falsification_comments(self, graph_path: Path) -> None:
        """pgmpy export comments summarize linked falsifications."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "fals-export", "Falsification Export", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "fals-export", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "fals-export", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "fals-export", treatment="concept/drug", outcome="concept/recovery")
        add_proposition(
            graph_path,
            text="Drug treatment improves recovery time",
            source="article:doi_10.1234/drug_recovery",
            confidence=0.85,
            subject="concept/drug",
            predicate="scic:causes",
            obj="concept/recovery",
            proposition_id="drug_causes_recovery_falsified_export",
        )
        add_falsification(
            graph_path,
            predicted="Drug treatment improves recovery time",
            source_of_prediction="topic:drug-mechanism",
            observed="Randomized follow-up showed no improvement",
            decision="Reject mechanistic interpretation",
            proposition_ref="proposition:drug_causes_recovery_falsified_export",
            falsification_id="drug-recovery-null-export",
        )
        add_edge(
            graph_path,
            "concept/drug",
            "scic:causes",
            "concept/recovery",
            graph_layer="graph/causal",
            claim_refs=["proposition:drug_causes_recovery_falsified_export"],
        )

        script = export_pgmpy_script(graph_path, "fals-export")

        assert "falsifications: 1" in script
        assert "latest_decision: Reject mechanistic interpretation" in script


class TestConfoundersDeclared:
    def test_confounder_declared_passes(self, graph_path: Path) -> None:
        """When a common cause has scic:confounds declared, check passes."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "conf-ok", "Conf OK", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "conf-ok", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "conf-ok", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "conf-ok", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "conf-ok", treatment="concept/x", outcome="concept/y")
        # Z causes both X and Y (common cause = confounder)
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        # Declare the confounding
        add_edge(graph_path, "concept/z", "scic:confounds", "concept/x", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "conf-ok")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_undeclared_confounder_warns(self, graph_path: Path) -> None:
        """When a common cause exists but no scic:confounds edge, check warns."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "conf-warn", "Conf Warn", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "conf-warn", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "conf-warn", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "conf-warn", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "conf-warn", treatment="concept/x", outcome="concept/y")
        # Z causes both X and Y but no confounds edge declared
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "conf-warn")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "warn"

    def test_no_common_causes_passes(self, graph_path: Path) -> None:
        """When there are no common causes, check passes."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "no-conf", "No Conf", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-conf", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "no-conf", "concept/y", "BoundaryOut")
        set_treatment_outcome(graph_path, "no-conf", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "no-conf")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_general_inquiry_skips_confounder_check(self, graph_path: Path) -> None:
        """General inquiries don't get confounders_declared check."""
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "confounders_declared" not in check_names


class TestIdentifiabilityCheck:
    def _build_identifiable_dag(self, graph_path: Path) -> str:
        """Build a DAG where X->Y is identifiable by adjusting for Z.
        Z -> X -> Y, Z -> Y (Z is a confounder, adjusting for Z identifies X->Y).
        """
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "ident-dag", "Identifiable", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "ident-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "ident-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "ident-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "ident-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "ident-dag"

    def test_identifiability_check_present(self, graph_path: Path) -> None:
        """Causal inquiry validation includes identifiability check."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        check_names = [r["check"] for r in results]
        assert "identifiability" in check_names

    def test_adjustment_sets_check_present(self, graph_path: Path) -> None:
        """Causal inquiry validation includes adjustment_sets check."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        check_names = [r["check"] for r in results]
        assert "adjustment_sets" in check_names

    @pytest.mark.skipif(not HAS_PGMPY, reason="pgmpy not installed")
    def test_identifiable_dag_passes(self, graph_path: Path) -> None:
        """With pgmpy installed, identifiable DAG passes identifiability check."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        ident_check = next(r for r in results if r["check"] == "identifiability")
        assert ident_check["status"] == "pass"

    @pytest.mark.skipif(not HAS_PGMPY, reason="pgmpy not installed")
    def test_adjustment_sets_reported(self, graph_path: Path) -> None:
        """With pgmpy, adjustment sets are reported as info."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        adj_check = next(r for r in results if r["check"] == "adjustment_sets")
        assert adj_check["status"] == "info"
        assert "z" in adj_check["message"].lower()

    @pytest.mark.skipif(HAS_PGMPY, reason="pgmpy IS installed")
    def test_skip_when_pgmpy_not_installed(self, graph_path: Path) -> None:
        """Without pgmpy, checks have skip status."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        ident_check = next(r for r in results if r["check"] == "identifiability")
        assert ident_check["status"] == "skip"

    def test_identifiability_without_treatment_outcome_skips(self, graph_path: Path) -> None:
        """Without treatment/outcome set, identifiability check is skipped."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "no-est", "No Estimand", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-est", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "no-est", "concept/y", "BoundaryOut")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "no-est")
        ident_check = next((r for r in results if r["check"] == "identifiability"), None)
        assert ident_check is not None
        assert ident_check["status"] == "skip"

    def test_general_inquiry_skips_identifiability(self, graph_path: Path) -> None:
        """General inquiries don't get identifiability or adjustment_sets checks."""
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "identifiability" not in check_names
        assert "adjustment_sets" not in check_names

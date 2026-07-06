"""Tests for causal inquiry type system."""

import importlib.util
from pathlib import Path
from typing import TypedDict, cast

import pytest
from conftest import build_entity_graph, build_inquiry_graph

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    VALID_INQUIRY_TYPES,
    add_falsification,
    get_inquiry,
    validate_inquiry,
)

HAS_PGMPY = importlib.util.find_spec("pgmpy") is not None


def _build_compiled_inquiry_graph(graph_path: Path, slug: str, **inquiry: object) -> None:
    """Compile one inquiry into ``graph_path`` from source.

    Thin wrapper over the shared ``build_inquiry_graph`` conftest helper with
    ``normalize_slug=True`` — the causal tests use hyphenated slugs and rely on the
    retired ``add_inquiry`` mutator's ``_slug`` normalization so the readers
    (``get_inquiry`` / ``validate_inquiry``) resolve the same inquiry URI.
    """
    build_inquiry_graph(graph_path, slug=slug, normalize_slug=True, **inquiry)  # type: ignore[arg-type]


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class FalsificationView(TypedDict):
    predicted: str
    decision: str


def _project_root_for_graph(graph_path: Path) -> Path:
    return graph_path.parent.parent


def _entity(kind: str, entity_id: str, title: str, **frontmatter: object) -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {"title": title, "status": "active", **frontmatter},
        "body": f"{title}\n",
    }


def _concept(entity_id: str, title: str | None = None) -> dict:
    return _entity("concept", entity_id, title or entity_id.replace("-", " ").title())


def _hypothesis(entity_id: str, title: str = "Test hypothesis") -> dict:
    return _entity("hypothesis", entity_id, title, source_refs=[])


def _proposition(
    entity_id: str,
    title: str,
    *,
    confidence: float | None = None,
    source_refs: list[str] | None = None,
) -> dict:
    frontmatter: dict[str, object] = {"source_refs": source_refs or []}
    if confidence is not None:
        frontmatter["confidence"] = confidence
    return _entity("proposition", entity_id, title, **frontmatter)


def _causal_relation(subject: str, predicate: str, obj: str) -> dict:
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "graph_layer": "graph/causal",
    }


def _author_entities(
    graph_path: Path,
    entities: list[dict],
    relations: list[dict] | None = None,
) -> None:
    build_entity_graph(_project_root_for_graph(graph_path), entities, relations)


class TestInquiryType:
    def test_causal_profile_reports_causal_type(self, graph_path: Path) -> None:
        """A causal inquiry is reported as inquiry_type 'causal' by get_inquiry."""
        _author_entities(graph_path, [_concept("x"), _concept("y"), _hypothesis("h01")])
        _build_compiled_inquiry_graph(
            graph_path,
            slug="causal-test",
            profile="causal",
            treatment="concept:x",
            outcome="concept:y",
        )
        result = get_inquiry(graph_path, "causal-test")
        assert result["inquiry_type"] == "causal"

    def test_investigation_profile_reports_general_type(self, graph_path: Path) -> None:
        """An investigation inquiry is reported as inquiry_type 'general'."""
        _author_entities(graph_path, [_hypothesis("h01")])
        _build_compiled_inquiry_graph(graph_path, slug="general-test", profile="investigation")
        result = get_inquiry(graph_path, "general-test")
        assert result["inquiry_type"] == "general"

    def test_invalid_inquiry_profile_rejected(self) -> None:
        """An unknown inquiry profile fails early at model parse (was the
        add_inquiry 'Invalid inquiry type' guard)."""
        from pydantic import ValidationError
        from science_model.patch_definition import InquiryProfile

        with pytest.raises(ValidationError):
            InquiryProfile(profile="randomized")  # type: ignore[arg-type]

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

        _author_entities(graph_path, [_concept("x"), _concept("y"), _hypothesis("h01")])
        _build_compiled_inquiry_graph(
            graph_path, slug="causal-1", profile="causal", treatment="concept:x", outcome="concept:y"
        )
        _build_compiled_inquiry_graph(graph_path, slug="general-1", profile="investigation")
        rows = list_inquiries(graph_path)
        causal_row = next(r for r in rows if r["slug"] == "causal_1")
        general_row = next(r for r in rows if r["slug"] == "general_1")
        assert causal_row["inquiry_type"] == "causal"
        assert general_row["inquiry_type"] == "general"


class TestTreatmentOutcome:
    def test_set_treatment_outcome(self, graph_path: Path) -> None:
        """Setting treatment and outcome stores predicates in inquiry graph."""
        _author_entities(graph_path, [_concept("drug", "Drug"), _concept("recovery", "Recovery"), _hypothesis("h01")])
        _build_compiled_inquiry_graph(
            graph_path,
            slug="drug-effect",
            profile="causal",
            treatment="concept:drug",
            outcome="concept:recovery",
        )
        info = get_inquiry(graph_path, "drug-effect")
        assert info["treatment"] == str(PROJECT_NS["concept/drug"])
        assert info["outcome"] == str(PROJECT_NS["concept/recovery"])

    def test_treatment_on_investigation_rejected(self) -> None:
        """An investigation profile must not carry an estimand — rejected at model
        parse (was the set_treatment_outcome 'only supported for causal' guard)."""
        from pydantic import ValidationError
        from science_model.patch_definition import InquiryProfile

        with pytest.raises(ValidationError):
            InquiryProfile(profile="investigation", treatment="concept:x", outcome="concept:y")


class TestCausalValidation:
    def _setup_causal_inquiry(self, graph_path: Path, relations: list[dict] | None = None) -> str:
        """Helper: create a causal inquiry with variables and edges."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("test_hyp")],
            relations=relations,
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="causal-test",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
        return "causal-test"

    def test_acyclic_causal_edges_pass(self, graph_path: Path) -> None:
        """Acyclic causal edges pass validation."""
        slug = self._setup_causal_inquiry(
            graph_path,
            relations=[
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
            ],
        )
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "pass"

    def test_cyclic_causal_edges_fail(self, graph_path: Path) -> None:
        """Cyclic causal edges fail validation."""
        slug = self._setup_causal_inquiry(
            graph_path,
            relations=[
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:y", "scic:causes", "concept:x"),
            ],
        )
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "fail"

    def test_general_inquiry_skips_causal_checks(self, graph_path: Path) -> None:
        """General inquiries don't get causal validation checks."""
        _author_entities(graph_path, [_hypothesis("test_hyp")])
        _build_compiled_inquiry_graph(graph_path, slug="gen", profile="investigation")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "causal_acyclicity" not in check_names


class TestExportPgmpy:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Build a simple X->Y<-Z causal inquiry."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("h1")],
            relations=[
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="xy-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
        return "xy-dag"

    def test_export_pgmpy_generates_valid_script(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "from pgmpy.models import DiscreteBayesianNetwork" in script
        assert "DiscreteBayesianNetwork(" in script
        assert "CausalInference" in script

    def test_export_pgmpy_uses_non_deprecated_class(self, graph_path: Path) -> None:
        """pgmpy>=1.0 renamed BayesianNetwork -> DiscreteBayesianNetwork."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "from pgmpy.models import BayesianNetwork\n" not in script
        assert "= BayesianNetwork(" not in script

    def test_export_pgmpy_includes_provenance_comments(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "# Generated from inquiry:" in script

    def test_export_pgmpy_rejects_non_causal(self, graph_path: Path) -> None:
        _author_entities(graph_path, [_hypothesis("h1")])
        _build_compiled_inquiry_graph(graph_path, slug="gen", profile="investigation")
        with pytest.raises(ValueError, match="only supported for causal"):
            export_pgmpy_script(graph_path, "gen")

    def test_export_pgmpy_contains_edge_tuples(self, graph_path: Path) -> None:
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        # Should contain tuple pairs for edges
        assert '("x", "y")' in script or '("x","y")' in script

    def test_export_pgmpy_edge_level_provenance(self, graph_path: Path) -> None:
        """Export includes claim text, confidence, and source as comments on edges."""
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _hypothesis("h1", "Test"),
                _proposition(
                    "drug_causes_recovery",
                    "Drug treatment improves recovery time",
                    confidence=0.85,
                ),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="prov-pgmpy",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery"],
                }
            ],
        )
        script = export_pgmpy_script(graph_path, "prov-pgmpy")
        assert 'claim: "proposition/drug_causes_recovery"' in script
        assert "confidence: 0.85" in script
        assert "sources:" in script

    def test_export_pgmpy_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash when available."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "# Revision:" in script

    def test_export_pgmpy_includes_confounds_as_directed_edges(self, graph_path: Path) -> None:
        """A confounder declared only via scic:confounds must appear as directed
        edges so the exported model exposes the backdoor path instead of falsely
        reporting an empty adjustment set."""
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _concept("hidden", "Hidden"),
                _hypothesis("h1"),
            ],
            relations=[
                _causal_relation("concept:drug", "scic:causes", "concept:recovery"),
                _causal_relation("concept:hidden", "scic:confounds", "concept:drug"),
                _causal_relation("concept:hidden", "scic:confounds", "concept:recovery"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="conf-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
        )

        script = export_pgmpy_script(graph_path, "conf-dag")

        # Confounder edges are now part of the directed model structure.
        assert '("hidden", "drug")' in script
        assert '("hidden", "recovery")' in script

    # Source-authored concepts do not emit the retired mutator observability payload;
    # variable-observability TODO/comment coverage was intentionally dropped in Phase 3a.

    def test_export_pgmpy_reads_compiled_patch_inquiry_edges(self, graph_path: Path) -> None:
        """Patch-authored inquiries compile to their own named graph and must export causal edges."""
        _build_compiled_inquiry_graph(
            graph_path,
            slug="patch-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
            ],
            treatment="concept:x",
            outcome="concept:y",
            flow_edges=[
                {"subject": "concept:x", "predicate": "causes", "object": "concept:y"},
            ],
        )

        script = export_pgmpy_script(graph_path, "patch-dag")

        assert '("x", "y")' in script


class TestExportChirho:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Build a simple X->Y<-Z causal inquiry."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("h1")],
            relations=[
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="xy-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
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
        _author_entities(graph_path, [_hypothesis("h1")])
        _build_compiled_inquiry_graph(graph_path, slug="gen", profile="investigation")
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
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _hypothesis("h1", "Test"),
                _proposition(
                    "drug_causes_recovery",
                    "Drug treatment improves recovery time",
                    confidence=0.85,
                ),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="prov-chirho",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery"],
                }
            ],
        )
        script = export_chirho_script(graph_path, "prov-chirho")
        assert "confidence: 0.85" in script
        assert "sources:" in script

    def test_export_chirho_preserves_parent_specific_claims(self, graph_path: Path) -> None:
        """Each incoming causal edge keeps its own attached claim provenance."""
        _author_entities(
            graph_path,
            [
                _concept("x", "X"),
                _concept("y", "Y"),
                _concept("z", "Z"),
                _hypothesis("h1", "Test"),
                _proposition("x_causes_y", "X causes Y", confidence=0.8),
                _proposition("z_causes_y", "Z causes Y", confidence=0.9),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="multi-parent",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
            flow_edges=[
                {
                    "subject": "concept:x",
                    "predicate": "causes",
                    "object": "concept:y",
                    "claim_refs": ["proposition:x_causes_y"],
                },
                {
                    "subject": "concept:z",
                    "predicate": "causes",
                    "object": "concept:y",
                    "claim_refs": ["proposition:z_causes_y"],
                },
            ],
        )

        script = export_chirho_script(graph_path, "multi-parent")
        assert "x: confidence: 0.8" in script
        assert "z: confidence: 0.9" in script

    def test_export_chirho_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "# Revision:" in script

    # Source-authored concepts do not emit the retired mutator observability payload;
    # variable-observability TODO/comment coverage was intentionally dropped in Phase 3a.


class TestEdgeProvenance:
    """Tests for source-authored edge provenance in causal exports.

    Phase 3a intentionally drops mutator-only edge-claim payload assertions
    (observability, compositional/platform/evidence-line semantics,
    pre-registrations, interaction terms, and bridge metadata).
    """

    def _build_dag_with_claims(self, graph_path: Path) -> str:
        """Build a DAG with claims supporting the causal edges."""
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _concept("severity", "Severity"),
                _hypothesis("h1"),
                _proposition("drug_causes_recovery", "Drug treatment improves recovery time", confidence=0.85),
                _proposition("severity_causes_recovery", "Disease severity affects recovery outcomes", confidence=0.90),
            ],
            relations=[
                _causal_relation("concept:severity", "scic:causes", "concept:drug"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="prov-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
                {"ref": "concept:severity", "role": "BoundaryIn"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery"],
                },
                {
                    "subject": "concept:severity",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:severity_causes_recovery"],
                },
            ],
        )
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
        assert claim["confidence"] == 0.85
        assert claim["sources"]
        assert claim["support_count"] == 0
        assert claim["dispute_count"] == 0

    def test_edges_without_claims_have_empty_list(self, graph_path: Path) -> None:
        """Edges with no matching claims still have a 'claims' key with empty list."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        _author_entities(
            graph_path,
            [_concept("a", "A"), _concept("b", "B"), _hypothesis("h1")],
            relations=[_causal_relation("concept:a", "scic:causes", "concept:b")],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="no-claims",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:a", "role": "BoundaryIn"},
                {"ref": "concept:b", "role": "BoundaryOut"},
            ],
            treatment="concept:a",
            outcome="concept:b",
        )
        edges = _get_causal_edges_for_inquiry(graph_path, "no-claims")
        assert len(edges) == 1
        assert edges[0]["claims"] == []

    def test_enriched_edges_include_linked_falsifications(self, graph_path: Path) -> None:
        """Claim bundles include linked falsification records when present."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry

        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _hypothesis("h1"),
                _proposition(
                    "drug_causes_recovery_falsified",
                    "Drug treatment improves recovery time",
                    confidence=0.85,
                ),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="fals-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery_falsified"],
                }
            ],
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

        edges = _get_causal_edges_for_inquiry(graph_path, "fals-dag")
        edge = next(e for e in edges if "drug" in e["subject"] and "recovery" in e["object"])
        claim = edge["claims"][0]

        assert len(claim["falsifications"]) == 1
        falsification = cast(FalsificationView, claim["falsifications"][0])
        assert falsification["predicted"] == "Drug treatment improves recovery time"
        assert falsification["decision"] == "Reject mechanistic interpretation"

    def test_export_pgmpy_includes_falsification_comments(self, graph_path: Path) -> None:
        """pgmpy export comments summarize linked falsifications."""
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _hypothesis("h1"),
                _proposition(
                    "drug_causes_recovery_falsified_export",
                    "Drug treatment improves recovery time",
                    confidence=0.85,
                ),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="fals-export",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery_falsified_export"],
                }
            ],
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

        script = export_pgmpy_script(graph_path, "fals-export")

        assert "falsifications: 1" in script
        assert "latest_decision: Reject mechanistic interpretation" in script


class TestConfoundersDeclared:
    def test_confounder_declared_passes(self, graph_path: Path) -> None:
        """When a common cause has scic:confounds declared, check passes."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("h1", "Test")],
            relations=[
                _causal_relation("concept:z", "scic:causes", "concept:x"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:z", "scic:confounds", "concept:x"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="conf-ok",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
        results = validate_inquiry(graph_path, "conf-ok")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_undeclared_confounder_warns(self, graph_path: Path) -> None:
        """When a common cause exists but no scic:confounds edge, check warns."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("h1", "Test")],
            relations=[
                _causal_relation("concept:z", "scic:causes", "concept:x"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
                _causal_relation("concept:x", "scic:causes", "concept:y"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="conf-warn",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
        results = validate_inquiry(graph_path, "conf-warn")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "warn"

    def test_no_common_causes_passes(self, graph_path: Path) -> None:
        """When there are no common causes, check passes."""
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _hypothesis("h1", "Test")],
            relations=[_causal_relation("concept:x", "scic:causes", "concept:y")],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="no-conf",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
        results = validate_inquiry(graph_path, "no-conf")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_general_inquiry_skips_confounder_check(self, graph_path: Path) -> None:
        """General inquiries don't get confounders_declared check."""
        _author_entities(graph_path, [_hypothesis("h1", "Test")])
        _build_compiled_inquiry_graph(graph_path, slug="gen", profile="investigation")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "confounders_declared" not in check_names


class TestIdentifiabilityCheck:
    def _build_identifiable_dag(self, graph_path: Path) -> str:
        """Build a DAG where X->Y is identifiable by adjusting for Z.
        Z -> X -> Y, Z -> Y (Z is a confounder, adjusting for Z identifies X->Y).
        """
        _author_entities(
            graph_path,
            [_concept("x", "X"), _concept("y", "Y"), _concept("z", "Z"), _hypothesis("h1", "Test")],
            relations=[
                _causal_relation("concept:x", "scic:causes", "concept:y"),
                _causal_relation("concept:z", "scic:causes", "concept:x"),
                _causal_relation("concept:z", "scic:causes", "concept:y"),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="ident-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
                {"ref": "concept:z", "role": "BoundaryIn"},
            ],
            treatment="concept:x",
            outcome="concept:y",
        )
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

    # A causal inquiry without a treatment/outcome estimand is not expressible
    # from source (the InquiryProfile model requires both), so the identifiability
    # check's "skip when no estimand" branch is unreachable for source-built causal
    # inquiries. The estimand-required invariant is proven at the model layer
    # (TestInquiryType / TestTreatmentOutcome::test_treatment_on_investigation_rejected);
    # general inquiries skipping identifiability is covered below.

    def test_general_inquiry_skips_identifiability(self, graph_path: Path) -> None:
        """General inquiries don't get identifiability or adjustment_sets checks."""
        _author_entities(graph_path, [_hypothesis("h1", "Test")])
        _build_compiled_inquiry_graph(graph_path, slug="gen", profile="investigation")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "identifiability" not in check_names
        assert "adjustment_sets" not in check_names

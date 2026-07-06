"""CLI tests for causal DAG commands.

Causal inquiry graphs are produced by the pure compiler (the path that replaced
the retired ``inquiry add-*`` / ``set-estimand`` mutators); these tests build the
inquiry through the ``build_inquiry_graph`` conftest helper and exercise the
reader/export CLI against it. ``scic:causes`` edges that the original tests added
to ``graph/causal`` are still added there via ``graph add edge`` (the export
reader reads them from both the inquiry graph and ``graph/causal``).
"""

from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import build_inquiry_graph
from rdflib import Literal
from rdflib.namespace import PROV, RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.store import (
    CITO_NS,
    INITIAL_GRAPH_TEMPLATE,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    _edge_statement_uri,
    _graph_uri,
    _load_dataset,
    _resolve_term,
    _save_dataset,
    _slug,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


def _edit_graph(graph_path: Path, update) -> None:
    dataset = _load_dataset(graph_path)
    update(dataset)
    _save_dataset(dataset, graph_path)


def _write_concept(graph_path: Path, label: str, concept_type: str | None = None, status: str | None = None) -> None:
    def update(dataset) -> None:
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        concept_uri = PROJECT_NS[f"concept/{_slug(label)}"]
        knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
        knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))
        if concept_type is not None:
            knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
        if status is not None:
            knowledge.add((concept_uri, SCI_NS.projectStatus, Literal(status)))

    _edit_graph(graph_path, update)


def _write_hypothesis(graph_path: Path, slug: str, text: str = "Test hypothesis") -> None:
    def update(dataset) -> None:
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        hypothesis_uri = PROJECT_NS[f"hypothesis/{slug}"]
        knowledge.add((hypothesis_uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((hypothesis_uri, SCHEMA_NS.text, Literal(text)))

    _edit_graph(graph_path, update)


def _write_proposition(
    graph_path: Path,
    slug: str,
    text: str,
    *,
    source: str = "paper:doi_test",
    confidence: float | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    obj: str | None = None,
) -> None:
    def update(dataset) -> None:
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        prop_uri = PROJECT_NS[f"proposition/{slug}"]
        knowledge.add((prop_uri, RDF.type, SCI_NS.Proposition))
        knowledge.add((prop_uri, SCHEMA_NS.text, Literal(text)))
        provenance.add((prop_uri, PROV.wasDerivedFrom, _resolve_term(source)))
        if confidence is not None:
            provenance.add((prop_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))
        if subject is not None and predicate is not None and obj is not None:
            knowledge.add((prop_uri, SCI_NS.propSubject, _resolve_term(subject)))
            knowledge.add((prop_uri, SCI_NS.propPredicate, _resolve_term(predicate)))
            knowledge.add((prop_uri, SCI_NS.propObject, _resolve_term(obj)))

    _edit_graph(graph_path, update)


def _write_evidence_edge(graph_path: Path, source: str, target: str, stance: str) -> None:
    def update(dataset) -> None:
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        predicate_uri = CITO_NS.supports if stance == "supports" else CITO_NS.disputes
        knowledge.add((_resolve_term(source), predicate_uri, _resolve_term(target)))

    _edit_graph(graph_path, update)


def _write_graph_edge(
    graph_path: Path,
    subject: str,
    predicate: str,
    obj: str,
    graph_layer: str,
    claim_refs: list[str] | None = None,
) -> None:
    def update(dataset) -> None:
        layer = dataset.graph(_graph_uri(graph_layer))
        s_uri = _resolve_term(subject)
        p_uri = _resolve_term(predicate)
        o_uri = _resolve_term(obj)
        layer.add((s_uri, p_uri, o_uri))
        if claim_refs:
            statement_uri = _edge_statement_uri(graph_layer, s_uri, p_uri, o_uri)
            layer.add((statement_uri, RDF.type, RDF.Statement))
            layer.add((statement_uri, RDF.subject, s_uri))
            layer.add((statement_uri, RDF.predicate, p_uri))
            layer.add((statement_uri, RDF.object, o_uri))
            for claim_ref in claim_refs:
                layer.add((statement_uri, SCI_NS.backedByClaim, _resolve_term(claim_ref)))

    _edit_graph(graph_path, update)


def _setup_causal_inquiry(graph_path: Path) -> None:
    """Set up the ``testdag`` causal inquiry via the compile path + graph/causal edges."""
    _write_concept(graph_path, "X", concept_type="sci:Variable", status="active")
    _write_concept(graph_path, "Y", concept_type="sci:Variable", status="active")
    _write_concept(graph_path, "Z", concept_type="sci:Variable", status="active")
    _write_hypothesis(graph_path, "test_hyp")
    build_inquiry_graph(
        graph_path,
        slug="testdag",
        title="Test DAG",
        profile="causal",
        focal="hypothesis:test_hyp",
        treatment="concept:x",
        outcome="concept:y",
        boundary_roles=[
            {"ref": "concept:x", "role": "BoundaryIn"},
            {"ref": "concept:y", "role": "BoundaryOut"},
            {"ref": "concept:z", "role": "BoundaryIn"},
        ],
    )
    _write_graph_edge(graph_path, "concept/x", "scic:causes", "concept/y", "graph/causal")
    _write_graph_edge(graph_path, "concept/z", "scic:causes", "concept/y", "graph/causal")


class TestInquiryInitType:
    def test_init_scaffolds_causal_profile(self, runner: CliRunner, tmp_path: Path) -> None:
        """`inquiry init --profile causal` scaffolds a causal patch-definition source."""
        result = runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "dag1",
                "--label",
                "DAG",
                "--target",
                "hypothesis:h1",
                "--profile",
                "causal",
                "--treatment",
                "concept:x",
                "--outcome",
                "concept:y",
                "--project-root",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        text = (tmp_path / "entities" / "patches" / "dag1.md").read_text()
        assert "patch_type: inquiry" in text
        assert "profile: causal" in text


class TestInquiryTypeInOutput:
    def test_show_displays_type(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry show text output includes the inquiry type."""
        p = str(graph_path)
        _write_hypothesis(graph_path, "h1")
        build_inquiry_graph(
            graph_path,
            slug="dag1",
            title="DAG",
            profile="causal",
            focal="hypothesis:h1",
            treatment="concept:x",
            outcome="concept:y",
        )
        result = runner.invoke(main, ["inquiry", "show", "dag1", "--path", p])
        assert result.exit_code == 0
        assert "Type: causal" in result.output

    def test_list_displays_type_column(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry list includes a Type column."""
        p = str(graph_path)
        _write_hypothesis(graph_path, "h1")
        build_inquiry_graph(
            graph_path,
            slug="dag1",
            title="DAG",
            profile="causal",
            focal="hypothesis:h1",
            treatment="concept:x",
            outcome="concept:y",
        )
        result = runner.invoke(main, ["inquiry", "list", "--path", p])
        assert result.exit_code == 0
        assert "causal" in result.output


class TestExportCLI:
    def test_export_pgmpy_includes_inquiry_local_causal_edges(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        _write_concept(graph_path, "X", concept_type="sci:Variable", status="active")
        _write_concept(graph_path, "Y", concept_type="sci:Variable", status="active")
        _write_hypothesis(graph_path, "test_hyp")
        _write_proposition(
            graph_path,
            "x_causes_y",
            "X causes Y",
            source="paper:doi_claim",
            subject="concept:x",
            predicate="scic:causes",
            obj="concept:y",
        )

        # A causal inquiry with an inquiry-local `causes` flow edge (backed by the
        # claim) compiles to an in-graph scic:causes edge with backedByClaim.
        build_inquiry_graph(
            graph_path,
            slug="localdag",
            title="Local DAG",
            profile="causal",
            focal="hypothesis:test_hyp",
            treatment="concept:x",
            outcome="concept:y",
            boundary_roles=[
                {"ref": "concept:x", "role": "BoundaryIn"},
                {"ref": "concept:y", "role": "BoundaryOut"},
            ],
            flow_edges=[
                {
                    "subject": "concept:x",
                    "predicate": "causes",
                    "object": "concept:y",
                    "claim_refs": ["proposition:x_causes_y"],
                }
            ],
        )

        export_result = runner.invoke(main, ["inquiry", "export-pgmpy", "localdag", "--path", p])
        assert export_result.exit_code == 0, export_result.output
        assert '("x", "y")' in export_result.output
        assert 'claim: "X causes Y"' in export_result.output

    def test_export_pgmpy_uses_explicit_claim_attachments(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        _setup_causal_inquiry(graph_path)
        _write_proposition(
            graph_path,
            "x_causes_y",
            "X causes Y",
            source="paper:doi_claim",
            confidence=0.85,
            subject="concept:x",
            predicate="scic:causes",
            obj="concept:y",
        )
        _write_proposition(
            graph_path,
            "support_xy",
            "Independent study supports X causes Y",
            source="paper:doi_support",
            confidence=0.7,
        )
        _write_proposition(
            graph_path,
            "dispute_xy",
            "Counter-evidence disputes X causes Y",
            source="paper:doi_dispute",
            confidence=0.4,
        )
        _write_evidence_edge(graph_path, "proposition/support_xy", "proposition/x_causes_y", "supports")
        _write_evidence_edge(graph_path, "proposition/dispute_xy", "proposition/x_causes_y", "disputes")
        _write_graph_edge(
            graph_path,
            "concept/x",
            "scic:causes",
            "concept/y",
            "graph/causal",
            claim_refs=["proposition:x_causes_y"],
        )

        result = runner.invoke(main, ["inquiry", "export-pgmpy", "testdag", "--path", p])
        assert result.exit_code == 0
        assert 'claim: "X causes Y"' in result.output
        assert "confidence: 0.85" in result.output
        assert "supports: 1" in result.output
        assert "disputes: 1" in result.output
        assert "TODO" in result.output
        assert "Edge z -> y has no attached relation claim" in result.output

    def test_export_pgmpy_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        _setup_causal_inquiry(graph_path)
        out_file = tmp_path / "dag.py"
        result = runner.invoke(
            main, ["inquiry", "export-pgmpy", "testdag", "--output", str(out_file), "--path", str(graph_path)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "BayesianNetwork" in content

    def test_export_chirho_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        _setup_causal_inquiry(graph_path)
        out_file = tmp_path / "model.py"
        result = runner.invoke(
            main, ["inquiry", "export-chirho", "testdag", "--output", str(out_file), "--path", str(graph_path)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "pyro.sample" in content

    def test_export_pgmpy_stdout(self, runner: CliRunner, graph_path: Path) -> None:
        _setup_causal_inquiry(graph_path)
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "testdag", "--path", str(graph_path)])
        assert result.exit_code == 0
        assert "BayesianNetwork" in result.output

    def test_export_non_causal_errors(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        _write_hypothesis(graph_path, "h1")
        runner.invoke(main, ["inquiry", "init", "gen", "--label", "General", "--target", "hypothesis:h1", "--path", p])
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "gen", "--path", p])
        assert result.exit_code != 0

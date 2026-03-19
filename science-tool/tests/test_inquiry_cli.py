"""CLI tests for inquiry subcommands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import URIRef
from rdflib.namespace import RDF

from science_tool.cli import main
from science_tool.graph.store import PROJECT_NS, SCI_NS, _load_dataset


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Create a temp dir with initialized graph + a hypothesis target."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    r = CliRunner()
    result = r.invoke(main, ["graph", "init", "--path", str(gp)])
    assert result.exit_code == 0
    r.invoke(
        main,
        [
            "graph",
            "add",
            "hypothesis",
            "H01",
            "--text",
            "Test hypothesis",
            "--source",
            "paper:doi_test",
            "--path",
            str(gp),
        ],
    )
    return gp


class TestInquiryInit:
    def test_init(self, runner: CliRunner, graph_path: Path) -> None:
        result = runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "sp-geometry",
                "--label",
                "Signal peptide geometry",
                "--target",
                "hypothesis:h01",
                "--path",
                str(graph_path),
            ],
        )
        assert result.exit_code == 0
        assert "inquiry/sp_geometry" in result.output

    def test_init_duplicate_fails(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "dup", "--label", "A", "--target", "hypothesis:h01", "--path", p])
        result = runner.invoke(
            main, ["inquiry", "init", "dup", "--label", "B", "--target", "hypothesis:h01", "--path", p]
        )
        assert result.exit_code != 0


class TestInquiryAddNode:
    def test_add_boundary_in(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "input_data", "--path", p])
        result = runner.invoke(
            main, ["inquiry", "add-node", "test", "concept:input_data", "--role", "BoundaryIn", "--path", p]
        )
        assert result.exit_code == 0


class TestInquiryAddEdge:
    def test_add_edge(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "a", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "b", "--path", p])
        result = runner.invoke(
            main, ["inquiry", "add-edge", "test", "concept:a", "sci:feedsInto", "concept:b", "--path", p]
        )
        assert result.exit_code == 0

    def test_add_edge_with_relation_claim_attaches_claim_to_edge(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "a", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "b", "--path", p])
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "concept:a",
                "sci:feedsInto",
                "concept:b",
                "--id",
                "a_feeds_into_b",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        result = runner.invoke(
            main,
            [
                "inquiry",
                "add-edge",
                "test",
                "concept:a",
                "sci:feedsInto",
                "concept:b",
                "--claim",
                "relation_claim:a_feeds_into_b",
                "--path",
                p,
            ],
        )
        assert result.exit_code == 0

        show_result = runner.invoke(main, ["inquiry", "show", "test", "--format", "json", "--path", p])
        assert show_result.exit_code == 0
        info = json.loads(show_result.output)
        assert info["edges"] == [
            {
                "subject": "http://example.org/project/concept/a",
                "predicate": "http://example.org/science/vocab/feedsInto",
                "object": "http://example.org/project/concept/b",
                "claims": ["http://example.org/project/relation_claim/a_feeds_into_b"],
            }
        ]

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        statement_uri = next(inquiry_graph.subjects(RDF.subject, PROJECT_NS["concept/a"]), None)
        assert statement_uri is not None
        assert (statement_uri, SCI_NS.backedByClaim, PROJECT_NS["relation_claim/a_feeds_into_b"]) in inquiry_graph
        assert (statement_uri, SCI_NS.validatedBy, PROJECT_NS["relation_claim/a_feeds_into_b"]) not in inquiry_graph


class TestInquiryAddNodeInterior:
    def test_add_interior_node(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "middle_step", "--path", p])
        result = runner.invoke(main, ["inquiry", "add-node", "test", "concept:middle_step", "--path", p])
        assert result.exit_code == 0
        assert "interior" in result.output


class TestInquiryAddAssumption:
    def test_add_assumption(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        result = runner.invoke(
            main,
            ["inquiry", "add-assumption", "test", "Mean pooling sufficient", "--source", "paper:doi_test", "--path", p],
        )
        assert result.exit_code == 0
        assert "assumption" in result.output.lower()


class TestInquiryAddTransformation:
    def test_add_transformation(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        result = runner.invoke(
            main, ["inquiry", "add-transformation", "test", "Extract sequences", "--tool", "BioPython", "--path", p]
        )
        assert result.exit_code == 0
        assert "transformation" in result.output.lower()


class TestInquiryList:
    def test_list_empty(self, runner: CliRunner, graph_path: Path) -> None:
        result = runner.invoke(main, ["inquiry", "list", "--path", str(graph_path), "--format", "json"])
        assert result.exit_code == 0

    def test_list_with_inquiries(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "i1", "--label", "First", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["inquiry", "init", "i2", "--label", "Second", "--target", "hypothesis:h01", "--path", p])
        result = runner.invoke(main, ["inquiry", "list", "--path", p, "--format", "json"])
        assert result.exit_code == 0
        assert "First" in result.output
        assert "Second" in result.output


class TestInquiryShow:
    def test_show(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "Test", "--target", "hypothesis:h01", "--path", p])
        result = runner.invoke(main, ["inquiry", "show", "test", "--path", p, "--format", "json"])
        assert result.exit_code == 0
        assert "Test" in result.output


class TestInquirySummary:
    def test_inquiry_summary_reports_claim_backing_and_priority(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "summary-test",
                "--label",
                "Summary Test Inquiry",
                "--target",
                "hypothesis:h01",
                "--path",
                p,
            ],
        )
        runner.invoke(main, ["graph", "add", "concept", "a", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "b", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "c", "--path", p])

        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "concept:a",
                "sci:feedsInto",
                "concept:b",
                "--id",
                "flow_a_b",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "concept:b",
                "sci:feedsInto",
                "concept:c",
                "--id",
                "flow_b_c",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        runner.invoke(
            main,
            [
                "inquiry",
                "add-edge",
                "summary-test",
                "concept:a",
                "sci:feedsInto",
                "concept:b",
                "--claim",
                "relation_claim:flow_a_b",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "inquiry",
                "add-edge",
                "summary-test",
                "concept:b",
                "sci:feedsInto",
                "concept:c",
                "--claim",
                "relation_claim:flow_b_c",
                "--path",
                p,
            ],
        )

        runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
                "Empirical evidence for inquiry-backed claim",
                "--source",
                "paper:doi_test",
                "--evidence-type",
                "empirical_data_evidence",
                "--id",
                "flow_a_b_support",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "claim/flow_a_b_support",
                "cito:supports",
                "relation_claim:flow_a_b",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
                "Literature support for contested inquiry-backed claim",
                "--source",
                "paper:doi_test",
                "--evidence-type",
                "literature_evidence",
                "--id",
                "flow_b_c_support",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "claim/flow_b_c_support",
                "cito:supports",
                "relation_claim:flow_b_c",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
                "Negative result disputing inquiry-backed claim",
                "--source",
                "paper:doi_test",
                "--evidence-type",
                "negative_result",
                "--id",
                "flow_b_c_dispute",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "claim/flow_b_c_dispute",
                "cito:disputes",
                "relation_claim:flow_b_c",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        result = runner.invoke(main, ["graph", "inquiry-summary", "--format", "json", "--path", p])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = payload["rows"][0]
        assert row["inquiry"] == "http://example.org/project/inquiry/summary_test"
        assert row["claim_count"] == "2"
        assert row["backed_claim_count"] == "2"
        assert row["contested_claim_count"] == "1"
        assert row["single_source_claim_count"] == "2"
        assert row["no_empirical_claim_count"] == "1"
        assert float(row["avg_risk_score"]) > 0.0
        assert float(row["priority_score"]) > 0.0

    def test_inquiry_summary_table_headers_are_sensible(self, runner: CliRunner, graph_path: Path) -> None:
        result = runner.invoke(main, ["graph", "inquiry-summary", "--path", str(graph_path)])
        assert result.exit_code == 0
        assert "Graph Inquiry Summary" in result.output
        assert "Inquiry" in result.output


class TestInquiryValidate:
    def test_validate_valid(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["inquiry", "init", "test", "--label", "T", "--target", "hypothesis:h01", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "din", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "dout", "--path", p])
        runner.invoke(main, ["inquiry", "add-node", "test", "concept:din", "--role", "BoundaryIn", "--path", p])
        runner.invoke(main, ["inquiry", "add-node", "test", "concept:dout", "--role", "BoundaryOut", "--path", p])
        runner.invoke(
            main, ["inquiry", "add-edge", "test", "concept:din", "sci:feedsInto", "concept:dout", "--path", p]
        )
        result = runner.invoke(main, ["inquiry", "validate", "test", "--path", p, "--format", "json"])
        assert result.exit_code == 0

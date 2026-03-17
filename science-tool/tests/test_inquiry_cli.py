"""CLI tests for inquiry subcommands."""

import json

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


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

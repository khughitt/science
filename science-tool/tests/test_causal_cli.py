"""CLI tests for causal DAG commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


def _setup_causal_inquiry(runner: CliRunner, graph_path: Path) -> None:
    """Set up a causal inquiry via CLI commands."""
    p = str(graph_path)
    runner.invoke(main, ["graph", "add", "concept", "X", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "concept", "Y", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "concept", "Z", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "hypothesis", "test hyp", "--source", "paper:doi_test", "--path", p])
    runner.invoke(
        main,
        [
            "inquiry",
            "init",
            "test-dag",
            "--label",
            "Test DAG",
            "--target",
            "hypothesis:test_hyp",
            "--type",
            "causal",
            "--path",
            p,
        ],
    )
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/x", "--role", "BoundaryIn", "--path", p])
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/y", "--role", "BoundaryOut", "--path", p])
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/z", "--role", "BoundaryIn", "--path", p])
    runner.invoke(
        main, ["inquiry", "set-estimand", "test-dag", "--treatment", "concept/x", "--outcome", "concept/y", "--path", p]
    )
    runner.invoke(
        main, ["graph", "add", "edge", "concept/x", "scic:causes", "concept/y", "--graph", "graph/causal", "--path", p]
    )
    runner.invoke(
        main, ["graph", "add", "edge", "concept/z", "scic:causes", "concept/y", "--graph", "graph/causal", "--path", p]
    )


class TestInquiryInitType:
    def test_init_with_type_causal(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        result = runner.invoke(
            main,
            ["inquiry", "init", "dag1", "--label", "DAG", "--target", "hypothesis:h1", "--type", "causal", "--path", p],
        )
        assert result.exit_code == 0
        assert "Created inquiry" in result.output


class TestInquiryTypeInOutput:
    def test_show_displays_type(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry show text output includes the inquiry type."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(
            main,
            ["inquiry", "init", "dag1", "--label", "DAG", "--target", "hypothesis:h1", "--type", "causal", "--path", p],
        )
        result = runner.invoke(main, ["inquiry", "show", "dag1", "--path", p])
        assert result.exit_code == 0
        assert "Type: causal" in result.output

    def test_list_displays_type_column(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry list includes a Type column."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(
            main,
            ["inquiry", "init", "dag1", "--label", "DAG", "--target", "hypothesis:h1", "--type", "causal", "--path", p],
        )
        result = runner.invoke(main, ["inquiry", "list", "--path", p])
        assert result.exit_code == 0
        assert "causal" in result.output


class TestExportCLI:
    def test_export_pgmpy_includes_inquiry_local_causal_edges(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(
            main, ["graph", "add", "concept", "X", "--type", "sci:Variable", "--status", "active", "--path", p]
        )
        runner.invoke(
            main, ["graph", "add", "concept", "Y", "--type", "sci:Variable", "--status", "active", "--path", p]
        )
        runner.invoke(main, ["graph", "add", "hypothesis", "test hyp", "--source", "paper:doi_test", "--path", p])
        runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "local-dag",
                "--label",
                "Local DAG",
                "--target",
                "hypothesis:test_hyp",
                "--type",
                "causal",
                "--path",
                p,
            ],
        )
        runner.invoke(main, ["inquiry", "add-node", "local-dag", "concept/x", "--role", "BoundaryIn", "--path", p])
        runner.invoke(main, ["inquiry", "add-node", "local-dag", "concept/y", "--role", "BoundaryOut", "--path", p])
        runner.invoke(
            main,
            ["inquiry", "set-estimand", "local-dag", "--treatment", "concept/x", "--outcome", "concept/y", "--path", p],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "X causes Y",
                "--subject",
                "concept:x",
                "--predicate",
                "scic:causes",
                "--object",
                "concept:y",
                "--id",
                "x_causes_y",
                "--source",
                "article:doi_claim",
                "--path",
                p,
            ],
        )

        result = runner.invoke(
            main,
            [
                "inquiry",
                "add-edge",
                "local-dag",
                "concept:x",
                "scic:causes",
                "concept:y",
                "--claim",
                "proposition:x_causes_y",
                "--path",
                p,
            ],
        )
        assert result.exit_code == 0

        export_result = runner.invoke(main, ["inquiry", "export-pgmpy", "local-dag", "--path", p])
        assert export_result.exit_code == 0
        assert '("x", "y")' in export_result.output
        assert 'claim: "X causes Y"' in export_result.output

    def test_export_pgmpy_uses_explicit_claim_attachments(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        _setup_causal_inquiry(runner, graph_path)
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "X causes Y",
                "--subject",
                "concept:x",
                "--predicate",
                "scic:causes",
                "--object",
                "concept:y",
                "--id",
                "x_causes_y",
                "--source",
                "article:doi_claim",
                "--confidence",
                "0.85",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Independent study supports X causes Y",
                "--id",
                "support_xy",
                "--source",
                "article:doi_support",
                "--confidence",
                "0.7",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Counter-evidence disputes X causes Y",
                "--id",
                "dispute_xy",
                "--source",
                "article:doi_dispute",
                "--confidence",
                "0.4",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "evidence",
                "proposition/support_xy",
                "proposition/x_causes_y",
                "--stance",
                "supports",
                "--path",
                p,
            ],
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "evidence",
                "proposition/dispute_xy",
                "proposition/x_causes_y",
                "--stance",
                "disputes",
                "--path",
                p,
            ],
        )

        attach_result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/x",
                "scic:causes",
                "concept/y",
                "--graph",
                "graph/causal",
                "--claim",
                "proposition:x_causes_y",
                "--path",
                p,
            ],
        )
        assert attach_result.exit_code == 0

        result = runner.invoke(main, ["inquiry", "export-pgmpy", "test-dag", "--path", p])
        assert result.exit_code == 0
        assert 'claim: "X causes Y"' in result.output
        assert "confidence: 0.85" in result.output
        assert "supports: 1" in result.output
        assert "disputes: 1" in result.output
        assert "TODO" in result.output
        assert "Edge z -> y has no attached relation claim" in result.output

    def test_export_pgmpy_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        _setup_causal_inquiry(runner, graph_path)
        out_file = tmp_path / "dag.py"
        result = runner.invoke(
            main, ["inquiry", "export-pgmpy", "test-dag", "--output", str(out_file), "--path", str(graph_path)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "BayesianNetwork" in content

    def test_export_chirho_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        _setup_causal_inquiry(runner, graph_path)
        out_file = tmp_path / "model.py"
        result = runner.invoke(
            main, ["inquiry", "export-chirho", "test-dag", "--output", str(out_file), "--path", str(graph_path)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "pyro.sample" in content

    def test_export_pgmpy_stdout(self, runner: CliRunner, graph_path: Path) -> None:
        _setup_causal_inquiry(runner, graph_path)
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "test-dag", "--path", str(graph_path)])
        assert result.exit_code == 0
        assert "BayesianNetwork" in result.output

    def test_export_non_causal_errors(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(main, ["inquiry", "init", "gen", "--label", "General", "--target", "hypothesis:h1", "--path", p])
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "gen", "--path", p])
        assert result.exit_code != 0

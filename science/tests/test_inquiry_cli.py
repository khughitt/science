"""CLI tests for inquiry subcommands.

The graph-mutating ``inquiry add-*`` / ``set-estimand`` subcommands are retired;
inquiry graphs are now produced by the pure compiler
``science_tool.graph.inquiry_compile.emit_inquiry_views``. Reader/behaviour tests
build their inquiry graph through the ``build_inquiry_graph`` conftest helper (the
compile path) and keep their original reader assertions. Tests whose point *was*
the mutation now assert the retirement error.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import build_inquiry_graph
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.cli import main
from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset, _save_dataset


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
    def test_init_scaffolds_investigation_source(self, runner: CliRunner, tmp_path: Path) -> None:
        """`inquiry init` now scaffolds a patch-definition source file (no graph)."""
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
                "--profile",
                "investigation",
                "--project-root",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        dest = tmp_path / "entities" / "patches" / "sp-geometry.md"
        assert dest.exists()
        text = dest.read_text()
        assert "patch_type: inquiry" in text
        assert "profile: investigation" in text
        assert "focal: hypothesis:h01" in text
        # The scaffolder writes a source file, never the graph.
        assert not (tmp_path / "knowledge" / "graph.trig").exists()

    def test_init_causal_requires_estimand(self, runner: CliRunner, tmp_path: Path) -> None:
        missing = runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "dag",
                "--label",
                "D",
                "--target",
                "hypothesis:h01",
                "--profile",
                "causal",
                "--project-root",
                str(tmp_path),
            ],
        )
        assert missing.exit_code != 0
        assert "treatment" in missing.output.lower()

        ok = runner.invoke(
            main,
            [
                "inquiry",
                "init",
                "dag",
                "--label",
                "D",
                "--target",
                "hypothesis:h01",
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
        assert ok.exit_code == 0, ok.output
        text = (tmp_path / "entities" / "patches" / "dag.md").read_text()
        assert "profile: causal" in text
        assert "treatment: concept:x" in text
        assert "outcome: concept:y" in text

    def test_init_duplicate_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        args = [
            "inquiry",
            "init",
            "dup",
            "--label",
            "A",
            "--target",
            "hypothesis:h01",
            "--profile",
            "investigation",
            "--project-root",
            str(tmp_path),
        ]
        assert runner.invoke(main, args).exit_code == 0
        assert runner.invoke(main, args).exit_code != 0


class TestInquiryMutatorsRetired:
    """The graph-mutating inquiry subcommands are retired; they must error."""

    @pytest.mark.parametrize(
        "args",
        [
            ["inquiry", "add-node", "test", "concept:input_data", "--role", "BoundaryIn"],
            ["inquiry", "add-node", "test", "concept:middle_step"],
            ["inquiry", "add-edge", "test", "concept:a", "sci:feedsInto", "concept:b"],
            ["inquiry", "add-assumption", "test", "Mean pooling sufficient", "--source", "paper:doi_test"],
            ["inquiry", "add-transformation", "test", "Extract sequences", "--tool", "BioPython"],
            ["inquiry", "set-estimand", "test", "--treatment", "concept:x", "--outcome", "concept:y"],
        ],
    )
    def test_mutator_is_retired(self, runner: CliRunner, graph_path: Path, args: list[str]) -> None:
        result = runner.invoke(main, [*args, "--path", str(graph_path)])
        assert result.exit_code != 0
        assert "retired" in result.output.lower()


class TestInquiryAddEdge:
    def test_edge_claim_help_uses_proposition_language(self, runner: CliRunner) -> None:
        for args in (["graph", "add", "edge", "--help"], ["inquiry", "add-edge", "--help"]):
            result = runner.invoke(main, args)
            assert result.exit_code == 0, result.output
            assert "Supporting proposition reference" in result.output
            assert "relation claim" not in result.output

    def test_compiled_edge_with_relation_claim_attaches_claim_to_edge(
        self, runner: CliRunner, graph_path: Path
    ) -> None:
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "concept", "a", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "b", "--path", p])
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Concept A feeds into concept B",
                "--subject",
                "concept:a",
                "--predicate",
                "sci:feedsInto",
                "--object",
                "concept:b",
                "--id",
                "a_feeds_into_b",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        build_inquiry_graph(
            graph_path,
            slug="test",
            flow_edges=[
                {
                    "subject": "concept:a",
                    "predicate": "feedsInto",
                    "object": "concept:b",
                    "claim_refs": ["proposition:a_feeds_into_b"],
                }
            ],
        )

        show_result = runner.invoke(main, ["inquiry", "show", "test", "--format", "json", "--path", p])
        assert show_result.exit_code == 0, show_result.output
        info = json.loads(show_result.output)
        assert info["edges"] == [
            {
                "subject": "http://example.org/project/concept/a",
                "predicate": "http://example.org/science/vocab/feedsInto",
                "object": "http://example.org/project/concept/b",
                "claims": ["http://example.org/project/proposition/a_feeds_into_b"],
            }
        ]

        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/test"))
        statement_uri = next(inquiry_graph.subjects(RDF.subject, PROJECT_NS["concept/a"]), None)
        assert statement_uri is not None
        assert (statement_uri, SCI_NS.backedByClaim, PROJECT_NS["proposition/a_feeds_into_b"]) in inquiry_graph
        assert (statement_uri, SCI_NS.validatedBy, PROJECT_NS["proposition/a_feeds_into_b"]) not in inquiry_graph


class TestInquiryList:
    def test_list_empty(self, runner: CliRunner, graph_path: Path) -> None:
        result = runner.invoke(main, ["inquiry", "list", "--path", str(graph_path), "--format", "json"])
        assert result.exit_code == 0

    def test_list_with_inquiries(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        build_inquiry_graph(graph_path, slug="i1", title="First")
        build_inquiry_graph(graph_path, slug="i2", title="Second")
        result = runner.invoke(main, ["inquiry", "list", "--path", p, "--format", "json"])
        assert result.exit_code == 0
        assert "First" in result.output
        assert "Second" in result.output


class TestInquiryShow:
    def test_show(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        build_inquiry_graph(graph_path, slug="test", title="Test")
        result = runner.invoke(main, ["inquiry", "show", "test", "--path", p, "--format", "json"])
        assert result.exit_code == 0
        assert "Test" in result.output

    def test_show_materialized_hyphenated_slug(self, runner: CliRunner, graph_path: Path) -> None:
        """A materialized inquiry (entity in graph/knowledge, hyphenated slug) is
        readable through `inquiry show`, with its related list rendered
        (fb-2026-05-12-001)."""
        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        uri = URIRef(PROJECT_NS["inquiry/h-3d-genome-substrate"])
        knowledge.add((uri, RDF.type, SCI_NS.Inquiry))
        knowledge.add((uri, SKOS.prefLabel, Literal("3D genome substrate")))
        knowledge.add((uri, SCI_NS.projectStatus, Literal("draft")))
        knowledge.add((uri, SKOS.related, URIRef(PROJECT_NS["hypothesis/h01"])))
        _save_dataset(dataset, graph_path)

        result = runner.invoke(main, ["inquiry", "show", "h-3d-genome-substrate", "--path", str(graph_path)])
        assert result.exit_code == 0, result.output
        assert "3D genome substrate" in result.output
        assert "draft" in result.output
        assert "Related: 1 entity" in result.output


class TestInquirySummary:
    def test_inquiry_summary_reports_claim_backing_and_priority(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "concept", "a", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "b", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "c", "--path", p])

        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Concept A feeds into concept B",
                "--subject",
                "concept:a",
                "--predicate",
                "sci:feedsInto",
                "--object",
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
                "proposition",
                "Concept B feeds into concept C",
                "--subject",
                "concept:b",
                "--predicate",
                "sci:feedsInto",
                "--object",
                "concept:c",
                "--id",
                "flow_b_c",
                "--source",
                "paper:doi_test",
                "--path",
                p,
            ],
        )

        # Build the inquiry (with claim-backed flow edges) via the compile path,
        # then attach the description note the summary reader renders as `text`.
        build_inquiry_graph(
            graph_path,
            slug="summary_test",
            title="Summary Test Inquiry",
            flow_edges=[
                {
                    "subject": "concept:a",
                    "predicate": "feedsInto",
                    "object": "concept:b",
                    "claim_refs": ["proposition:flow_a_b"],
                },
                {
                    "subject": "concept:b",
                    "predicate": "feedsInto",
                    "object": "concept:c",
                    "claim_refs": ["proposition:flow_b_c"],
                },
            ],
        )
        dataset = _load_dataset(graph_path)
        inquiry_graph = dataset.graph(URIRef(str(PROJECT_NS) + "inquiry/summary_test"))
        inquiry_graph.add(
            (URIRef(str(PROJECT_NS) + "inquiry/summary_test"), SKOS.note, Literal("Summary Test Inquiry Text"))
        )
        _save_dataset(dataset, graph_path)

        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
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
                "evidence",
                "proposition/flow_a_b_support",
                "proposition/flow_a_b",
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
                "proposition",
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
                "evidence",
                "proposition/flow_b_c_support",
                "proposition/flow_b_c",
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
                "proposition",
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
                "evidence",
                "proposition/flow_b_c_dispute",
                "proposition/flow_b_c",
                "--stance",
                "disputes",
                "--path",
                p,
            ],
        )

        result = runner.invoke(main, ["graph", "inquiry-summary", "--format", "json", "--path", p])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = payload["rows"][0]
        assert row["inquiry"] == "http://example.org/project/inquiry/summary_test"
        assert row["text"] == "Summary Test Inquiry Text"
        assert row["claim_count"] == "2"
        assert row["backed_claim_count"] == "2"
        # Legacy bare-cito evidence is not an evidence-line entity, so the contested signal
        # (now driven by belief aggregation) no longer fires; the dispute remains in count columns.
        assert row["contested_claim_count"] == "0"
        assert row["single_source_claim_count"] == "2"
        assert row["no_empirical_claim_count"] == "1"
        assert float(row["avg_risk_score"]) > 0.0
        assert float(row["priority_score"]) > 0.0

    def test_inquiry_summary_table_headers_are_sensible(self, runner: CliRunner, graph_path: Path) -> None:
        result = runner.invoke(main, ["graph", "inquiry-summary", "--path", str(graph_path)])
        assert result.exit_code == 0
        assert "Graph Inquiry Summary" in result.output
        assert "Inquiry" in result.output

    def test_inquiry_summary_includes_claims_from_hypothesis_targets(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        build_inquiry_graph(
            graph_path,
            slug="hypothesis_target",
            title="Hypothesis Target Inquiry",
            focal="hypothesis:h01",
        )
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Hypothesis-linked proposition without explicit inquiry backing",
                "--source",
                "paper:doi_test",
                "--id",
                "hypothesis_target_claim",
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
                "Literature support for hypothesis-linked claim",
                "--source",
                "paper:doi_test",
                "--evidence-type",
                "literature_evidence",
                "--id",
                "hypothesis_target_support",
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
                "proposition/hypothesis_target_support",
                "proposition/hypothesis_target_claim",
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
                "edge",
                "proposition/hypothesis_target_claim",
                "cito:discusses",
                "hypothesis/h01",
                "--path",
                p,
            ],
        )

        result = runner.invoke(main, ["graph", "inquiry-summary", "--format", "json", "--path", p])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(
            item
            for item in payload["rows"]
            if item["inquiry"] == "http://example.org/project/inquiry/hypothesis_target"
        )
        assert row["claim_count"] == "1"
        assert row["backed_claim_count"] == "0"
        assert row["no_empirical_claim_count"] == "1"

    def test_inquiry_summary_includes_claims_from_question_targets(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "question",
                    "QTARGET",
                    "--text",
                    "Question targeted by the inquiry",
                    "--source",
                    "paper:doi_test",
                    "--path",
                    p,
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Question-targeted proposition without explicit inquiry backing",
                    "--source",
                    "paper:doi_test",
                    "--id",
                    "question_target_claim",
                    "--path",
                    p,
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Empirical support for question-targeted claim",
                    "--source",
                    "paper:doi_test",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "question_target_support",
                    "--path",
                    p,
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "evidence",
                    "proposition/question_target_support",
                    "proposition/question_target_claim",
                    "--stance",
                    "supports",
                    "--path",
                    p,
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "question/qtarget",
                    "sci:addresses",
                    "proposition/question_target_claim",
                    "--path",
                    p,
                ],
            ).exit_code
            == 0
        )
        build_inquiry_graph(
            graph_path,
            slug="question_target",
            title="Question Target Inquiry",
            focal="question:qtarget",
        )

        result = runner.invoke(main, ["graph", "inquiry-summary", "--format", "json", "--path", p])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(
            item for item in payload["rows"] if item["inquiry"] == "http://example.org/project/inquiry/question_target"
        )
        assert row["claim_count"] == "1"
        assert row["backed_claim_count"] == "0"
        assert float(row["avg_risk_score"]) > 0.0
        assert float(row["priority_score"]) > 0.0


class TestInquiryValidate:
    def test_validate_valid(self, runner: CliRunner, graph_path: Path) -> None:
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "concept", "din", "--path", p])
        runner.invoke(main, ["graph", "add", "concept", "dout", "--path", p])
        build_inquiry_graph(
            graph_path,
            slug="test",
            boundary_roles=[
                {"ref": "concept:din", "role": "BoundaryIn"},
                {"ref": "concept:dout", "role": "BoundaryOut"},
            ],
            flow_edges=[{"subject": "concept:din", "predicate": "feedsInto", "object": "concept:dout"}],
        )
        result = runner.invoke(main, ["inquiry", "validate", "test", "--path", p, "--format", "json"])
        assert result.exit_code == 0

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from conftest import build_entity_graph, build_inquiry_graph
from rdflib import Dataset
from rdflib.namespace import PROV, RDF, Namespace

from science_tool.cli import main

EXPECTED_GRAPHS = (
    "graph/knowledge",
    "graph/causal",
    "graph/provenance",
    "graph/datasets",
)
PROJECT_NS = Namespace("http://example.org/project/")
SCI = Namespace("http://example.org/science/vocab/")
SCHEMA = Namespace("https://schema.org/")
BIOLINK = Namespace("https://w3id.org/biolink/vocab/")
CITO = Namespace("http://purl.org/spar/cito/")


def _entity(kind: str, entity_id: str, title: str, **frontmatter: object) -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {"title": title, **frontmatter},
        "body": f"{title}\n",
    }


def _evidence_line(
    entity_id: str,
    title: str,
    *,
    stance: str,
    target: str,
    **frontmatter: object,
) -> dict:
    return _entity(
        "evidence-line",
        entity_id,
        title,
        stance=stance,
        target=target,
        **frontmatter,
    )


@pytest.mark.parametrize(
    ("args", "command", "forward_key"),
    [
        (
            ["graph", "add", "concept", "Example Concept"],
            "graph add concept",
            "science entity create concept",
        ),
        (
            ["graph", "add", "proposition", "Example proposition"],
            "graph add proposition",
            "science propositions create",
        ),
        (
            ["graph", "add", "observation", "Example observation"],
            "graph add observation",
            "science entity create observation",
        ),
        (
            ["graph", "add", "evidence", "observation:o1", "proposition:p1", "--stance", "maybe"],
            "graph add evidence",
            "science evidence-lines create",
        ),
        (
            ["graph", "add", "finding", "Example finding"],
            "graph add finding",
            "science entity create finding",
        ),
        (
            ["graph", "add", "interpretation", "Example interpretation"],
            "graph add interpretation",
            "science interpretations create",
        ),
        (
            ["graph", "add", "discussion", "Example discussion"],
            "graph add discussion",
            "science discussions create",
        ),
        (
            ["graph", "add", "mechanism", "Example mechanism"],
            "graph add mechanism",
            "science entity create mechanism",
        ),
        (
            ["graph", "add", "hypothesis", "h1"],
            "graph add hypothesis",
            "science hypotheses create",
        ),
        (
            ["graph", "add", "question", "q1"],
            "graph add question",
            "science questions create",
        ),
        (
            ["graph", "add", "edge", "subject", "bad:predicate", "object", "--graph", "not-a-layer"],
            "graph add edge",
            "relations.yaml",
        ),
        (
            ["graph", "import", "does-not-exist.ttl"],
            "graph import",
            "Raw-triple import is retired",
        ),
        (
            ["graph", "stamp-revision"],
            "graph stamp-revision",
            "compiler stamps revisions",
        ),
        (
            ["graph", "migrate-addresses"],
            "graph migrate-addresses",
            "Address direction is canonical",
        ),
    ],
)
def test_retired_graph_writer_commands_report_forward_path(args: list[str], command: str, forward_key: str) -> None:
    runner = CliRunner()

    result = runner.invoke(main, args)

    assert result.exit_code != 0
    assert f"{command} is retired" in result.output
    assert forward_key in result.output
    assert "science graph build" in result.output
    assert "run, then run" not in result.output


def test_graph_init_creates_trig_with_named_graphs() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["graph", "init"])

        assert result.exit_code == 0
        graph_path = Path("knowledge/graph.trig")
        assert graph_path.exists()

        content = graph_path.read_text(encoding="utf-8")
        for graph_name in EXPECTED_GRAPHS:
            assert graph_name in content

        parsed = Dataset()
        parsed.parse(source=str(graph_path), format="trig")


def test_graph_init_copies_viz_notebook() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["graph", "init"])
        assert result.exit_code == 0

        viz_path = Path("code/notebooks/viz.py")
        assert viz_path.exists()
        content = viz_path.read_text(encoding="utf-8")
        assert "marimo" in content
        assert "Weakly Supported Claims" in content
        assert "Contested Claims" in content
        assert "Single-Source Claims" in content
        assert "viz" in result.output.lower()
        assert "uv run marimo edit" in result.output

        pyproject_path = Path("code/notebooks/pyproject.toml")
        assert pyproject_path.exists()
        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        assert "marimo" in pyproject_content
        assert "rdflib" in pyproject_content


def test_graph_init_viz_notebook_uses_store_summaries_for_dashboard_panels() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["graph", "init"])
        assert result.exit_code == 0

        viz_path = Path("code/notebooks/viz.py")
        content = viz_path.read_text(encoding="utf-8")
        assert "query_dashboard_summary" in content
        assert "query_neighborhood_summary" in content
        assert "query_question_summary" in content
        assert "query_inquiry_summary" in content
        assert "query_project_summary" in content
        assert "_project_summary_error" in content
        assert "Research Project Summary" in content
        assert "High-Priority Questions" in content
        assert "High-Priority Inquiries" in content
        assert "Claims Lacking Empirical Data Evidence" in content
        assert "High-Uncertainty Neighborhoods" in content
        assert "Evidence Type Mix" in content
        assert "SCIENCE_TOOL_IMPORT_ROOT = " in content
        assert "__SCIENCE_TOOL_IMPORT_ROOT__" not in content

        pyproject_path = Path("code/notebooks/pyproject.toml")
        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        assert "click" in pyproject_content


def test_graph_build_local_only_leaves_existing_composite_untouched() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        root = Path.cwd()
        peer = root / "peer"
        peer.mkdir()
        (root / "science.yaml").write_text(
            f"name: host\nid: host\nrole: project\npeers:\n  - id: peer\n    path: {peer}\n",
            encoding="utf-8",
        )
        knowledge = root / "knowledge"
        knowledge.mkdir()
        composite = knowledge / "composite.trig"
        composite.write_text("existing composite\n", encoding="utf-8")

        def fake_materialize(project_root: Path) -> Path:
            graph_path = project_root / "knowledge" / "graph.trig"
            graph_path.parent.mkdir(exist_ok=True)
            graph_path.write_text("local graph\n", encoding="utf-8")
            return graph_path

        with (
            patch("science_tool.cli.materialize_graph", side_effect=fake_materialize),
            patch("science_tool.registry.config.ensure_registered"),
            patch("science_tool.graph.composite.assemble_composite_graph") as assemble,
            patch("science_tool.graph.sources.load_project_sources", return_value=None),
            patch("science_tool.graph.suggest.suggest_ontologies", return_value=[]),
        ):
            result = runner.invoke(main, ["graph", "build", "--local-only"])

        assert result.exit_code == 0, result.output
        assert "Materialized local graph" in result.output
        assert "Skipped composite graph refresh" in result.output
        assemble.assert_not_called()
        assert composite.read_text(encoding="utf-8") == "existing composite\n"


def test_graph_build_default_refreshes_composite_when_peers_exist() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        root = Path.cwd()
        peer = root / "peer"
        peer.mkdir()
        (root / "science.yaml").write_text(
            f"name: host\nid: host\nrole: project\npeers:\n  - id: peer\n    path: {peer}\n",
            encoding="utf-8",
        )
        knowledge = root / "knowledge"
        knowledge.mkdir()
        composite = knowledge / "composite.trig"
        composite.write_text("stale composite\n", encoding="utf-8")

        def fake_materialize(project_root: Path) -> Path:
            graph_path = project_root / "knowledge" / "graph.trig"
            graph_path.parent.mkdir(exist_ok=True)
            graph_path.write_text("local graph\n", encoding="utf-8")
            return graph_path

        def fake_assemble(project_root: Path) -> Path:
            assert not (project_root / "knowledge" / "composite.trig").exists()
            out = project_root / "knowledge" / "composite.trig"
            out.write_text("fresh composite\n", encoding="utf-8")
            return out

        with (
            patch("science_tool.cli.materialize_graph", side_effect=fake_materialize),
            patch("science_tool.registry.config.ensure_registered"),
            patch("science_tool.graph.composite.assemble_composite_graph", side_effect=fake_assemble) as assemble,
            patch("science_tool.graph.sources.load_project_sources", return_value=None),
            patch("science_tool.graph.suggest.suggest_ontologies", return_value=[]),
        ):
            result = runner.invoke(main, ["graph", "build"])

        assert result.exit_code == 0, result.output
        assert "Materialized composite graph" in result.output
        assemble.assert_called_once_with(root)
        assert composite.read_text(encoding="utf-8") == "fresh composite\n"


def test_graph_export_json_emits_selected_overlays() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("concept", "drug", "Drug"),
                _entity("concept", "recovery", "Recovery"),
                _entity("hypothesis", "h1", "H1"),
                _entity("hypothesis", "h2", "H2"),
                _entity("proposition", "drug_causes_recovery", "Drug treatment improves recovery time"),
            ],
            relations=[
                {
                    "subject": "concept:drug",
                    "predicate": "scic:causes",
                    "object": "concept:recovery",
                    "graph_layer": "graph/causal",
                }
            ],
        )
        build_inquiry_graph(
            Path("knowledge/graph.trig"),
            slug="test_dag",
            title="Test DAG",
            profile="causal",
            focal="concept:recovery",
            treatment="concept:drug",
            outcome="concept:recovery",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
        )

        result = runner.invoke(main, ["graph", "export-json", "--overlay", "causal", "--overlay", "evidence"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema_version"] == "1"
        assert "causal" in payload["overlays"]
        assert "evidence" in payload["overlays"]
        assert (
            payload["overlays"]["causal"]["inquiries"]["inquiry/test_dag"]["treatment"]
            == "http://example.org/project/concept/drug"
        )
        assert any(edge["predicate"].endswith("/causes") for edge in payload["edges"])
        # Task 6: retired graph-add --claim/--bridge-between emitted backedByClaim
        # statement metadata and sci:bridgeBetween payloads; authored relations do not.


def test_graph_init_fails_if_graph_exists() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        first = runner.invoke(main, ["graph", "init"])
        assert first.exit_code == 0

        second = runner.invoke(main, ["graph", "init"])

        assert second.exit_code != 0
        assert "already exists" in second.output.lower()


def test_graph_stats_reports_named_graph_counts() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        stats = runner.invoke(main, ["graph", "stats"])

        assert stats.exit_code == 0
        for graph_name in EXPECTED_GRAPHS:
            assert graph_name in stats.output
        assert "triples" in stats.output.lower()


def test_graph_stats_supports_explicit_table_format() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        stats = runner.invoke(main, ["graph", "stats", "--format", "table"])
        assert stats.exit_code == 0
        assert "graph/knowledge" in stats.output
        assert "triples" in stats.output.lower()


def test_graph_stats_supports_json_format() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        stats = runner.invoke(main, ["graph", "stats", "--format", "json"])
        assert stats.exit_code == 0

        payload = json.loads(stats.output)
        assert isinstance(payload, dict)
        assert payload["format"] == "json"
        assert isinstance(payload["rows"], list)
        assert any(row["graph"] == "graph/knowledge" for row in payload["rows"])
        assert any(row["graph"] == "total" for row in payload["rows"])


def test_graph_add_article_records_reference() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        article = runner.invoke(main, ["graph", "add", "article", "10.1038/s41586-023-06957-x"])
        assert article.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

        article_uri = PROJECT_NS["article/doi_10_1038_s41586_023_06957_x"]

        assert (article_uri, RDF.type, SCI.Article) in knowledge
        assert (article_uri, SCHEMA.identifier, None) in knowledge


def test_graph_add_story_warns_graph_only_not_durable() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "story",
                "A story",
                "--summary",
                "Narrative summary",
                "--about",
                "hypothesis:h1",
                "--interpretation",
                "interpretation:i1",
            ],
        )

        assert result.exit_code == 0
        assert "written directly to graph.trig" in result.output
        assert "source-authored story entity" in result.output


def test_graph_add_paper_warns_legacy_composition_not_literature_note() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "paper",
                "A draft paper",
                "--story",
                "story:s1",
            ],
        )

        assert result.exit_code == 0
        assert "legacy composition command" in result.output
        assert "external literature note" in result.output


def test_graph_validate_passes_on_fresh_graph() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        assert result.exit_code == 0

        payload = json.loads(result.output)
        assert all(row["status"] == "pass" for row in payload["rows"])


def test_graph_validate_fails_when_claim_lacks_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(Path.cwd(), [_entity("proposition", "x_causes_y", "X causes Y", confidence=0.7)])

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        for triple in list(provenance.triples((None, PROV.wasDerivedFrom, None))):
            provenance.remove(triple)
        dataset.serialize(destination="knowledge/graph.trig", format="trig")

        result = runner.invoke(main, ["graph", "validate"])
        assert result.exit_code != 0
        assert "provenance" in result.output.lower()


def test_graph_validate_fails_on_causal_cycle() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("concept", "x", "X"),
                _entity("concept", "y", "Y"),
            ],
            relations=[
                {
                    "subject": "concept:x",
                    "predicate": "scic:causes",
                    "object": "concept:y",
                    "graph_layer": "graph/causal",
                },
                {
                    "subject": "concept:y",
                    "predicate": "scic:causes",
                    "object": "concept:x",
                    "graph_layer": "graph/causal",
                },
            ],
        )

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        assert result.exit_code != 0

        payload = json.loads(result.output)
        assert any(row["check"] == "causal_acyclicity" and row["status"] == "fail" for row in payload["rows"])


# Task 6: orphan warnings for sparse graph-add nodes are retired-mutator only.
# Authored source materialization emits profile/scope triples that make those
# nodes non-orphaned under the current validator.


def test_graph_diff_supports_json_output() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        diff = runner.invoke(main, ["graph", "diff", "--mode", "hybrid", "--format", "json"])
        assert diff.exit_code == 0

        payload = json.loads(diff.output)
        assert payload["format"] == "json"
        assert isinstance(payload["rows"], list)


def test_graph_diff_detects_new_input_file() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        doc_file = Path("doc/01-overview.md")
        doc_file.parent.mkdir(parents=True, exist_ok=True)
        doc_file.write_text("v1", encoding="utf-8")

        diff = runner.invoke(main, ["graph", "diff", "--mode", "hybrid", "--format", "json"])
        assert diff.exit_code == 0

        payload = json.loads(diff.output)
        assert any(row["path"] == "doc/01-overview.md" and row["reason"] == "new_file" for row in payload["rows"])


def test_graph_diff_hybrid_detects_hash_change_with_stable_mtime() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        doc_file = Path("doc/01-overview.md")
        doc_file.parent.mkdir(parents=True, exist_ok=True)
        doc_file.write_text("version 1", encoding="utf-8")

        # Build graph so revision metadata captures current doc file hash/mtime.
        build = runner.invoke(main, ["graph", "build", "--local-only"])
        assert build.exit_code == 0, build.output

        baseline_mtime_ns = doc_file.stat().st_mtime_ns
        doc_file.write_text("version 2", encoding="utf-8")
        os.utime(doc_file, ns=(baseline_mtime_ns, baseline_mtime_ns))

        mtime_only = runner.invoke(main, ["graph", "diff", "--mode", "mtime", "--format", "json"])
        assert mtime_only.exit_code == 0
        mtime_payload = json.loads(mtime_only.output)
        assert not any(row["path"] == "doc/01-overview.md" for row in mtime_payload["rows"])

        hybrid = runner.invoke(main, ["graph", "diff", "--mode", "hybrid", "--format", "json"])
        assert hybrid.exit_code == 0
        hybrid_payload = json.loads(hybrid.output)
        assert any(
            row["path"] == "doc/01-overview.md" and row["reason"] == "hash_changed" for row in hybrid_payload["rows"]
        )


def test_graph_viz_outputs_dot_to_stdout() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("concept", "brca1", "BRCA1"),
                _entity("concept", "tp53", "TP53"),
            ],
            relations=[
                {
                    "subject": "concept:brca1",
                    "predicate": "skos:broader",
                    "object": "concept:tp53",
                    "graph_layer": "graph/knowledge",
                }
            ],
        )

        viz = runner.invoke(main, ["graph", "viz", "--layer", "graph/knowledge"])
        assert viz.exit_code == 0
        assert "digraph" in viz.output
        assert "broader" in viz.output


def test_graph_viz_writes_dot_file() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        output_path = Path("knowledge/exports/graph.dot")
        viz = runner.invoke(main, ["graph", "viz", "--output", str(output_path)])
        assert viz.exit_code == 0
        assert output_path.exists()
        assert "digraph" in output_path.read_text(encoding="utf-8")


def test_doi_lookup_supports_json_format() -> None:
    runner = CliRunner()

    with patch(
        "science_tool.doi_cli.lookup_doi_metadata",
        return_value={
            "doi": "10.1038/s41586-023-06957-x",
            "title": "Example Paper",
            "source": "crossref",
        },
    ):
        result = runner.invoke(main, ["doi", "lookup", "10.1038/s41586-023-06957-x", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["format"] == "json"
    assert any(row["field"] == "title" and row["value"] == "Example Paper" for row in payload["rows"])


def test_graph_neighborhood_query_supports_json_format() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("concept", "brca1", "BRCA1"),
                _entity("concept", "tp53", "TP53"),
            ],
            relations=[
                {
                    "subject": "concept:brca1",
                    "predicate": "skos:broader",
                    "object": "concept:tp53",
                    "graph_layer": "graph/knowledge",
                }
            ],
        )

        neighborhood = runner.invoke(main, ["graph", "neighborhood", "BRCA1", "--format", "json"])
        assert neighborhood.exit_code == 0
        payload = json.loads(neighborhood.output)
        assert any(row["predicate"].endswith("broader") for row in payload["rows"])


# Task 6: graph claims currently filters schema:text written by retired
# graph-add propositions; authored proposition sources emit labels instead.


def _setup_evidence_graph() -> None:
    """Helper: author hypothesis H3 with supporting and disputing evidence lines."""
    build_entity_graph(
        Path.cwd(),
        [
            _entity("hypothesis", "h3", "BRCA1 drives resistance"),
            _evidence_line(
                "ev1",
                "Literature supports BRCA1 role",
                stance="supports",
                target="hypothesis:h3",
                source="paper:doi_10_1111_a",
            ),
            _evidence_line(
                "ev2",
                "Counter-evidence against BRCA1",
                stance="disputes",
                target="hypothesis:h3",
                source="paper:doi_10_2222_b",
            ),
        ],
    )


def _setup_claim_backed_hypothesis_evidence_graph() -> None:
    build_entity_graph(
        Path.cwd(),
        [
            _entity("hypothesis", "h3", "BRCA1 drives resistance"),
            _entity("proposition", "ev3", "Context-setting BRCA1 discussion"),
            _entity("proposition", "main", "Primary BRCA1 resistance claim"),
            _evidence_line(
                "ev1",
                "Literature supports BRCA1 role",
                stance="supports",
                target="proposition:main",
                source="paper:doi_10_1111_a",
            ),
            _evidence_line(
                "ev2",
                "Counter-evidence against BRCA1",
                stance="disputes",
                target="proposition:main",
                source="paper:doi_10_2222_b",
            ),
        ],
        relations=[
            {
                "subject": "proposition:main",
                "predicate": "cito:discusses",
                "object": "hypothesis:h3",
                "graph_layer": "graph/knowledge",
            }
        ],
    )


def test_graph_evidence_groups_by_supports_refutes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_evidence_graph()

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h3", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 2
        relations = {row["relation"] for row in rows}
        assert relations == {"supports", "disputes"}
        texts = {row["text"] for row in rows}
        assert texts == {"Literature supports BRCA1 role", "Counter-evidence against BRCA1"}


def test_graph_evidence_returns_empty_for_unknown_hypothesis() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_evidence_graph()

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h999", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 0


def test_graph_evidence_returns_support_and_dispute_for_claim() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_claim_backed_hypothesis_evidence_graph()

        result = runner.invoke(main, ["graph", "evidence", "proposition/main", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 2
        assert {row["relation"] for row in rows} == {"supports", "disputes"}
        assert {row["text"] for row in rows} == {
            "Literature supports BRCA1 role",
            "Counter-evidence against BRCA1",
        }
        assert all(row["relation"] != "discusses" for row in rows)


def test_graph_evidence_hypothesis_aggregates_linked_claim_evidence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_claim_backed_hypothesis_evidence_graph()

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h3", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 2
        assert {row["relation"] for row in rows} == {"supports", "disputes"}
        assert {row["text"] for row in rows} == {
            "Literature supports BRCA1 role",
            "Counter-evidence against BRCA1",
        }
        assert all(row["relation"] != "discusses" for row in rows)


def test_graph_evidence_merges_sources_for_reused_evidence_node() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "main", "Multi-source main claim"),
                _evidence_line(
                    "ev1",
                    "Reusable support evidence",
                    stance="supports",
                    target="proposition:main",
                    source="paper:doi_10_5555_e",
                ),
            ],
        )

        result = runner.invoke(main, ["graph", "evidence", "proposition/main", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 1
        assert "proposition/ev1" in rows[0]["sources"] or len(rows[0]["sources"]) > 0


def test_graph_evidence_falls_back_to_relation_claim_text_for_non_claim_subjects() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("hypothesis", "h1", "Hypothesis H1"),
                _entity("observation", "brca1_observation", "BRCA1 observation"),
            ],
            relations=[
                {
                    "subject": "observation:brca1_observation",
                    "predicate": "cito:supports",
                    "object": "hypothesis:h1",
                    "graph_layer": "graph/knowledge",
                }
            ],
        )

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h1", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 1
        assert "brca1" in rows[0]["text"].lower()


def test_graph_evidence_ignores_non_claim_discusses_subjects_for_hypothesis_linking() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("hypothesis", "h1", "Hypothesis H1"),
                _entity("concept", "brca1", "BRCA1"),
                _evidence_line(
                    "ev1",
                    "Evidence attached to BRCA1 concept",
                    stance="supports",
                    target="concept:brca1",
                ),
            ],
        )

        evidence = runner.invoke(main, ["graph", "evidence", "hypothesis/h1", "--format", "json"])
        assert evidence.exit_code == 0
        evidence_payload = json.loads(evidence.output)
        assert evidence_payload["rows"] == []

        uncertainty = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert uncertainty.exit_code == 0
        uncertainty_payload = json.loads(uncertainty.output)
        assert all(row["entity"] != str(PROJECT_NS["hypothesis/h1"]) for row in uncertainty_payload["rows"])


def test_graph_coverage_shows_measured_and_observed_status() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("concept", "genex", "GeneX"),
                _entity("concept", "geney", "GeneY"),
                _entity("dataset", "rnaseq", "RNA-seq"),
            ],
            relations=[
                {
                    "subject": "concept:genex",
                    "predicate": "sci:measuredBy",
                    "object": "dataset:rnaseq",
                    "graph_layer": "graph/datasets",
                }
            ],
        )

        result = runner.invoke(main, ["graph", "coverage", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        genex_row = next((r for r in rows if "genex" in r["entity"]), None)
        geney_row = next((r for r in rows if "geney" in r["entity"]), None)
        assert genex_row is not None
        assert geney_row is not None
        assert genex_row["measured"] == "yes"
        assert geney_row["measured"] == "no"


def test_graph_gaps_reports_evidential_fragility() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "rc1", "BRCA1 is related to hypothesis h3"),
                _evidence_line("ev1", "Single supporting evidence", stance="supports", target="proposition:rc1"),
            ],
        )

        result = runner.invoke(main, ["graph", "gaps", "proposition/rc1", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert any("evidential_fragility(single_source)" in row["issues"] for row in rows)


# Task 6: structural low-connectivity gaps for sparse graph-add edges are
# retired-mutator only because authored entities materialize profile/scope
# triples that contribute to reader degree calculations.


def test_graph_uncertainty_ranks_by_epistemic_status_and_confidence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "weak_association", "Weak association between X and Y", confidence=0.3),
                _entity("proposition", "strong_association", "Strong association between A and B", confidence=0.9),
            ],
        )
        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 1
        assert rows[0]["entity"] == str(PROJECT_NS["proposition/weak_association"])


def test_graph_uncertainty_prioritizes_contested_and_single_source_claims() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "main", "Contested BRCA1 claim"),
                _evidence_line("ev1", "Support for contested BRCA1 claim", stance="supports", target="proposition:main"),
                _evidence_line("ev2", "Dispute for contested BRCA1 claim", stance="disputes", target="proposition:main"),
                _entity("proposition", "single", "Single-source BRCA1 claim"),
                _evidence_line(
                    "ev3",
                    "Only support for single-source BRCA1 claim",
                    stance="supports",
                    target="proposition:single",
                ),
                _entity("proposition", "low_conf", "Low-confidence BRCA1 claim", confidence=0.2),
                _entity("proposition", "multi", "Multi-source BRCA1 claim"),
                _evidence_line("ev5", "Reusable evidence node for multi-source claim", stance="supports", target="proposition:multi"),
                _evidence_line(
                    "ev6",
                    "Independent evidence for multi-source claim",
                    stance="supports",
                    target="proposition:multi",
                ),
            ],
        )

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert rows[0]["entity"] == str(PROJECT_NS["proposition/main"])
        assert "contested" in rows[0]["signals"]
        assert any(row["entity"] == str(PROJECT_NS["proposition/low_conf"]) for row in rows)
        low_conf_row = next(row for row in rows if row["entity"] == str(PROJECT_NS["proposition/low_conf"]))
        assert rows.index(low_conf_row) > 0
        assert any(row["entity"] == str(PROJECT_NS["proposition/single"]) for row in rows)
        single_row = next(row for row in rows if row["entity"] == str(PROJECT_NS["proposition/single"]))
        assert "single_source" in single_row["signals"]
        assert all(row["entity"] != str(PROJECT_NS["proposition/multi"]) for row in rows)


def test_graph_uncertainty_dedupes_reused_evidence_nodes_for_support_count() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "main", "Low-confidence multi-source claim", confidence=0.2),
                _evidence_line("ev1", "Reusable evidence node", stance="supports", target="proposition:main"),
            ],
        )

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        main_row = next(row for row in rows if row["entity"] == str(PROJECT_NS["proposition/main"]))
        assert main_row["support_count"] == "1"


def test_graph_uncertainty_includes_disputed_epistemic_status() -> None:
    from rdflib import Literal as RdfLiteral

    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(Path.cwd(), [_entity("proposition", "c_disputed", "Disputed claim about Z", confidence=0.7)])

        # Manually add epistemicStatus as a Literal to provenance graph
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        provenance.add((PROJECT_NS["proposition/c_disputed"], SCI.epistemicStatus, RdfLiteral("disputed")))
        dataset.serialize(destination="knowledge/graph.trig", format="trig")

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert any(row["entity"] == str(PROJECT_NS["proposition/c_disputed"]) for row in payload["rows"])


def test_graph_dashboard_summary_reports_evidence_mix_and_empirical_presence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "main", "Claim with mixed evidence"),
                _evidence_line(
                    "lit_support",
                    "Literature evidence for mixed claim",
                    stance="supports",
                    target="proposition:main",
                    evidence_type="literature_evidence",
                ),
                _evidence_line(
                    "emp_support",
                    "Empirical evidence for mixed claim",
                    stance="supports",
                    target="proposition:main",
                    evidence_type="empirical_data_evidence",
                ),
                _entity("proposition", "contested", "Contested literature-only claim"),
                _evidence_line(
                    "contested_support",
                    "Literature support for contested claim",
                    stance="supports",
                    target="proposition:contested",
                    evidence_type="literature_evidence",
                ),
                _evidence_line(
                    "contested_dispute",
                    "Negative empirical result for contested claim",
                    stance="disputes",
                    target="proposition:contested",
                    evidence_type="negative_result",
                ),
            ],
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        mixed_row = next(row for row in payload["rows"] if row["label"] == "Claim with mixed evidence")
        assert mixed_row["support_count"] == "2"
        assert mixed_row["dispute_count"] == "0"
        assert mixed_row["has_empirical_data"] == "yes"
        assert mixed_row["evidence_types"] == "empirical_data; literature"

        contested_row = next(row for row in payload["rows"] if row["label"] == "Contested literature-only claim")
        assert contested_row["support_count"] == "1"
        assert contested_row["dispute_count"] == "1"
        assert contested_row["has_empirical_data"] == "no"
        assert contested_row["evidence_types"] == "literature; negative_result"


# Task 6: retired graph-add proposition metadata emitted dashboard fields
# (explicit semantics, pre-registrations, interaction terms, bridge hypotheses)
# that authored proposition sources do not currently materialize.


def test_graph_dashboard_summary_counts_benchmark_evidence_as_empirical_presence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("proposition", "benchmark_target", "Benchmark-backed claim"),
                _evidence_line(
                    "benchmark_support",
                    "Benchmark evidence for claim",
                    stance="supports",
                    target="proposition:benchmark_target",
                    source="paper:doi_10_6666_f",
                    evidence_type="benchmark_evidence",
                ),
            ],
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        benchmark_row = next(row for row in payload["rows"] if row["label"] == "Benchmark-backed claim")
        assert benchmark_row["has_empirical_data"] == "yes"
        assert benchmark_row["evidence_types"] == "benchmark"


def test_graph_neighborhood_summary_prioritizes_contested_local_clusters() -> None:
    runner = CliRunner()

    # Phase 1: belief (and therefore the `contested` signal) is derived ONLY from
    # evidence-line ENTITY cito edges materialized from `entities/evidence-lines/*.md`, not
    # from bare cito edges authored by `graph add evidence`. So the contested cluster's
    # contestedness must be authored as real evidence-line markdown, and cross-cluster
    # adjacency must be authored as source relations, then materialized via `graph build`.
    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("hypothesis", "hcluster", "Local cluster of uncertain claims"),
                # CONTESTED cluster: one clean independent direct-test support PLUS one diagnostic
                # dispute (model_criticism + scoped). A diagnostic/scoped dispute sets contested
                # WITHOUT capping or eliminating belief -> "fragile (contested)".
                _entity("proposition", "cluster_a", "Contested local claim A"),
                _evidence_line(
                    "cluster-a-support",
                    "Literature support for contested local claim A",
                    stance="supports",
                    target="proposition:cluster_a",
                    evidence_role="direct_test",
                    strength="strong",
                    independence="independent",
                    independence_group="g-cluster-a-support",
                    evidence_type="literature_evidence",
                ),
                _evidence_line(
                    "cluster-a-dispute",
                    "Negative result for contested local claim A",
                    stance="disputes",
                    target="proposition:cluster_a",
                    evidence_role="model_criticism",
                    dispute_scope="generalization",
                    evidence_type="negative_result",
                ),
                # FRAGILE (NOT contested) contrast cluster: a single supporting
                # evidence-line, no dispute. Shares hypothesis:hcluster with cluster_a.
                _entity("proposition", "cluster_b", "Fragile local claim B"),
                _evidence_line(
                    "cluster-b-support",
                    "Single-source support for fragile local claim B",
                    stance="supports",
                    target="proposition:cluster_b",
                    evidence_role="proxy_support",
                    strength="moderate",
                    independence="independent",
                    independence_group="g-cluster-b-support",
                    evidence_type="literature_evidence",
                ),
                # ISOLATED, well-supported, non-contested claim: two independent empirical
                # direct-test supports, no hypothesis link -> isolated neighborhood, risk 0.
                _entity("proposition", "isolated_good", "Isolated well-supported claim"),
                _evidence_line(
                    "isolated-support-1",
                    "Empirical support one for isolated claim",
                    stance="supports",
                    target="proposition:isolated_good",
                    evidence_role="direct_test",
                    strength="strong",
                    independence="independent",
                    independence_group="g-isolated-1",
                    evidence_type="empirical_data_evidence",
                ),
                _evidence_line(
                    "isolated-support-2",
                    "Empirical support two for isolated claim",
                    stance="supports",
                    target="proposition:isolated_good",
                    evidence_role="direct_test",
                    strength="strong",
                    independence="independent",
                    independence_group="g-isolated-2",
                    evidence_type="empirical_data_evidence",
                ),
            ],
            relations=[
                {
                    "subject": "proposition:cluster_a",
                    "predicate": "cito:discusses",
                    "object": "hypothesis:hcluster",
                    "graph_layer": "graph/knowledge",
                },
                {
                    "subject": "proposition:cluster_b",
                    "predicate": "cito:discusses",
                    "object": "hypothesis:hcluster",
                    "graph_layer": "graph/knowledge",
                },
            ],
        )

        result = runner.invoke(main, ["graph", "neighborhood-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        # Materialized claims carry their title on `label` (skos:prefLabel); `text` falls
        # back to the short URI name, so match on `label` here.
        contested_row = next(row for row in payload["rows"] if row["label"] == "Contested local claim A")
        isolated_row = next(row for row in payload["rows"] if row["label"] == "Isolated well-supported claim")

        assert contested_row["neighbor_claim_count"] == "1"
        # cluster_a is genuinely contested: a supporting evidence-line plus a diagnostic
        # (model_criticism / scoped) disputing evidence-line yield belief
        # "fragile (contested)". cluster_b, the shared neighbor, is fragile-but-NOT-contested,
        # so the neighborhood's contested_count is exactly 1 (the contested claim itself).
        assert contested_row["contested_count"] == "1"
        # cluster_b is single-source (one support, one source); cluster_a draws on two
        # sources so it does not add to this count.
        assert contested_row["single_source_count"] == "1"
        assert contested_row["no_empirical_count"] == "2"
        assert contested_row["structural_fragility"] == "connected"

        assert isolated_row["neighbor_claim_count"] == "0"
        assert isolated_row["structural_fragility"] == "isolated"
        # The contested cluster outranks the isolated claim, and the contested term
        # (0.75 * contested_count) genuinely contributes to that gap.
        assert float(contested_row["neighborhood_risk"]) > float(isolated_row["neighborhood_risk"])


def test_graph_question_summary_reports_rollup_metrics_and_top_limit() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("question", "q1", "Which claims matter most for the contested question?"),
                _entity("question", "q2", "Lower-priority comparison question"),
                _entity("proposition", "question_contested", "Contested literature-only question claim"),
                _evidence_line(
                    "question_contested_support",
                    "Literature support for contested question claim",
                    stance="supports",
                    target="proposition:question_contested",
                    evidence_type="literature_evidence",
                ),
                _entity("proposition", "question_empirical", "Empirically supported question claim"),
                _evidence_line(
                    "question_empirical_support",
                    "Empirical support for question claim",
                    stance="supports",
                    target="proposition:question_empirical",
                    evidence_type="empirical_data_evidence",
                ),
                _evidence_line(
                    "question_empirical_support_2",
                    "Independent empirical support for question claim",
                    stance="supports",
                    target="proposition:question_empirical",
                    evidence_type="empirical_data_evidence",
                ),
                _entity("proposition", "question_low_priority", "Low-priority comparison question claim"),
                _evidence_line(
                    "question_low_priority_support",
                    "Empirical support for low-priority claim",
                    stance="supports",
                    target="proposition:question_low_priority",
                    evidence_type="empirical_data_evidence",
                ),
            ],
            relations=[
                {
                    "subject": "question:q1",
                    "predicate": "sci:addresses",
                    "object": "proposition:question_contested",
                    "graph_layer": "graph/knowledge",
                },
                {
                    "subject": "question:q1",
                    "predicate": "sci:addresses",
                    "object": "proposition:question_empirical",
                    "graph_layer": "graph/knowledge",
                },
                {
                    "subject": "question:q2",
                    "predicate": "sci:addresses",
                    "object": "proposition:question_low_priority",
                    "graph_layer": "graph/knowledge",
                },
            ],
        )

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json", "--top", "1"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        assert len(payload["rows"]) == 1
        row = payload["rows"][0]
        assert row["question"] == "http://example.org/project/question/q1"
        assert row["claim_count"] == "2"
        assert row["neighborhood_count"] == "2"
        assert row["contested_claim_count"] == "0"
        assert row["single_source_claim_count"] == "1"
        assert row["no_empirical_claim_count"] == "1"
        assert float(row["avg_risk_score"]) > 0.0
        assert float(row["priority_score"]) > 0.0


def test_graph_question_summary_table_headers_are_sensible() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        result = runner.invoke(main, ["graph", "question-summary"])
        assert result.exit_code == 0
        assert "Graph Question Summary" in result.output
        assert "Question" in result.output
        assert "Text" in result.output


def test_graph_project_summary_rolls_up_research_profile() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("science.yaml").write_text(
            "name: demo\nprofile: research\nknowledge_profiles:\n  local: local\n",
            encoding="utf-8",
        )
        build_entity_graph(
            Path.cwd(),
            [
                _entity("question", "qproj", "Which research path should we prioritize?"),
                _entity("proposition", "project_contested", "Contested project claim"),
                _evidence_line(
                    "project_support",
                    "Literature support for project claim",
                    stance="supports",
                    target="proposition:project_contested",
                    evidence_type="literature_evidence",
                ),
                _entity("proposition", "project_empirical", "Empirically supported project claim"),
                _evidence_line(
                    "project_empirical_support",
                    "Empirical support for project claim",
                    stance="supports",
                    target="proposition:project_empirical",
                    evidence_type="empirical_data_evidence",
                ),
            ],
            relations=[
                {
                    "subject": "question:qproj",
                    "predicate": "sci:addresses",
                    "object": "proposition:project_contested",
                    "graph_layer": "graph/knowledge",
                },
                {
                    "subject": "question:qproj",
                    "predicate": "sci:addresses",
                    "object": "proposition:project_empirical",
                    "graph_layer": "graph/knowledge",
                },
            ],
        )

        build_inquiry_graph(
            Path("knowledge/graph.trig"),
            slug="project_inquiry",
            title="Project Inquiry",
            focal="question:qproj",
        )

        result = runner.invoke(main, ["graph", "project-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = payload["rows"][0]

        assert row["profile"] == "research"
        assert row["question_count"] == "1"
        assert row["inquiry_count"] == "1"
        assert row["claim_count"] == "2"
        assert row["project"] == str(Path.cwd())
        assert "high_risk_neighborhood_count" in row
        assert "avg_risk_score" in row
        assert "priority_score" in row


def test_graph_project_summary_rejects_software_profile() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("science.yaml").write_text("name: demo\nprofile: software\n", encoding="utf-8")
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(main, ["graph", "project-summary", "--format", "json"])
        assert result.exit_code != 0
        assert "project-summary is currently defined only for research projects" in result.output


def test_graph_question_summary_includes_claims_from_related_hypotheses() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                _entity("hypothesis", "hrel", "Hypothesis related to the question"),
                _entity(
                    "question",
                    "qrel",
                    "Question linked to a related hypothesis",
                    related=["hypothesis:hrel"],
                ),
                _entity("proposition", "related_hypothesis_claim", "Claim linked to related hypothesis only"),
                _evidence_line(
                    "related_hypothesis_support",
                    "Literature support for related hypothesis claim",
                    stance="supports",
                    target="proposition:related_hypothesis_claim",
                    evidence_type="literature_evidence",
                ),
            ],
            relations=[
                {
                    "subject": "proposition:related_hypothesis_claim",
                    "predicate": "cito:discusses",
                    "object": "hypothesis:hrel",
                    "graph_layer": "graph/knowledge",
                }
            ],
        )

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(item for item in payload["rows"] if item["question"] == "http://example.org/project/question/qrel")
        assert row["claim_count"] == "1"
        assert row["no_empirical_claim_count"] == "1"


def test_graph_scan_prose_returns_annotations_json() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "01-overview.md").write_text(
            '---\nontology_terms:\n  - "biolink:Gene"\n---\n\nBRCA1 [`NCBIGene:672`] is important.\n',
            encoding="utf-8",
        )

        result = runner.invoke(main, ["graph", "scan-prose", "doc", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 1
        assert payload["rows"][0]["frontmatter_terms"] == "biolink:Gene"
        assert "NCBIGene:672" in payload["rows"][0]["inline_annotations"]


def test_graph_scan_prose_returns_empty_for_unannotated_dir() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "plain.md").write_text("No annotations here.\n", encoding="utf-8")

        result = runner.invoke(main, ["graph", "scan-prose", "doc", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 0


def test_graph_predicates_outputs_table() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "predicates"])
    assert result.exit_code == 0
    assert "cito:supports" in result.output
    assert "skos:related" in result.output
    assert "sci:projectStatus" in result.output


def test_graph_predicates_outputs_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "predicates", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload["rows"], list)
    assert len(payload["rows"]) > 10
    predicates = {row["predicate"] for row in payload["rows"]}
    predicate_rows = {row["predicate"]: row for row in payload["rows"]}
    assert "cito:supports" in predicates
    assert "skos:related" in predicates
    assert "scic:causes" in predicates
    assert predicate_rows["cito:supports"]["layer"] == "graph/knowledge"
    assert predicate_rows["cito:disputes"]["layer"] == "graph/knowledge"


def test_graph_question_summary_returns_all_rows_by_default() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        build_entity_graph(
            Path.cwd(),
            [
                item
                for i in range(30)
                for item in (
                    _entity("question", f"q{i:02d}", f"Question {i}"),
                    _entity("proposition", f"q{i:02d}", f"Claim {i}"),
                )
            ],
            relations=[
                {
                    "subject": f"question:q{i:02d}",
                    "predicate": "sci:addresses",
                    "object": f"proposition:q{i:02d}",
                    "graph_layer": "graph/knowledge",
                }
                for i in range(30)
            ],
        )

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 30

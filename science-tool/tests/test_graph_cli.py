import json
import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rdflib import Dataset, Literal
from rdflib.namespace import PROV, RDF, SKOS, Namespace

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


def test_graph_export_json_emits_selected_overlays() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "Drug"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "Recovery"]).exit_code == 0
        assert (
            runner.invoke(main, ["graph", "add", "hypothesis", "H1", "--text", "H1", "--source", "paper:h1"]).exit_code
            == 0
        )
        assert (
            runner.invoke(main, ["graph", "add", "hypothesis", "H2", "--text", "H2", "--source", "paper:h2"]).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Drug treatment improves recovery time",
                    "--source",
                    "paper:doi_10.1234/drug_recovery",
                    "--id",
                    "drug_causes_recovery",
                    "--subject",
                    "concept/drug",
                    "--predicate",
                    "scic:causes",
                    "--object",
                    "concept/recovery",
                    "--bridge-between",
                    "hypothesis:h1",
                    "--bridge-between",
                    "hypothesis:h2",
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
                    "concept/drug",
                    "scic:causes",
                    "concept/recovery",
                    "--graph",
                    "graph/causal",
                    "--claim",
                    "proposition:drug_causes_recovery",
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                [
                    "inquiry",
                    "init",
                    "test-dag",
                    "--label",
                    "Test DAG",
                    "--target",
                    "concept/recovery",
                    "--type",
                    "causal",
                ],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/drug", "--role", "BoundaryIn"]).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main, ["inquiry", "add-node", "test-dag", "concept/recovery", "--role", "BoundaryOut"]
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                ["inquiry", "set-estimand", "test-dag", "--treatment", "concept/drug", "--outcome", "concept/recovery"],
            ).exit_code
            == 0
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
        edge_id = next(edge["id"] for edge in payload["edges"] if edge["predicate"].endswith("/causes"))
        assert payload["overlays"]["evidence"]["edges"][edge_id]["claims"][0]["bridge_between"] == [
            "hypothesis/h1",
            "hypothesis/h2",
        ]


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


def test_graph_add_concept_writes_expected_triples() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        add = runner.invoke(
            main,
            ["graph", "add", "concept", "BRCA1", "--type", "biolink:Gene", "--ontology-id", "NCBIGene:672"],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/brca1"]

        assert (concept_uri, RDF.type, SCI.Concept) in knowledge
        assert (concept_uri, RDF.type, BIOLINK.Gene) in knowledge
        assert (concept_uri, SKOS.prefLabel, None) in knowledge
        assert (concept_uri, SCHEMA.identifier, None) in knowledge


def test_graph_add_mechanism_writes_expected_triples() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "PHF19"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "PRC2 complex"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "PHF19-PRC2 dampens IFN signaling",
                    "--source",
                    "paper:doi_10_1000_ifn",
                    "--id",
                    "ifn_silencing",
                ],
            ).exit_code
            == 0
        )

        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "mechanism",
                "PHF19 / PRC2 / IFN",
                "--summary",
                "PHF19-PRC2 dampens IFN signaling.",
                "--participant",
                "concept:phf19",
                "--participant",
                "concept:prc2_complex",
                "--proposition",
                "proposition:ifn_silencing",
                "--id",
                "phf19-prc2-ifn",
            ],
        )
        assert add.exit_code == 0
        assert "Added mechanism:" in add.output

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        mechanism_uri = PROJECT_NS["mechanism/phf19_prc2_ifn"]

        assert (mechanism_uri, RDF.type, SCI.Mechanism) in knowledge
        assert (mechanism_uri, SKOS.prefLabel, Literal("PHF19 / PRC2 / IFN")) in knowledge
        assert (mechanism_uri, SCHEMA.description, Literal("PHF19-PRC2 dampens IFN signaling.")) in knowledge
        assert (mechanism_uri, SCI.hasParticipant, PROJECT_NS["concept/phf19"]) in knowledge
        assert (mechanism_uri, SCI.hasParticipant, PROJECT_NS["concept/prc2_complex"]) in knowledge
        assert (mechanism_uri, SCI.hasProposition, PROJECT_NS["proposition/ifn_silencing"]) in knowledge
        assert (mechanism_uri, SCI.projectStatus, Literal("draft")) in knowledge


def test_graph_add_mechanism_requires_two_participants() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "PHF19"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "PHF19-PRC2 dampens IFN signaling",
                    "--source",
                    "paper:doi_10_1000_ifn",
                    "--id",
                    "ifn_silencing",
                ],
            ).exit_code
            == 0
        )

        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "mechanism",
                "PHF19 / PRC2 / IFN",
                "--summary",
                "PHF19-PRC2 dampens IFN signaling.",
                "--participant",
                "concept:phf19",
                "--proposition",
                "proposition:ifn_silencing",
            ],
        )

        assert add.exit_code != 0
        assert "at least two participants" in add.output.lower()


def test_graph_add_paper_claim_hypothesis_records_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        article = runner.invoke(main, ["graph", "add", "article", "10.1038/s41586-023-06957-x"])
        assert article.exit_code == 0

        proposition = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "BRCA1 is associated with treatment resistance",
                "--source",
                "paper:doi_10_1038_s41586_023_06957_x",
                "--confidence",
                "0.8",
            ],
        )
        assert proposition.exit_code == 0

        hypothesis = runner.invoke(
            main,
            [
                "graph",
                "add",
                "hypothesis",
                "H3",
                "--text",
                "BRCA1 overexpression increases resistance",
                "--source",
                "paper:doi_10_1038_s41586_023_06957_x",
            ],
        )
        assert hypothesis.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])

        article_uri = PROJECT_NS["article/doi_10_1038_s41586_023_06957_x"]
        hypothesis_uri = PROJECT_NS["hypothesis/h3"]

        assert (article_uri, RDF.type, SCI.Article) in knowledge
        assert (article_uri, SCHEMA.identifier, None) in knowledge
        assert (hypothesis_uri, RDF.type, SCI.Hypothesis) in knowledge
        assert (hypothesis_uri, SCHEMA.text, None) in knowledge
        assert any(pred == SCI.confidence for _, pred, _ in provenance)
        assert any(pred == PROV.wasDerivedFrom for _, pred, _ in provenance)


def test_graph_add_edge_targets_requested_layer() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "skos:broader",
                "concept/tp53",
                "--graph",
                "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        assert (PROJECT_NS["concept/brca1"], SKOS.broader, PROJECT_NS["concept/tp53"]) in knowledge


def test_graph_add_relation_claim_writes_claim_types_and_relation_metadata() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        proposition = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "brca1 supports h3",
                "--source",
                "paper:doi_10_1038_s41586_023_06957_x",
                "--confidence",
                "0.8",
                "--id",
                "RC1",
                "--subject",
                "concept/brca1",
                "--predicate",
                "cito:supports",
                "--object",
                "hypothesis/h3",
            ],
        )
        assert proposition.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/rc1"]

        assert (prop_uri, RDF.type, SCI.Proposition) in knowledge
        assert (prop_uri, SCI.propSubject, PROJECT_NS["concept/brca1"]) in knowledge
        assert (prop_uri, SCI.propPredicate, Namespace("http://purl.org/spar/cito/").supports) in knowledge
        assert (prop_uri, SCI.propObject, PROJECT_NS["hypothesis/h3"]) in knowledge
        assert (prop_uri, SCHEMA.text, Literal("brca1 supports h3")) in knowledge
        assert (prop_uri, PROV.wasDerivedFrom, PROJECT_NS["paper/doi_10_1038_s41586_023_06957_x"]) in provenance
        assert any(pred == SCI.confidence for _, pred, _ in provenance.triples((prop_uri, None, None)))


def test_graph_add_edge_rejects_scientific_assertion_predicates() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "cito:supports",
                "hypothesis/h3",
                "--graph",
                "graph/knowledge",
            ],
        )

        assert edge.exit_code != 0
        assert "evidence" in edge.output

        disputes = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "cito:disputes",
                "hypothesis/h3",
                "--graph",
                "graph/knowledge",
            ],
        )

        assert disputes.exit_code != 0
        assert "evidence" in disputes.output

        # cito:discusses is a linking predicate, not an evidence stance — allowed via add edge
        discusses = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "proposition/c1",
                "cito:discusses",
                "hypothesis/h3",
                "--graph",
                "graph/knowledge",
            ],
        )

        assert discusses.exit_code == 0


def test_graph_add_edge_allows_structural_skos_related_in_knowledge() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "skos:related",
                "concept/tp53",
                "--graph",
                "graph/knowledge",
            ],
        )

        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        assert (PROJECT_NS["concept/brca1"], SKOS.related, PROJECT_NS["concept/tp53"]) in knowledge


def test_graph_add_edge_rejects_unknown_curie_prefix() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "scii:relatedTo",
                "concept/tp53",
                "--graph",
                "graph/knowledge",
            ],
        )

        assert edge.exit_code != 0
        assert "unknown curie prefix" in edge.output.lower()


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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "X causes Y",
                    "--source",
                    "paper:doi_10_1000_xyz",
                    "--confidence",
                    "0.7",
                ],
            ).exit_code
            == 0
        )

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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
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
                    "concept/y",
                    "scic:causes",
                    "concept/x",
                    "--graph",
                    "graph/causal",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        assert result.exit_code != 0

        payload = json.loads(result.output)
        assert any(row["check"] == "causal_acyclicity" and row["status"] == "fail" for row in payload["rows"])


def test_graph_validate_warns_orphaned_nodes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add a concept with no edges (only rdf:type triple)
        assert (
            runner.invoke(
                main,
                ["graph", "add", "concept", "Orphan Node", "--type", "biolink:Gene"],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        # Orphan check should be a warning (status=warn), not a failure
        assert result.exit_code == 0

        payload = json.loads(result.output)
        orphan_rows = [r for r in payload["rows"] if r["check"] == "orphaned_nodes"]
        assert len(orphan_rows) == 1
        assert orphan_rows[0]["status"] == "warn"
        assert "1" in orphan_rows[0]["details"]


def test_graph_validate_warns_orphaned_claim_nodes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Unlinked proposition",
                    "--source",
                    "paper:doi_10_8888_h",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        assert result.exit_code == 0

        payload = json.loads(result.output)
        orphan_rows = [r for r in payload["rows"] if r["check"] == "orphaned_nodes"]
        assert len(orphan_rows) == 1
        assert orphan_rows[0]["status"] == "warn"
        assert "1" in orphan_rows[0]["details"]


def test_graph_validate_warns_orphaned_question_nodes_with_maturity_only() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "question",
                    "Q1",
                    "--text",
                    "Open question",
                    "--source",
                    "paper:doi_10_9999_i",
                ],
            ).exit_code
            == 0
        )

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        knowledge.add((PROJECT_NS["question/q1"], SCI.maturity, Literal("early")))
        dataset.serialize(destination="knowledge/graph.trig", format="trig")

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        assert result.exit_code == 0

        payload = json.loads(result.output)
        orphan_rows = [r for r in payload["rows"] if r["check"] == "orphaned_nodes"]
        assert len(orphan_rows) == 1
        assert orphan_rows[0]["status"] == "warn"
        assert "1" in orphan_rows[0]["details"]


def test_graph_add_claim_same_text_different_sources_creates_distinct_claims() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Same proposition text",
                    "--source",
                    "paper:doi_10_1111_a",
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
                    "Same proposition text",
                    "--source",
                    "paper:doi_10_2222_b",
                ],
            ).exit_code
            == 0
        )

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

        proposition_entities = {str(subj) for subj, _, _ in knowledge.triples((None, RDF.type, SCI.Proposition))}
        assert len(proposition_entities) == 2


def test_graph_add_claim_supports_explicit_id() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        proposition = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Proposition with explicit ID",
                "--source",
                "paper:doi_10_3333_c",
                "--id",
                "C42",
            ],
        )
        assert proposition.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        assert (PROJECT_NS["proposition/c42"], RDF.type, SCI.Proposition) in knowledge


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

        # Update graph so revision metadata captures current doc file hash/mtime.
        assert runner.invoke(main, ["graph", "add", "concept", "BRCA1"]).exit_code == 0

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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "concept/brca1",
                    "skos:broader",
                    "concept/tp53",
                    "--graph",
                    "graph/knowledge",
                ],
            ).exit_code
            == 0
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
        "science_tool.cli.lookup_doi_metadata",
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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "concept/brca1",
                    "skos:broader",
                    "concept/tp53",
                    "--graph",
                    "graph/knowledge",
                ],
            ).exit_code
            == 0
        )

        neighborhood = runner.invoke(main, ["graph", "neighborhood", "BRCA1", "--format", "json"])
        assert neighborhood.exit_code == 0
        payload = json.loads(neighborhood.output)
        assert any(row["predicate"].endswith("broader") for row in payload["rows"])


def test_graph_claims_query_filters_about_term() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "BRCA1 is linked to resistance",
                    "--source",
                    "paper:doi_10_1111_a",
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
                    "Unrelated metabolism proposition",
                    "--source",
                    "paper:doi_10_2222_b",
                ],
            ).exit_code
            == 0
        )

        claims = runner.invoke(main, ["graph", "claims", "--about", "BRCA1", "--format", "json"])
        assert claims.exit_code == 0
        payload = json.loads(claims.output)
        assert any("BRCA1" in row["text"] for row in payload["rows"])
        assert not any("Unrelated metabolism proposition" in row["text"] for row in payload["rows"])


def _setup_evidence_graph(runner: CliRunner) -> None:
    """Helper: init graph, add hypothesis H3, add supporting and disputing propositions."""
    assert runner.invoke(main, ["graph", "init"]).exit_code == 0
    assert (
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "hypothesis",
                "H3",
                "--text",
                "BRCA1 drives resistance",
                "--source",
                "paper:doi_10_1111_a",
            ],
        ).exit_code
        == 0
    )
    # Add proposition entities and link them with evidence edges
    assert (
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Literature supports BRCA1 role",
                "--source",
                "paper:doi_10_1111_a",
                "--id",
                "ev1",
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
                "proposition/ev1",
                "hypothesis/h3",
                "--stance",
                "supports",
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
                "Counter-evidence against BRCA1",
                "--source",
                "paper:doi_10_2222_b",
                "--id",
                "ev2",
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
                "proposition/ev2",
                "hypothesis/h3",
                "--stance",
                "disputes",
            ],
        ).exit_code
        == 0
    )


def _setup_claim_backed_hypothesis_evidence_graph(runner: CliRunner) -> None:
    assert runner.invoke(main, ["graph", "init"]).exit_code == 0
    assert (
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "hypothesis",
                "H3",
                "--text",
                "BRCA1 drives resistance",
                "--source",
                "paper:doi_10_1111_a",
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
                "Context-setting BRCA1 discussion",
                "--source",
                "paper:doi_10_3333_c",
                "--id",
                "ev3",
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
                "Primary BRCA1 resistance claim",
                "--source",
                "paper:doi_10_1111_a",
                "--id",
                "main",
            ],
        ).exit_code
        == 0
    )
    # Link proposition/main to hypothesis/h3 via cito:discusses
    assert (
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "proposition/main",
                "cito:discusses",
                "hypothesis/h3",
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
                "Literature supports BRCA1 role",
                "--source",
                "paper:doi_10_1111_a",
                "--id",
                "ev1",
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
                "proposition/ev1",
                "proposition/main",
                "--stance",
                "supports",
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
                "Counter-evidence against BRCA1",
                "--source",
                "paper:doi_10_2222_b",
                "--id",
                "ev2",
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
                "proposition/ev2",
                "proposition/main",
                "--stance",
                "disputes",
            ],
        ).exit_code
        == 0
    )


def test_graph_evidence_groups_by_supports_refutes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_evidence_graph(runner)

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
        _setup_evidence_graph(runner)

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h999", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 0


def test_graph_evidence_returns_support_and_dispute_for_claim() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_claim_backed_hypothesis_evidence_graph(runner)

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
        _setup_claim_backed_hypothesis_evidence_graph(runner)

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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Multi-source main claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "main",
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
                    "Reusable support evidence",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "ev1",
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
                    "proposition/ev1",
                    "proposition/main",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "hypothesis",
                    "H1",
                    "--text",
                    "Hypothesis H1",
                    "--source",
                    "paper:doi_10_7777_g",
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
                    "concept/brca1",
                    "hypothesis/h1",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h1", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 1
        assert "brca1" in rows[0]["text"].lower() or "h1" in rows[0]["text"].lower()


def test_graph_evidence_ignores_non_claim_discusses_subjects_for_hypothesis_linking() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "hypothesis",
                    "H1",
                    "--text",
                    "Hypothesis H1",
                    "--source",
                    "paper:doi_10_7777_g",
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
                    "Evidence attached to BRCA1 concept",
                    "--source",
                    "paper:doi_10_7777_g",
                    "--id",
                    "ev1",
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
                    "proposition/ev1",
                    "concept/brca1",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "GeneX"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "GeneY"]).exit_code == 0
        # Link GeneX to a dataset
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "concept/genex",
                    "sci:measuredBy",
                    "dataset/rnaseq",
                    "--graph",
                    "graph/datasets",
                ],
            ).exit_code
            == 0
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


def test_graph_gaps_identifies_low_connectivity_and_missing_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Create center and a neighbor with only one connection (low connectivity)
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "concept/brca1",
                    "skos:broader",
                    "concept/orphan",
                    "--graph",
                    "graph/knowledge",
                ],
            ).exit_code
            == 0
        )
        result = runner.invoke(main, ["graph", "gaps", "concept/brca1", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert any("low_connectivity" in row["issues"] for row in rows)


def test_graph_gaps_distinguishes_structural_and_evidential_fragility() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "concept/brca1",
                    "skos:broader",
                    "concept/orphan",
                    "--graph",
                    "graph/knowledge",
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
                    "hypothesis",
                    "H3",
                    "--text",
                    "BRCA1 contributes to resistance",
                    "--source",
                    "paper:doi_10_1111_a",
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
                    "BRCA1 is related to hypothesis h3",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "rc1",
                    "--subject",
                    "concept/brca1",
                    "--predicate",
                    "sci:relatedTo",
                    "--object",
                    "hypothesis/h3",
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
                    "Single supporting evidence",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "ev1",
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
                    "proposition/ev1",
                    "proposition/rc1",
                    "--stance",
                    "supports",
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
                    "Second supporting evidence from same source",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "ev2",
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
                    "proposition/ev2",
                    "proposition/rc1",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "gaps", "concept/brca1", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert any("structural_fragility" in row["issues"] for row in rows)
        assert any("evidential_fragility(single_source)" in row["issues"] for row in rows)


def test_graph_uncertainty_ranks_by_epistemic_status_and_confidence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add a low-confidence proposition
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Weak association between X and Y",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--confidence",
                    "0.3",
                ],
            ).exit_code
            == 0
        )
        # Add a normal-confidence proposition (should NOT appear)
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Strong association between A and B",
                    "--source",
                    "paper:doi_10_2222_b",
                    "--confidence",
                    "0.9",
                ],
            ).exit_code
            == 0
        )
        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert len(rows) == 1
        assert "Weak" in rows[0]["text"]


def test_graph_uncertainty_prioritizes_contested_and_single_source_claims() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Contested BRCA1 claim",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "main",
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
                    "Support for contested BRCA1 claim",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "ev1",
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
                    "proposition/ev1",
                    "proposition/main",
                    "--stance",
                    "supports",
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
                    "Dispute for contested BRCA1 claim",
                    "--source",
                    "paper:doi_10_2222_b",
                    "--id",
                    "ev2",
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
                    "proposition/ev2",
                    "proposition/main",
                    "--stance",
                    "disputes",
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
                    "Single-source BRCA1 claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--id",
                    "single",
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
                    "Only support for single-source BRCA1 claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--id",
                    "ev3",
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
                    "proposition/ev3",
                    "proposition/single",
                    "--stance",
                    "supports",
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
                    "Low-confidence BRCA1 claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--confidence",
                    "0.2",
                    "--id",
                    "low_conf",
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
                    "Second support for single-source BRCA1 claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--id",
                    "ev4",
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
                    "proposition/ev4",
                    "proposition/single",
                    "--stance",
                    "supports",
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
                    "Multi-source BRCA1 claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "multi",
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
                    "Reusable evidence node for multi-source claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "ev5",
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
                    "proposition/ev5",
                    "proposition/multi",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )
        # Second evidence from a different source to make multi truly multi-source
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Independent evidence for multi-source claim",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--id",
                    "ev6",
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
                    "proposition/ev6",
                    "proposition/multi",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        assert rows[0]["text"] == "Contested BRCA1 claim"
        assert "contested" in rows[0]["signals"]
        assert any(row["text"] == "Low-confidence BRCA1 claim" for row in rows)
        low_conf_row = next(row for row in rows if row["text"] == "Low-confidence BRCA1 claim")
        assert rows.index(low_conf_row) > 0
        assert any(row["text"] == "Single-source BRCA1 claim" for row in rows)
        single_row = next(row for row in rows if row["text"] == "Single-source BRCA1 claim")
        assert "single_source" in single_row["signals"]
        assert all(row["text"] != "Multi-source BRCA1 claim" for row in rows)


def test_graph_uncertainty_dedupes_reused_evidence_nodes_for_support_count() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Low-confidence multi-source claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--confidence",
                    "0.2",
                    "--id",
                    "main",
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
                    "Reusable evidence node",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "ev1",
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
                    "proposition/ev1",
                    "proposition/main",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rows = payload["rows"]
        main_row = next(row for row in rows if row["text"] == "Low-confidence multi-source claim")
        assert main_row["support_count"] == "1"


def test_graph_uncertainty_includes_disputed_epistemic_status() -> None:
    from rdflib import Literal as RdfLiteral

    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Disputed claim about Z",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--confidence",
                    "0.7",
                    "--id",
                    "C_disputed",
                ],
            ).exit_code
            == 0
        )

        # Manually add epistemicStatus as a Literal to provenance graph
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        provenance.add((PROJECT_NS["proposition/c_disputed"], SCI.epistemicStatus, RdfLiteral("disputed")))
        dataset.serialize(destination="knowledge/graph.trig", format="trig")

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert any("Disputed" in row["text"] for row in payload["rows"])


def test_graph_add_claim_accepts_evidence_type_metadata() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Literature support for dashboard summary",
                "--source",
                "paper:doi_10_1111_a",
                "--evidence-type",
                "literature_evidence",
                "--id",
                "lit_support",
            ],
        )
        assert result.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/lit_support"]

        assert (prop_uri, SCI.evidenceType, Literal("literature_evidence")) in provenance


def test_graph_add_claim_accepts_explicit_evidence_semantics() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Cross-dataset but mechanistically indirect claim",
                "--source",
                "paper:doi_10_7777_semantics",
                "--id",
                "semantics_claim",
                "--statistical-support",
                "replicated",
                "--mechanistic-support",
                "inferred",
                "--replication-scope",
                "cross_dataset",
                "--claim-status",
                "weakened",
            ],
        )
        assert result.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/semantics_claim"]

        assert (prop_uri, SCI.statisticalSupport, Literal("replicated")) in provenance
        assert (prop_uri, SCI.mechanisticSupport, Literal("inferred")) in provenance
        assert (prop_uri, SCI.replicationScope, Literal("cross_dataset")) in provenance
        assert (prop_uri, SCI.claimStatus, Literal("weakened")) in provenance


def test_graph_add_claim_accepts_pre_registration_links() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Claim linked to a pre-registration",
                "--source",
                "paper:doi_10_9999_prereg",
                "--id",
                "prereg_claim",
                "--pre-registration",
                "pre-registration:edge-ribosome-e2f1",
                "--pre-registration",
                "pre-registration:edge-mtor-ribosome",
            ],
        )
        assert result.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/prereg_claim"]

        assert (
            prop_uri,
            SCI.preRegisteredIn,
            PROJECT_NS["pre-registration/edge-ribosome-e2f1"],
        ) in provenance
        assert (
            prop_uri,
            SCI.preRegisteredIn,
            PROJECT_NS["pre-registration/edge-mtor-ribosome"],
        ) in provenance


def test_graph_add_claim_accepts_interaction_terms() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "KRAS", "--type", "sci:Variable"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "KRAS modifies the drug to recovery slope",
                "--source",
                "paper:doi_10_1313_interaction",
                "--id",
                "interaction_claim",
                "--interaction-term",
                '{"modifier":"concept/kras","effect":"amplifies","note":"stronger survival slope in KRAS-mutant cases"}',
            ],
        )
        assert result.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/interaction_claim"]

        interaction_terms = list(provenance.objects(prop_uri, SCI.interactionTerm))
        assert len(interaction_terms) == 1
        payload = json.loads(str(interaction_terms[0]))
        assert payload["modifier"] == "http://example.org/project/concept/kras"
        assert payload["effect"] == "amplifies"


def test_graph_add_claim_accepts_bridge_between_hypotheses() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main, ["graph", "add", "hypothesis", "H1", "--text", "Hypothesis 1", "--source", "paper:doi_h1"]
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main, ["graph", "add", "hypothesis", "H2", "--text", "Hypothesis 2", "--source", "paper:doi_h2"]
            ).exit_code
            == 0
        )

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Bridge claim between H1 and H2",
                "--source",
                "paper:doi_10_1515_bridge",
                "--id",
                "bridge_claim",
                "--bridge-between",
                "hypothesis:h1",
                "--bridge-between",
                "hypothesis:h2",
            ],
        )
        assert result.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        prop_uri = PROJECT_NS["proposition/bridge_claim"]

        assert (prop_uri, SCI.bridgeBetween, PROJECT_NS["hypothesis/h1"]) in provenance
        assert (prop_uri, SCI.bridgeBetween, PROJECT_NS["hypothesis/h2"]) in provenance
        assert (prop_uri, CITO.discusses, PROJECT_NS["hypothesis/h1"]) in knowledge
        assert (prop_uri, CITO.discusses, PROJECT_NS["hypothesis/h2"]) in knowledge


def test_graph_dashboard_summary_reports_evidence_mix_and_empirical_presence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Claim with mixed evidence",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "main",
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
                    "Literature evidence for mixed claim",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "lit_support",
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
                    "proposition/lit_support",
                    "proposition/main",
                    "--stance",
                    "supports",
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
                    "Empirical evidence for mixed claim",
                    "--source",
                    "paper:doi_10_2222_b",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "emp_support",
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
                    "proposition/emp_support",
                    "proposition/main",
                    "--stance",
                    "supports",
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
                    "Contested literature-only claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--id",
                    "contested",
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
                    "Literature support for contested claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "contested_support",
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
                    "proposition/contested_support",
                    "proposition/contested",
                    "--stance",
                    "supports",
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
                    "Negative empirical result for contested claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--evidence-type",
                    "negative_result",
                    "--id",
                    "contested_dispute",
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
                    "proposition/contested_dispute",
                    "proposition/contested",
                    "--stance",
                    "disputes",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        mixed_row = next(row for row in payload["rows"] if row["text"] == "Claim with mixed evidence")
        assert mixed_row["support_count"] == "2"
        assert mixed_row["dispute_count"] == "0"
        assert mixed_row["has_empirical_data"] == "yes"
        assert mixed_row["belief_state"] in {"supported", "well_supported"}
        assert mixed_row["evidence_types"] == "empirical_data_evidence; literature_evidence"

        contested_row = next(row for row in payload["rows"] if row["text"] == "Contested literature-only claim")
        assert contested_row["support_count"] == "1"
        assert contested_row["dispute_count"] == "1"
        assert contested_row["has_empirical_data"] == "no"
        assert contested_row["belief_state"] == "contested"
        assert contested_row["evidence_types"] == "literature_evidence; negative_result"


def test_graph_dashboard_summary_reports_explicit_evidence_semantics() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Explicitly typed causal claim",
                    "--source",
                    "paper:doi_10_8888_semantics",
                    "--id",
                    "typed_claim",
                    "--statistical-support",
                    "replicated",
                    "--mechanistic-support",
                    "direct",
                    "--replication-scope",
                    "cross_dataset",
                    "--claim-status",
                    "active",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(item for item in payload["rows"] if item["text"] == "Explicitly typed causal claim")

        assert row["statistical_support"] == "replicated"
        assert row["mechanistic_support"] == "direct"
        assert row["replication_scope"] == "cross_dataset"
        assert row["claim_status"] == "active"


def test_graph_dashboard_summary_reports_pre_registration_links() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Pre-registered causal claim",
                    "--source",
                    "paper:doi_10_1212_prereg",
                    "--id",
                    "pre_registered_claim",
                    "--pre-registration",
                    "pre-registration:edge-ribosome-e2f1",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(item for item in payload["rows"] if item["text"] == "Pre-registered causal claim")

        assert row["pre_registration_count"] == "1"
        assert row["pre_registrations"] == "pre-registration/edge-ribosome-e2f1"


def test_graph_dashboard_summary_reports_interaction_terms() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "KRAS", "--type", "sci:Variable"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Interaction-typed causal claim",
                    "--source",
                    "paper:doi_10_1414_interaction",
                    "--id",
                    "interaction_typed_claim",
                    "--confidence",
                    "0.8",
                    "--interaction-term",
                    '{"modifier":"concept/kras","effect":"amplifies","note":"slope stronger in KRAS-mutant samples"}',
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(item for item in payload["rows"] if item["text"] == "Interaction-typed causal claim")

        assert row["interaction_count"] == "1"
        assert row["interaction_modifiers"] == "concept/kras(amplifies)"


def test_graph_dashboard_summary_reports_cross_hypothesis_bridges() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main, ["graph", "add", "hypothesis", "H1", "--text", "Hypothesis 1", "--source", "paper:doi_h1"]
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main, ["graph", "add", "hypothesis", "H2", "--text", "Hypothesis 2", "--source", "paper:doi_h2"]
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
                    "Bridge claim between H1 and H2",
                    "--source",
                    "paper:doi_10_1616_bridge",
                    "--id",
                    "bridge_summary_claim",
                    "--bridge-between",
                    "hypothesis:h1",
                    "--bridge-between",
                    "hypothesis:h2",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        row = next(item for item in payload["rows"] if item["text"] == "Bridge claim between H1 and H2")

        assert row["bridge_count"] == "2"
        assert row["bridge_hypotheses"] == "hypothesis/h1; hypothesis/h2"


def test_graph_dashboard_summary_counts_benchmark_evidence_as_empirical_presence() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Benchmark-backed claim",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--id",
                    "benchmark_target",
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
                    "Benchmark evidence for claim",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--evidence-type",
                    "benchmark_evidence",
                    "--id",
                    "benchmark_support",
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
                    "proposition/benchmark_support",
                    "proposition/benchmark_target",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "dashboard-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        benchmark_row = next(row for row in payload["rows"] if row["text"] == "Benchmark-backed claim")
        assert benchmark_row["has_empirical_data"] == "yes"
        assert benchmark_row["evidence_types"] == "benchmark_evidence"


def test_graph_neighborhood_summary_prioritizes_contested_local_clusters() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "hypothesis",
                    "Hcluster",
                    "--text",
                    "Local cluster of uncertain claims",
                    "--source",
                    "paper:doi_10_1111_a",
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
                    "Contested local claim A",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "cluster_a",
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
                    "Literature support for contested local claim A",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "cluster_a_support",
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
                    "proposition/cluster_a_support",
                    "proposition/cluster_a",
                    "--stance",
                    "supports",
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
                    "Negative result for contested local claim A",
                    "--source",
                    "paper:doi_10_2222_b",
                    "--evidence-type",
                    "negative_result",
                    "--id",
                    "cluster_a_dispute",
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
                    "proposition/cluster_a_dispute",
                    "proposition/cluster_a",
                    "--stance",
                    "disputes",
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
                    "Fragile local claim B",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--id",
                    "cluster_b",
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
                    "Single-source support for fragile local claim B",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "cluster_b_support",
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
                    "proposition/cluster_b_support",
                    "proposition/cluster_b",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        # Link cluster_a and cluster_b to hypothesis/hcluster so they share a neighborhood
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "proposition/cluster_a",
                    "cito:discusses",
                    "hypothesis/hcluster",
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
                    "proposition/cluster_b",
                    "cito:discusses",
                    "hypothesis/hcluster",
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
                    "Isolated well-supported claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--id",
                    "isolated_good",
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
                    "Empirical support one for isolated claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "isolated_support_1",
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
                    "proposition/isolated_support_1",
                    "proposition/isolated_good",
                    "--stance",
                    "supports",
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
                    "Empirical support two for isolated claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "isolated_support_2",
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
                    "proposition/isolated_support_2",
                    "proposition/isolated_good",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "neighborhood-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        contested_row = next(row for row in payload["rows"] if row["text"] == "Contested local claim A")
        isolated_row = next(row for row in payload["rows"] if row["text"] == "Isolated well-supported claim")

        assert contested_row["neighbor_claim_count"] == "1"
        assert contested_row["contested_count"] == "1"
        assert contested_row["single_source_count"] == "1"
        assert contested_row["no_empirical_count"] == "2"
        assert contested_row["structural_fragility"] == "connected"

        assert isolated_row["neighbor_claim_count"] == "0"
        assert isolated_row["structural_fragility"] == "isolated"
        assert float(contested_row["neighborhood_risk"]) > float(isolated_row["neighborhood_risk"])


def test_graph_question_summary_reports_rollup_metrics_and_top_limit() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "question",
                    "Q1",
                    "--text",
                    "Which claims matter most for the contested question?",
                    "--source",
                    "paper:doi_10_1111_a",
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
                    "question",
                    "Q2",
                    "--text",
                    "Lower-priority comparison question",
                    "--source",
                    "paper:doi_10_2222_b",
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
                    "Contested literature-only question claim",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "question_contested",
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
                    "Literature support for contested question claim",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "question_contested_support",
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
                    "proposition/question_contested_support",
                    "proposition/question_contested",
                    "--stance",
                    "supports",
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
                    "Negative result disputing contested question claim",
                    "--source",
                    "paper:doi_10_3333_c",
                    "--evidence-type",
                    "negative_result",
                    "--id",
                    "question_contested_dispute",
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
                    "proposition/question_contested_dispute",
                    "proposition/question_contested",
                    "--stance",
                    "disputes",
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
                    "Empirically supported question claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--id",
                    "question_empirical",
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
                    "Empirical support for question claim",
                    "--source",
                    "paper:doi_10_4444_d",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "question_empirical_support",
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
                    "proposition/question_empirical_support",
                    "proposition/question_empirical",
                    "--stance",
                    "supports",
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
                    "Low-priority comparison question claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--id",
                    "question_low_priority",
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
                    "Empirical support for low-priority claim",
                    "--source",
                    "paper:doi_10_5555_e",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "question_low_priority_support",
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
                    "proposition/question_low_priority_support",
                    "proposition/question_low_priority",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )

        for prop_ref, question_ref in (
            ("proposition/question_contested", "question/q1"),
            ("proposition/question_empirical", "question/q1"),
            ("proposition/question_low_priority", "question/q2"),
        ):
            assert (
                runner.invoke(
                    main,
                    [
                        "graph",
                        "add",
                        "edge",
                        question_ref,
                        "sci:addresses",
                        prop_ref,
                    ],
                ).exit_code
                == 0
            )

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json", "--top", "1"])
        assert result.exit_code == 0
        payload = json.loads(result.output)

        assert len(payload["rows"]) == 1
        row = payload["rows"][0]
        assert row["question"] == "http://example.org/project/question/q1"
        assert row["claim_count"] == "2"
        assert row["neighborhood_count"] == "2"
        assert row["contested_claim_count"] == "1"
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


def test_graph_migrate_addresses_flips_anti_canonical_triples() -> None:
    """Anti-canonical (?prop sci:addresses ?question) triples must flip to canonical
    (?question sci:addresses ?prop) and become visible to question-summary."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                ["graph", "add", "question", "Q1", "--text", "Why?", "--source", "paper:a"],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                ["graph", "add", "proposition", "Because.", "--source", "paper:a", "--id", "p1"],
            ).exit_code
            == 0
        )

        # Write the edge in the anti-canonical direction by going straight through
        # the store helper, bypassing the warning-only validation in add_edge.
        from rdflib import Dataset

        from science_tool.graph.store import (
            DEFAULT_GRAPH_PATH,
            PROJECT_NS,
            SCI_NS,
            _graph_uri,
            _save_dataset,
        )

        dataset = Dataset()
        dataset.parse(source=str(DEFAULT_GRAPH_PATH), format="trig")
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))
        prop_uri = PROJECT_NS["proposition/p1"]
        question_uri = PROJECT_NS["question/q1"]
        knowledge.add((prop_uri, SCI_NS.addresses, question_uri))
        _save_dataset(dataset, DEFAULT_GRAPH_PATH)

        # Dry-run reports the flip but does not write.
        dry = runner.invoke(main, ["graph", "migrate-addresses"])
        assert dry.exit_code == 0
        assert "Would flip 1" in dry.output

        # Apply actually rewrites.
        applied = runner.invoke(main, ["graph", "migrate-addresses", "--apply"])
        assert applied.exit_code == 0
        assert "Flipped 1" in applied.output

        # Re-running on already-canonical data is a no-op.
        again = runner.invoke(main, ["graph", "migrate-addresses"])
        assert again.exit_code == 0
        assert "No anti-canonical" in again.output


def test_graph_add_edge_warns_on_reversed_addresses_direction() -> None:
    """The bonus validation should warn (but not fail) on anti-canonical writes."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                ["graph", "add", "question", "Q1", "--text", "Why?", "--source", "paper:a"],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                main,
                ["graph", "add", "proposition", "Because.", "--source", "paper:a", "--id", "p1"],
            ).exit_code
            == 0
        )

        result = runner.invoke(
            main,
            ["graph", "add", "edge", "proposition/p1", "sci:addresses", "question/q1"],
        )
        assert result.exit_code == 0
        assert "direction looks reversed" in result.output


def test_graph_project_summary_rolls_up_research_profile() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("science.yaml").write_text("name: demo\nprofile: research\n", encoding="utf-8")
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "question",
                    "QPROJ",
                    "--text",
                    "Which research path should we prioritize?",
                    "--source",
                    "paper:doi_10_7777_g",
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
                    "Contested project claim",
                    "--source",
                    "paper:doi_10_7777_g",
                    "--id",
                    "project_contested",
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
                    "Literature support for project claim",
                    "--source",
                    "paper:doi_10_7777_g",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "project_support",
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
                    "Negative result for project claim",
                    "--source",
                    "paper:doi_10_8888_h",
                    "--evidence-type",
                    "negative_result",
                    "--id",
                    "project_dispute",
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
                    "Empirically supported project claim",
                    "--source",
                    "paper:doi_10_9999_i",
                    "--id",
                    "project_empirical",
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
                    "Empirical support for project claim",
                    "--source",
                    "paper:doi_10_9999_i",
                    "--evidence-type",
                    "empirical_data_evidence",
                    "--id",
                    "project_empirical_support",
                ],
            ).exit_code
            == 0
        )

        for subject, target, stance in (
            ("proposition/project_support", "proposition/project_contested", "supports"),
            ("proposition/project_dispute", "proposition/project_contested", "disputes"),
            ("proposition/project_empirical_support", "proposition/project_empirical", "supports"),
        ):
            assert runner.invoke(main, ["graph", "add", "evidence", subject, target, "--stance", stance]).exit_code == 0

        for prop_ref in ("proposition/project_contested", "proposition/project_empirical"):
            assert (
                runner.invoke(main, ["graph", "add", "edge", "question/qproj", "sci:addresses", prop_ref]).exit_code
                == 0
            )

        assert (
            runner.invoke(
                main,
                [
                    "inquiry",
                    "init",
                    "project-inquiry",
                    "--label",
                    "Project Inquiry",
                    "--target",
                    "question:qproj",
                    "--path",
                    "knowledge/graph.trig",
                ],
            ).exit_code
            == 0
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
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "hypothesis",
                    "HREL",
                    "--text",
                    "Hypothesis related to the question",
                    "--source",
                    "paper:doi_10_6666_f",
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
                    "question",
                    "QREL",
                    "--text",
                    "Question linked to a related hypothesis",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--related",
                    "hypothesis:hrel",
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
                    "Claim linked to related hypothesis only",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--id",
                    "related_hypothesis_claim",
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
                    "Literature support for related hypothesis claim",
                    "--source",
                    "paper:doi_10_6666_f",
                    "--evidence-type",
                    "literature_evidence",
                    "--id",
                    "related_hypothesis_support",
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
                    "proposition/related_hypothesis_support",
                    "proposition/related_hypothesis_claim",
                    "--stance",
                    "supports",
                ],
            ).exit_code
            == 0
        )
        # Link proposition to hypothesis so it's found via _linked_claims_for_hypothesis
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "edge",
                    "proposition/related_hypothesis_claim",
                    "cito:discusses",
                    "hypothesis/hrel",
                ],
            ).exit_code
            == 0
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


def test_cito_prefix_resolves_in_relation_claim() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        proposition = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "proposition c1 supports hypothesis h1",
                "--source",
                "paper:doi_10_1234_example",
                "--subject",
                "proposition/c1",
                "--predicate",
                "cito:supports",
                "--object",
                "hypothesis/h1",
            ],
        )
        assert proposition.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        prop_uri = next(knowledge.subjects(RDF.type, SCI.Proposition))
        cito_supports = Namespace("http://purl.org/spar/cito/")["supports"]
        assert (prop_uri, SCI.propPredicate, cito_supports) in knowledge


def test_dcterms_prefix_resolves_in_add_edge() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "dcterms:identifier",
                "concept/ncbigene_672",
                "--graph",
                "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        dcterms_id = Namespace("http://purl.org/dc/terms/")["identifier"]
        assert (PROJECT_NS["concept/brca1"], dcterms_id, PROJECT_NS["concept/ncbigene_672"]) in knowledge


def test_graph_add_concept_with_note_writes_skos_note() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(main, ["graph", "add", "concept", "DNABERT-2", "--note", "12 layers; max context 2048 nt"])
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        notes = list(knowledge.objects(concept_uri, SKOS.note))
        assert len(notes) == 1
        assert str(notes[0]) == "12 layers; max context 2048 nt"


def test_graph_add_concept_with_definition_writes_skos_definition() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "concept",
                "Epistasis",
                "--definition",
                "Nonadditive interactions between genetic variants",
            ],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/epistasis"]
        defs = list(knowledge.objects(concept_uri, SKOS.definition))
        assert len(defs) == 1
        assert "Nonadditive" in str(defs[0])


def test_graph_add_concept_with_property_bare_key_uses_sci_namespace() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "concept",
                "DNABERT-2",
                "--property",
                "hasArchitecture",
                "BERT encoder",
                "--property",
                "hasParameters",
                "117M",
            ],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        assert (concept_uri, SCI["hasArchitecture"], None) in knowledge
        assert (concept_uri, SCI["hasParameters"], None) in knowledge
        arch_vals = [str(o) for o in knowledge.objects(concept_uri, SCI["hasArchitecture"])]
        assert "BERT encoder" in arch_vals


def test_graph_add_concept_with_property_curie_key_resolves_namespace() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(
            main,
            ["graph", "add", "concept", "DNABERT-2", "--property", "schema:description", "A DNA foundation model"],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        assert (concept_uri, SCHEMA["description"], None) in knowledge


def test_graph_add_concept_with_status_writes_project_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(main, ["graph", "add", "concept", "DNABERT-2", "--status", "selected-primary"])
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        statuses = [str(o) for o in knowledge.objects(concept_uri, SCI["projectStatus"])]
        assert "selected-primary" in statuses


def test_graph_add_concept_with_source_writes_provenance() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(main, ["graph", "add", "concept", "DNABERT-2", "--source", "paper:doi_10_1234_test"])
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        sources = list(provenance.objects(concept_uri, PROV.wasDerivedFrom))
        assert len(sources) == 1
        assert str(sources[0]).endswith("doi_10_1234_test")


def test_graph_add_hypothesis_with_status_writes_project_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "hypothesis",
                "H1",
                "--text",
                "Test hypothesis",
                "--source",
                "paper:doi_10_1111_a",
                "--status",
                "active",
            ],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        hyp_uri = PROJECT_NS["hypothesis/h1"]
        statuses = [str(o) for o in knowledge.objects(hyp_uri, SCI["projectStatus"])]
        assert "active" in statuses


def test_graph_add_question_creates_entity_with_provenance() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "question",
                "Q01",
                "--text",
                "Which tokenization strategy best preserves biological signals?",
                "--source",
                "paper:doi_10_1111_a",
            ],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        q_uri = PROJECT_NS["question/q01"]
        assert (q_uri, RDF.type, SCI["Question"]) in knowledge
        assert (q_uri, SCHEMA["text"], None) in knowledge
        assert (q_uri, SCHEMA["identifier"], None) in knowledge
        assert any(provenance.triples((q_uri, PROV.wasDerivedFrom, None)))
        # Default maturity is "open"
        maturity_vals = [str(o) for o in knowledge.objects(q_uri, SCI["maturity"])]
        assert "open" in maturity_vals


def test_graph_add_question_with_maturity_and_related_hypothesis() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert (
            runner.invoke(
                main,
                ["graph", "add", "hypothesis", "H1", "--text", "Test hyp", "--source", "paper:doi_10_1111_a"],
            ).exit_code
            == 0
        )
        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "question",
                "Q05",
                "--text",
                "How should models be selected?",
                "--source",
                "paper:doi_10_2222_b",
                "--maturity",
                "partially-resolved",
                "--related",
                "hypothesis/h1",
            ],
        )
        assert add.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        q_uri = PROJECT_NS["question/q05"]
        maturity_vals = [str(o) for o in knowledge.objects(q_uri, SCI["maturity"])]
        assert "partially-resolved" in maturity_vals
        related = [str(o) for o in knowledge.objects(q_uri, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related)


def test_graph_add_question_with_generic_related() -> None:
    """graph add question --related should accept any entity reference, not just hypotheses."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add a hypothesis entity first
        assert (
            runner.invoke(
                main, ["graph", "add", "hypothesis", "H1", "--text", "Test", "--source", "paper:doi_10_1111_a"]
            ).exit_code
            == 0
        )

        add = runner.invoke(
            main,
            [
                "graph",
                "add",
                "question",
                "Q10",
                "--text",
                "How does X relate to Y?",
                "--source",
                "paper:doi_10_2222_b",
                "--related",
                "hypothesis/h1",
            ],
        )
        assert add.exit_code == 0, add.output

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        q_uri = PROJECT_NS["question/q10"]
        related = [str(o) for o in knowledge.objects(q_uri, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related)


def test_graph_stamp_revision_updates_revision_metadata() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "notes.md").write_text("some notes", encoding="utf-8")

        result = runner.invoke(main, ["graph", "stamp-revision"])
        assert result.exit_code == 0
        assert "revision" in result.output.lower()

        # Verify the revision metadata was written by checking diff sees no stale files
        diff = runner.invoke(main, ["graph", "diff", "--mode", "hybrid", "--format", "json"])
        assert diff.exit_code == 0
        payload = json.loads(diff.output)
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


def test_graph_add_edge_slugifies_bare_terms() -> None:
    """Bare terms (no prefix, no URL) should be auto-slugified in edge subjects/objects."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add concept first so it exists
        assert runner.invoke(main, ["graph", "add", "concept", "Nucleotide Transformer v2"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/nucleotide_transformer_v2",
                "skos:broader",
                "Some New Thing",
                "--graph",
                "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        # The bare term "Some New Thing" should resolve to slugified URI
        assert (
            PROJECT_NS["concept/nucleotide_transformer_v2"],
            Namespace("http://www.w3.org/2004/02/skos/core#")["broader"],
            PROJECT_NS["some_new_thing"],
        ) in knowledge


def test_graph_add_edge_warns_on_nonexistent_entity() -> None:
    """Adding an edge referencing a non-existent entity should emit a warning to stderr."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        # First add a concept so one side exists
        assert runner.invoke(main, ["graph", "add", "concept", "BRCA1"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph",
                "add",
                "edge",
                "concept/brca1",
                "skos:broader",
                "concept/nonexistent",
                "--graph",
                "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0
        # The warning is written to stderr via click.echo(err=True),
        # but CliRunner mixes stderr into output by default
        assert "Warning" in edge.output
        assert "not yet in the graph" in edge.output


def test_graph_add_edge_echoes_resolved_uris() -> None:
    """The CLI should echo resolved URIs, not raw input strings."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(main, ["graph", "add", "concept", "BRCA1"]).exit_code == 0

        edge = runner.invoke(
            main,
            ["graph", "add", "edge", "concept/brca1", "skos:broader", "concept/tp53", "--graph", "graph/knowledge"],
        )
        assert edge.exit_code == 0
        # Output should show resolved short forms, not raw input
        assert "concept/brca1" in edge.output
        assert "skos:broader" in edge.output


def test_graph_question_summary_returns_all_rows_by_default() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        for i in range(30):
            question_ref = f"question/q{i:02d}"
            proposition_ref = f"proposition/q{i:02d}"
            assert (
                runner.invoke(
                    main,
                    [
                        "graph",
                        "add",
                        "question",
                        f"Q{i:02d}",
                        "--text",
                        f"Question {i}",
                        "--source",
                        "paper:doi_10_5555_all",
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
                        f"Claim {i}",
                        "--source",
                        "paper:doi_10_5555_all",
                        "--id",
                        f"q{i:02d}",
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
                        question_ref,
                        "sci:addresses",
                        proposition_ref,
                    ],
                ).exit_code
                == 0
            )

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 30

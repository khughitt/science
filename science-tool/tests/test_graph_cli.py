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
        assert "viz" in result.output.lower()
        assert "uv run marimo edit" in result.output

        pyproject_path = Path("code/notebooks/pyproject.toml")
        assert pyproject_path.exists()
        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        assert "marimo" in pyproject_content
        assert "rdflib" in pyproject_content


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


def test_graph_add_paper_claim_hypothesis_records_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0

        paper = runner.invoke(main, ["graph", "add", "paper", "--doi", "10.1038/s41586-023-06957-x"])
        assert paper.exit_code == 0

        claim = runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
                "BRCA1 is associated with treatment resistance",
                "--source",
                "paper:doi_10_1038_s41586_023_06957_x",
                "--confidence",
                "0.8",
            ],
        )
        assert claim.exit_code == 0

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

        paper_uri = PROJECT_NS["paper/doi_10_1038_s41586_023_06957_x"]
        hypothesis_uri = PROJECT_NS["hypothesis/h3"]

        assert (paper_uri, RDF.type, SCI.Paper) in knowledge
        assert (paper_uri, SCHEMA.identifier, None) in knowledge
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

        relation_claim = runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "concept/brca1",
                "cito:supports",
                "hypothesis/h3",
                "--source",
                "paper:doi_10_1038_s41586_023_06957_x",
                "--confidence",
                "0.8",
                "--id",
                "RC1",
            ],
        )
        assert relation_claim.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        claim_uri = PROJECT_NS["relation_claim/rc1"]

        assert (claim_uri, RDF.type, SCI.Claim) in knowledge
        assert (claim_uri, RDF.type, SCI.RelationClaim) in knowledge
        assert (claim_uri, SCI.claimSubject, PROJECT_NS["concept/brca1"]) in knowledge
        assert (claim_uri, SCI.claimPredicate, Namespace("http://purl.org/spar/cito/").supports) in knowledge
        assert (claim_uri, SCI.claimObject, PROJECT_NS["hypothesis/h3"]) in knowledge
        assert (PROJECT_NS["concept/brca1"], Namespace("http://purl.org/spar/cito/").supports, PROJECT_NS["hypothesis/h3"]) not in knowledge
        assert (claim_uri, SCHEMA.text, Literal("brca1 supports h3")) in knowledge
        assert (claim_uri, PROV.wasDerivedFrom, PROJECT_NS["paper/doi_10_1038_s41586_023_06957_x"]) in provenance
        assert any(pred == SCI.confidence for _, pred, _ in provenance.triples((claim_uri, None, None)))


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
        assert "relation-claim" in edge.output


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
                    "claim",
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
                    "claim",
                    "Same claim text",
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
                    "claim",
                    "Same claim text",
                    "--source",
                    "paper:doi_10_2222_b",
                ],
            ).exit_code
            == 0
        )

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

        claim_entities = {str(subj) for subj, _, _ in knowledge.triples((None, RDF.type, SCI.Claim))}
        assert len(claim_entities) == 2


def test_graph_add_claim_supports_explicit_id() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        claim = runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
                "Claim with explicit ID",
                "--source",
                "paper:doi_10_3333_c",
                "--id",
                "C42",
            ],
        )
        assert claim.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        assert (PROJECT_NS["claim/c42"], RDF.type, SCI.Claim) in knowledge


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
                    "claim",
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
                    "claim",
                    "Unrelated metabolism claim",
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
        assert not any("Unrelated metabolism claim" in row["text"] for row in payload["rows"])


def _setup_evidence_graph(runner: CliRunner) -> None:
    """Helper: init graph, add hypothesis H3, add supporting and disputing claims."""
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
    # Add claim entities and link them with relation claims
    assert (
        runner.invoke(
            main,
            [
                "graph",
                "add",
                "claim",
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
                "relation-claim",
                "claim/ev1",
                "cito:supports",
                "hypothesis/h3",
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
                "claim",
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
                "relation-claim",
                "claim/ev2",
                "cito:disputes",
                "hypothesis/h3",
                "--source",
                "paper:doi_10_2222_b",
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
                "claim",
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
                "relation-claim",
                "claim/ev3",
                "cito:discusses",
                "claim/main",
                "--source",
                "paper:doi_10_3333_c",
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
                "claim",
                "Primary BRCA1 resistance claim",
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
                "relation-claim",
                "claim/main",
                "cito:discusses",
                "hypothesis/h3",
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
                "claim",
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
                "relation-claim",
                "claim/ev1",
                "cito:supports",
                "claim/main",
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
                "claim",
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
                "relation-claim",
                "claim/ev2",
                "cito:disputes",
                "claim/main",
                "--source",
                "paper:doi_10_2222_b",
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

        result = runner.invoke(main, ["graph", "evidence", "claim/main", "--format", "json"])
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
                    "relation-claim",
                    "concept/brca1",
                    "sci:relatedTo",
                    "hypothesis/h3",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--id",
                    "rc1",
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
                    "claim",
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
                    "relation-claim",
                    "claim/ev1",
                    "cito:supports",
                    "relation_claim/rc1",
                    "--source",
                    "paper:doi_10_1111_a",
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
        # Add a low-confidence claim
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "claim",
                    "Weak association between X and Y",
                    "--source",
                    "paper:doi_10_1111_a",
                    "--confidence",
                    "0.3",
                ],
            ).exit_code
            == 0
        )
        # Add a normal-confidence claim (should NOT appear)
        assert (
            runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "claim",
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
                    "claim",
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
                    "claim",
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
                    "relation-claim",
                    "claim/ev1",
                    "cito:supports",
                    "claim/main",
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
                    "claim",
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
                    "relation-claim",
                    "claim/ev2",
                    "cito:disputes",
                    "claim/main",
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
                    "claim",
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
                    "claim",
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
                    "relation-claim",
                    "claim/ev3",
                    "cito:supports",
                    "claim/single",
                    "--source",
                    "paper:doi_10_3333_c",
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
                    "claim",
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
                    "claim",
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
        provenance.add((PROJECT_NS["claim/c_disputed"], SCI.epistemicStatus, RdfLiteral("disputed")))
        dataset.serialize(destination="knowledge/graph.trig", format="trig")

        result = runner.invoke(main, ["graph", "uncertainty", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert any("Disputed" in row["text"] for row in payload["rows"])


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
        relation_claim = runner.invoke(
            main,
            [
                "graph",
                "add",
                "relation-claim",
                "claim/c1",
                "cito:supports",
                "hypothesis/h1",
                "--source",
                "paper:doi_10_1234_example",
            ],
        )
        assert relation_claim.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        claim_uri = next(knowledge.subjects(RDF.type, SCI.RelationClaim))
        cito_supports = Namespace("http://purl.org/spar/cito/")["supports"]
        assert (claim_uri, SCI.claimPredicate, cito_supports) in knowledge


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
                "--related-hypothesis",
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
    assert predicate_rows["cito:supports"]["layer"] == "relation-claim"
    assert predicate_rows["cito:disputes"]["layer"] == "relation-claim"


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

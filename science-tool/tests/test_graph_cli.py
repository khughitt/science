from pathlib import Path
import json
import os
from unittest.mock import patch

from click.testing import CliRunner
from rdflib import Dataset
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
                "sci:relatedTo",
                "concept/tp53",
                "--graph",
                "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        assert (PROJECT_NS["concept/brca1"], SCI.relatedTo, PROJECT_NS["concept/tp53"]) in knowledge


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
                    "sci:relatedTo",
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
        assert "relatedTo" in viz.output


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
                    "sci:relatedTo",
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
        assert any(row["predicate"].endswith("relatedTo") for row in payload["rows"])


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
    """Helper: init graph, add hypothesis H3, add supporting and refuting evidence."""
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
    # Add evidence entities and link them
    assert (
        runner.invoke(
            main,
            ["graph", "add", "edge", "evidence/ev1", "rdf:type", "sci:Evidence", "--graph", "graph/knowledge"],
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
                "evidence/ev1",
                "schema:text",
                "http://example.org/project/lit_supports_BRCA1",
                "--graph",
                "graph/knowledge",
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            main,
            ["graph", "add", "edge", "evidence/ev1", "sci:supports", "hypothesis/h3", "--graph", "graph/knowledge"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            main,
            ["graph", "add", "edge", "evidence/ev2", "rdf:type", "sci:Evidence", "--graph", "graph/knowledge"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            main,
            ["graph", "add", "edge", "evidence/ev2", "sci:refutes", "hypothesis/h3", "--graph", "graph/knowledge"],
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
        assert relations == {"supports", "refutes"}


def test_graph_evidence_returns_empty_for_unknown_hypothesis() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _setup_evidence_graph(runner)

        result = runner.invoke(main, ["graph", "evidence", "hypothesis/h999", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 0


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
                    "sci:relatedTo",
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


def test_cito_prefix_resolves_in_add_edge() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        edge = runner.invoke(
            main,
            ["graph", "add", "edge", "claim/c1", "cito:supports", "hypothesis/h1", "--graph", "graph/knowledge"],
        )
        assert edge.exit_code == 0
        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        cito_supports = Namespace("http://purl.org/spar/cito/")["supports"]
        assert (PROJECT_NS["claim/c1"], cito_supports, PROJECT_NS["hypothesis/h1"]) in knowledge


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

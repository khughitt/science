"""End-to-end test for the inquiry workflow.

Inquiry graphs are produced by the pure compiler (the path that replaced the
retired ``inquiry add-*`` mutators); these tests build the inquiry through the
``build_inquiry_graph`` conftest helper and exercise the reader CLI (list / show
/ validate) against it.
"""

from pathlib import Path

from click.testing import CliRunner
from conftest import build_inquiry_graph

from science_tool.cli import main


def test_full_inquiry_lifecycle(tmp_path: Path) -> None:
    """Test compile -> list -> show -> validate lifecycle via the reader CLI."""
    runner = CliRunner()
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    graph_file = knowledge / "graph.trig"
    graph_path = str(graph_file)

    # 1. Init graph
    result = runner.invoke(main, ["graph", "init", "--path", graph_path])
    assert result.exit_code == 0, f"graph init failed: {result.output}"

    # 2. Add a hypothesis as target
    result = runner.invoke(
        main,
        [
            "graph",
            "add",
            "hypothesis",
            "H01",
            "--text",
            "SP embeddings occupy distinct geometric regions",
            "--source",
            "paper:doi_test",
            "--path",
            graph_path,
        ],
    )
    assert result.exit_code == 0, f"add hypothesis failed: {result.output}"

    # 3. Add concepts
    for concept in ["uniprot_sps", "esm2_model", "sp_embeddings", "distance_matrix", "t1_comparison"]:
        result = runner.invoke(main, ["graph", "add", "concept", concept, "--path", graph_path])
        assert result.exit_code == 0, f"add concept {concept} failed: {result.output}"

    # 4. Compile the inquiry (boundaries + data flow edges) via the compile path.
    build_inquiry_graph(
        graph_file,
        slug="sp_geometry",
        title="Signal peptide embedding geometry",
        focal="hypothesis:h01",
        boundary_roles=[
            {"ref": "concept:uniprot_sps", "role": "BoundaryIn"},
            {"ref": "concept:esm2_model", "role": "BoundaryIn"},
            {"ref": "concept:distance_matrix", "role": "BoundaryOut"},
            {"ref": "concept:t1_comparison", "role": "BoundaryOut"},
        ],
        flow_edges=[
            {"subject": "concept:uniprot_sps", "predicate": "feedsInto", "object": "concept:sp_embeddings"},
            {"subject": "concept:esm2_model", "predicate": "feedsInto", "object": "concept:sp_embeddings"},
            {"subject": "concept:sp_embeddings", "predicate": "feedsInto", "object": "concept:distance_matrix"},
            {"subject": "concept:sp_embeddings", "predicate": "feedsInto", "object": "concept:t1_comparison"},
        ],
    )

    # 5. List inquiries
    result = runner.invoke(main, ["inquiry", "list", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "sp_geometry" in result.output

    # 6. Show inquiry
    result = runner.invoke(main, ["inquiry", "show", "sp_geometry", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "Signal peptide" in result.output
    assert "boundary_in" in result.output
    assert "boundary_out" in result.output

    # 7. Validate — should pass
    result = runner.invoke(
        main,
        [
            "inquiry",
            "validate",
            "sp_geometry",
            "--path",
            graph_path,
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, f"validate failed: {result.output}"


def test_inquiry_validation_catches_unreachable(tmp_path: Path) -> None:
    """Validate catches unreachable BoundaryOut nodes."""
    runner = CliRunner()
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    graph_file = knowledge / "graph.trig"
    graph_path = str(graph_file)

    runner.invoke(main, ["graph", "init", "--path", graph_path])
    runner.invoke(
        main,
        ["graph", "add", "hypothesis", "H01", "--text", "Test", "--source", "paper:doi_test", "--path", graph_path],
    )

    for c in ["input_data", "output_a", "output_b"]:
        runner.invoke(main, ["graph", "add", "concept", c, "--path", graph_path])

    # output_b has no incoming flow edge -> unreachable BoundaryOut.
    build_inquiry_graph(
        graph_file,
        slug="broken",
        title="Broken",
        focal="hypothesis:h01",
        boundary_roles=[
            {"ref": "concept:input_data", "role": "BoundaryIn"},
            {"ref": "concept:output_a", "role": "BoundaryOut"},
            {"ref": "concept:output_b", "role": "BoundaryOut"},
        ],
        flow_edges=[{"subject": "concept:input_data", "predicate": "feedsInto", "object": "concept:output_a"}],
    )

    result = runner.invoke(main, ["inquiry", "validate", "broken", "--path", graph_path, "--format", "json"])
    # Should exit non-zero due to unreachable boundary, and report the failure.
    assert result.exit_code != 0
    assert "fail" in result.output

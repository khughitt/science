"""End-to-end test for the inquiry workflow."""

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def test_full_inquiry_lifecycle(tmp_path: Path) -> None:
    """Test sketch -> specify -> validate lifecycle via CLI."""
    runner = CliRunner()
    graph_path = str(tmp_path / "knowledge" / "graph.trig")
    (tmp_path / "knowledge").mkdir()

    # 1. Init graph
    result = runner.invoke(main, ["graph", "init", "--path", graph_path])
    assert result.exit_code == 0, f"graph init failed: {result.output}"

    # 2. Add a hypothesis as target
    result = runner.invoke(main, [
        "graph", "add", "hypothesis", "H01",
        "--text", "SP embeddings occupy distinct geometric regions",
        "--source", "paper:doi_test",
        "--path", graph_path,
    ])
    assert result.exit_code == 0, f"add hypothesis failed: {result.output}"

    # 3. Create inquiry (sketch)
    result = runner.invoke(main, [
        "inquiry", "init", "sp-geometry",
        "--label", "Signal peptide embedding geometry",
        "--target", "hypothesis:h01",
        "--description", "Test whether SP embeddings form distinct clusters",
        "--path", graph_path,
    ])
    assert result.exit_code == 0, f"inquiry init failed: {result.output}"
    assert "inquiry/sp_geometry" in result.output

    # 4. Add concepts
    for concept in ["uniprot_sps", "esm2_model", "sp_embeddings", "distance_matrix", "t1_comparison"]:
        result = runner.invoke(main, ["graph", "add", "concept", concept, "--path", graph_path])
        assert result.exit_code == 0, f"add concept {concept} failed: {result.output}"

    # 5. Set boundary roles
    for entity, role in [
        ("concept:uniprot_sps", "BoundaryIn"),
        ("concept:esm2_model", "BoundaryIn"),
        ("concept:distance_matrix", "BoundaryOut"),
        ("concept:t1_comparison", "BoundaryOut"),
    ]:
        result = runner.invoke(main, [
            "inquiry", "add-node", "sp-geometry", entity, "--role", role, "--path", graph_path,
        ])
        assert result.exit_code == 0, f"add-node {entity} {role} failed: {result.output}"

    # 6. Add data flow edges
    edges = [
        ("concept:uniprot_sps", "sci:feedsInto", "concept:sp_embeddings"),
        ("concept:esm2_model", "sci:feedsInto", "concept:sp_embeddings"),
        ("concept:sp_embeddings", "sci:feedsInto", "concept:distance_matrix"),
        ("concept:sp_embeddings", "sci:feedsInto", "concept:t1_comparison"),
    ]
    for s, p, o in edges:
        result = runner.invoke(main, [
            "inquiry", "add-edge", "sp-geometry", s, p, o, "--path", graph_path,
        ])
        assert result.exit_code == 0, f"add-edge {s}->{o} failed: {result.output}"

    # 7. List inquiries
    result = runner.invoke(main, ["inquiry", "list", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "sp_geometry" in result.output

    # 8. Show inquiry
    result = runner.invoke(main, ["inquiry", "show", "sp-geometry", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "Signal peptide" in result.output
    assert "boundary_in" in result.output
    assert "boundary_out" in result.output

    # 9. Validate — should pass
    result = runner.invoke(main, [
        "inquiry", "validate", "sp-geometry", "--path", graph_path, "--format", "json",
    ])
    assert result.exit_code == 0, f"validate failed: {result.output}"


def test_inquiry_validation_catches_unreachable(tmp_path: Path) -> None:
    """Validate catches unreachable BoundaryOut nodes."""
    runner = CliRunner()
    graph_path = str(tmp_path / "knowledge" / "graph.trig")
    (tmp_path / "knowledge").mkdir()

    runner.invoke(main, ["graph", "init", "--path", graph_path])
    runner.invoke(main, ["graph", "add", "hypothesis", "H01", "--text", "Test", "--source", "paper:doi_test", "--path", graph_path])
    runner.invoke(main, ["inquiry", "init", "broken", "--label", "Broken", "--target", "hypothesis:h01", "--path", graph_path])

    # Add concepts
    for c in ["input_data", "output_a", "output_b"]:
        runner.invoke(main, ["graph", "add", "concept", c, "--path", graph_path])

    # Set boundaries — output_b will be unreachable
    runner.invoke(main, ["inquiry", "add-node", "broken", "concept:input_data", "--role", "BoundaryIn", "--path", graph_path])
    runner.invoke(main, ["inquiry", "add-node", "broken", "concept:output_a", "--role", "BoundaryOut", "--path", graph_path])
    runner.invoke(main, ["inquiry", "add-node", "broken", "concept:output_b", "--role", "BoundaryOut", "--path", graph_path])
    runner.invoke(main, ["inquiry", "add-edge", "broken", "concept:input_data", "sci:feedsInto", "concept:output_a", "--path", graph_path])
    # No edge to output_b!

    result = runner.invoke(main, ["inquiry", "validate", "broken", "--path", graph_path, "--format", "json"])
    # Should exit non-zero due to unreachable boundary
    assert result.exit_code != 0 or "fail" in result.output

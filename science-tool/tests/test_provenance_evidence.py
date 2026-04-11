import pytest
from pathlib import Path
from science_tool.graph.store import add_evidence_edge, add_observation, add_proposition


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Create a minimal graph file with two entities to link."""
    from science_tool.graph.store import init_graph_file
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True, exist_ok=True)
    init_graph_file(gp)
    add_observation(gp, "test observation", data_source="test-pkg", observation_id="obs-1")
    add_proposition(gp, "test proposition", source="test-pkg", proposition_id="prop-1")
    return gp


def test_add_evidence_with_independence(graph_path: Path):
    """Evidence edge with independence annotation stores the value."""
    add_evidence_edge(
        graph_path, "obs-1", "prop-1",
        stance="supports",
        strength="moderate",
        independence="circular",
    )
    # Verify the RDF contains the independence predicate
    from rdflib import Dataset
    ds = Dataset()
    ds.parse(str(graph_path), format="trig")
    independence_values = [
        str(o) for g in ds.graphs() for s, p, o in g.triples((None, None, None))
        if "evidenceIndependence" in str(p)
    ]
    assert "circular" in independence_values


def test_add_evidence_without_independence(graph_path: Path):
    """Evidence edge without independence flag works as before."""
    add_evidence_edge(
        graph_path, "obs-1", "prop-1",
        stance="supports",
    )
    from rdflib import Dataset
    ds = Dataset()
    ds.parse(str(graph_path), format="trig")
    independence_values = [
        str(o) for g in ds.graphs() for s, p, o in g.triples((None, None, None))
        if "evidenceIndependence" in str(p)
    ]
    assert len(independence_values) == 0


def test_add_evidence_invalid_independence(graph_path: Path):
    """Invalid independence value raises ClickException."""
    import click
    with pytest.raises(click.ClickException, match="Independence must be"):
        add_evidence_edge(
            graph_path, "obs-1", "prop-1",
            stance="supports",
            independence="invalid-value",
        )

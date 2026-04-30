from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.cli import main


def _make_child(path: Path, child_id: str, role: str, meta_path: Path, with_graph: bool = True) -> None:
    path.mkdir()
    (path / "science.yaml").write_text(
        f"""
name: {child_id}
id: {child_id}
role: {role}
parent: {meta_path}
profile: research
research_question: "child {child_id}"
""",
        encoding="utf-8",
    )
    if with_graph:
        (path / "knowledge").mkdir()
        ex = rdflib.Namespace("https://example.org/")
        dataset = Dataset()
        dataset.graph(URIRef(f"https://example.org/{child_id}/graph/knowledge")).add(
            (ex[f"{child_id}-claim"], RDF.type, ex.Claim)
        )
        dataset.serialize(destination=path / "knowledge" / "graph.trig", format="trig")


def test_federation_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    b = tmp_path / "b"
    meta.mkdir()
    (meta / "science.yaml").write_text(
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella."
children:
  - id: a
    path: {a}
    role: data-source
  - id: b
    path: {b}
    role: cancer-type
""",
        encoding="utf-8",
    )
    _make_child(a, "a", "data-source", meta)
    _make_child(b, "b", "cancer-type", meta)

    runner = CliRunner()
    monkeypatch.chdir(meta)

    result = runner.invoke(main, ["federation", "validate"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(main, ["graph", "build"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(main, ["federation", "status"])
    assert result.exit_code == 0, result.output
    assert "a" in result.output
    assert "b" in result.output

    dataset = Dataset()
    dataset.parse(meta / "knowledge" / "graph.trig", format="trig")
    graph_names = {
        str(graph.identifier)
        for graph in dataset.graphs()
        if graph.identifier != URIRef("urn:x-rdflib:default")
    }
    assert {"cancer://a", "cancer://b", "cancer://meta"}.issubset(graph_names)

    a_subjects = {str(subject) for subject in dataset.graph(URIRef("cancer://a")).subjects()}
    assert "https://example.org/a-claim" in a_subjects

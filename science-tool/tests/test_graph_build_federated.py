from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.cli import main


def test_graph_build_in_meta_uses_federated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()

    (meta / "science.yaml").write_text(
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
        encoding="utf-8",
    )
    (a / "science.yaml").write_text(
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )

    (a / "knowledge").mkdir()
    ex = rdflib.Namespace("https://example.org/")
    a_ds = Dataset()
    a_ds.graph(URIRef("https://example.org/a/graph/knowledge")).add((ex["a-claim"], RDF.type, ex.Claim))
    a_ds.serialize(destination=a / "knowledge" / "graph.trig", format="trig")

    monkeypatch.chdir(meta)
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build"])
    assert result.exit_code == 0, result.output

    out_ds = Dataset()
    out_ds.parse(meta / "knowledge" / "graph.trig", format="trig")
    graph_names = {
        str(graph.identifier)
        for graph in out_ds.graphs()
        if graph.identifier != URIRef("urn:x-rdflib:default")
    }
    assert "cancer://a" in graph_names
    assert "cancer://meta" in graph_names

    a_graph = out_ds.graph(URIRef("cancer://a"))
    a_subjects = {str(subject) for subject in a_graph.subjects()}
    assert "https://example.org/a-claim" in a_subjects

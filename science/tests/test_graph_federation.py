from pathlib import Path

import pytest
import rdflib
from rdflib import Dataset, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.federation import assemble_federated_graph


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def _write_layered_trig(child_root: Path, child_id: str) -> None:
    """Write a TriG file with multiple named graphs, like real child outputs."""
    knowledge_dir = child_root / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    dataset = Dataset()
    ex = rdflib.Namespace("https://example.org/")
    knowledge = dataset.graph(URIRef(f"https://example.org/{child_id}/graph/knowledge"))
    knowledge.add((ex[f"{child_id}-claim"], RDF.type, ex.Claim))
    bridge = dataset.graph(URIRef(f"https://example.org/{child_id}/graph/bridge"))
    bridge.add((ex[f"{child_id}-link"], RDF.type, ex.Bridge))
    dataset.serialize(destination=knowledge_dir / "graph.trig", format="trig")


def test_assembles_named_graphs_per_child(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    b = tmp_path / "b"
    for directory in (meta, a, b):
        directory.mkdir()

    _write_yaml(
        meta,
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
  - id: b
    path: {b}
    role: cancer-type
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
    )
    _write_yaml(
        b,
        f"""
name: b
id: b
role: cancer-type
parent: {meta}
profile: research
research_question: "..."
""",
    )
    _write_layered_trig(a, "a")
    _write_layered_trig(b, "b")

    out_path = assemble_federated_graph(meta)
    assert out_path.exists()

    dataset = Dataset()
    dataset.parse(out_path, format="trig")
    graph_names = {
        str(graph.identifier) for graph in dataset.graphs() if graph.identifier != URIRef("urn:x-rdflib:default")
    }
    assert "cancer://a" in graph_names
    assert "cancer://b" in graph_names
    assert "cancer://meta" in graph_names

    a_graph = dataset.graph(URIRef("cancer://a"))
    a_subjects = {str(subject) for subject in a_graph.subjects()}
    assert "https://example.org/a-claim" in a_subjects, "knowledge-layer triple missing"
    assert "https://example.org/a-link" in a_subjects, "bridge-layer triple missing"

    meta_graph = dataset.graph(URIRef("cancer://meta"))
    prov_rows = {(str(subject), str(obj)) for subject, _, obj in meta_graph.triples((None, PROV.wasDerivedFrom, None))}
    prov_subjects = {subject for subject, _ in prov_rows}
    assert "cancer://a" in prov_subjects
    assert "cancer://b" in prov_subjects
    assert any(obj.startswith("file://") and obj.endswith("/a/knowledge/graph.trig") for _, obj in prov_rows)


def test_federated_graph_assembly_is_byte_stable_for_identical_inputs(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    child = tmp_path / "child"
    for directory in (meta, child):
        directory.mkdir()

    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: child
    path: {child}
    role: cancer-type
""",
    )
    _write_yaml(
        child,
        f"""
name: child
id: child
role: cancer-type
parent: {meta}
profile: research
research_question: "..."
""",
    )
    _write_layered_trig(child, "child")

    out_path = assemble_federated_graph(meta)
    first = out_path.read_bytes()
    out_path.unlink()

    out_path = assemble_federated_graph(meta)
    second = out_path.read_bytes()

    assert second == first


def test_includes_meta_local_triples(tmp_path: Path) -> None:
    """Meta's own local graph must end up in cancer://meta."""
    meta = tmp_path / "meta"
    meta.mkdir()
    _write_yaml(
        meta,
        """
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella."
children: []
""",
    )
    knowledge_dir = meta / "knowledge"
    knowledge_dir.mkdir()
    pre = Dataset()
    ex = rdflib.Namespace("https://example.org/")
    graph = pre.graph(URIRef("https://example.org/meta/graph/knowledge"))
    graph.add((ex["meta-claim"], RDF.type, ex.UmbrellaClaim))
    pre.serialize(destination=knowledge_dir / "graph.trig", format="trig")

    out_path = assemble_federated_graph(meta)
    dataset = Dataset()
    dataset.parse(out_path, format="trig")
    meta_graph = dataset.graph(URIRef("cancer://meta"))
    meta_subjects = {str(subject) for subject in meta_graph.subjects()}
    assert "https://example.org/meta-claim" in meta_subjects, "meta's own local triple lost"


def test_skips_child_without_graph_trig(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
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
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
    )
    out_path = assemble_federated_graph(meta)
    assert out_path.exists()


def test_refuses_non_meta_root(tmp_path: Path) -> None:
    a = tmp_path / "a"
    a.mkdir()
    _write_yaml(
        a,
        """
name: a
id: a
role: data-source
profile: research
research_question: "..."
""",
    )
    with pytest.raises(ValueError, match="not a meta"):
        assemble_federated_graph(a)

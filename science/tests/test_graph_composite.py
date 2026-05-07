from __future__ import annotations

from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner
from rdflib import Dataset, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.cli import main
from science_tool.graph.composite import assemble_composite_graph
from science_tool.graph.io import read_revision_manifest
from science_tool.peers import PeerUnresolved
from science_tool.registry.config import ensure_registered, load_global_config


def _write_project(root: Path, project_id: str, peers: list[tuple[str, Path]] | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    peer_lines: list[str] = []
    for peer_id, peer_path in peers or []:
        peer_lines.extend(
            [
                f"  - id: {peer_id}",
                f"    path: {peer_path}",
            ]
        )
    peers_yaml = "\n".join(peer_lines)
    if peers_yaml:
        peers_yaml = f"peers:\n{peers_yaml}\n"
    (root / "science.yaml").write_text(
        f"""
name: {project_id}
id: {project_id}
profile: research
research_question: "..."
{peers_yaml}""",
        encoding="utf-8",
    )


def _write_local_graph(root: Path, project_id: str) -> None:
    knowledge_dir = root / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    dataset = Dataset()
    ex = rdflib.Namespace("https://example.org/")
    knowledge = dataset.graph(URIRef(f"https://example.org/{project_id}/graph/knowledge"))
    knowledge.add((ex[f"{project_id}-claim"], RDF.type, ex.Claim))
    bridge = dataset.graph(URIRef(f"https://example.org/{project_id}/graph/bridge"))
    bridge.add((ex[f"{project_id}-bridge"], RDF.type, ex.Bridge))
    dataset.serialize(destination=knowledge_dir / "graph.trig", format="trig")


def _write_composite_only(root: Path, project_id: str) -> None:
    knowledge_dir = root / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    dataset = Dataset()
    ex = rdflib.Namespace("https://example.org/")
    graph = dataset.graph(URIRef(f"https://example.org/{project_id}/graph/composite"))
    graph.add((ex[f"{project_id}-composite-only"], RDF.type, ex.CompositeOnly))
    dataset.serialize(destination=knowledge_dir / "composite.trig", format="trig")


def _load_dataset(path: Path) -> Dataset:
    dataset = Dataset()
    dataset.parse(path, format="trig")
    return dataset


def _subjects(dataset: Dataset, graph_id: str) -> set[str]:
    return {str(subject) for subject in dataset.graph(URIRef(graph_id)).subjects()}


def test_composite_unions_peers_local_graphs(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer_a = tmp_path / "peer-a"
    peer_b = tmp_path / "peer-b"
    _write_project(host, "host", [("peer-a", peer_a), ("peer-b", peer_b)])
    _write_project(peer_a, "peer-a")
    _write_project(peer_b, "peer-b")
    for root, project_id in ((host, "host"), (peer_a, "peer-a"), (peer_b, "peer-b")):
        _write_local_graph(root, project_id)

    out_path = assemble_composite_graph(host)

    assert out_path == host / "knowledge" / "composite.trig"
    assert out_path.exists()
    dataset = _load_dataset(out_path)
    assert "https://example.org/host-claim" in _subjects(dataset, "cancer://host")
    assert "https://example.org/peer-a-claim" in _subjects(dataset, "cancer://peer-a")
    assert "https://example.org/peer-b-claim" in _subjects(dataset, "cancer://peer-b")

    host_graph = dataset.graph(URIRef("cancer://host"))
    derived_from = {
        (str(subject), str(obj)) for subject, _, obj in host_graph.triples((None, PROV.wasDerivedFrom, None))
    }
    assert any(subject == "cancer://peer-a" for subject, _ in derived_from)
    assert any(subject == "cancer://peer-b" for subject, _ in derived_from)
    assert all(obj.endswith("/knowledge/graph.trig") for _, obj in derived_from)


def test_composite_skips_peer_with_no_local_graph(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    _write_project(host, "host", [("peer", peer)])
    _write_project(peer, "peer")
    _write_local_graph(host, "host")
    _write_composite_only(peer, "peer")

    out_path = assemble_composite_graph(host)

    dataset = _load_dataset(out_path)
    all_subjects = {str(subject) for graph in dataset.graphs() for subject in graph.subjects()}
    assert "https://example.org/host-claim" in all_subjects
    assert "https://example.org/peer-composite-only" not in all_subjects
    assert "cancer://peer" not in {
        str(graph.identifier) for graph in dataset.graphs() if graph.identifier != dataset.default_graph.identifier
    }


def test_composite_never_reads_peer_composite_trig(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    _write_project(host, "host", [("peer", peer)])
    _write_project(peer, "peer")
    _write_local_graph(host, "host")
    _write_local_graph(peer, "peer")
    sentinel = "https://example.org/peer-composite-only"
    (peer / "knowledge" / "composite.trig").write_text(f"<{sentinel}> not valid trig\n", encoding="utf-8")

    out_path = assemble_composite_graph(host)

    dataset = _load_dataset(out_path)
    all_subjects = {str(subject) for graph in dataset.graphs() for subject in graph.subjects()}
    assert "https://example.org/host-claim" in _subjects(dataset, "cancer://host")
    assert "https://example.org/peer-claim" in _subjects(dataset, "cancer://peer")
    assert sentinel not in all_subjects


def test_composite_propagates_missing_peer_path(tmp_path: Path) -> None:
    host = tmp_path / "host"
    missing_peer = tmp_path / "missing-peer"
    _write_project(host, "host", [("missing-peer", missing_peer)])
    _write_local_graph(host, "host")

    with pytest.raises(PeerUnresolved, match="missing-peer"):
        assemble_composite_graph(host)

    assert not (host / "knowledge" / "composite.trig").exists()


def test_composite_rejects_peer_id_mismatch(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    _write_project(host, "host", [("declared-peer", peer)])
    _write_project(peer, "actual-peer")
    _write_local_graph(host, "host")
    _write_local_graph(peer, "actual-peer")

    with pytest.raises(ValueError, match="declared-peer.*actual-peer"):
        assemble_composite_graph(host)

    assert not (host / "knowledge" / "composite.trig").exists()


def test_composite_no_peers_writes_only_local(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write_project(host, "host")
    _write_local_graph(host, "host")

    out_path = assemble_composite_graph(host)

    assert out_path == host / "knowledge" / "composite.trig"
    assert out_path.exists()
    dataset = _load_dataset(out_path)
    graph_names = {
        str(graph.identifier) for graph in dataset.graphs() if graph.identifier != dataset.default_graph.identifier
    }
    assert "cancer://host" in graph_names
    assert "https://example.org/host-claim" in _subjects(dataset, "cancer://host")
    assert all(not graph_name.startswith("cancer://peer") for graph_name in graph_names)


def test_composite_revision_manifest_uses_project_root(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write_project(host, "host")
    _write_local_graph(host, "host")

    out_path = assemble_composite_graph(host)

    dataset = _load_dataset(out_path)
    manifest = read_revision_manifest(dataset)
    assert "science.yaml" in manifest


def test_composite_graph_assembly_is_byte_stable_for_identical_inputs(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    _write_project(host, "host", [("peer", peer)])
    _write_project(peer, "peer")
    _write_local_graph(host, "host")
    _write_local_graph(peer, "peer")

    out_path = assemble_composite_graph(host)
    first = out_path.read_bytes()

    out_path = assemble_composite_graph(host)
    second = out_path.read_bytes()

    assert second == first


def test_composite_bidirectional_peering_does_not_recurse(tmp_path: Path) -> None:
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    _write_project(project_a, "a", [("b", project_b)])
    _write_project(project_b, "b", [("a", project_a)])
    _write_local_graph(project_a, "a")
    _write_local_graph(project_b, "b")

    out_a = assemble_composite_graph(project_a)
    out_b = assemble_composite_graph(project_b)

    dataset_a = _load_dataset(out_a)
    dataset_b = _load_dataset(out_b)
    assert "https://example.org/a-claim" in _subjects(dataset_a, "cancer://a")
    assert "https://example.org/b-claim" in _subjects(dataset_a, "cancer://b")
    assert "https://example.org/b-claim" in _subjects(dataset_b, "cancer://b")
    assert "https://example.org/a-claim" in _subjects(dataset_b, "cancer://a")


def test_graph_build_writes_composite_when_peers_present(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    _write_project(host, "host", [("peer", peer)])
    _write_project(peer, "peer")
    _write_local_graph(peer, "peer")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code == 0, result.output
    assert (host / "knowledge" / "graph.trig").is_file()
    assert (host / "knowledge" / "composite.trig").is_file()


def test_graph_build_no_peers_no_composite(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write_project(host, "host")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code == 0, result.output
    assert (host / "knowledge" / "graph.trig").is_file()
    assert not (host / "knowledge" / "composite.trig").exists()


def test_graph_build_clears_stale_registry_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))
    host = tmp_path / "host"
    _write_project(host, "host")
    ensure_registered(host, "host", project_id="host", role="standalone", parent="legacy-parent")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code == 0, result.output
    cfg = load_global_config()
    entry = next(project for project in cfg.projects if project.path == str(host.resolve()))
    assert entry.parent is None


def test_graph_build_no_peers_removes_stale_composite(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write_project(host, "host")
    _write_composite_only(host, "host")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code == 0, result.output
    assert (host / "knowledge" / "graph.trig").is_file()
    assert not (host / "knowledge" / "composite.trig").exists()


def test_graph_build_no_config_removes_stale_composite(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_composite_only(host, "host")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code == 0, result.output
    assert (host / "knowledge" / "graph.trig").is_file()
    assert not (host / "knowledge" / "composite.trig").exists()


def test_graph_build_missing_peer_reports_click_error(tmp_path: Path) -> None:
    host = tmp_path / "host"
    missing_peer = tmp_path / "missing-peer"
    _write_project(host, "host", [("missing-peer", missing_peer)])

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "missing-peer" in result.output


def test_graph_build_missing_peer_removes_stale_composite(tmp_path: Path) -> None:
    host = tmp_path / "host"
    missing_peer = tmp_path / "missing-peer"
    _write_project(host, "host", [("missing-peer", missing_peer)])
    _write_composite_only(host, "host")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "missing-peer" in result.output
    assert not (host / "knowledge" / "composite.trig").exists()

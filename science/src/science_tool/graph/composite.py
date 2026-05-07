"""Composite graph assembly.

Composite graph assembly reads ONLY local ``knowledge/graph.trig`` files from
the host project and its declared peers. It never reads another project's
``knowledge/composite.trig``. The assembled graph is written to the host's
``<root>/knowledge/composite.trig``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.graph import Graph
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.io import save_canonical_graph_dataset
from science_tool.peers import ResolvedPeer, make_local_resolver
from science_tool.project_config import load_project_config

_URI_SCHEME = "cancer"


def _project_uri(project_id: str) -> URIRef:
    return URIRef(f"{_URI_SCHEME}://{project_id}")


def assemble_composite_graph(project_root: Path) -> Path:
    """Assemble host plus peer local graph.trig files into composite.trig."""
    cfg = load_project_config(project_root)

    out_dir = project_root / "knowledge"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "composite.trig"

    dataset = Dataset()
    host_uri = _project_uri(cfg.id or project_root.name)
    host_graph = dataset.graph(host_uri)
    _include_local_graph(project_root, host_graph)

    resolver = make_local_resolver(project_root)
    for peer_id in sorted(resolver.known_ids()):
        peer = resolver.resolve(peer_id)
        _validate_peer_id(peer)
        peer_uri = _project_uri(peer.id)
        included = _include_peer_graph(dataset, peer, peer_uri)
        if included:
            peer_graph_path = _local_graph_path(peer.path)
            source_uri = URIRef(peer_graph_path.resolve().as_uri())
            host_graph.add((peer_uri, PROV.wasDerivedFrom, source_uri))
            host_graph.add((source_uri, RDF.type, PROV.Entity))
            host_graph.add((peer_uri, PROV.generatedAtTime, _source_graph_timestamp(peer_graph_path)))

    save_canonical_graph_dataset(dataset, out_path)
    return out_path


def _local_graph_path(project_root: Path) -> Path:
    return project_root / "knowledge" / "graph.trig"


def _validate_peer_id(peer: ResolvedPeer) -> None:
    peer_cfg = load_project_config(peer.path)
    if peer_cfg.id != peer.id:
        raise ValueError(f"declared peer id {peer.id!r} does not match peer project id {peer_cfg.id!r} at {peer.path}")


def _include_local_graph(project_root: Path, dest_graph: Graph) -> bool:
    src_path = _local_graph_path(project_root)
    if not src_path.is_file():
        return False

    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            dest_graph.add(triple)
    return True


def _include_peer_graph(dataset: Dataset, peer: ResolvedPeer, peer_uri: URIRef) -> bool:
    src_path = _local_graph_path(peer.path)
    if not src_path.is_file():
        return False

    target = dataset.graph(peer_uri)
    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            target.add(triple)
    return True


def _source_graph_timestamp(graph_path: Path) -> Literal:
    seconds, nanoseconds = divmod(graph_path.stat().st_mtime_ns, 1_000_000_000)
    timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=nanoseconds // 1000)
    return Literal(timestamp.isoformat().replace("+00:00", "Z"), datatype=XSD.dateTime)

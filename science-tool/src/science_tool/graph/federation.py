"""Federated graph assembly.

Existing per-project graph builds write ``knowledge/graph.trig`` from
``materialize_graph(project_root) -> Path``. The local materializer serializes an
``rdflib.Dataset`` as TriG with named layers from ``GRAPH_LAYERS`` in
``graph/store.py``: ``graph/knowledge``, ``graph/bridge``, ``graph/causal``,
``graph/provenance``, and ``graph/datasets``.

Federation reads each TriG with ``rdflib.Dataset`` and unions all source contexts
into one ``cancer://<project-id>`` named graph per child.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.graph import Graph
from rdflib.namespace import PROV, RDF, XSD

from science_tool.project_config import ChildEntry, ProjectRole, load_project_config, resolve_child_path

_URI_SCHEME = "cancer"


def _project_uri(project_id: str) -> URIRef:
    return URIRef(f"{_URI_SCHEME}://{project_id}")


def assemble_federated_graph(meta_root: Path) -> Path:
    """Assemble meta's federated graph.trig from existing graph files."""
    cfg = load_project_config(meta_root)
    if cfg.role != ProjectRole.META:
        raise ValueError(f"{meta_root} is role={cfg.role!r}; not a meta project")

    out_dir = meta_root / "knowledge"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "graph.trig"

    dataset = Dataset()
    meta_uri = _project_uri(cfg.id or meta_root.name)
    meta_graph = dataset.graph(meta_uri)
    _include_meta_local_graph(meta_root, meta_graph)

    timestamp = Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)
    for child in cfg.children:
        child_uri = _project_uri(child.id)
        included = _include_child_graph(dataset, child, child_uri)
        if included:
            source_uri = URIRef(_child_graph_path(child).resolve().as_uri())
            meta_graph.add((child_uri, PROV.wasDerivedFrom, source_uri))
            meta_graph.add((source_uri, RDF.type, PROV.Entity))
            meta_graph.add((child_uri, PROV.generatedAtTime, timestamp))

    dataset.serialize(destination=out_path, format="trig")
    return out_path


def _include_meta_local_graph(meta_root: Path, dest_graph: Graph) -> None:
    src_path = meta_root / "knowledge" / "graph.trig"
    if not src_path.is_file():
        return

    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            dest_graph.add(triple)


def _child_graph_path(child: ChildEntry) -> Path:
    return resolve_child_path(child) / "knowledge" / "graph.trig"


def _include_child_graph(dataset: Dataset, child: ChildEntry, child_uri: URIRef) -> bool:
    src_path = _child_graph_path(child)
    if not src_path.is_file():
        return False

    target = dataset.graph(child_uri)
    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            target.add(triple)
    return True

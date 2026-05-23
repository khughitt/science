from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.io import (
    build_input_manifest as _build_input_manifest,
    read_revision_manifest as _read_revision_manifest,
)

from .constants import PROJECT_NS, REVISION_URI, SCHEMA_NS
from .dataset import _load_dataset, _save_dataset
from .identity import _graph_uri, _slug


def import_snapshot(graph_path: Path, snapshot_path: Path) -> int:
    """Import a Turtle snapshot into :graph/knowledge and record provenance. Returns triple count."""
    if not snapshot_path.exists():
        raise click.ClickException(f"Snapshot file not found: {snapshot_path}")

    from rdflib import Graph

    snapshot = Graph()
    snapshot.parse(str(snapshot_path), format="turtle")
    imported_count = len(snapshot)

    if imported_count == 0:
        raise click.ClickException(f"Snapshot contains no triples: {snapshot_path}")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    for triple in snapshot:
        knowledge.add(triple)

    # Record import provenance
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    import_uri = URIRef(PROJECT_NS[f"import/{_slug(snapshot_path.stem)}"])
    import_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for triple in list(provenance.triples((import_uri, None, None))):
        provenance.remove(triple)

    provenance.add((import_uri, RDF.type, PROV.Activity))
    provenance.add((import_uri, SCHEMA_NS.name, Literal(f"Import: {snapshot_path.name}")))
    provenance.add((import_uri, PROV.generatedAtTime, Literal(import_time, datatype=XSD.dateTime)))
    provenance.add((import_uri, SCHEMA_NS.size, Literal(imported_count, datatype=XSD.integer)))

    _save_dataset(dataset, graph_path)
    return imported_count


def stamp_revision(graph_path: Path) -> str:
    """Update graph revision metadata without adding entities. Returns the revision timestamp."""
    dataset = _load_dataset(graph_path)
    _save_dataset(dataset, graph_path)

    # Read back the stamped time
    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    time_obj = next(provenance.objects(REVISION_URI, SCHEMA_NS.dateModified), None)
    return str(time_obj) if time_obj else "unknown"

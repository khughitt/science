from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD

SCHEMA_NS = Namespace("https://schema.org/")
SCI_NS = Namespace("http://example.org/science/vocab/")
SNAPSHOT_NS = Namespace("http://example.org/science/snapshots/")

DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


def bind_common_prefixes(g: Graph) -> None:
    """Bind standard prefixes to a graph for clean Turtle output."""
    g.bind("rdf", RDF)
    g.bind("skos", SKOS)
    g.bind("prov", PROV)
    g.bind("schema", SCHEMA_NS)
    g.bind("sci", SCI_NS)
    g.bind("xsd", XSD)


def write_snapshot(
    g: Graph,
    *,
    output_path: Path,
    name: str,
    source_url: str,
    version: str,
    node_count: int,
    triple_count: int,
) -> Path:
    """Serialize graph to Turtle and update manifest.ttl alongside it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_path), format="turtle")

    _update_manifest(
        manifest_path=output_path.parent / "manifest.ttl",
        snapshot_stem=output_path.stem,
        name=name,
        source_url=source_url,
        version=version,
        node_count=node_count,
        triple_count=triple_count,
        snapshot_path=output_path,
    )

    return output_path


def _update_manifest(
    manifest_path: Path,
    snapshot_stem: str,
    name: str,
    source_url: str,
    version: str,
    node_count: int,
    triple_count: int,
    snapshot_path: Path,
) -> None:
    """Write or update a manifest.ttl entry for this snapshot."""
    if manifest_path.exists():
        manifest = Graph()
        manifest.parse(str(manifest_path), format="turtle")
    else:
        manifest = Graph()

    manifest.bind("prov", PROV)
    manifest.bind("schema", SCHEMA_NS)
    manifest.bind("xsd", XSD)
    manifest.bind("", SNAPSHOT_NS)

    entry = URIRef(SNAPSHOT_NS[snapshot_stem])

    # Remove old triples for this entry
    for triple in list(manifest.triples((entry, None, None))):
        manifest.remove(triple)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    file_hash = _sha256_file(snapshot_path)
    size_str = f"{node_count} nodes, {triple_count} triples"

    manifest.add((entry, RDF.type, PROV.Entity))
    manifest.add((entry, RDF.type, SCHEMA_NS.Dataset))
    manifest.add((entry, SCHEMA_NS.name, Literal(name)))
    manifest.add((entry, PROV.generatedAtTime, Literal(now, datatype=XSD.dateTime)))
    manifest.add((entry, PROV.wasDerivedFrom, URIRef(source_url)))
    manifest.add((entry, SCHEMA_NS.version, Literal(version)))
    manifest.add((entry, SCHEMA_NS.size, Literal(size_str)))
    manifest.add((entry, SCHEMA_NS.sha256, Literal(file_hash)))

    manifest.serialize(destination=str(manifest_path), format="turtle")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()

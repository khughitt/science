"""emit_source_snapshots: graph contract + reified bears_on edge (Slice B)."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, Literal
from rdflib.namespace import RDF, XSD

from science_tool.graph.io import entity_uri_for_ref
from science_tool.graph.source_records import SourceChange, SourceSnapshot
from science_tool.graph.source_snapshots import (
    SourceSnapshotEmission,
    SourceSnapshotResult,
    emit_source_snapshots,
    source_change_uri,
    source_snapshot_uri,
)
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS


def _emit(result: SourceSnapshotResult) -> Dataset:
    ds = Dataset()
    emit_source_snapshots(ds, result)
    return ds


def test_unchanged_snapshot_emits_node_and_bears_on_but_no_change():
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="h", latest_change=None)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)

    prov = ds.graph(PROJECT_NS["graph/provenance"])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/h1.md")
    entity = entity_uri_for_ref("hypothesis:h1")

    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    assert (ss, SCI_NS.sourcePath, Literal("entities/h1.md")) in prov
    assert (ss, SCHEMA_NS.sha256, Literal("h")) in prov
    assert (ss, SCI_NS.bearsOn, entity) in knowledge
    # no SourceChange when latest_change is None
    assert prov.value(ss, SCI_NS.latestSourceChange) is None
    assert list(prov.subjects(RDF.type, SCI_NS.SourceChange)) == []


def test_snapshot_bears_on_emits_reified_depth1_edge():
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="h", latest_change=None)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/h1.md")
    entity = entity_uri_for_ref("hypothesis:h1")

    edge_nodes = [
        n
        for n in knowledge.subjects(RDF.type, SCI_NS.BearsOnEdge)
        if (n, SCI_NS.bearsOnSource, ss) in knowledge and (n, SCI_NS.bearsOnTarget, entity) in knowledge
    ]
    assert len(edge_nodes) == 1
    assert (edge_nodes[0], SCI_NS.bearsOnDepth, Literal(1, datatype=XSD.integer)) in knowledge


def test_changed_snapshot_emits_linked_source_change():
    change = SourceChange(sha256="newh", observed_on=date(2026, 6, 15))
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="newh", latest_change=change)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    ss = source_snapshot_uri("entities/h1.md")
    change_node = source_change_uri("entities/h1.md", "newh")

    assert (ss, SCI_NS.latestSourceChange, change_node) in prov
    assert (change_node, RDF.type, SCI_NS.SourceChange) in prov
    assert (change_node, SCHEMA_NS.sha256, Literal("newh")) in prov
    assert (change_node, SCI_NS.observedOn, Literal("2026-06-15", datatype=XSD.date)) in prov

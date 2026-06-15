"""Source-observation layer (patchwork kernel Spec 3, Slice B).

Observes the content identity of each loaded markdown-backed entity file, diffs it
against the prior build's persisted SourceSnapshots, and emits typed SourceChange
freshness-origins. Filesystem-touching (file hashing + prior-graph read); called by
`materialize_graph`, which passes the precomputed result into the pure
`_build_dataset_from_sources`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_tool.graph.freshness import _emit_bears_on_edge
from science_tool.graph.io import _sha256_file, entity_uri_for_ref
from science_tool.graph.source_records import SourceChange, SourceSnapshot
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS

MARKDOWN_ADAPTER_NAME = "markdown"


def source_snapshot_uri(source_path: str) -> URIRef:
    """Stable per-path snapshot-node IRI (sha256-slugged for IRI safety)."""
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"source-snapshot/{digest}"])


def source_change_uri(source_path: str, sha256: str) -> URIRef:
    """Stable per-(path, new-hash) change-event IRI → carry-forward is byte-identical."""
    key = f"{source_path}\x00{sha256}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"source-change/{digest}"])


@dataclass(frozen=True)
class _PriorSnapshot:
    sha256: str
    latest_change: SourceChange | None


@dataclass(frozen=True)
class SourceSnapshotEmission:
    """One snapshot ready to emit, plus the entity it backs (bears_on target)."""

    snapshot: SourceSnapshot
    entity_canonical_id: str


@dataclass(frozen=True)
class SourceSnapshotResult:
    emissions: list[SourceSnapshotEmission] = field(default_factory=list)
    # snapshot-node URI str -> observed_on of the current latest change (freshness input)
    source_changes: dict[str, date] = field(default_factory=dict)


def read_prior_snapshots(prior_graph_path: Path) -> dict[str, _PriorSnapshot]:
    """Read baseline snapshots from a prior graph.trig.

    Missing file, or an empty / whitespace-only / pre-Slice-B graph (parses to no
    SourceSnapshot nodes) → empty baseline. A corrupt NON-EMPTY graph.trig is NOT
    swallowed: it raises, because silently treating it as empty would suppress the
    very source-change event Slice B exists to detect.
    """
    if not prior_graph_path.exists():
        return {}
    text = prior_graph_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}  # empty / whitespace-only = valid empty baseline
    dataset = Dataset()
    dataset.parse(data=text, format="trig")  # corrupt non-empty → raises (fail loud)
    prov = dataset.graph(PROJECT_NS["graph/provenance"])
    prior: dict[str, _PriorSnapshot] = {}
    for ss in prov.subjects(RDF.type, SCI_NS.SourceSnapshot):
        path_lit = prov.value(ss, SCI_NS.sourcePath)
        sha_lit = prov.value(ss, SCHEMA_NS.sha256)
        if path_lit is None or sha_lit is None:
            continue
        change_node = prov.value(ss, SCI_NS.latestSourceChange)
        latest: SourceChange | None = None
        if change_node is not None:
            c_sha = prov.value(change_node, SCHEMA_NS.sha256)
            c_on = prov.value(change_node, SCI_NS.observedOn)
            if c_sha is not None and c_on is not None:
                latest = SourceChange(sha256=str(c_sha), observed_on=date.fromisoformat(str(c_on)))
        prior[str(path_lit)] = _PriorSnapshot(sha256=str(sha_lit), latest_change=latest)
    return prior


def compute_source_snapshots(sources: Any, *, prior_graph_path: Path, today: date) -> SourceSnapshotResult:
    """Observe + diff + carry-forward snapshots for loaded markdown-backed entities."""
    prior = read_prior_snapshots(prior_graph_path)
    project_root = Path(sources.project_root)
    result = SourceSnapshotResult()
    for entity in sources.entities:
        if sources.entity_source_adapters.get(entity.canonical_id) != MARKDOWN_ADAPTER_NAME:
            continue
        rel_path = entity.file_path
        abs_path = project_root / rel_path
        current_hash = _sha256_file(abs_path)  # fail loud if unreadable/missing
        prior_snap = prior.get(rel_path)
        if prior_snap is None:
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=None)
        elif prior_snap.sha256 == current_hash:
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=prior_snap.latest_change)
        else:
            change = SourceChange(sha256=current_hash, observed_on=today)
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=change)
        result.emissions.append(SourceSnapshotEmission(snapshot=snap, entity_canonical_id=entity.canonical_id))
        if snap.latest_change is not None:
            result.source_changes[str(source_snapshot_uri(rel_path))] = snap.latest_change.observed_on
    return result


def emit_source_snapshots(dataset: Dataset, result: SourceSnapshotResult) -> None:
    """Emit snapshot/change triples (provenance) + SS bears_on entity (knowledge)."""
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for emission in result.emissions:
        snap = emission.snapshot
        ss = source_snapshot_uri(snap.source_path)
        provenance.add((ss, RDF.type, SCI_NS.SourceSnapshot))
        provenance.add((ss, SCI_NS.sourcePath, Literal(snap.source_path)))
        provenance.add((ss, SCHEMA_NS.sha256, Literal(snap.sha256)))

        entity_uri = entity_uri_for_ref(emission.entity_canonical_id)
        knowledge.add((ss, SCI_NS.bearsOn, entity_uri))
        _emit_bears_on_edge(knowledge, ss, entity_uri, 1)

        change = snap.latest_change
        if change is not None:
            change_node = source_change_uri(snap.source_path, change.sha256)
            provenance.add((ss, SCI_NS.latestSourceChange, change_node))
            provenance.add((change_node, RDF.type, SCI_NS.SourceChange))
            provenance.add((change_node, SCHEMA_NS.sha256, Literal(change.sha256)))
            provenance.add((change_node, SCI_NS.observedOn, Literal(change.observed_on.isoformat(), datatype=XSD.date)))

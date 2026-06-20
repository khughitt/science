from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping

from rdflib import Dataset, URIRef

from science_tool.graph.attention import AttentionCandidate
from science_tool.wander.neighbors import NeighborSet, neighbors_for
from science_tool.wander.provenance import created_date_for, source_path_for
from science_tool.wander.references import Reference, active_references_for


@dataclass
class ContextBundle:
    entity_id: str
    uri: str
    kind: str
    label: str
    freshness_state: str
    weight: float
    components: Mapping[str, float]
    source_path: str | None
    mtime: date | None
    content_length: int | None
    created_date: date | None
    neighbors: NeighborSet
    active_references: list[Reference]


def assemble_bundle(
    candidate: AttentionCandidate,
    dataset: Dataset,
    *,
    repo_root: Path | None = None,
) -> ContextBundle:
    """Combine an `AttentionCandidate` with graph + filesystem context."""
    entity_uri = URIRef(candidate.uri)
    source_path = source_path_for(entity_uri, dataset)
    mtime: date | None = None
    content_length: int | None = None
    if source_path is not None:
        path = Path(source_path)
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
            content_length = len(path.read_text(errors="replace"))

    return ContextBundle(
        entity_id=candidate.entity_id,
        uri=candidate.uri,
        kind=candidate.kind,
        label=candidate.label,
        freshness_state=candidate.freshness_state,
        weight=candidate.weight,
        components=dict(candidate.components),
        source_path=source_path,
        mtime=mtime,
        content_length=content_length,
        created_date=created_date_for(entity_uri, dataset, source_path=source_path, repo_root=repo_root),
        neighbors=neighbors_for(entity_uri, dataset),
        active_references=active_references_for(entity_uri, dataset),
    )

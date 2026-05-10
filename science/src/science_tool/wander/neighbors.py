from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import Dataset, URIRef

from science_tool.graph.store import canonical_id_from_entity_uri
from science_tool.graph.io import PROJECT_NS, SCI_NS

OTHER_PREDICATE_CAP = 10


@dataclass(frozen=True)
class NeighborEdge:
    predicate_short: str
    neighbor_id: str
    neighbor_uri: str


@dataclass
class NeighborSet:
    bears_on_incoming: list[str] = field(default_factory=list)
    bears_on_outgoing: list[str] = field(default_factory=list)
    other_incoming: list[NeighborEdge] = field(default_factory=list)
    other_outgoing: list[NeighborEdge] = field(default_factory=list)


def neighbors_for(entity_uri: URIRef, dataset: Dataset) -> NeighborSet:
    """Return neighbors split by direction and predicate, with capping per spec."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    result = NeighborSet()

    for subj in knowledge.subjects(SCI_NS.bearsOn, entity_uri):
        eid = canonical_id_from_entity_uri(str(subj))
        if eid:
            result.bears_on_incoming.append(eid)
    for obj in knowledge.objects(entity_uri, SCI_NS.bearsOn):
        eid = canonical_id_from_entity_uri(str(obj))
        if eid:
            result.bears_on_outgoing.append(eid)

    for subj, pred, _obj in knowledge.triples((None, None, entity_uri)):
        if pred == SCI_NS.bearsOn:
            continue
        eid = canonical_id_from_entity_uri(str(subj))
        if eid is None:
            continue
        if len(result.other_incoming) >= OTHER_PREDICATE_CAP:
            break
        result.other_incoming.append(NeighborEdge(_short(pred), eid, str(subj)))

    for _subj, pred, obj in knowledge.triples((entity_uri, None, None)):
        if pred == SCI_NS.bearsOn:
            continue
        if not isinstance(obj, URIRef):
            continue
        eid = canonical_id_from_entity_uri(str(obj))
        if eid is None:
            continue
        if len(result.other_outgoing) >= OTHER_PREDICATE_CAP:
            break
        result.other_outgoing.append(NeighborEdge(_short(pred), eid, str(obj)))

    result.bears_on_incoming.sort()
    result.bears_on_outgoing.sort()
    return result


def _short(predicate_uri: URIRef) -> str:
    text = str(predicate_uri)
    for sep in ("#", "/"):
        idx = text.rfind(sep)
        if idx != -1:
            return text[idx + 1 :]
    return text

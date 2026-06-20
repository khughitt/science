from __future__ import annotations

from dataclasses import dataclass

from rdflib import Dataset, URIRef

from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.store import canonical_id_from_entity_uri

# Match _CLOSED_STATUSES in science_tool.tasks: a task only stops counting as
# an "active reference" once it's done or retired. Deferred/blocked still count.
INACTIVE_TASK_STATUSES = frozenset({"done", "retired"})


@dataclass(frozen=True)
class Reference:
    entity_id: str
    kind: str  # "task" | "hypothesis"


def active_references_for(entity_uri: URIRef, dataset: Dataset) -> list[Reference]:
    """Return tasks/hypotheses that reference this entity (excluding inactive tasks)."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    references: list[Reference] = []
    for subj, _, _ in knowledge.triples((None, None, entity_uri)):
        if not isinstance(subj, URIRef):
            continue
        eid = canonical_id_from_entity_uri(str(subj))
        if eid is None:
            continue
        kind, _, _ = eid.partition(":")
        if kind not in ("task", "hypothesis"):
            continue
        if kind == "task" and _is_inactive_task(knowledge, subj):
            continue
        references.append(Reference(entity_id=eid, kind=kind))
    seen: dict[str, Reference] = {}
    for ref in references:
        seen.setdefault(ref.entity_id, ref)
    return sorted(seen.values(), key=lambda r: r.entity_id)


def _is_inactive_task(knowledge, task_uri: URIRef) -> bool:
    for status_literal in knowledge.objects(task_uri, SCI_NS.projectStatus):
        if str(status_literal).lower() in INACTIVE_TASK_STATUSES:
            return True
    return False

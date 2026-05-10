from __future__ import annotations

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.io import PROJECT_NS, SCI_NS

from science_tool.wander.neighbors import neighbors_for
from science_tool.wander.references import active_references_for


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def test_neighbors_split_bears_on_from_other_predicates() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("hypothesis/h1")
    knowledge.add((target, RDF.type, SCI_NS.Hypothesis))
    a, b = _u("article/a"), _u("article/b")
    knowledge.add((a, SCI_NS.bearsOn, target))
    knowledge.add((b, SCI_NS.bearsOn, target))
    related = _u("hypothesis/h2")
    knowledge.add((target, SCI_NS.relatedTo, related))

    result = neighbors_for(target, dataset)

    assert sorted(result.bears_on_incoming) == ["article:a", "article:b"]
    assert result.bears_on_outgoing == []
    other_outgoing_ids = [edge.neighbor_id for edge in result.other_outgoing]
    assert "hypothesis:h2" in other_outgoing_ids


def test_neighbors_caps_other_predicates_at_10_each_direction() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("hypothesis/h1")
    knowledge.add((target, RDF.type, SCI_NS.Hypothesis))
    for i in range(15):
        knowledge.add((target, SCI_NS.relatedTo, _u(f"hypothesis/h{i + 100}")))

    result = neighbors_for(target, dataset)

    assert len(result.other_outgoing) == 10


def test_active_references_returns_referencing_tasks_and_hypotheses() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("proposition/p1")
    knowledge.add((target, RDF.type, SCI_NS.Proposition))
    referencing_task = _u("task/t1")
    knowledge.add((referencing_task, RDF.type, SCI_NS.Task))
    knowledge.add((referencing_task, SKOS.related, target))
    referencing_hyp = _u("hypothesis/h1")
    knowledge.add((referencing_hyp, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((referencing_hyp, SCI_NS.bearsOn, target))
    unrelated_dataset = _u("dataset/d1")
    knowledge.add((unrelated_dataset, RDF.type, SCI_NS.Dataset))
    knowledge.add((unrelated_dataset, SCI_NS.bearsOn, target))

    refs = active_references_for(target, dataset)

    ids = sorted(ref.entity_id for ref in refs)
    assert ids == ["hypothesis:h1", "task:t1"]


def test_active_references_excludes_archived_or_completed_tasks() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("proposition/p1")
    archived_task = _u("task/old")
    knowledge.add((archived_task, RDF.type, SCI_NS.Task))
    knowledge.add((archived_task, SCI_NS.projectStatus, Literal("archived")))
    knowledge.add((archived_task, SKOS.related, target))
    completed_task = _u("task/done")
    knowledge.add((completed_task, RDF.type, SCI_NS.Task))
    knowledge.add((completed_task, SCI_NS.projectStatus, Literal("completed")))
    knowledge.add((completed_task, SKOS.related, target))

    assert active_references_for(target, dataset) == []

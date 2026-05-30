from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.dataset_independence import (
    ReducedUsage,
    UsageFact,
    read_dataset_usage_facts,
    reduce_usage_facts,
)
from science_tool.graph.io import PROJECT_NS, SCI_NS


def _usage_graph(*facts: tuple[str, str, str, str, str]) -> Graph:
    graph = Graph()
    for index, (consumer, dataset, role, overlap, source) in enumerate(facts):
        consumer_uri = PROJECT_NS[consumer]
        dataset_uri = PROJECT_NS[dataset]
        usage = PROJECT_NS[f"dataset-usage/u{index}"]
        graph.add((consumer_uri, SCI_NS.hasDatasetUsage, usage))
        graph.add((usage, RDF.type, SCI_NS.DatasetUsage))
        graph.add((usage, SCI_NS.dataset, dataset_uri))
        graph.add((usage, SCI_NS.usageRole, Literal(role)))
        graph.add((usage, SCI_NS.usageOverlap, Literal(overlap)))
        graph.add((usage, SCI_NS.usageSource, Literal(source)))
    return graph


def test_read_dataset_usage_facts_from_b1_graph() -> None:
    graph = _usage_graph(("paper/p1", "dataset/gtex-v8", "analyzed", "full", "authored"))

    facts = read_dataset_usage_facts(graph)

    assert facts == [
        UsageFact(
            consumer=PROJECT_NS["paper/p1"],
            dataset=PROJECT_NS["dataset/gtex-v8"],
            role="analyzed",
            overlap="full",
            source="authored",
            usage_node=PROJECT_NS["dataset-usage/u0"],
        )
    ]


def test_reduce_usage_facts_uses_most_dependent_wins_and_overlap_max() -> None:
    consumer = PROJECT_NS["dataset/derived"]
    dataset = PROJECT_NS["dataset/gtex-v8"]
    facts = [
        UsageFact(consumer, dataset, "validation_source", "full", "authored", PROJECT_NS["dataset-usage/validation"]),
        UsageFact(consumer, dataset, "upstream", "unknown", "derivation.inputs", PROJECT_NS["dataset-usage/upstream"]),
        UsageFact(consumer, dataset, "analyzed", "full", "authored", PROJECT_NS["dataset-usage/analyzed"]),
    ]

    reduced = reduce_usage_facts(facts)

    assert reduced == {
        (consumer, dataset): ReducedUsage(
            consumer=consumer,
            dataset=dataset,
            interpretation="dependence",
            role="analyzed",
            overlap="full",
            sources=frozenset({"authored", "derivation.inputs"}),
            usage_nodes=frozenset(
                {
                    PROJECT_NS["dataset-usage/upstream"],
                    PROJECT_NS["dataset-usage/analyzed"],
                }
            ),
        )
    }


def test_reduce_usage_facts_keeps_validation_and_citation_non_committing() -> None:
    consumer = PROJECT_NS["paper/p1"]
    dataset = PROJECT_NS["dataset/gtex-v8"]
    validation = UsageFact(consumer, dataset, "validation_source", "full", "authored", PROJECT_NS["dataset-usage/v"])
    citation = UsageFact(consumer, PROJECT_NS["dataset/cited"], "cited", "full", "authored", PROJECT_NS["dataset-usage/c"])

    reduced = reduce_usage_facts([validation, citation])

    assert reduced[(consumer, dataset)].interpretation == "validation"
    assert reduced[(consumer, PROJECT_NS["dataset/cited"])].interpretation == "citation"

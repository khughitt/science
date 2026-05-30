"""Dataset-derived independence signals for B2."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import SCI_NS

DEPENDENCE_ROLES = frozenset({"analyzed", "set_definition_source", "training", "upstream"})
VALIDATION_ROLE = "validation_source"
CITED_ROLE = "cited"
OVERLAP_RANK = {"unknown": 0, "partial": 1, "full": 2}
ROLE_RANK = {
    "cited": 0,
    "validation_source": 1,
    "upstream": 2,
    "training": 3,
    "set_definition_source": 4,
    "analyzed": 5,
}

UsageInterpretation = Literal["dependence", "validation", "citation"]


@dataclass(frozen=True, slots=True)
class UsageFact:
    consumer: URIRef
    dataset: URIRef
    role: str
    overlap: str
    source: str
    usage_node: URIRef


@dataclass(frozen=True, slots=True)
class ReducedUsage:
    consumer: URIRef
    dataset: URIRef
    interpretation: UsageInterpretation
    role: str
    overlap: str
    sources: frozenset[str]
    usage_nodes: frozenset[URIRef]


def read_dataset_usage_facts(provenance: Graph) -> list[UsageFact]:
    facts: list[UsageFact] = []
    for consumer, _, usage_node in provenance.triples((None, SCI_NS.hasDatasetUsage, None)):
        if (usage_node, RDF.type, SCI_NS.DatasetUsage) not in provenance:
            continue
        dataset = _one_uri(provenance, usage_node, SCI_NS.dataset)
        role = _one_literal(provenance, usage_node, SCI_NS.usageRole)
        overlap = _one_literal(provenance, usage_node, SCI_NS.usageOverlap) or "unknown"
        source = _one_literal(provenance, usage_node, SCI_NS.usageSource) or ""
        if dataset is None or role is None:
            continue
        facts.append(UsageFact(URIRef(consumer), dataset, role, overlap, source, URIRef(usage_node)))
    return sorted(facts, key=lambda fact: (str(fact.consumer), str(fact.dataset), str(fact.usage_node)))


def reduce_usage_facts(facts: list[UsageFact]) -> dict[tuple[URIRef, URIRef], ReducedUsage]:
    grouped: dict[tuple[URIRef, URIRef], list[UsageFact]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.consumer, fact.dataset)].append(fact)

    reduced: dict[tuple[URIRef, URIRef], ReducedUsage] = {}
    for key, group in grouped.items():
        dependence = [fact for fact in group if fact.role in DEPENDENCE_ROLES]
        validation = [fact for fact in group if fact.role == VALIDATION_ROLE]
        if dependence:
            winners = dependence
            interpretation: UsageInterpretation = "dependence"
            role = max((fact.role for fact in dependence), key=lambda item: ROLE_RANK.get(item, -1))
            overlap = max((fact.overlap for fact in dependence), key=lambda item: OVERLAP_RANK.get(item, -1))
        elif validation:
            winners = validation
            interpretation = "validation"
            role = VALIDATION_ROLE
            overlap = max((fact.overlap for fact in validation), key=lambda item: OVERLAP_RANK.get(item, -1))
        else:
            winners = group
            interpretation = "citation"
            role = CITED_ROLE
            overlap = max((fact.overlap for fact in group), key=lambda item: OVERLAP_RANK.get(item, -1))
        reduced[key] = ReducedUsage(
            consumer=key[0],
            dataset=key[1],
            interpretation=interpretation,
            role=role,
            overlap=overlap,
            sources=frozenset(fact.source for fact in winners if fact.source),
            usage_nodes=frozenset(fact.usage_node for fact in winners),
        )
    return reduced


def _one_uri(graph: Graph, subject: URIRef, predicate: URIRef) -> URIRef | None:
    for value in graph.objects(subject, predicate):
        if isinstance(value, URIRef):
            return value
    return None


def _one_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for value in graph.objects(subject, predicate):
        return str(value)
    return None

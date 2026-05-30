"""Dataset-derived independence signals for B2."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from rdflib import Graph, Literal as RDFLiteral, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS

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
DERIVED_GROUP_PREFIX = "dataset-derived:"

RecordKind = Literal["candidate", "commitment"]


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


@dataclass(frozen=True, slots=True)
class LineAncestor:
    line: URIRef
    target: URIRef
    dataset: URIRef
    usage: ReducedUsage
    path: Literal["direct", "indirect-bears-on", "virtual"]


@dataclass(frozen=True, slots=True)
class DatasetIndependenceRecord:
    kind: RecordKind
    reason: str
    target: URIRef
    members: frozenset[URIRef]
    datasets: frozenset[URIRef]
    usage_nodes: frozenset[URIRef]
    independence_group: str

    @property
    def independence(self) -> str | None:
        return "shared-source" if self.kind == "commitment" else None


@dataclass(frozen=True, slots=True)
class CandidateEdge:
    left: LineAncestor
    right: LineAncestor
    dataset: URIRef
    reason: str


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


def derive_dataset_independence_records(knowledge: Graph, provenance: Graph) -> list[DatasetIndependenceRecord]:
    reduced = reduce_usage_facts(read_dataset_usage_facts(provenance))
    line_targets = _evidence_line_targets(knowledge)
    ancestors = _line_ancestors(knowledge, provenance, reduced, line_targets)
    records: list[DatasetIndependenceRecord] = []
    for target in sorted(set(line_targets.values()), key=str):
        target_lines = frozenset(line for line, line_target in line_targets.items() if line_target == target)
        records.extend(_commitment_components(target, target_lines, ancestors))
        records.extend(_candidate_components(target, target_lines, ancestors))
    return sorted(records, key=lambda record: (record.kind, str(record.target), record.reason, sorted(map(str, record.members))))


def emit_dataset_independence_records(provenance: Graph, records: list[DatasetIndependenceRecord]) -> None:
    for record in records:
        node = _record_uri(record)
        klass = SCI_NS.DatasetIndependenceCommitment if record.kind == "commitment" else SCI_NS.DatasetIndependenceCandidate
        provenance.add((node, RDF.type, klass))
        provenance.add((node, SCI_NS.independenceTarget, record.target))
        provenance.add((node, SCI_NS.independenceGroup, RDFLiteral(record.independence_group)))
        provenance.add((node, SCI_NS.independenceReason, RDFLiteral(record.reason)))
        for member in sorted(record.members, key=str):
            provenance.add((node, SCI_NS.independenceMember, member))
        for dataset in sorted(record.datasets, key=str):
            provenance.add((node, SCI_NS.sharedDataset, dataset))
        for usage_node in sorted(record.usage_nodes, key=str):
            provenance.add((node, SCI_NS.derivedFromDatasetUsage, usage_node))


def _evidence_line_targets(knowledge: Graph) -> dict[URIRef, URIRef]:
    out: dict[URIRef, URIRef] = {}
    for predicate in (CITO_NS.supports, CITO_NS.disputes):
        for line, _, target in knowledge.triples((None, predicate, None)):
            if (line, RDF.type, SCI_NS.EvidenceLine) in knowledge and isinstance(line, URIRef) and isinstance(target, URIRef):
                out[line] = target
    return out


def _line_ancestors(
    knowledge: Graph,
    provenance: Graph,
    reduced: dict[tuple[URIRef, URIRef], ReducedUsage],
    line_targets: dict[URIRef, URIRef],
) -> list[LineAncestor]:
    ancestors: list[LineAncestor] = []
    for line, target in line_targets.items():
        for (consumer, _dataset), usage in reduced.items():
            path = _ancestor_path(knowledge, provenance, line, target, consumer)
            if path is None:
                continue
            ancestors.append(LineAncestor(line=line, target=target, dataset=usage.dataset, usage=usage, path=path))
    return ancestors


def _ancestor_path(knowledge: Graph, provenance: Graph, line: URIRef, target: URIRef, consumer: URIRef) -> str | None:
    if consumer == line:
        return "virtual" if _is_virtual_gene_set_member(consumer) else "direct"
    if (line, PROV.wasDerivedFrom, consumer) in provenance:
        return "virtual" if _is_virtual_gene_set_member(consumer) else "direct"
    if (consumer, SCI_NS.bearsOn, target) in knowledge:
        return "indirect-bears-on"
    return None


def _is_virtual_gene_set_member(uri: URIRef) -> bool:
    return "/virtual/geneset-member/" in str(uri)


def _commitment_components(
    target: URIRef,
    target_lines: frozenset[URIRef],
    ancestors: list[LineAncestor],
) -> list[DatasetIndependenceRecord]:
    direct_full = [
        ancestor
        for ancestor in ancestors
        if ancestor.target == target
        and ancestor.line in target_lines
        and ancestor.path == "direct"
        and ancestor.usage.interpretation == "dependence"
        and ancestor.usage.overlap == "full"
    ]
    return _components_from_ancestors("commitment", "full-overlap", target, direct_full)


def _candidate_components(
    target: URIRef,
    target_lines: frozenset[URIRef],
    ancestors: list[LineAncestor],
) -> list[DatasetIndependenceRecord]:
    out: list[DatasetIndependenceRecord] = []
    edges_by_reason: dict[str, list[CandidateEdge]] = defaultdict(list)
    for edge in _candidate_edges(target, target_lines, ancestors):
        edges_by_reason[edge.reason].append(edge)
    for reason, edges in sorted(edges_by_reason.items()):
        out.extend(_records_from_candidate_edges(target, reason, edges))
    return out


def _candidate_edges(
    target: URIRef,
    target_lines: frozenset[URIRef],
    ancestors: list[LineAncestor],
) -> list[CandidateEdge]:
    by_dataset: dict[URIRef, list[LineAncestor]] = defaultdict(list)
    for ancestor in ancestors:
        if ancestor.target != target or ancestor.line not in target_lines:
            continue
        by_dataset[ancestor.dataset].append(ancestor)
    out: list[CandidateEdge] = []
    for dataset, group in by_dataset.items():
        ordered = sorted(group, key=lambda ancestor: str(ancestor.line))
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                if left.line == right.line:
                    continue
                if _is_committable_pair(left, right):
                    continue
                reason = _candidate_reason(left, right)
                if reason is not None:
                    out.append(CandidateEdge(left=left, right=right, dataset=dataset, reason=reason))
    return out


def _is_committable_pair(left: LineAncestor, right: LineAncestor) -> bool:
    return (
        left.path == right.path == "direct"
        and left.usage.interpretation == right.usage.interpretation == "dependence"
        and left.usage.overlap == right.usage.overlap == "full"
    )


def _candidate_reason(left: LineAncestor, right: LineAncestor) -> str | None:
    if "indirect-bears-on" in {left.path, right.path}:
        return "indirect-bears-on"
    if "virtual" in {left.path, right.path}:
        return "virtual-row"
    interpretations = {left.usage.interpretation, right.usage.interpretation}
    if "citation" in interpretations:
        return "citation-only"
    if "validation" in interpretations:
        return "validation"
    overlaps = {left.usage.overlap, right.usage.overlap}
    if "unknown" in overlaps:
        return "unknown-overlap"
    if "partial" in overlaps:
        return "partial-overlap"
    return None


def _components_from_ancestors(
    kind: RecordKind,
    reason: str,
    target: URIRef,
    ancestors: list[LineAncestor],
) -> list[DatasetIndependenceRecord]:
    by_dataset: dict[URIRef, list[LineAncestor]] = defaultdict(list)
    for ancestor in ancestors:
        by_dataset[ancestor.dataset].append(ancestor)

    edges: list[tuple[URIRef, URIRef, URIRef]] = []
    for dataset, group in by_dataset.items():
        lines = sorted({ancestor.line for ancestor in group}, key=str)
        if len(lines) < 2:
            continue
        for left, right in zip(lines, lines[1:], strict=False):
            edges.append((left, right, dataset))
    if not edges:
        return []

    records: list[DatasetIndependenceRecord] = []
    for members in _connected_components(edges):
        member_datasets = frozenset(dataset for left, right, dataset in edges if left in members and right in members)
        usage_nodes = frozenset(
            node
            for ancestor in ancestors
            if ancestor.line in members and ancestor.dataset in member_datasets
            for node in ancestor.usage.usage_nodes
        )
        records.append(
            DatasetIndependenceRecord(
                kind=kind,
                reason=reason,
                target=target,
                members=frozenset(members),
                datasets=member_datasets,
                usage_nodes=usage_nodes,
                independence_group=_group_key(member_datasets),
            )
        )
    return records


def _records_from_candidate_edges(
    target: URIRef,
    reason: str,
    edges: list[CandidateEdge],
) -> list[DatasetIndependenceRecord]:
    graph_edges = [(edge.left.line, edge.right.line, edge.dataset) for edge in edges]
    records: list[DatasetIndependenceRecord] = []
    for members in _connected_components(graph_edges):
        component_edges = [edge for edge in edges if edge.left.line in members and edge.right.line in members]
        datasets = frozenset(edge.dataset for edge in component_edges)
        usage_nodes = frozenset(
            node
            for edge in component_edges
            for ancestor in (edge.left, edge.right)
            for node in ancestor.usage.usage_nodes
        )
        records.append(
            DatasetIndependenceRecord(
                kind="candidate",
                reason=reason,
                target=target,
                members=frozenset(members),
                datasets=datasets,
                usage_nodes=usage_nodes,
                independence_group=_group_key(datasets),
            )
        )
    return records


def _connected_components(edges: list[tuple[URIRef, URIRef, URIRef]]) -> list[frozenset[URIRef]]:
    adjacency: dict[URIRef, set[URIRef]] = defaultdict(set)
    for left, right, _dataset in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    seen: set[URIRef] = set()
    components: list[frozenset[URIRef]] = []
    for start in sorted(adjacency, key=str):
        if start in seen:
            continue
        queue = deque([start])
        members: set[URIRef] = set()
        while queue:
            item = queue.popleft()
            if item in seen:
                continue
            seen.add(item)
            members.add(item)
            queue.extend(sorted(adjacency[item] - seen, key=str))
        components.append(frozenset(members))
    return components


def _group_key(datasets: frozenset[URIRef]) -> str:
    ordered = sorted(str(dataset) for dataset in datasets)
    if len(ordered) == 1:
        return DERIVED_GROUP_PREFIX + ordered[0].rstrip("/").split("/")[-1]
    digest = hashlib.sha256(json.dumps(ordered, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return DERIVED_GROUP_PREFIX + digest


def _record_uri(record: DatasetIndependenceRecord) -> URIRef:
    payload = {
        "kind": record.kind,
        "reason": record.reason,
        "target": str(record.target),
        "members": sorted(map(str, record.members)),
        "datasets": sorted(map(str, record.datasets)),
        "usage_nodes": sorted(map(str, record.usage_nodes)),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return PROJECT_NS[f"dataset-independence/{digest}"]


def _one_uri(graph: Graph, subject: URIRef, predicate: URIRef) -> URIRef | None:
    for value in graph.objects(subject, predicate):
        if isinstance(value, URIRef):
            return value
    return None


def _one_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for value in graph.objects(subject, predicate):
        return str(value)
    return None

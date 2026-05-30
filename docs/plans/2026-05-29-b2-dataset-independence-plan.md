# B2 Dataset-Derived Independence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive candidate and committed evidence-line non-independence from B1 `sci:DatasetUsage` graph truth, feeding review warnings and committed belief collapse without reparsing source files.

**Architecture:** Add one focused graph derivation module that reads usage nodes, reduces duplicate `(consumer, dataset)` facts, builds evidence-line dataset ancestry, and materializes component records with B2-specific predicates. Belief collection explicitly merges committed records into `EvidenceUnit`s with authored-wins precedence; validation reads derived records for expanded `independence.suspect-circular` and contradiction checks.

**Tech Stack:** rdflib `Dataset`/`Graph`, dataclasses, pytest, existing `science_tool.graph.belief`, existing `science_tool.graph.materialize`, existing `science_tool.validate` check framework.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/graph/dataset_independence.py` | Pure B2 usage reduction, evidence-line ancestry indexing, candidate/commitment derivation, component grouping, graph record emission, committed metadata lookup for belief collection. |
| `science/src/science_tool/graph/materialize.py` | Invoke B2 derivation after B1 usage nodes and `bears_on` closure exist. |
| `science/src/science_tool/graph/belief.py` | Merge committed B2 metadata into collected `EvidenceUnit`s without writing same-predicate triples onto line nodes. |
| `science/src/science_tool/graph/belief_weights.py` | Bump `CONFIG_VERSION` once committed B2 records affect aggregation. |
| `science/src/science_tool/validate/checks/evidence_lines.py` | Extend `independence.suspect-circular` and add committed-vs-authored contradiction reporting from materialized B2 records. |
| `science/tests/test_dataset_independence.py` | Pure and graph-level B2 derivation tests. |
| `science/tests/test_belief_collect.py` | Belief collection merge precedence tests. |
| `science/tests/test_belief_aggregate.py` | Aggregation behavior for candidate-vs-committed records and contested groups. |
| `science/tests/test_belief_weights.py` | Config version assertion update. |
| `science/tests/validate/test_checks_evidence_lines.py` | Derived candidate/commitment validation tests. |
| `docs/plans/2026-05-29-b2-dataset-independence-design.md` | Mark implementation state after all code lands. |

Do not emit derived `sci:evidenceIndependence`, `sci:independenceGroup`, or `sci:sharedDataset` triples onto evidence-line nodes. That would collide with authored values and make `_lit()` order-dependent.

## Task 1: Usage Reduction

**Files:**
- Create: `science/src/science_tool/graph/dataset_independence.py`
- Test: `science/tests/test_dataset_independence.py`

- [ ] **Step 1: Write failing pure reduction tests**

Create `science/tests/test_dataset_independence.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.dataset_independence'`.

- [ ] **Step 3: Implement usage facts and reduction**

Create `science/src/science_tool/graph/dataset_independence.py`:

```python
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
ROLE_RANK = {"cited": 0, "validation_source": 1, "upstream": 2, "training": 3, "set_definition_source": 4, "analyzed": 5}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/dataset_independence.py science/tests/test_dataset_independence.py
rtk git commit -m "feat: reduce dataset usage for independence"
```

## Task 2: Evidence-Line Ancestors And Derived Component Records

**Files:**
- Modify: `science/src/science_tool/graph/dataset_independence.py`
- Modify: `science/tests/test_dataset_independence.py`

- [ ] **Step 1: Write failing graph derivation tests**

Append to `science/tests/test_dataset_independence.py`:

```python
from rdflib.namespace import PROV

from science_tool.graph.dataset_independence import (
    DERIVED_GROUP_PREFIX,
    derive_dataset_independence_records,
    emit_dataset_independence_records,
)
from science_tool.graph.io import CITO_NS


def _line_graph() -> tuple[Graph, Graph, URIRef, URIRef, URIRef]:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    return knowledge, provenance, target, line_a, line_b


def _add_usage(provenance: Graph, consumer: URIRef, dataset: URIRef, role: str, overlap: str, suffix: str) -> URIRef:
    usage = PROJECT_NS[f"dataset-usage/{suffix}"]
    provenance.add((consumer, SCI_NS.hasDatasetUsage, usage))
    provenance.add((usage, RDF.type, SCI_NS.DatasetUsage))
    provenance.add((usage, SCI_NS.dataset, dataset))
    provenance.add((usage, SCI_NS.usageRole, Literal(role)))
    provenance.add((usage, SCI_NS.usageOverlap, Literal(overlap)))
    provenance.add((usage, SCI_NS.usageSource, Literal("authored")))
    return usage


def test_full_overlap_direct_shared_dataset_derives_one_commitment_component() -> None:
    knowledge, provenance, target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "analyzed", "full", "a")
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "b")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert len(records) == 1
    record = records[0]
    assert record.kind == "commitment"
    assert record.reason == "full-overlap"
    assert record.target == target
    assert record.members == frozenset({line_a, line_b})
    assert record.datasets == frozenset({dataset})
    assert record.independence == "shared-source"
    assert record.independence_group == f"{DERIVED_GROUP_PREFIX}gtex-v8"


def test_unknown_overlap_shared_dataset_derives_candidate_only() -> None:
    knowledge, provenance, _target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "analyzed", "unknown", "a")
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "b")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert [(record.kind, record.reason) for record in records] == [("candidate", "unknown-overlap")]


def test_bears_on_only_shared_dataset_is_candidate_even_with_full_overlap() -> None:
    knowledge, provenance, target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    paper = PROJECT_NS["paper/p1"]
    _add_usage(provenance, paper, dataset, "analyzed", "full", "paper")
    knowledge.add((paper, SCI_NS.bearsOn, target))
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "line")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert [(record.kind, record.reason, record.members) for record in records] == [
        ("candidate", "indirect-bears-on", frozenset({line_a, line_b}))
    ]


def test_transitive_hub_full_overlap_forms_one_conservative_component() -> None:
    knowledge, provenance, target, line_a, line_b = _line_graph()
    line_c = PROJECT_NS["evidence-line/c"]
    knowledge.add((line_c, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line_c, CITO_NS.supports, target))
    dataset_x = PROJECT_NS["dataset/x"]
    dataset_y = PROJECT_NS["dataset/y"]
    _add_usage(provenance, line_a, dataset_x, "analyzed", "full", "a-x")
    _add_usage(provenance, line_b, dataset_x, "analyzed", "full", "b-x")
    _add_usage(provenance, line_b, dataset_y, "analyzed", "full", "b-y")
    _add_usage(provenance, line_c, dataset_y, "analyzed", "full", "c-y")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert len(records) == 1
    assert records[0].kind == "commitment"
    assert records[0].target == target
    assert records[0].members == frozenset({line_a, line_b, line_c})
    assert records[0].datasets == frozenset({dataset_x, dataset_y})


def test_emit_records_uses_b2_specific_predicates_not_evidence_line_or_target() -> None:
    knowledge, provenance, target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "analyzed", "full", "a")
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)

    emit_dataset_independence_records(provenance, records)

    record_nodes = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(record_nodes) == 1
    record = record_nodes[0]
    assert (record, SCI_NS.independenceTarget, target) in provenance
    assert (record, SCI_NS.independenceMember, line_a) in provenance
    assert (record, SCI_NS.independenceMember, line_b) in provenance
    assert (record, SCI_NS.sharedDataset, dataset) in provenance
    assert list(provenance.triples((record, SCI_NS.evidenceLine, None))) == []
    assert list(provenance.triples((record, SCI_NS.target, None))) == []
    assert list(provenance.triples((line_a, SCI_NS.evidenceIndependence, None))) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py::test_full_overlap_direct_shared_dataset_derives_one_commitment_component science/tests/test_dataset_independence.py::test_unknown_overlap_shared_dataset_derives_candidate_only science/tests/test_dataset_independence.py::test_bears_on_only_shared_dataset_is_candidate_even_with_full_overlap science/tests/test_dataset_independence.py::test_transitive_hub_full_overlap_forms_one_conservative_component science/tests/test_dataset_independence.py::test_emit_records_uses_b2_specific_predicates_not_evidence_line_or_target -q
```

Expected: FAIL with missing `derive_dataset_independence_records`.

- [ ] **Step 3: Implement derivation and graph emission**

Add these definitions to `science/src/science_tool/graph/dataset_independence.py`:

```python
import hashlib
import json
from collections import deque

from rdflib import Literal as RDFLiteral
from rdflib.namespace import PROV

from science_tool.graph.io import CITO_NS, PROJECT_NS

DERIVED_GROUP_PREFIX = "dataset-derived:"

RecordKind = Literal["candidate", "commitment"]


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
```

Then add the implementation:

```python
def derive_dataset_independence_records(knowledge: Graph, provenance: Graph) -> list[DatasetIndependenceRecord]:
    reduced = reduce_usage_facts(read_dataset_usage_facts(provenance))
    line_targets = _evidence_line_targets(knowledge)
    ancestors = _line_ancestors(knowledge, provenance, reduced, line_targets)
    records: list[DatasetIndependenceRecord] = []
    for target in sorted(line_targets, key=str):
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
```

Add helpers:

```python
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
```

This intentionally checks `(consumer, sci:bearsOn, target)`. `freshness.py` emits that orientation after closure for a source consumer that reaches an evidence line/proposition, so B2 should not reverse the edge.

Add component logic:

```python
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
    return _components_from_edges("commitment", "full-overlap", target, direct_full)


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


def _components_from_edges(
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

    components = _connected_components(edges)
    records: list[DatasetIndependenceRecord] = []
    for members in components:
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
    components = _connected_components(graph_edges)
    records: list[DatasetIndependenceRecord] = []
    for members in components:
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
```

- [ ] **Step 4: Run derivation tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/dataset_independence.py science/tests/test_dataset_independence.py
rtk git commit -m "feat: derive dataset independence records"
```

## Task 3: Materialize B2 Records In Graph Build

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Modify: `science/tests/test_dataset_usage_materialize.py`
- Modify: `science/tests/test_graph_materialize.py`

- [ ] **Step 1: Write failing materialization integration test**

In `science/tests/test_dataset_usage_materialize.py`, change:

```python
from rdflib.namespace import RDF
```

to:

```python
from rdflib.namespace import PROV, RDF
```

Then append:

```python
def test_materialize_graph_emits_dataset_independence_commitment(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "doc" / "datasets").mkdir(parents=True)
    (root / "doc" / "datasets" / "gtex.md").write_text(
        "---\nid: dataset:gtex-v8\nkind: dataset\ntitle: GTEx\n---\n",
        encoding="utf-8",
    )
    (root / "doc" / "papers").mkdir(parents=True)
    (root / "doc" / "papers" / "p1.md").write_text(
        "---\nid: paper:p1\nkind: paper\ntitle: P1\ndataset_usage:\n  - ref: dataset:gtex-v8\n    role: analyzed\n    overlap: full\n---\n",
        encoding="utf-8",
    )
    (root / "doc" / "papers" / "p2.md").write_text(
        "---\nid: paper:p2\nkind: paper\ntitle: P2\ndataset_usage:\n  - ref: dataset:gtex-v8\n    role: analyzed\n    overlap: full\n---\n",
        encoding="utf-8",
    )
    (root / "doc" / "evidence").mkdir(parents=True)
    (root / "doc" / "evidence" / "a.md").write_text(
        "---\nid: evidence-line:a\nkind: evidence-line\ntarget: proposition:p1\nstance: supports\nsource: paper:p1\n---\n",
        encoding="utf-8",
    )
    (root / "doc" / "evidence" / "b.md").write_text(
        "---\nid: evidence-line:b\nkind: evidence-line\ntarget: proposition:p1\nstance: supports\nsource: paper:p2\n---\n",
        encoding="utf-8",
    )

    graph_path = materialize_graph(root)
    dataset = Dataset()
    dataset.parse(graph_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]

    assert (line_a, PROV.wasDerivedFrom, PROJECT_NS["paper/p1"]) in provenance
    assert (line_b, PROV.wasDerivedFrom, PROJECT_NS["paper/p2"]) in provenance

    records = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(records) == 1
    assert (records[0], SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")) in provenance
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_emits_dataset_independence_commitment -q
```

Expected: FAIL because no B2 commitment records are emitted.

- [ ] **Step 3: Wire B2 into materialization**

In `science/src/science_tool/graph/materialize.py`, import:

```python
from science_tool.graph.dataset_independence import (
    derive_dataset_independence_records,
    emit_dataset_independence_records,
)
```

Inside `_build_dataset_from_sources`, after the `_derive_bears_on_layer(...)` block and before the freshness block / `return dataset`, add:

```python
    emit_dataset_independence_records(
        provenance,
        derive_dataset_independence_records(knowledge, provenance),
    )
```

Do not put this in `materialize_graph`: that function only receives the already-built dataset and does not have `knowledge` or `provenance` locals. `_build_dataset_from_sources` is the correct scope because it owns `knowledge`, `provenance`, and the `_derive_bears_on_layer(...)` call. Placing B2 there also means B2 records are derived consistently for both disk materialization and the in-memory `propagate_freshness_in_memory` sweep, because both paths share this helper.

- [ ] **Step 4: Run materialization tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py science/tests/test_graph_materialize.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/materialize.py science/tests/test_dataset_usage_materialize.py science/tests/test_graph_materialize.py
rtk git commit -m "feat: materialize dataset independence records"
```

## Task 4: Belief Collection Merge And Config Version

**Files:**
- Modify: `science/src/science_tool/graph/dataset_independence.py`
- Modify: `science/src/science_tool/graph/belief.py`
- Modify: `science/src/science_tool/graph/belief_weights.py`
- Modify: `science/tests/test_belief_collect.py`
- Modify: `science/tests/test_belief_aggregate.py`
- Modify: `science/tests/test_belief_weights.py`
- Modify: `science/tests/test_belief_snapshot.py`
- Modify: `science/tests/test_belief_cli.py`

- [ ] **Step 1: Write failing collection and aggregation tests**

Append to `science/tests/test_belief_collect.py`:

```python
def test_collect_evidence_units_merges_committed_dataset_independence_for_untagged_lines() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    record = PROJECT_NS["dataset-independence/r1"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCommitment))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert [(unit.line_uri, unit.independence, unit.independence_group) for unit in units] == [
        (str(line_a), "shared-source", "dataset-derived:gtex-v8"),
        (str(line_b), "shared-source", "dataset-derived:gtex-v8"),
    ]


def test_collect_evidence_units_keeps_authored_circular_over_derived_commitment() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line = PROJECT_NS["evidence-line/a"]
    record = PROJECT_NS["dataset-independence/r1"]
    knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line, CITO_NS.supports, target))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal("circular")))
    provenance.add((line, SCI_NS.independenceGroup, Literal("manual-circular")))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCommitment))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert units[0].independence == "circular"
    assert units[0].independence_group == "manual-circular"
```

Append to `science/tests/test_belief_aggregate.py`:

```python
def test_aggregate_belief_candidates_do_not_collapse_but_committed_records_do() -> None:
    ungrouped = [
        EvidenceUnit(str(PROJECT_NS["evidence-line/a"]), "supports", "medium", None, None, None, None, None, None, False, None, ()),
        EvidenceUnit(str(PROJECT_NS["evidence-line/b"]), "supports", "medium", None, None, None, None, None, None, False, None, ()),
    ]
    committed = [
        EvidenceUnit(str(PROJECT_NS["evidence-line/a"]), "supports", "medium", "shared-source", "dataset-derived:gtex-v8", None, None, None, None, False, None, ()),
        EvidenceUnit(str(PROJECT_NS["evidence-line/b"]), "supports", "medium", "shared-source", "dataset-derived:gtex-v8", None, None, None, None, False, None, ()),
    ]

    assert len(reduce_units(ungrouped).kept) == 2
    reduced = reduce_units(committed)
    assert len(reduced.kept) == 1
    assert len(reduced.collapsed) == 1
```

In `science/tests/test_belief_weights.py`, change the config assertion inside `test_phase2_constants_present` to:

```python
assert bw.CONFIG_VERSION == "belief-logodds-v3"
```

In `science/tests/test_belief_snapshot.py`, change:

```python
assert row["config_version"] == "belief-logodds-v2"
```

to:

```python
assert row["config_version"] == "belief-logodds-v3"
```

In `science/tests/test_belief_cli.py`, change the canned snapshot row from:

```python
"input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v2",
```

to:

```python
"input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_belief_collect.py::test_collect_evidence_units_merges_committed_dataset_independence_for_untagged_lines science/tests/test_belief_collect.py::test_collect_evidence_units_keeps_authored_circular_over_derived_commitment science/tests/test_belief_aggregate.py::test_aggregate_belief_candidates_do_not_collapse_but_committed_records_do science/tests/test_belief_weights.py::test_phase2_constants_present science/tests/test_belief_snapshot.py::test_snapshot_records_basic_shape science/tests/test_belief_cli.py::test_belief_snapshot_writes_jsonl -q
```

Expected: belief collection tests FAIL because committed records are ignored; config test FAILS with current `belief-logodds-v2`.

- [ ] **Step 3: Add committed metadata lookup**

Add to `science/src/science_tool/graph/dataset_independence.py`:

```python
@dataclass(frozen=True, slots=True)
class DerivedCommitmentMetadata:
    independence: str
    independence_group: str


def committed_metadata_by_line(provenance: Graph, targets: frozenset[URIRef]) -> dict[URIRef, DerivedCommitmentMetadata]:
    out: dict[URIRef, DerivedCommitmentMetadata] = {}
    for record in provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment):
        target = _one_uri(provenance, URIRef(record), SCI_NS.independenceTarget)
        if target not in targets:
            continue
        group = _one_literal(provenance, URIRef(record), SCI_NS.independenceGroup)
        if group is None:
            continue
        for member in provenance.objects(record, SCI_NS.independenceMember):
            if isinstance(member, URIRef):
                out[member] = DerivedCommitmentMetadata("shared-source", group)
    return out
```

- [ ] **Step 4: Merge committed metadata in belief collection**

In `science/src/science_tool/graph/belief.py`, import:

```python
from .dataset_independence import committed_metadata_by_line
```

Add:

```python
def _with_derived_commitment(unit: EvidenceUnit, derived: dict[URIRef, object]) -> EvidenceUnit:
    metadata = derived.get(URIRef(unit.line_uri))
    if metadata is None:
        return unit
    if unit.independence in (CIRCULAR, SHARED_SOURCE, INDEPENDENT):
        return unit
    return EvidenceUnit(
        line_uri=unit.line_uri,
        stance=unit.stance,
        strength=unit.strength,
        independence=metadata.independence,
        independence_group=metadata.independence_group,
        evidence_role=unit.evidence_role,
        evidence_type=unit.evidence_type,
        dispute_scope=unit.dispute_scope,
        proxy_directness=unit.proxy_directness,
        has_measurement_model=unit.has_measurement_model,
        source=unit.source,
        observability_keys=unit.observability_keys,
        is_reference_dataset=unit.is_reference_dataset,
    )
```

At the end of `collect_evidence_units`, before returning:

```python
    derived = committed_metadata_by_line(provenance, frozenset(targets))
    return [_with_derived_commitment(unit, derived) for unit in units]
```

Keep authored `independent` untouched so validation can surface the contradiction instead of hiding it during collection.

- [ ] **Step 5: Bump config version**

In `science/src/science_tool/graph/belief_weights.py`, change:

```python
CONFIG_VERSION = "belief-logodds-v2"   # A2 curation down-weight; bump on any change here
```

to:

```python
CONFIG_VERSION = "belief-logodds-v3"   # B2 committed dataset-derived independence; bump on any scoring input change
```

- [ ] **Step 6: Run belief tests**

Run:

```bash
uv run --frozen pytest science/tests/test_belief_collect.py science/tests/test_belief_aggregate.py science/tests/test_belief_weights.py science/tests/test_belief_snapshot.py science/tests/test_belief_cli.py -q
```

Expected: PASS after updating every `belief-logodds-v2` assertion in the affected belief tests to `belief-logodds-v3`.

- [ ] **Step 7: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/dataset_independence.py science/src/science_tool/graph/belief.py science/src/science_tool/graph/belief_weights.py science/tests/test_belief_collect.py science/tests/test_belief_aggregate.py science/tests/test_belief_weights.py science/tests/test_belief_snapshot.py science/tests/test_belief_cli.py
rtk git commit -m "feat: merge committed dataset independence into belief"
```

## Task 5: Validation For Candidates And Authored Contradictions

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Modify: `science/tests/validate/test_checks_evidence_lines.py`

- [ ] **Step 1: Write failing validation tests**

Append to `science/tests/validate/test_checks_evidence_lines.py`:

```python
from rdflib import Dataset


def _ctx_with_b2_graph(tmp_path: Path, *, record_type: URIRef, authored: dict[str, str] | None = None) -> ValidateContext:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    if authored:
        for key, value in authored.items():
            predicate = {
                "independence": SCI_NS.evidenceIndependence,
                "independence_group": SCI_NS.independenceGroup,
                "shared_dataset": SCI_NS.sharedDataset,
            }[key]
            provenance.add((line_a, predicate, Literal(value)))
    record = PROJECT_NS["dataset-independence/r1"]
    provenance.add((record, RDF.type, record_type))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceReason, Literal("unknown-overlap")))
    provenance.add((record, SCI_NS.sharedDataset, PROJECT_NS["dataset/gtex-v8"]))
    ds.serialize(graph_path, format="trig")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_suspect_circular_warns_for_untagged_lines_with_derived_candidate(tmp_path: Path) -> None:
    ctx = _ctx_with_b2_graph(tmp_path, record_type=SCI_NS.DatasetIndependenceCandidate)

    results = list(check_independence_suspect_circular(ctx))

    assert [(result.severity, result.rule) for result in results] == [
        (Severity.WARN, "independence.suspect-circular")
    ]


def test_committed_dataset_dependence_errors_when_line_authored_independent(tmp_path: Path) -> None:
    ctx = _ctx_with_b2_graph(
        tmp_path,
        record_type=SCI_NS.DatasetIndependenceCommitment,
        authored={"independence": "independent"},
    )

    results = list(check_independence_suspect_circular(ctx))

    assert [(result.severity, result.rule) for result in results] == [
        (Severity.ERROR, "independence.dataset-derived-contradiction")
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_evidence_lines.py::test_suspect_circular_warns_for_untagged_lines_with_derived_candidate science/tests/validate/test_checks_evidence_lines.py::test_committed_dataset_dependence_errors_when_line_authored_independent -q
```

Expected: FAIL because the check does not read B2 records.

B2 validation reads `knowledge/graph.trig` if present and emits no B2-derived result when it is absent. That means these warnings are only as current as the last graph build; the check must not reparse papers, datasets, or gene-set CSVs during validate.

- [ ] **Step 3: Extend evidence-line validation to read B2 graph records**

In `science/src/science_tool/validate/checks/evidence_lines.py`, add imports:

```python
from rdflib import Dataset, URIRef
from science_tool.graph.io import PROJECT_NS, SCI_NS
```

Add helper functions near `check_independence_suspect_circular`:

```python
def _load_provenance_graph(ctx: ValidateContext):
    graph_path = ctx.project_root / "knowledge" / "graph.trig"
    if not graph_path.exists():
        return None
    dataset = Dataset()
    dataset.parse(graph_path, format="trig")
    return dataset.graph(PROJECT_NS["graph/provenance"])


def _line_independence(provenance, line: URIRef) -> str | None:
    if provenance is None:
        return None
    for value in provenance.objects(line, SCI_NS.evidenceIndependence):
        return str(value)
    return None
```

At the start of `check_independence_suspect_circular`, load provenance:

```python
    provenance = _load_provenance_graph(ctx)
```

After the existing authored pair loop, add:

```python
    if provenance is None:
        return
    for record in provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment):
        members = [member for member in provenance.objects(record, SCI_NS.independenceMember) if isinstance(member, URIRef)]
        for member in members:
            if _line_independence(provenance, member) == "independent":
                yield Result(
                    severity=Severity.ERROR,
                    path=None,
                    line=None,
                    message=f"{member}: authored independence=independent contradicts committed dataset-derived shared-source dependence",
                    rule="independence.dataset-derived-contradiction",
                    task=None,
                )
    for record in provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCandidate):
        members = [member for member in provenance.objects(record, SCI_NS.independenceMember) if isinstance(member, URIRef)]
        if len(members) < 2:
            continue
        eligible = [
            member
            for member in members
            if _line_independence(provenance, member) in (None, "independent")
        ]
        if len(eligible) >= 2:
            reason = next((str(value) for value in provenance.objects(record, SCI_NS.independenceReason)), "dataset-derived")
            yield Result(
                severity=Severity.WARN,
                path=None,
                line=None,
                message=f"dataset-derived candidate dependence ({reason}) links {len(eligible)} untagged/authored-independent lines on the same target",
                rule="independence.suspect-circular",
                task=None,
            )
```

This deliberately reads materialized graph truth and does not reparse papers, datasets, or gene-set CSVs.

- [ ] **Step 4: Run validation tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_evidence_lines.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_evidence_lines.py
rtk git commit -m "feat: validate dataset-derived independence"
```

## Task 6: Refutation Of Authored Dataset-Based Groups

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Modify: `science/tests/validate/test_checks_evidence_lines.py`

- [ ] **Step 1: Write failing refutation tests**

Append to `science/tests/validate/test_checks_evidence_lines.py`:

```python
def test_authored_shared_dataset_refuted_only_when_all_group_members_are_checkable(tmp_path: Path) -> None:
    ctx = _ctx_with_b2_graph(
        tmp_path,
        record_type=SCI_NS.DatasetIndependenceCandidate,
        authored={
            "independence": "shared-source",
            "independence_group": "manual-gtex",
            "shared_dataset": str(PROJECT_NS["dataset/other"]),
        },
    )

    results = list(check_independence_suspect_circular(ctx))

    assert any(result.rule == "independence.shared-dataset-refuted" for result in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_evidence_lines.py::test_authored_shared_dataset_refuted_only_when_all_group_members_are_checkable -q
```

Expected: FAIL because no `independence.shared-dataset-refuted` result exists.

- [ ] **Step 3: Implement narrow refutation warning**

Add this helper in `evidence_lines.py`:

```python
def _record_datasets(provenance, record) -> set[str]:
    return {str(value) for value in provenance.objects(record, SCI_NS.sharedDataset)}
```

In the B2 section of `check_independence_suspect_circular`, for each `DatasetIndependenceCommitment` and `DatasetIndependenceCandidate`, build a map:

```python
    b2_datasets_by_member: dict[str, set[str]] = defaultdict(set)
    if provenance is not None:
        for klass in (SCI_NS.DatasetIndependenceCommitment, SCI_NS.DatasetIndependenceCandidate):
            for record in provenance.subjects(RDF.type, klass):
                datasets = _record_datasets(provenance, record)
                for member in provenance.objects(record, SCI_NS.independenceMember):
                    b2_datasets_by_member[str(member)].update(datasets)
```

Then warn only when a line has authored `shared_dataset`, B2 has some dataset evidence for that same line, and the authored dataset is absent from B2's dataset set:

```python
    for member_uri, b2_datasets in sorted(b2_datasets_by_member.items()):
        member = URIRef(member_uri)
        authored_dataset = next((str(value) for value in provenance.objects(member, SCI_NS.sharedDataset)), None)
        if authored_dataset and b2_datasets and authored_dataset not in b2_datasets:
            yield Result(
                severity=Severity.WARN,
                path=None,
                line=None,
                message=f"{member_uri}: authored shared_dataset {authored_dataset!r} is not supported by dataset-derived independence records",
                rule="independence.shared-dataset-refuted",
                task=None,
            )
```

This is narrower than a full proof of absence, but it respects the design's "enough graph data" boundary by requiring B2 dataset evidence for that line before warning.

- [ ] **Step 4: Run validation tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_evidence_lines.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_evidence_lines.py
rtk git commit -m "feat: warn on refuted shared dataset groups"
```

## Task 7: Regression Coverage For Candidate Boundaries

**Files:**
- Modify: `science/tests/test_dataset_independence.py`
- Modify: `science/tests/test_belief_collect.py`

- [ ] **Step 1: Add boundary regression tests**

Append to `science/tests/test_dataset_independence.py`:

```python
def test_validation_source_mixed_with_dependence_is_candidate_not_commitment() -> None:
    knowledge, provenance, _target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "validation_source", "full", "a")
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "b")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert [(record.kind, record.reason) for record in records] == [("candidate", "validation")]


def test_cited_alone_is_candidate_only_and_never_commitment() -> None:
    knowledge, provenance, _target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "cited", "full", "a")
    _add_usage(provenance, line_b, dataset, "cited", "full", "b")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert [(record.kind, record.reason) for record in records] == [("candidate", "citation-only")]


def test_virtual_geneset_member_is_candidate_only_even_with_full_overlap() -> None:
    knowledge, provenance, _target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    virtual = PROJECT_NS["virtual/geneset-member/collection/set-a"]
    _add_usage(provenance, virtual, dataset, "analyzed", "full", "virtual")
    provenance.add((line_a, PROV.wasDerivedFrom, virtual))
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "line")

    records = derive_dataset_independence_records(knowledge, provenance)

    assert [(record.kind, record.reason) for record in records] == [("candidate", "virtual-row")]
```

Append to `science/tests/test_belief_collect.py`:

```python
def test_collect_evidence_units_ignores_dataset_independence_candidates_for_scoring() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    record = PROJECT_NS["dataset-independence/r1"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCandidate))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert [(unit.independence, unit.independence_group) for unit in units] == [(None, None), (None, None)]
```

- [ ] **Step 2: Run boundary tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py science/tests/test_belief_collect.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

Run:

```bash
rtk git add science/tests/test_dataset_independence.py science/tests/test_belief_collect.py
rtk git commit -m "test: cover dataset independence boundaries"
```

## Task 8: Documentation Status And Full Verification

**Files:**
- Modify: `docs/plans/2026-05-29-b2-dataset-independence-design.md`

- [ ] **Step 1: Update design status**

In `docs/plans/2026-05-29-b2-dataset-independence-design.md`, change:

```markdown
Status: design drafted; implementation plan next
```

to:

```markdown
Status: implementation ready; see `docs/plans/2026-05-29-b2-dataset-independence-plan.md`
```

- [ ] **Step 2: Run affected tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_independence.py science/tests/test_dataset_usage_materialize.py science/tests/test_belief_collect.py science/tests/test_belief_aggregate.py science/tests/test_belief_weights.py science/tests/test_belief_snapshot.py science/tests/test_belief_cli.py science/tests/validate/test_checks_evidence_lines.py -q
uv run --frozen pytest science/tests/validate -q
```

Expected: PASS.

- [ ] **Step 3: Run lint and whitespace checks**

Run:

```bash
uv run --frozen ruff check science/src/science_tool/graph/dataset_independence.py science/src/science_tool/graph/materialize.py science/src/science_tool/graph/belief.py science/src/science_tool/graph/belief_weights.py science/src/science_tool/validate/checks/evidence_lines.py science/tests/test_dataset_independence.py science/tests/test_dataset_usage_materialize.py science/tests/test_belief_collect.py science/tests/test_belief_aggregate.py science/tests/test_belief_weights.py science/tests/test_belief_snapshot.py science/tests/test_belief_cli.py science/tests/validate/test_checks_evidence_lines.py
rtk git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 4: Commit**

Run:

```bash
rtk git add docs/plans/2026-05-29-b2-dataset-independence-design.md
rtk git commit -m "docs: mark B2 implementation ready"
```

## Self-Review Checklist

- [ ] Spec coverage: usage reduction, most-dependent-wins, direct-vs-`bears_on` ancestry, virtual-row candidate boundary, candidate/commitment split, connected components, non-overloaded predicates, explicit belief merge precedence, validation severities, aggregation boundary, and all acceptance bullets are assigned to tasks above.
- [ ] Placeholder scan: this plan has no intentionally vague code-edit steps; every implementation step names exact files and concrete functions or replacements.
- [ ] Type consistency: `UsageFact`, `ReducedUsage`, `LineAncestor`, `DatasetIndependenceRecord`, `DerivedCommitmentMetadata`, `derive_dataset_independence_records`, `emit_dataset_independence_records`, and `committed_metadata_by_line` are introduced before later tasks use them.

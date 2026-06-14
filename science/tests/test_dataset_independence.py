from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.dataset_independence import (
    DERIVED_GROUP_PREFIX,
    ReducedUsage,
    UsageFact,
    derive_dataset_independence_records,
    emit_dataset_independence_records,
    read_dataset_usage_facts,
    reduce_usage_facts,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


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


def _add_sub_cohort(knowledge, child, parent):
    knowledge.add((child, SCI_NS.subCohortOf, parent))


def test_child_parent_full_overlap_pair_is_commitment():
    knowledge, provenance, target, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]
    _add_sub_cohort(knowledge, ppp, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [r.kind for r in records] == ["commitment"]
    assert records[0].members == frozenset({line_a, line_b})
    assert records[0].datasets == frozenset({ppp, ukb})


def test_sibling_full_overlap_pair_is_candidate_lineage_sibling():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]; nmr = PROJECT_NS["dataset/ukb-nmr"]
    _add_sub_cohort(knowledge, ppp, ukb); _add_sub_cohort(knowledge, nmr, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, nmr, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [(r.kind, r.reason) for r in records] == [("candidate", "lineage-sibling")]
    assert records[0].datasets == frozenset({ppp, nmr})


def test_child_parent_partial_is_candidate_partial_overlap():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]
    _add_sub_cohort(knowledge, ppp, ukb)
    _add_usage(provenance, line_a, ppp, "analyzed", "partial", "a")
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert [(r.kind, r.reason) for r in records] == [("candidate", "partial-overlap")]


def test_unrelated_datasets_stay_independent():
    knowledge, provenance, _t, line_a, line_b = _line_graph()
    ppp = PROJECT_NS["dataset/ukb-ppp"]; fin = PROJECT_NS["dataset/finngen"]
    _add_usage(provenance, line_a, ppp, "analyzed", "full", "a")
    _add_usage(provenance, line_b, fin, "analyzed", "full", "b")
    assert derive_dataset_independence_records(knowledge, provenance) == []


def test_grandparent_chain_full_overlap_is_commitment():
    knowledge, provenance, target, line_a, line_b = _line_graph()
    ukb = PROJECT_NS["dataset/uk-biobank"]; ppp = PROJECT_NS["dataset/ukb-ppp"]; sub = PROJECT_NS["dataset/ppp-sub"]
    _add_sub_cohort(knowledge, ppp, ukb); _add_sub_cohort(knowledge, sub, ppp)
    _add_usage(provenance, line_a, sub, "analyzed", "full", "a")   # grandchild
    _add_usage(provenance, line_b, ukb, "analyzed", "full", "b")   # grandparent
    assert [r.kind for r in derive_dataset_independence_records(knowledge, provenance)] == ["commitment"]


def test_identical_dataset_commitment_group_key_regression():
    knowledge, provenance, target, line_a, line_b = _line_graph()
    dataset = PROJECT_NS["dataset/gtex-v8"]
    _add_usage(provenance, line_a, dataset, "analyzed", "full", "a")
    _add_usage(provenance, line_b, dataset, "analyzed", "full", "b")
    records = derive_dataset_independence_records(knowledge, provenance)
    assert len(records) == 1
    assert records[0].kind == "commitment"
    assert records[0].independence_group == f"{DERIVED_GROUP_PREFIX}gtex-v8"
    assert records[0].datasets == frozenset({dataset})

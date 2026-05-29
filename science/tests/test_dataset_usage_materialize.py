from __future__ import annotations

import pytest
from rdflib import Graph, URIRef
from science_model.entities import Entity, PaperEntity
from science_model.packages.schema import AccessBlock, DatasetUsage, DerivationBlock

from science_tool.graph.store import PROJECT_NS, SCI_NS


def _base_entity_kwargs() -> dict[str, object]:
    return {
        "id": "observation:o1",
        "canonical_id": "observation:o1",
        "kind": "observation",
        "type": "observation",
        "title": "Observation",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "doc/observations/o1.md",
    }


def _paper() -> PaperEntity:
    return PaperEntity(
        id="paper:Adams2025",
        canonical_id="paper:Adams2025",
        kind="paper",
        type="paper",
        title="Adams",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/papers/Adams2025.md",
        datasets=["dataset:gtex-v8", "dataset:encode-v4"],
        dataset_usage=[DatasetUsage(ref="dataset:gtex-v8", role="cited")],
    )


def test_entity_usage_records_are_universal_for_authored_dataset_usage() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    entity = Entity(
        **_base_entity_kwargs(),
        dataset_usage=[DatasetUsage(ref="dataset:gtex-v8", role="validation_source", overlap="partial")],
    )

    records = usage_records_for_entity(entity)

    assert [(r.consumer_id, r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("observation:o1", "dataset:gtex-v8", "validation_source", "partial", "authored")
    ]


def test_paper_legacy_datasets_union_without_duplicate() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    records = usage_records_for_entity(_paper())

    assert [(r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("dataset:gtex-v8", "cited", "unknown", "authored"),
        ("dataset:encode-v4", "analyzed", "unknown", "paper.datasets"),
    ]


def test_paper_legacy_datasets_duplicate_refs_emit_once() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    paper = PaperEntity(
        id="paper:Adams2025",
        canonical_id="paper:Adams2025",
        kind="paper",
        type="paper",
        title="Adams",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/papers/Adams2025.md",
        datasets=["dataset:encode-v4", "dataset:encode-v4"],
        dataset_usage=[],
    )

    records = usage_records_for_entity(paper)

    assert [(r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("dataset:encode-v4", "analyzed", "unknown", "paper.datasets")
    ]


def test_derived_dataset_inputs_project_to_upstream_unknown() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    entity = Entity(
        id="dataset:derived",
        canonical_id="dataset:derived",
        kind="dataset",
        type="dataset",
        title="Derived",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="data/derived/datapackage.yaml",
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:w",
            workflow_run="workflow-run:r",
            git_commit="abc",
            config_snapshot="cfg",
            produced_at="2026-05-29",
            inputs=["dataset:raw"],
        ),
    )

    records = usage_records_for_entity(entity)

    assert [(r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("dataset:raw", "upstream", "unknown", "derivation.inputs")
    ]


def test_dataset_self_reference_is_materialization_error() -> None:
    from science_tool.graph.dataset_usage import DatasetUsageMaterializationError, usage_records_for_entity

    entity = Entity(
        id="dataset:self",
        canonical_id="dataset:self",
        kind="dataset",
        type="dataset",
        title="Self",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="data/self/datapackage.yaml",
        origin="external",
        access=AccessBlock(level="public", verified=True),
        dataset_usage=[DatasetUsage(ref="dataset:self", role="analyzed")],
    )

    with pytest.raises(DatasetUsageMaterializationError, match="self-referential"):
        usage_records_for_entity(entity)


def test_virtual_geneset_member_uri_uses_canonical_percent_encoding() -> None:
    from science_tool.graph.dataset_usage import virtual_geneset_member_uri

    uri = virtual_geneset_member_uri("dataset:reactome-v89", "A B/é")

    assert uri == URIRef(PROJECT_NS["virtual/geneset-member/reactome-v89/A%20B%2F%C3%A9"])


def test_add_usage_record_to_graph_preserves_absolute_virtual_consumer_uri() -> None:
    from science_tool.graph.dataset_usage import (
        DatasetUsageRecord,
        add_usage_record_to_graph,
        usage_node_uri,
        virtual_geneset_member_uri,
    )

    consumer = virtual_geneset_member_uri("dataset:reactome-v89", "MYC targets")
    record = DatasetUsageRecord(
        consumer_id=str(consumer),
        dataset_ref="dataset:gtex-v8",
        role="annotates",
        overlap="partial",
        source="geneset.members_resource",
        source_path="data/reactome/members.tsv",
        row_key="MYC targets",
    )
    graph = Graph()

    add_usage_record_to_graph(record, graph)

    assert (consumer, SCI_NS.hasDatasetUsage, usage_node_uri(record)) in graph


def test_usage_node_uri_is_deterministic_for_record_payload() -> None:
    from science_tool.graph.dataset_usage import DatasetUsageRecord, usage_node_uri

    record = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="validation_source",
        overlap="partial",
        source="authored",
        source_path="doc/observations/o1.md",
    )
    same_record = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="validation_source",
        overlap="partial",
        source="authored",
        source_path="doc/observations/o1.md",
    )
    changed_role = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="analyzed",
        overlap="partial",
        source="authored",
        source_path="doc/observations/o1.md",
    )

    assert usage_node_uri(record) == usage_node_uri(same_record)
    assert usage_node_uri(record) != usage_node_uri(changed_role)

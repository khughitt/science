from __future__ import annotations

import pytest
from rdflib import Dataset, Graph, Literal, Literal as RDFLiteral, URIRef
from rdflib.namespace import PROV, RDF
from science_model.entities import Entity, EntityType, PaperEntity
from science_model.packages.schema import AccessBlock, DatasetUsage, DerivationBlock

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import KnowledgeProfiles, ProjectSources
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _paper() -> PaperEntity:
    return PaperEntity(
        id="paper:Adams2025",
        canonical_id="paper:Adams2025",
        kind="paper",
        type=EntityType.PAPER,
        title="Adams",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/papers/Adams2025.md",
        datasets=["dataset:gtex-v8", "dataset:encode-v4"],
        dataset_usage=[DatasetUsage(ref="dataset:gtex-v8", role="cited")],
    )


def test_entity_usage_records_are_universal_for_authored_dataset_usage() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    entity = Entity(
        id="observation:o1",
        canonical_id="observation:o1",
        kind="observation",
        type=EntityType.OBSERVATION,
        title="Observation",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/observations/o1.md",
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
        type=EntityType.PAPER,
        title="Adams",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/papers/Adams2025.md",
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
        type=EntityType.DATASET,
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
        type=EntityType.DATASET,
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


def test_materialize_graph_rejects_dataset_usage_self_reference(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "self" / "datapackage.yaml",
        "self",
        "dataset_usage:\n"
        "  - ref: dataset:self\n"
        "    role: analyzed\n",
    )

    with pytest.raises(ValueError, match="self-referential"):
        materialize_graph(tmp_path)


def test_virtual_geneset_member_uri_uses_canonical_percent_encoding() -> None:
    from science_tool.graph.dataset_usage import virtual_geneset_member_uri

    uri = virtual_geneset_member_uri("dataset:reactome-v89", "A B/é")

    assert uri == URIRef(PROJECT_NS["virtual/geneset-member/reactome-v89/A%20B%2F%C3%A9"])


def test_virtual_member_uri_normalizes_nfc() -> None:
    from science_tool.graph.dataset_usage import virtual_geneset_member_uri

    composed = virtual_geneset_member_uri("dataset:reactome-v89", "é")
    decomposed = virtual_geneset_member_uri("dataset:reactome-v89", "e\u0301")

    assert composed == decomposed


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
    node = usage_node_uri(record)

    add_usage_record_to_graph(record, graph)

    assert (consumer, SCI_NS.hasDatasetUsage, node) in graph
    assert (node, RDF.type, SCI_NS.DatasetUsage) in graph
    assert (node, SCI_NS.dataset, URIRef(PROJECT_NS["dataset/gtex-v8"])) in graph
    assert (node, SCI_NS.usageRole, RDFLiteral("annotates")) in graph
    assert (node, SCI_NS.usageOverlap, RDFLiteral("partial")) in graph
    assert (node, SCI_NS.usageSource, RDFLiteral("geneset.members_resource")) in graph


def test_geneset_row_usage_rejects_virtual_uri_normalization_collision() -> None:
    from types import SimpleNamespace

    from science_tool.graph.dataset_usage import DatasetUsageMaterializationError, usage_records_for_geneset_rows

    rows = [
        SimpleNamespace(set_key="é", dataset_usage=()),
        SimpleNamespace(set_key="e\u0301", dataset_usage=()),
    ]

    with pytest.raises(DatasetUsageMaterializationError, match="collides"):
        usage_records_for_geneset_rows(
            collection_id="dataset:reactome-v89",
            source_path="data/reactome/datapackage.yaml",
            rows=rows,
        )


def test_usage_node_uri_is_deterministic_for_record_payload() -> None:
    from science_tool.graph.dataset_usage import DatasetUsageRecord, usage_node_uri

    record = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="validation_source",
        overlap="partial",
        source="authored",
        source_path="entities/observations/o1.md",
    )
    same_record = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="validation_source",
        overlap="partial",
        source="authored",
        source_path="entities/observations/o1.md",
    )
    changed_role = DatasetUsageRecord(
        consumer_id="observation:o1",
        dataset_ref="dataset:gtex-v8",
        role="analyzed",
        overlap="partial",
        source="authored",
        source_path="entities/observations/o1.md",
    )

    assert usage_node_uri(record) == usage_node_uri(same_record)
    assert usage_node_uri(record) != usage_node_uri(changed_role)


def test_parent_dataset_materializes_sub_cohort_of(tmp_path):
    from science_tool.graph.dataset_usage import project_entity_uri
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "uk-biobank" / "datapackage.yaml",
        "uk-biobank",
        "origin: external\n"
        "access:\n"
        "  level: controlled\n"
        "  verified: true\n",
    )
    _write_dataset(
        tmp_path / "data" / "ukb-ppp" / "datapackage.yaml",
        "ukb-ppp",
        "origin: external\n"
        "access:\n"
        "  level: controlled\n"
        "  verified: true\n"
        "parent_dataset: dataset:uk-biobank\n",
    )

    trig = materialize_graph(tmp_path)
    knowledge = _load_trig(trig).graph(PROJECT_NS["graph/knowledge"])

    child_uri = project_entity_uri("dataset:ukb-ppp")
    parent_uri = project_entity_uri("dataset:uk-biobank")
    assert (child_uri, SCI_NS.subCohortOf, parent_uri) in knowledge


def _write_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")


def _write_dataset(path, slug, extra):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "type: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        f"{extra}",
        encoding="utf-8",
    )


def _load_trig(path):
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def test_materialize_graph_emits_entity_usage_nodes(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:gtex-v8\n",
    )
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex-v8\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "---\n",
        encoding="utf-8",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    paper_uri = PROJECT_NS["paper/Adams2025".lower()]
    derived_uri = PROJECT_NS["dataset/derived"]
    gtex_uri = PROJECT_NS["dataset/gtex-v8"]
    paper_nodes = list(graph.objects(paper_uri, SCI_NS.hasDatasetUsage))
    derived_nodes = list(graph.objects(derived_uri, SCI_NS.hasDatasetUsage))

    assert len(paper_nodes) == 1
    assert len(derived_nodes) == 1
    assert (paper_nodes[0], RDF.type, SCI_NS.DatasetUsage) in graph
    assert (paper_nodes[0], SCI_NS.dataset, gtex_uri) in graph
    assert (paper_nodes[0], SCI_NS.usageRole, Literal("analyzed")) in graph
    assert (paper_nodes[0], SCI_NS.usageOverlap, Literal("full")) in graph
    assert (paper_nodes[0], SCI_NS.usageSource, Literal("authored")) in graph
    assert (derived_nodes[0], RDF.type, SCI_NS.DatasetUsage) in graph
    assert (derived_nodes[0], SCI_NS.dataset, gtex_uri) in graph
    assert (derived_nodes[0], SCI_NS.usageRole, Literal("upstream")) in graph
    assert (derived_nodes[0], SCI_NS.usageOverlap, Literal("unknown")) in graph
    assert (derived_nodes[0], SCI_NS.usageSource, Literal("derivation.inputs")) in graph


def test_materialize_graph_emits_dataset_independence_commitment(tmp_path) -> None:
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    prop_dir = tmp_path / "entities" / "propositions"
    prop_dir.mkdir(parents=True)
    (prop_dir / "p1.md").write_text(
        "---\n"
        "id: proposition:p1\n"
        "type: proposition\n"
        "title: P1\n"
        "status: active\n"
        "claim_layer: empirical_regularity\n"
        "identification_strength: observational\n"
        "proxy_directness: direct\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "---\n",
        encoding="utf-8",
    )
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    for slug in ("p1", "p2"):
        (paper_dir / f"{slug}.md").write_text(
            "---\n"
            f"id: paper:{slug}\n"
            "type: paper\n"
            f"title: {slug.upper()}\n"
            "status: active\n"
            "created: '2026-05-29'\n"
            "updated: '2026-05-29'\n"
            "dataset_usage:\n"
            "  - ref: dataset:gtex-v8\n"
            "    role: analyzed\n"
            "    overlap: full\n"
            "---\n",
            encoding="utf-8",
        )
    evidence_dir = tmp_path / "entities" / "evidence-lines"
    evidence_dir.mkdir(parents=True)
    for slug, paper in (("a", "p1"), ("b", "p2")):
        (evidence_dir / f"{slug}.md").write_text(
            "---\n"
            f"id: evidence-line:{slug}\n"
            "type: evidence-line\n"
            f"title: Evidence {slug.upper()}\n"
            "status: active\n"
            "stance: supports\n"
            "target: proposition:p1\n"
            f"source: paper:{paper}\n"
            "strength: moderate\n"
            "created: '2026-05-29'\n"
            "updated: '2026-05-29'\n"
            "---\n",
            encoding="utf-8",
        )

    graph_path = materialize_graph(tmp_path)
    provenance = _load_trig(graph_path).graph(PROJECT_NS["graph/provenance"])
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]

    assert (line_a, PROV.wasDerivedFrom, PROJECT_NS["paper/p1"]) in provenance
    assert (line_b, PROV.wasDerivedFrom, PROJECT_NS["paper/p2"]) in provenance

    records = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(records) == 1
    assert (
        records[0],
        SCI_NS.independenceGroup,
        Literal("dataset-derived:gtex-v8"),
    ) in provenance


@pytest.mark.parametrize(
    ("frontmatter", "field_name"),
    [
        (
            "dataset_usage:\n"
            "  - ref: dataset:gtex-v88\n"
            "    role: analyzed\n"
            "    overlap: full\n",
            "dataset_usage",
        ),
        ('datasets: ["dataset:gtex-v88"]\n', "datasets"),
    ],
)
def test_materialize_graph_rejects_unresolved_paper_usage_refs(tmp_path, frontmatter, field_name):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        f"{frontmatter}"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        materialize_graph(tmp_path)

    message = str(excinfo.value)
    assert "Cannot materialize graph with unresolved references" in message
    assert field_name in message
    assert "dataset:gtex-v88" in message
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_materialize_graph_rejects_unresolved_derivation_inputs(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:gtex-v88\n",
    )

    with pytest.raises(ValueError) as excinfo:
        materialize_graph(tmp_path)

    message = str(excinfo.value)
    assert "Cannot materialize graph with unresolved references" in message
    assert "derivation.inputs" in message
    assert "dataset:gtex-v88" in message
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_materialize_graph_canonicalizes_authored_usage_alias(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "aliases: [dataset:gtex]\n"
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        'datasets: ["dataset:gtex-v8"]\n'
        "---\n",
        encoding="utf-8",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])
    paper_uri = PROJECT_NS["paper/Adams2025".lower()]
    paper_nodes = list(graph.objects(paper_uri, SCI_NS.hasDatasetUsage))

    assert len(paper_nodes) == 1
    assert (paper_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (paper_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex"]) not in graph
    assert (paper_nodes[0], SCI_NS.usageSource, Literal("authored")) in graph


def test_materialize_graph_rejects_legacy_paper_dataset_bare_alias(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "aliases: [dataset:gtex, gtex]\n"
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        'datasets: ["gtex"]\n'
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        materialize_graph(tmp_path)

    message = str(excinfo.value)
    assert "Cannot materialize graph with unresolved references" in message
    assert "datasets" in message
    assert "gtex" in message


def test_materialize_graph_canonicalizes_derivation_input_alias(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "aliases: [dataset:gtex]\n"
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:gtex\n",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])
    derived_uri = PROJECT_NS["dataset/derived"]
    derived_nodes = list(graph.objects(derived_uri, SCI_NS.hasDatasetUsage))

    assert len(derived_nodes) == 1
    assert (derived_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (derived_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex"]) not in graph
    assert (derived_nodes[0], SCI_NS.usageSource, Literal("derivation.inputs")) in graph


def test_materialize_graph_rejects_dataset_self_reference_through_alias(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "aliases: [dataset:derived-alias]\n"
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:derived-alias\n",
    )

    with pytest.raises(ValueError, match="self-referential dataset usage"):
        materialize_graph(tmp_path)

    assert not (tmp_path / "knowledge" / "graph.trig").exists()


@pytest.mark.parametrize(
    ("frontmatter", "field_name"),
    [
        (
            "dataset_usage:\n"
            "  - ref: dataset:smith\n"
            "    role: analyzed\n"
            "    overlap: full\n",
            "dataset_usage",
        ),
        ('datasets: ["dataset:smith"]\n', "datasets"),
    ],
)
def test_materialize_graph_audits_paper_usage_refs_as_dataset_only(tmp_path, frontmatter, field_name):
    from science_tool.graph.materialize import materialization_audit, materialize_graph

    _write_project(tmp_path)
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Smith2024.md").write_text(
        "---\n"
        "id: paper:Smith2024\n"
        "type: paper\n"
        "title: Smith\n"
        "aliases: [dataset:smith]\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "---\n",
        encoding="utf-8",
    )
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        f"{frontmatter}"
        "---\n",
        encoding="utf-8",
    )

    rows, has_failures = materialization_audit(tmp_path)

    assert has_failures is True
    assert any(
        row["check"] == "invalid_dataset_reference"
        and row["field"] == field_name
        and row["target"] == "dataset:smith"
        for row in rows
    )
    with pytest.raises(ValueError) as excinfo:
        materialize_graph(tmp_path)

    message = str(excinfo.value)
    assert "Cannot materialize graph with unresolved references" in message
    assert field_name in message
    assert "dataset:smith" in message
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_materialize_graph_audits_derivation_inputs_as_dataset_only(tmp_path):
    from science_tool.graph.materialize import materialization_audit, materialize_graph

    _write_project(tmp_path)
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Smith2024.md").write_text(
        "---\n"
        "id: paper:Smith2024\n"
        "type: paper\n"
        "title: Smith\n"
        "aliases: [dataset:smith]\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "---\n",
        encoding="utf-8",
    )
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:smith\n",
    )

    rows, has_failures = materialization_audit(tmp_path)

    assert has_failures is True
    assert any(
        row["check"] == "invalid_dataset_reference"
        and row["field"] == "derivation.inputs"
        and row["target"] == "dataset:smith"
        for row in rows
    )
    with pytest.raises(ValueError) as excinfo:
        materialize_graph(tmp_path)

    message = str(excinfo.value)
    assert "Cannot materialize graph with unresolved references" in message
    assert "derivation.inputs" in message
    assert "dataset:smith" in message
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def _write_geneset_collection(root, *, with_members=True):
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "source_class: reference\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    if with_members:
        (dp_dir / "sets.csv").write_text(
            "set_key,name,member_ids,dataset_usage\n"
            'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:gtex-v8"",""role"":""set_definition_source"",""overlap"":""full""}]"\n',
            encoding="utf-8",
        )


def test_materialize_graph_emits_geneset_row_usage_nodes(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_geneset_collection(tmp_path)

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]
    nodes = list(graph.objects(row_uri, SCI_NS.hasDatasetUsage))

    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (nodes[0], SCI_NS.usageRole, Literal("set_definition_source")) in graph
    assert (nodes[0], SCI_NS.usageOverlap, Literal("full")) in graph
    assert (nodes[0], SCI_NS.usageSource, Literal("geneset.members_resource")) in graph


def test_materialize_graph_canonicalizes_geneset_row_usage_alias(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "aliases: [dataset:gtex]\n"
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_geneset_collection(tmp_path)
    (tmp_path / "data" / "reactome" / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:gtex"",""role"":""set_definition_source""}]"\n',
        encoding="utf-8",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]
    nodes = list(graph.objects(row_uri, SCI_NS.hasDatasetUsage))

    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex"]) not in graph


def test_materialize_graph_requires_geneset_members_resource(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_geneset_collection(tmp_path, with_members=False)

    with pytest.raises(RuntimeError, match="members_resource"):
        materialize_graph(tmp_path)


def test_geneset_usage_records_require_commons_members_resource(tmp_path):
    from science_tool.graph import materialize

    project_root = tmp_path / "project"
    project_root.mkdir()
    commons_entity = tmp_path / "commons" / "datasets" / "reactome-v89" / "entity.md"
    commons_entity.parent.mkdir(parents=True)
    commons_entity.write_text(
        "---\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "members_resource: sets\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n"
        "---\n",
        encoding="utf-8",
    )
    entity = Entity(
        id="dataset:reactome-v89",
        canonical_id="dataset:reactome-v89",
        kind="dataset",
        type=EntityType.DATASET,
        title="Reactome",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path=str(commons_entity),
    )
    sources = ProjectSources(
        project_name="demo",
        project_root=str(project_root),
        profiles=KnowledgeProfiles(local="local"),
        entities=[entity],
        entity_source_adapters={"dataset:reactome-v89": "commons-merged"},
        registry=EntityRegistry.with_core_types(),
    )
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases={})

    with pytest.raises(RuntimeError, match="members_resource"):
        list(materialize._geneset_usage_records(sources, resolver=resolver))


def test_materialize_graph_emits_commons_geneset_row_usage_nodes(tmp_path, monkeypatch):
    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder
    from science_tool.graph.materialize import materialize_graph

    commons_root = tmp_path / "commons"
    (commons_root / "datasets" / "rnaseq-example").mkdir(parents=True)
    (commons_root / "datasets" / "rnaseq-example" / "entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0\n"
        "id: dataset:rnaseq-example\n"
        "type: dataset\n"
        "title: RNA-seq\n"
        "version: 1.0.0\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access: {level: public, verified: true}\n"
        "---\n",
        encoding="utf-8",
    )
    (commons_root / "datasets" / "rnaseq-example" / "datapackage.yaml").write_text(
        "resources: []\n",
        encoding="utf-8",
    )
    reactome_dir = commons_root / "datasets" / "reactome-v89"
    reactome_dir.mkdir(parents=True)
    (reactome_dir / "entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "version: 1.0.0\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "source_class: reference\n"
        "access: {level: public, verified: true}\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "---\n",
        encoding="utf-8",
    )
    (reactome_dir / "datapackage.yaml").write_text(
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    (reactome_dir / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:rnaseq-example"",""role"":""set_definition_source""}]"\n',
        encoding="utf-8",
    )
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    _write_project(tmp_path)
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "dataset_usage:\n"
        "  - ref: dataset:reactome-v89\n"
        "    role: analyzed\n"
        "---\n",
        encoding="utf-8",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])
    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]
    nodes = list(graph.objects(row_uri, SCI_NS.hasDatasetUsage))

    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/rnaseq-example"]) in graph
    assert (nodes[0], SCI_NS.usageSource, Literal("geneset.members_resource")) in graph

    # §B4 provenance: a commons-merged geneset cites the datapackage (where the member
    # CSV lives), not the commons entity.md — locks the source_path=fm["_path"] behavior.
    from science_tool.graph import materialize as _materialize_mod
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases={})
    records = list(_materialize_mod._geneset_usage_records(sources, resolver=resolver))
    assert records
    assert all(r.source_path.endswith("datapackage.yaml") for r in records)


def test_materialization_audit_reports_unresolved_geneset_row_usage_refs(tmp_path):
    from science_tool.graph.materialize import materialization_audit

    _write_project(tmp_path)
    _write_geneset_collection(tmp_path)
    (tmp_path / "data" / "reactome" / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:missing"",""role"":""set_definition_source""}]"\n',
        encoding="utf-8",
    )

    rows, has_failures = materialization_audit(tmp_path)

    assert has_failures is True
    assert any(
        row["check"] == "unresolved_reference"
        and row["field"] == "members_resource.dataset_usage"
        and row["target"] == "dataset:missing"
        for row in rows
    )


def test_materialization_audit_reports_non_dataset_geneset_row_usage_refs(tmp_path):
    from science_tool.graph.materialize import materialization_audit

    _write_project(tmp_path)
    paper_dir = tmp_path / "entities" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Smith2024.md").write_text(
        "---\n"
        "id: paper:Smith2024\n"
        "type: paper\n"
        "title: Smith\n"
        "aliases: [dataset:smith]\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "---\n",
        encoding="utf-8",
    )
    _write_geneset_collection(tmp_path)
    (tmp_path / "data" / "reactome" / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:smith"",""role"":""set_definition_source""}]"\n',
        encoding="utf-8",
    )

    rows, has_failures = materialization_audit(tmp_path)

    assert has_failures is True
    assert any(
        row["check"] == "invalid_dataset_reference"
        and row["field"] == "members_resource.dataset_usage"
        and row["target"] == "dataset:smith"
        for row in rows
    )


def _write_promoted_geneset_collection(root):
    """Markdown owner at entities/datasets/reactome-v89.md shadowing geneset datapackage.

    This exercises the §B4 promoted-owner path: the markdown entity wins the owner
    column (adapter tag "markdown"), and the geneset resource metadata lives in the
    deferred datapackage.  Member extraction must still find the members CSV.
    """
    ds_dir = root / "entities" / "datasets"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "reactome-v89.md").write_text(
        "---\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "datapackage: data/reactome/datapackage.yaml\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n",
        encoding="utf-8",
    )
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "source_class: reference\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    (dp_dir / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:gtex-v8"",""role"":""set_definition_source"",""overlap"":""full""}]"\n',
        encoding="utf-8",
    )


def test_materialize_graph_emits_geneset_row_usage_nodes_for_promoted_markdown_owner(tmp_path):
    """Regression guard for footgun-a: geneset members must not silently disappear when
    the dataset entity has a markdown owner (adapter tag "markdown") that shadows the
    geneset datapackage.  Previously the adapter-tag gate skipped all such entities."""
    from science_tool.graph import materialize
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import load_project_sources

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_promoted_geneset_collection(tmp_path)

    # (1) Member edge must be present — same assertion as the orphan-datapackage test.
    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]
    nodes = list(graph.objects(row_uri, SCI_NS.hasDatasetUsage))

    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (nodes[0], SCI_NS.usageRole, Literal("set_definition_source")) in graph
    assert (nodes[0], SCI_NS.usageOverlap, Literal("full")) in graph
    assert (nodes[0], SCI_NS.usageSource, Literal("geneset.members_resource")) in graph

    # (2) Provenance must cite the datapackage, not the markdown owner file.
    sources = load_project_sources(tmp_path)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases={})
    records = list(materialize._geneset_usage_records(sources, resolver=resolver))

    assert len(records) == 1
    assert records[0].source_path == "data/reactome/datapackage.yaml"
    assert records[0].source_path != "entities/datasets/reactome-v89.md"


def _write_orphan_geneset_collection(root):
    """Orphan geneset datapackage (no entity-file owner) + members CSV.

    Same datapackage as _write_promoted_geneset_collection but WITHOUT a markdown
    owner, and carrying created/updated so the promoter writes a dated (non-sentinel)
    owner that strict-loads. This is the pre-promotion state the real promoter acts on.
    """
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "source_class: reference\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    (dp_dir / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:gtex-v8"",""role"":""set_definition_source"",""overlap"":""full""}]"\n',
        encoding="utf-8",
    )


def test_promote_orphans_then_materialize_preserves_geneset_members_end_to_end(tmp_path):
    """End-to-end cross-task guard: an ORPHAN geneset datapackage driven through the
    REAL promoter must still yield geneset member edges (provenance = datapackage) after
    re-materialization under the synthesized markdown owner. This exercises the seam the
    three Phase-2a tasks create — the per-task tests hand-build the post-promotion state;
    this one runs the actual promoter."""
    from science_tool.datapackage_promote import plan_orphan_promotions, promote_orphan_datapackages
    from science_tool.graph import materialize
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import load_project_sources

    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\naccess:\n  level: public\n  verified: true\n"
        "created: '2026-01-01'\nupdated: '2026-01-01'\n",
    )
    _write_orphan_geneset_collection(tmp_path)

    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]

    # Before promotion: the orphan datapackage owns the id; members extract.
    graph0 = _load_trig(materialize_graph(tmp_path)).graph(PROJECT_NS["graph/provenance"])
    assert list(graph0.objects(row_uri, SCI_NS.hasDatasetUsage))

    # Run the REAL promoter (gtex-v8 is also an orphan datapackage here, so both promote).
    report = promote_orphan_datapackages(tmp_path, apply=True)
    promoted = [p.canonical_id for p in report["promotions"]]
    assert "dataset:reactome-v89" in promoted
    assert (tmp_path / "entities" / "datasets" / "reactome-v89.md").exists()
    # Idempotent: every datapackage now defers, so nothing remains to promote.
    assert plan_orphan_promotions(tmp_path) == []

    # After promotion: the markdown owner wins; members must STILL extract.
    graph1 = _load_trig(materialize_graph(tmp_path)).graph(PROJECT_NS["graph/provenance"])
    nodes = list(graph1.objects(row_uri, SCI_NS.hasDatasetUsage))
    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph1

    sources = load_project_sources(tmp_path)
    assert sources.entity_source_adapters["dataset:reactome-v89"] == "markdown"
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases={})
    records = list(materialize._geneset_usage_records(sources, resolver=resolver))
    assert len(records) == 1
    assert records[0].source_path == "data/reactome/datapackage.yaml"

from __future__ import annotations

import pytest
from rdflib import Dataset, Graph, Literal, Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF
from science_model.entities import Entity, EntityType, PaperEntity
from science_model.packages.schema import AccessBlock, DatasetUsage, DerivationBlock

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
        file_path="doc/papers/Adams2025.md",
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
        file_path="doc/observations/o1.md",
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
    node = usage_node_uri(record)

    add_usage_record_to_graph(record, graph)

    assert (consumer, SCI_NS.hasDatasetUsage, node) in graph
    assert (node, RDF.type, SCI_NS.DatasetUsage) in graph
    assert (node, SCI_NS.dataset, URIRef(PROJECT_NS["dataset/gtex-v8"])) in graph
    assert (node, SCI_NS.usageRole, RDFLiteral("annotates")) in graph
    assert (node, SCI_NS.usageOverlap, RDFLiteral("partial")) in graph
    assert (node, SCI_NS.usageSource, RDFLiteral("geneset.members_resource")) in graph


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
    paper_dir = tmp_path / "doc" / "papers"
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
    paper_dir = tmp_path / "doc" / "papers"
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
    paper_dir = tmp_path / "doc" / "papers"
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


def test_materialize_graph_canonicalizes_legacy_paper_dataset_alias(tmp_path):
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
    paper_dir = tmp_path / "doc" / "papers"
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

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])
    paper_uri = PROJECT_NS["paper/Adams2025".lower()]
    paper_nodes = list(graph.objects(paper_uri, SCI_NS.hasDatasetUsage))

    assert len(paper_nodes) == 1
    assert (paper_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (paper_nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex"]) not in graph
    assert (paper_nodes[0], SCI_NS.usageSource, Literal("paper.datasets")) in graph


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
    paper_dir = tmp_path / "doc" / "papers"
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
    paper_dir = tmp_path / "doc" / "papers"
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


def test_materialize_graph_requires_geneset_members_resource(tmp_path):
    from science_tool.graph.materialize import materialize_graph

    _write_project(tmp_path)
    _write_geneset_collection(tmp_path, with_members=False)

    with pytest.raises(RuntimeError, match="members_resource"):
        materialize_graph(tmp_path)

from __future__ import annotations

from science_model.entities import EntityType, ProjectEntity
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument
from science_tool.graph.storage_adapters.aggregate import AggregateAdapter
from science_tool.graph.storage_adapters.bib import BibAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter


def _mk_entity(cid: str, kind: str) -> ProjectEntity:
    """Minimal valid ProjectEntity (all required base fields supplied)."""
    return ProjectEntity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=EntityType(kind),
        title="X",
        project="test",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="test",
    )


def test_base_defaults_are_inert() -> None:
    # TaskAdapter overrides none of the new policy → it exercises the base defaults.
    adapter = TaskAdapter()
    assert adapter.skip_core_on_missing_identity is False
    assert adapter.should_defer(already_owned=True) is False
    assert adapter.source_document(SourceRef(adapter_name="task", path="t.md"), {}) is None
    entity = _mk_entity("task:t1", "task")
    assert adapter.on_owner_declared(
        entity=entity, ref=SourceRef(adapter_name="task", path="t.md"), raw={}, kind="task"
    ) is None
    assert adapter.deferred_dataset_datapackage(
        entity=entity, ref=SourceRef(adapter_name="task", path="t.md")
    ) is None


def test_external_reference_defers_only_when_already_owned() -> None:
    adapter = BibAdapter()
    assert adapter.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert adapter.should_defer(already_owned=True) is True
    assert adapter.should_defer(already_owned=False) is False


def test_markdown_overrides() -> None:
    adapter = MarkdownAdapter()
    assert adapter.skip_core_on_missing_identity is True
    ref = SourceRef(adapter_name="markdown", path="entities/h1.md")
    raw = {"kind": "hypothesis", "title": "H1", "content": "body text"}
    doc = adapter.source_document(ref, raw)
    assert isinstance(doc, MarkdownSourceDocument)
    assert doc.path == "entities/h1.md"
    assert doc.body == "body text"
    assert "content" not in doc.frontmatter
    assert doc.frontmatter["kind"] == "hypothesis"


def test_datapackage_overrides() -> None:
    adapter = DatapackageAdapter()
    assert adapter.should_defer(already_owned=True) is True
    assert adapter.should_defer(already_owned=False) is False
    entity = _mk_entity("dataset:ds2", "dataset")
    ref = SourceRef(adapter_name="datapackage", path="data/ds2/datapackage.yaml")
    assert adapter.deferred_dataset_datapackage(entity=entity, ref=ref) == (
        "dataset:ds2",
        "data/ds2/datapackage.yaml",
    )


def test_aggregate_on_owner_declared_builds_row_meta() -> None:
    adapter = AggregateAdapter(local_profile="local")
    entity = _mk_entity("concept:coined", "concept")
    ref = SourceRef(adapter_name="aggregate", path="knowledge/sources/local/entities.yaml", line=0)
    meta = adapter.on_owner_declared(entity=entity, ref=ref, raw={"source_path": "x"}, kind="concept")
    assert isinstance(meta, AggregateRowMeta)
    assert meta.canonical_id == "concept:coined"
    assert meta.line == 0
    assert meta.kind == "concept"
    assert meta.source_path == "x"
    assert meta.primary_external_id is None

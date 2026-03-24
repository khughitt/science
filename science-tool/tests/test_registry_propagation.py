from __future__ import annotations

from datetime import date

from science_tool.graph.sources import SourceEntity
from science_tool.registry.propagation import (
    compute_propagations,
    write_propagated_entity,
)


def _source_entity(
    canonical_id: str,
    kind: str,
    title: str,
    related: list[str],
    source_path: str | None = None,
    tags: list[str] | None = None,
) -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="core",
        source_path=source_path or f"doc/{canonical_id.replace(':', '-')}.md",
        related=related,
        content_preview="Test content preview.",
        tags=tags or [],
    )


def test_propagation_finds_cross_project_content():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert len(actions) == 1
    assert actions[0].source_project == "proj-a"
    assert actions[0].target_project == "proj-b"


def test_propagation_with_different_local_ids():
    """Entities matched via ontology with different local IDs should propagate."""
    shared_pairs = [("gene:tp53", "gene:tumor-protein-53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [_source_entity("question:q2", "question", "Q about tumor protein", ["gene:tumor-protein-53"])],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert len(actions) == 2  # q1->proj-b and q2->proj-a


def test_propagation_skips_already_present():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert actions == []


def test_propagation_skips_sync_sourced_entities():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    q1 = _source_entity(
        "question:q1",
        "question",
        "Q about TP53",
        ["gene:tp53"],
        source_path="doc/sync/q1-from-proj-c.md",
        tags=["sync-propagated"],
    )
    project_sources = {"proj-a": [q1], "proj-b": []}
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert actions == []


def test_propagation_tag_gated_task():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    t1 = _source_entity("task:t1", "task", "Run analysis", ["gene:tp53"])
    t2 = _source_entity("task:t2", "task", "Shared task", ["gene:tp53"], tags=["cross-project"])
    project_sources = {"proj-a": [t1, t2], "proj-b": []}
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    ids = {a.entity.canonical_id for a in actions}
    assert "task:t1" not in ids
    assert "task:t2" in ids


def test_propagation_excludes_non_propagatable_types():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("workflow:w1", "workflow", "Pipeline", ["gene:tp53"])],
        "proj-b": [],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert actions == []


def test_write_propagated_entity(tmp_path):
    entity = _source_entity("question:q1-tp53", "question", "TP53 methylation?", ["gene:tp53"])
    output_path = write_propagated_entity(
        entity=entity,
        source_project="aging-clocks",
        target_project_root=tmp_path,
        sync_date=date(2026, 3, 23),
    )
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "sync_source:" in content
    assert 'project: "aging-clocks"' in content
    assert "sync-propagated" in content
    assert output_path.parent.name == "sync"

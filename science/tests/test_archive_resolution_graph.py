# science/tests/test_archive_resolution_graph.py
"""Graph: edges to archived ids materialize to a stub node; files not rehydrated (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path

rdflib = pytest.importorskip("rdflib")

from rdflib import Dataset  # noqa: E402
from rdflib.namespace import RDF  # noqa: E402

from science_tool.graph.store import PROJECT_NS, SCI_NS  # noqa: E402


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")


def _live(tmp_path: Path, body: str) -> None:
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-live.md").write_text(body, encoding="utf-8")


def _build_graph_text(tmp_path: Path) -> str:
    from science_tool.graph.materialize import materialize_graph
    out_path = materialize_graph(tmp_path, strict=False)
    return out_path.read_text(encoding="utf-8")


def _build_knowledge_graph(tmp_path: Path):
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(tmp_path, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(out_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def _entity_uri(ref: str):
    kind, slug = ref.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug}"]


def _proposition(tmp_path: Path, slug: str, title: str | None = None) -> None:
    d = tmp_path / "entities" / "propositions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "kind: proposition\n"
        f"title: {title or slug}\n"
        "---\n"
        "Claim.\n",
        encoding="utf-8",
    )


def test_archived_ref_edges_land_per_graph_and_stub(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(tmp_path, "---\nid: interpretation:0001-live\nkind: interpretation\ntitle: Live\n"
                    "related:\n  - interpretation:0002-gone\n"
                    "source_refs:\n  - interpretation:0002-gone\n"
                    "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-gone\n---\n")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               kind="interpretation", title="Gone v1", superseded_by="interpretation:0003-new",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0003-new",
               kind="interpretation", title="New", original_path="entities/interpretations/0003-new.md", archived_at="T1"))
    text = _build_graph_text(tmp_path)
    assert "0002-gone" in text                        # edge target present
    assert "related" in text                           # related -> skos:related (knowledge graph)
    assert "wasDerivedFrom" in text                    # source_refs -> prov:wasDerivedFrom (provenance graph)
    assert "supersedes" in text                        # relations[].target -> relation predicate
    assert "ArchivedEntity" in text                   # stub typed
    assert "Gone v1" in text                           # label from index
    assert "supersededBy" in text                      # superseded_by resolvable -> emitted


def test_unknown_ref_still_fails_audit(tmp_path: Path) -> None:
    # The archive fix resolves ACTIVE archived ids only — a genuine unknown ref
    # (neither live nor archived) must still fail the graph audit, NOT get a stub.
    _seed(tmp_path)
    _live(tmp_path, "---\nid: interpretation:0001-live\nkind: interpretation\ntitle: Live\n"
                    "related:\n  - interpretation:0099-typo\n---\n")
    with pytest.raises(ValueError, match="unresolved"):
        _build_graph_text(tmp_path)


def test_unreferenced_archived_scalar_lineage_emits_stub_and_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "kind: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="interpretation:0002-gone",
            kind="interpretation",
            title="Gone",
            superseded_by="interpretation:0003-new",
            original_path="entities/interpretations/0002-gone.md",
            archived_at="T1",
        ),
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="interpretation:0003-new",
            kind="interpretation",
            title="New",
            original_path="entities/interpretations/0003-new.md",
            archived_at="T1",
        ),
    )

    knowledge = _build_knowledge_graph(tmp_path)

    gone = _entity_uri("interpretation:0002-gone")
    new = _entity_uri("interpretation:0003-new")
    assert (gone, RDF.type, SCI_NS.ArchivedEntity) in knowledge
    assert (gone, SCI_NS.supersededBy, new) in knowledge
    assert (new, RDF.type, SCI_NS.ArchivedEntity) in knowledge


def test_unreferenced_archived_resynthesized_into_emits_all_lineage_edges(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "kind: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:broad",
            kind="proposition",
            title="Broad",
            status="superseded",
            resynthesized_into=["proposition:negative", "proposition:positive"],
            original_path="entities/propositions/broad.md",
            archived_at="T1",
        ),
    )
    _proposition(tmp_path, "negative", "Negative")
    _proposition(tmp_path, "positive", "Positive")

    knowledge = _build_knowledge_graph(tmp_path)

    broad = _entity_uri("proposition:broad")
    assert (broad, RDF.type, SCI_NS.ArchivedEntity) in knowledge
    assert set(knowledge.objects(broad, SCI_NS.supersededBy)) == {
        _entity_uri("proposition:negative"),
        _entity_uri("proposition:positive"),
    }


def test_archived_resynthesized_into_rejects_unknown_target(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "kind: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:broad",
            kind="proposition",
            title="Broad",
            resynthesized_into=["proposition:missing"],
            original_path="entities/propositions/broad.md",
            archived_at="T1",
        ),
    )

    with pytest.raises(ValueError, match="unknown archived lineage target proposition:missing"):
        _build_knowledge_graph(tmp_path)

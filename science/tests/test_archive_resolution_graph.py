# science/tests/test_archive_resolution_graph.py
"""Graph: edges to archived ids materialize to a stub node; files not rehydrated (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path

rdflib = pytest.importorskip("rdflib")


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


def test_archived_ref_edges_land_per_graph_and_stub(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(tmp_path, "---\nid: interpretation:0001-live\ntype: interpretation\ntitle: Live\n"
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
    _live(tmp_path, "---\nid: interpretation:0001-live\ntype: interpretation\ntitle: Live\n"
                    "related:\n  - interpretation:0099-typo\n---\n")
    with pytest.raises(ValueError, match="unresolved"):
        _build_graph_text(tmp_path)

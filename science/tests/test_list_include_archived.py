# science/tests/test_list_include_archived.py
"""list_entities(include_archived=True) merges archive-origin rows, tagged (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.entities import list_entities


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-live.md").write_text("---\nid: interpretation:0001-live\ntype: interpretation\ntitle: Live\nstatus: complete\n---\n", encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               kind="interpretation", title="Gone", status="superseded",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))


def test_default_excludes_archived(tmp_path: Path) -> None:
    _seed(tmp_path)
    ids = {row["id"] for row in list_entities(tmp_path)}
    assert ids == {"interpretation:0001-live"}


def test_include_archived_merges_tagged_rows(tmp_path: Path) -> None:
    _seed(tmp_path)
    rows = list_entities(tmp_path, include_archived=True)
    by_id = {r["id"]: r for r in rows}
    assert "interpretation:0002-gone" in by_id
    assert by_id["interpretation:0002-gone"].get("archived") is True
    assert by_id["interpretation:0001-live"].get("archived") in (False, None)


def test_related_with_include_archived_is_rejected(tmp_path: Path) -> None:
    from science_tool.entities import EntityCommandError
    _seed(tmp_path)
    with pytest.raises(EntityCommandError):
        list_entities(tmp_path, related="interpretation:0001-live", include_archived=True)

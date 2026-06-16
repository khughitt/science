"""ArchiveRow gains consolidation fields; _relocate_rows is the shared move primitive."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import (
    ArchiveRow,
    _relocate_rows,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)


def test_archive_row_has_consolidation_fields() -> None:
    row = ArchiveRow(op="archive", id="finding:0001-x", consolidated_into="synthesis:0001-d", digest_insight="X")
    assert row.consolidated_into == "synthesis:0001-d"
    assert row.digest_insight == "X"
    # round-trips through json
    assert ArchiveRow.model_validate_json(row.model_dump_json()).consolidated_into == "synthesis:0001-d"


def test_old_rows_without_new_fields_load_as_none() -> None:
    row = ArchiveRow.model_validate_json('{"op": "archive", "id": "finding:0001-x"}')
    assert row.consolidated_into is None
    assert row.digest_insight is None


def test_relocate_rows_moves_and_appends(tmp_path: Path) -> None:
    src_rel = "entities/findings/0001-x.md"
    src = tmp_path / src_rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nid: finding:0001-x\n---\nbody\n", encoding="utf-8")
    row = ArchiveRow(op="archive", id="finding:0001-x", kind="finding", original_path=src_rel,
                     consolidated_into="synthesis:0001-d", digest_insight="X")
    result = _relocate_rows(archive_index_path(tmp_path), tmp_path, [row], now="T1")
    assert result["applied"] == ["finding:0001-x"]
    assert not src.exists()
    assert (tmp_path / derive_archive_path(src_rel)).exists()
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id["finding:0001-x"].consolidated_into == "synthesis:0001-d"
    assert idx.active_by_id["finding:0001-x"].archived_at == "T1"

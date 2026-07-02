# science/tests/test_archive_index.py
"""Append-only archive index: fold, tombstone, resolvable ids (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import (
    ArchiveRow,
    append_row,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)


def test_archive_index_path(tmp_path: Path) -> None:
    assert archive_index_path(tmp_path) == tmp_path / "entities" / "_archive" / "archive-index.jsonl"


def test_derive_archive_path_mirrors_kind_subtree() -> None:
    assert derive_archive_path("entities/interpretations/0067-x.md") == "entities/_archive/interpretations/0067-x.md"


def test_append_and_fold_last_write_wins(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", kind="interpretation",
                             aliases=["int:x-old"], same_as=["interpretation:y"],
                             original_path="entities/interpretations/x.md", archived_at="T1"))
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:x"}
    # alias + same_as + canonical all resolve to canonical:
    assert idx.resolvable_ids()["int:x-old"] == "interpretation:x"
    assert idx.resolvable_ids()["interpretation:y"] == "interpretation:x"
    assert idx.resolvable_ids()["interpretation:x"] == "interpretation:x"


def test_tombstone_removes_from_active(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", kind="interpretation",
                             original_path="entities/interpretations/x.md", archived_at="T1"))
    append_row(p, ArchiveRow(op="unarchive", id="interpretation:x",
                             restored_path="entities/interpretations/x.md", unarchived_at="T2"))
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id == {}
    assert idx.resolvable_ids() == {}


def test_re_archive_after_unarchive_is_active(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    for op, ts in (("archive", "T1"), ("unarchive", "T2"), ("archive", "T3")):
        append_row(p, ArchiveRow(op=op, id="interpretation:x", kind="interpretation",
                                 original_path="entities/interpretations/x.md",
                                 archived_at=ts, restored_path="entities/interpretations/x.md", unarchived_at=ts))
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:x"}


def test_every_row_has_schema_version(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", original_path="entities/interpretations/x.md", archived_at="T1"))
    line = p.read_text(encoding="utf-8").splitlines()[0]
    import json
    assert json.loads(line)["schema_version"] == 1


def test_missing_index_loads_empty(tmp_path: Path) -> None:
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id == {}


def test_archive_row_round_trips_resynthesized_into() -> None:
    row = ArchiveRow(
        op="archive",
        id="proposition:broad",
        kind="proposition",
        status="superseded",
        original_path="entities/propositions/broad.md",
        resynthesized_into=["proposition:negative", "proposition:positive"],
    )

    loaded = ArchiveRow.model_validate_json(row.model_dump_json())

    assert loaded.resynthesized_into == ["proposition:negative", "proposition:positive"]


def test_archive_row_backfills_empty_resynthesized_into_for_existing_rows() -> None:
    loaded = ArchiveRow.model_validate_json('{"op": "archive", "id": "proposition:old"}')

    assert loaded.resynthesized_into == []

# science/tests/test_archive_verify.py
"""verify_archive reconciles fs<->index and detects alias collisions (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import ArchiveRow, append_row, archive_index_path, verify_archive


def _archived_file(tmp_path: Path, rel: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nid: x\n---\n", encoding="utf-8")


def test_clean_archive_has_no_problems(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               original_path="entities/interpretations/0001-x.md", archived_at="T1"))
    assert verify_archive(tmp_path, live_alias_space=set()) == []


def test_moved_but_unindexed_detected(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")  # file present, no row
    problems = verify_archive(tmp_path, live_alias_space=set())
    assert any("no active index row" in p for p in problems)


def test_indexed_but_missing_file_detected(tmp_path: Path) -> None:
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               original_path="entities/interpretations/0001-x.md", archived_at="T1"))  # no file moved
    problems = verify_archive(tmp_path, live_alias_space=set())
    assert any("file missing" in p for p in problems)


def test_alias_collision_with_live_space_detected(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               aliases=["shared-alias"], original_path="entities/interpretations/0001-x.md", archived_at="T1"))
    problems = verify_archive(tmp_path, live_alias_space={"shared-alias"})
    assert any("collides" in p for p in problems)


def test_archive_vs_archive_alias_collision_detected(tmp_path: Path) -> None:
    # Two ACTIVE archive rows share an alias/same_as -> archive-vs-archive collision.
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")
    _archived_file(tmp_path, "entities/_archive/interpretations/0002-y.md")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               aliases=["dup"], original_path="entities/interpretations/0001-x.md", archived_at="T1"))
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-y",
               same_as=["dup"], original_path="entities/interpretations/0002-y.md", archived_at="T1"))
    problems = verify_archive(tmp_path, live_alias_space=set())
    assert any("multiple active entries" in p for p in problems)

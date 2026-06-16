# science/tests/test_archive_mutators.py
"""archive_entities / unarchive_entities: relocate, index, reverse (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import (
    archive_entities,
    archive_index_path,
    load_archive_index,
    unarchive_entities,
)


def _write(root: Path, kind: str, name: str, fm: str) -> Path:
    d = root / "entities" / kind
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(fm, encoding="utf-8")
    return p


def _superseded(root: Path, kind: str, name: str, eid: str) -> Path:
    return _write(root, kind, name, f"---\nid: {eid}\ntype: {kind[:-1]}\nstatus: superseded\n---\nbody\n")


def test_report_lists_candidates_without_moving(tmp_path: Path) -> None:
    p = _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    report = archive_entities(tmp_path, apply=False, now="T1")
    assert [c["id"] for c in report["candidates"]] == ["interpretation:0001-x"]
    assert report["applied"] == []
    assert p.exists()  # not moved
    assert not archive_index_path(tmp_path).exists()


def test_apply_moves_and_indexes(tmp_path: Path) -> None:
    p = _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    report = archive_entities(tmp_path, apply=True, now="T1")
    assert report["applied"] == ["interpretation:0001-x"]
    assert not p.exists()
    moved = tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md"
    assert moved.exists()
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:0001-x"}
    assert idx.active_by_id["interpretation:0001-x"].reason == "status:superseded"
    assert idx.active_by_id["interpretation:0001-x"].original_path == "entities/interpretations/0001-x.md"


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    report2 = archive_entities(tmp_path, apply=True, now="T2")  # already relocated, not re-seen
    assert report2["candidates"] == []
    assert report2["applied"] == []


def test_only_hidden_statuses_are_candidates(tmp_path: Path) -> None:
    _write(tmp_path, "hypotheses", "0001-a", "---\nid: hypothesis:0001-a\ntype: hypothesis\nstatus: proposed\n---\n")
    _superseded(tmp_path, "interpretations", "0002-b", "interpretation:0002-b")
    report = archive_entities(tmp_path, apply=False, now="T1")
    assert [c["id"] for c in report["candidates"]] == ["interpretation:0002-b"]


def test_report_surfaces_inbound_live_refs(tmp_path: Path) -> None:
    # A live survivor references the superseded candidate via relations[].target.
    _superseded(tmp_path, "interpretations", "0002-old", "interpretation:0002-old")
    _write(tmp_path, "interpretations", "0003-new",
           "---\nid: interpretation:0003-new\ntype: interpretation\nstatus: complete\n"
           "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-old\n"
           "related:\n  - interpretation:0002-old\n---\n")
    report = archive_entities(tmp_path, apply=False, now="T1")
    cand = next(c for c in report["candidates"] if c["id"] == "interpretation:0002-old")
    assert cand["inbound_live_refs"] == ["interpretation:0003-new"]


def test_unarchive_restores_and_tombstones(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    report = unarchive_entities(tmp_path, ["interpretation:0001-x"], apply=True, now="T2")
    assert report["applied"] == ["interpretation:0001-x"]
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert load_archive_index(tmp_path).active_by_id == {}


def test_archive_collision_fails_before_overwriting(tmp_path: Path) -> None:
    # A stale file already sitting at the derived archive path must NOT be clobbered.
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    stale = tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale archived content\n", encoding="utf-8")
    with pytest.raises(Exception):
        archive_entities(tmp_path, apply=True, now="T1")
    # stale file untouched; live file not moved
    assert stale.read_text(encoding="utf-8") == "stale archived content\n"
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()


def test_unarchive_collision_fails_before_moving(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    # Recreate a live file at the original path -> restore must refuse.
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    with pytest.raises(Exception):
        unarchive_entities(tmp_path, ["interpretation:0001-x"], apply=True, now="T2")
    # archive copy still present, no tombstone applied
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    assert set(load_archive_index(tmp_path).active_by_id) == {"interpretation:0001-x"}

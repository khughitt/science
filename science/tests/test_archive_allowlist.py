"""Cohort-scoped archive: the allowlist is authoritative (Gap 2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveError, archive_entities


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    return tmp_path


def _entity(root: Path, kind_dir: str, stem: str, entity_id: str, kind: str, status: str) -> Path:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stem}.md"
    path.write_text(
        f"---\nid: {entity_id}\nkind: {kind}\ntitle: {stem}\nstatus: {status}\n---\n\nbody\n",
        encoding="utf-8",
    )
    return path


def test_allowlist_archives_only_enumerated_ids(tmp_path: Path) -> None:
    root = _project(tmp_path)
    target = _entity(root, "plans", "0001-target", "plan:0001-target", "plan", "superseded")
    bystander = _entity(root, "interpretations", "0002-by", "interpretation:0002-by", "interpretation", "superseded")

    report = archive_entities(root, ids=frozenset({"plan:0001-target"}), apply=True, now="2026-07-17T00:00:00Z")

    # applied is list[str] -- archive.py:207 via _relocate_rows -> dict[str, list[str]]
    assert report["applied"] == ["plan:0001-target"]
    assert [row["id"] for row in report["candidates"]] == ["plan:0001-target"]
    assert not target.exists()
    assert (root / "entities" / "_archive" / "plans" / "0001-target.md").exists()
    assert bystander.exists(), "out-of-cohort entity was archived"


def test_same_kind_same_status_entity_is_untouched(tmp_path: Path) -> None:
    """The test a --kind filter fails and an allowlist passes."""
    root = _project(tmp_path)
    _entity(root, "plans", "0001-in", "plan:0001-in", "plan", "superseded")
    excluded = _entity(root, "plans", "0002-out", "plan:0002-out", "plan", "superseded")
    excluded_bytes = excluded.read_bytes()

    archive_entities(root, ids=frozenset({"plan:0001-in"}), apply=True, now="2026-07-17T00:00:00Z")

    assert excluded.exists()
    assert excluded.read_bytes() == excluded_bytes


def test_zero_out_of_cohort_files_change(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _entity(root, "plans", "0001-in", "plan:0001-in", "plan", "superseded")
    _entity(root, "plans", "0002-out", "plan:0002-out", "plan", "superseded")
    _entity(root, "questions", "0003-q", "question:0003-q", "question", "superseded")

    before = {p: p.read_bytes() for p in (root / "entities").rglob("*.md") if p.name != "0001-in.md"}

    archive_entities(root, ids=frozenset({"plan:0001-in"}), apply=True, now="2026-07-17T00:00:00Z")

    after = {p: p.read_bytes() for p in (root / "entities").rglob("*.md") if p.name != "0001-in.md"}
    assert after == before


def test_dry_run_report_is_scoped_too(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _entity(root, "plans", "0001-in", "plan:0001-in", "plan", "superseded")
    _entity(root, "plans", "0002-out", "plan:0002-out", "plan", "superseded")

    report = archive_entities(root, ids=frozenset({"plan:0001-in"}), apply=False, now="2026-07-17T00:00:00Z")

    assert [row["id"] for row in report["candidates"]] == ["plan:0001-in"]
    assert report["applied"] == []


def test_unknown_id_fails_early(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _entity(root, "plans", "0001-in", "plan:0001-in", "plan", "superseded")

    with pytest.raises(ArchiveError, match="not found"):
        archive_entities(root, ids=frozenset({"plan:9999-ghost"}), apply=True, now="2026-07-17T00:00:00Z")


def test_id_with_non_archive_status_fails_early(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _entity(root, "plans", "0001-active", "plan:0001-active", "plan", "active")

    with pytest.raises(ArchiveError, match="status"):
        archive_entities(root, ids=frozenset({"plan:0001-active"}), apply=True, now="2026-07-17T00:00:00Z")


def test_allowlist_none_preserves_status_sweep_behaviour(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _entity(root, "plans", "0001-a", "plan:0001-a", "plan", "superseded")
    _entity(root, "plans", "0002-b", "plan:0002-b", "plan", "superseded")

    report = archive_entities(root, apply=False, now="2026-07-17T00:00:00Z")

    assert {row["id"] for row in report["candidates"]} == {"plan:0001-a", "plan:0002-b"}

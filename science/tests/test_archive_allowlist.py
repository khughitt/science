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


def _superseding_pair(root: Path, loser: str, winner: str, *, loser_status: str = "active") -> None:
    """A canonical supersession edge: relations[].predicate == sci:supersedes.

    Top-level `supersedes:` is NOT the canonical edge and is ignored by the
    graph builder -- see consolidation.py:13.
    """
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{loser}.md").write_text(
        f"---\nid: interpretation:{loser}\nkind: interpretation\ntitle: {loser}\nstatus: {loser_status}\n---\n\nbody\n",
        encoding="utf-8",
    )
    (d / f"{winner}.md").write_text(
        f"---\nid: interpretation:{winner}\nkind: interpretation\ntitle: {winner}\nstatus: complete\n"
        f"relations:\n  - predicate: sci:supersedes\n    target: interpretation:{loser}\n---\n\nbody\n",
        encoding="utf-8",
    )


def test_mark_superseded_allowlist_scopes_to_mark(tmp_path: Path) -> None:
    from science_tool.consolidation import mark_superseded

    root = _project(tmp_path)
    _superseding_pair(root, "0001-loser-a", "0002-winner-a")
    _superseding_pair(root, "0003-loser-b", "0004-winner-b")

    report = mark_superseded(root, ids=frozenset({"interpretation:0001-loser-a"}), apply=True)

    assert report["applied"] == ["interpretation:0001-loser-a"]
    marked = (root / "entities" / "interpretations" / "0001-loser-a.md").read_text(encoding="utf-8")
    untouched = (root / "entities" / "interpretations" / "0003-loser-b.md").read_text(encoding="utf-8")
    assert "status: superseded" in marked
    assert "status: active" in untouched, "out-of-cohort member was marked"


def test_mark_superseded_allowlist_also_scopes_to_repair(tmp_path: Path) -> None:
    """to_repair is written on every apply (consolidation.py:618) -- it must be scoped too."""
    from science_tool.consolidation import mark_superseded

    root = _project(tmp_path)
    # In cohort: needs the status stamp (to_mark).
    _superseding_pair(root, "0001-loser-a", "0002-winner-a")
    # OUT of cohort: already superseded, but its inverse is missing -> to_repair.
    _superseding_pair(root, "0003-loser-b", "0004-winner-b", loser_status="superseded")
    out_of_cohort = root / "entities" / "interpretations" / "0003-loser-b.md"
    before = out_of_cohort.read_bytes()

    report = mark_superseded(root, ids=frozenset({"interpretation:0001-loser-a"}), apply=True)

    assert report["repaired"] == [], "an out-of-cohort entity was repaired"
    assert out_of_cohort.read_bytes() == before, "an out-of-cohort entity was written"


def test_mark_superseded_allowlist_can_target_a_repair(tmp_path: Path) -> None:
    from science_tool.consolidation import mark_superseded

    root = _project(tmp_path)
    _superseding_pair(root, "0003-loser-b", "0004-winner-b", loser_status="superseded")

    report = mark_superseded(root, ids=frozenset({"interpretation:0003-loser-b"}), apply=True)

    assert report["repaired"] == ["interpretation:0003-loser-b"]
    text = (root / "entities" / "interpretations" / "0003-loser-b.md").read_text(encoding="utf-8")
    assert "superseded_by: interpretation:0004-winner-b" in text


def test_mark_superseded_unknown_id_fails_early(tmp_path: Path) -> None:
    from science_tool.consolidation import SupersessionError, mark_superseded

    root = _project(tmp_path)
    _superseding_pair(root, "0001-loser-a", "0002-winner-a")

    with pytest.raises(SupersessionError, match="not derivable"):
        mark_superseded(root, ids=frozenset({"interpretation:9999-ghost"}), apply=True)


def test_mark_superseded_dry_run_report_is_scoped(tmp_path: Path) -> None:
    from science_tool.consolidation import mark_superseded

    root = _project(tmp_path)
    _superseding_pair(root, "0001-loser-a", "0002-winner-a")
    _superseding_pair(root, "0003-loser-b", "0004-winner-b")

    report = mark_superseded(root, ids=frozenset({"interpretation:0001-loser-a"}), apply=False)

    assert report["to_mark"] == ["interpretation:0001-loser-a"]
    assert report["applied"] == []
    assert "interpretation:0003-loser-b" not in report["to_mark"]


def test_mark_superseded_dry_run_unknown_id_fails_early(tmp_path: Path) -> None:
    from science_tool.consolidation import SupersessionError, mark_superseded

    root = _project(tmp_path)
    _superseding_pair(root, "0001-loser-a", "0002-winner-a")

    with pytest.raises(SupersessionError, match="not derivable"):
        mark_superseded(root, ids=frozenset({"interpretation:9999-ghost"}), apply=False)

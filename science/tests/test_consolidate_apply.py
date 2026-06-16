"""apply_consolidation: dry-run + apply demote/relocate/index (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import derive_archive_path, load_archive_index
from science_tool.consolidate import ConsolidateError, apply_consolidation, scaffold_digest
from science_tool.entities import _atomic_replace_text, _parse_markdown_file, _render_markdown, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def _scaffolded(root: Path) -> str:
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    create_entity(root, "finding", "B", entity_id="finding:0002-b")
    scaffold_digest(root, digest_id="synthesis:0001-d",
                    member_ids=["finding:0001-a", "finding:0002-b"], title="Digest")
    return "synthesis:0001-d"


def test_dry_run_reports_without_mutation(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    report = apply_consolidation(root, digest, apply=False, now="T1")
    assert set(report["members"]) == {"finding:0001-a", "finding:0002-b"}
    assert report["applied"] == []
    assert set(report["destinations"]) == {"finding:0001-a", "finding:0002-b"}
    assert (root / "entities" / "findings" / "0001-a.md").exists()  # not moved
    assert not load_archive_index(root).active_by_id


def test_apply_demotes_relocates_indexes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    report = apply_consolidation(root, digest, apply=True, now="T1")
    assert set(report["applied"]) == {"finding:0001-a", "finding:0002-b"}
    # members relocated
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
    moved = root / derive_archive_path("entities/findings/0001-a.md")
    assert moved.exists()
    fm, _ = _parse_markdown_file(moved)
    assert fm["status"] == "archived"
    assert fm["consolidated_into"] == digest
    # index rows carry consolidation provenance
    idx = load_archive_index(root)
    row = idx.active_by_id["finding:0001-a"]
    assert row.consolidated_into == digest
    assert row.digest_insight == "A"
    # digest stays live, unmoved
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()


def test_apply_rejects_non_cluster_digest(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "synthesis", "Not a digest", entity_id="synthesis:0002-plain")
    with pytest.raises(ConsolidateError, match="cluster-digest"):
        apply_consolidation(root, "synthesis:0002-plain", apply=True, now="T1")


def test_apply_rejects_digest_without_consolidates_relation(tmp_path: Path) -> None:
    # A cluster-digest with no sci:consolidates relations -> fail loud.
    root = _project(tmp_path)
    create_entity(root, "synthesis", "Empty digest", entity_id="synthesis:0003-empty")
    path = root / "entities" / "synthesis" / "0003-empty.md"
    fm, body = _parse_markdown_file(path)
    fm["report_kind"] = "cluster-digest"  # but no relations
    _atomic_replace_text(path, _render_markdown(fm, body))
    with pytest.raises(ConsolidateError, match="no sci:consolidates"):
        apply_consolidation(root, "synthesis:0003-empty", apply=True, now="T1")


def test_apply_rejects_already_archived_member(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    apply_consolidation(root, digest, apply=True, now="T1")  # finding:0001-a now archived
    # A new digest cannot re-consolidate the already-archived member.
    create_entity(root, "finding", "C", entity_id="finding:0003-c")
    with pytest.raises(ConsolidateError, match="already archived"):
        scaffold_digest(root, digest_id="synthesis:0009-d2",
                        member_ids=["finding:0003-c", "finding:0001-a"], title="D2")

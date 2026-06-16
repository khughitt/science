"""scaffold_digest: mint a cluster-digest with typed consolidates relations (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.consolidate import ConsolidateError, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def _member(root: Path, kind: str, eid: str, title: str) -> None:
    create_entity(root, kind, title, entity_id=eid)


def test_scaffold_mints_digest_with_consolidates_relations(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    _member(root, "finding", "finding:0002-b", "B")
    report = scaffold_digest(
        root, digest_id="synthesis:0001-digest", member_ids=["finding:0001-a", "finding:0002-b"], title="Digest"
    )
    path = Path(report["digest_path"])
    assert path.exists()
    fm, _ = _parse_markdown_file(path)
    assert fm["report_kind"] == "cluster-digest"
    rels = fm["relations"]
    assert {r["target"] for r in rels} == {"finding:0001-a", "finding:0002-b"}
    assert all(r["predicate"] == "sci:consolidates" for r in rels)


def test_scaffold_rejects_unknown_member(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ConsolidateError, match="not a known live entity"):
        scaffold_digest(root, digest_id="synthesis:0001-digest", member_ids=["finding:9999-x"], title="D")


def test_scaffold_rejects_digest_id_among_members(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    with pytest.raises(ConsolidateError, match="digest id"):
        scaffold_digest(
            root, digest_id="synthesis:0001-digest",
            member_ids=["finding:0001-a", "synthesis:0001-digest"], title="D",
        )


def test_consolidatable_predicate_fails_loud_for_closed_vocab_without_archived(tmp_path: Path) -> None:
    from science_tool.consolidate import _is_consolidatable

    root = _project(tmp_path)
    assert _is_consolidatable(root, "finding") is True   # gained archived in Task 1
    assert _is_consolidatable(root, "paper") is False     # closed vocab ["active","retired"], no archived


def test_scaffold_rejects_digest_id_colliding_with_archived(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    # An entity with the chosen digest id is already ACTIVE in the archive index.
    append_row(
        archive_index_path(root),
        ArchiveRow(op="archive", id="synthesis:0001-digest", kind="synthesis",
                   original_path="entities/synthesis/0001-digest.md", archived_at="T1"),
    )
    with pytest.raises(ConsolidateError, match="collides with an archived"):
        scaffold_digest(root, digest_id="synthesis:0001-digest", member_ids=["finding:0001-a"], title="D")

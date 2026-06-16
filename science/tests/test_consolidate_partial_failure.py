"""apply_consolidation is per-member-atomic on a multi-member partial failure (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

import science_tool.consolidate as consolidate
from science_tool.archive import load_archive_index
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_second_member_failure_leaves_first_committed_second_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    create_entity(root, "finding", "B", entity_id="finding:0002-b")
    scaffold_digest(root, digest_id="synthesis:0001-d",
                    member_ids=["finding:0001-a", "finding:0002-b"], title="D")
    b_path = root / "entities" / "findings" / "0002-b.md"
    b_before = b_path.read_bytes()

    real = consolidate._relocate_rows

    def selective(index_path, project_root, rows, *, now):
        if any(r.id == "finding:0002-b" for r in rows):
            raise RuntimeError("boom on member 2")
        return real(index_path, project_root, rows, now=now)

    monkeypatch.setattr(consolidate, "_relocate_rows", selective)
    with pytest.raises(RuntimeError, match="boom on member 2"):
        apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")

    # member 1 committed: relocated + indexed
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
    assert set(load_archive_index(root).active_by_id) == {"finding:0001-a"}
    # member 2 restored: still live, original bytes, status not archived
    assert b_path.exists()
    assert b_path.read_bytes() == b_before
    fm, _ = _parse_markdown_file(b_path)
    assert fm["status"] != "archived"

"""apply_consolidation restores member bytes if relocation fails mid-apply (P4)."""
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


def test_append_failure_restores_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    scaffold_digest(root, digest_id="synthesis:0001-d", member_ids=["finding:0001-a"], title="D")
    member_path = root / "entities" / "findings" / "0001-a.md"
    before = member_path.read_bytes()

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    # Force the index append (inside _relocate_rows) to fail.
    monkeypatch.setattr(consolidate, "_relocate_rows", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")

    # Member file restored exactly (status reverted, still at original path).
    assert member_path.exists()
    assert member_path.read_bytes() == before
    fm, _ = _parse_markdown_file(member_path)
    assert fm["status"] != "archived"
    assert "consolidated_into" not in fm
    assert not load_archive_index(root).active_by_id

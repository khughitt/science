"""scaffold_digest removes the brand-new digest file if the rewrite/revalidate fails (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

import science_tool.consolidate as consolidate
from science_tool.consolidate import scaffold_digest
from science_tool.entities import create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_scaffold_removes_file_on_rewrite_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")

    def boom(*args, **kwargs):
        raise RuntimeError("rewrite failed")

    # Force the post-create frontmatter rewrite to fail.
    monkeypatch.setattr(consolidate, "_atomic_replace_text", boom)
    with pytest.raises(RuntimeError, match="rewrite failed"):
        scaffold_digest(root, digest_id="synthesis:0001-d", member_ids=["finding:0001-a"], title="D")

    # The brand-new digest file must have been removed (rollback).
    assert not (root / "entities" / "synthesis" / "0001-d.md").exists()

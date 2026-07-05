# science/tests/test_archive_resolution_validate.py
"""A live ref to an archived id resolves (not dangling); unknown still flagged (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.validate.checks.cross_references import check_cross_references
from science_tool.validate.context import ValidateContext


def _write(root: Path, kind: str, name: str, body: str) -> None:
    d = root / "entities" / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(body, encoding="utf-8")


def _ctx(tmp_path: Path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    return ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)


def test_ref_to_archived_id_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "interpretations", "0001-live",
           "---\nid: interpretation:0001-live\nkind: interpretation\nrelated:\n  - interpretation:0002-gone\n---\n")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))
    msgs = [r.message for r in check_cross_references(_ctx(tmp_path))]
    assert not any("0002-gone" in m and "not found" in m for m in msgs)


def test_unknown_ref_still_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "interpretations", "0001-live",
           "---\nid: interpretation:0001-live\nkind: interpretation\nrelated:\n  - interpretation:0099-typo\n---\n")
    msgs = [r.message for r in check_cross_references(_ctx(tmp_path))]
    assert any("0099-typo" in m and "not found" in m for m in msgs)

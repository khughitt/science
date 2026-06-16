# science/tests/test_entity_scan.py
"""Tests for the sole sanctioned recursive entities/ scanner (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.entity_scan import iter_entity_markdown


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nid: x\n---\n", encoding="utf-8")


def test_skips_archive_by_default(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_archive" / "hypotheses" / "0002-b.md")
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root)}
    assert found == {"hypotheses/0001-a.md"}


def test_include_archived_unskips_only_archive(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_archive" / "hypotheses" / "0002-b.md")
    _touch(root / "_scratch" / "0003-c.md")  # other _-prefixed: still skipped
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root, include_archived=True)}
    assert found == {"hypotheses/0001-a.md", "_archive/hypotheses/0002-b.md"}


def test_always_skips_other_underscore_segments(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_scratch" / "0002-b.md")
    _touch(root / "hypotheses" / "_wip" / "0003-c.md")
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root)}
    assert found == {"hypotheses/0001-a.md"}


def test_missing_root_yields_nothing(tmp_path: Path) -> None:
    assert list(iter_entity_markdown(tmp_path / "entities")) == []


def test_deterministic_sorted_order(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    for name in ("0003-c", "0001-a", "0002-b"):
        _touch(root / "hypotheses" / f"{name}.md")
    out = [p.name for p in iter_entity_markdown(root)]
    assert out == ["0001-a.md", "0002-b.md", "0003-c.md"]

"""Tests for MarkdownAdapter — single-entity markdown + YAML frontmatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.storage_adapters.markdown import MarkdownAdapter


def test_adapter_name() -> None:
    assert MarkdownAdapter().name == "markdown"


def test_discovers_under_default_scan_roots(tmp_path: Path) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nProse.\n',
        encoding="utf-8",
    )
    (tmp_path / "specs").mkdir(parents=True)
    (tmp_path / "specs" / "rq.md").write_text(
        '---\nid: "spec:rq"\ntype: "spec"\ntitle: "RQ"\n---\n',
        encoding="utf-8",
    )
    refs = MarkdownAdapter().discover(tmp_path)
    paths = {r.path for r in refs}
    assert "doc/hypotheses/h1.md" in paths
    assert "specs/rq.md" in paths
    for r in refs:
        assert r.adapter_name == "markdown"


def test_load_raw_returns_dispatchable_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    p = tmp_path / "doc" / "hypotheses" / "h1.md"
    p.write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nBody prose.\n',
        encoding="utf-8",
    )
    adapter = MarkdownAdapter()
    refs = adapter.discover(tmp_path)
    # load_raw resolves ref.path against cwd — chdir so it works.
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["canonical_id"] == "hypothesis:h1"
    assert raw["kind"] == "hypothesis"
    assert raw["title"] == "H1"
    assert raw["content"].startswith("Body prose")
    assert raw["file_path"] == "doc/hypotheses/h1.md"


def test_custom_scan_roots_honored(tmp_path: Path) -> None:
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom" / "c.md").write_text(
        '---\nid: "concept:c"\ntype: "concept"\ntitle: "C"\n---\n',
        encoding="utf-8",
    )
    refs = MarkdownAdapter(scan_roots=["custom"]).discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].path == "custom/c.md"


def test_returns_empty_when_no_markdown_files(tmp_path: Path) -> None:
    refs = MarkdownAdapter().discover(tmp_path)
    assert refs == []


def test_load_raw_handles_file_without_frontmatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A markdown file without frontmatter should still parse — returns minimal dict."""
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "no_fm.md").write_text("Just prose, no frontmatter.\n", encoding="utf-8")
    adapter = MarkdownAdapter()
    refs = adapter.discover(tmp_path)
    assert len(refs) == 1
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    # File has no kind/canonical_id — caller (registry) will reject with "missing kind".
    # Adapter returns the content and file_path at minimum.
    assert raw["content"].startswith("Just prose")
    assert raw["file_path"] == "doc/no_fm.md"

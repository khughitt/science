"""Tests for MarkdownProvider — behavior matches existing _load_markdown_entities."""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.markdown import MarkdownProvider


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=root,
        project_slug=root.name,
        local_profile="local",
    )


def test_markdown_provider_name_is_markdown() -> None:
    assert MarkdownProvider().name == "markdown"


def test_discovers_entities_under_default_scan_roots(tmp_path: Path) -> None:
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nProse.\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    ids = [e.canonical_id for e in out]
    assert "hypothesis:h1" in ids


def test_discovers_under_specs_root(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir(parents=True)
    (tmp_path / "specs" / "research-question.md").write_text(
        '---\nid: "spec:rq"\ntype: "spec"\ntitle: "RQ"\n---\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "spec:rq" for e in out)


def test_discovers_under_research_packages_root(tmp_path: Path) -> None:
    rp = tmp_path / "research" / "packages" / "lens" / "rp1"
    rp.mkdir(parents=True)
    (rp / "research-package.md").write_text(
        '---\nid: "research-package:rp1"\ntype: "research-package"\ntitle: "RP1"\n---\n',
        encoding="utf-8",
    )
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "research-package:rp1" for e in out)


def test_returns_empty_when_no_scan_roots_exist(tmp_path: Path) -> None:
    out = MarkdownProvider().discover(_ctx(tmp_path))
    assert out == []


def test_custom_scan_roots_are_honored(tmp_path: Path) -> None:
    (tmp_path / "custom" / "hypotheses").mkdir(parents=True)
    (tmp_path / "custom" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    p = MarkdownProvider(scan_roots=["custom"])
    out = p.discover(_ctx(tmp_path))
    assert any(e.canonical_id == "hypothesis:h1" for e in out)

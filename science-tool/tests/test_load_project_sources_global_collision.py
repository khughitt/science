"""Tests for the global collision check in load_project_sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.source_types import EntityIdCollisionError


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text("name: collide\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_no_collision_no_error(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    assert any(e.canonical_id == "hypothesis:h1" for e in sources.entities)


def test_collision_between_markdown_and_aggregate_raises(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "hypothesis:h1"\n    kind: "hypothesis"\n    title: "H1 dup"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    assert "hypothesis:h1" in str(exc_info.value)


def test_collision_between_resolver_and_specialized_parser_raises(tmp_path: Path) -> None:
    """A markdown entity and a task with the same canonical_id collide globally."""
    _seed_project(tmp_path)
    (tmp_path / "doc").mkdir(parents=True)
    (tmp_path / "doc" / "task-t01.md").write_text(
        '---\nid: "task:t01"\ntype: "task"\ntitle: "T01 from markdown"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01 from task DSL\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    assert "task:t01" in str(exc_info.value)

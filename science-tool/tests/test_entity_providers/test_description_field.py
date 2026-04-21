"""Tests for the SourceEntity.description field — per-provider prose sourcing."""

from __future__ import annotations

from pathlib import Path

import pytest


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: desc\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_markdown_entity_with_body_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nThis is the prose body.\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "hypothesis:h1"]
    assert es[0].description.strip() == "This is the prose body."


def test_aggregate_entry_with_description_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c1"\n    kind: "concept"\n    title: "C1"\n    profile: "local"\n    description: "Aggregate-entry prose."\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c1"]
    assert es[0].description == "Aggregate-entry prose."


def test_aggregate_entry_without_description_defaults_empty(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c2"\n    kind: "concept"\n    title: "C2"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c2"]
    assert es[0].description == ""


def test_task_description_populates_description(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nTask prose body.\n",
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "task:t01"]
    assert es[0].description == "Task prose body."


def test_description_field_defaults_empty_string() -> None:
    from science_tool.graph.source_types import SourceEntity

    se = SourceEntity(
        canonical_id="x:1",
        kind="x",
        title="x",
        profile="local",
        source_path="x.md",
        provider="markdown",
    )
    assert se.description == ""

"""Tests for the SourceEntity.provider field — every loader sets it explicitly."""

from __future__ import annotations

from pathlib import Path

import pytest


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: prov\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_markdown_provider_sets_markdown(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "hypothesis:h1"]
    assert len(es) == 1
    assert es[0].provider == "markdown"


def test_aggregate_provider_sets_aggregate(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        'entities:\n  - canonical_id: "concept:c1"\n    kind: "concept"\n    title: "C1"\n    profile: "local"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "concept:c1"]
    assert len(es) == 1
    assert es[0].provider == "aggregate"


def test_task_specialized_parser_sets_task(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "tasks").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "task:t01"]
    assert len(es) == 1
    assert es[0].provider == "task"


def test_model_source_specialized_parser_sets_model(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "models.yaml").write_text(
        'models:\n  - canonical_id: "model:m1"\n    title: "M1"\n    profile: "local"\n    source_path: "knowledge/sources/local/models.yaml"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "model:m1"]
    assert len(es) == 1
    assert es[0].provider == "model"


def test_parameter_source_specialized_parser_sets_parameter(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "parameters.yaml").write_text(
        'parameters:\n  - canonical_id: "parameter:p1"\n    title: "P1"\n    symbol: "p"\n    profile: "local"\n    source_path: "knowledge/sources/local/parameters.yaml"\n',
        encoding="utf-8",
    )
    from science_tool.graph.sources import load_project_sources

    es = [e for e in load_project_sources(tmp_path).entities if e.canonical_id == "parameter:p1"]
    assert len(es) == 1
    assert es[0].provider == "parameter"


def test_provider_field_is_required() -> None:
    """SourceEntity construction without provider is a Pydantic error."""
    from science_tool.graph.source_types import SourceEntity

    with pytest.raises(Exception):  # pydantic.ValidationError
        SourceEntity(canonical_id="x:1", kind="x", title="x", profile="local", source_path="x.md")  # type: ignore[call-arg]

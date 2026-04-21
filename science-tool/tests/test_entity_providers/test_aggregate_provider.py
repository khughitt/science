"""Tests for AggregateProvider — multi-type aggregate (entities.yaml) for Phase 2."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_tool.graph.entity_providers.aggregate import AggregateProvider
from science_tool.graph.entity_providers.base import EntityDiscoveryContext


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=root,
        project_slug=root.name,
        local_profile="local",
    )


def test_aggregate_provider_name_is_aggregate() -> None:
    assert AggregateProvider().name == "aggregate"


def test_returns_empty_when_no_entities_yaml(tmp_path: Path) -> None:
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert out == []


def test_loads_multi_type_entries_from_entities_yaml(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {"canonical_id": "paper:doe2024", "kind": "paper", "title": "Doe 2024", "profile": "local"},
                    {"canonical_id": "concept:c1", "kind": "concept", "title": "C1", "profile": "local"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    assert any("paper:" in i for i in ids)
    assert "concept:c1" in ids


def test_skips_non_dict_entries_silently(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    "not a dict",
                    {"canonical_id": "concept:c1", "kind": "concept", "title": "C1", "profile": "local"},
                    42,
                ]
            }
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    assert ids == {"concept:c1"}


def test_skips_when_top_level_not_a_list(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": "not-a-list"}), encoding="utf-8")
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert out == []


def test_single_type_aggregate_json_loads_topics(tmp_path: Path) -> None:
    """doc/topics/topics.json with multiple entries produces multiple topic entities."""
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.json").write_text(
        json.dumps(
            [
                {"id": "topic:rare-x", "title": "Rare X"},
                {"id": "topic:rare-y", "title": "Rare Y", "description": "Some prose."},
            ]
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    ids = {e.canonical_id for e in out}
    assert ids == {"topic:rare-x", "topic:rare-y"}
    rare_y = next(e for e in out if e.canonical_id == "topic:rare-y")
    assert rare_y.description == "Some prose."
    assert rare_y.kind == "topic"


def test_single_type_aggregate_yaml_works_same_as_json(tmp_path: Path) -> None:
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.yaml").write_text(
        yaml.safe_dump(
            [
                {"id": "topic:rare-z", "title": "Rare Z"},
            ]
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "topic:rare-z" for e in out)


def test_single_type_aggregate_kind_inferred_from_filename(tmp_path: Path) -> None:
    """topics.json → kind: topic, datasets.json → kind: dataset, etc."""
    ds_dir = tmp_path / "doc" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "datasets.json").write_text(
        json.dumps(
            [
                {"id": "dataset:agg1", "title": "Aggregate dataset 1"},
            ]
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    es = [e for e in out if e.canonical_id == "dataset:agg1"]
    assert len(es) == 1
    assert es[0].kind == "dataset"


def test_single_type_aggregate_coexists_with_markdown_in_same_directory(tmp_path: Path) -> None:
    """A markdown file and an aggregate file in the same dir both load (different IDs)."""
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "rich-topic.md").write_text(
        '---\nid: "topic:rich"\ntype: "topic"\ntitle: "Rich"\n---\nNarrative.\n',
        encoding="utf-8",
    )
    (topics_dir / "topics.json").write_text(
        json.dumps(
            [
                {"id": "topic:thin1", "title": "Thin 1"},
            ]
        ),
        encoding="utf-8",
    )
    out = AggregateProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "topic:thin1" for e in out)

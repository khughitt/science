"""Tests for AggregateProvider — multi-type aggregate (entities.yaml) for Phase 2."""

from __future__ import annotations

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

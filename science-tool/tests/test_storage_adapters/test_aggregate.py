"""Tests for AggregateAdapter — multi-entity + single-type (kind-from-filename) storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from science_tool.graph.storage_adapters.aggregate import AggregateAdapter


def test_adapter_name() -> None:
    assert AggregateAdapter(local_profile="local").name == "aggregate"


def test_multi_type_entities_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {"canonical_id": "paper:doe2024", "kind": "paper", "title": "Doe 2024"},
                    {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"},
                ]
            }
        ),
        encoding="utf-8",
    )
    a = AggregateAdapter(local_profile="local")
    refs = a.discover(tmp_path)
    assert len(refs) == 2
    monkeypatch.chdir(tmp_path)
    raws = [a.load_raw(r) for r in refs]
    kinds = {r["kind"] for r in raws}
    assert kinds == {"paper", "concept"}


def test_single_type_json_kind_from_filename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.json").write_text(
        json.dumps(
            [
                {"id": "topic:rare-x", "title": "Rare X"},
                {"id": "topic:rare-y", "title": "Rare Y"},
            ]
        ),
        encoding="utf-8",
    )
    a = AggregateAdapter(local_profile="local")
    refs = a.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raws = [a.load_raw(r) for r in refs]
    assert all(r["kind"] == "topic" for r in raws)
    ids = {r.get("id") or r.get("canonical_id") for r in raws}
    assert ids == {"topic:rare-x", "topic:rare-y"}


def test_skips_non_dict_entries(tmp_path: Path) -> None:
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": ["not-a-dict", {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"}, 42],
            }
        ),
        encoding="utf-8",
    )
    refs = AggregateAdapter(local_profile="local").discover(tmp_path)
    assert len(refs) == 1  # only the one valid dict entry


def test_returns_empty_when_no_aggregate_files(tmp_path: Path) -> None:
    assert AggregateAdapter(local_profile="local").discover(tmp_path) == []


def test_source_ref_line_carries_entry_index(tmp_path: Path) -> None:
    """For multi-entity files, SourceRef.line carries the list index for actionable errors."""
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    (src / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {"canonical_id": "concept:c1", "kind": "concept", "title": "C1"},
                    {"canonical_id": "concept:c2", "kind": "concept", "title": "C2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    refs = AggregateAdapter(local_profile="local").discover(tmp_path)
    assert refs[0].line == 0
    assert refs[1].line == 1


def test_single_type_yaml_also_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    a = AggregateAdapter(local_profile="local")
    refs = a.discover(tmp_path)
    assert len(refs) == 1
    monkeypatch.chdir(tmp_path)
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "topic"
    assert raw.get("id") == "topic:rare-z"

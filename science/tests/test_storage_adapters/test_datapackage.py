"""Tests for DatapackageAdapter — promoted datasets (datapackage.yaml IS the entity)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.storage_adapters.datapackage import (
    DatapackageAdapter,
    EntityDatapackageInvalidError,
)


def test_adapter_name() -> None:
    assert DatapackageAdapter().name == "datapackage"


def test_discovers_entity_profile_only(tmp_path: Path) -> None:
    # Non-entity datapackage (silently skipped):
    (tmp_path / "data" / "runtime-only").mkdir(parents=True)
    (tmp_path / "data" / "runtime-only" / "datapackage.yaml").write_text(
        yaml.safe_dump({"profiles": ["science-pkg-runtime-1.0"], "name": "r"}),
        encoding="utf-8",
    )
    # Entity-profile datapackage:
    (tmp_path / "data" / "myset").mkdir(parents=True)
    (tmp_path / "data" / "myset" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
                "name": "myset",
                "id": "dataset:myset",
                "type": "dataset",
                "title": "My set",
            }
        ),
        encoding="utf-8",
    )
    refs = DatapackageAdapter().discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].path.endswith("data/myset/datapackage.yaml")


def test_load_raw_extracts_entity_subset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data" / "myset").mkdir(parents=True)
    (tmp_path / "data" / "myset" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "myset",
                "id": "dataset:myset",
                "type": "dataset",
                "title": "My set",
                "description": "Set description.",
                "resources": [{"name": "r", "path": "r.csv"}],  # runtime-only
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    adapter = DatapackageAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "dataset"
    assert raw["canonical_id"] == "dataset:myset"
    assert raw["title"] == "My set"
    assert raw["origin"] == "external"
    # Runtime-only `resources` should NOT be in the raw entity dict:
    assert "resources" not in raw


def test_entity_profile_missing_id_raises(tmp_path: Path) -> None:
    (tmp_path / "data" / "broken").mkdir(parents=True)
    (tmp_path / "data" / "broken" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "broken",
                "title": "Broken",
            }
        ),
        encoding="utf-8",
    )
    adapter = DatapackageAdapter()
    with pytest.raises(EntityDatapackageInvalidError, match="id"):
        _ = adapter.discover(tmp_path)


def test_walks_results_directory(tmp_path: Path) -> None:
    (tmp_path / "results" / "wf" / "r1" / "out").mkdir(parents=True)
    (tmp_path / "results" / "wf" / "r1" / "out" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "wf-r1",
                "id": "dataset:wf-r1",
                "type": "dataset",
                "title": "WF R1",
            }
        ),
        encoding="utf-8",
    )
    refs = DatapackageAdapter().discover(tmp_path)
    assert any(r.path.endswith("results/wf/r1/out/datapackage.yaml") for r in refs)


def test_malformed_yaml_silently_skipped(tmp_path: Path) -> None:
    (tmp_path / "data" / "bad").mkdir(parents=True)
    (tmp_path / "data" / "bad" / "datapackage.yaml").write_text("not: valid: yaml: at: all", encoding="utf-8")
    assert DatapackageAdapter().discover(tmp_path) == []


def test_returns_empty_when_no_datapackages(tmp_path: Path) -> None:
    assert DatapackageAdapter().discover(tmp_path) == []

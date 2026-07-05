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
                "kind": "dataset",
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
                "kind": "dataset",
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
                "kind": "dataset",
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


def test_load_raw_surfaces_a1_taxonomy_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A promoted reference-collection member (datapackage-backed) declaring A1 fields.
    (tmp_path / "data" / "refcoll").mkdir(parents=True)
    (tmp_path / "data" / "refcoll" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "refcoll",
                "id": "dataset:refcoll",
                "kind": "dataset",
                "title": "Ref coll",
                "origin": "external",
                "access": {"level": "public", "verified": True},
                "source_class": "reference",
                "dataset_usage": [
                    {"ref": "dataset:src", "role": "set_definition_source", "overlap": "full"}
                ],
            }
        ),
        encoding="utf-8",
    )
    adapter = DatapackageAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["source_class"] == "reference"
    assert raw["dataset_usage"][0]["role"] == "set_definition_source"


def test_load_raw_surfaces_derived_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data" / "am").mkdir(parents=True)
    (tmp_path / "data" / "am" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "am",
                "id": "dataset:am",
                "kind": "dataset",
                "title": "AlphaMissense",
                "origin": "external",
                "access": {"level": "public", "verified": True},
                "source_class": "derived",
                "derived_kind": "model_output",
            }
        ),
        encoding="utf-8",
    )
    adapter = DatapackageAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["source_class"] == "derived"
    assert raw["derived_kind"] == "model_output"


def test_datapackage_adapter_preserves_geneset_extension_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "data" / "reactome").mkdir(parents=True)
    (tmp_path / "data" / "reactome" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:reactome-v89",
                "kind": "dataset",
                "title": "Reactome v89",
                "status": "active",
                "origin": "external",
                "tier": "use-now",
                "member_key_column": "set_key",
                "members_resource": "sets",
                "n_sets": 1,
                "set_size_summary": {"min": 2, "median": 2, "max": 2},
                "identifier_space": {"tier": "gene", "namespace": "hgnc_id"},
                "resources": [{"name": "sets", "path": "sets.csv"}],
            }
        ),
        encoding="utf-8",
    )
    adapter = DatapackageAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)

    raw = adapter.load_raw(refs[0])

    assert raw["member_key_column"] == "set_key"
    assert raw["members_resource"] == "sets"
    assert raw["n_sets"] == 1
    assert raw["set_size_summary"]["median"] == 2
    assert raw["identifier_space"]["namespace"] == "hgnc_id"

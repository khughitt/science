"""End-to-end tests for the unified load flow (registry + adapters)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entities import DatasetEntity, Entity, ProjectEntity, TaskEntity

from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.sources import load_project_sources


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\n",
        encoding="utf-8",
    )


def test_load_produces_typed_entity_instances(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    assert isinstance(by_id["hypothesis:h1"], ProjectEntity)
    assert isinstance(by_id["task:t01"], TaskEntity)


def test_load_produces_dataset_entity_for_datapackage(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "data" / "ds1").mkdir(parents=True)
    (tmp_path / "data" / "ds1" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "ds1",
                "id": "dataset:ds1",
                "type": "dataset",
                "title": "DS1",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:ds1")
    assert isinstance(ds, DatasetEntity)
    assert ds.origin == "external"


def test_global_identity_collision_across_adapters(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "x",
                "id": "dataset:x",
                "type": "dataset",
                "title": "X dp",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EntityIdentityCollisionError, match="dataset:x"):
        load_project_sources(tmp_path)


def test_all_entities_inherit_from_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    assert all(isinstance(e, Entity) for e in sources.entities)


def test_load_normalizes_legacy_parameter_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "parameters").mkdir(parents=True)
    (tmp_path / "doc" / "parameters" / "p1.md").write_text(
        '---\nid: "parameter:kcat"\ntype: "parameter"\ntitle: "kcat"\n---\n',
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    assert "parameter:kcat" in by_id
    assert by_id["parameter:kcat"].kind == "canonical_parameter"
    assert isinstance(by_id["parameter:kcat"], ProjectEntity)

"""Tests for DatapackageDirectoryProvider — entity-flavored datapackages only."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.datapackage_directory import DatapackageDirectoryProvider
from science_tool.graph.source_types import EntityDatapackageInvalidError


def _ctx(root: Path) -> EntityDiscoveryContext:
    return EntityDiscoveryContext(project_root=root, project_slug=root.name, local_profile="local")


def test_provider_name_is_datapackage_directory() -> None:
    assert DatapackageDirectoryProvider().name == "datapackage-directory"


def test_returns_empty_when_no_datapackages_exist(tmp_path: Path) -> None:
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []


def test_skips_non_entity_datapackages(tmp_path: Path) -> None:
    """A datapackage WITHOUT science-pkg-entity-1.0 in profiles is silently ignored."""
    dp_dir = tmp_path / "data" / "non-entity"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "non-entity",
                "resources": [{"name": "r", "path": "r.csv"}],
            }
        ),
        encoding="utf-8",
    )
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []


def test_loads_entity_profile_datapackage(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "myset"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
                "name": "myset",
                "id": "dataset:myset",
                "type": "dataset",
                "title": "My set",
                "description": "Frictionless top-level description.",
                "resources": [{"name": "r", "path": "r.csv"}],
            }
        ),
        encoding="utf-8",
    )
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert len(out) == 1
    assert out[0].canonical_id == "dataset:myset"
    assert out[0].kind == "dataset"
    assert out[0].title == "My set"
    assert out[0].description == "Frictionless top-level description."
    assert out[0].provider == "datapackage-directory"


def test_walks_results_directory_too(tmp_path: Path) -> None:
    dp_dir = tmp_path / "results" / "wf" / "r1" / "out"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "wf-r1-out",
                "id": "dataset:wf-r1-out",
                "type": "dataset",
                "title": "WF r1 out",
                "resources": [{"name": "r", "path": "r.csv"}],
            }
        ),
        encoding="utf-8",
    )
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert any(e.canonical_id == "dataset:wf-r1-out" for e in out)


def test_entity_profile_datapackage_missing_id_raises(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "broken"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "broken",
                "resources": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EntityDatapackageInvalidError) as exc_info:
        DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    msg = str(exc_info.value)
    assert "broken" in msg
    assert "id" in msg


def test_entity_profile_datapackage_missing_type_raises(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "broken2"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "broken2",
                "id": "dataset:b2",
                "title": "Broken 2",
                "resources": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EntityDatapackageInvalidError):
        DatapackageDirectoryProvider().discover(_ctx(tmp_path))


def test_malformed_yaml_in_non_entity_datapackage_silently_ignored(tmp_path: Path) -> None:
    """We can't determine if malformed YAML was an entity datapackage; conservative skip."""
    dp_dir = tmp_path / "data" / "bad-yaml"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text("not: valid: yaml: at: all", encoding="utf-8")
    out = DatapackageDirectoryProvider().discover(_ctx(tmp_path))
    assert out == []

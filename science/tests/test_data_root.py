from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from science_tool.data_root import (
    DataRootConfigError,
    discover_project_root,
    logical_data_dir_to_physical,
    resolve_data_root,
)
from science_tool.project_config import ProjectConfig, load_project_config


def _write_project(root: Path, extra: dict | None = None) -> None:
    payload = {"name": "Demo", "id": "demo"}
    if extra:
        payload.update(extra)
    (root / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_nearest_project_root_reexported(tmp_path: Path) -> None:
    from science_tool.data_root import nearest_project_root

    (tmp_path / "science.yaml").write_text("id: p\n", encoding="utf-8")
    assert nearest_project_root(tmp_path) == tmp_path


def test_default_root_is_project_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(tmp_path) == tmp_path.resolve() / "data"


def test_env_root_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": str(tmp_path / "project-data")}})
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("SCIENCE_DATA_ROOT", str(tmp_path / "env-data"))
    assert resolve_data_root(tmp_path) == tmp_path / "env-data"


def test_relative_env_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    monkeypatch.setenv("SCIENCE_DATA_ROOT", "relative-data")
    with pytest.raises(DataRootConfigError, match="SCIENCE_DATA_ROOT.*absolute"):
        resolve_data_root(tmp_path)


def test_project_relative_root_is_project_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_project(project, {"data": {"root": "bulk"}})
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(project) == project.resolve() / "bulk"


def test_global_root_is_parent_plus_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"id": "project-id"})
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(
        yaml.safe_dump({"data": {"root": str(tmp_path / "bulk-parent")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(tmp_path) == tmp_path / "bulk-parent" / "project-id"


def test_relative_global_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(yaml.safe_dump({"data": {"root": "relative"}}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    with pytest.raises(DataRootConfigError, match="global data.root.*absolute"):
        resolve_data_root(tmp_path)


def test_project_data_config_forbids_typos_but_top_level_extra_survives() -> None:
    config = ProjectConfig.model_validate({"name": "Demo", "unknown": "kept"})
    assert config.model_extra == {"unknown": "kept"}
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"name": "Demo", "data": {"rot": "/tmp/x"}})


def test_load_project_config_parses_data_root(tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": "bulk"}})
    config = load_project_config(tmp_path)
    assert config.data is not None
    assert config.data.root == Path("bulk")


def test_logical_data_dir_to_physical_uses_leaf_name(tmp_path: Path) -> None:
    assert logical_data_dir_to_physical(tmp_path / "bulk", Path("data/processed")) == (
        tmp_path / "bulk" / "processed"
    )


def test_discover_project_root_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_project(project)
    monkeypatch.setenv("SCIENCE_PROJECT_ROOT", str(project))
    assert discover_project_root() == project.resolve()


def test_discover_project_root_walks_up(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "a" / "b"
    nested.mkdir(parents=True)
    _write_project(project)
    assert discover_project_root(nested) == project.resolve()


def test_discover_project_root_falls_back_without_science_yaml(tmp_path: Path) -> None:
    assert discover_project_root(tmp_path) == tmp_path.resolve()


def test_project_config_path_reexported():
    from science_tool.data_root import PROJECT_CONFIG_FILENAME, project_config_path

    assert PROJECT_CONFIG_FILENAME == "science.yaml"
    assert project_config_path(Path("/x/y")) == Path("/x/y/science.yaml")

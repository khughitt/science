from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.registry.config import (
    GlobalConfig,
    RegisteredProject,
    SyncSettings,
    ensure_registered,
    load_global_config,
    save_global_config,
)


def test_global_config_defaults():
    cfg = GlobalConfig()
    assert cfg.sync.stale_after_days == 7
    assert cfg.projects == []


def test_global_config_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    cfg = GlobalConfig(
        sync=SyncSettings(stale_after_days=14),
        projects=[
            RegisteredProject(path="/home/user/proj-a", name="proj-a", registered=date(2026, 3, 15)),
        ],
    )
    save_global_config(cfg, config_path)
    loaded = load_global_config(config_path)
    assert loaded.sync.stale_after_days == 14
    assert len(loaded.projects) == 1
    assert loaded.projects[0].name == "proj-a"


def test_load_global_config_missing_file(tmp_path):
    cfg = load_global_config(tmp_path / "missing.yaml")
    assert cfg.projects == []
    assert cfg.sync.stale_after_days == 7


def test_ensure_registered_adds_new_project(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(
        project_root=Path("/home/user/proj-a"),
        project_name="proj-a",
        config_path=config_path,
    )
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 1
    assert cfg.projects[0].name == "proj-a"
    assert cfg.projects[0].path == "/home/user/proj-a"


def test_ensure_registered_idempotent(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 1


def test_ensure_registered_multiple_projects(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(Path("/home/user/proj-a"), "proj-a", config_path)
    ensure_registered(Path("/home/user/proj-b"), "proj-b", config_path)
    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 2
    names = {p.name for p in cfg.projects}
    assert names == {"proj-a", "proj-b"}

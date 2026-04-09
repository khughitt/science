from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.registry.config import (
    GlobalConfig,
    RegisteredProject,
    SyncSettings,
    ensure_registered,
    load_global_config,
    prune_missing_projects,
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


def test_ensure_registered_uses_runtime_science_config_dir(tmp_path, monkeypatch):
    from science_tool.registry import config as registry_config

    project_root = tmp_path / "proj-a"
    project_root.mkdir()

    legacy_dir = tmp_path / "legacy-config"
    isolated_dir = tmp_path / "isolated-config"
    monkeypatch.setattr(registry_config, "DEFAULT_CONFIG_PATH", legacy_dir / "config.yaml")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(isolated_dir))

    registry_config.ensure_registered(project_root, "proj-a")

    isolated_config_path = isolated_dir / "config.yaml"
    assert isolated_config_path.exists()
    assert not (legacy_dir / "config.yaml").exists()

    cfg = registry_config.load_global_config(isolated_config_path)
    assert len(cfg.projects) == 1
    assert cfg.projects[0].path == str(project_root.resolve())


def test_prune_missing_projects_removes_nonexistent(tmp_path):
    """Prune removes projects whose paths don't exist."""
    config_path = tmp_path / "config.yaml"

    # Create one real project with science.yaml
    real_project = tmp_path / "real-proj"
    real_project.mkdir()
    (real_project / "science.yaml").write_text("name: real-proj\n")

    cfg = GlobalConfig(
        projects=[
            RegisteredProject(path=str(real_project), name="real-proj", registered=date(2026, 3, 15)),
            RegisteredProject(path="/nonexistent/fake-proj", name="fake-proj", registered=date(2026, 3, 15)),
        ],
    )
    save_global_config(cfg, config_path)

    pruned = prune_missing_projects(config_path)
    assert pruned == ["/nonexistent/fake-proj"]

    reloaded = load_global_config(config_path)
    assert len(reloaded.projects) == 1
    assert reloaded.projects[0].name == "real-proj"


def test_prune_missing_projects_no_change(tmp_path):
    """Prune is a no-op when all projects exist."""
    config_path = tmp_path / "config.yaml"

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "science.yaml").write_text("name: proj\n")

    cfg = GlobalConfig(
        projects=[RegisteredProject(path=str(proj), name="proj", registered=date(2026, 3, 15))],
    )
    save_global_config(cfg, config_path)

    pruned = prune_missing_projects(config_path)
    assert pruned == []

    reloaded = load_global_config(config_path)
    assert len(reloaded.projects) == 1

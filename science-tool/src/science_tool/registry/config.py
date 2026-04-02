"""Global configuration and project auto-registration for Science multi-project sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

SCIENCE_CONFIG_DIR = Path.home() / ".config" / "science"
DEFAULT_CONFIG_PATH = SCIENCE_CONFIG_DIR / "config.yaml"


class SyncSettings(BaseModel):
    """Settings controlling sync behavior."""

    stale_after_days: int = 7


class RegisteredProject(BaseModel):
    """A project registered for cross-project sync."""

    path: str
    name: str
    registered: date


class GlobalConfig(BaseModel):
    """Top-level configuration for Science multi-project sync."""

    sync: SyncSettings = Field(default_factory=SyncSettings)
    projects: list[RegisteredProject] = Field(default_factory=list)


def load_global_config(config_path: Path = DEFAULT_CONFIG_PATH) -> GlobalConfig:
    """Load global config from YAML. Returns defaults if the file is missing."""
    if not config_path.exists():
        return GlobalConfig()
    raw = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        return GlobalConfig()
    return GlobalConfig.model_validate(data)


def save_global_config(config: GlobalConfig, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save global config to YAML, creating parent directories as needed."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def prune_missing_projects(config_path: Path = DEFAULT_CONFIG_PATH) -> list[str]:
    """Remove projects whose paths no longer exist. Returns list of pruned paths."""
    cfg = load_global_config(config_path)
    pruned: list[str] = []
    kept: list[RegisteredProject] = []
    for project in cfg.projects:
        resolved = Path(project.path).expanduser().resolve()
        if resolved.is_dir() and (resolved / "science.yaml").is_file():
            kept.append(project)
        else:
            pruned.append(project.path)
    if pruned:
        cfg.projects = kept
        save_global_config(cfg, config_path)
    return pruned


def ensure_registered(
    project_root: Path,
    project_name: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Register a project if not already listed. Idempotent; uses resolved path."""
    resolved = str(project_root.resolve())
    cfg = load_global_config(config_path)

    for project in cfg.projects:
        if project.path == resolved:
            return

    cfg.projects.append(
        RegisteredProject(
            path=resolved,
            name=project_name,
            registered=date.today(),
        )
    )
    save_global_config(cfg, config_path)

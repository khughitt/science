"""Global configuration and project auto-registration for Science multi-project sync."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, ConfigDict, Field
from science_model.frontmatter import project_config_path

from science_tool.commons.config import CommonsSettings

_UNSET = object()


def _safe_resolved(path_str: str) -> Path:
    """Resolve a stored project path (expanding ~ and following symlinks).

    Tolerates unresolvable paths by falling back to the lexical absolute form so
    a single bad entry never breaks registration/dedup.
    """
    try:
        return Path(path_str).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(path_str).expanduser().absolute()


def get_science_config_dir() -> Path:
    """Resolve the Science config directory at runtime."""
    configured_dir = os.environ.get("SCIENCE_CONFIG_DIR")
    if configured_dir:
        return Path(configured_dir).expanduser()

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "science"

    return Path.home() / ".config" / "science"


def get_default_config_path() -> Path:
    """Resolve the default global config path at runtime."""
    return get_science_config_dir() / "config.yaml"


SCIENCE_CONFIG_DIR = get_science_config_dir()
DEFAULT_CONFIG_PATH = get_default_config_path()


class SyncSettings(BaseModel):
    """Settings controlling sync behavior."""

    stale_after_days: int = 7


class DataSettings(BaseModel):
    """Global shared parent for per-project bulk data roots."""

    model_config = ConfigDict(extra="forbid")

    root: Path | None = None


class RegisteredProject(BaseModel):
    """A project registered for cross-project sync."""

    path: str
    name: str
    registered: date
    id: str | None = None
    role: str | None = None
    parent: str | None = None


class GlobalConfig(BaseModel):
    """Top-level configuration for Science multi-project sync."""

    sync: SyncSettings = Field(default_factory=SyncSettings)
    projects: list[RegisteredProject] = Field(default_factory=list)
    data: DataSettings = Field(default_factory=DataSettings)
    commons: CommonsSettings = Field(default_factory=CommonsSettings)


def load_global_config(config_path: Path | None = None) -> GlobalConfig:
    """Load global config from YAML. Returns defaults if the file is missing."""
    config_path = config_path or get_default_config_path()
    if not config_path.exists():
        return GlobalConfig()
    raw = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        return GlobalConfig()
    return GlobalConfig.model_validate(data)


def save_global_config(config: GlobalConfig, config_path: Path | None = None) -> None:
    """Save global config to YAML, creating parent directories as needed."""
    config_path = config_path or get_default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def prune_missing_projects(config_path: Path | None = None) -> list[str]:
    """Remove projects whose paths no longer exist. Returns list of pruned paths."""
    config_path = config_path or get_default_config_path()
    cfg = load_global_config(config_path)
    pruned: list[str] = []
    kept: list[RegisteredProject] = []
    for project in cfg.projects:
        resolved = Path(project.path).expanduser().resolve()
        if resolved.is_dir() and project_config_path(resolved).is_file():
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
    config_path: Path | None = None,
    project_id: str | None = None,
    role: str | None = None,
    parent: str | None | object = _UNSET,
) -> None:
    """Register or refresh a project. Idempotent; uses resolved path."""
    config_path = config_path or get_default_config_path()
    resolved_path = project_root.resolve()
    resolved = str(resolved_path)
    cfg = load_global_config(config_path)

    # Match by *resolved* path, not raw string: a project reachable via a symlink
    # alias (e.g. ~/d -> realpath) must not auto-register a duplicate entry that
    # shares the same id (fb-2026-05-30-010). `prune_missing_projects` already
    # resolves stored paths the same way.
    matches = [
        project
        for project in cfg.projects
        if _safe_resolved(project.path) == resolved_path
    ]
    if matches:
        primary = matches[0]
        changed = False
        # Collapse any pre-existing duplicates that resolve to the same real path
        # (self-heals a config that already accumulated colliding-id entries).
        if len(matches) > 1:
            cfg.projects = [
                project
                for project in cfg.projects
                if project is primary or _safe_resolved(project.path) != resolved_path
            ]
            changed = True
        # Normalize the stored path to the real path so future raw-string reads agree.
        if primary.path != resolved:
            primary.path = resolved
            changed = True
        if project_id is not None and primary.id != project_id:
            primary.id = project_id
            changed = True
        if role is not None and primary.role != role:
            primary.role = role
            changed = True
        if parent is not _UNSET and primary.parent != parent:
            primary.parent = cast(str | None, parent)
            changed = True
        if changed:
            save_global_config(cfg, config_path)
        return

    cfg.projects.append(
        RegisteredProject(
            path=resolved,
            name=project_name,
            registered=date.today(),
            id=project_id,
            role=role,
            parent=None if parent is _UNSET else cast(str | None, parent),
        )
    )
    save_global_config(cfg, config_path)

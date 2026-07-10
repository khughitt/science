"""Project bulk-data root resolution."""

from __future__ import annotations

import os
from pathlib import Path

from science_model.frontmatter import PROJECT_CONFIG_FILENAME, project_config_path  # noqa: F401
from science_tool.project_config import ProjectConfig, load_project_config
from science_tool.registry.config import load_global_config


class DataRootConfigError(ValueError):
    """Raised when a data-root configuration value is invalid."""


def discover_project_root(start: Path | None = None) -> Path:
    """Resolve a project root from env, nearest science.yaml ancestor, or cwd."""
    if start is None:
        if env := os.environ.get("SCIENCE_PROJECT_ROOT"):
            return Path(env).expanduser().resolve()
        start = Path.cwd()
    candidate = start.expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for root in (candidate, *candidate.parents):
        if project_config_path(root).is_file():
            return root
    return candidate


def logical_data_dir_to_physical(data_root: Path, logical_dir: Path) -> Path:
    """Map logical data/raw to physical <data_root>/raw."""
    return data_root / logical_dir.name


def resolve_data_root(project_root: Path, config: ProjectConfig | None = None) -> Path:
    """Resolve a project's physical bulk-data root."""
    project_root = project_root.expanduser().resolve()
    if env := os.environ.get("SCIENCE_DATA_ROOT"):
        return _require_absolute(Path(env).expanduser(), "SCIENCE_DATA_ROOT")

    project_config = config or _load_project_config_if_present(project_root)
    if project_config is not None and project_config.data is not None and project_config.data.root is not None:
        return _resolve_project_path(project_root, project_config.data.root)

    global_config = load_global_config()
    if global_config.data.root is not None:
        parent = _require_absolute(Path(global_config.data.root).expanduser(), "global data.root")
        project_id = project_config.id if project_config is not None and project_config.id else project_root.name
        return parent / project_id

    return project_root / "data"


def _load_project_config_if_present(project_root: Path) -> ProjectConfig | None:
    if not project_config_path(project_root).is_file():
        return None
    return load_project_config(project_root)


def _resolve_project_path(project_root: Path, value: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def _require_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise DataRootConfigError(f"{label} must be absolute, got {path}")
    return path

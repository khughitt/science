"""Resolve project directory paths from science.yaml mappings."""

from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULTS: dict[str, str] = {
    "doc_dir": "doc",
    "code_dir": "code",
    "data_dir": "data",
    "models_dir": "models",
    "specs_dir": "specs",
    "papers_dir": "papers",
    "knowledge_dir": "knowledge",
    "tasks_dir": "tasks",
    "templates_dir": "templates",
    "prompts_dir": "prompts",
}


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved project directory paths."""

    root: Path
    doc_dir: Path
    code_dir: Path
    data_dir: Path
    models_dir: Path
    specs_dir: Path
    papers_dir: Path
    knowledge_dir: Path
    tasks_dir: Path
    templates_dir: Path
    prompts_dir: Path


def resolve_paths(project_root: Path) -> ProjectPaths:
    """Read science.yaml and resolve directory paths with defaults."""
    yaml_path = project_root / "science.yaml"
    mappings: dict[str, str] = {}

    if yaml_path.is_file():
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        mappings = data.get("paths", {}) or {}

    resolved: dict[str, Path] = {"root": project_root}
    for key, default in _DEFAULTS.items():
        raw = mappings.get(key, default)
        resolved[key] = project_root / raw.rstrip("/")

    return ProjectPaths(**resolved)

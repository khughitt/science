"""Resolve canonical project directory paths from the Science profile."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

import yaml

ProjectProfile: TypeAlias = Literal["research", "software"]

_COMMON_DEFAULTS: dict[str, str] = {
    "doc_dir": "doc",
    "data_dir": "data",
    "models_dir": "models",
    "specs_dir": "specs",
    "papers_dir": "papers",
    "knowledge_dir": "knowledge",
    "tasks_dir": "tasks",
    "templates_dir": ".ai/templates",
    "prompts_dir": ".ai/prompts",
}

_CODE_DIR_BY_PROFILE: dict[ProjectProfile, str] = {
    "research": "code",
    "software": "src",
}


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved canonical project paths."""

    root: Path
    profile: ProjectProfile
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


def _resolve_profile(project_root: Path) -> ProjectProfile:
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return "research"

    with open(yaml_path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    raw_profile = data.get("profile") or "research"
    if raw_profile not in _CODE_DIR_BY_PROFILE:
        raise ValueError(f"Unsupported project profile: {raw_profile!r}")
    return raw_profile


def resolve_paths(project_root: Path) -> ProjectPaths:
    """Resolve canonical paths from the project's declared profile."""

    profile = _resolve_profile(project_root)
    return ProjectPaths(
        root=project_root,
        profile=profile,
        doc_dir=project_root / _COMMON_DEFAULTS["doc_dir"],
        code_dir=project_root / _CODE_DIR_BY_PROFILE[profile],
        data_dir=project_root / _COMMON_DEFAULTS["data_dir"],
        models_dir=project_root / _COMMON_DEFAULTS["models_dir"],
        specs_dir=project_root / _COMMON_DEFAULTS["specs_dir"],
        papers_dir=project_root / _COMMON_DEFAULTS["papers_dir"],
        knowledge_dir=project_root / _COMMON_DEFAULTS["knowledge_dir"],
        tasks_dir=project_root / _COMMON_DEFAULTS["tasks_dir"],
        templates_dir=project_root / _COMMON_DEFAULTS["templates_dir"],
        prompts_dir=project_root / _COMMON_DEFAULTS["prompts_dir"],
    )

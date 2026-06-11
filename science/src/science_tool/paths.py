"""Resolve canonical project directory paths from the Science profile."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

import yaml

ProjectProfile: TypeAlias = Literal["research", "software"]

_COMMON_DEFAULTS: dict[str, str] = {
    "doc_dir": "doc",
    "entities_dir": "entities",
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
    entities_dir: Path
    code_dir: Path
    data_dir: Path
    models_dir: Path
    specs_dir: Path
    papers_dir: Path
    knowledge_dir: Path
    tasks_dir: Path
    templates_dir: Path
    prompts_dir: Path
    code_roots: tuple[Path, ...] = ()
    app_roots: tuple[Path, ...] = ()
    code_excludes: tuple[str, ...] = ()
    hardcoded_path_patterns: tuple[str, ...] = ()


def _load_manifest(project_root: Path) -> dict:
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return {}
    with open(yaml_path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"science.yaml {key} must be a list of strings")
    return value


def _normalize_root_names(data: dict, key: str) -> list[str]:
    """Validate root entries are non-empty, relative, project-contained, non-nested, de-duplicated.

    Nested roots (one entry an ancestor of another, e.g. ``code`` and
    ``code/stages``) are rejected: they would make the same file discoverable
    under two roots, yielding a duplicate ``code-file`` id and a hard collision
    at graph-build time. Failing early here with a clear message is preferable.
    """
    normalized: list[str] = []
    for name in _str_list(data, key):
        if not name.strip():
            raise ValueError(f"science.yaml {key} entries must be non-empty relative paths")
        candidate = Path(name)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"science.yaml {key} entries must be relative paths inside the project: {name!r}")
        if name in normalized:
            continue
        for other in normalized:
            shorter, longer = sorted((candidate.parts, Path(other).parts), key=len)
            if longer[: len(shorter)] == shorter:
                raise ValueError(f"science.yaml {key} entries must not be nested: {name!r} overlaps {other!r}")
        normalized.append(name)
    return normalized


def _resolve_profile(data: dict) -> ProjectProfile:
    raw_profile = data.get("profile") or "research"
    if raw_profile not in _CODE_DIR_BY_PROFILE:
        raise ValueError(f"Unsupported project profile: {raw_profile!r}")
    return raw_profile


def resolve_paths(project_root: Path) -> ProjectPaths:
    """Resolve canonical paths and declared code/app roots from science.yaml."""

    data = _load_manifest(project_root)
    profile = _resolve_profile(data)
    declared_code = _normalize_root_names(data, "code_roots")
    code_root_names = declared_code or [_CODE_DIR_BY_PROFILE[profile]]
    app_root_names = _normalize_root_names(data, "app_roots")
    return ProjectPaths(
        root=project_root,
        profile=profile,
        doc_dir=project_root / _COMMON_DEFAULTS["doc_dir"],
        entities_dir=project_root / _COMMON_DEFAULTS["entities_dir"],
        code_dir=project_root / code_root_names[0],
        data_dir=project_root / _COMMON_DEFAULTS["data_dir"],
        models_dir=project_root / _COMMON_DEFAULTS["models_dir"],
        specs_dir=project_root / _COMMON_DEFAULTS["specs_dir"],
        papers_dir=project_root / _COMMON_DEFAULTS["papers_dir"],
        knowledge_dir=project_root / _COMMON_DEFAULTS["knowledge_dir"],
        tasks_dir=project_root / _COMMON_DEFAULTS["tasks_dir"],
        templates_dir=project_root / _COMMON_DEFAULTS["templates_dir"],
        prompts_dir=project_root / _COMMON_DEFAULTS["prompts_dir"],
        code_roots=tuple(project_root / name for name in code_root_names),
        app_roots=tuple(project_root / name for name in app_root_names),
        code_excludes=tuple(_str_list(data, "code_excludes")),
        hardcoded_path_patterns=tuple(_str_list(data, "hardcoded_path_patterns")),
    )

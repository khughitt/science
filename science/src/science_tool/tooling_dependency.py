from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


CANONICAL_SCIENCE_SOURCE = (
    'science = { git = "https://github.com/khughitt/science.git", '
    'subdirectory = "science" }'
)


class ScienceSourceKind(StrEnum):
    MISSING = "missing"
    GIT = "git"
    SAME_REPO_PATH = "same-repo-path"
    EXTERNAL_PATH = "external-path"


@dataclass(frozen=True)
class ScienceDependency:
    dev_dependency_present: bool
    source_kind: ScienceSourceKind
    resolved_path: Path | None = None


def inspect_science_dependency(project_root: Path) -> ScienceDependency:
    pyproject_path = project_root / "pyproject.toml"
    with pyproject_path.open("rb") as stream:
        data = tomllib.load(stream)

    dependency_groups = data.get("dependency-groups")
    dev_group = dependency_groups.get("dev", []) if isinstance(dependency_groups, dict) else []
    dev_dependency_present = isinstance(dev_group, list) and any(
        isinstance(entry, str) and _requirement_name(entry) == "science"
        for entry in dev_group
    )
    if not dev_dependency_present:
        return ScienceDependency(False, ScienceSourceKind.MISSING)

    source = _science_source(data)
    if not isinstance(source, dict):
        return ScienceDependency(True, ScienceSourceKind.MISSING)
    if isinstance(source.get("git"), str):
        return ScienceDependency(True, ScienceSourceKind.GIT)

    raw_path = source.get("path")
    if not isinstance(raw_path, str):
        return ScienceDependency(True, ScienceSourceKind.MISSING)

    resolved_path = (project_root / raw_path).resolve()
    project_repo = _git_worktree_root(project_root)
    source_repo = _git_worktree_root(resolved_path)
    kind = (
        ScienceSourceKind.SAME_REPO_PATH
        if project_repo is not None and project_repo == source_repo
        else ScienceSourceKind.EXTERNAL_PATH
    )
    return ScienceDependency(True, kind, resolved_path)


def _science_source(data: dict[str, Any]) -> object:
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    uv = tool.get("uv")
    if not isinstance(uv, dict):
        return None
    sources = uv.get("sources")
    if not isinstance(sources, dict):
        return None
    return sources.get("science")


def _requirement_name(requirement: str) -> str:
    return re.split(r"\s*(?:\[|@|===|==|~=|!=|<=|>=|<|>)", requirement.strip(), maxsplit=1)[0]


def _git_worktree_root(path: Path) -> Path | None:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None

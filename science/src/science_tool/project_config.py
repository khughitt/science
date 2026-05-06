"""Typed schema for science.yaml. Non-breaking: extra fields are allowed."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.functional_validators import BeforeValidator


class ProjectRole(StrEnum):
    META = "meta"
    CANCER_TYPE = "cancer-type"
    DATA_SOURCE = "data-source"
    MECHANISM = "mechanism"
    CONDITION = "condition"
    STANDALONE = "standalone"


def _coerce_role(value: Any) -> Any:
    """Accept known enum values or free-form strings."""
    if value is None:
        return ProjectRole.STANDALONE
    if isinstance(value, ProjectRole):
        return value
    if isinstance(value, str):
        try:
            return ProjectRole(value)
        except ValueError:
            return value
    raise TypeError(f"role must be string, got {type(value).__name__}")


RoleField = Annotated[ProjectRole | str, BeforeValidator(_coerce_role)]


class ChildEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    role: RoleField = ProjectRole.STANDALONE


class ProjectConfig(BaseModel):
    """Typed view of science.yaml. Non-listed fields are preserved as-is."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    role: RoleField = ProjectRole.STANDALONE
    parent: str | None = None
    children: list[ChildEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _children_only_on_meta(self) -> ProjectConfig:
        if self.children and self.role != ProjectRole.META:
            raise ValueError("children: manifest is only valid on role=meta projects")
        return self

    @model_validator(mode="after")
    def _children_unique_ids(self) -> ProjectConfig:
        ids = [child.id for child in self.children]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate child id in children manifest")
        return self


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load and validate science.yaml at ``project_root``. Defaults id to dirname."""
    yaml_path = project_root / "science.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if "id" not in raw or raw["id"] is None:
        raw["id"] = project_root.resolve().name
    return ProjectConfig.model_validate(raw)


def resolve_child_path(child: ChildEntry) -> Path:
    """Resolve a tilde-prefixed child path to a physical path."""
    return Path(child.path).expanduser().resolve()


def paths_equivalent(a: Path, b: Path) -> bool:
    """Compare two paths after symlink resolution."""
    try:
        return a.expanduser().resolve() == b.expanduser().resolve()
    except OSError:
        return False


def resolve_parent_path(parent: str | None) -> Path | None:
    """Resolve a tilde-prefixed parent path.

    If the path does not exist, return the expanded but unresolved path so callers can
    distinguish "not configured" from "configured but absent".
    """
    if parent is None:
        return None
    expanded = Path(parent).expanduser()
    try:
        return expanded.resolve(strict=True)
    except (OSError, FileNotFoundError):
        return expanded

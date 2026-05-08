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


class PeerEntry(BaseModel):
    """Declares another project this one references.

    `id` must match the peer project's own self-declared `id:` (validated by
    `validate_peers()` at use time, not at parse time, so configs with
    transient inconsistencies still load).

    `path` is a local filesystem path. Three accepted shapes:
      - absolute (`/...`)
      - `~`-anchored (`~/d/...`)
      - relative to this project's root (`../mm30`)

    Reserved fields (`git`, `repo`, `url`, `doi`, `ref`, `version`) are
    accepted at parse time (extra="allow") but flagged by `validate_peers()`
    until their respective specs ship. See project-peers design Decision 2.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    path: str


class ProjectConfig(BaseModel):
    """Typed view of science.yaml. Non-listed fields are preserved as-is."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    role: RoleField = ProjectRole.STANDALONE
    peers: list[PeerEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_fields(cls, raw: Any) -> Any:
        if isinstance(raw, dict):
            illegal = [k for k in ("parent", "children") if k in raw]
            if illegal:
                raise ValueError(
                    f"science.yaml uses removed field(s) {illegal!r}. "
                    "Run `science peers migrate` to migrate to `peers:`."
                )
        return raw


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load and validate science.yaml at ``project_root``. Defaults id to dirname."""
    yaml_path = project_root / "science.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if "id" not in raw or raw["id"] is None:
        raw["id"] = project_root.resolve().name
    return ProjectConfig.model_validate(raw)


def paths_equivalent(a: Path, b: Path) -> bool:
    """Compare two paths after symlink resolution."""
    try:
        return a.expanduser().resolve() == b.expanduser().resolve()
    except OSError:
        return False

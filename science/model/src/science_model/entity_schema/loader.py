"""Load JSON Schema files for the multi-project entity schema layer."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
)

_SCHEMAS_PACKAGE = "science_model.schemas"


class SchemaNotFoundError(FileNotFoundError):
    """Raised when a profile component does not map to a known schema file."""


def is_extension(component: ProfileComponent) -> bool:
    """True for a domain/project extension — the only kind of schema a project may author."""
    return component.name != BASE_NAME and component.name != "overlay" and (
        component.name not in TYPE_MIXIN_NAMES
    )


class SchemaLoader:
    """Resolve profile components to JSON Schema dicts, with caching.

    `project_dir` is a project's own `schemas/` directory. It is searched ONLY for extension
    components -- never for the base or a type mixin. A project that could drop its own
    `mixin-hypothesis-1.0.json` into that directory would silently redefine the core kind for
    itself, re-opening the per-project divergence this whole schema convergence exists to close.
    A project may OWN fields; it may not REDEFINE the kind.
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        *,
        project_schemas: Mapping[str, dict[str, Any]] | None = None,
    ) -> None:
        if project_dir is not None and project_schemas is not None:
            raise ValueError(
                "project_dir and project_schemas are mutually exclusive schema sources"
            )
        self._project_dir = project_dir
        self._project_schemas = (
            {
                filename: deepcopy(schema)
                for filename, schema in project_schemas.items()
            }
            if project_schemas is not None
            else None
        )
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    def load(self, component: ProfileComponent) -> dict[str, Any]:
        key = (component.name, component.version)
        if key in self._cache:
            return self._cache[key]
        filename = filename_for(component)
        schema = self._load(component, filename)
        self._cache[key] = schema
        return schema

    def _load(self, component: ProfileComponent, filename: str) -> dict[str, Any]:
        if is_extension(component):
            if (
                self._project_schemas is not None
                and filename in self._project_schemas
            ):
                return self._project_schemas[filename]
            if self._project_dir is not None:
                candidate = self._project_dir / filename
                if candidate.is_file():
                    return json.loads(candidate.read_text(encoding="utf-8"))
        return _load_resource(filename)


def filename_for(component: ProfileComponent) -> str:
    if component.name == BASE_NAME:
        return f"{component.name}-{component.version}.json"
    if component.name == "overlay":
        return f"overlay-{component.version}.json"
    if component.name in TYPE_MIXIN_NAMES:
        return f"mixin-{component.name}-{component.version}.json"
    # Extensions: replace dots with hyphens (e.g. bio.rnaseq -> bio-rnaseq).
    flat = component.name.replace(".", "-")
    return f"extension-{flat}-{component.version}.json"


@lru_cache(maxsize=None)
def _list_resources() -> frozenset[str]:
    return frozenset(r.name for r in resources.files(_SCHEMAS_PACKAGE).iterdir())


def _load_resource(filename: str) -> dict[str, Any]:
    if filename not in _list_resources():
        raise SchemaNotFoundError(f"schema resource {filename!r} not found in {_SCHEMAS_PACKAGE}")
    text = resources.files(_SCHEMAS_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    return json.loads(text)

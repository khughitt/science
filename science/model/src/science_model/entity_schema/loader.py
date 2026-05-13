"""Load JSON Schema files for the multi-project entity schema layer."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
)

_SCHEMAS_PACKAGE = "science_model.schemas"


class SchemaNotFoundError(FileNotFoundError):
    """Raised when a profile component does not map to a known schema file."""


class SchemaLoader:
    """Resolve profile components to JSON Schema dicts, with caching."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    def load(self, component: ProfileComponent) -> dict[str, Any]:
        key = (component.name, component.version)
        if key in self._cache:
            return self._cache[key]
        filename = _filename_for(component)
        schema = _load_resource(filename)
        self._cache[key] = schema
        return schema


def _filename_for(component: ProfileComponent) -> str:
    if component.name == BASE_NAME:
        return f"{component.name}-{component.version}.json"
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

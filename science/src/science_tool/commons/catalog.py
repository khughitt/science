"""Parse V1 commons catalog source declarations.

This module validates reserved remote-ready source declarations only. It does
not fetch, update, or execute remote catalogs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

SourceType = Literal["path", "git", "github", "zenodo"]

_SOURCE_TYPES = {"path", "git", "github", "zenodo"}
_REQUIRED_FIELD_BY_TYPE: dict[SourceType, str] = {
    "path": "uri",
    "git": "uri",
    "github": "repo",
    "zenodo": "doi",
}


class CatalogError(ValueError):
    """Raised when a commons catalog declaration is invalid."""


@dataclass(frozen=True, slots=True)
class CatalogSource:
    type: SourceType
    uri: str | None = None
    repo: str | None = None
    doi: str | None = None


@dataclass(frozen=True, slots=True)
class CommonsCatalog:
    catalog_version: int
    sources: dict[str, CatalogSource]


def _load_yaml_no_duplicate_keys(path: Path, text: str) -> object:
    try:
        node = yaml.compose(text)
        _reject_duplicate_mapping_keys(path, node)
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path}: malformed YAML: {exc}") from exc


def _reject_duplicate_mapping_keys(path: Path, node: object) -> None:
    if node is None:
        return
    if isinstance(node, yaml.MappingNode):
        seen_keys: set[str] = set()
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                raise CatalogError(f"{path}: malformed YAML: expected scalar mapping keys")
            key = key_node.value
            if key in seen_keys:
                raise CatalogError(f"{path}: duplicate key {key!r}")
            seen_keys.add(key)
            _reject_duplicate_mapping_keys(path, value_node)
        return
    if isinstance(node, yaml.SequenceNode):
        for value_node in node.value:
            _reject_duplicate_mapping_keys(path, value_node)


def load_commons_catalog(path: Path) -> CommonsCatalog:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CommonsCatalog(catalog_version=1, sources={})

    loaded = _load_yaml_no_duplicate_keys(path, text)
    raw = {} if loaded is None else loaded
    if not isinstance(raw, dict):
        raise CatalogError(f"{path}: expected mapping")

    catalog_version = raw.get("catalog_version", 1)
    if type(catalog_version) is not int or catalog_version != 1:
        raise CatalogError(f"{path}: expected catalog_version 1")

    raw_sources = raw.get("sources", {})
    if not isinstance(raw_sources, dict):
        raise CatalogError(f"{path}: sources expected mapping")

    sources: dict[str, CatalogSource] = {}
    for name, source_raw in raw_sources.items():
        if not isinstance(name, str):
            raise CatalogError(f"{path}: source names must be strings")
        if not isinstance(source_raw, dict):
            raise CatalogError(f"{path}: source {name!r} expected mapping")

        raw_source_type = source_raw.get("type")
        if not isinstance(raw_source_type, str) or raw_source_type not in _SOURCE_TYPES:
            raise CatalogError(f"{path}: unsupported source type {raw_source_type!r} for source {name!r}")

        source_type = cast(SourceType, raw_source_type)
        required_field = _REQUIRED_FIELD_BY_TYPE[source_type]
        required_value = source_raw.get(required_field)
        if not isinstance(required_value, str) or not required_value:
            raise CatalogError(f"{path}: {source_type} source {name!r} requires {required_field!r}")

        sources[name] = CatalogSource(
            type=source_type,
            uri=source_raw.get("uri") if isinstance(source_raw.get("uri"), str) else None,
            repo=source_raw.get("repo") if isinstance(source_raw.get("repo"), str) else None,
            doi=source_raw.get("doi") if isinstance(source_raw.get("doi"), str) else None,
        )

    return CommonsCatalog(catalog_version=1, sources=sources)

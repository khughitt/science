"""Shared resource helpers for bio.geneset collection member tables."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.datapackage import validate_logical_path
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsRootNotFoundError,
    DataResourceNotFoundError,
)
from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.geneset import is_geneset_frontmatter
from science_tool.commons.resolver import resolve


def geneset_resource_frontmatter(project_root: Path, entity_path: str | Path) -> dict[str, Any] | None:
    path = Path(entity_path)
    source_path = path if path.is_absolute() else project_root / path
    fm = raw_frontmatter(source_path)
    if not is_geneset_frontmatter(fm):
        return None
    if source_path.name == "entity.md":
        fm["_path"] = str(source_path.parent / "datapackage.yaml")
    else:
        fm["_path"] = str(path)
    return fm


def resource_path_for_members(project_root: Path, fm: dict[str, Any]) -> Path | Exception | None:
    rel = fm.get("_path")
    resource_name = fm.get("members_resource")
    if not isinstance(rel, str) or not isinstance(resource_name, str):
        return None
    dp_path = project_root / rel
    try:
        doc = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    resources = doc.get("resources")
    if not isinstance(resources, list):
        return None
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("name") != resource_name:
            continue
        resource_path = resource.get("path")
        if not isinstance(resource_path, str):
            return None
        try:
            logical_path = validate_logical_path(resource_path)
        except CommonsError as exc:
            return exc
        return dp_path.parent / logical_path
    return None


def _read_csv(path: Path) -> list[dict[str, Any]] | Exception:
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeError, csv.Error) as exc:
        return exc


def _resolve_commons_members_path(fm: dict[str, Any]) -> Path | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get("members_resource")
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        return resolve(dataset_id, resource_name).path
    except (CommonsRootNotFoundError, CommonsEntityError, DataResourceNotFoundError):
        return None
    except CommonsError as exc:
        return exc


def read_member_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = resource_path_for_members(project_root, fm)
    if isinstance(path, Exception):
        return path
    if path is not None and path.is_file():
        return _read_csv(path)
    commons_path = _resolve_commons_members_path(fm)
    if isinstance(commons_path, Exception):
        return commons_path
    if commons_path is None:
        return None
    return _read_csv(commons_path)

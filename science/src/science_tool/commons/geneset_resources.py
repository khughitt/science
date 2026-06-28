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


def resolve_dataset_datapackage_source(
    *, entity_adapter: str | None, entity_path: str | Path, datapackage_rel: str | None
) -> str | Path | None:
    """The datapackage source for a dataset entity, independent of which adapter won the
    owner column (design §B4):

    - the entity IS the datapackage (orphan) or a commons-merged dataset → the entity's
      own source path;
    - a real owner with a deferred datapackage attachment → the recorded ``datapackage_rel``;
    - no datapackage attachment → ``None``.
    """
    if entity_adapter in {"datapackage", "commons-merged"}:
        return entity_path
    if datapackage_rel is not None:
        return datapackage_rel
    return None


def dataset_datapackage_path(
    *, entity_adapter: str | None, entity_path: str | Path, datapackage_rel: str | None
) -> Path | None:
    """The LOCAL datapackage file for a dataset entity (design §B4), or ``None``.

    Like ``resolve_dataset_datapackage_source`` but excludes ``commons-merged`` (those
    resources are owned/materialized by the commons scope, not this project) and
    normalizes an ``entity.md`` source to its sibling ``datapackage.yaml``. Used to
    materialize a dataset's resources as DCAT distributions (§B4) regardless of whether
    the datapackage is an orphan owner or a deferred attachment on a real owner.
    """
    if entity_adapter == "datapackage":
        source: str | Path = entity_path
    elif datapackage_rel is not None:
        source = datapackage_rel
    else:
        return None
    path = Path(source)
    if path.name == "entity.md":
        return path.parent / "datapackage.yaml"
    return path


def dataset_geneset_frontmatter(
    project_root: Path,
    entity_path: str | Path,
    *,
    entity_adapter: str | None,
    datapackage_rel: str | None,
) -> dict[str, Any] | None:
    """Geneset resource frontmatter for a dataset entity, independent of which
    adapter won the owner column (design §B4).

    A datapackage's geneset resource metadata stays in the datapackage; a promoted
    markdown owner does not duplicate it. So member extraction reads the geneset
    shape from the datapackage:

    - the entity IS the datapackage (orphan) or a commons-merged dataset → read from
      the entity's own source path (preserves prior behavior);
    - a real owner with a deferred datapackage attachment → read from the recorded
      datapackage path (``datapackage_rel``);
    - no datapackage attachment → ``None`` (not a geneset dataset).
    """
    source = resolve_dataset_datapackage_source(
        entity_adapter=entity_adapter, entity_path=entity_path, datapackage_rel=datapackage_rel
    )
    if source is None:
        return None
    return geneset_resource_frontmatter(project_root, source)


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


def read_commons_member_rows(
    fm: dict[str, Any],
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get("members_resource")
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        resolved = resolve(dataset_id, resource_name, commons_root=commons_root, data_root=data_root)
    except CommonsError as exc:
        return exc
    return _read_csv(resolved.path)

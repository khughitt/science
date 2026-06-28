"""Resource helpers for bio.reference_graph graph/index/edge artifacts."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Literal

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import load_data_overrides, resolve_commons_data_root, resolve_commons_root
from science_tool.commons.datapackage import read_datapackage, validate_logical_path
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsRootNotFoundError,
    DataResourceNotFoundError,
)
from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.geneset_resources import resolve_dataset_datapackage_source
from science_tool.commons.reference_graph import is_reference_graph_frontmatter
from science_tool.commons.resolver import resolve

ResourceKind = Literal["graph", "node", "edge"]

_DATASET_ID = re.compile(r"^dataset:[a-z0-9][a-z0-9-]{1,63}$")
_RESOURCE_FIELD_BY_KIND: dict[ResourceKind, str] = {
    "graph": "graph_resource",
    "node": "node_index_resource",
    "edge": "edge_resource",
}


def reference_graph_resource_frontmatter(project_root: Path, entity_path: str | Path) -> dict[str, Any] | None:
    path = Path(entity_path)
    source_path = path if path.is_absolute() else project_root / path
    fm = raw_frontmatter(source_path)
    if not is_reference_graph_frontmatter(fm):
        return None
    if source_path.name == "entity.md":
        datapackage_path = source_path.parent / "datapackage.yaml"
        try:
            fm["_path"] = str(datapackage_path.relative_to(project_root))
        except ValueError:
            fm["_path"] = str(datapackage_path)
    else:
        fm["_path"] = str(path)
    return fm


def dataset_reference_graph_frontmatter(
    project_root: Path,
    entity_path: str | Path,
    *,
    entity_adapter: str | None,
    datapackage_rel: str | None,
) -> dict[str, Any] | None:
    source = resolve_dataset_datapackage_source(
        entity_adapter=entity_adapter, entity_path=entity_path, datapackage_rel=datapackage_rel
    )
    if source is None:
        return None
    return reference_graph_resource_frontmatter(project_root, source)


def resource_path_for_reference_graph(
    project_root: Path,
    fm: dict[str, Any],
    *,
    kind: ResourceKind,
) -> Path | Exception | None:
    rel = fm.get("_path")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
    if not isinstance(rel, str) or not isinstance(resource_name, str):
        return None
    try:
        logical_rel = validate_logical_path(rel)
    except CommonsError as exc:
        return exc
    dp_path = project_root / logical_rel
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


def _read_commons_csv_resource(
    fm: dict[str, Any],
    *,
    kind: ResourceKind,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        resolved = resolve(dataset_id, resource_name, commons_root=commons_root, data_root=data_root)
    except CommonsError as exc:
        return exc
    return _read_csv(resolved.path)


def _resolve_commons_resource_path(fm: dict[str, Any], *, kind: ResourceKind) -> Path | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        return resolve(dataset_id, resource_name).path
    except (CommonsRootNotFoundError, CommonsEntityError, DataResourceNotFoundError):
        return None
    except CommonsError as exc:
        return exc


def _commons_graph_resource_available(fm: dict[str, Any]) -> bool | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND["graph"])
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        validate_logical_path(resource_name)
        commons_root = resolve_commons_root()
        data_root = resolve_commons_data_root()
        if not commons_root.is_dir():
            raise CommonsRootNotFoundError(commons_root)
        if not _DATASET_ID.fullmatch(dataset_id):
            raise CommonsEntityError(
                commons_root,
                canonical_id=dataset_id,
                cause=ValueError(
                    f"data resolve requires a dataset id of the form 'dataset:<slug>', got {dataset_id!r}"
                ),
            )
        record = CommonsEntityAdapter(commons_root).load(dataset_id)
        if record.datapackage_path is None:
            raise CommonsEntityError(
                record.body_path,
                canonical_id=dataset_id,
                cause=ValueError("dataset record is missing its datapackage path"),
            )
        resource = read_datapackage(record.datapackage_path).resource(resource_name)
        data_root_candidate = data_root / record.slug / resource.path
        if data_root_candidate.is_file():
            return True
        override_dir = load_data_overrides().get(record.slug)
        override_candidate = override_dir / resource.path if override_dir is not None else None
        return override_candidate.is_file() if override_candidate is not None else False
    except (CommonsRootNotFoundError, CommonsEntityError, DataResourceNotFoundError):
        return None
    except CommonsError as exc:
        return exc


def _resource_path(project_root: Path, fm: dict[str, Any], *, kind: ResourceKind) -> Path | Exception | None:
    path = resource_path_for_reference_graph(project_root, fm, kind=kind)
    if isinstance(path, Exception):
        return path
    if path is not None and path.is_file():
        return path
    commons_path = _resolve_commons_resource_path(fm, kind=kind)
    if isinstance(commons_path, Exception):
        return commons_path
    if commons_path is None:
        return None
    return commons_path


def graph_resource_available(project_root: Path, fm: dict[str, Any]) -> bool | Exception | None:
    path = resource_path_for_reference_graph(project_root, fm, kind="graph")
    if isinstance(path, Exception):
        return path
    if path is not None and path.is_file():
        return True
    return _commons_graph_resource_available(fm)


def read_node_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path(project_root, fm, kind="node")
    if isinstance(path, Exception) or path is None:
        return path
    return _read_csv(path)


def read_edge_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path(project_root, fm, kind="edge")
    if isinstance(path, Exception) or path is None:
        return path
    return _read_csv(path)


def read_commons_node_rows(
    fm: dict[str, Any],
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    return _read_commons_csv_resource(fm, kind="node", commons_root=commons_root, data_root=data_root)


def read_commons_edge_rows(
    fm: dict[str, Any],
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]] | Exception | None:
    return _read_commons_csv_resource(fm, kind="edge", commons_root=commons_root, data_root=data_root)

"""Shared resource helpers for bio.geneset collection member tables."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.datapackage import validate_logical_path
from science_tool.commons.errors import CommonsError

PROFILE_TOKEN = "+bio.geneset/"


def is_geneset_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and PROFILE_TOKEN in f"+{profile}"


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


def read_member_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = resource_path_for_members(project_root, fm)
    if isinstance(path, Exception):
        return path
    if path is None or not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeError, csv.Error) as exc:
        return exc

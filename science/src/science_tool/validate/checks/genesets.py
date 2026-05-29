"""Gene-set collection checks (D1 collection rows only)."""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Iterator
from pathlib import Path
from statistics import median
from typing import Any

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.datapackage import validate_logical_path
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import (
    GENE_CROSSWALK_ID,
    MEMBER_KEY_COLUMN as GENE_KEY_COLUMN,
    SUPPORTED_GENE_NAMESPACES,
)
from science_tool.commons.geneset import (
    GENESET_MEMBER_KEY_COLUMN,
    GenesetCollectionError,
    GenesetRow,
    parse_geneset_rows,
)
from science_tool.commons.protein_crosswalk import (
    MEMBER_KEY_COLUMN as PROTEIN_KEY_COLUMN,
    PROTEIN_CROSSWALK_ID,
    SUPPORTED_PROTEIN_NAMESPACES,
)
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_PROFILE_TOKEN = "+bio.geneset/"
_SUPPORTED_BY_TIER = {
    "gene": (SUPPORTED_GENE_NAMESPACES, GENE_CROSSWALK_ID, "+bio.gene_crosswalk/", GENE_KEY_COLUMN),
    "protein": (
        SUPPORTED_PROTEIN_NAMESPACES,
        PROTEIN_CROSSWALK_ID,
        "+bio.protein_crosswalk/",
        PROTEIN_KEY_COLUMN,
    ),
}


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _is_geneset(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and _PROFILE_TOKEN in f"+{profile}"


def _collection_defect(fm: dict[str, Any]) -> str | None:
    if fm.get("member_key_column") != GENESET_MEMBER_KEY_COLUMN:
        return "member_key_column must be 'set_key'"
    resource = fm.get("members_resource")
    if not isinstance(resource, str) or not resource.strip():
        return "members_resource must name a Frictionless resource"
    n_sets = fm.get("n_sets")
    if not isinstance(n_sets, int) or n_sets < 1:
        return "n_sets must be a positive integer"
    summary = fm.get("set_size_summary")
    if not isinstance(summary, dict):
        return "set_size_summary must be an object"
    for key in ("min", "median", "max"):
        value = summary.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            return f"set_size_summary.{key} must be a non-negative number"
    if not (summary["min"] <= summary["median"] <= summary["max"]):
        return "set_size_summary must satisfy min <= median <= max"
    ident = fm.get("identifier_space")
    if not isinstance(ident, dict):
        return "identifier_space must be an object"
    tier = ident.get("tier")
    if tier not in _SUPPORTED_BY_TIER:
        return "identifier_space.tier must be 'gene' or 'protein'"
    namespace = ident.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "identifier_space.namespace is required"
    registry = ident.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "identifier_space.registry must be a 'dataset:' reference"
    status = ident.get("resolution_status")
    if status not in (None, "resolved", "declared_unresolved"):
        return "identifier_space.resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _registry_id(ident: dict[str, Any]) -> str:
    tier = str(ident["tier"])
    registry = ident.get("registry")
    return registry if isinstance(registry, str) else _SUPPORTED_BY_TIER[tier][1]


def _is_expected_registry(meta: dict[str, Any], *, tier: str) -> bool:
    _namespaces, _default_id, profile_token, key_column = _SUPPORTED_BY_TIER[tier]
    profile = str(meta.get("schema_profile") or "")
    return profile_token in f"+{profile}" and meta.get("member_key_column") == key_column


def _row_stats(rows: list[GenesetRow]) -> tuple[int, float, int]:
    sizes = sorted(row.n_members for row in rows)
    return sizes[0], float(median(sizes)), sizes[-1]


def _summary_matches(summary: dict[str, Any], rows: list[GenesetRow]) -> bool:
    min_size, median_size, max_size = _row_stats(rows)
    return (
        summary.get("min") == min_size
        and math.isclose(float(summary.get("median")), median_size, rel_tol=0.0, abs_tol=1e-9)
        and summary.get("max") == max_size
    )


def evaluate_geneset_collections(
    datasets: Iterable[dict[str, Any]],
    *,
    rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception],
    registry_meta_by_id: dict[str, dict[str, Any] | None],
) -> Iterator[Result]:
    for fm in datasets:
        if not _is_geneset(fm):
            continue
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        defect = _collection_defect(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed bio.geneset collection -- {defect}",
                "geneset.collection-malformed",
            )
            continue
        raw_rows = rows_by_dataset_id.get(ident)
        if raw_rows is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: members_resource is unavailable; row contract cannot be verified",
                "geneset.members-resource-unavailable",
            )
            continue
        if isinstance(raw_rows, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: members_resource malformed -- {raw_rows}",
                "geneset.members-resource-malformed",
            )
            continue
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError as exc:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: members_resource malformed -- {exc}",
                "geneset.members-resource-malformed",
            )
            continue
        if len(rows) != fm["n_sets"]:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: n_sets={fm['n_sets']} but members_resource has {len(rows)} rows",
                "geneset.n-sets-mismatch",
            )
            continue
        if not _summary_matches(fm["set_size_summary"], rows):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: set_size_summary does not match members_resource member counts",
                "geneset.set-size-summary-mismatch",
            )
            continue
        ident_space = fm["identifier_space"]
        tier = str(ident_space["tier"])
        supported_namespaces = _SUPPORTED_BY_TIER[tier][0]
        namespace = str(ident_space["namespace"])
        if namespace not in supported_namespaces:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: identifier_space namespace {namespace!r} is not supported for {tier}",
                "geneset.identifier-namespace-unsupported",
            )
            continue
        if ident_space.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: identifier_space declared_unresolved (honoured, RCM-D2)",
                "geneset.identifier-declared-unresolved",
            )
            continue
        registry_id = _registry_id(ident_space)
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: identifier registry {registry_id!r} unavailable; namespace cannot be verified",
                "geneset.identifier-registry-unavailable",
            )
            continue
        if not _is_expected_registry(meta, tier=tier):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: identifier registry {registry_id!r} is not a {tier} crosswalk collection",
                "geneset.identifier-registry-invalid",
            )


def _resource_path_for_members(project_root: Path, fm: dict[str, Any]) -> Path | Exception | None:
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


def _read_member_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path_for_members(project_root, fm)
    if isinstance(path, Exception):
        return path
    if path is None or not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeError, csv.Error) as exc:
        return exc


def _load_registry_meta(
    registry_id: str,
    *,
    local_by_id: dict[str, dict[str, Any]],
    commons_cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    if registry_id in local_by_id:
        fm = local_by_id[registry_id]
        return {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
    if registry_id in commons_cache:
        return commons_cache[registry_id]
    root = resolve_commons_root()
    meta: dict[str, Any] | None = None
    if root.is_dir():
        try:
            record = CommonsEntityAdapter(root).load(registry_id)
            fm = record.frontmatter
            meta = {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
        except CommonsError:
            meta = None
    commons_cache[registry_id] = meta
    return meta


@Check(section="gene-set collections", order=34)
def check_genesets(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    genesets = [fm for fm in datasets if _is_geneset(fm)]
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    rows_by_dataset_id = {
        str(fm["id"]): _read_member_rows(ctx.project_root, fm)
        for fm in genesets
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    declared_registries: set[str] = set()
    for fm in genesets:
        ident = fm.get("identifier_space")
        if not isinstance(ident, dict) or ident.get("resolution_status") == "declared_unresolved":
            continue
        tier = ident.get("tier")
        namespace = ident.get("namespace")
        if tier in _SUPPORTED_BY_TIER and isinstance(namespace, str) and namespace in _SUPPORTED_BY_TIER[str(tier)][0]:
            declared_registries.add(_registry_id(ident))
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared_registries
    }
    yield from evaluate_geneset_collections(
        genesets,
        rows_by_dataset_id=rows_by_dataset_id,
        registry_meta_by_id=registry_meta_by_id,
    )

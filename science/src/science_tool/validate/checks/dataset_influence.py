"""Dataset influence/provenance checks for Pillar B1."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import is_geneset_frontmatter, read_member_rows
from science_tool.validate._helpers import dataset_frontmatters, entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

DatasetRefStatus = Literal["resolved", "missing", "unavailable"]
_COMMONS_LAYOUT_DIRS = (".git", "datasets", "papers", "topics", "themes")
_ROLES = ("analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training")
_OVERLAPS = ("full", "partial", "unknown")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    if entry.get("role") not in _ROLES:
        return f"role must be one of {list(_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in _OVERLAPS:
        return f"overlap must be one of {list(_OVERLAPS)}"
    return None


def _iter_usage_entries(fm: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    usage = fm.get("dataset_usage")
    if usage is None:
        return [], None
    if not isinstance(usage, list):
        return [], f"dataset_usage must be a list, got {type(usage).__name__}"
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(usage):
        defect = _usage_defect(entry)
        if defect is not None:
            return [], f"dataset_usage[{index}] malformed -- {defect}"
        entries.append(entry)
    return entries, None


def evaluate_dataset_influence(
    frontmatters: Iterable[dict[str, Any]],
    *,
    dataset_ref_status: dict[str, DatasetRefStatus],
    row_usage_refs: Iterable[tuple[str, str, str]],
) -> Iterator[Result]:
    refs_to_check: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        kind = fm.get("kind") or fm.get("type")
        usage_entries, defect = _iter_usage_entries(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {defect}",
                "dataset-influence.dataset-usage-malformed",
            )
            continue

        for entry in usage_entries:
            ref = str(entry["ref"])
            if kind == "dataset" and ref == ident:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: dataset_usage must not reference itself",
                    "dataset-influence.self-reference",
                )
                continue
            refs_to_check.append((ref, ident, str(path or "")))

        derivation = fm.get("derivation")
        if kind == "dataset" and isinstance(derivation, dict):
            inputs = derivation.get("inputs")
            if isinstance(inputs, list):
                for ref in inputs:
                    if isinstance(ref, str) and ref == ident:
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: derivation.inputs must not reference itself",
                            "dataset-influence.self-reference",
                        )
                    elif isinstance(ref, str) and ref.startswith("dataset:"):
                        refs_to_check.append((ref, ident, str(path or "")))

        if kind == "paper":
            raw_datasets = fm.get("datasets")
            if raw_datasets is None:
                raw_datasets = []
            if not isinstance(raw_datasets, list):
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: datasets must be a list of dataset: refs",
                    "dataset-influence.paper-datasets-invalid",
                )
                continue
            explicit_by_ref = {str(entry["ref"]): entry for entry in usage_entries}
            for ref in raw_datasets:
                if not isinstance(ref, str) or not ref.startswith("dataset:"):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: paper.datasets entry {ref!r} is not a dataset: ref",
                        "dataset-influence.paper-datasets-invalid",
                    )
                    continue
                if ref in explicit_by_ref:
                    entry = explicit_by_ref[ref]
                    if entry.get("role") != "analyzed":
                        yield _result(
                            Severity.WARN,
                            path,
                            f"{ident}: paper.datasets {ref!r} conflicts with explicit dataset_usage; explicit entry materializes",
                            "dataset-influence.paper-datasets-conflict",
                        )
                    continue
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: legacy paper.datasets {ref!r} should migrate to dataset_usage",
                    "dataset-influence.paper-datasets-legacy",
                )
                refs_to_check.append((ref, ident, str(path or "")))

    refs_to_check.extend(row_usage_refs)
    for ref, consumer, path in refs_to_check:
        status = dataset_ref_status.get(ref, "missing")
        if status == "resolved":
            continue
        if status == "unavailable":
            yield _result(
                Severity.INFO,
                path,
                f"{consumer}: dataset ref {ref!r} cannot be checked because registry resources are unavailable",
                "dataset-influence.ref-unresolved-unavailable",
            )
        else:
            yield _result(
                Severity.WARN,
                path,
                f"{consumer}: dataset ref {ref!r} does not resolve to a local or commons dataset",
                "dataset-influence.ref-unresolved",
            )


def _dataset_ref_statuses(ctx: ValidateContext, refs: set[str]) -> dict[str, DatasetRefStatus]:
    local_ids = {
        str(fm["id"])
        for fm in dataset_frontmatters(ctx)
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    root = resolve_commons_root()
    commons_available = _has_initialized_commons_layout(root)
    adapter = CommonsEntityAdapter(root) if commons_available else None
    out: dict[str, DatasetRefStatus] = {}
    for ref in refs:
        if ref in local_ids:
            out[ref] = "resolved"
            continue
        if adapter is None:
            out[ref] = "unavailable"
            continue
        try:
            record = adapter.load(ref)
        except CommonsError:
            out[ref] = "missing"
            continue
        kind = record.frontmatter.get("kind") or record.frontmatter.get("type")
        out[ref] = "resolved" if kind == "dataset" else "missing"
    return out


def _has_initialized_commons_layout(root: Path) -> bool:
    return root.is_dir() and all((root / dirname).is_dir() for dirname in _COMMONS_LAYOUT_DIRS)


def _collect_refs(frontmatters: list[dict[str, Any]], row_usage_refs: list[tuple[str, str, str]]) -> set[str]:
    refs = {ref for ref, _consumer, _path in row_usage_refs}
    for fm in frontmatters:
        usage = fm.get("dataset_usage")
        if isinstance(usage, list):
            for entry in usage:
                if isinstance(entry, dict) and isinstance(entry.get("ref"), str):
                    refs.add(entry["ref"])
        datasets = fm.get("datasets")
        if isinstance(datasets, list):
            refs.update(ref for ref in datasets if isinstance(ref, str) and ref.startswith("dataset:"))
        derivation = fm.get("derivation")
        if isinstance(derivation, dict) and isinstance(derivation.get("inputs"), list):
            refs.update(ref for ref in derivation["inputs"] if isinstance(ref, str) and ref.startswith("dataset:"))
    return refs


def _row_usage_refs(ctx: ValidateContext, frontmatters: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        if not is_geneset_frontmatter(fm):
            continue
        ident = fm.get("id")
        path = str(fm.get("_path") or "")
        if not isinstance(ident, str) or not ident:
            continue
        raw_rows = read_member_rows(ctx.project_root, fm)
        if raw_rows is None or isinstance(raw_rows, Exception):
            continue
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError:
            continue
        for row in rows:
            for usage in row.dataset_usage:
                refs.append((str(usage["ref"]), f"{ident}#{row.set_key}", path))
    return refs


@Check(section="dataset influence", order=35)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters = entity_frontmatters(ctx)
    row_refs = _row_usage_refs(ctx, frontmatters)
    statuses = _dataset_ref_statuses(ctx, _collect_refs(frontmatters, row_refs))
    yield from evaluate_dataset_influence(
        frontmatters,
        dataset_ref_status=statuses,
        row_usage_refs=row_refs,
    )

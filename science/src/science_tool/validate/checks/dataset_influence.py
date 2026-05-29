"""Dataset influence/provenance checks for Pillar B1."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

DatasetRefStatus = Literal["resolved", "missing", "unavailable"]
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
            raw_datasets = fm.get("datasets") or []
            if raw_datasets and not isinstance(raw_datasets, list):
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


@Check(section="dataset influence", order=35)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
    return iter(())

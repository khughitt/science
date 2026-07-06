"""Validate check: aggregating outputs must meet their declared support floor.

Opt-in and fail-closed. An output is gated iff its workflow ``outputs[]`` entry
declares a ``support`` block. The floor lives on the workflow entity; the observed
support is a producer-authored stamp propagated by register-run onto the per-output
datapackage under ``science.support``. This check joins them and never reads parquet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_declared_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _workflow_support_floors(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """workflow id -> {output slug -> declared support floor dict}."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for fm in records:
        if fm.get("kind") != "workflow":
            continue
        wf_id = fm.get("id")
        if not isinstance(wf_id, str) or not wf_id:
            continue
        floors: dict[str, dict[str, Any]] = {}
        for output in fm.get("outputs") or []:
            if not isinstance(output, dict):
                continue
            slug = output.get("slug")
            support = output.get("support")
            if isinstance(slug, str) and isinstance(support, dict):
                floors[slug] = support
        if floors:
            out[wf_id] = floors
    return out


def _support_stamp(datapackage: dict[str, Any] | None) -> dict[str, Any] | None:
    if datapackage is None:
        return None
    science = datapackage.get("science")
    if not isinstance(science, dict):
        return None
    support = science.get("support")
    return support if isinstance(support, dict) else None


def _unsafe_datapackage_reason(datapackage: str) -> str | None:
    path = PurePosixPath(datapackage)
    if path.is_absolute():
        return "absolute paths are not allowed"
    if ".." in path.parts:
        return "parent-directory traversal is not allowed"
    return None


def evaluate_aggregation_support(
    entities: Iterable[dict[str, Any]],
    read_datapackage: Callable[[str], dict[str, Any] | None],
) -> Iterator[Result]:
    records = list(entities)
    floors_by_workflow = _workflow_support_floors(records)

    for fm in records:
        if fm.get("kind") != "dataset":
            continue
        derivation = fm.get("derivation")
        datapackage = fm.get("datapackage")
        if not isinstance(derivation, dict) or not isinstance(datapackage, str):
            continue
        wf_id = derivation.get("workflow")
        if not isinstance(wf_id, str):
            continue
        slug = PurePosixPath(datapackage).parent.name
        floor = floors_by_workflow.get(wf_id, {}).get(slug)
        if floor is None:
            continue

        ident = fm.get("id")
        path = fm.get("_path") if isinstance(fm.get("_path"), str) else None
        prefix = f"{ident}: output {slug!r}"
        declared_unit = floor.get("unit")
        floor_min = floor.get("min")
        floor_expected = floor.get("expected")

        unsafe_reason = _unsafe_datapackage_reason(datapackage)
        if unsafe_reason is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} datapackage {datapackage!r} is unsafe: {unsafe_reason}",
                "aggregation-support.stamp-missing",
            )
            continue

        try:
            datapackage_doc = read_datapackage(datapackage)
        except Exception as exc:  # noqa: BLE001 - one bad datapackage must not stop the check
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} could not read datapackage {datapackage!r}: {type(exc).__name__}: {exc}",
                "aggregation-support.stamp-missing",
            )
            continue

        stamp = _support_stamp(datapackage_doc)
        observed = stamp.get("observed") if stamp is not None else None

        if observed is None:
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} declares support floor min={floor_min} but no observed support was stamped",
                "aggregation-support.stamp-missing",
            )
            continue

        stamped_unit = stamp.get("unit") if stamp is not None else None
        if stamped_unit != declared_unit:
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} stamped unit {stamped_unit!r} != declared unit {declared_unit!r}",
                "aggregation-support.unit-mismatch",
            )
            continue

        if not _valid_count(observed):
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} stamped observed={observed!r} is not a non-negative integer",
                "aggregation-support.malformed-stamp",
            )
            continue

        if _valid_declared_count(floor_min) and observed < floor_min:
            yield _result(
                Severity.ERROR,
                path,
                f"{prefix} observed support {observed} < declared floor min={floor_min}",
                "aggregation-support.below-floor",
            )
        elif (
            _valid_declared_count(floor_min)
            and _valid_declared_count(floor_expected)
            and observed >= floor_min
            and observed < floor_expected
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{prefix} observed support {observed} < expected {floor_expected} (>= floor min={floor_min})",
                "aggregation-support.below-expected",
            )


@Check(section="aggregation support", order=34)
def check_aggregation_support(ctx: ValidateContext) -> Iterator[Result]:
    def _read(rel: str) -> dict[str, Any] | None:
        p = ctx.project_root / rel
        if not p.is_file():
            return None
        data = ctx.read_yaml(p)
        return data if isinstance(data, dict) else None

    yield from evaluate_aggregation_support(entity_frontmatters(ctx), _read)

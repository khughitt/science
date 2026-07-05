"""Benchmark metadata checks for dataset frontmatter."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from science_model.packages.schema import (
    BENCHMARK_TASK_SUPPORT_DATE_RE,
    BENCHMARK_TASK_SUPPORT_FIELDS,
    BENCHMARK_TASK_SUPPORT_REASON_RE,
    BENCHMARK_TASK_SUPPORT_STATES,
)
from science_tool.datasets.semantics import dataset_class_for
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_TASK_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _valid_task_id(value: str) -> bool:
    return 2 <= len(value) <= 64 and _TASK_ID_RE.fullmatch(value) is not None


def _result(severity: Severity, path: object, message: str, rule: str) -> Result:
    result_path = Path(path) if isinstance(path, str | Path) else None
    return Result(severity, result_path, None, message, rule, None)


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and any(_nonempty_str(item) for item in value)


def _string_items(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item.strip() for item in value if isinstance(item, str) and item.strip()}


def _task_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [task for task in value if isinstance(task, Mapping)]


def _task_support_mapping(task: Mapping[str, Any]) -> Mapping[str, Any] | None:
    support = task.get("support")
    if support is None:
        return None
    if isinstance(support, Mapping):
        return support
    return {}


def _nonempty_string_items(value: object) -> bool:
    return isinstance(value, list) and all(_nonempty_str(item) for item in value)


def _dataset_class(fm: Mapping[str, Any]) -> str:
    try:
        return dataset_class_for(fm)
    except ValueError:
        return "deposit"


def evaluate_benchmark_metadata(datasets: Iterable[dict]) -> Iterator[Result]:
    for fm in datasets:
        if fm.get("kind") != "dataset":
            continue

        if "benchmark" not in fm:
            continue

        benchmark = fm["benchmark"]
        path = fm.get("_path")
        ident = fm.get("id", "?")
        if _dataset_class(fm) == "pointer":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: pointer dataset carries benchmark metadata",
                "benchmark.pointer-block",
            )

        if not isinstance(benchmark, Mapping):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: benchmark block must be a mapping",
                "benchmark.block-malformed",
            )
            continue

        tasks = _task_mappings(benchmark.get("tasks"))
        limitations = benchmark.get("limitations")
        has_benchmark_kinds = "benchmark_kinds" in benchmark
        benchmark_kinds = _string_items(benchmark.get("benchmark_kinds"))

        if has_benchmark_kinds and not tasks and not _nonempty_string_list(limitations):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: benchmark kinds are listed without tasks or limitations",
                "benchmark.facets-lack-task-or-limitation",
            )

        valid_tasks: list[Mapping[str, Any]] = []
        seen_task_ids: set[str] = set()
        duplicate_task_ids: set[str] = set()
        for task in tasks:
            raw_task_id = task.get("id")
            if not isinstance(raw_task_id, str) or not _valid_task_id(raw_task_id):
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: benchmark task id {raw_task_id!r} must be 2-64 chars of lowercase kebab-case",
                    "benchmark.task-id-invalid",
                )
                continue

            valid_tasks.append(task)
            if raw_task_id in seen_task_ids:
                duplicate_task_ids.add(raw_task_id)
            else:
                seen_task_ids.add(raw_task_id)

        for task_id in sorted(duplicate_task_ids):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: duplicate benchmark task id {task_id!r}",
                "benchmark.task-id-duplicate",
            )

        for task in valid_tasks:
            support = _task_support_mapping(task)
            if support is not None:
                for key in sorted(set(support) - BENCHMARK_TASK_SUPPORT_FIELDS):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support field {key!r} is invalid",
                        "benchmark.task-support-field-invalid",
                    )

                state = support.get("state")
                if not isinstance(state, str) or state not in BENCHMARK_TASK_SUPPORT_STATES:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support state {state!r} is invalid",
                        "benchmark.task-support-state-invalid",
                    )

                has_reason = "reason" in support
                reason = support.get("reason")
                reason_text = reason.strip() if isinstance(reason, str) else ""
                if state in {"candidate", "blocked"} and not reason_text:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason is required for state {state!r}",
                        "benchmark.task-support-reason-required",
                    )
                if has_reason and not isinstance(reason, str):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason {reason!r} must be a string",
                        "benchmark.task-support-reason-invalid",
                    )
                elif reason_text and BENCHMARK_TASK_SUPPORT_REASON_RE.fullmatch(reason_text) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason {reason_text!r} must be lowercase kebab-case",
                        "benchmark.task-support-reason-invalid",
                    )

                has_checked_at = "checked_at" in support
                checked_at = support.get("checked_at")
                checked_at_text = checked_at.strip() if isinstance(checked_at, str) else ""
                if has_checked_at and not isinstance(checked_at, str):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support checked_at {checked_at!r} must be a string",
                        "benchmark.task-support-checked-at-invalid",
                    )
                elif checked_at_text and BENCHMARK_TASK_SUPPORT_DATE_RE.fullmatch(checked_at_text) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support checked_at {checked_at_text!r} must be an ISO date",
                        "benchmark.task-support-checked-at-invalid",
                    )

                for key in ("evidence", "notes"):
                    if key in support and not _nonempty_string_items(support.get(key)):
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: benchmark task {task['id']!r} support {key} must be a list of nonempty strings",
                            f"benchmark.task-support-{key}-invalid",
                        )

            if not (_nonempty_str(task.get("task_type")) and _nonempty_str(task.get("prediction_target"))):
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: benchmark task {task['id']!r} is missing task_type or prediction_target",
                    "benchmark.task-sparse",
                )

        if "perturbation-response" in benchmark_kinds and not any(
            _nonempty_str(task.get("intervention")) or _nonempty_string_list(task.get("contexts")) for task in tasks
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: perturbation-response benchmark needs an intervention or contexts",
                "benchmark.perturbation-context-missing",
            )

        if "time-series" in benchmark_kinds and not any(
            _nonempty_string_list(task.get("timepoints")) for task in tasks
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: time-series benchmark needs task timepoints",
                "benchmark.timepoints-missing",
            )


@Check(section="benchmark metadata", order=34)
def check_benchmark_metadata(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_benchmark_metadata(dataset_frontmatters(ctx))

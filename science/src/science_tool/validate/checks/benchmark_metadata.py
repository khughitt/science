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
from science_model.audit import FindingRule

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.datasets.semantics import dataset_class_for
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_TASK_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


SECTION, RULES = declare_validation_rules(
    section_id="benchmark-metadata",
    section_title="benchmark metadata",
    section_order=134,
    rule_ids=(
        "benchmark.block-malformed",
        "benchmark.facets-lack-task-or-limitation",
        "benchmark.perturbation-context-missing",
        "benchmark.pointer-block",
        "benchmark.task-id-duplicate",
        "benchmark.task-id-invalid",
        "benchmark.task-sparse",
        "benchmark.task-support-checked-at-invalid",
        "benchmark.task-support-evidence-invalid",
        "benchmark.task-support-field-invalid",
        "benchmark.task-support-notes-invalid",
        "benchmark.task-support-reason-invalid",
        "benchmark.task-support-reason-required",
        "benchmark.task-support-state-invalid",
        "benchmark.timepoints-missing",
    ),
    severities=frozenset({"error", "warn", "info"}),
)

SUPPORT_FIELD_RULES = {
    "evidence": RULES["benchmark.task-support-evidence-invalid"],
    "notes": RULES["benchmark.task-support-notes-invalid"],
}


def _valid_task_id(value: str) -> bool:
    return 2 <= len(value) <= 64 and _TASK_ID_RE.fullmatch(value) is not None


def _result(
    severity: Severity,
    path: object,
    message: str,
    rule: FindingRule,
    *,
    key: list[str],
) -> CheckObservation:
    result_path = Path(path) if isinstance(path, str | Path) else None
    return validation_observation(
        severity=severity,
        path=result_path,
        line=None,
        message=message,
        rule=rule,
        task=None,
        qualifiers={"key": key},
    )


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


def evaluate_benchmark_metadata(datasets: Iterable[dict]) -> Iterator[CheckObservation]:
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
                RULES["benchmark.pointer-block"],
                key=["benchmark"],
            )

        if not isinstance(benchmark, Mapping):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: benchmark block must be a mapping",
                RULES["benchmark.block-malformed"],
                key=["benchmark"],
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
                RULES["benchmark.facets-lack-task-or-limitation"],
                key=["benchmark-kinds"],
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
                    RULES["benchmark.task-id-invalid"],
                    key=["task-id", repr(raw_task_id)],
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
                RULES["benchmark.task-id-duplicate"],
                key=["task-id", task_id],
            )

        for task in valid_tasks:
            support = _task_support_mapping(task)
            if support is not None:
                for key in sorted(set(support) - BENCHMARK_TASK_SUPPORT_FIELDS):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support field {key!r} is invalid",
                        RULES["benchmark.task-support-field-invalid"],
                        key=[str(task["id"]), key],
                    )

                state = support.get("state")
                if not isinstance(state, str) or state not in BENCHMARK_TASK_SUPPORT_STATES:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support state {state!r} is invalid",
                        RULES["benchmark.task-support-state-invalid"],
                        key=[str(task["id"])],
                    )

                has_reason = "reason" in support
                reason = support.get("reason")
                reason_text = reason.strip() if isinstance(reason, str) else ""
                if state in {"candidate", "blocked"} and not reason_text:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason is required for state {state!r}",
                        RULES["benchmark.task-support-reason-required"],
                        key=[str(task["id"])],
                    )
                if has_reason and not isinstance(reason, str):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason {reason!r} must be a string",
                        RULES["benchmark.task-support-reason-invalid"],
                        key=[str(task["id"])],
                    )
                elif reason_text and BENCHMARK_TASK_SUPPORT_REASON_RE.fullmatch(reason_text) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support reason {reason_text!r} must be lowercase kebab-case",
                        RULES["benchmark.task-support-reason-invalid"],
                        key=[str(task["id"])],
                    )

                has_checked_at = "checked_at" in support
                checked_at = support.get("checked_at")
                checked_at_text = checked_at.strip() if isinstance(checked_at, str) else ""
                if has_checked_at and not isinstance(checked_at, str):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support checked_at {checked_at!r} must be a string",
                        RULES["benchmark.task-support-checked-at-invalid"],
                        key=[str(task["id"])],
                    )
                elif checked_at_text and BENCHMARK_TASK_SUPPORT_DATE_RE.fullmatch(checked_at_text) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task['id']!r} support checked_at {checked_at_text!r} must be an ISO date",
                        RULES["benchmark.task-support-checked-at-invalid"],
                        key=[str(task["id"])],
                    )

                for key in ("evidence", "notes"):
                    if key in support and not _nonempty_string_items(support.get(key)):
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: benchmark task {task['id']!r} support {key} must be a list of nonempty strings",
                            SUPPORT_FIELD_RULES[key],
                            key=[str(task["id"])],
                        )

            if not (_nonempty_str(task.get("task_type")) and _nonempty_str(task.get("prediction_target"))):
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: benchmark task {task['id']!r} is missing task_type or prediction_target",
                    RULES["benchmark.task-sparse"],
                    key=[str(task["id"])],
                )

        if "perturbation-response" in benchmark_kinds and not any(
            _nonempty_str(task.get("intervention")) or _nonempty_string_list(task.get("contexts")) for task in tasks
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: perturbation-response benchmark needs an intervention or contexts",
                RULES["benchmark.perturbation-context-missing"],
                key=["perturbation-response"],
            )

        if "time-series" in benchmark_kinds and not any(
            _nonempty_string_list(task.get("timepoints")) for task in tasks
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: time-series benchmark needs task timepoints",
                RULES["benchmark.timepoints-missing"],
                key=["time-series"],
            )


@Check(section=SECTION, order=34, producer_id="validate.benchmark-metadata", rules=tuple(RULES.values()))
def check_benchmark_metadata(ctx: ValidateContext) -> Iterator[CheckObservation]:
    yield from evaluate_benchmark_metadata(dataset_frontmatters(ctx))

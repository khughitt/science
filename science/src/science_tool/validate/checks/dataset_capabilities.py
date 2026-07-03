"""Dataset capability metadata checks for target coverage.

Coverage gating treats absent or malformed capability metadata conservatively.
This validator surfaces the authoring problem before users discover it only via
`science dataset prioritize --coverage`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_QH_PREFIXES = ("question:", "hypothesis:")
_REQUIRED_FIELD = "required_capabilities"
_PROVIDED_FIELD = "provided_capabilities"


def _result(path: str | None, message: str, rule: str) -> Result:
    return Result(Severity.WARN, Path(path) if path else None, None, message, rule, None)


def evaluate_dataset_capabilities(entities: Iterable[dict[str, Any]]) -> Iterator[Result]:
    records = list(entities)
    dataset_to_targets, target_to_datasets = _frontmatter_reach(records)

    for fm in records:
        ident = fm.get("id")
        if not isinstance(ident, str) or not ident:
            continue
        kind = fm.get("kind") or fm.get("type")
        path = fm.get("_path")
        path_value = path if isinstance(path, str) else None

        if kind == "dataset":
            issue = _capability_shape_issue(fm.get(_PROVIDED_FIELD))
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: provided_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.provided-malformed",
                )
            elif issue == "missing" and dataset_to_targets.get(ident):
                yield _result(
                    path_value,
                    f"{ident}: dataset reaches {sorted(dataset_to_targets[ident])} but declares no provided_capabilities",
                    "dataset-capabilities.provided-missing",
                )
            continue

        if _is_qh(ident):
            issue = _capability_shape_issue(fm.get(_REQUIRED_FIELD))
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: required_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.required-malformed",
                )
            elif issue == "missing" and target_to_datasets.get(ident):
                yield _result(
                    path_value,
                    f"{ident}: target reaches {sorted(target_to_datasets[ident])} but declares no required_capabilities",
                    "dataset-capabilities.required-missing",
                )


def _frontmatter_reach(records: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    dataset_to_targets: dict[str, set[str]] = {}
    target_to_datasets: dict[str, set[str]] = {}
    for fm in records:
        ent_id = fm.get("id")
        if not isinstance(ent_id, str) or not ent_id:
            continue
        kind = fm.get("kind") or fm.get("type") or ""
        related = _string_list(fm.get("related"))
        if kind == "dataset":
            for target in (ref for ref in related if _is_qh(ref)):
                _link(dataset_to_targets, target_to_datasets, ent_id, target)
        elif _is_qh(ent_id):
            for dataset in _dataset_refs(related):
                _link(dataset_to_targets, target_to_datasets, dataset, ent_id)
            for dataset in _dataset_refs(_string_list(fm.get("datasets"))):
                _link(dataset_to_targets, target_to_datasets, dataset, ent_id)

        qh_targets = {ref for ref in related if _is_qh(ref)}
        for dataset in _dataset_usage_refs(fm):
            for target in qh_targets:
                _link(dataset_to_targets, target_to_datasets, dataset, target)
    return dataset_to_targets, target_to_datasets


def _link(
    dataset_to_targets: dict[str, set[str]],
    target_to_datasets: dict[str, set[str]],
    dataset: str,
    target: str,
) -> None:
    dataset_to_targets.setdefault(dataset, set()).add(target)
    target_to_datasets.setdefault(target, set()).add(dataset)


def _capability_shape_issue(value: Any) -> str | None:
    if value is None or value == []:
        return "missing"
    if not isinstance(value, list):
        return "malformed"
    for entry in value:
        if not isinstance(entry, Mapping) or not entry:
            return "malformed"
        for key, raw in entry.items():
            if not isinstance(key, str) or not key.strip():
                return "malformed"
            if not isinstance(raw, str) or not raw.strip():
                return "malformed"
    return None


def _dataset_refs(refs: list[str]) -> list[str]:
    return [ref for ref in refs if ref.startswith("dataset:")]


def _dataset_usage_refs(fm: dict[str, Any]) -> list[str]:
    usage = fm.get("dataset_usage")
    if not isinstance(usage, list):
        return []
    refs: list[str] = []
    for entry in usage:
        if not isinstance(entry, Mapping):
            continue
        ref = entry.get("ref")
        if isinstance(ref, str) and ref.startswith("dataset:"):
            refs.append(ref)
    return refs


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_qh(ref: str) -> bool:
    return ref.startswith(_QH_PREFIXES)


@Check(section="dataset capabilities", order=33)
def check_dataset_capabilities(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_capabilities(entity_frontmatters(ctx))

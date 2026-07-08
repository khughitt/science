"""Dataset capability metadata checks for target coverage.

Coverage gating treats absent or malformed capability metadata conservatively.
This validator surfaces the authoring problem before users discover it only via
`science dataset prioritize --coverage`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from science_tool.datasets.capability_scope import VALID_SCOPES
from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_QH_PREFIXES = ("question:", "hypothesis:")
_REQUIRED_FIELD = "required_capabilities"
_PROVIDED_FIELD = "provided_capabilities"

# Statuses that mark a question/hypothesis as *demand-closed*: its investigation
# is concluded, so it exerts no live pull on data. This is a distinct axis from
# the entity *visibility* set (`_LIVE_STATUSES` in entities.py, which keeps e.g.
# `answered` and `refuted` visible for the record): a concluded target is still
# shown to users but no longer needs capability annotation, and a candidate
# dataset that reaches only concluded targets is not filling a live gap.
#
# Deliberately conservative — a suppressor should fail toward keeping the WARN,
# since a false-suppress hides a real coverage gap while a false-keep only leaves
# a low-value warning. So evidentiary-settled-but-reopenable hypothesis states
# are treated as LIVE: `supported` (can still be strengthened) and `weakened`
# (verdict still open) both keep warning. Likewise `partially-answered`,
# `partially-supported`, and `deferred` retain residual/paused demand.
_DEMAND_CLOSED_STATUSES = frozenset(
    {
        # questions: investigation concluded
        "answered",
        "resolved",
        "closed",
        "rejected",
        "duplicate",
        # hypotheses: verdict settled against the claim
        "refuted",
        # shared terminal / abandoned lifecycle
        "superseded",
        "retired",
        "archived",
        "abandoned",
        "deprecated",
    }
)


def _result(path: str | None, message: str, rule: str) -> Result:
    return Result(Severity.WARN, Path(path) if path else None, None, message, rule, None)


def _is_demand_closed(status: Any) -> bool:
    return isinstance(status, str) and status in _DEMAND_CLOSED_STATUSES


def _scope_gate(
    scope: Any,
    ident: str,
    path_value: str | None,
    field_issue: str | None,
    field_name: str,
) -> tuple[bool, list[Result]]:
    """Resolve a `capability_scope` value.

    Returns (suppress_missing, results):
    - no scope declared            -> (False, [])  normal handling proceeds
    - unknown scope value          -> (False, [scope-unknown])  fail closed
    - valid scope, field empty     -> (True, [])   suppress *-missing
    - valid scope, field present   -> (True, [scope-conflict])  mutual exclusion
    """
    if scope is None:
        return False, []
    if not (isinstance(scope, str) and scope in VALID_SCOPES):
        return False, [
            _result(
                path_value,
                f"{ident}: unknown capability_scope {scope!r}; allowed: {sorted(VALID_SCOPES)}",
                "dataset-capabilities.scope-unknown",
            )
        ]
    if field_issue != "missing":
        return True, [
            _result(
                path_value,
                f"{ident}: capability_scope {scope!r} conflicts with non-empty {field_name}",
                "dataset-capabilities.scope-conflict",
            )
        ]
    return True, []


def evaluate_dataset_capabilities(entities: Iterable[dict[str, Any]]) -> Iterator[Result]:
    records = list(entities)
    dataset_to_targets, target_to_datasets = _frontmatter_reach(records)
    status_by_id = {ident: fm.get("status") for fm in records if isinstance((ident := fm.get("id")), str) and ident}

    for fm in records:
        ident = fm.get("id")
        if not isinstance(ident, str) or not ident:
            continue
        kind = fm.get("kind")
        path = fm.get("_path")
        path_value = path if isinstance(path, str) else None
        scope = fm.get("capability_scope")

        if kind == "dataset":
            issue = _capability_shape_issue(fm.get(_PROVIDED_FIELD))
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _PROVIDED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: provided_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.provided-malformed",
                )
            elif issue == "missing":
                targets = dataset_to_targets.get(ident)
                # Suppress when the dataset's entire reach is demand-closed: an
                # unannotated candidate serving only concluded targets is not a
                # live gap. Keep warning if any reached target is still live.
                if targets and not all(_is_demand_closed(status_by_id.get(t)) for t in targets):
                    yield _result(
                        path_value,
                        f"{ident}: dataset reaches {sorted(targets)} but declares no provided_capabilities",
                        "dataset-capabilities.provided-missing",
                    )
            continue

        if _is_qh(ident):
            issue = _capability_shape_issue(fm.get(_REQUIRED_FIELD))
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _REQUIRED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: required_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.required-malformed",
                )
            # Suppress a concluded target's missing-requirement WARN: it no longer
            # needs capability annotation to gate coverage of a live decision.
            elif issue == "missing" and target_to_datasets.get(ident) and not _is_demand_closed(fm.get("status")):
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
        kind = fm.get("kind") or ""
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

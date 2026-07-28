"""Dataset capability metadata checks for target coverage.

Coverage gating treats absent or malformed capability metadata conservatively.
This validator surfaces the authoring problem before users discover it only via
`science dataset prioritize --coverage`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from science_model.audit import FindingRule

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.datasets.capability_scope import VALID_SCOPES, is_valid_scope
from science_tool.datasets.capability_shape import capability_shape_issue
from science_tool.entities import CLOSED_LIFECYCLE_STATUSES
from science_tool.project_config import validated_entity_schema_version
from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_QH_PREFIXES = ("question:", "hypothesis:")
_REQUIRED_FIELD = "required_capabilities"
_PROVIDED_FIELD = "provided_capabilities"

# *Demand-closed*: the target's investigation is concluded, so it exerts no live pull on data. A
# distinct axis from entity *visibility* (`_LIVE_STATUSES` in entities.py): a concluded target is
# still shown to users, it just no longer needs capability annotation, and a candidate dataset whose
# whole reach is concluded is not filling a live gap.
#
# Deliberately conservative — a suppressor should fail toward KEEPING the WARN, since a false
# suppress hides a real coverage gap while a false keep only leaves a low-value warning.
#
# ☠️ QUESTIONS AND HYPOTHESES NOW ANSWER THIS DIFFERENTLY, and the split is not cosmetic. A
# hypothesis' conclusion moved to `verdict`; a QUESTION still encodes answeredness in `status`,
# because the question slice has not run. One shared status set could not express that, and reading
# a question's `status` through the hypothesis' new rules would silently reopen every answered
# question in the corpus. Each kind is asked in its own vocabulary until its own slice migrates it.
_QUESTION_CLOSED = frozenset({"answered", "resolved", "closed", "rejected", "duplicate"})


SECTION, RULES = declare_validation_rules(
    section_id="dataset-capabilities",
    section_title="dataset capabilities",
    section_order=132,
    rule_ids=(
        "dataset-capabilities.provided-malformed",
        "dataset-capabilities.provided-missing",
        "dataset-capabilities.required-malformed",
        "dataset-capabilities.required-missing",
        "dataset-capabilities.scope-conflict",
        "dataset-capabilities.scope-unknown",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def is_demand_closed(*, kind: str, status: str | None, verdict: str | None = None) -> bool:
    """Whether a question/hypothesis still exerts live pull on data. False == still demanding."""
    # The shared terminal lifecycle: closed for ANY kind, whatever the evidence said.
    if status in CLOSED_LIFECYCLE_STATUSES:
        return True
    if kind == "hypothesis":
        # `refuted` was the ONE hypothesis-specific value any consumer ever read, and it is a
        # VERDICT now, not a status. `supported` and `weakened` stay LIVE on purpose: a supported
        # hypothesis can still be strengthened and a weakened one is still open, so both keep
        # warning. Only a claim the evidence went AGAINST stops demanding data.
        return verdict == "refuted"
    if kind == "question":
        return status in _QUESTION_CLOSED
    return False


def _result(path: str | None, message: str, rule: FindingRule) -> CheckObservation:
    return validation_observation(
        severity=Severity.WARN,
        path=Path(path) if path else None,
        line=None,
        message=message,
        rule=rule,
        task=None,
        qualifiers={"key": []},
    )


def _fm_is_demand_closed(fm: Mapping[str, Any]) -> bool:
    """`is_demand_closed` over one raw frontmatter record."""
    ident = fm.get("id")
    kind = fm.get("kind")
    if not isinstance(kind, str):
        # The id prefix IS the kind for the q/h records this check reaches; a record with neither
        # cannot be classified, and an unclassifiable target must stay LIVE (keep the WARN).
        kind = ident.partition(":")[0] if isinstance(ident, str) else ""
    status = fm.get("status")
    verdict = fm.get("verdict")
    return is_demand_closed(
        kind=kind,
        status=status if isinstance(status, str) else None,
        verdict=verdict if isinstance(verdict, str) else None,
    )


def _scope_gate(
    scope: Any,
    ident: str,
    path_value: str | None,
    field_issue: str | None,
    field_name: str,
) -> tuple[bool, list[CheckObservation]]:
    """Resolve a `capability_scope` value.

    Returns (suppress_missing, results):
    - no scope declared            -> (False, [])  normal handling proceeds
    - unknown scope value          -> (False, [scope-unknown])  fail closed
    - valid scope, field empty     -> (True, [])   suppress *-missing
    - valid scope, field present   -> (True, [scope-conflict])  mutual exclusion
    """
    if scope is None:
        return False, []
    if not is_valid_scope(scope):
        return False, [
            _result(
                path_value,
                f"{ident}: unknown capability_scope {scope!r}; allowed: {sorted(VALID_SCOPES)}",
                RULES["dataset-capabilities.scope-unknown"],
            )
        ]
    if field_issue != "missing":
        return True, [
            _result(
                path_value,
                f"{ident}: capability_scope {scope!r} conflicts with non-empty {field_name}",
                RULES["dataset-capabilities.scope-conflict"],
            )
        ]
    return True, []


def evaluate_dataset_capabilities(entities: Iterable[dict[str, Any]], *, generation: int = 2) -> Iterator[CheckObservation]:
    records = list(entities)
    dataset_to_targets, target_to_datasets = _frontmatter_reach(records)
    # Closure is decided PER RECORD, because it now takes the kind and the verdict -- not a status
    # looked up in one kind-blind map. An id absent from this map is treated as LIVE below, which is
    # the conservative direction: an unknown target keeps the WARN.
    closed_by_id = {
        ident: _fm_is_demand_closed(fm) for fm in records if isinstance((ident := fm.get("id")), str) and ident
    }

    for fm in records:
        ident = fm.get("id")
        if not isinstance(ident, str) or not ident:
            continue
        kind = fm.get("kind")
        path = fm.get("_path")
        path_value = path if isinstance(path, str) else None
        scope = fm.get("capability_scope")

        if kind == "dataset":
            issue = capability_shape_issue(fm.get(_PROVIDED_FIELD), generation=generation)
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _PROVIDED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: {_malformed_message(_PROVIDED_FIELD, generation=generation)}",
                    RULES["dataset-capabilities.provided-malformed"],
                )
            elif issue == "missing":
                targets = dataset_to_targets.get(ident)
                # Suppress when the dataset's entire reach is demand-closed: an
                # unannotated candidate serving only concluded targets is not a
                # live gap. Keep warning if any reached target is still live.
                if targets and not all(closed_by_id.get(t, False) for t in targets):
                    yield _result(
                        path_value,
                        f"{ident}: dataset reaches {sorted(targets)} but declares no provided_capabilities",
                        RULES["dataset-capabilities.provided-missing"],
                    )
            continue

        if _is_qh(ident):
            issue = capability_shape_issue(fm.get(_REQUIRED_FIELD), generation=generation)
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _REQUIRED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: {_malformed_message(_REQUIRED_FIELD, generation=generation)}",
                    RULES["dataset-capabilities.required-malformed"],
                )
            # Suppress a concluded target's missing-requirement WARN: it no longer
            # needs capability annotation to gate coverage of a live decision.
            elif issue == "missing" and target_to_datasets.get(ident) and not _fm_is_demand_closed(fm):
                yield _result(
                    path_value,
                    f"{ident}: target reaches {sorted(target_to_datasets[ident])} but declares no required_capabilities",
                    RULES["dataset-capabilities.required-missing"],
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


def _malformed_message(field_name: str, *, generation: int) -> str:
    if generation >= 3:
        return f"{field_name} must be a list of {{data_product, qualifiers}} objects"
    return f"{field_name} must be a non-empty list of non-empty string mappings"


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


@Check(section=SECTION, order=33, producer_id="validate.dataset-capabilities", rules=tuple(RULES.values()))
def check_dataset_capabilities(ctx: ValidateContext) -> Iterator[CheckObservation]:
    # `ctx.manifest` IS the raw science.yaml dict (see `ValidateContext.from_project_root`) --
    # the same authority `validated_entity_schema_version` reads through everywhere else. Absence
    # of a pin means "unpinned", not "generation 0", so it defaults to 2 here.
    generation = validated_entity_schema_version(ctx.manifest) or 2
    yield from evaluate_dataset_capabilities(entity_frontmatters(ctx), generation=generation)

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
)


class ReconciliationApplyError(RuntimeError):
    """Raised when proposition reconciliation apply cannot proceed safely."""


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str
    after_sha256: str
    final_text: str
    changed: bool


@dataclass(frozen=True)
class ApplyActionResult:
    action_id: str
    kind: str
    canonical_proposition: str
    members: tuple[str, ...]
    duplicate_propositions: tuple[str, ...]
    status: str
    changed_paths: tuple[str, ...] = ()
    noop_paths: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ReconciliationApplyReport:
    status: str
    selected_actions: int
    changed_paths: tuple[str, ...]
    noop_paths: tuple[str, ...]
    actions: tuple[ApplyActionResult, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    written_paths: tuple[str, ...] = ()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _format_issue(issue: object, index: int) -> str:
    if not isinstance(issue, Mapping):
        raise ReconciliationApplyError(
            f"action plan has malformed top-level error at index {index}"
        )
    reason = issue.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ReconciliationApplyError("action plan has malformed error entry: missing reason")
    detail = issue.get("detail")
    if detail is None or detail == "":
        return reason
    return f"{reason}: {detail}"


def _format_blocker(action_id: str, blocker: object, index: int) -> str:
    if not isinstance(blocker, Mapping):
        raise ReconciliationApplyError(f"{action_id} has malformed blocker at index {index}")
    reason = blocker.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ReconciliationApplyError(f"{action_id} has malformed blocker at index {index}")
    detail = blocker.get("detail")
    if detail is None or detail == "":
        return reason
    return f"{reason}: {detail}"


def _duplicate_action_ids(actions: Sequence[ReconciliationAction]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for action in actions:
        if action.action_id in seen:
            duplicates.add(action.action_id)
        seen.add(action.action_id)
    return tuple(sorted(duplicates))


def select_canonicalization_actions(
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
) -> tuple[ReconciliationAction, ...]:
    if plan.errors:
        error_messages = "; ".join(
            _format_issue(error, index) for index, error in enumerate(plan.errors)
        )
        raise ReconciliationApplyError(
            "action plan has top-level errors; "
            f"{error_messages}; run plan-proposition-reconciliation first"
        )

    duplicate_action_ids = _duplicate_action_ids(plan.actions)
    if duplicate_action_ids:
        raise ReconciliationApplyError(
            "duplicate reconciliation action id(s) in plan: "
            f"{', '.join(duplicate_action_ids)}"
        )

    by_id = {action.action_id: action for action in plan.actions}
    if requested_action_ids:
        seen_requested_ids: set[str] = set()
        duplicate_requested_ids: set[str] = set()
        for action_id in requested_action_ids:
            if action_id in seen_requested_ids:
                duplicate_requested_ids.add(action_id)
            seen_requested_ids.add(action_id)
        if duplicate_requested_ids:
            raise ReconciliationApplyError(
                "duplicate reconciliation action request(s): "
                f"{', '.join(sorted(duplicate_requested_ids))}"
            )
        unknown = sorted(set(requested_action_ids) - set(by_id))
        if unknown:
            raise ReconciliationApplyError(
                f"unknown reconciliation action(s): {', '.join(unknown)}"
            )
        candidates = tuple(by_id[action_id] for action_id in requested_action_ids)
    else:
        candidates = tuple(
            action
            for action in plan.actions
            if action.kind == "canonicalize_propositions"
            and action.status == "ready"
            and not action.blockers
        )

    selected: list[ReconciliationAction] = []
    for action in candidates:
        if action.kind == "resynthesize_proposition":
            raise ReconciliationApplyError(
                f"{action.action_id} is resynthesize_proposition; "
                "factorization resynthesis is not executable by Half C"
            )
        if action.blockers:
            blocker_messages = [
                _format_blocker(action.action_id, blocker, index)
                for index, blocker in enumerate(action.blockers)
            ]
            raise ReconciliationApplyError(
                f"{action.action_id} has blocker(s): {'; '.join(blocker_messages)}"
            )
        if action.kind != "canonicalize_propositions" or action.status != "ready":
            raise ReconciliationApplyError(
                f"{action.action_id} is {action.status} {action.kind}, "
                "not executable by Half C"
            )
        if not action.canonical_proposition:
            raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
        if len(action.members) < 2:
            raise ReconciliationApplyError(f"{action.action_id} has fewer than two members")
        selected.append(action)

    if not selected:
        raise ReconciliationApplyError("no ready canonicalize_propositions actions to apply")

    seen_members: dict[str, str] = {}
    for action in selected:
        for member in action.members:
            other = seen_members.get(member)
            if other is not None and other != action.action_id:
                raise ReconciliationApplyError(
                    f"{member} is targeted by multiple selected actions: "
                    f"{other}, {action.action_id}"
                )
            seen_members[member] = action.action_id

    return tuple(sorted(selected, key=lambda action: action.action_id))

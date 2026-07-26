"""Screen a plan whose `status` UNDER-claims its real progress (design §4.3, §5).

Deterministic, advisory, and PERMANENT WARN: a screen that gates defeats its own
imperfect-but-cheap contract, so this never uses `severity_for_kind` and never
joins a gate tier. Findings feed `science entity review`; a confirmed false
positive is suppressed with an evidence-scoped `accepted_validation` entry (§5.5).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.correspondence.extract import extract_deliverables, extract_task_refs
from science_tool.correspondence.probe import (
    Probe,
    ProbeResult,
    TaskState,
    probe_path,
    resolve_tasks,
)
from science_tool.correspondence.signature import evidence_signature
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# draft < active < complete. Anything else (terminal, unknown) is off-axis: silent.
_LIFECYCLE_RANK = {"draft": 0, "active": 1, "complete": 2}

def _names(probes: list[Probe], result: ProbeResult) -> str:
    return ", ".join(p.target for p in probes if p.result is result) or "none"


def _drift_result(
    rule: str,
    rel_path: Path,
    entity_id: str,
    claimed: str,
    adjudicated: Adjudicated,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
) -> Result:
    signature = evidence_signature(
        claimed=claimed, probes=probes, task_states=task_states, adjudicated=adjudicated.value
    )
    tasks_text = ", ".join(f"{ref}={state.value}" for ref, state in task_states) or "none"
    message = (
        f"{entity_id}: status {claimed!r} under-claims progress "
        f"(adjudicated {adjudicated.value!r}). "
        f"present: {_names(probes, ProbeResult.PRESENT)}; "
        f"absent: {_names(probes, ProbeResult.ABSENT)}; tasks: {tasks_text}. "
        f"Fix the status to {adjudicated.value!r}, or accept with an evidence-scoped "
        f"health.accepted_validation entry. evidence-signature: {signature}"
    )
    return Result(Severity.WARN, rel_path, None, message, rule, None)


@Check(section="plan correspondence drift", order=205)
def check_correspondence_drift(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return
    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind, status = fm.get("kind"), fm.get("status")
        # Plans only, by explicit design decision (§3): adding a second correspondence-
        # scoped kind is a deliberate design task, not a config change. The rule id is
        # still derived so that task needs no rename here.
        if kind != "plan" or not isinstance(status, str) or not status:
            continue
        rule = f"{kind}.correspondence-drift"
        claimed_rank = _LIFECYCLE_RANK.get(status)
        if claimed_rank is None:
            continue  # terminal / off-axis claimed status
        deliverables = extract_deliverables(ctx.body(path))
        if not deliverables:
            continue  # nothing probeable -> indeterminate -> silent
        probes = [probe_path(ctx.project_root, d) for d in deliverables]
        task_states = resolve_tasks(ctx.project_root, extract_task_refs(ctx.body(path)))
        adjudicated = adjudicate(
            [p.result for p in probes],
            [state for _ref, state in task_states],
            superseded=False,
        )
        adjudicated_rank = _LIFECYCLE_RANK.get(adjudicated.value)
        if adjudicated_rank is None:
            continue  # indeterminate / off-axis
        if claimed_rank < adjudicated_rank:  # UNDER-CLAIM
            raw_id = fm.get("id")
            entity_id = raw_id if isinstance(raw_id, str) else path.stem
            yield _drift_result(
                rule, path.relative_to(ctx.project_root), entity_id, status, adjudicated, probes, task_states
            )

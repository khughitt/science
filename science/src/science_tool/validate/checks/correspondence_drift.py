"""Screen a plan whose `status` UNDER-claims its real progress (design §4.3, §5).

Deterministic, advisory, and PERMANENT WARN: a screen that gates defeats its own
imperfect-but-cheap contract, so this never uses `severity_for_kind` and never
joins a gate tier. Findings feed `science entity review`; a confirmed false
positive is suppressed with an evidence-scoped `accepted_validation` entry (§5.5).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.audit import FindingRule, FindingSection

from science_tool.validate.findings import validation_observation
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
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import CorrespondenceQualifiers
from science_tool.validate.result import Severity

# draft < active < complete. Anything else (terminal, unknown) is off-axis: silent.
_LIFECYCLE_RANK = {"draft": 0, "active": 1, "complete": 2}

SECTION = FindingSection(
    id="correspondence-drift",
    title="correspondence drift",
    section_order=159,
)
RULE_CORRESPONDENCE_DRIFT = FindingRule(
    id="plan.correspondence-drift",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=CorrespondenceQualifiers,
    identity_qualifiers=("evidence_signature",),
    title="Plan correspondence drift",
    section=SECTION.id,
    display_order=15901,
    default_visibility="visible",
)


def _names(probes: list[Probe], result: ProbeResult) -> str:
    return ", ".join(p.target for p in probes if p.result is result) or "none"


def _drift_result(
    rel_path: Path,
    entity_id: str,
    claimed: str,
    adjudicated: Adjudicated,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
) -> CheckObservation:
    signature = evidence_signature(
        claimed=claimed, probes=probes, task_states=task_states, adjudicated=adjudicated.value
    )
    tasks_text = ", ".join(f"{ref}={state.value}" for ref, state in task_states) or "none"
    message = (
        f"{entity_id}: status {claimed!r} is below the adjudicated floor "
        f"{adjudicated.value!r}. "
        f"claim holds: {_names(probes, ProbeResult.PRESENT)}; "
        f"claim does not hold: {_names(probes, ProbeResult.ABSENT)}; tasks: {tasks_text}. "
        f"The true status is at least {adjudicated.value!r} and may be higher -- "
        f"`adjudicate()` classifies, it does not estimate, and {Adjudicated.ACTIVE.value!r} is "
        f"its catch-all branch. Verify against the deliverables before setting a status, or "
        f"accept with an evidence-scoped health.accepted_validation entry. "
        f"evidence-signature: {signature}"
    )
    return validation_observation(
        severity=Severity.WARN,
        path=rel_path,
        line=None,
        message=message,
        rule=RULE_CORRESPONDENCE_DRIFT,
        task=None,
        qualifiers={"task": None, "evidence_signature": signature},
    )


@Check(
    section=SECTION,
    order=205,
    producer_id="validate.correspondence-drift",
    rules=(RULE_CORRESPONDENCE_DRIFT,),
)
def check_correspondence_drift(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return
    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind, status = fm.get("kind"), fm.get("status")
        # Plans only, by explicit design decision (§3): adding a second correspondence-
        # scoped kind is a deliberate design task, not a config change.
        if kind != "plan" or not isinstance(status, str) or not status:
            continue
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
                path.relative_to(ctx.project_root),
                entity_id,
                status,
                adjudicated,
                probes,
                task_states,
            )

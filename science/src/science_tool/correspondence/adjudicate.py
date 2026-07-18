"""Deterministic lifecycle adjudication from probe results (design §2, §4.1)."""

from __future__ import annotations

from enum import StrEnum

from science_tool.correspondence.probe import ProbeResult, TaskState


class Adjudicated(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    ARCHIVED = "archived"
    INDETERMINATE = "indeterminate"


def adjudicate(
    deliverables: list[ProbeResult],
    tasks: list[TaskState],
    *,
    superseded: bool,
) -> Adjudicated:
    if superseded:
        return Adjudicated.SUPERSEDED
    if not deliverables or ProbeResult.UNKNOWN in deliverables:
        # Nothing probed, or a probe could not run: the instrument established
        # nothing. That is not evidence of deadness (design §6.3).
        return Adjudicated.INDETERMINATE
    all_present = all(d is ProbeResult.PRESENT for d in deliverables)
    none_present = all(d is ProbeResult.ABSENT for d in deliverables)
    tasks_settled = all(t is TaskState.DONE for t in tasks)  # vacuously true if empty
    tasks_unstarted = not tasks or all(t is TaskState.MISSING for t in tasks)
    if all_present and tasks_settled:
        return Adjudicated.COMPLETE
    if none_present and tasks_unstarted:
        return Adjudicated.DRAFT
    return Adjudicated.ACTIVE

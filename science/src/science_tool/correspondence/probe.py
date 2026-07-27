"""Tri-state probes against the project tree.

Design §5.2/§6.3: `unknown` is not `absent`. Only `absent` is evidence of
deadness; a probe that could not run is a fact about the instrument, and
collapsing the two is exactly how absence of evidence becomes evidence of
absence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from science_model.tasks import TaskStatus

from science_tool.correspondence.extract import Deliverable, Polarity
from science_tool.tasks import task_status_index


class ProbeResult(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class TaskState(StrEnum):
    DONE = "done"
    ACTIVE = "active"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Probe:
    target: str
    result: ProbeResult
    detail: str
    polarity: Polarity = Polarity.CREATE


def probe_path(worktree: Path, deliverable: Deliverable) -> Probe:
    """Probe one declared deliverable.

    `PRESENT` means "the plan's claim about this path holds", not "the file
    exists": for a `REMOVE` deliverable the exit criterion is that the target is
    gone, so its result is inverted. Without that, a retirement plan is scored
    exactly backwards -- the more of it that has succeeded, the less complete it
    reads (fb-2026-07-26-014).
    """
    rel = deliverable.path
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts:
        return Probe(rel, ProbeResult.UNKNOWN, f"{rel}: outside the project, unprobeable")
    target = worktree / rel
    exists = target.exists()
    if deliverable.polarity is Polarity.REMOVE:
        if exists:
            detail = f"{rel}: declared for removal, still at {target}"
            return Probe(rel, ProbeResult.ABSENT, detail, Polarity.REMOVE)
        detail = f"{rel}: declared for removal, gone from {target}"
        return Probe(rel, ProbeResult.PRESENT, detail, Polarity.REMOVE)
    if exists:
        return Probe(rel, ProbeResult.PRESENT, f"{rel}: exists at {target}", Polarity.CREATE)
    return Probe(rel, ProbeResult.ABSENT, f"{rel}: not found at {target}", Polarity.CREATE)


def _state_for(status: str | None) -> TaskState:
    if status is None:
        return TaskState.MISSING
    if status == TaskStatus.DONE:
        return TaskState.DONE
    if status == TaskStatus.RETIRED:
        # Abandonment is off the progress axis: it is neither completion nor
        # work in flight. Same rule as an UNKNOWN probe -- the instrument does
        # not know what it measured.
        return TaskState.UNKNOWN
    return TaskState.ACTIVE


def resolve_tasks(worktree: Path, task_ids: list[str]) -> list[tuple[str, TaskState]]:
    """Resolve every cited task id against the task ledgers, reading them once.

    The status field is the record, not the filename and not which file the
    block sits in. Terminal entries live in ``tasks/done/YYYY-MM.md`` rollups,
    while open tasks live in YAML-frontmatter files under ``tasks/active/``.
    """
    index = task_status_index(worktree / "tasks")
    return [(task_id, _state_for(index.get(task_id))) for task_id in task_ids]


def resolve_task(worktree: Path, task_id: str) -> TaskState:
    return resolve_tasks(worktree, [task_id])[0][1]

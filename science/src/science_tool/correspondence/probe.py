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


class ProbeResult(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class TaskState(StrEnum):
    DONE = "done"
    ACTIVE = "active"
    MISSING = "missing"


@dataclass(frozen=True)
class Probe:
    target: str
    result: ProbeResult
    detail: str


def probe_path(worktree: Path, rel: str) -> Probe:
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts:
        return Probe(rel, ProbeResult.UNKNOWN, f"{rel}: outside the project, unprobeable")
    target = worktree / rel
    if target.exists():
        return Probe(rel, ProbeResult.PRESENT, f"{rel}: exists at {target}")
    return Probe(rel, ProbeResult.ABSENT, f"{rel}: not found at {target}")


def resolve_task(worktree: Path, task_id: str) -> TaskState:
    from science_tool.tasks import find_task_location

    try:
        location = find_task_location(worktree / "tasks", task_id)
    except KeyError:
        return TaskState.MISSING
    return TaskState.DONE if location.path.parent.name == "done" else TaskState.ACTIVE

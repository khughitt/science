"""Tri-state probes against a pinned worktree.

Design §5.2/§6.3: `unknown` is not `absent`. Only `absent` is evidence of
deadness; a probe that could not run is a fact about the instrument, and
collapsing the two is exactly how absence of evidence becomes evidence of
absence.
"""

from __future__ import annotations

import re
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
    done_dir = worktree / "tasks" / "done"
    if done_dir.is_dir():
        # Whole-id match: `t25-*.md` must not be satisfied by `t254-*.md`.
        for path in done_dir.glob(f"{task_id}*.md"):
            stem = path.stem
            if stem == task_id or stem.startswith(f"{task_id}-"):
                return TaskState.DONE
    active = worktree / "tasks" / "active.md"
    if active.is_file():
        if re.search(rf"\b{re.escape(task_id)}\b", active.read_text(errors="replace")):
            return TaskState.ACTIVE
    return TaskState.MISSING

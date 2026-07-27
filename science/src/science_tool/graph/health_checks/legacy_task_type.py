"""Legacy-task-type health check: tasks still carrying the legacy `type:` field."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.health_checks.base import HealthCheck
from science_tool.instruments import InstrumentResult


class LegacyTaskTypeFinding(TypedDict):
    task_id: str
    legacy_type: str
    source_file: str


def collect_legacy_task_type(project_root: Path) -> InstrumentResult[LegacyTaskTypeFinding]:
    """Return the tasks still carrying the legacy `type:` field.

    ``unwired`` when there is no ``tasks/`` directory: no task file was read, so
    "no legacy task types" is a claim about a backlog that was never opened.
    """
    from science_tool.tasks import _parse_path_tasks, _task_search_paths

    tasks_dir = project_root / "tasks"
    if not tasks_dir.is_dir():
        return InstrumentResult.unwired(
            code="tasks_dir_missing",
            reason=f"{tasks_dir.name}/ does not exist; no task file was read",
        )

    findings: list[LegacyTaskTypeFinding] = []
    for path in _task_search_paths(tasks_dir):
        for task in _parse_path_tasks(path):
            if task.type:
                findings.append(
                    LegacyTaskTypeFinding(
                        task_id=task.id,
                        legacy_type=task.type,
                        source_file=str(path.relative_to(project_root)),
                    )
                )
    return InstrumentResult.from_rows(findings)


CHECK = HealthCheck(
    name="legacy_task_type",
    description="Find tasks still carrying the legacy type field.",
    requires_sources=False,
    run=lambda context: collect_legacy_task_type(context.project_root),
    empty=lambda _root: [],
)

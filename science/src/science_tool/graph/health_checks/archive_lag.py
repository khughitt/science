"""Archive-lag health check: completed tasks that should be archived."""

from __future__ import annotations

from typing import TypedDict, cast

from science_tool.graph.health_checks.base import HealthCheck, HealthContext


class TaskArchiveLag(TypedDict):
    done_in_active: int
    retired_in_active: int
    missing_completed: int


def archive_lag_total(archive_lag: TaskArchiveLag) -> int:
    return (
        archive_lag["done_in_active"]
        + archive_lag["retired_in_active"]
        + archive_lag["missing_completed"]
    )


def _collect_archive_lag(context: HealthContext) -> TaskArchiveLag:
    from science_tool.tasks_archive import count_archivable

    return cast("TaskArchiveLag", count_archivable(context.project_root / "tasks"))


CHECK = HealthCheck(
    name="archive_lag",
    description="Count completed tasks that should be archived.",
    requires_sources=False,
    run=_collect_archive_lag,
    empty=lambda _root: {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
)

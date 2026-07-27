from __future__ import annotations

from datetime import date
from pathlib import Path

from science_model.tasks import Task
from science_tool import tasks_ledger
from science_tool.tasks import render_tasks


def _task(
    task_id: str,
    *,
    title: str = "Task",
    completed: date | None = date(2026, 3, 15),
    description: str = "Description.",
) -> Task:
    return Task(
        id=task_id,
        title=title,
        status="done",
        created=date(2026, 3, 1),
        completed=completed,
        description=description,
    )


def test_appends_absent_terminal_task_to_completed_month() -> None:
    task = _task("t001")

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [task], {}, today=date(2026, 4, 25)
    )

    assert conflicts == []
    assert post_images == {Path("done/2026-03.md"): render_tasks([task])}


def test_skips_one_structurally_equal_task_already_in_any_ledger() -> None:
    task = _task("t001", description="Description.\n")
    equivalent = _task("t001", description="Description.")

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [task], {Path("done/2026-02.md"): ("", [equivalent])}, today=date(2026, 4, 25)
    )

    assert post_images == {}
    assert conflicts == []


def test_reports_conflict_when_existing_id_differs_structurally() -> None:
    task = _task("t001")
    changed = _task("t001", title="Changed task")

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [task], {Path("done/2026-03.md"): ("", [changed])}, today=date(2026, 4, 25)
    )

    assert post_images == {}
    assert conflicts == ["t001"]


def test_reports_conflict_when_id_occurs_in_two_ledgers() -> None:
    task = _task("t001")

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [task],
        {
            Path("done/2026-02.md"): ("", [_task("t001")]),
            Path("done/2026-03.md"): ("", [_task("t001")]),
        },
        today=date(2026, 4, 25),
    )

    assert post_images == {}
    assert conflicts == ["t001"]


def test_routes_undated_terminal_task_using_explicit_today() -> None:
    task = _task("t001", completed=None)

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [task], {}, today=date(2026, 4, 25)
    )

    assert conflicts == []
    assert post_images == {Path("done/2026-04.md"): render_tasks([task])}


def test_preserves_relative_destination_preamble_and_existing_task_order() -> None:
    existing = _task("t900", completed=date(2026, 3, 10))
    terminal = _task("t001")
    preamble = "# Done March 2026\n\nIntroductory prose.\n\n"

    post_images, conflicts = tasks_ledger.plan_ledger_appends(
        [terminal],
        {Path("done/2026-03.md"): (preamble, [existing])},
        today=date(2026, 4, 25),
    )

    assert conflicts == []
    assert post_images == {
        Path("done/2026-03.md"): preamble + render_tasks([existing, terminal])
    }

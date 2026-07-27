"""Interactive blocker repair against split task storage."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import click
from click.testing import CliRunner
from science_model.tasks import Task

from science_tool import tasks as task_module
from science_tool.cli import main


def _task(
    *,
    title: str = "Blocked task",
    status: str = "blocked",
    blocked_by: list[str] | None = None,
) -> Task:
    return Task(
        id="t001",
        title=title,
        status=status,
        priority="P1",
        aspects=[],
        blocked_by=blocked_by or ["old-string"],
        created=date(2026, 7, 26),
        completed=date(2026, 7, 26) if status == "done" else None,
        description="Task details.",
    )


def _write_active(tasks_dir: Path, task: Task) -> Path:
    path = tasks_dir / "active" / "t001-blocked-task.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def test_fix_blockers_repairs_split_task_and_prompts_without_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active_path = _write_active(tasks_dir, _task())
    lock_state = {"held": False, "acquisitions": 0}
    original_lock = task_module._task_allocation_lock

    @contextmanager
    def tracked_lock(path: Path) -> Iterator[None]:
        lock_state["held"] = True
        lock_state["acquisitions"] += 1
        try:
            with original_lock(path):
                yield
        finally:
            lock_state["held"] = False

    def replace_blocker(*_args: object, **_kwargs: object) -> str:
        assert lock_state["held"] is False
        return "dataset:foo"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(task_module, "_task_allocation_lock", tracked_lock)
    monkeypatch.setattr(click, "prompt", replace_blocker)
    monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: True)

    result = CliRunner().invoke(main, ["tasks", "fix-blockers"])

    assert result.exit_code == 0, result.output
    assert task_module.parse_task_file(active_path).blocked_by == ["dataset:foo"]
    assert lock_state == {"held": False, "acquisitions": 1}


def test_fix_blockers_rejects_active_change_during_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active_path = _write_active(tasks_dir, _task())

    def concurrently_edit_task(*_args: object, **_kwargs: object) -> str:
        changed = _task(title="Concurrent title")
        active_path.write_text(task_module.render_task_file(changed), encoding="utf-8")
        return "dataset:foo"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "prompt", concurrently_edit_task)
    monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: True)

    result = CliRunner().invoke(main, ["tasks", "fix-blockers"])

    assert result.exit_code != 0
    assert "tasks changed under you; re-run fix-blockers" in result.output
    persisted = task_module.parse_task_file(active_path)
    assert persisted.title == "Concurrent title"
    assert persisted.blocked_by == ["old-string"]


def test_fix_blockers_rejects_done_collision_when_active_source_is_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active_path = _write_active(tasks_dir, _task())
    active_before = active_path.read_bytes()

    def concurrently_complete_task(*_args: object, **_kwargs: object) -> str:
        done_path = tasks_dir / "done" / "2026-07.md"
        done_path.parent.mkdir(parents=True)
        done_path.write_text(
            task_module.render_tasks([_task(status="done")]),
            encoding="utf-8",
        )
        return "dataset:foo"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "prompt", concurrently_complete_task)
    monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: True)

    result = CliRunner().invoke(main, ["tasks", "fix-blockers"])

    assert result.exit_code != 0
    assert "duplicate task id t001" in result.output
    assert "tasks changed under you" not in result.output
    assert active_path.read_bytes() == active_before

"""Idempotent recovery for the active-file to done-ledger move."""

from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool import tasks as task_module


def _active_task() -> Task:
    return Task(
        id="t042",
        title="Recoverable move",
        status="active",
        priority="P1",
        aspects=["software-development"],
        created=date(2026, 7, 20),
        description="Original description.",
    )


def _write_active(tasks_dir: Path, task: Task) -> Path:
    path = tasks_dir / "active" / f"{task.id}-recoverable-move.md"
    path.parent.mkdir(parents=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def _write_done(path: Path, *tasks: Task) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_tasks(list(tasks)), encoding="utf-8")


def _move(tasks_dir: Path, task: Task, *, target_status: str) -> None:
    with task_module._task_allocation_lock(tasks_dir):
        task_module._move_task_to_done(tasks_dir, task, target_status=target_status)


def test_retry_after_ledger_append_deletes_active_without_duplicate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _active_task()
    active_path = _write_active(tasks_dir, active)
    completed = active.model_copy(
        update={
            "status": "done",
            "completed": date(2026, 7, 31),
            "description": f"{active.description}\n\nFinished.",
        }
    )
    real_delete = task_module.delete_task_file

    def crash_after_append(_tasks_dir: Path, _task_id: str) -> None:
        raise RuntimeError("simulated crash after ledger append")

    monkeypatch.setattr(task_module, "delete_task_file", crash_after_append)
    with pytest.raises(RuntimeError, match="simulated crash"):
        _move(tasks_dir, completed, target_status="done")

    done_path = tasks_dir / "done" / "2026-07.md"
    assert active_path.is_file()
    assert [task.id for task in task_module.parse_tasks(done_path)] == ["t042"]

    monkeypatch.setattr(task_module, "delete_task_file", real_delete)
    _move(tasks_dir, completed, target_status="done")

    assert not active_path.exists()
    assert [task.id for task in task_module.parse_tasks(done_path)] == ["t042"]


def test_next_month_retry_finds_prior_ledger_and_does_not_append_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _active_task()
    active_path = _write_active(tasks_dir, active)
    first_attempt = active.model_copy(
        update={
            "status": "done",
            "completed": date(2026, 7, 31),
            "description": f"{active.description}\n\nFirst-attempt note.",
        }
    )
    real_delete = task_module.delete_task_file

    def crash_after_append(_tasks_dir: Path, _task_id: str) -> None:
        raise RuntimeError("simulated crash after ledger append")

    monkeypatch.setattr(task_module, "delete_task_file", crash_after_append)
    with pytest.raises(RuntimeError, match="simulated crash"):
        _move(tasks_dir, first_attempt, target_status="done")

    monkeypatch.setattr(task_module, "delete_task_file", real_delete)
    next_month_retry = active.model_copy(
        update={"status": "done", "completed": date(2026, 8, 1)}
    )
    _move(tasks_dir, next_month_retry, target_status="done")

    assert not active_path.exists()
    assert [task.id for task in task_module.parse_tasks(tasks_dir / "done" / "2026-07.md")] == [
        "t042"
    ]
    assert not (tasks_dir / "done" / "2026-08.md").exists()


def test_retry_refuses_ledger_occurrence_with_changed_stable_field(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _active_task()
    active_path = _write_active(tasks_dir, active)
    conflicting = active.model_copy(
        update={
            "title": "Different task",
            "status": "done",
            "completed": date(2026, 7, 31),
        }
    )
    done_path = tasks_dir / "done" / "2026-07.md"
    _write_done(done_path, conflicting)
    retry = active.model_copy(update={"status": "done", "completed": date(2026, 8, 1)})

    with pytest.raises(ValueError, match=r"conflicting.*t042"):
        _move(tasks_dir, retry, target_status="done")

    assert active_path.is_file()
    assert task_module.parse_tasks(done_path) == [conflicting]
    assert not (tasks_dir / "done" / "2026-08.md").exists()


def test_done_retry_refuses_matching_retired_ledger_occurrence(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _active_task()
    active_path = _write_active(tasks_dir, active)
    retired = active.model_copy(
        update={"status": "retired", "completed": date(2026, 7, 31)}
    )
    done_path = tasks_dir / "done" / "2026-07.md"
    _write_done(done_path, retired)
    retry = active.model_copy(update={"status": "done", "completed": date(2026, 8, 1)})

    with pytest.raises(ValueError, match=r"conflicting.*t042"):
        _move(tasks_dir, retry, target_status="done")

    assert active_path.is_file()
    assert task_module.parse_tasks(done_path) == [retired]
    assert not (tasks_dir / "done" / "2026-08.md").exists()


def test_retry_refuses_id_occurring_in_two_done_ledgers(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _active_task()
    active_path = _write_active(tasks_dir, active)
    done = active.model_copy(update={"status": "done", "completed": date(2026, 7, 31)})
    older = tasks_dir / "done" / "2026-07.md"
    newer = tasks_dir / "done" / "2026-08.md"
    _write_done(older, done)
    _write_done(newer, done.model_copy(update={"completed": date(2026, 8, 1)}))
    retry = active.model_copy(update={"status": "done", "completed": date(2026, 9, 1)})

    with pytest.raises(ValueError, match=r"multiple.*t042"):
        _move(tasks_dir, retry, target_status="done")

    assert active_path.is_file()
    assert [task.id for task in task_module.parse_tasks(older)] == ["t042"]
    assert [task.id for task in task_module.parse_tasks(newer)] == ["t042"]
    assert not (tasks_dir / "done" / "2026-09.md").exists()

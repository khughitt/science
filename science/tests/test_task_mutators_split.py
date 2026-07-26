"""Task mutations against split per-file storage."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Callable, Iterator

import pytest
from science_model.tasks import Task
from science_tool import tasks as task_module


def _task(
    task_id: str,
    *,
    title: str = "Existing task",
    status: str = "active",
    blocked_by: list[str] | None = None,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        type="dev",
        aspects=[],
        priority="P1",
        status=status,
        blocked_by=blocked_by or [],
        created=date(2026, 7, 20),
        completed=date(2026, 7, 21) if status in {"done", "retired"} else None,
        description="Existing description.",
    )


def _write_active(tasks_dir: Path, task: Task, *, suffix: str = "original") -> Path:
    path = tasks_dir / "active" / f"{task.id}-{suffix}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def _write_done(path: Path, *tasks: Task) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_tasks(list(tasks)), encoding="utf-8")
    return path


def _active_path(tasks_dir: Path, task_id: str) -> Path:
    matches = list((tasks_dir / "active").glob(f"{task_id}-*.md"))
    matches.extend((tasks_dir / "active").glob(f"{task_id}.md"))
    assert len(matches) == 1
    return matches[0]


def test_add_allocates_from_active_and_done_and_creates_one_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    existing = _write_active(tasks_dir, _task("t004", title="Earlier task"))
    _write_done(tasks_dir / "done" / "2026-06.md", _task("t010", status="done"))

    task = task_module.add_task(tmp_path, tasks_dir, "New split task", "P2")

    assert task.id == "t011"
    assert existing.is_file()
    created = _active_path(tasks_dir, "t011")
    assert created.name == "t011-new-split-task.md"
    assert task_module.parse_task_file(created) == task
    assert not (tasks_dir / "active.md").exists()


def test_append_note_rewrites_only_the_active_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    target = _write_active(tasks_dir, _task("t001"))
    untouched = _write_active(tasks_dir, _task("t002", title="Untouched task"))
    untouched_before = untouched.read_bytes()

    task = task_module.append_task_note(
        tasks_dir,
        "t001",
        "Clarified scope.",
        note_date=date(2026, 7, 22),
    )

    assert "- 2026-07-22: Clarified scope." in task.description
    assert not target.exists()
    assert task_module.parse_task_file(_active_path(tasks_dir, "t001")) == task
    assert untouched.read_bytes() == untouched_before
    assert not (tasks_dir / "active.md").exists()


def test_edit_rewrites_and_renames_only_the_active_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    original = _write_active(tasks_dir, _task("t001"))
    untouched = _write_active(tasks_dir, _task("t002", title="Untouched task"))
    untouched_before = untouched.read_bytes()

    task = task_module.edit_task(
        tmp_path,
        tasks_dir,
        "t001",
        title="Renamed task",
        priority="P2",
        status="deferred",
    )

    renamed = tasks_dir / "active" / "t001-renamed-task.md"
    assert not original.exists()
    assert task_module.parse_task_file(renamed) == task
    assert untouched.read_bytes() == untouched_before
    assert not (tasks_dir / "active.md").exists()


def test_complete_moves_task_to_done_and_deletes_active_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))

    task = task_module.complete_task(tasks_dir, "t001", note="Finished.")

    assert task.status == "done"
    assert task.completed == date.today()
    assert not active.exists()
    done = tasks_dir / "done" / f"{date.today():%Y-%m}.md"
    assert task_module.parse_tasks(done) == [task]


def test_retire_moves_task_to_done_and_deletes_active_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))

    task = task_module.retire_task(tasks_dir, "t001", reason="Superseded.")

    assert task.status == "retired"
    assert task.completed == date.today()
    assert not active.exists()
    done = tasks_dir / "done" / f"{date.today():%Y-%m}.md"
    assert task_module.parse_tasks(done) == [task]


def test_defer_rewrites_the_active_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))

    task = task_module.defer_task(tasks_dir, "t001", reason="Waiting for data.")

    assert task.status == "deferred"
    assert "Waiting for data." in task.description
    assert not active.exists()
    assert task_module.parse_task_file(_active_path(tasks_dir, "t001")) == task
    assert not (tasks_dir / "active.md").exists()


def test_block_rewrites_the_active_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))

    task = task_module.block_task(
        tmp_path,
        tasks_dir,
        "t001",
        blocked_by=["task:t002"],
        force=True,
    )

    assert task.status == "blocked"
    assert task.blocked_by == ["task:t002"]
    assert not active.exists()
    assert task_module.parse_task_file(_active_path(tasks_dir, "t001")) == task
    assert not (tasks_dir / "active.md").exists()


def test_unblock_rewrites_the_active_task_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(
        tasks_dir,
        _task("t001", status="blocked", blocked_by=["task:t002"]),
    )

    task = task_module.unblock_task(tasks_dir, "t001")

    assert task.status == "active"
    assert task.blocked_by == []
    assert not active.exists()
    assert task_module.parse_task_file(_active_path(tasks_dir, "t001")) == task
    assert not (tasks_dir / "active.md").exists()


@pytest.mark.parametrize("status", ["done", "retired"])
def test_edit_refuses_to_terminalize_an_active_task(tmp_path: Path, status: str) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))
    before = active.read_bytes()

    with pytest.raises(ValueError, match=r"use science tasks done/retire to close a task"):
        task_module.edit_task(tmp_path, tasks_dir, "t001", status=status)

    assert active.read_bytes() == before


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "\t",
        " leading",
        "trailing ",
        "two\nlines",
        "bare ] bracket",
    ],
    ids=[
        "empty",
        "spaces-only",
        "tab-only",
        "leading-space",
        "trailing-space",
        "newline",
        "closing-bracket",
    ],
)
def test_add_rejects_unsafe_title_without_creating_a_task(tmp_path: Path, title: str) -> None:
    tasks_dir = tmp_path / "tasks"

    with pytest.raises(ValueError, match="task title"):
        task_module.add_task(tmp_path, tasks_dir, title, "P1")

    assert not (tasks_dir / "active").exists()


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "\t",
        " leading",
        "trailing ",
        "two\nlines",
        "bare ] bracket",
    ],
    ids=[
        "empty",
        "spaces-only",
        "tab-only",
        "leading-space",
        "trailing-space",
        "newline",
        "closing-bracket",
    ],
)
def test_edit_rejects_unsafe_title_without_changing_the_task(tmp_path: Path, title: str) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))
    before = active.read_bytes()

    with pytest.raises(ValueError, match="task title"):
        task_module.edit_task(tmp_path, tasks_dir, "t001", title=title)

    assert active.read_bytes() == before
    assert list((tasks_dir / "active").glob("t001*.md")) == [active]


def test_archived_note_rewrites_ledger_in_place_without_creating_active_file(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    ledger = _write_done(
        tasks_dir / "done" / "2026-06.md",
        _task("t001", status="done"),
        _task("t002", title="Untouched archive", status="done"),
    )

    task = task_module.append_task_note(
        tasks_dir,
        "t001",
        "Post-completion note.",
        note_date=date(2026, 7, 22),
    )

    archived = task_module.parse_tasks(ledger)
    assert archived[0] == task
    assert archived[1].title == "Untouched archive"
    assert not (tasks_dir / "active").exists()


def test_archived_edit_rewrites_ledger_in_place_without_creating_active_file(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    ledger = _write_done(
        tasks_dir / "done" / "2026-06.md",
        _task("t001", status="done"),
    )

    task = task_module.edit_task(
        tmp_path,
        tasks_dir,
        "t001",
        title="Renamed archived task",
        priority="P2",
    )

    assert task_module.parse_tasks(ledger) == [task]
    assert ledger.name == "2026-06.md"
    assert not (tasks_dir / "active").exists()


def test_archived_note_atomic_write_failure_preserves_original_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    ledger = _write_done(
        tasks_dir / "done" / "2026-06.md",
        _task("t001", status="done"),
    )
    before = ledger.read_bytes()

    def fail_before_replace(_path: Path, _text: str) -> None:
        raise OSError("simulated atomic write failure")

    monkeypatch.setattr(task_module, "atomic_write_text", fail_before_replace)

    with pytest.raises(OSError, match="simulated atomic write failure"):
        task_module.append_task_note(tasks_dir, "t001", "Should not land.")

    assert ledger.read_bytes() == before


def test_archived_edit_atomic_write_failure_preserves_original_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    ledger = _write_done(
        tasks_dir / "done" / "2026-06.md",
        _task("t001", status="done"),
    )
    before = ledger.read_bytes()

    def fail_before_replace(_path: Path, _text: str) -> None:
        raise OSError("simulated atomic write failure")

    monkeypatch.setattr(task_module, "atomic_write_text", fail_before_replace)

    with pytest.raises(OSError, match="simulated atomic write failure"):
        task_module.edit_task(tmp_path, tasks_dir, "t001", priority="P2")

    assert ledger.read_bytes() == before


CrashDuplicateMutation = Callable[[Path, Path], object]


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "note",
            lambda project_root, tasks_dir: task_module.append_task_note(
                tasks_dir,
                "t001",
                "Should not land.",
            ),
        ),
        (
            "edit",
            lambda project_root, tasks_dir: task_module.edit_task(
                project_root,
                tasks_dir,
                "t001",
                priority="P3",
            ),
        ),
        (
            "defer",
            lambda project_root, tasks_dir: task_module.defer_task(
                tasks_dir,
                "t001",
                reason="Should not land.",
            ),
        ),
        (
            "block",
            lambda project_root, tasks_dir: task_module.block_task(
                project_root,
                tasks_dir,
                "t001",
                blocked_by=["task:t999"],
                force=True,
            ),
        ),
        (
            "unblock",
            lambda project_root, tasks_dir: task_module.unblock_task(tasks_dir, "t001"),
        ),
    ],
)
def test_non_recovery_mutators_leave_crash_duplicate_inert(
    tmp_path: Path,
    name: str,
    mutate: CrashDuplicateMutation,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))
    ledger = _write_done(
        tasks_dir / "done" / "2026-06.md",
        _task("t001", status="done"),
    )
    active_before = active.read_bytes()
    ledger_before = ledger.read_bytes()

    with pytest.raises(ValueError, match=r"duplicate task id t001"):
        mutate(tmp_path, tasks_dir)

    assert active.read_bytes() == active_before, name
    assert ledger.read_bytes() == ledger_before, name


SuccessfulMutation = Callable[[Path, Path], object]


@pytest.mark.parametrize(
    ("name", "mutate", "initial_status"),
    [
        (
            "add",
            lambda project_root, tasks_dir: task_module.add_task(
                project_root,
                tasks_dir,
                "Added task",
                "P2",
            ),
            None,
        ),
        (
            "note",
            lambda project_root, tasks_dir: task_module.append_task_note(
                tasks_dir,
                "t001",
                "A note.",
            ),
            "active",
        ),
        (
            "edit",
            lambda project_root, tasks_dir: task_module.edit_task(
                project_root,
                tasks_dir,
                "t001",
                priority="P2",
            ),
            "active",
        ),
        (
            "done",
            lambda project_root, tasks_dir: task_module.complete_task(tasks_dir, "t001"),
            "active",
        ),
        (
            "defer",
            lambda project_root, tasks_dir: task_module.defer_task(tasks_dir, "t001"),
            "active",
        ),
        (
            "retire",
            lambda project_root, tasks_dir: task_module.retire_task(tasks_dir, "t001"),
            "active",
        ),
        (
            "block",
            lambda project_root, tasks_dir: task_module.block_task(
                project_root,
                tasks_dir,
                "t001",
                blocked_by=["task:t999"],
                force=True,
            ),
            "active",
        ),
        (
            "unblock",
            lambda project_root, tasks_dir: task_module.unblock_task(tasks_dir, "t001"),
            "blocked",
        ),
    ],
)
def test_each_top_level_mutator_locks_once_and_gates_inside_the_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    mutate: SuccessfulMutation,
    initial_status: str | None,
) -> None:
    tasks_dir = tmp_path / "tasks"
    if initial_status is not None:
        _write_active(
            tasks_dir,
            _task(
                "t001",
                status=initial_status,
                blocked_by=["task:t002"] if initial_status == "blocked" else None,
            ),
        )

    real_lock = task_module._task_allocation_lock
    real_gate = task_module._require_split
    lock_entries = 0
    gate_calls = 0
    lock_held = False

    @contextmanager
    def counted_lock(path: Path) -> Iterator[None]:
        nonlocal lock_entries, lock_held
        lock_entries += 1
        assert not lock_held
        with real_lock(path):
            lock_held = True
            try:
                yield
            finally:
                lock_held = False

    def counted_gate(path: Path) -> None:
        nonlocal gate_calls
        assert lock_held, f"{name} ran the storage gate outside its lock"
        gate_calls += 1
        real_gate(path)

    monkeypatch.setattr(task_module, "_task_allocation_lock", counted_lock)
    monkeypatch.setattr(task_module, "_require_split", counted_gate)

    mutate(tmp_path, tasks_dir)

    assert lock_entries == 1, name
    assert gate_calls == 1, name

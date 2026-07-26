"""Split-layout task reads and searches."""

from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool import tasks as task_module


def _task(
    task_id: str,
    *,
    title: str | None = None,
    status: str = "active",
    blocked_by: list[str] | None = None,
) -> Task:
    return Task(
        id=task_id,
        title=title or task_id,
        status=status,
        priority="P1",
        aspects=[],
        blocked_by=blocked_by or [],
        created=date(2026, 7, 20),
        completed=date(2026, 7, 21) if status == "done" else None,
        description=f"Description for {task_id}.",
    )


def _write_active(tasks_dir: Path, task: Task, *, suffix: str = "task") -> Path:
    path = tasks_dir / "active" / f"{task.id}-{suffix}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def _write_done(path: Path, *tasks: Task) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_tasks(list(tasks)), encoding="utf-8")
    return path


def test_read_active_parses_split_files_in_task_id_order(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active(tasks_dir, _task("t010", title="Ten"))
    _write_active(tasks_dir, _task("t002", title="Two"))

    tasks = task_module._read_active(tasks_dir, require_split=True)

    assert [(task.id, task.title) for task in tasks] == [("t002", "Two"), ("t010", "Ten")]


def test_read_active_rejects_duplicate_ids_across_files(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active(tasks_dir, _task("t001"), suffix="first")
    _write_active(tasks_dir, _task("t001"), suffix="second")

    with pytest.raises(ValueError, match=r"duplicate task ids.*t001"):
        task_module._read_active(tasks_dir)


def test_task_search_paths_are_active_files_then_newest_done_ledgers(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active_2 = _write_active(tasks_dir, _task("t002"))
    active_1 = _write_active(tasks_dir, _task("t001"))
    done_old = _write_done(tasks_dir / "done" / "2026-06.md", _task("t003", status="done"))
    done_new = _write_done(tasks_dir / "done" / "2026-07.md", _task("t004", status="done"))

    assert task_module._task_search_paths(tasks_dir) == [
        active_1,
        active_2,
        done_new,
        done_old,
    ]


def test_find_task_location_rejects_active_and_done_occurrences(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t001"))
    done = _write_done(tasks_dir / "done" / "2026-07.md", _task("t001", status="done"))

    with pytest.raises(ValueError, match="duplicate task id t001") as excinfo:
        task_module.find_task_location(tasks_dir, "t001")

    assert str(active) in str(excinfo.value)
    assert str(done) in str(excinfo.value)


def test_find_task_location_rejects_occurrences_in_two_done_ledgers(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    older = _write_done(tasks_dir / "done" / "2026-06.md", _task("t001", status="done"))
    newer = _write_done(tasks_dir / "done" / "2026-07.md", _task("t001", status="done"))

    with pytest.raises(ValueError, match="duplicate task id t001") as excinfo:
        task_module.find_task_location(tasks_dir, "t001")

    assert str(older) in str(excinfo.value)
    assert str(newer) in str(excinfo.value)


def test_find_task_location_rejects_duplicate_blocks_in_one_done_ledger(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    ledger = _write_done(
        tasks_dir / "done" / "2026-07.md",
        _task("t001", title="First", status="done"),
        _task("t001", title="Second", status="done"),
    )

    with pytest.raises(ValueError, match="duplicate task id t001") as excinfo:
        task_module.find_task_location(tasks_dir, "t001")

    assert str(ledger) in str(excinfo.value)


def test_find_dangling_task_refs_parses_active_frontmatter_files(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active(tasks_dir, _task("t001", blocked_by=["task:t999"]))

    assert task_module.find_dangling_task_refs(tasks_dir) == {"t001": ["task:t999"]}


def test_id_scans_include_active_frontmatter_and_done_headers_without_parsing_bodies(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = _write_active(tasks_dir, _task("t040"))
    active.write_text(
        active.read_text(encoding="utf-8") + "\n## [t999] Body heading, not an active ID\n",
        encoding="utf-8",
    )
    done = _write_done(tasks_dir / "done" / "2026-07.md", _task("t050", status="done"))
    done.write_text(
        done.read_text(encoding="utf-8") + "\n## [not-a-task] Malformed task-like body heading\n",
        encoding="utf-8",
    )

    assert task_module.known_task_ids(tasks_dir) == {"t040", "t050"}
    assert task_module.next_task_id(tasks_dir) == "t051"

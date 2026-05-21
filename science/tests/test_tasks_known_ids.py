from pathlib import Path

from science_tool.tasks import known_task_ids


def test_collects_ids_from_active_and_done(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "done").mkdir(parents=True)
    (tasks / "active.md").write_text(
        "## [t491] Active one\n- created: 2026-01-01\n\n## [t492] Active two\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    (tasks / "done" / "2026-01.md").write_text(
        "## [t100] Done one\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    assert known_task_ids(tasks) == {"t491", "t492", "t100"}


def test_missing_tasks_dir_is_empty(tmp_path: Path) -> None:
    assert known_task_ids(tmp_path / "tasks") == set()


def test_ignores_invalid_headers(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    # 'task-1' is not a valid tNNN id, so it must not be collected.
    (tasks / "active.md").write_text(
        "## [t491] Valid\n- created: 2026-01-01\n\n## [task-1] Invalid\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    assert known_task_ids(tasks) == {"t491"}

from pathlib import Path

from science_tool.tasks import known_task_ids


def test_collects_ids_from_active_and_done(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "active").mkdir(parents=True)
    (tasks / "done").mkdir()
    (tasks / "active" / "t491-one.md").write_text(
        "---\nid: t491\n---\n",
        encoding="utf-8",
    )
    (tasks / "active" / "t492-two.md").write_text(
        "---\nid: t492\n---\n",
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
    (tasks / "active").mkdir(parents=True)
    # Body headings are not task declarations in active frontmatter files.
    (tasks / "active" / "t491-valid.md").write_text(
        "---\nid: t491\n---\n\n## [task-1] Invalid body heading\n",
        encoding="utf-8",
    )
    assert known_task_ids(tasks) == {"t491"}

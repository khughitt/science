from pathlib import Path

import pytest

from science_tool.tasks import known_task_ids, task_status_index


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


# --- task_status_index (fb-2026-07-26-013) ---


def test_status_index_reads_active_and_month_rollups(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "done").mkdir(parents=True)
    (tasks / "active").mkdir()
    (tasks / "active" / "t491-active-one.md").write_text(
        "---\nid: t491\nstatus: active\n---\n",
        encoding="utf-8",
    )
    (tasks / "done" / "2026-01.md").write_text(
        "## [t100] Done one\n- status: done\n- created: 2026-01-01\n- completed: 2026-01-02\n\n"
        "Prose.\n\n"
        "## [t101] Retired one\n- status: retired\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    assert task_status_index(tasks) == {"t491": "active", "t100": "done", "t101": "retired"}


def test_status_index_stops_at_the_end_of_the_field_block(tmp_path: Path) -> None:
    """A body `- status:` line does not override active frontmatter."""
    tasks = tmp_path / "tasks"
    (tasks / "active").mkdir(parents=True)
    (tasks / "active" / "t491-one.md").write_text(
        "---\nid: t491\nstatus: active\n---\n\n"
        "Checklist:\n- status: done\n",
        encoding="utf-8",
    )
    assert task_status_index(tasks) == {"t491": "active"}


def test_status_index_omits_a_task_declaring_no_status(tmp_path: Path) -> None:
    """Absent is not `active` -- callers decide what an undeclared status means."""
    tasks = tmp_path / "tasks"
    (tasks / "active").mkdir(parents=True)
    (tasks / "active" / "t491-one.md").write_text(
        "---\nid: t491\n---\n",
        encoding="utf-8",
    )
    assert task_status_index(tasks) == {}


def test_status_index_rejects_a_duplicated_id(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "done").mkdir(parents=True)
    (tasks / "active").mkdir()
    (tasks / "active" / "t491-one.md").write_text(
        "---\nid: t491\nstatus: active\n---\n",
        encoding="utf-8",
    )
    (tasks / "done" / "2026-01.md").write_text(
        "## [t491] One\n- status: done\n- created: 2026-01-01\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate task id t491"):
        task_status_index(tasks)


def test_status_index_missing_dir_is_empty(tmp_path: Path) -> None:
    assert task_status_index(tmp_path / "tasks") == {}

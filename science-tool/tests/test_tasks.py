"""Tests for task model and markdown parser/renderer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from science_tool.tasks import (
    Task,
    add_task,
    append_task_note,
    block_task,
    complete_task,
    defer_task,
    edit_task,
    find_task_location,
    list_tasks,
    next_task_id,
    parse_tasks,
    render_task,
    render_tasks,
    retire_task,
    unblock_task,
    warn_invalid_statuses,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


SINGLE_TASK = """\
## [t001] Reproduce DNABERT-2 baseline
- type: dev
- priority: P1
- status: active
- related: [hypothesis:h01, topic:dnabert2]
- blocked-by: [t003]
- created: 2026-03-08

Short description of what needs to happen and why.
"""

TAGGED_TASK = """\
## [t010] Tagged task
- type: dev
- priority: P2
- status: proposed
- tags: [lens-system, umap]
- group: visualization
- created: 2026-04-01

A task with tags and a group.
"""

MULTI_TASK = """\
## [t001] First task
- type: dev
- priority: P1
- status: active
- created: 2026-03-08

First description.

## [t002] Second task
- type: research
- priority: P2
- status: blocked
- related: [hypothesis:h01]
- blocked-by: [t001]
- created: 2026-03-09

Second description.
"""


def test_task_has_no_tags_field():
    """After unification, Task should not have a tags field in its schema."""
    from science_model.tasks import Task

    assert "tags" not in Task.model_fields


def test_render_and_parse_task_without_tags(tmp_path: Path) -> None:
    """Tasks should render and parse without any tags field."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    t = add_task(tasks_dir, "Test task", "dev", "P1", related=["topic:umap"])
    assert "- tags:" not in render_task(t)
    tasks = parse_tasks(tasks_dir / "active.md")
    assert tasks[0].related == ["topic:umap"]


def test_parse_single_task_all_fields(tmp_path: Path) -> None:
    f = _write(tmp_path / "active.md", SINGLE_TASK)
    tasks = parse_tasks(f)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.id == "t001"
    assert t.title == "Reproduce DNABERT-2 baseline"
    assert t.type == "dev"
    assert t.priority == "P1"
    assert t.status == "active"
    assert t.created == date(2026, 3, 8)
    assert t.description == "Short description of what needs to happen and why."
    assert t.related == ["hypothesis:h01", "topic:dnabert2"]
    assert t.blocked_by == ["t003"]
    assert t.completed is None


def test_parse_multiple_tasks(tmp_path: Path) -> None:
    f = _write(tmp_path / "active.md", MULTI_TASK)
    tasks = parse_tasks(f)
    assert len(tasks) == 2
    assert tasks[0].id == "t001"
    assert tasks[1].id == "t002"
    assert tasks[1].type == "research"
    assert tasks[1].blocked_by == ["t001"]


def test_parse_empty_file(tmp_path: Path) -> None:
    f = _write(tmp_path / "empty.md", "")
    tasks = parse_tasks(f)
    assert tasks == []


def test_parse_missing_file(tmp_path: Path) -> None:
    tasks = parse_tasks(tmp_path / "nonexistent.md")
    assert tasks == []


def test_parse_optional_fields_omitted(tmp_path: Path) -> None:
    content = """\
## [t005] Minimal task
- type: dev
- priority: P2
- status: todo
- created: 2026-03-10

Just a minimal task.
"""
    f = _write(tmp_path / "active.md", content)
    tasks = parse_tasks(f)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.related == []
    assert t.blocked_by == []
    assert t.completed is None


def test_roundtrip_parse_render_parse(tmp_path: Path) -> None:
    f = _write(tmp_path / "active.md", SINGLE_TASK)
    tasks1 = parse_tasks(f)
    rendered = render_tasks(tasks1)
    f2 = _write(tmp_path / "roundtrip.md", rendered)
    tasks2 = parse_tasks(f2)
    assert len(tasks1) == len(tasks2)
    for a, b in zip(tasks1, tasks2):
        assert a.id == b.id
        assert a.title == b.title
        assert a.type == b.type
        assert a.priority == b.priority
        assert a.status == b.status
        assert a.created == b.created
        assert a.description == b.description
        assert a.related == b.related
        assert a.blocked_by == b.blocked_by
        assert a.completed == b.completed


def test_render_includes_completed_when_present() -> None:
    t = Task(
        id="t010",
        title="Done task",
        type="dev",
        priority="P1",
        status="done",
        created=date(2026, 3, 1),
        description="All done.",
        completed=date(2026, 3, 5),
    )
    rendered = render_task(t)
    assert "- completed: 2026-03-05" in rendered


def test_render_excludes_completed_when_absent() -> None:
    t = Task(
        id="t010",
        title="Active task",
        type="dev",
        priority="P1",
        status="active",
        created=date(2026, 3, 1),
        description="Still going.",
    )
    rendered = render_task(t)
    assert "completed" not in rendered


def test_next_task_id_empty_dir(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    assert next_task_id(tasks_dir) == "t001"


def test_next_task_id_considers_active(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    _write(
        tasks_dir / "active.md",
        """\
## [t003] Some task
- type: dev
- priority: P1
- status: active
- created: 2026-03-08

Desc.
""",
    )
    assert next_task_id(tasks_dir) == "t004"


def test_next_task_id_considers_done_dir(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    _write(
        tasks_dir / "active.md",
        """\
## [t002] Active task
- type: dev
- priority: P1
- status: active
- created: 2026-03-08

Desc.
""",
    )
    _write(
        done_dir / "2026-03.md",
        """\
## [t005] Done task
- type: dev
- priority: P1
- status: done
- created: 2026-03-01
- completed: 2026-03-07

Done desc.
""",
    )
    assert next_task_id(tasks_dir) == "t006"


# ---------------------------------------------------------------------------
# Tests for task operations
# ---------------------------------------------------------------------------


def _make_tasks_dir(tmp_path: Path) -> Path:
    """Create a tasks_dir with an active.md containing one task."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    _write(
        tasks_dir / "active.md",
        """\
## [t001] Existing task
- type: dev
- priority: P1
- status: active
- created: 2026-03-01

Existing description.
""",
    )
    return tasks_dir


class TestAddTask:
    def test_add_creates_task_in_active(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        t = add_task(tasks_dir, title="New task", task_type="research", priority="P2")
        assert t.id == "t001"
        assert t.title == "New task"
        assert t.type == "research"
        assert t.priority == "P2"
        assert t.status == "proposed"
        assert t.created == date.today()
        # Verify it was written to active.md
        tasks = parse_tasks(tasks_dir / "active.md")
        assert len(tasks) == 1
        assert tasks[0].id == "t001"

    def test_add_appends_to_existing(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = add_task(tasks_dir, title="Second task", task_type="dev", priority="P1")
        assert t.id == "t002"
        tasks = parse_tasks(tasks_dir / "active.md")
        assert len(tasks) == 2
        assert tasks[1].id == "t002"

    def test_add_with_optional_fields(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        t = add_task(
            tasks_dir,
            title="Blocked task",
            task_type="dev",
            priority="P1",
            related=["hypothesis:h01"],
            blocked_by=["t001"],
            description="Some notes.",
        )
        assert t.related == ["hypothesis:h01"]
        assert t.blocked_by == ["t001"]
        assert t.description == "Some notes."


class TestCompleteTask:
    def test_complete_moves_to_done(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = complete_task(tasks_dir, "t001")
        assert t.status == "done"
        assert t.completed == date.today()
        # active.md should be empty
        active_tasks = parse_tasks(tasks_dir / "active.md")
        assert len(active_tasks) == 0
        # done file should have the task
        done_path = tasks_dir / "done" / f"{date.today().strftime('%Y-%m')}.md"
        done_tasks = parse_tasks(done_path)
        assert len(done_tasks) == 1
        assert done_tasks[0].id == "t001"

    def test_complete_with_note(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = complete_task(tasks_dir, "t001", note="Finished early.")
        assert "Finished early." in t.description

    def test_complete_not_found_raises(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        with pytest.raises(KeyError):
            complete_task(tasks_dir, "t999")


class TestDeferTask:
    def test_defer_sets_status(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = defer_task(tasks_dir, "t001")
        assert t.status == "deferred"
        tasks = parse_tasks(tasks_dir / "active.md")
        assert tasks[0].status == "deferred"

    def test_defer_with_reason(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = defer_task(tasks_dir, "t001", reason="Waiting on data.")
        assert "Waiting on data." in t.description


class TestBlockTask:
    def test_block_adds_blocker(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = block_task(tasks_dir, "t001", blocked_by="t002")
        assert t.status == "blocked"
        assert "t002" in t.blocked_by
        tasks = parse_tasks(tasks_dir / "active.md")
        assert tasks[0].status == "blocked"
        assert "t002" in tasks[0].blocked_by

    def test_block_appends_to_existing_blockers(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        block_task(tasks_dir, "t001", blocked_by="t002")
        t = block_task(tasks_dir, "t001", blocked_by="t003")
        assert "t002" in t.blocked_by
        assert "t003" in t.blocked_by


class TestUnblockTask:
    def test_unblock_clears_blockers(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        block_task(tasks_dir, "t001", blocked_by="t002")
        t = unblock_task(tasks_dir, "t001")
        assert t.status == "active"
        assert t.blocked_by == []


class TestEditTask:
    def test_edit_priority(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = edit_task(tasks_dir, "t001", priority="P3")
        assert t.priority == "P3"
        tasks = parse_tasks(tasks_dir / "active.md")
        assert tasks[0].priority == "P3"

    def test_edit_multiple_fields(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = edit_task(tasks_dir, "t001", priority="P2", status="todo", aspects=["hypothesis-testing"])
        assert t.priority == "P2"
        assert t.status == "todo"
        assert t.aspects == ["hypothesis-testing"]

    def test_edit_related(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = edit_task(tasks_dir, "t001", related=["hypothesis:h01"])
        assert t.related == ["hypothesis:h01"]

    def test_edit_not_found_raises(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        with pytest.raises(KeyError):
            edit_task(tasks_dir, "t999", priority="P3")


class TestTaskLocation:
    def _setup_active_and_done(self, tmp_path: Path) -> Path:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] Active copy
- priority: P1
- status: active
- created: 2026-04-01

Active description.
""",
        )
        _write(
            tasks_dir / "done" / "2026-03.md",
            """\
## [t002] Older archived task
- priority: P2
- status: done
- created: 2026-03-01
- completed: 2026-03-05

Older archive.
""",
        )
        _write(
            tasks_dir / "done" / "2026-04.md",
            """\
## [t002] Newer archived task
- priority: P0
- status: done
- created: 2026-04-01
- completed: 2026-04-05

Newer archive.
""",
        )
        return tasks_dir

    def test_find_task_location_finds_active_task(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        location = find_task_location(tasks_dir, "t001")

        assert location.path == tasks_dir / "active.md"
        assert location.task.title == "Active copy"

    def test_find_task_location_searches_archives_newest_first(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        location = find_task_location(tasks_dir, "t002")

        assert location.path == tasks_dir / "done" / "2026-04.md"
        assert location.task.title == "Newer archived task"

    def test_find_task_location_active_wins_duplicate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)
        _write(
            tasks_dir / "done" / "2026-05.md",
            """\
## [t001] Archived duplicate
- priority: P3
- status: done
- created: 2026-05-01
- completed: 2026-05-02

Duplicate.
""",
        )

        location = find_task_location(tasks_dir, "t001")

        captured = capsys.readouterr()
        assert location.path == tasks_dir / "active.md"
        assert "WARNING: duplicate task id t001 found in" in captured.err
        assert "active.md" in captured.err
        assert "2026-05.md" in captured.err

    def test_find_task_location_missing_lists_searched_files(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        with pytest.raises(KeyError) as excinfo:
            find_task_location(tasks_dir, "t999")

        message = str(excinfo.value)
        assert "Task t999 not found" in message
        assert "active.md" in message
        assert "2026-03.md" in message
        assert "2026-04.md" in message

    def test_edit_task_rewrites_archived_owner_file(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        task = edit_task(tasks_dir, "t002", description="Updated archived description.")

        assert task.description == "Updated archived description."
        archived_tasks = parse_tasks(tasks_dir / "done" / "2026-04.md")
        older_tasks = parse_tasks(tasks_dir / "done" / "2026-03.md")
        assert archived_tasks[0].description == "Updated archived description."
        assert older_tasks[0].description == "Older archive."

    def test_edit_task_rejects_reopening_archived_task(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        with pytest.raises(ValueError, match="Cannot set archived task t002 to non-closed status 'active'"):
            edit_task(tasks_dir, "t002", status="active")

        archived_tasks = parse_tasks(tasks_dir / "done" / "2026-04.md")
        assert archived_tasks[0].status == "done"

    def test_append_task_note_creates_notes_section(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        task = append_task_note(tasks_dir, "t001", "Clarified scope.", note_date=date(2026, 4, 28))

        assert task.description == "Active description.\n\n### Notes\n\n- 2026-04-28: Clarified scope."

    def test_append_task_note_empty_description_starts_with_notes(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] Empty description
- priority: P1
- status: active
- created: 2026-04-01

""",
        )

        task = append_task_note(tasks_dir, "t001", "First note.", note_date=date(2026, 4, 28))

        assert task.description == "### Notes\n\n- 2026-04-28: First note."

    def test_append_task_note_appends_to_existing_notes_section(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] Has notes
- priority: P1
- status: active
- created: 2026-04-01

Body.

### Notes

- 2026-04-27: First note.
""",
        )

        task = append_task_note(tasks_dir, "t001", "Second note.", note_date=date(2026, 4, 21))

        assert task.description.endswith("- 2026-04-27: First note.\n- 2026-04-21: Second note.")

    def test_append_task_note_inserts_before_following_equal_heading(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] Has trailing heading
- priority: P1
- status: active
- created: 2026-04-01

Body.

### Notes

- 2026-04-27: First note.

### References

- paper:smith2024
""",
        )

        task = append_task_note(tasks_dir, "t001", "Inserted note.", note_date=date(2026, 4, 28))

        assert task.description == (
            "Body.\n\n"
            "### Notes\n\n"
            "- 2026-04-27: First note.\n"
            "- 2026-04-28: Inserted note.\n\n"
            "### References\n\n"
            "- paper:smith2024"
        )

    def test_append_task_note_rewrites_archived_owner_file(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        task = append_task_note(tasks_dir, "t002", "Archived note.", note_date=date(2026, 4, 28))

        assert task.title == "Newer archived task"
        assert "Archived note." in (tasks_dir / "done" / "2026-04.md").read_text()
        assert "Archived note." not in (tasks_dir / "done" / "2026-03.md").read_text()

    def test_append_task_note_rejects_blank_note(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)

        with pytest.raises(ValueError, match="Task note cannot be empty"):
            append_task_note(tasks_dir, "t001", "   ", note_date=date(2026, 4, 28))

    def test_render_tasks_is_idempotent_after_parse(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_active_and_done(tmp_path)
        parsed_once = parse_tasks(tasks_dir / "done" / "2026-04.md")
        rendered_once = render_tasks(parsed_once)
        parsed_twice = parse_tasks(_write(tmp_path / "roundtrip.md", rendered_once))
        rendered_twice = render_tasks(parsed_twice)

        assert rendered_twice == rendered_once

    def test_append_task_note_roundtrip_preserves_other_tasks(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] First
- priority: P1
- status: active
- created: 2026-04-01

First body.

## [t002] Second
- priority: P2
- status: active
- created: 2026-04-02

Second body.
""",
        )
        before = parse_tasks(tasks_dir / "active.md")

        append_task_note(tasks_dir, "t001", "Only first changes.", note_date=date(2026, 4, 28))
        after = parse_tasks(tasks_dir / "active.md")

        assert after[1] == before[1]
        assert after[0].title == before[0].title
        assert after[0].description != before[0].description


class TestListTasks:
    def _setup_multi(self, tmp_path: Path) -> Path:
        _write(
            tmp_path / "science.yaml",
            "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n",
        )
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(
            tasks_dir / "active.md",
            """\
## [t001] Dev task
- priority: P1
- status: active
- aspects: [software-development]
- created: 2026-03-01

Dev desc.

## [t002] Research task
- priority: P2
- status: blocked
- blocked-by: [t001]
- aspects: [hypothesis-testing]
- created: 2026-03-02

Research desc.

## [t003] Another dev task
- priority: P2
- status: active
- related: [hypothesis:h01]
- aspects: [software-development]
- created: 2026-03-03

Another dev desc.
""",
        )
        return tasks_dir

    def test_list_all(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir)
        assert len(result) == 3

    def test_list_by_aspect(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, aspects=["software-development"])
        assert len(result) == 2
        assert {t.id for t in result} == {"t001", "t003"}

    def test_list_by_priority(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, priority="P1")
        assert len(result) == 1
        assert result[0].id == "t001"

    def test_list_by_status(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, status="blocked")
        assert len(result) == 1
        assert result[0].id == "t002"

    def test_list_by_related_exact(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, related="hypothesis:h01")
        assert len(result) == 1
        assert result[0].id == "t003"

    def test_list_by_related_substring(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, related="h01")
        assert len(result) == 1
        assert result[0].id == "t003"

    def test_list_combined_filters(self, tmp_path: Path) -> None:
        tasks_dir = self._setup_multi(tmp_path)
        result = list_tasks(tasks_dir, aspects=["software-development"], priority="P2")
        assert len(result) == 1
        assert result[0].id == "t003"


MIXED_STATUS_TASKS = """\
## [t001] Open task
- type: dev
- priority: P1
- status: proposed
- created: 2026-03-01

Open.

## [t002] Done task
- type: dev
- priority: P2
- status: done
- created: 2026-03-02
- completed: 2026-03-05

Done.

## [t003] Retired task
- type: dev
- priority: P3
- status: retired
- created: 2026-03-03
- completed: 2026-03-06

Retired.

## [t004] Active task
- type: research
- priority: P1
- status: active
- created: 2026-03-04

Active.
"""


class TestDoneHiding:
    def _setup(self, tmp_path: Path) -> Path:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        _write(tasks_dir / "active.md", MIXED_STATUS_TASKS)
        return tasks_dir

    def test_default_hides_done_and_retired(self, tmp_path: Path) -> None:
        tasks_dir = self._setup(tmp_path)
        result = list_tasks(tasks_dir)
        ids = {t.id for t in result}
        assert ids == {"t001", "t004"}

    def test_include_done_shows_all(self, tmp_path: Path) -> None:
        tasks_dir = self._setup(tmp_path)
        result = list_tasks(tasks_dir, include_done=True)
        assert len(result) == 4

    def test_status_filter_done_returns_done(self, tmp_path: Path) -> None:
        tasks_dir = self._setup(tmp_path)
        result = list_tasks(tasks_dir, status="done")
        assert len(result) == 1
        assert result[0].id == "t002"

    def test_status_filter_retired_returns_retired(self, tmp_path: Path) -> None:
        tasks_dir = self._setup(tmp_path)
        result = list_tasks(tasks_dir, status="retired")
        assert len(result) == 1
        assert result[0].id == "t003"


class TestInvalidStatusWarning:
    def test_warns_on_invalid_status(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        tasks = [
            Task(id="t001", title="Bad", type="dev", priority="P1", status="complete", created=date(2026, 3, 1)),
            Task(id="t002", title="Good", type="dev", priority="P1", status="done", created=date(2026, 3, 1)),
        ]
        warn_invalid_statuses(tasks)
        captured = capsys.readouterr()
        assert "WARNING: [t001] has invalid status 'complete'" in captured.err
        assert "t002" not in captured.err

    def test_no_warning_for_valid_statuses(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        tasks = [
            Task(id="t001", title="A", type="dev", priority="P1", status="proposed", created=date(2026, 3, 1)),
            Task(id="t002", title="B", type="dev", priority="P1", status="done", created=date(2026, 3, 1)),
            Task(id="t003", title="C", type="dev", priority="P1", status="retired", created=date(2026, 3, 1)),
        ]
        warn_invalid_statuses(tasks)
        captured = capsys.readouterr()
        assert captured.err == ""


class TestTagsAndGroups:
    def test_legacy_tags_silently_dropped(self, tmp_path: Path) -> None:
        """After parse-time merge removal, `- tags:` in task markdown is silently ignored.
        Use `science-tool graph migrate-tags` to migrate legacy task tags."""
        f = _write(tmp_path / "active.md", TAGGED_TASK)
        tasks = parse_tasks(f)
        assert len(tasks) == 1
        t = tasks[0]
        assert "topic:lens-system" not in t.related
        assert "topic:umap" not in t.related
        assert "meta:lens-system" not in t.related
        assert t.group == "visualization"

    def test_roundtrip_without_tags(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "active.md", TAGGED_TASK)
        tasks1 = parse_tasks(f)
        rendered = render_tasks(tasks1)
        assert "- tags:" not in rendered
        f2 = _write(tmp_path / "roundtrip.md", rendered)
        tasks2 = parse_tasks(f2)
        # Tags are dropped on parse, so round-trip drops them
        assert tasks1[0].related == tasks2[0].related
        assert tasks1[0].group == tasks2[0].group

    def test_empty_tags_not_rendered(self) -> None:
        t = Task(
            id="t001",
            title="Plain task",
            type="dev",
            priority="P2",
            status="proposed",
            created=date(2026, 4, 1),
            description="Desc.",
        )
        rendered = render_task(t)
        assert "- tags:" not in rendered
        assert "- group:" not in rendered

    def test_add_with_related_and_group(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        t = add_task(
            tasks_dir,
            title="Tagged task",
            task_type="dev",
            priority="P2",
            related=["topic:symmetry", "topic:umap"],
            group="lens-system",
        )
        assert t.related == ["topic:symmetry", "topic:umap"]
        assert t.group == "lens-system"
        tasks = parse_tasks(tasks_dir / "active.md")
        assert tasks[0].related == ["topic:symmetry", "topic:umap"]
        assert tasks[0].group == "lens-system"

    def test_edit_group(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = edit_task(tasks_dir, "t001", group="new-group")
        assert t.group == "new-group"

    def test_list_by_related(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        add_task(tasks_dir, "T1", "dev", "P1", related=["topic:alpha", "topic:beta"])
        add_task(tasks_dir, "T2", "dev", "P2", related=["topic:beta", "topic:gamma"])
        add_task(tasks_dir, "T3", "dev", "P1", related=["topic:alpha"])
        result = list_tasks(tasks_dir, related="topic:alpha")
        assert len(result) == 2
        assert {t.id for t in result} == {"t001", "t003"}

    def test_list_by_group(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        add_task(tasks_dir, "T1", "dev", "P1", group="lens")
        add_task(tasks_dir, "T2", "dev", "P2", group="lens")
        add_task(tasks_dir, "T3", "dev", "P1", group="other")
        result = list_tasks(tasks_dir, group="lens")
        assert len(result) == 2


def test_task_accepts_aspects_field() -> None:
    from science_model.tasks import Task

    t = Task(id="t001", title="demo", aspects=["hypothesis-testing"])
    assert t.aspects == ["hypothesis-testing"]


def test_task_defaults_aspects_to_empty_list() -> None:
    from science_model.tasks import Task

    t = Task(id="t001", title="demo")
    assert t.aspects == []


def test_task_create_and_update_carry_aspects() -> None:
    from science_model.tasks import TaskCreate, TaskUpdate

    create = TaskCreate(title="demo", aspects=["software-development"])
    update = TaskUpdate(aspects=["hypothesis-testing"])
    assert create.aspects == ["software-development"]
    assert update.aspects == ["hypothesis-testing"]


def test_parse_task_reads_aspects_inline_field(tmp_path):
    from science_tool.tasks import parse_tasks

    active = tmp_path / "active.md"
    active.write_text(
        "## [t001] Example\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: [hypothesis-testing, computational-analysis]\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    tasks = parse_tasks(active)
    assert len(tasks) == 1
    assert tasks[0].aspects == ["hypothesis-testing", "computational-analysis"]


class TestRetireTask:
    def test_retire_moves_to_done(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = retire_task(tasks_dir, "t001")
        assert t.status == "retired"
        assert t.completed == date.today()
        # active.md should be empty
        active_tasks = parse_tasks(tasks_dir / "active.md")
        assert len(active_tasks) == 0
        # done file should have the task
        done_path = tasks_dir / "done" / f"{date.today().strftime('%Y-%m')}.md"
        done_tasks = parse_tasks(done_path)
        assert len(done_tasks) == 1
        assert done_tasks[0].status == "retired"

    def test_retire_with_reason(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = retire_task(tasks_dir, "t001", reason="Superseded by newer approach")
        assert "**Retired:** Superseded by newer approach" in t.description

    def test_retire_not_found_raises(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        with pytest.raises(KeyError):
            retire_task(tasks_dir, "t999")


def test_render_task_emits_aspects_when_nonempty() -> None:
    from datetime import date

    from science_tool.tasks import Task, render_task

    t = Task(
        id="t001",
        title="Demo",
        priority="P1",
        status="proposed",
        aspects=["hypothesis-testing", "computational-analysis"],
        created=date(2026, 4, 19),
    )
    rendered = render_task(t)
    assert "- aspects: [hypothesis-testing, computational-analysis]" in rendered


def test_render_task_omits_aspects_when_empty() -> None:
    from datetime import date

    from science_tool.tasks import Task, render_task

    t = Task(
        id="t001",
        title="Demo",
        priority="P1",
        status="proposed",
        created=date(2026, 4, 19),
    )
    rendered = render_task(t)
    assert "aspects" not in rendered


def test_add_task_with_aspects(tmp_path) -> None:
    from science_tool.tasks import add_task, parse_tasks

    (tmp_path / "active.md").write_text("")

    task = add_task(
        tasks_dir=tmp_path,
        title="Test task",
        priority="P1",
        aspects=["hypothesis-testing"],
    )
    assert task.aspects == ["hypothesis-testing"]
    assert task.type == ""

    reread = parse_tasks(tmp_path / "active.md")
    assert reread[0].aspects == ["hypothesis-testing"]


def test_add_task_without_aspects_writes_no_aspects_line(tmp_path) -> None:
    from science_tool.tasks import add_task

    (tmp_path / "active.md").write_text("")
    add_task(tasks_dir=tmp_path, title="Test", priority="P2")

    body = (tmp_path / "active.md").read_text()
    assert "aspects" not in body

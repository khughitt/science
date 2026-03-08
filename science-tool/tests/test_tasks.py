"""Tests for task model and markdown parser/renderer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.tasks import Task, next_task_id, parse_tasks, render_task, render_tasks


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

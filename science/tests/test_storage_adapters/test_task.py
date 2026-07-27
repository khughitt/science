"""Tests for TaskAdapter — wraps the existing task DSL parser."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task

import science_tool.graph.storage_adapters.task as task_module
from science_tool.graph.sources import load_project_sources
from science_tool.graph.storage_adapters.task import TaskAdapter
from science_tool.tasks import parse_tasks, render_task_file, render_tasks


def _write_active_task(tasks_dir: Path, task: Task, *, slug: str = "task") -> Path:
    path = tasks_dir / "active" / f"{task.id}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_task_file(task), encoding="utf-8")
    return path


def _task_node_fields(task: Task) -> dict[str, object]:
    return {
        "title": task.title,
        "task_type": task.type,
        "priority": task.priority,
        "status": task.status,
        "blocked_by": task.blocked_by,
        "related": task.related,
        "parent": task.parent,
        "group": task.group,
        "aspects": task.aspects,
        "artifacts": task.artifacts,
        "findings": task.findings,
        "created": task.created,
        "completed": task.completed,
        "content": task.description,
    }


def test_adapter_name() -> None:
    assert TaskAdapter().name == "task"


def test_split_active_and_done_files_build_equivalent_task_nodes(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    active_tasks = [
        Task(
            id="t001",
            project="task-project",
            title="First active task",
            type="research",
            aspects=["methods"],
            priority="P1",
            status="active",
            related=["question:q001"],
            group="graph",
            artifacts=["results/first.json"],
            findings=["finding:f001"],
            created=date(2026, 4, 20),
            description="First body.",
        ),
        Task(
            id="t002",
            project="task-project",
            title="Second active task",
            type="implementation",
            priority="P2",
            status="blocked",
            blocked_by=["task:t001"],
            parent="task:t001",
            created=date(2026, 4, 21),
            description="Second body.",
        ),
    ]
    done_task = Task(
        id="t003",
        project="task-project",
        title="Done task",
        type="research",
        priority="P3",
        status="done",
        created=date(2026, 4, 19),
        completed=date(2026, 4, 22),
        description="Done body.",
    )
    for task in active_tasks:
        _write_active_task(tasks_dir, task, slug=task.title.lower().replace(" ", "-"))
    done_path = tasks_dir / "done" / "2026-04.md"
    done_path.parent.mkdir()
    done_path.write_text(render_tasks([done_task]), encoding="utf-8")
    (tmp_path / "science.yaml").write_text(
        "name: task-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )

    aggregate_baseline = tmp_path / "aggregate-active-baseline.md"
    aggregate_baseline.write_text(render_tasks(active_tasks), encoding="utf-8")
    expected_tasks = [*parse_tasks(aggregate_baseline), done_task]

    sources = load_project_sources(tmp_path, include_commons=False)

    task_nodes = {
        entity.canonical_id: {
            field: getattr(entity, field)
            for field in _task_node_fields(expected_tasks[0])
        }
        for entity in sources.entities
        if entity.kind == "task"
    }
    assert task_nodes == {
        f"task:{task.id}": _task_node_fields(task) for task in expected_tasks
    }
    assert {
        task_id: sources.entity_source_adapters[task_id] for task_id in task_nodes
    } == dict.fromkeys(task_nodes, "task")
    assert {
        row.canonical_id: (row.source_ref.path, row.source_ref.line)
        for row in sources.identity_declarations
        if row.adapter == "task" and row.source_ref is not None
    } == {
        "task:t001": ("tasks/active/t001-first-active-task.md", 0),
        "task:t002": ("tasks/active/t002-second-active-task.md", 0),
        "task:t003": ("tasks/done/2026-04.md", 0),
    }


def test_split_active_file_uses_strict_frontmatter_parser(tmp_path: Path) -> None:
    path = _write_active_task(
        tmp_path / "tasks",
        Task(id="t001", title="T01", status="active", created=date(2026, 4, 20)),
    )
    path.write_text(
        path.read_text().replace("title: T01", "title: T01\nunexpected: value"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown frontmatter key"):
        TaskAdapter().discover(tmp_path)


def test_load_raw_produces_task_entity_shape(tmp_path: Path) -> None:
    _write_active_task(
        tmp_path / "tasks",
        Task(
            id="t001",
            title="T01",
            type="research",
            priority="P1",
            status="active",
            created=date(2026, 4, 20),
            description="Body prose.",
        ),
    )
    adapter = TaskAdapter()
    raw = adapter.load_raw(adapter.discover(tmp_path)[0])

    assert raw["kind"] == "task"
    assert raw["canonical_id"] == "task:t001"
    assert raw["title"] == "T01"
    assert raw["task_type"] == "research"
    assert raw["priority"] == "P1"
    assert raw["status"] == "active"
    assert raw["completed"] is None
    assert raw["content"] == "Body prose."


def test_returns_empty_when_no_tasks_dir(tmp_path: Path) -> None:
    assert TaskAdapter().discover(tmp_path) == []


def test_multiple_active_files_are_loaded_on_cache_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active_task(
        tasks_dir,
        Task(id="t001", title="T01", priority="P1", status="active", created=date(2026, 4, 20)),
    )
    _write_active_task(
        tasks_dir,
        Task(id="t002", title="T02", priority="P2", status="active", created=date(2026, 4, 20)),
    )

    refs = TaskAdapter().discover(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert len(refs) == 2
    assert refs[0].line == 0
    assert refs[1].line == 0
    raws = [TaskAdapter().load_raw(r) for r in refs]
    assert {raw["canonical_id"] for raw in raws} == {"task:t001", "task:t002"}


def test_discover_ignores_historical_alias_archive(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active_task(
        tasks_dir,
        Task(id="t001", title="T01", status="active", created=date(2026, 4, 20)),
    )
    (tasks_dir / "archive.md").write_text(
        "# Historical task aliases\n\n"
        "## [t024] Old analysis task\n"
        "- status: archived\n"
        "- note: Kept only so older documents can resolve task:t024.\n\n"
        "## [t35] Legacy short-form task\n"
        "- status: archived\n"
        "- note: Short-form historical alias.\n",
        encoding="utf-8",
    )

    refs = TaskAdapter().discover(tmp_path)

    assert len(refs) == 1


def test_discover_does_not_read_legacy_active_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(
        "## [t001] T01\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: active\n"
        "- created: 2026-04-20\n\n",
        encoding="utf-8",
    )

    assert TaskAdapter().discover(tmp_path) == []


def test_load_raw_uses_discovered_tasks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_active_task(
        tasks_dir,
        Task(id="t001", title="T01", priority="P1", status="active", created=date(2026, 4, 20)),
    )
    _write_active_task(
        tasks_dir,
        Task(id="t002", title="T02", priority="P2", status="active", created=date(2026, 4, 20)),
    )
    adapter = TaskAdapter()
    refs = adapter.discover(tmp_path)

    def fail_reparse(_path: Path) -> list[object]:
        raise AssertionError("load_raw reparsed task markdown")

    monkeypatch.setattr(task_module, "parse_tasks", fail_reparse)
    monkeypatch.setattr(task_module, "parse_task_file", fail_reparse, raising=False)

    assert [adapter.load_raw(ref)["canonical_id"] for ref in refs] == ["task:t001", "task:t002"]


def test_load_raw_includes_parent(tmp_path: Path) -> None:
    _write_active_task(
        tmp_path / "tasks",
        Task(
            id="t016",
            title="Follow-up",
            type="research",
            priority="P1",
            status="active",
            parent="task:t001",
            created=date(2026, 5, 5),
            description="Body prose.",
        ),
    )
    adapter = TaskAdapter()
    refs = adapter.discover(tmp_path)

    raw = adapter.load_raw(refs[0])

    assert raw["parent"] == "task:t001"

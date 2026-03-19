# Task Management System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a lightweight markdown-based task management system to science-tool with `tasks` CLI subcommand, `/science:tasks` command, and `/science:next-steps` command (replacing `review-tasks`).

**Architecture:** Tasks stored as structured markdown entries in `tasks/active.md` with monthly archival to `tasks/done/YYYY-MM.md`. A new `science_tool.tasks` module handles parsing/writing. CLI exposed via `science-tool tasks` click group. Two new science commands (`tasks`, `next-steps`) and updates to existing commands (`status`, `research-gaps`, `interpret-results`).

**Tech Stack:** Python 3.11+, click, rich, pathlib, re (for markdown parsing). No new dependencies.

---

### Task 1: Task model and markdown parser

**Files:**
- Create: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks.py`

**Step 1: Write the failing tests**

```python
"""Tests for task management module."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from science_tool.tasks import Task, parse_tasks, render_tasks, next_task_id


class TestTaskParsing:
    def test_parse_single_task(self, tmp_path: Path) -> None:
        md = textwrap.dedent("""\
            ## [t001] Reproduce DNABERT-2 baseline
            - type: dev
            - priority: P1
            - status: active
            - related: [hypothesis:h01, topic:dnabert2]
            - blocked-by: [t003]
            - created: 2026-03-08

            Set up the baseline reproduction pipeline.
        """)
        (tmp_path / "active.md").write_text(md)
        tasks = parse_tasks(tmp_path / "active.md")
        assert len(tasks) == 1
        t = tasks[0]
        assert t.id == "t001"
        assert t.title == "Reproduce DNABERT-2 baseline"
        assert t.type == "dev"
        assert t.priority == "P1"
        assert t.status == "active"
        assert t.related == ["hypothesis:h01", "topic:dnabert2"]
        assert t.blocked_by == ["t003"]
        assert t.created == "2026-03-08"
        assert "baseline reproduction" in t.description

    def test_parse_multiple_tasks(self, tmp_path: Path) -> None:
        md = textwrap.dedent("""\
            ## [t001] First task
            - type: research
            - priority: P1
            - status: active
            - created: 2026-03-08

            Do the first thing.

            ## [t002] Second task
            - type: dev
            - priority: P2
            - status: proposed
            - created: 2026-03-08

            Do the second thing.
        """)
        (tmp_path / "active.md").write_text(md)
        tasks = parse_tasks(tmp_path / "active.md")
        assert len(tasks) == 2
        assert tasks[0].id == "t001"
        assert tasks[1].id == "t002"

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / "active.md").write_text("")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks == []

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks == []

    def test_parse_optional_fields_omitted(self, tmp_path: Path) -> None:
        md = textwrap.dedent("""\
            ## [t001] Minimal task
            - type: research
            - priority: P2
            - status: proposed
            - created: 2026-03-08

            Just a simple task.
        """)
        (tmp_path / "active.md").write_text(md)
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].related == []
        assert tasks[0].blocked_by == []


class TestTaskRendering:
    def test_roundtrip(self, tmp_path: Path) -> None:
        md = textwrap.dedent("""\
            ## [t001] First task
            - type: research
            - priority: P1
            - status: active
            - related: [hypothesis:h01]
            - created: 2026-03-08

            Do the first thing.

            ## [t002] Second task
            - type: dev
            - priority: P2
            - status: proposed
            - created: 2026-03-08

            Do the second thing.
        """)
        (tmp_path / "active.md").write_text(md)
        tasks = parse_tasks(tmp_path / "active.md")
        rendered = render_tasks(tasks)
        reparsed = parse_tasks(tmp_path / "out.md")
        # Write rendered, then reparse
        (tmp_path / "out.md").write_text(rendered)
        reparsed = parse_tasks(tmp_path / "out.md")
        assert len(reparsed) == 2
        assert reparsed[0].id == "t001"
        assert reparsed[0].related == ["hypothesis:h01"]

    def test_render_with_completed_field(self) -> None:
        task = Task(
            id="t001", title="Done task", type="dev", priority="P1",
            status="done", created="2026-03-01", completed="2026-03-08",
            description="Finished.",
        )
        rendered = render_tasks([task])
        assert "- completed: 2026-03-08" in rendered


class TestNextTaskId:
    def test_next_id_empty(self, tmp_path: Path) -> None:
        assert next_task_id(tmp_path) == "t001"

    def test_next_id_from_active(self, tmp_path: Path) -> None:
        md = textwrap.dedent("""\
            ## [t003] Some task
            - type: dev
            - priority: P1
            - status: active
            - created: 2026-03-08

            Description.
        """)
        (tmp_path / "active.md").write_text(md)
        assert next_task_id(tmp_path) == "t004"

    def test_next_id_considers_done_dir(self, tmp_path: Path) -> None:
        md_active = textwrap.dedent("""\
            ## [t005] Active task
            - type: dev
            - priority: P1
            - status: active
            - created: 2026-03-08

            Description.
        """)
        md_done = textwrap.dedent("""\
            ## [t010] Old task
            - type: research
            - priority: P2
            - status: done
            - created: 2026-02-01
            - completed: 2026-02-15

            Done.
        """)
        (tmp_path / "active.md").write_text(md_active)
        (tmp_path / "done").mkdir()
        (tmp_path / "done" / "2026-02.md").write_text(md_done)
        assert next_task_id(tmp_path) == "t011"
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.tasks'`

**Step 3: Implement the tasks module**

```python
"""Lightweight markdown-based task management."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Task:
    """A single task entry."""

    id: str
    title: str
    type: str  # "research" or "dev"
    priority: str  # P0, P1, P2, P3
    status: str  # proposed, active, done, blocked, deferred
    created: str  # YYYY-MM-DD
    description: str = ""
    related: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    completed: str | None = None


_HEADING_RE = re.compile(r"^## \[([t]\d+)\] (.+)$")
_FIELD_RE = re.compile(r"^- (\w[\w-]*):\s*(.+)$")


def _parse_list_field(value: str) -> list[str]:
    """Parse a bracketed comma-separated list like '[hypothesis:h01, topic:x]'."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_tasks(path: Path) -> list[Task]:
    """Parse tasks from a markdown file."""
    if not path.exists():
        return []
    text = path.read_text()
    if not text.strip():
        return []

    tasks: list[Task] = []
    current_id: str | None = None
    current_title: str | None = None
    fields: dict[str, str] = {}
    desc_lines: list[str] = []

    def _flush() -> None:
        if current_id is not None and current_title is not None:
            tasks.append(Task(
                id=current_id,
                title=current_title,
                type=fields.get("type", ""),
                priority=fields.get("priority", ""),
                status=fields.get("status", ""),
                created=fields.get("created", ""),
                completed=fields.get("completed"),
                related=_parse_list_field(fields.get("related", "")),
                blocked_by=_parse_list_field(fields.get("blocked-by", "")),
                description="\n".join(desc_lines).strip(),
            ))

    in_fields = False
    for line in text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            _flush()
            current_id = heading_match.group(1)
            current_title = heading_match.group(2)
            fields = {}
            desc_lines = []
            in_fields = True
            continue

        if current_id is None:
            continue

        field_match = _FIELD_RE.match(line)
        if field_match and in_fields:
            fields[field_match.group(1)] = field_match.group(2)
            continue

        # Transition from fields to description on first non-field, non-blank line
        if in_fields and line.strip() == "":
            in_fields = False
            continue
        if in_fields and not field_match:
            in_fields = False

        desc_lines.append(line)

    _flush()
    return tasks


def render_task(task: Task) -> str:
    """Render a single task to markdown."""
    lines = [f"## [{task.id}] {task.title}"]
    lines.append(f"- type: {task.type}")
    lines.append(f"- priority: {task.priority}")
    lines.append(f"- status: {task.status}")
    if task.related:
        lines.append(f"- related: [{', '.join(task.related)}]")
    if task.blocked_by:
        lines.append(f"- blocked-by: [{', '.join(task.blocked_by)}]")
    lines.append(f"- created: {task.created}")
    if task.completed:
        lines.append(f"- completed: {task.completed}")
    lines.append("")
    if task.description:
        lines.append(task.description)
    return "\n".join(lines)


def render_tasks(tasks: list[Task]) -> str:
    """Render a list of tasks to markdown."""
    return "\n\n".join(render_task(t) for t in tasks) + "\n"


def next_task_id(tasks_dir: Path) -> str:
    """Determine the next task ID by scanning active + done files."""
    max_num = 0
    files = []
    active = tasks_dir / "active.md"
    if active.exists():
        files.append(active)
    done_dir = tasks_dir / "done"
    if done_dir.exists():
        files.extend(done_dir.glob("*.md"))

    for f in files:
        for task in parse_tasks(f):
            num = int(task.id[1:])
            if num > max_num:
                max_num = num

    return f"t{max_num + 1:03d}"
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat: add task model and markdown parser"
```

---

### Task 2: Task operations (add, done, defer, block, edit, list)

**Files:**
- Modify: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks.py`

**Step 1: Write the failing tests**

Append to `test_tasks.py`:

```python
from science_tool.tasks import add_task, complete_task, defer_task, block_task, unblock_task, edit_task, list_tasks


class TestAddTask:
    def test_add_creates_file_and_task(self, tmp_path: Path) -> None:
        task = add_task(
            tasks_dir=tmp_path,
            title="Write parser",
            task_type="dev",
            priority="P1",
            related=["hypothesis:h01"],
        )
        assert task.id == "t001"
        assert task.status == "proposed"
        tasks = parse_tasks(tmp_path / "active.md")
        assert len(tasks) == 1
        assert tasks[0].title == "Write parser"

    def test_add_increments_id(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="First", task_type="dev", priority="P1")
        task2 = add_task(tasks_dir=tmp_path, title="Second", task_type="research", priority="P2")
        assert task2.id == "t002"

    def test_add_with_description(self, tmp_path: Path) -> None:
        task = add_task(
            tasks_dir=tmp_path, title="Detailed task", task_type="dev",
            priority="P1", description="Do X then Y.",
        )
        tasks = parse_tasks(tmp_path / "active.md")
        assert "Do X then Y" in tasks[0].description


class TestCompleteTask:
    def test_complete_moves_to_done(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P1")
        complete_task(tasks_dir=tmp_path, task_id="t001", note="Shipped it")
        active = parse_tasks(tmp_path / "active.md")
        assert len(active) == 0
        done_files = list((tmp_path / "done").glob("*.md"))
        assert len(done_files) == 1
        done = parse_tasks(done_files[0])
        assert len(done) == 1
        assert done[0].status == "done"
        assert done[0].completed is not None
        assert "Shipped it" in done[0].description

    def test_complete_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(KeyError):
            complete_task(tasks_dir=tmp_path, task_id="t999")


class TestDeferTask:
    def test_defer_sets_status(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P1")
        defer_task(tasks_dir=tmp_path, task_id="t001", reason="Waiting on data")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].status == "deferred"
        assert "Waiting on data" in tasks[0].description


class TestBlockTask:
    def test_block_adds_blocker(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P1")
        add_task(tasks_dir=tmp_path, title="Task B", task_type="dev", priority="P1")
        block_task(tasks_dir=tmp_path, task_id="t001", blocked_by="t002")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].status == "blocked"
        assert "t002" in tasks[0].blocked_by

    def test_unblock_removes_blocker(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P1")
        add_task(tasks_dir=tmp_path, title="Task B", task_type="dev", priority="P1")
        block_task(tasks_dir=tmp_path, task_id="t001", blocked_by="t002")
        unblock_task(tasks_dir=tmp_path, task_id="t001")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].status == "active"
        assert tasks[0].blocked_by == []


class TestEditTask:
    def test_edit_priority(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P2")
        edit_task(tasks_dir=tmp_path, task_id="t001", priority="P0")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].priority == "P0"

    def test_edit_status(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Task A", task_type="dev", priority="P1")
        edit_task(tasks_dir=tmp_path, task_id="t001", status="active")
        tasks = parse_tasks(tmp_path / "active.md")
        assert tasks[0].status == "active"


class TestListTasks:
    def test_list_filters_by_type(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Research task", task_type="research", priority="P1")
        add_task(tasks_dir=tmp_path, title="Dev task", task_type="dev", priority="P1")
        result = list_tasks(tasks_dir=tmp_path, task_type="dev")
        assert len(result) == 1
        assert result[0].type == "dev"

    def test_list_filters_by_priority(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="High", task_type="dev", priority="P0")
        add_task(tasks_dir=tmp_path, title="Low", task_type="dev", priority="P3")
        result = list_tasks(tasks_dir=tmp_path, priority="P0")
        assert len(result) == 1
        assert result[0].priority == "P0"

    def test_list_filters_by_status(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="Active", task_type="dev", priority="P1")
        edit_task(tasks_dir=tmp_path, task_id="t001", status="active")
        add_task(tasks_dir=tmp_path, title="Proposed", task_type="dev", priority="P1")
        result = list_tasks(tasks_dir=tmp_path, status="active")
        assert len(result) == 1
        assert result[0].status == "active"

    def test_list_filters_by_related(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="A", task_type="dev", priority="P1", related=["hypothesis:h01"])
        add_task(tasks_dir=tmp_path, title="B", task_type="dev", priority="P1", related=["topic:rna"])
        result = list_tasks(tasks_dir=tmp_path, related="hypothesis:h01")
        assert len(result) == 1
        assert result[0].title == "A"

    def test_list_no_filters_returns_all(self, tmp_path: Path) -> None:
        add_task(tasks_dir=tmp_path, title="A", task_type="dev", priority="P1")
        add_task(tasks_dir=tmp_path, title="B", task_type="research", priority="P2")
        result = list_tasks(tasks_dir=tmp_path)
        assert len(result) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks.py -v -k "TestAdd or TestComplete or TestDefer or TestBlock or TestEdit or TestList"`
Expected: FAIL — `ImportError`

**Step 3: Implement the task operations**

Add to `tasks.py`:

```python
from datetime import date


def _find_task(tasks: list[Task], task_id: str) -> Task:
    """Find a task by ID, raise KeyError if not found."""
    for t in tasks:
        if t.id == task_id:
            return t
    raise KeyError(f"Task {task_id} not found")


def _write_active(tasks_dir: Path, tasks: list[Task]) -> None:
    """Write tasks to active.md."""
    (tasks_dir / "active.md").write_text(render_tasks(tasks) if tasks else "")


def add_task(
    tasks_dir: Path,
    title: str,
    task_type: str,
    priority: str,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    description: str = "",
) -> Task:
    """Add a new task to active.md."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_id = next_task_id(tasks_dir)
    task = Task(
        id=task_id,
        title=title,
        type=task_type,
        priority=priority,
        status="proposed",
        created=date.today().isoformat(),
        related=related or [],
        blocked_by=blocked_by or [],
        description=description,
    )
    tasks = parse_tasks(tasks_dir / "active.md")
    tasks.append(task)
    _write_active(tasks_dir, tasks)
    return task


def complete_task(tasks_dir: Path, task_id: str, note: str | None = None) -> Task:
    """Mark a task as done and archive it to done/YYYY-MM.md."""
    tasks = parse_tasks(tasks_dir / "active.md")
    task = _find_task(tasks, task_id)
    task.status = "done"
    task.completed = date.today().isoformat()
    if note:
        if task.description:
            task.description += f"\n\nCompletion note: {note}"
        else:
            task.description = f"Completion note: {note}"

    tasks = [t for t in tasks if t.id != task_id]
    _write_active(tasks_dir, tasks)

    done_dir = tasks_dir / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    month = date.today().strftime("%Y-%m")
    done_path = done_dir / f"{month}.md"
    existing = parse_tasks(done_path)
    existing.append(task)
    done_path.write_text(render_tasks(existing))
    return task


def defer_task(tasks_dir: Path, task_id: str, reason: str | None = None) -> Task:
    """Mark a task as deferred."""
    tasks = parse_tasks(tasks_dir / "active.md")
    task = _find_task(tasks, task_id)
    task.status = "deferred"
    if reason:
        if task.description:
            task.description += f"\n\nDeferred: {reason}"
        else:
            task.description = f"Deferred: {reason}"
    _write_active(tasks_dir, tasks)
    return task


def block_task(tasks_dir: Path, task_id: str, blocked_by: str) -> Task:
    """Mark a task as blocked by another task."""
    tasks = parse_tasks(tasks_dir / "active.md")
    task = _find_task(tasks, task_id)
    if blocked_by not in task.blocked_by:
        task.blocked_by.append(blocked_by)
    task.status = "blocked"
    _write_active(tasks_dir, tasks)
    return task


def unblock_task(tasks_dir: Path, task_id: str) -> Task:
    """Remove all blockers and set status to active."""
    tasks = parse_tasks(tasks_dir / "active.md")
    task = _find_task(tasks, task_id)
    task.blocked_by = []
    task.status = "active"
    _write_active(tasks_dir, tasks)
    return task


def edit_task(
    tasks_dir: Path,
    task_id: str,
    priority: str | None = None,
    status: str | None = None,
    task_type: str | None = None,
    related: list[str] | None = None,
) -> Task:
    """Edit task fields."""
    tasks = parse_tasks(tasks_dir / "active.md")
    task = _find_task(tasks, task_id)
    if priority is not None:
        task.priority = priority
    if status is not None:
        task.status = status
    if task_type is not None:
        task.type = task_type
    if related is not None:
        task.related = related
    _write_active(tasks_dir, tasks)
    return task


def list_tasks(
    tasks_dir: Path,
    task_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    related: str | None = None,
) -> list[Task]:
    """List tasks with optional filters."""
    tasks = parse_tasks(tasks_dir / "active.md")
    if task_type is not None:
        tasks = [t for t in tasks if t.type == task_type]
    if priority is not None:
        tasks = [t for t in tasks if t.priority == priority]
    if status is not None:
        tasks = [t for t in tasks if t.status == status]
    if related is not None:
        tasks = [t for t in tasks if related in t.related]
    return tasks
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat: add task operations (add, done, defer, block, edit, list)"
```

---

### Task 3: CLI commands for `science-tool tasks`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/tests/test_tasks_cli.py`

**Step 1: Write the failing tests**

```python
"""Tests for tasks CLI command group."""

from __future__ import annotations

import json
import textwrap

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestTasksAdd:
    def test_add_basic(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, [
                "tasks", "add", "Write the parser",
                "--type", "dev", "--priority", "P1",
            ])
            assert result.exit_code == 0
            assert "t001" in result.output

    def test_add_with_related(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, [
                "tasks", "add", "Investigate mechanism",
                "--type", "research", "--priority", "P1",
                "--related", "hypothesis:h01",
                "--related", "topic:folding",
            ])
            assert result.exit_code == 0
            assert "t001" in result.output

    def test_add_with_blocked_by(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "First task", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, [
                "tasks", "add", "Second task", "--type", "dev", "--priority", "P1",
                "--blocked-by", "t001",
            ])
            assert result.exit_code == 0
            assert "t002" in result.output


class TestTasksDone:
    def test_done_basic(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "Task A", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, ["tasks", "done", "t001"])
            assert result.exit_code == 0

    def test_done_with_note(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "Task A", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, [
                "tasks", "done", "t001", "--note", "Finished early",
            ])
            assert result.exit_code == 0

    def test_done_nonexistent(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "done", "t999"])
            assert result.exit_code != 0


class TestTasksDefer:
    def test_defer(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "Task A", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, [
                "tasks", "defer", "t001", "--reason", "Blocked on data",
            ])
            assert result.exit_code == 0


class TestTasksBlock:
    def test_block(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "A", "--type", "dev", "--priority", "P1",
            ])
            runner.invoke(main, [
                "tasks", "add", "B", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            assert result.exit_code == 0

    def test_unblock(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "A", "--type", "dev", "--priority", "P1",
            ])
            runner.invoke(main, [
                "tasks", "add", "B", "--type", "dev", "--priority", "P1",
            ])
            runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            result = runner.invoke(main, ["tasks", "unblock", "t001"])
            assert result.exit_code == 0


class TestTasksEdit:
    def test_edit_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "A", "--type", "dev", "--priority", "P2",
            ])
            result = runner.invoke(main, [
                "tasks", "edit", "t001", "--priority", "P0",
            ])
            assert result.exit_code == 0


class TestTasksList:
    def test_list_table(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "A", "--type", "dev", "--priority", "P1",
            ])
            runner.invoke(main, [
                "tasks", "add", "B", "--type", "research", "--priority", "P2",
            ])
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0
            assert "t001" in result.output
            assert "t002" in result.output

    def test_list_json(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "A", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, ["tasks", "list", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data["rows"]) == 1

    def test_list_filter_type(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "A", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "B", "--type", "research", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "list", "--type", "dev"])
            assert result.exit_code == 0
            assert "A" in result.output
            # B may or may not appear in table border etc, so check JSON
            result_json = runner.invoke(main, ["tasks", "list", "--type", "dev", "--format", "json"])
            data = json.loads(result_json.output)
            assert len(data["rows"]) == 1


class TestTasksShow:
    def test_show(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, [
                "tasks", "add", "My task", "--type", "dev", "--priority", "P1",
            ])
            result = runner.invoke(main, ["tasks", "show", "t001"])
            assert result.exit_code == 0
            assert "My task" in result.output

    def test_show_nonexistent(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "show", "t999"])
            assert result.exit_code != 0


class TestTasksSummary:
    def test_summary(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "A", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "B", "--type", "research", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "summary"])
            assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks_cli.py -v`
Expected: FAIL

**Step 3: Add the tasks CLI group to cli.py**

Add before the `if __name__` block at the end of `cli.py`:

```python
from science_tool.tasks import (
    add_task,
    block_task,
    complete_task,
    defer_task,
    edit_task,
    list_tasks,
    parse_tasks,
    unblock_task,
)

DEFAULT_TASKS_DIR = Path("tasks")


@main.group()
def tasks() -> None:
    """Task management commands."""


@tasks.command("add")
@click.argument("title")
@click.option("--type", "task_type", required=True, type=click.Choice(["research", "dev"]))
@click.option("--priority", required=True, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--description", default="")
def tasks_add(
    title: str, task_type: str, priority: str, related: tuple[str, ...],
    blocked_by: tuple[str, ...], description: str,
) -> None:
    """Add a new task."""
    task = add_task(
        tasks_dir=DEFAULT_TASKS_DIR,
        title=title,
        task_type=task_type,
        priority=priority,
        related=list(related),
        blocked_by=list(blocked_by),
        description=description,
    )
    click.echo(f"Created {task.id}: {task.title}")


@tasks.command("done")
@click.argument("task_id")
@click.option("--note", default=None)
def tasks_done(task_id: str, note: str | None) -> None:
    """Mark a task as done and archive it."""
    try:
        task = complete_task(tasks_dir=DEFAULT_TASKS_DIR, task_id=task_id, note=note)
        click.echo(f"Completed {task.id}: {task.title}")
    except KeyError as e:
        raise click.ClickException(str(e))


@tasks.command("defer")
@click.argument("task_id")
@click.option("--reason", default=None)
def tasks_defer(task_id: str, reason: str | None) -> None:
    """Defer a task."""
    try:
        task = defer_task(tasks_dir=DEFAULT_TASKS_DIR, task_id=task_id, reason=reason)
        click.echo(f"Deferred {task.id}: {task.title}")
    except KeyError as e:
        raise click.ClickException(str(e))


@tasks.command("block")
@click.argument("task_id")
@click.option("--by", "blocked_by", required=True)
def tasks_block(task_id: str, blocked_by: str) -> None:
    """Mark a task as blocked by another task."""
    try:
        task = block_task(tasks_dir=DEFAULT_TASKS_DIR, task_id=task_id, blocked_by=blocked_by)
        click.echo(f"Blocked {task.id} by {blocked_by}")
    except KeyError as e:
        raise click.ClickException(str(e))


@tasks.command("unblock")
@click.argument("task_id")
def tasks_unblock(task_id: str) -> None:
    """Remove all blockers from a task."""
    try:
        task = unblock_task(tasks_dir=DEFAULT_TASKS_DIR, task_id=task_id)
        click.echo(f"Unblocked {task.id}: {task.title}")
    except KeyError as e:
        raise click.ClickException(str(e))


@tasks.command("edit")
@click.argument("task_id")
@click.option("--priority", type=click.Choice(["P0", "P1", "P2", "P3"]), default=None)
@click.option("--status", type=click.Choice(["proposed", "active", "blocked", "deferred"]), default=None)
@click.option("--type", "task_type", type=click.Choice(["research", "dev"]), default=None)
def tasks_edit(task_id: str, priority: str | None, status: str | None, task_type: str | None) -> None:
    """Edit task fields."""
    try:
        task = edit_task(
            tasks_dir=DEFAULT_TASKS_DIR, task_id=task_id,
            priority=priority, status=status, task_type=task_type,
        )
        click.echo(f"Updated {task.id}: {task.title}")
    except KeyError as e:
        raise click.ClickException(str(e))


@tasks.command("list")
@click.option("--type", "task_type", type=click.Choice(["research", "dev"]), default=None)
@click.option("--priority", type=click.Choice(["P0", "P1", "P2", "P3"]), default=None)
@click.option("--status", default=None)
@click.option("--related", default=None)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_list(
    task_type: str | None, priority: str | None, status: str | None,
    related: str | None, output_format: str,
) -> None:
    """List tasks with optional filters."""
    result = list_tasks(
        tasks_dir=DEFAULT_TASKS_DIR,
        task_type=task_type, priority=priority, status=status, related=related,
    )
    if not result:
        click.echo("No tasks found.")
        return
    rows = [
        {"id": t.id, "title": t.title, "type": t.type, "priority": t.priority, "status": t.status}
        for t in result
    ]
    emit_query_rows(
        output_format=output_format,
        title="Tasks",
        columns=[("id", "ID"), ("title", "Title"), ("type", "Type"), ("priority", "Priority"), ("status", "Status")],
        rows=rows,
    )


@tasks.command("show")
@click.argument("task_id")
def tasks_show(task_id: str) -> None:
    """Show details for a single task."""
    all_tasks = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    matching = [t for t in all_tasks if t.id == task_id]
    if not matching:
        raise click.ClickException(f"Task {task_id} not found")
    from science_tool.tasks import render_task
    click.echo(render_task(matching[0]))


@tasks.command("summary")
def tasks_summary() -> None:
    """Show task counts by status, type, and priority."""
    all_tasks = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    if not all_tasks:
        click.echo("No active tasks.")
        return

    from collections import Counter
    by_status = Counter(t.status for t in all_tasks)
    by_type = Counter(t.type for t in all_tasks)
    by_priority = Counter(t.priority for t in all_tasks)

    click.echo(f"Total: {len(all_tasks)}")
    click.echo(f"By status: {dict(by_status)}")
    click.echo(f"By type: {dict(by_type)}")
    click.echo(f"By priority: {dict(by_priority)}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_tasks_cli.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_tasks_cli.py
git commit -m "feat: add science-tool tasks CLI subcommands"
```

---

### Task 4: `/science:tasks` command

**Files:**
- Remove: `commands/review-tasks.md`
- Create: `commands/tasks.md`

**Step 1: Write the command file**

```markdown
---
description: Manage research and development tasks — add, complete, defer, list, and filter. Use when the user wants to track work items, mark things done, or see what's on the backlog.
---

# Tasks

Manage the project task queue in `tasks/active.md`.
`$ARGUMENTS` specifies the action (add, done, defer, list, show, summary) and any parameters.

## Setup

Read `tasks/active.md` if it exists. If `tasks/` directory doesn't exist, create it.

## Actions

### No arguments or "list"

Show active tasks sorted by priority (P0 first). Use:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks list
```

### "add <description>"

Interactively create a task. Ask the user for:
- **Type:** research or dev
- **Priority:** P0-P3
- **Related entities:** (optional) e.g. hypothesis:h01, topic:protein-folding

Then run:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks add "<title>" --type=<type> --priority=<priority> [--related=<ref>...]
```

### "done <task_id>"

Mark a task complete. Optionally ask for a completion note.

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks done <task_id> [--note="<note>"]
```

### "defer <task_id>"

Defer a task. Ask for a reason.

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks defer <task_id> [--reason="<reason>"]
```

### Other actions

Pass through to `science-tool tasks`:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool tasks <action> [args...]
```

## After Changes

Commit: `git add tasks/ && git commit -m "tasks: <brief description of change>"`
```

**Step 2: Commit**

```bash
git rm commands/review-tasks.md
git add commands/tasks.md
git commit -m "feat: add /science:tasks command, remove review-tasks"
```

---

### Task 5: `/science:next-steps` command

**Files:**
- Create: `commands/next-steps.md`

**Step 1: Write the command file**

```markdown
---
description: Synthesize recent progress, current project state, and suggest next actions. Use at session start, when the user says "what should I work on", "next steps", "priorities", or "what's next". Replaces the old review-tasks command.
---

# Next Steps

Synthesize the current state of the project and suggest next actions.
Use `$ARGUMENTS` as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. `specs/hypotheses/` — status of each hypothesis
4. `doc/questions/` — open, high-priority questions
5. `doc/10-research-gaps.md`

Also run: `git log --oneline -15 --format="%h %s (%cr)"`

## Output

### 1. Recent Progress

Summarize what's been accomplished recently by combining:
- Recently completed tasks from `tasks/done/`
- Recent git commits

Group by theme (research, development, documentation) rather than listing chronologically.
Keep to 5-8 bullet points maximum.

### 2. Current State

From `tasks/active.md`, show:
- **P0 tasks** (critical path) — full detail
- **P1 tasks** (active work) — title and status
- **Blocked tasks** — what's blocking them
- **Hypothesis status** — one-line summary per hypothesis from `specs/hypotheses/`

### 3. Suggested Next Steps

Recommend 3-5 actions based on:
- Unblocked tasks that were previously blocked
- Highest-priority active tasks without recent commits
- Stale tasks (active but no related activity in >7 days)
- Open high-priority questions that could become tasks
- Research gaps that haven't been addressed

For each suggestion, include:
- The task ID (if it exists) or "new task" if suggesting something not yet tracked
- A brief rationale (1 sentence)
- The suggested command to run (e.g. `/science:research-topic`, `/science:tasks add ...`)

## Format

Use rich terminal formatting:
- Section headers as `##`
- Tables for task lists
- Bullet lists for progress and suggestions
- Bold for emphasis on critical items

Do not modify any files. This is a read-only analysis command.
```

**Step 2: Commit**

```bash
git add commands/next-steps.md
git commit -m "feat: add /science:next-steps command"
```

---

### Task 6: Update existing commands to use `tasks/`

**Files:**
- Modify: `commands/status.md` (section 8)
- Modify: `commands/research-gaps.md` (after-writing section)
- Modify: `commands/interpret-results.md` (update-priorities section)
- Modify: `references/project-structure.md` (add tasks/ directory)
- Modify: `references/claude-md-template.md` (update RESEARCH_PLAN.md references)

**Step 1: Update `commands/status.md` section 8**

Replace section 8 ("Next Steps", lines 94-100) with:

```markdown
### 8. Next Steps

From `tasks/active.md`:

- Show P0 and P1 tasks (top 5 items)
- Note any blocked tasks
- If no tasks file exists, note this and suggest `/science:tasks add`
```

**Step 2: Update `commands/research-gaps.md` after-writing section**

Replace lines 52-56 with:

```markdown
## After Writing

1. Offer to create tasks from recommended items: "Create tasks from these gaps?"
   - If accepted, run `science-tool tasks add` for each recommended task with appropriate priority, type, and related entities
2. Cross-link relevant items in `doc/questions/`.
3. Commit: `git add -A && git commit -m "plan: research gap analysis and priorities"`
```

**Step 3: Update `commands/interpret-results.md` section 5 and after-writing**

Replace lines 78-81 with:

```markdown
### 5. Update priorities

Given the findings, propose changes to the task queue:
- Tasks to add via `science-tool tasks add`
- Existing tasks to reprioritize or complete
- Hypotheses to pursue further or set aside
- Next commands to run
```

Replace line 92 with:

```markdown
3. Update task queue: add new tasks, complete or reprioritize existing ones via `science-tool tasks`.
```

**Step 4: Update `references/project-structure.md`**

Add after the `RESEARCH_PLAN.md` row in the top-level files table:

```markdown
| `RESEARCH_PLAN.md` | High-level research strategy (direction, phases, long-term goals) | Agent during planning |
```

Add a new directory section:

```markdown
### `tasks/` — Task Queue

Lightweight task management.

- `active.md` — current task queue (structured entries with ID, type, priority, status, links)
- `done/YYYY-MM.md` — completed tasks archived monthly
```

**Step 5: Update `references/claude-md-template.md`**

Update the reference to `RESEARCH_PLAN.md` to clarify it's a strategic document, and add `tasks/active.md` as the operational task queue.

**Step 6: Commit**

```bash
git add commands/status.md commands/research-gaps.md commands/interpret-results.md references/project-structure.md references/claude-md-template.md
git commit -m "refactor: update commands to use tasks/ instead of RESEARCH_PLAN.md as task queue"
```

---

### Task 7: Add validation check for tasks

**Files:**
- Modify: `scripts/validate.sh`

**Step 1: Read current validate.sh to find the right insertion point**

Find the last check number and add a new check after it.

**Step 2: Add the check**

Add a new check that validates:
- `tasks/active.md` exists (warn if not, don't fail — new projects may not have tasks yet)
- Each entry has required fields (type, priority, status, created)
- Task IDs are unique
- Task IDs follow `t\d{3}` format

**Step 3: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: add tasks/active.md validation check"
```

---

### Task 8: Update project template for new projects

**Files:**
- Modify: `commands/create-project.md` — ensure new projects get a `tasks/` directory with empty `active.md`

**Step 1: Read `commands/create-project.md` to understand the current project scaffolding**

**Step 2: Add `tasks/active.md` creation to the scaffolding steps**

The initial `active.md` can be empty or contain a comment:

```markdown
<!-- Task queue. Use /science:tasks to manage. -->
```

**Step 3: Commit**

```bash
git add commands/create-project.md
git commit -m "feat: scaffold tasks/ directory in new projects"
```

---

### Task 9: Run full test suite and lint

**Step 1: Run all tests**

```bash
cd science-tool && uv run --frozen pytest -v
```

**Step 2: Run linting**

```bash
cd science-tool && uv run --frozen ruff check .
cd science-tool && uv run --frozen ruff format --check .
cd science-tool && uv run --frozen pyright
```

**Step 3: Fix any issues and commit**

```bash
git add -A && git commit -m "fix: resolve lint and type check issues"
```

---

Plan complete and saved to `docs/plans/2026-03-08-task-management-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open a new session with executing-plans, batch execution with checkpoints

Which approach?
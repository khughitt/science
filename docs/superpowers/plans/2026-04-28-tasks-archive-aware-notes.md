# Tasks Archive-Aware Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science-tool tasks` locate active and archived tasks, safely edit archived tasks, and append dated task notes through the CLI.

**Architecture:** Keep the existing markdown task store. Add location-aware helpers to `science_tool.tasks` that search `tasks/active.md` first and `tasks/done/*.md` newest-first, then rewrite the owning file through the existing parser/renderer. Add `tasks note` as a thin Click command over the library note appender.

**Tech Stack:** Python 3.11+, Click, pathlib, dataclasses, pytest, Ruff, Pyright.

---

## File Structure

Modify:

- `science-tool/src/science_tool/tasks.py` — owns task parsing/rendering and task mutations; add `TaskLocation`, archive-aware lookup/write, archived-status guard, and note append helpers.
- `science-tool/src/science_tool/cli.py` — wire `tasks show`, `tasks edit`, and new `tasks note` command to archive-aware helpers.
- `science-tool/tests/test_tasks.py` — unit tests for lookup order, duplicate warnings, archived edit guard, note grammar, and round-trip stability.
- `science-tool/tests/test_tasks_cli.py` — CLI tests for archived show/edit, note output/date handling, and rejected inputs.

Create: no new source or test files.

Remove: no files.

---

### Task 1: Location-Aware Lookup

**Files:**
- Modify: `science-tool/tests/test_tasks.py`
- Modify: `science-tool/src/science_tool/tasks.py`

- [ ] **Step 1: Write failing lookup tests**

Append these tests after `TestEditTask` in `science-tool/tests/test_tasks.py`:

```python
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

    def test_find_task_location_active_wins_duplicate(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
```

Also add `find_task_location` to the import list from `science_tool.tasks`.

- [ ] **Step 2: Run lookup tests and verify they fail**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation -q
```

Expected: FAIL because `find_task_location` is not imported or not defined.

- [ ] **Step 3: Implement location helpers**

In `science-tool/src/science_tool/tasks.py`, add `dataclass` import:

```python
from dataclasses import dataclass
```

Add these definitions after `_write_active`:

```python
@dataclass(frozen=True)
class TaskLocation:
    """A task plus the markdown file that currently owns it."""

    path: Path
    task: Task
    tasks: list[Task]


def _task_search_paths(tasks_dir: Path) -> list[Path]:
    paths = [tasks_dir / "active.md"]
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        paths.extend(sorted(done_dir.glob("*.md"), reverse=True))
    return paths


def _find_matches(tasks_dir: Path, task_id: str) -> list[TaskLocation]:
    matches: list[TaskLocation] = []
    for path in _task_search_paths(tasks_dir):
        tasks = parse_tasks(path)
        for task in tasks:
            if task.id == task_id:
                matches.append(TaskLocation(path=path, task=task, tasks=tasks))
                break
    return matches


def find_task_location(tasks_dir: Path, task_id: str) -> TaskLocation:
    """Find a task in active.md or done/*.md, preferring active then newest archives."""
    matches = _find_matches(tasks_dir, task_id)
    if not matches:
        searched = ", ".join(str(path) for path in _task_search_paths(tasks_dir))
        msg = f"Task {task_id} not found in tasks/active.md or tasks/done/*.md (searched: {searched})"
        raise KeyError(msg)
    if len(matches) > 1:
        locations = ", ".join(str(match.path) for match in matches)
        print(f"WARNING: duplicate task id {task_id} found in {locations}; using {matches[0].path}", file=sys.stderr)
    return matches[0]


def write_task_location(location: TaskLocation) -> None:
    """Rewrite the markdown file that owns a task location."""
    location.path.parent.mkdir(parents=True, exist_ok=True)
    location.path.write_text(render_tasks(location.tasks) if location.tasks else "")
```

Update `__all__` to include `TaskLocation`, `find_task_location`, and `write_task_location`.

- [ ] **Step 4: Run lookup tests and verify they pass**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation -q
```

Expected: PASS.

- [ ] **Step 5: Commit lookup helpers**

Run:

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(tasks): locate tasks across active and archives"
```

---

### Task 2: Archive-Aware Edit And Show

**Files:**
- Modify: `science-tool/tests/test_tasks.py`
- Modify: `science-tool/tests/test_tasks_cli.py`
- Modify: `science-tool/src/science_tool/tasks.py`
- Modify: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Write failing unit tests for archived edit**

Append to `TestTaskLocation` in `science-tool/tests/test_tasks.py`:

```python
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
```

- [ ] **Step 2: Write failing CLI tests for archived show/edit**

Add to `TestTasksShow` in `science-tool/tests/test_tasks_cli.py`:

```python
    def test_show_displays_archived_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            (tasks_dir / "done" / "2026-04.md").write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "show", "t141"])

            assert result.exit_code == 0, result.output
            assert "Archived task" in result.output
            assert "Archived details." in result.output

    def test_show_missing_task_mentions_archives(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            (tasks_dir / "done" / "2026-04.md").write_text("")

            result = runner.invoke(main, ["tasks", "show", "t999"])

            assert result.exit_code != 0
            assert "tasks/done/*.md" in result.output
            assert "2026-04.md" in result.output
```

Add to `TestTasksEdit`:

```python
    def test_edit_archived_description(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "edit", "t141", "--description", "Corrected details."])

            assert result.exit_code == 0, result.output
            assert "Corrected details." in archived_path.read_text()

    def test_edit_archived_rejects_non_closed_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "edit", "t141", "--status", "active"])

            assert result.exit_code != 0
            assert "Cannot set archived task t141 to non-closed status 'active'" in result.output
            assert "- status: done" in archived_path.read_text()
```

- [ ] **Step 3: Run edit/show tests and verify they fail**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation tests/test_tasks_cli.py::TestTasksShow tests/test_tasks_cli.py::TestTasksEdit -q
```

Expected: FAIL because `edit_task` and `tasks show` still use active-only lookup.

- [ ] **Step 4: Implement archive-aware edit**

In `science-tool/src/science_tool/tasks.py`, add:

```python
_CLOSED_STATUS_VALUES = {TaskStatus.DONE.value, TaskStatus.RETIRED.value}
```

near `_CLOSED_STATUSES`.

Change `edit_task` to find and rewrite the owning file:

```python
def edit_task(
    tasks_dir: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str | None = None,
) -> Task:
    """Update specified fields on a task."""
    location = find_task_location(tasks_dir, task_id)
    task = location.task

    if location.path != tasks_dir / "active.md" and status is not None and status not in _CLOSED_STATUS_VALUES:
        msg = f"Cannot set archived task {task_id} to non-closed status '{status}'"
        raise ValueError(msg)

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority
    if status is not None:
        task.status = status
    if aspects is not None:
        task.aspects = aspects
    if related is not None:
        task.related = related
    if blocked_by is not None:
        task.blocked_by = blocked_by
    if group is not None:
        task.group = group

    write_task_location(location)
    return task
```

Keep `_find_task` and active-only lifecycle commands unchanged.

- [ ] **Step 5: Implement archive-aware CLI show and ValueError handling**

In `science-tool/src/science_tool/cli.py`, update `tasks_edit` exception handling:

```python
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
```

Update `tasks_show`:

```python
@tasks.command("show")
@click.argument("task_id")
def tasks_show(task_id: str) -> None:
    """Show full details of a task."""
    from science_tool.tasks import find_task_location, render_task

    try:
        location = find_task_location(DEFAULT_TASKS_DIR, task_id)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(render_task(location.task))
```

- [ ] **Step 6: Run edit/show tests and verify they pass**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation tests/test_tasks_cli.py::TestTasksShow tests/test_tasks_cli.py::TestTasksEdit -q
```

Expected: PASS.

- [ ] **Step 7: Commit archive-aware show/edit**

Run:

```bash
git add science-tool/src/science_tool/tasks.py science-tool/src/science_tool/cli.py science-tool/tests/test_tasks.py science-tool/tests/test_tasks_cli.py
git commit -m "feat(tasks): show and edit archived tasks safely"
```

---

### Task 3: Dated Note Append

**Files:**
- Modify: `science-tool/tests/test_tasks.py`
- Modify: `science-tool/src/science_tool/tasks.py`

- [ ] **Step 1: Write failing note unit tests**

Append to `TestTaskLocation` in `science-tool/tests/test_tasks.py`:

```python
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
```

Also add `append_task_note` to the import list from `science_tool.tasks`.

- [ ] **Step 2: Run note unit tests and verify they fail**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation -q
```

Expected: FAIL because `append_task_note` is not imported or not defined.

- [ ] **Step 3: Implement note append helpers**

In `science-tool/src/science_tool/tasks.py`, add regexes near the existing regex constants:

```python
_NOTES_HEADING_RE = re.compile(r"^###\s+Notes\s*$")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,3})\s+.+$")
```

Add helper functions before `append_task_note`:

```python
def _format_note(note_date: date, note: str) -> str:
    cleaned = note.strip()
    if not cleaned:
        msg = "Task note cannot be empty"
        raise ValueError(msg)
    return f"- {note_date.isoformat()}: {cleaned}"


def _heading_level(line: str) -> int | None:
    match = _MARKDOWN_HEADING_RE.match(line)
    if match is None:
        return None
    return len(match.group(1))


def _append_note_to_description(description: str, note_line: str) -> str:
    description = description.strip()
    if not description:
        return f"### Notes\n\n{note_line}"

    lines = description.splitlines()
    notes_index = next((i for i, line in enumerate(lines) if _NOTES_HEADING_RE.match(line)), None)
    if notes_index is None:
        return f"{description}\n\n### Notes\n\n{note_line}"

    insert_index = len(lines)
    for i in range(notes_index + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= 3:
            insert_index = i
            break

    before = lines[:insert_index]
    while before and before[-1] == "":
        before.pop()
    after = lines[insert_index:]
    if after:
        return "\n".join([*before, note_line, "", *after]).strip()
    return "\n".join([*before, note_line]).strip()
```

Add public function:

```python
def append_task_note(tasks_dir: Path, task_id: str, note: str, note_date: date | None = None) -> Task:
    """Append a dated journal note to a task in active.md or done/*.md."""
    location = find_task_location(tasks_dir, task_id)
    task = location.task
    line = _format_note(note_date or date.today(), note)
    task.description = _append_note_to_description(task.description, line)
    write_task_location(location)
    return task
```

Update `__all__` to include `append_task_note`.

- [ ] **Step 4: Run note unit tests and verify they pass**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py::TestTaskLocation -q
```

Expected: PASS.

- [ ] **Step 5: Commit note library support**

Run:

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(tasks): append dated task notes"
```

---

### Task 4: Notes CLI

**Files:**
- Modify: `science-tool/tests/test_tasks_cli.py`
- Modify: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Write failing notes CLI tests**

Add this class after `TestTasksEdit` in `science-tool/tests/test_tasks_cli.py`:

```python
class TestTasksNote:
    def test_note_appends_to_active_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "Clarified scope.", "--date", "2026-04-28"])

            assert result.exit_code == 0, result.output
            assert "Added note to [t001] (2026-04-28)" in result.output
            body = Path("tasks/active.md").read_text()
            assert "### Notes" in body
            assert "- 2026-04-28: Clarified scope." in body

    def test_note_appends_to_archived_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "note", "t141", "Archived clarification.", "--date", "2026-04-28"])

            assert result.exit_code == 0, result.output
            assert "Added note to [t141] (2026-04-28)" in result.output
            assert "- 2026-04-28: Archived clarification." in archived_path.read_text()

    def test_note_rejects_blank_note(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "   ", "--date", "2026-04-28"])

            assert result.exit_code != 0
            assert "Task note cannot be empty" in result.output

    def test_note_rejects_invalid_date(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "Clarified.", "--date", "not-a-date"])

            assert result.exit_code != 0
            assert "Date must use YYYY-MM-DD" in result.output
```

- [ ] **Step 2: Run notes CLI tests and verify they fail**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks_cli.py::TestTasksNote -q
```

Expected: FAIL because `tasks note` does not exist.

- [ ] **Step 3: Implement `tasks note` CLI**

In `science-tool/src/science_tool/cli.py`, add after `tasks_edit`:

```python
@tasks.command("note")
@click.argument("task_id")
@click.argument("note")
@click.option("--date", "note_date_raw", default=None, help="Note date in YYYY-MM-DD format.")
def tasks_note(task_id: str, note: str, note_date_raw: str | None) -> None:
    """Append a dated note to a task."""
    from datetime import date

    from science_tool.tasks import append_task_note

    note_date = date.today()
    if note_date_raw is not None:
        try:
            note_date = date.fromisoformat(note_date_raw)
        except ValueError as exc:
            raise click.ClickException("Date must use YYYY-MM-DD") from exc

    try:
        task = append_task_note(DEFAULT_TASKS_DIR, task_id, note, note_date=note_date)
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Added note to [{task.id}] ({note_date.isoformat()})")
```

- [ ] **Step 4: Run notes CLI tests and verify they pass**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks_cli.py::TestTasksNote -q
```

Expected: PASS.

- [ ] **Step 5: Commit notes CLI**

Run:

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_tasks_cli.py
git commit -m "feat(tasks): add dated note command"
```

---

### Task 5: Final Verification

**Files:** Verify only, unless formatting changes files.

- [ ] **Step 1: Run focused task tests**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py tests/test_tasks_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full task archive-adjacent tests**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py tests/test_tasks_cli.py tests/test_tasks_archive.py tests/test_health.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting**

Run:

```bash
cd science-tool
uv run --frozen ruff format .
```

Expected: command completes successfully. If files change, inspect and commit them.

- [ ] **Step 4: Run lint**

Run:

```bash
cd science-tool
uv run --frozen ruff check .
```

Expected: PASS.

- [ ] **Step 5: Run type check**

Run:

```bash
cd science-tool
uv run --frozen pyright
```

Expected: PASS or only pre-existing unrelated errors. Any new errors from this work must be fixed.

- [ ] **Step 6: Manual CLI smoke test**

Run:

```bash
cd science-tool
tmpdir="$(mktemp -d)"
cd "$tmpdir"
science-tool tasks add "Smoke task" --priority P1
science-tool tasks done t001 --note "Initial completion."
science-tool tasks show t001
science-tool tasks note t001 "Post-completion clarification." --date 2026-04-28
science-tool tasks show t001
```

Expected:

- `show t001` succeeds after `done` moves the task to `tasks/done/YYYY-MM.md`.
- Final `show t001` includes `### Notes` and `- 2026-04-28: Post-completion clarification.`

- [ ] **Step 7: Commit any formatting fixes**

If `ruff format` changed files, run:

```bash
git add science-tool/src/science_tool/tasks.py science-tool/src/science_tool/cli.py science-tool/tests/test_tasks.py science-tool/tests/test_tasks_cli.py
git commit -m "chore(tasks): format archive-aware notes changes"
```

Skip if `git status --short` is clean.

---

## Self-Review

- Spec coverage: archive-aware `show`, safe archive-aware `edit`, `tasks note`, notes grammar, duplicate warnings, missing-task searched files, archive mutability, and round-trip stability are covered.
- Placeholder scan: no `TBD`, `TODO`, or vague edge-case placeholders are intentionally present.
- Type consistency: `TaskLocation`, `find_task_location`, `write_task_location`, and `append_task_note` are defined before use and return the shapes expected by CLI and tests.

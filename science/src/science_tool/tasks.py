"""Task markdown parser/renderer and CRUD operations for science.

The Task model is defined in science-model and re-exported here for convenience.
"""

from __future__ import annotations

import fcntl
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate

__all__ = [
    "Task",
    "TaskCreate",
    "TaskAspectValidationError",
    "TaskIntegrityError",
    "TaskLocation",
    "TaskStatus",
    "TaskUpdate",
    "append_task_note",
    "find_dangling_task_refs",
    "find_task_location",
    "parse_tasks_for_cli",
    "retire_task",
    "validate_task_aspects",
    "write_task_location",
]

_VALID_STATUSES = {s.value for s in TaskStatus}


class TaskIntegrityError(ValueError):
    """A task-file write would corrupt or lose data and was refused.

    Raised by the round-trip guard when the text about to be persisted does not
    re-parse to the tasks it was rendered from (e.g. a description line starting
    with ``## [`` is mistaken for a task header), so callers never silently
    write a self-corrupting file.
    """


_TASK_ID_PATTERN = r"t[0-9]{3,}"
_HEADER_RE = re.compile(rf"^##\s+\[({_TASK_ID_PATTERN})\]\s+(.+)$")
_ANY_TASK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+([\w-]+):\s*(.*)$")
_LIST_RE = re.compile(r"^\[(.+)\]$")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,3})\s+.+$")
_NOTES_HEADING_RE = re.compile(r"^###\s+Notes\s*$")
_LOCAL_PARENT_RE = re.compile(r"^task:t[0-9]{3,}$")
_TASK_HEADING_PREFIX_RE = re.compile(r"^##\s+\[", re.MULTILINE)


def _parse_list_value(raw: str) -> list[str]:
    """Parse a bracketed, comma-separated list value like '[t001, t002]'."""
    m = _LIST_RE.match(raw.strip())
    if not m:
        return []
    return [item.strip() for item in m.group(1).split(",") if item.strip()]


def _parse_task_header(line: str, *, path: Path | None = None) -> tuple[str, str]:
    """Parse and validate a task header line."""
    match = _HEADER_RE.match(line)
    if match:
        return match.group(1), match.group(2).strip()

    loose = _ANY_TASK_HEADER_RE.match(line)
    if loose:
        task_id = loose.group(1)
        where = f" in {path}" if path is not None else ""
        msg = (
            f"Invalid task id '{task_id}'{where}: task ids must match tNNN. "
            "Use parent: task:t001 for fragments or subtasks."
        )
        raise ValueError(msg)

    where = f" in {path}" if path is not None else ""
    raise ValueError(f"Invalid task header{where}: {line}")


class TaskAspectValidationError(ValueError):
    """Raised when task-scoped aspects are malformed."""


def validate_task_aspects(aspects: list[str]) -> list[str]:
    """Validate task-scoped aspect labels.

    Task aspects are local routing metadata: they use the shared aspect
    vocabulary, but do not require the aspect to be enabled globally in
    science.yaml.
    """
    from science_model.aspects import KNOWN_ASPECTS

    if not aspects:
        raise TaskAspectValidationError("Task aspects list is empty; omit --aspects instead.")
    seen: set[str] = set()
    validated: list[str] = []
    for aspect in aspects:
        if aspect in seen:
            raise TaskAspectValidationError(f"duplicate task aspect: {aspect!r}")
        seen.add(aspect)
        if aspect not in KNOWN_ASPECTS:
            raise TaskAspectValidationError(
                f"{aspect!r} is not in the aspect vocabulary ({sorted(KNOWN_ASPECTS)})."
            )
        validated.append(aspect)
    return validated


def _parse_parent(raw: str, *, task_id: str) -> str:
    parent = raw.strip()
    if not parent:
        return ""
    if _LOCAL_PARENT_RE.match(parent):
        return parent
    raise ValueError(f"parent for task {task_id} must be local task ref like task:t001")


def _required_field(fields: dict[str, str], field: str, *, task_id: str, path: Path | None) -> str:
    try:
        return fields[field]
    except KeyError as exc:
        where = f" in {path}" if path is not None else ""
        raise ValueError(f"task {task_id}{where} missing required field: {field}") from exc


def _parse_task_block(lines: list[str], *, path: Path | None = None) -> Task:
    """Parse a single task block (header line + metadata + description)."""
    task_id, title = _parse_task_header(lines[0], path=path)

    fields: dict[str, str] = {}
    desc_start = 1
    seen_field = False
    for i, line in enumerate(lines[1:], start=1):
        fm = _FIELD_RE.match(line)
        if fm:
            seen_field = True
            fields[fm.group(1)] = fm.group(2).strip()
            desc_start = i + 1
        elif line.strip() == "":
            if not seen_field:
                desc_start = i + 1
                continue
            desc_start = i + 1
            break
        else:
            break

    # Collect description lines (skip leading/trailing blank lines)
    desc_lines = lines[desc_start:]
    description = "\n".join(desc_lines).strip()

    created = date.fromisoformat(_required_field(fields, "created", task_id=task_id, path=path))
    completed_raw = fields.get("completed")
    completed = date.fromisoformat(completed_raw) if completed_raw else None

    return Task(
        id=task_id,
        title=title,
        type=fields.get("type", ""),
        aspects=_parse_list_value(fields.get("aspects", "")),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        created=created,
        description=description,
        related=_parse_list_value(fields.get("related", "")),
        parent=_parse_parent(fields.get("parent", ""), task_id=task_id),
        blocked_by=_parse_list_value(fields.get("blocked-by", "")),
        group=fields.get("group", ""),
        completed=completed,
    )


def _parse_tasks_text(text: str, *, path: Path | None = None) -> list[Task]:
    """Parse task blocks from markdown text (no file I/O)."""
    if not text.strip():
        return []

    lines = text.splitlines()
    # Split into blocks at task headers, including malformed task headers so
    # validation can fail with a task-ID-specific error.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _ANY_TASK_HEADER_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)

    return [_parse_task_block(block, path=path) for block in blocks]


def parse_tasks(path: Path) -> list[Task]:
    """Parse tasks from a markdown file. Returns empty list if file is missing or empty."""
    if not path.is_file():
        return []
    return _parse_tasks_text(path.read_text(), path=path)


def _verify_round_trip(text: str, expected: list[Task], *, path: Path) -> None:
    """Guard against silent task-file corruption / data loss.

    Re-parse the text we are about to persist and confirm it yields exactly the
    tasks it was rendered from (same ids, same descriptions). The common failure
    is a description line starting with ``## [`` (a task-header shape) which the
    parser would split into a phantom block on the next read.
    """
    try:
        reparsed = _parse_tasks_text(text, path=path)
    except ValueError as exc:
        raise TaskIntegrityError(
            f"refusing to write {path}: the rendered task file does not parse back "
            f"({exc}). A task description likely contains a line starting with "
            f"'## [' — indent or rephrase it so it is not read as a task header."
        ) from exc
    got = [t.id for t in reparsed]
    want = [t.id for t in expected]
    if got != want:
        raise TaskIntegrityError(
            f"refusing to write {path}: task set changed on round-trip "
            f"(expected {want}, got {got}); aborting to avoid data loss."
        )
    for original, parsed in zip(expected, reparsed):
        if original.description.strip() != parsed.description.strip():
            raise TaskIntegrityError(
                f"refusing to write {path}: description of task {original.id} does "
                f"not round-trip; a body line is being read as task structure. "
                f"Aborting to avoid data loss."
            )


def _task_ref_number(ref: str) -> str | None:
    """Extract a bare tNNN id from a task ref like 'task:t001' or 't001'."""
    candidate = ref.strip()
    if candidate.startswith("task:"):
        candidate = candidate[len("task:") :]
    return candidate if re.fullmatch(_TASK_ID_PATTERN, candidate) else None


def find_dangling_task_refs(tasks_dir: Path) -> dict[str, list[str]]:
    """Map task-id -> blocked_by/parent task refs that do not resolve to a known task.

    A post-write self-check: if a sibling task block was dropped, a surviving
    `blocked-by: [task:tNNN]` (or `parent:`) is reported here so the problem is
    caught at the task layer rather than only at `graph build`.
    """
    known = known_task_ids(tasks_dir)
    dangling: dict[str, list[str]] = {}
    for path in _task_search_paths(tasks_dir):
        for task in parse_tasks(path):
            bad: list[str] = []
            for ref in [*task.blocked_by, task.parent]:
                if not ref:
                    continue
                num = _task_ref_number(ref)
                if num is not None and num not in known:
                    bad.append(ref)
            if bad:
                dangling[task.id] = bad
    return dangling


def parse_tasks_for_cli(path: Path) -> tuple[list[Task], list[str]]:
    """Parse tasks AND surface user-facing warnings.

    Detects legacy untyped blocker refs and returns them as warning strings.
    Programmatic callers should prefer `parse_tasks` to avoid noise.
    """
    # Deferred import to avoid a circular dependency:
    # tasks_blockers -> entities -> graph -> tasks
    from science_tool.tasks_blockers import is_typed_ref  # noqa: PLC0415

    tasks = parse_tasks(path)
    warnings: list[str] = []
    for task in tasks:
        for ref in task.blocked_by:
            if not is_typed_ref(ref):
                warnings.append(
                    f"task {task.id}: legacy untyped blocker {ref!r} — run 'science tasks fix-blockers' to retype"
                )
    return tasks, warnings


def render_task(task: Task) -> str:
    """Render a single task to markdown."""
    lines = [f"## [{task.id}] {task.title}"]
    if task.type:
        lines.append(f"- type: {task.type}")
    lines.append(f"- priority: {task.priority}")
    lines.append(f"- status: {task.status}")
    if task.parent:
        lines.append(f"- parent: {task.parent}")
    # aspects is a validate-required field, so emit it even when empty
    # (a task added without --aspects must still be validate-clean).
    items = ", ".join(task.aspects)
    lines.append(f"- aspects: [{items}]")
    if task.related:
        items = ", ".join(task.related)
        lines.append(f"- related: [{items}]")
    if task.blocked_by:
        items = ", ".join(task.blocked_by)
        lines.append(f"- blocked-by: [{items}]")
    if task.group:
        lines.append(f"- group: {task.group}")
    lines.append(f"- created: {task.created.isoformat()}")
    if task.completed is not None:
        lines.append(f"- completed: {task.completed.isoformat()}")
    lines.append("")
    lines.append(task.description)
    return "\n".join(lines) + "\n"


def render_tasks(tasks: list[Task]) -> str:
    """Render a list of tasks to markdown."""
    return "\n".join(render_task(t) for t in tasks)


def _strict_task_ids_in_text(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match:
            ids.append(match.group(1))
    return ids


@contextmanager
def _task_allocation_lock(tasks_dir: Path) -> Iterator[None]:
    """Serialize ID allocation + active.md writes across concurrent processes.

    Without this, parallel `science tasks add` invocations each read the same max
    ID and the same active.md, producing duplicate IDs and lost writes. An
    exclusive advisory lock on a sentinel file makes the read-allocate-write
    sequence atomic; the lock auto-releases if a holder crashes.
    """
    tasks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = tasks_dir / ".tasks.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def next_task_id(tasks_dir: Path) -> str:
    """Determine the next task ID by scanning active.md and done/ directory."""
    max_num = 0

    active = tasks_dir / "active.md"
    if active.is_file():
        for task_id in _strict_task_ids_in_text(active.read_text()):
            max_num = max(max_num, int(task_id[1:]))

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        for f in done_dir.glob("*.md"):
            for task_id in _strict_task_ids_in_text(f.read_text()):
                max_num = max(max_num, int(task_id[1:]))

    return f"t{max_num + 1:03d}"


def _read_active(tasks_dir: Path) -> list[Task]:
    return parse_tasks(tasks_dir / "active.md")


def _task_file_preamble(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text()
    match = _TASK_HEADING_PREFIX_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


def _render_task_file(path: Path, tasks: list[Task]) -> str:
    preamble = _task_file_preamble(path)
    rendered = render_tasks(tasks) if tasks else ""
    return preamble + rendered


def _write_active(tasks_dir: Path, tasks: list[Task]) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    active = tasks_dir / "active.md"
    text = _render_task_file(active, tasks)
    _verify_round_trip(text, tasks, path=active)
    active.write_text(text)


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


def known_task_ids(tasks_dir: Path) -> set[str]:
    """Every valid task id (tNNN) declared as a header in active.md and done/*.md.

    A header-only scan (not full parse): a field-level problem in one task block
    must not crash callers that only need the set of declared ids. `_HEADER_RE`
    matches only valid tNNN headers and exposes the id as group 1; check_tasks
    owns reporting malformed task blocks.
    """
    ids: set[str] = set()
    for path in _task_search_paths(tasks_dir):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _HEADER_RE.match(line)
            if match:
                ids.add(match.group(1))
    return ids


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
    text = _render_task_file(location.path, location.tasks)
    _verify_round_trip(text, location.tasks, path=location.path)
    location.path.write_text(text)


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


def append_task_note(tasks_dir: Path, task_id: str, note: str, note_date: date | None = None) -> Task:
    """Append a dated journal note to a task in active.md or done/*.md."""
    location = find_task_location(tasks_dir, task_id)
    task = location.task
    line = _format_note(note_date or date.today(), note)
    task.description = _append_note_to_description(task.description, line)
    write_task_location(location)
    return task


def _find_task(tasks: list[Task], task_id: str) -> Task:
    for t in tasks:
        if t.id == task_id:
            return t
    msg = f"Task {task_id} not found in active.md"
    raise KeyError(msg)


def add_task(
    project_root: Path,
    tasks_dir: Path,
    title: str,
    priority: str,
    task_type: str = "",
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str = "",
    description: str = "",
    *,
    force: bool = False,
) -> Task:
    """Create a task with status 'proposed', auto-assign ID, write to active.md."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

    validated_blockers = validate_blocker_refs(project_root, blocked_by, force=force) if blocked_by else []
    with _task_allocation_lock(tasks_dir):
        task_id = next_task_id(tasks_dir)
        task = Task(
            id=task_id,
            title=title,
            type=task_type,
            aspects=aspects or [],
            priority=priority,
            status="proposed",
            created=date.today(),
            related=related or [],
            blocked_by=validated_blockers,
            group=group,
            description=description,
        )
        tasks = _read_active(tasks_dir)
        tasks.append(task)
        _write_active(tasks_dir, tasks)
    return task


def _move_task_to_done(tasks_dir: Path, remaining: list[Task], done_path: Path, task: Task) -> None:
    """Atomically move a task from active.md to a done archive.

    Both the new active.md and the new done file are rendered AND round-trip
    verified before either is written, so a corrupting payload (or a parser
    fragility) aborts the whole move instead of half-applying it and losing data.
    """
    tasks_dir.mkdir(parents=True, exist_ok=True)
    done_path.parent.mkdir(parents=True, exist_ok=True)

    active = tasks_dir / "active.md"
    active_text = _render_task_file(active, remaining)
    _verify_round_trip(active_text, remaining, path=active)

    existing_done = parse_tasks(done_path)
    existing_done.append(task)
    done_text = render_tasks(existing_done)
    _verify_round_trip(done_text, existing_done, path=done_path)

    # Both renders verified — now commit both writes.
    active.write_text(active_text)
    done_path.write_text(done_text)


def complete_task(tasks_dir: Path, task_id: str, note: str | None = None) -> Task:
    """Mark task done, add completion date, move from active.md to done/YYYY-MM.md."""
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "done"
    task.completed = date.today()
    if note:
        task.description = f"{task.description}\n\n{note}".strip()

    remaining = [t for t in tasks if t.id != task_id]
    done_dir = tasks_dir / "done"
    done_path = done_dir / f"{date.today().strftime('%Y-%m')}.md"
    _move_task_to_done(tasks_dir, remaining, done_path, task)
    return task


def defer_task(tasks_dir: Path, task_id: str, reason: str | None = None) -> Task:
    """Set status to 'deferred', append reason to description."""
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "deferred"
    if reason:
        task.description = f"{task.description}\n\n{reason}".strip()

    _write_active(tasks_dir, tasks)
    return task


def retire_task(tasks_dir: Path, task_id: str, reason: str | None = None) -> Task:
    """Set status to 'retired', append reason. Moves to done/ archive like complete_task."""
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "retired"
    task.completed = date.today()
    if reason:
        task.description = f"{task.description}\n\n**Retired:** {reason}".strip()

    remaining = [t for t in tasks if t.id != task_id]
    done_dir = tasks_dir / "done"
    done_path = done_dir / f"{date.today().strftime('%Y-%m')}.md"
    _move_task_to_done(tasks_dir, remaining, done_path, task)
    return task


def block_task(
    project_root: Path,
    tasks_dir: Path,
    task_id: str,
    blocked_by: list[str],
    *,
    force: bool = False,
) -> Task:
    """Add typed blockers to a task, set status to 'blocked'."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

    validated = validate_blocker_refs(project_root, blocked_by, force=force)
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "blocked"
    for ref in validated:
        if ref not in task.blocked_by:
            task.blocked_by.append(ref)

    _write_active(tasks_dir, tasks)
    return task


def unblock_task(tasks_dir: Path, task_id: str) -> Task:
    """Clear blocked_by list, set status to 'active'."""
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "active"
    task.blocked_by = []

    _write_active(tasks_dir, tasks)
    return task


def edit_task(
    project_root: Path,
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
    *,
    force: bool = False,
) -> Task:
    """Update specified fields on a task."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

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
        for ref in related:
            if ref not in task.related:
                task.related.append(ref)
    if blocked_by is not None:
        task.blocked_by = validate_blocker_refs(project_root, blocked_by, force=force)
    if group is not None:
        task.group = group

    write_task_location(location)
    return task


def warn_invalid_statuses(tasks: list[Task]) -> None:
    """Print warnings to stderr for tasks with non-canonical statuses."""
    for t in tasks:
        if t.status not in _VALID_STATUSES:
            print(
                f"WARNING: [{t.id}] has invalid status '{t.status}' "
                f"(expected one of: {', '.join(sorted(_VALID_STATUSES))})",
                file=sys.stderr,
            )


# Statuses that represent closed tasks (excluded from default listing)
_CLOSED_STATUSES = {TaskStatus.DONE, TaskStatus.RETIRED}
_CLOSED_STATUS_VALUES = {TaskStatus.DONE.value, TaskStatus.RETIRED.value}


def list_tasks(
    tasks_dir: Path,
    project_root: Path | None = None,
    priority: str | None = None,
    status: str | None = None,
    related: str | None = None,
    group: str | None = None,
    aspects: list[str] | None = None,
    include_done: bool = False,
) -> list[Task]:
    """Filter active tasks by optional criteria.

    By default, done and retired tasks are excluded. Pass ``include_done=True``
    or filter by a specific ``status`` to include them.
    """
    tasks = _read_active(tasks_dir)

    warn_invalid_statuses(tasks)

    if priority is not None:
        tasks = [t for t in tasks if t.priority == priority]
    if status is not None:
        tasks = [t for t in tasks if t.status == status]
    elif not include_done:
        tasks = [t for t in tasks if t.status not in _CLOSED_STATUSES]
    if related is not None:
        tasks = [t for t in tasks if any(related in r for r in t.related)]
    if group is not None:
        tasks = [t for t in tasks if t.group == group]
    if aspects:
        from science_model.aspects import (
            load_project_aspects,
            matches_aspect_filter,
            resolve_entity_aspects,
        )

        project_aspects = load_project_aspects(project_root or tasks_dir.parent)
        filter_set = set(aspects)
        tasks = [
            t
            for t in tasks
            if matches_aspect_filter(
                resolve_entity_aspects(t.aspects or None, project_aspects),
                filter_set,
            )
        ]

    return tasks

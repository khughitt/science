"""Task model and markdown parser/renderer for science-tool."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Task:
    """A single actionable task in the research project."""

    id: str
    title: str
    type: str
    priority: str
    status: str
    created: date
    related: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    completed: date | None = None
    description: str = ""


_HEADER_RE = re.compile(r"^##\s+\[(\w+)\]\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+([\w-]+):\s+(.+)$")
_LIST_RE = re.compile(r"^\[(.+)\]$")


def _parse_list_value(raw: str) -> list[str]:
    """Parse a bracketed, comma-separated list value like '[t001, t002]'."""
    m = _LIST_RE.match(raw.strip())
    if not m:
        return []
    return [item.strip() for item in m.group(1).split(",") if item.strip()]


def _parse_task_block(lines: list[str]) -> Task:
    """Parse a single task block (header line + metadata + description)."""
    header_match = _HEADER_RE.match(lines[0])
    if not header_match:
        msg = f"Invalid task header: {lines[0]}"
        raise ValueError(msg)

    task_id = header_match.group(1)
    title = header_match.group(2).strip()

    fields: dict[str, str] = {}
    desc_start = 1
    for i, line in enumerate(lines[1:], start=1):
        fm = _FIELD_RE.match(line)
        if fm:
            fields[fm.group(1)] = fm.group(2).strip()
            desc_start = i + 1
        elif line.strip() == "":
            desc_start = i + 1
            break
        else:
            break

    # Collect description lines (skip leading/trailing blank lines)
    desc_lines = lines[desc_start:]
    description = "\n".join(desc_lines).strip()

    created = date.fromisoformat(fields["created"])
    completed_raw = fields.get("completed")
    completed = date.fromisoformat(completed_raw) if completed_raw else None

    return Task(
        id=task_id,
        title=title,
        type=fields.get("type", ""),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        created=created,
        description=description,
        related=_parse_list_value(fields.get("related", "")),
        blocked_by=_parse_list_value(fields.get("blocked-by", "")),
        completed=completed,
    )


def parse_tasks(path: Path) -> list[Task]:
    """Parse tasks from a markdown file. Returns empty list if file is missing or empty."""
    if not path.is_file():
        return []

    text = path.read_text()
    if not text.strip():
        return []

    lines = text.splitlines()
    # Split into blocks at ## headers
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _HEADER_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)

    return [_parse_task_block(block) for block in blocks]


def render_task(task: Task) -> str:
    """Render a single task to markdown."""
    lines = [f"## [{task.id}] {task.title}"]
    lines.append(f"- type: {task.type}")
    lines.append(f"- priority: {task.priority}")
    lines.append(f"- status: {task.status}")
    if task.related:
        items = ", ".join(task.related)
        lines.append(f"- related: [{items}]")
    if task.blocked_by:
        items = ", ".join(task.blocked_by)
        lines.append(f"- blocked-by: [{items}]")
    lines.append(f"- created: {task.created.isoformat()}")
    if task.completed is not None:
        lines.append(f"- completed: {task.completed.isoformat()}")
    lines.append("")
    lines.append(task.description)
    return "\n".join(lines) + "\n"


def render_tasks(tasks: list[Task]) -> str:
    """Render a list of tasks to markdown."""
    return "\n".join(render_task(t) for t in tasks)


_TASK_ID_RE = re.compile(r"\[t(\d+)\]")


def next_task_id(tasks_dir: Path) -> str:
    """Determine the next task ID by scanning active.md and done/ directory."""
    max_num = 0

    # Scan active.md
    active = tasks_dir / "active.md"
    if active.is_file():
        for m in _TASK_ID_RE.finditer(active.read_text()):
            max_num = max(max_num, int(m.group(1)))

    # Scan done/ directory
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        for f in done_dir.glob("*.md"):
            for m in _TASK_ID_RE.finditer(f.read_text()):
                max_num = max(max_num, int(m.group(1)))

    return f"t{max_num + 1:03d}"

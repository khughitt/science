"""Colored table rendering for task lists."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from science_model.tasks import Task

from science_tool.styles import (
    TASK_PRIORITY_STYLES,
    TASK_STATUS_STYLES,
    TASK_TYPE_STYLES,
    age_style,
    get_console,
    render_entity_ref,
)
from science_tool.tasks_readiness import ReadinessResolver

# ── Status: sort order and colors ────────────────────────────────────────

_STATUS_ORDER: dict[str, int] = {
    "active": 0,
    "blocked": 1,
    "proposed": 2,
    "deferred": 3,
    "done": 4,
    "retired": 5,
}

# ── Sorting ──────────────────────────────────────────────────────────────


def sort_tasks(tasks: list[Task]) -> list[Task]:
    """Sort tasks by (status rank, id)."""
    return sorted(tasks, key=lambda t: (_STATUS_ORDER.get(t.status, 99), t.id))


# ── Blocker summary ──────────────────────────────────────────────────────


def render_blocker_summary(task: Task, resolver: ReadinessResolver) -> str | None:
    """Render the second-line blocker summary, or None when not blocked."""
    if task.status != "blocked" or not task.blocked_by:
        return None
    readinesses = [resolver.resolve_ref(ref) for ref in task.blocked_by]
    count = len(readinesses)
    if all(r.ready for r in readinesses):
        return f"        [{task.id}] blocked-by: {count} (all ready — run 'tasks unblock {task.id}')"
    # Group not-ready readinesses by state for the breakdown.
    by_state: dict[str, int] = {}
    for r in readinesses:
        if not r.ready:
            by_state[r.state] = by_state.get(r.state, 0) + 1
    breakdown = ", ".join(f"{count_n} {state}" for state, count_n in by_state.items())
    return f"        [{task.id}] blocked-by: {count} ({breakdown})"


# ── Table rendering ──────────────────────────────────────────────────────


def _render_related_refs(refs: list[str]) -> Text:
    text = Text()
    for index, ref in enumerate(refs):
        if index:
            text.append(", ", style="dim")
        text.append_text(render_entity_ref(ref))
    return text


def render_tasks_table(tasks: list[Task], resolver: ReadinessResolver | None = None) -> None:
    """Render a colored Rich table of tasks to stdout."""
    has_groups = any(t.group for t in tasks)
    has_related = any(t.related for t in tasks)

    table = Table(title="Tasks", show_lines=False)
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Pri")
    table.add_column("Status")
    if has_groups:
        table.add_column("Group")
    if has_related:
        table.add_column("Related")
    table.add_column("Created")

    for t in tasks:
        id_text = Text(t.id, style="bold")
        title_text = Text(t.title)
        type_text = Text(t.type, style=TASK_TYPE_STYLES.get(t.type, ""))
        pri_text = Text(t.priority, style=TASK_PRIORITY_STYLES.get(t.priority, ""))
        status_text = Text(t.status, style=TASK_STATUS_STYLES.get(t.status, ""))
        created_text = Text(t.created.isoformat(), style=age_style(t.created))

        row: list[Text] = [id_text, title_text, type_text, pri_text, status_text]
        if has_groups:
            row.append(Text(t.group, style="cyan"))
        if has_related:
            row.append(_render_related_refs(t.related))
        row.append(created_text)

        table.add_row(*row)

    console = get_console()
    console.print(table)

    if resolver is not None:
        for t in tasks:
            summary = render_blocker_summary(t, resolver)
            if summary is not None:
                console.print(summary)

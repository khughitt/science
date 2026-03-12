"""Colored table rendering for task lists."""

from __future__ import annotations

from datetime import date

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from science_model.tasks import Task

# ── Status: sort order and colors ────────────────────────────────────────

_STATUS_ORDER: dict[str, int] = {
    "active": 0,
    "blocked": 1,
    "proposed": 2,
    "deferred": 3,
    "done": 4,
}

_STATUS_STYLE: dict[str, str] = {
    "active": "bold green",
    "blocked": "bold red",
    "proposed": "yellow",
    "deferred": "dim",
    "done": "blue",
}

# ── Type colors ──────────────────────────────────────────────────────────

_TYPE_STYLE: dict[str, str] = {
    "dev": "cyan",
    "research": "magenta",
    "analysis": "blue",
    "writing": "green",
}

# ── Priority colors ─────────────────────────────────────────────────────

_PRIORITY_STYLE: dict[str, str] = {
    "P0": "bold red",
    "P1": "red",
    "P2": "yellow",
    "P3": "dim",
}

# ── Created: continuous age gradient ─────────────────────────────────────


def _age_style(created: date) -> Style:
    """Map task age to a green→yellow→red gradient."""
    days = (date.today() - created).days
    # Clamp to 0–90 day range for the gradient
    t = min(max(days, 0), 90) / 90.0
    # Green (0,180,60) → Yellow (200,180,0) → Red (200,60,0)
    if t < 0.5:
        s = t * 2  # 0→1 over first half
        r = int(60 + 140 * s)
        g = int(180)
        b = int(60 - 60 * s)
    else:
        s = (t - 0.5) * 2  # 0→1 over second half
        r = int(200)
        g = int(180 - 120 * s)
        b = int(0)
    return Style(color=f"#{r:02x}{g:02x}{b:02x}")


# ── Sorting ──────────────────────────────────────────────────────────────


def sort_tasks(tasks: list[Task]) -> list[Task]:
    """Sort tasks by (status rank, id)."""
    return sorted(tasks, key=lambda t: (_STATUS_ORDER.get(t.status, 99), t.id))


# ── Table rendering ──────────────────────────────────────────────────────


def render_tasks_table(tasks: list[Task]) -> None:
    """Render a colored Rich table of tasks to stdout."""
    table = Table(title="Tasks", show_lines=False)
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Pri")
    table.add_column("Status")
    table.add_column("Created")

    for t in tasks:
        id_text = Text(t.id, style="bold")
        title_text = Text(t.title)
        type_text = Text(t.type, style=_TYPE_STYLE.get(t.type, ""))
        pri_text = Text(t.priority, style=_PRIORITY_STYLE.get(t.priority, ""))
        status_text = Text(t.status, style=_STATUS_STYLE.get(t.status, ""))
        created_text = Text(t.created.isoformat(), style=_age_style(t.created))

        table.add_row(id_text, title_text, type_text, pri_text, status_text, created_text)

    console = Console()
    console.print(table)

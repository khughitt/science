"""Archiver for done/retired entries in `tasks/active.md`.

Reuses the parser/renderer in `science_tool.tasks` and routes terminal-state
entries to `tasks/done/YYYY-MM.md` based on each entry's `completed:` date
(falling back to the current month with a warning when missing).

The archiver is purely additive: it does not modify the existing
`science_tool.tasks` writers, and treats `active.md` preamble (any text above
the first `## [tNNN]` heading) as a byte-for-byte round-trip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_tool.tasks import (
    Task,
    _HEADER_RE,
    _parse_task_block,
    parse_tasks,
    render_tasks,
)

__all__ = [
    "ArchiveEntry",
    "ArchivePlan",
    "ArchiveResult",
    "ParseError",
    "apply_archive",
    "count_archivable",
    "plan_archive",
]


# Statuses moved by the archiver. `deferred` is intentionally NOT included —
# deferred entries stay visible in `active.md` for re-engagement.
_TERMINAL_STATUSES: frozenset[str] = frozenset({"done", "retired"})


@dataclass(frozen=True)
class ArchiveEntry:
    """One task selected for archiving, with its computed destination."""

    task: Task
    destination: Path
    missing_completed: bool


@dataclass(frozen=True)
class ParseError:
    """A task block in `active.md` that could not be parsed."""

    heading: str
    message: str


@dataclass(frozen=True)
class ArchivePlan:
    """The result of scanning `active.md` and classifying its entries."""

    tasks_dir: Path
    preamble: str
    entries: list[ArchiveEntry]
    parse_errors: list[ParseError]
    remaining: list[Task]


@dataclass(frozen=True)
class ArchiveResult:
    """The outcome of applying an :class:`ArchivePlan`."""

    moved: list[Task]
    skipped_duplicates: list[str]
    destinations_written: list[Path]


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


_HEADING_PREFIX_RE = re.compile(r"^##\s+\[", re.MULTILINE)


def _split_preamble_and_blocks(text: str) -> tuple[str, list[list[str]]]:
    """Split `active.md` text into (preamble, [task-block-lines, ...]).

    Preamble is everything before the first `## [` heading, preserved
    byte-for-byte. Task blocks are split at each `## [` heading.
    """
    if not text:
        return "", []

    match = _HEADING_PREFIX_RE.search(text)
    if match is None:
        # No headings — entire file is preamble.
        return text, []

    preamble = text[: match.start()]
    body = text[match.start() :]

    lines = body.splitlines()
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

    return preamble, blocks


def _destination_for(task: Task, today: date) -> tuple[Path, bool]:
    """Return (relative-to-tasks_dir destination filename, missing_completed)."""
    completed = task.completed
    missing = completed is None
    routing_date = completed or today
    return Path("done") / f"{routing_date.strftime('%Y-%m')}.md", missing


def plan_archive(tasks_dir: Path, *, today: date | None = None) -> ArchivePlan:
    """Scan `tasks_dir/active.md` and build an archive plan.

    Returns an ``ArchivePlan`` with:

    - ``preamble``: text above the first task heading (byte-identical).
    - ``entries``: terminal-state tasks (status in {"done", "retired"}) with
      their destination path computed from each entry's ``completed:`` date.
      When ``completed:`` is missing, ``missing_completed`` is set and the
      destination falls back to ``today`` (default: ``date.today()``).
    - ``parse_errors``: task blocks that failed to parse — collected, not
      raised. ``apply_archive`` will refuse to write if this list is non-empty.
    - ``remaining``: every parseable, non-terminal task, in original order.

    The function is pure: it never writes to disk and is safe to call from
    health checks and dry-run previews.
    """
    today = today or date.today()
    active = tasks_dir / "active.md"
    if not active.is_file():
        return ArchivePlan(
            tasks_dir=tasks_dir,
            preamble="",
            entries=[],
            parse_errors=[],
            remaining=[],
        )

    text = active.read_text()
    preamble, blocks = _split_preamble_and_blocks(text)

    entries: list[ArchiveEntry] = []
    parse_errors: list[ParseError] = []
    remaining: list[Task] = []

    for block in blocks:
        heading = block[0] if block else ""
        try:
            task = _parse_task_block(block)
        except (ValueError, KeyError) as exc:
            parse_errors.append(ParseError(heading=heading, message=str(exc)))
            continue

        if task.status in _TERMINAL_STATUSES:
            relative_dest, missing = _destination_for(task, today)
            entries.append(
                ArchiveEntry(
                    task=task,
                    destination=tasks_dir / relative_dest,
                    missing_completed=missing,
                )
            )
        else:
            remaining.append(task)

    return ArchivePlan(
        tasks_dir=tasks_dir,
        preamble=preamble,
        entries=entries,
        parse_errors=parse_errors,
        remaining=remaining,
    )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _read_destination(path: Path) -> tuple[str, list[Task]]:
    """Read a destination file, returning (preamble, parsed-tasks).

    Returns ("", []) when the file is missing. Reuses the planner's preamble
    splitter so destination files preserve any header text byte-for-byte.
    """
    if not path.is_file():
        return "", []
    text = path.read_text()
    if not text.strip():
        return text, []
    preamble, blocks = _split_preamble_and_blocks(text)
    tasks = [_parse_task_block(block) for block in blocks]
    return preamble, tasks


def apply_archive(plan: ArchivePlan) -> ArchiveResult:
    """Apply an :class:`ArchivePlan`: move terminal entries into `done/YYYY-MM.md`.

    - Refuses to write if ``plan.parse_errors`` is non-empty (raises ``RuntimeError``).
    - No-op (zero writes) when ``plan.entries`` is empty.
    - Groups entries by destination, reads the existing destination preamble +
      tasks, appends only entries whose ids are not already present, then writes.
    - Rewrites ``active.md`` as ``plan.preamble + render_tasks(plan.remaining)``
      (empty string when both are empty, matching ``_write_active``).
    - Idempotent: re-running on the same state produces zero writes.
    """
    if plan.parse_errors:
        msg = (
            f"Refusing to apply: {len(plan.parse_errors)} parse error(s) in active.md "
            f"(first: {plan.parse_errors[0].heading!r})"
        )
        raise RuntimeError(msg)

    if not plan.entries:
        return ArchiveResult(moved=[], skipped_duplicates=[], destinations_written=[])

    # Group entries by destination, preserving plan order within each group.
    by_destination: dict[Path, list[ArchiveEntry]] = {}
    for entry in plan.entries:
        by_destination.setdefault(entry.destination, []).append(entry)

    moved: list[Task] = []
    skipped: list[str] = []
    destinations_written: list[Path] = []

    for destination, entries in by_destination.items():
        dest_preamble, existing_tasks = _read_destination(destination)
        existing_ids = {t.id for t in existing_tasks}
        appended: list[Task] = []
        for entry in entries:
            if entry.task.id in existing_ids:
                skipped.append(entry.task.id)
                continue
            appended.append(entry.task)
            moved.append(entry.task)
            existing_ids.add(entry.task.id)

        if not appended:
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        new_tasks = existing_tasks + appended
        destination.write_text(dest_preamble + render_tasks(new_tasks))
        destinations_written.append(destination)

    # Rewrite active.md regardless: every entry was either moved or recorded
    # as a duplicate, and in both cases it must be removed from active.
    active_path = plan.tasks_dir / "active.md"
    plan.tasks_dir.mkdir(parents=True, exist_ok=True)
    rendered_remaining = render_tasks(plan.remaining) if plan.remaining else ""
    if plan.preamble or rendered_remaining:
        active_path.write_text(plan.preamble + rendered_remaining)
    else:
        active_path.write_text("")

    return ArchiveResult(
        moved=moved,
        skipped_duplicates=skipped,
        destinations_written=destinations_written,
    )


# ---------------------------------------------------------------------------
# Counters (used by `science-tool health` without importing the writer path)
# ---------------------------------------------------------------------------


def count_archivable(tasks_dir: Path) -> dict[str, int]:
    """Return archive-lag counts for ``tasks_dir`` without writing anything.

    Used by ``science-tool health`` to surface drift without taking any
    side-effects on disk.
    """
    plan = plan_archive(tasks_dir)
    return {
        "done_in_active": sum(1 for e in plan.entries if e.task.status == "done"),
        "retired_in_active": sum(1 for e in plan.entries if e.task.status == "retired"),
        "missing_completed": sum(1 for e in plan.entries if e.missing_completed),
    }

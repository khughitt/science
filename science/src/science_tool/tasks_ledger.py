"""Neutral done-ledger read/destination primitives shared by `tasks` (`--since`) and the storage migrator."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from science_tool.tasks import _HEADER_RE, Task, _parse_task_block


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

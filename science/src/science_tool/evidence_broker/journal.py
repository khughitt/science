"""The append-only record of what a run was shown.

The journal lives outside the project tree. Spend is derived by counting request events rather than
stored in a counter an actor could reset. Every operation uses one captured run-directory descriptor
and one open journal descriptor, so neither pathname nor file identity is re-resolved mid-request.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from science_model.evidence_broker import (
    MAX_BUDGET,
    MAX_INLINE_INPUTS,
    MAX_TARGET_CHARS,
    ExposureEntry,
    InlineInput,
    Outcome,
)
from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.findings.paths import (
    PathExistsError,
    PathSafetyError,
    create_regular_file_at,
    open_dir_anchored,
    open_lock_at,
    open_record_at,
    read_regular_fd,
    write_all,
)

_LOCK_SUFFIX = ".lock"

MAX_ENTRY_BYTES = 24 * MAX_TARGET_CHARS + 512
MAX_JOURNAL_BYTES = (MAX_BUDGET + MAX_INLINE_INPUTS) * MAX_ENTRY_BYTES


class JournalHandle(NamedTuple):
    """The captured run directory and open journal file."""

    dir_fd: int
    fd: int
    name: str


class JournalError(RuntimeError):
    """The journal could not be created, appended to, or read."""


def _encode_inline(inline: InlineInput) -> str:
    return json.dumps(
        {
            "event": "inline",
            "target": inline.target,
            "sha256": inline.sha256,
            "lines": inline.lines,
        },
        sort_keys=True,
    )


def _encode_request(entry: ExposureEntry) -> str:
    return json.dumps(
        {
            "event": "request",
            "op": entry.op,
            "target": entry.target,
            "pathspec": entry.pathspec,
            "commit": entry.commit,
            "sha256": entry.sha256,
            "outcome": entry.outcome.value,
        },
        sort_keys=True,
    )


def _bounded_line(encoded: str) -> bytes:
    line = (encoded + "\n").encode()
    if len(line) > MAX_ENTRY_BYTES:
        raise JournalError(
            f"the encoded entry is {len(line)} bytes, over the {MAX_ENTRY_BYTES} bound that "
            f"keeps a full journal under {MAX_JOURNAL_BYTES}"
        )
    return line


@contextmanager
def open_journal(path: Path, *, project_root: Path) -> Iterator[JournalHandle]:
    """Capture the run directory and journal inode once for all operations."""
    reject_baseline_inside_project(path, project_root)
    try:
        directory = open_dir_anchored(path.parent)
    except PathSafetyError as exc:
        raise JournalError(f"could not open the run directory {path.parent}: {exc}") from exc
    try:
        try:
            record = open_record_at(directory, path.name)
        except PathSafetyError as exc:
            raise JournalError(f"could not open journal {path}: {exc}") from exc
        try:
            yield JournalHandle(dir_fd=directory, fd=record, name=path.name)
        finally:
            os.close(record)
    finally:
        os.close(directory)


@contextmanager
def journal_lock(path: Path, *, project_root: Path) -> Iterator[JournalHandle]:
    """Serialize count, budget check, serve, delivery, and append on one handle."""
    with open_journal(path, project_root=project_root) as handle:
        try:
            descriptor = open_lock_at(handle.dir_fd, handle.name + _LOCK_SUFFIX)
        except PathSafetyError as exc:
            raise JournalError(f"could not lock {path}: {exc}") from exc
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield handle
        finally:
            os.close(descriptor)


def create_journal(path: Path, *, project_root: Path, inline: tuple[InlineInput, ...]) -> None:
    """Create exactly once and seed all validated inline entries."""
    reject_baseline_inside_project(path, project_root)
    lines = tuple(_bounded_line(_encode_inline(entry)) for entry in inline)
    try:
        directory = open_dir_anchored(path.parent, create=True)
    except PathSafetyError as exc:
        raise JournalError(f"could not create the run directory {path.parent}: {exc}") from exc
    try:
        try:
            descriptor = create_regular_file_at(directory, path.name)
        except PathExistsError as exc:
            raise JournalError(
                f"{path} already holds a journal; a run's exposure record is opened once"
            ) from exc
        except PathSafetyError as exc:
            raise JournalError(f"could not create journal {path}: {exc}") from exc
        try:
            for line in lines:
                write_all(descriptor, line)
        except PathSafetyError as exc:
            raise JournalError(f"could not seed journal {path}: {exc}") from exc
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


def append_request(handle: JournalHandle, entry: ExposureEntry) -> None:
    """Append one bounded line to the inode from which the spend was counted."""
    line = _bounded_line(_encode_request(entry))
    try:
        write_all(handle.fd, line)
    except PathSafetyError as exc:
        raise JournalError(f"could not append to journal {handle.name}: {exc}") from exc


def read_journal(handle: JournalHandle) -> tuple[ExposureEntry, ...]:
    """Parse every line or raise; damaged records never become shorter honest records."""
    try:
        text = read_regular_fd(handle.fd, MAX_JOURNAL_BYTES)
    except PathSafetyError as exc:
        raise JournalError(f"could not read journal {handle.name}: {exc}") from exc

    entries: list[ExposureEntry] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{handle.name} line {number} is not JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise JournalError(f"{handle.name} line {number} is not a JSON object")
        try:
            if event["event"] == "inline":
                entries.append(
                    ExposureEntry(
                        op="inline",
                        target=event["target"],
                        commit="",
                        sha256=event["sha256"],
                        outcome=Outcome.SERVED,
                    )
                )
            elif event["event"] == "request":
                entries.append(
                    ExposureEntry(
                        op=event["op"],
                        target=event["target"],
                        pathspec=event["pathspec"],
                        commit=event["commit"],
                        sha256=event["sha256"],
                        outcome=Outcome(event["outcome"]),
                    )
                )
            else:
                raise JournalError(
                    f"{handle.name} line {number} has unknown event {event['event']!r}"
                )
        except (KeyError, ValueError) as exc:
            raise JournalError(
                f"{handle.name} line {number} is not a journal event: {exc}"
            ) from exc
    return tuple(entries)


def count_requests(entries: tuple[ExposureEntry, ...]) -> int:
    """Count request events; supervisor-seeded inline entries spend nothing."""
    return len([entry for entry in entries if entry.op != "inline"])

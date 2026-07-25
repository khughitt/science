"""The payload output channel for budgeted commands.

A budgeted command constructs ONE sink, renders its complete payload into it, and flushes
once. Rich renderables go through ``sink.console``; plain lines through ``sink.echo``. No
payload reaches stdout until ``flush()``. After a successful file flush, a command may emit
one fixed-shape bounded control notice directly; that notice is the sole exception.

Why a channel rather than a wrapper around ``emit``'s JSON branch: a command like
``health`` renders 21 tables and a dozen messages directly. Wrapping only the final
serialization would leave all of that on stdout and write an empty ``--output`` file.
Owning the channel is what makes the ceiling payload-total and ``--output`` complete.

The sink holds characters, not rows, so it never truncates: it cannot count omitted items
nor cut without severing a table box or an ANSI escape. Semantic narrowing belongs in
projection, which runs before anything is rendered. A projected payload that still
exceeds its ceiling is a budget misconfiguration, so ``flush()`` raises -- printing
nothing rather than a misleading prefix.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import click
from rich.console import Console

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, visible_len
from science_tool.budget.registry import CommandBudget
from science_tool.styles import ColorPolicy, get_color_policy, get_console


class BudgetExceeded(click.ClickException):
    """A projected payload still exceeded its ceiling."""


class BoundedSink:
    def __init__(
        self,
        budget: CommandBudget | None,
        *,
        output_path: Path | None = None,
        command_path: str = "",
        complete_via: str = "",
    ) -> None:
        if budget is not None and output_path is None and not complete_via:
            raise ValueError("complete_via is required for a budgeted stdout sink")
        self._budget = budget
        self._output_path = output_path
        self._command_path = command_path
        self._complete_via = complete_via
        self._buffer = StringIO()
        self._console: Console | None = None
        self._flushed = False
        self._reserved_path: Path | None = None

    @property
    def console(self) -> Console:
        """A Rich console writing into this sink at the pinned budget width."""
        if self._console is None:
            selected = get_color_policy()
            render_policy = (
                ColorPolicy.NEVER
                if self._output_path is not None or selected is ColorPolicy.NEVER
                else ColorPolicy.ALWAYS
            )
            self._console = get_console(
                file=self._buffer,
                width=BUDGET_CONSOLE_WIDTH,
                color_policy=render_policy,
            )
        return self._console

    @property
    def is_file_sink(self) -> bool:
        return self._output_path is not None

    @property
    def complete_via(self) -> str:
        return self._complete_via

    @property
    def max_rows(self) -> int | None:
        """Row cap for projection, or None when nothing may be dropped.

        A file sink always returns None: ``--output PATH`` is guaranteed complete, so
        projection must not run against one.
        """
        if self._output_path is not None:
            return None
        return self._budget.max_rows if self._budget is not None else None

    def echo(self, text: str = "") -> None:
        self._buffer.write(text + "\n")

    def write(self, text: str) -> None:
        """Append raw text with no trailing newline added."""
        self._buffer.write(text)

    @contextmanager
    def reserve_output(self) -> Iterator[None]:
        """Reserve a writable sibling temp file for a mutation-before-report flow.

        Entering the context proves that the output parent exists, the destination is
        not a directory, and a same-directory temporary file can be created. The final
        destination is left untouched until ``flush()`` atomically replaces it. Any
        exception before or during flush removes the reservation.
        """
        if self._output_path is None:
            raise ValueError("reserve_output requires a file sink")
        if self._reserved_path is not None:
            raise RuntimeError("output is already reserved")
        reserved = self._create_temp_path()
        self._reserved_path = reserved
        try:
            yield
        finally:
            reserved.unlink(missing_ok=True)
            self._reserved_path = None

    def flush(self) -> None:
        if self._flushed:
            return
        text = self._buffer.getvalue()

        if self._output_path is not None:
            self._flush_file(text)
            self._flushed = True
            return

        if self._budget is not None:
            size = visible_len(text)
            if size > self._budget.max_chars:
                raise self._exceeded(size)

        # Rich already applied the caller's color policy while rendering into the
        # buffer. Preserve explicit ALWAYS, strip explicit NEVER, and let Click make
        # its normal terminal decision for AUTO.
        color_policy = get_color_policy()
        color = (
            True
            if color_policy is ColorPolicy.ALWAYS
            else False
            if color_policy is ColorPolicy.NEVER
            else None
        )
        click.echo(text, nl=False, color=color)
        self._flushed = True

    def _create_temp_path(self) -> Path:
        assert self._output_path is not None
        if self._output_path.is_dir():
            raise IsADirectoryError(f"{self._output_path} is a directory")
        parent = self._output_path.parent
        if not parent.is_dir():
            raise FileNotFoundError(f"output parent does not exist: {parent}")
        fd, raw_path = tempfile.mkstemp(
            dir=parent,
            prefix=f".{self._output_path.name}.",
            suffix=".tmp",
        )
        os.close(fd)
        return Path(raw_path)

    def _flush_file(self, text: str) -> None:
        assert self._output_path is not None
        temp_path = self._reserved_path or self._create_temp_path()
        try:
            with temp_path.open("w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self._output_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _exceeded(self, size: int) -> BudgetExceeded:
        assert self._budget is not None
        return BudgetExceeded(
            f"{self._command_path or 'command'} produced {size} visible chars after "
            f"projection, over its {self._budget.max_chars} ceiling. "
            f"Nothing was printed. For the complete payload run:\n  {self._complete_via}"
        )

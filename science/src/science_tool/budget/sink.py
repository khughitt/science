"""The payload output channel for budgeted commands.

A budgeted command constructs ONE sink, renders its complete payload into it, and flushes
once. Rich renderables go through ``sink.console``; plain lines through ``sink.echo``. No
payload reaches stdout until ``flush()``. After a successful file flush, a command may emit
one fixed success confirmation directly; that bounded control notice is the sole exception.

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

from io import StringIO
from pathlib import Path

import click
from rich.console import Console

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, visible_len
from science_tool.budget.registry import CommandBudget
from science_tool.styles import get_console


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

    @property
    def console(self) -> Console:
        """A Rich console writing into this sink at the pinned budget width."""
        if self._console is None:
            self._console = get_console(file=self._buffer, width=BUDGET_CONSOLE_WIDTH)
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

    def flush(self) -> None:
        if self._flushed:
            return
        text = self._buffer.getvalue()

        if self._output_path is not None:
            self._output_path.write_text(text, encoding="utf-8")
            self._flushed = True
            return

        if self._budget is not None:
            size = visible_len(text)
            if size > self._budget.max_chars:
                raise self._exceeded(size)

        click.echo(text, nl=False)
        self._flushed = True

    def _exceeded(self, size: int) -> BudgetExceeded:
        assert self._budget is not None
        return BudgetExceeded(
            f"{self._command_path or 'command'} produced {size} visible chars after "
            f"projection, over its {self._budget.max_chars} ceiling. "
            f"Nothing was printed. For the complete payload run:\n  {self._complete_via}"
        )

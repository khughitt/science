from __future__ import annotations

from pathlib import Path

import pytest
from rich.table import Table

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH
from science_tool.budget.registry import CommandBudget, PayloadShape
from science_tool.budget.sink import BoundedSink, BudgetExceeded

ROWS_BUDGET = CommandBudget(max_chars=100, shape=PayloadShape.ROWS, max_rows=5)
TASKS_COMPLETE = "science tasks list --output tasks.json"
HEALTH_COMPLETE = "science health --output health.json"


def test_echo_reaches_stdout_only_after_flush(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    sink.echo("hello")
    assert capsys.readouterr().out == ""
    sink.flush()
    assert capsys.readouterr().out == "hello\n"


def test_console_output_is_captured_by_the_sink(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    table = Table(title="T")
    table.add_column("C")
    table.add_row("x")
    sink.console.print(table)
    sink.flush()
    assert "┏" in capsys.readouterr().out


def test_console_uses_the_pinned_width() -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    assert sink.console.width == BUDGET_CONSOLE_WIDTH


def test_over_budget_flush_prints_nothing_and_raises(capsys) -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=10, shape=PayloadShape.ROWS, max_rows=5),
        command_path="tasks list",
        complete_via=TASKS_COMPLETE,
    )
    sink.echo("x" * 50)
    with pytest.raises(BudgetExceeded) as excinfo:
        sink.flush()
    assert capsys.readouterr().out == ""
    assert "tasks list" in str(excinfo.value)
    assert "--output" in str(excinfo.value)


def test_many_sections_share_one_command_total_ceiling() -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=100, shape=PayloadShape.REPORT),
        command_path="health",
        complete_via=HEALTH_COMPLETE,
    )
    for _ in range(3):
        sink.echo("y" * 50)
    with pytest.raises(BudgetExceeded):
        sink.flush()


def test_file_sink_is_never_truncated(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    sink = BoundedSink(
        CommandBudget(max_chars=10, shape=PayloadShape.REPORT),
        output_path=target,
        command_path="health",
    )
    sink.echo("y" * 10_000)
    sink.flush()
    assert target.read_text() == "y" * 10_000 + "\n"


def test_file_sink_reports_no_row_cap(tmp_path: Path) -> None:
    """--output is complete, so projection must not run against a file sink."""
    sink = BoundedSink(ROWS_BUDGET, output_path=tmp_path / "o.json", command_path="tasks list")
    assert sink.max_rows is None
    assert sink.is_file_sink is True


def test_stdout_sink_reports_the_budget_row_cap() -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    assert sink.max_rows == 5


def test_budgeted_stdout_sink_requires_complete_via() -> None:
    with pytest.raises(ValueError, match="complete_via"):
        BoundedSink(ROWS_BUDGET, command_path="tasks list")


def test_unbudgeted_command_is_unbounded(capsys) -> None:
    sink = BoundedSink(None, command_path="tasks add")
    sink.echo("z" * 100_000)
    sink.flush()
    assert len(capsys.readouterr().out) == 100_001


def test_ansi_does_not_count_against_the_ceiling(capsys) -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=12, shape=PayloadShape.ROWS, max_rows=5),
        command_path="tasks list",
        complete_via=TASKS_COMPLETE,
    )
    sink.echo("\x1b[1;31m" + "x" * 9 + "\x1b[0m")
    sink.flush()
    assert "x" * 9 in capsys.readouterr().out


def test_flush_is_idempotent(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    sink.echo("once")
    sink.flush()
    sink.flush()
    assert capsys.readouterr().out == "once\n"

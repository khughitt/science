from __future__ import annotations

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, visible_len
from science_tool.styles import get_console


def test_visible_len_ignores_ansi_escapes() -> None:
    assert visible_len("hello") == 5
    assert visible_len("\x1b[1;31mhello\x1b[0m") == 5


def test_visible_len_counts_newlines() -> None:
    assert visible_len("ab\ncd") == 5


def test_get_console_honours_an_explicit_width() -> None:
    console = get_console(width=BUDGET_CONSOLE_WIDTH)
    assert console.width == BUDGET_CONSOLE_WIDTH


def test_explicit_width_beats_terminal_columns(monkeypatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    assert get_console(width=BUDGET_CONSOLE_WIDTH).width == BUDGET_CONSOLE_WIDTH


def test_width_console_is_not_cached_across_calls() -> None:
    """A width-specific console must never poison the context-cached default."""
    a = get_console(width=50)
    b = get_console(width=120)
    assert a is not b
    assert (a.width, b.width) == (50, 120)
